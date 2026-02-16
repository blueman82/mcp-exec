---
name: campaign-nlserver-status
description: Check nlserver process health and status for Campaign instance
---

# Campaign nlserver Process Status

Check nlserver process health and status.

## Arguments

```
/campaign-nlserver-status <instance> [--container=<n>]
```

- `instance`: Campaign instance name (required)
- `--container`: Container number 1, 2, 3 (default: 1)

## Diagnostic Script (Preferred)

Run the comprehensive diagnostic script for a full JSON report in one SSH call:

```bash
ssh -o ConnectTimeout=30 <instance>-<container>.campaign.adobe.com "bash -s" \
  < ~/.claude/scripts/campaign-diagnose.sh 2>/dev/null
```

This covers: endpoint test, system health, nlserver pdump, watchdog crashes, core dumps, DB status, web.log errors, and login monitor — all in one call with JSON output.

Use the manual commands below only when the script is unavailable or you need to investigate a specific area in more detail.

## Manual Instructions

### Container Awareness

Campaign instances typically have multiple containers (e.g., `<instance>-1`, `<instance>-2`, `<instance>-3`). The alert may fire for one container but the issue may originate from another. Check which containers exist:

```bash
# List containers by checking /etc/hosts on the alerted container
ssh <instance>-1.campaign.adobe.com \
  "grep '<instance>' /etc/hosts 2>/dev/null"
```

Not all checks need to run on every container — use judgement based on the problem:
- **Login monitor / web module alerts**: Check the alerted container first. If healthy, the issue may have been transient or on a different container behind the load balancer.
- **DB connectivity issues**: Any container can check — they share the same RDS.
- **Workflow / MTA issues**: These typically run on the console container (usually `-1`), not on all containers.
- **Core dumps / crashes**: Check the specific container where the crash occurred (the PID in the watchdog log identifies the container).

### Step 0: Run Runbook Endpoint Test FIRST

Before pdump or any other check, run the endpoint test per the Login Monitor runbook. This tests the full apache → web module → database path in one command.

**For ACC instances (SOAP Logon test):**
```bash
ssh <instance>-<container>.campaign.adobe.com \
  "curl -sk --max-time 10 -w '\nHTTP:%{http_code} TIME:%{time_total}s' -X POST \
   -H 'Content-Type: text/xml; charset=utf-8' \
   -H 'SOAPAction: xtk:session#Logon' \
   -d '<?xml version=\"1.0\"?><soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:urn=\"urn:xtk:session\"><soapenv:Header/><soapenv:Body><urn:Logon><urn:sessiontoken/><urn:strLogin>test</urn:strLogin><urn:strPassword>test</urn:strPassword><urn:elemParameters/></urn:Logon></soapenv:Body></soapenv:Envelope>' \
   'https://localhost:443/nl/jsp/soaprouter.jsp'" 2>&1
```

- **PASS**: `XSV-350012 Invalid login or password` (HTTP 403) — full path works, credentials correctly rejected
- **FAIL**: SOAP fault with error detail (e.g., `XSV-350063 No data source defined`) — application error
- **HANG**: Web module unresponsive — check process state, load, memory

**For ACS instances (amcPing test):**
```bash
ssh <instance>-<container>.campaign.adobe.com \
  "curl -skS --max-time 10 -w '\nHTTP:%{http_code} TIME:%{time_total}s SIZE:%{size_download}' \
   'https://localhost:443/jssp/nms/amcPing.jssp?__sessiontoken=test'" 2>&1
```

- **PASS**: `Authentication failure` (HTTP 403, 534 bytes) — full path works
- **FAIL**: HTTP 500 (546 bytes, text/plain) — web module error
- **HANG**: Web module unresponsive

### Step 1: Detect nl6 vs nl7 and Run pdump

```bash
# Detect which version is installed
ssh <instance>-<container>.campaign.adobe.com \
  "if [ -d /usr/local/neolane/nl7 ]; then
     sudo su - neolane -c '/usr/local/neolane/nl7/bin/nlserver pdump'
   elif [ -d /usr/local/neolane/nl6 ]; then
     sudo su - neolane -c '/usr/local/neolane/nl6/bin/nlserver pdump'
   else
     echo 'ERROR: Neither nl6 nor nl7 found'
   fi" 2>&1 | tail -50
```

**Note on log paths:**
- nl7: `/usr/local/neolane/nl7/log/default/` (web.log, watchdog.log)
- nl6: `/usr/local/neolane/nl6/var/default/log/` (web.log, watchdog.log) — note the different path structure

### Process Reference

| Process | Description | Typical Memory |
|---------|-------------|----------------|
| watchdog | Master process | 15-30 MB |
| web@default | Web server | 1-4 GB |
| mta@instance | Mail Transfer Agent | 200-800 MB |
| wfserver@instance | Workflow server | 30-100 MB |
| inMail@instance | Bounce processing | 40-80 MB |
| sms@instance | SMS connector | 30-60 MB |

### Status Indicators

| Status | Meaning |
|--------|---------|
| idle | Running, waiting for work |
| active | Currently executing |
| starting | Initializing |
| stopped | Not running |

### Check Logs

```bash
# nl7 log paths:
#   /usr/local/neolane/nl7/log/default/web.log
#   /usr/local/neolane/nl7/log/default/watchdog.log
#   /usr/local/neolane/nl7/log/<instance>/mta.log, runwf.log, etc.

# nl6/v8 log paths (different structure!):
#   /usr/local/neolane/nl6/var/default/log/web.log
#   /usr/local/neolane/nl6/var/default/log/watchdog.log
#   /usr/local/neolane/nl6/var/<instance>/log/mta.log, etc.

# Login monitor probe log (NR integration):
#   /var/log/newrelic/loginmonitor.log

# Detect and tail appropriate web log:
ssh <instance>-1.campaign.adobe.com \
  "if [ -f /usr/local/neolane/nl7/log/default/web.log ]; then
     sudo tail -20 /usr/local/neolane/nl7/log/default/web.log
   elif [ -f /usr/local/neolane/nl6/var/default/log/web.log ]; then
     sudo tail -20 /usr/local/neolane/nl6/var/default/log/web.log
   fi"

# Watchdog crash history:
ssh <instance>-1.campaign.adobe.com \
  "sudo grep -i 'crash\|SRV-810' /usr/local/neolane/nl7/log/default/watchdog.log 2>/dev/null || \
   sudo grep -i 'crash\|SRV-810' /usr/local/neolane/nl6/var/default/log/watchdog.log 2>/dev/null | tail -10"
```

### Restart Services

```bash
# Restart all
ssh <instance>-1.campaign.adobe.com \
  "sudo su - neolane -c '/usr/local/neolane/nl6/bin/nlserver restart'"

# Restart specific module
ssh <instance>-1.campaign.adobe.com \
  "sudo su - neolane -c '/usr/local/neolane/nl6/bin/nlserver restart web@default'"
```

### Output Format

Present pdump output with:
- Process list with memory usage
- Status indicators
- Any processes with unusual memory or status
- Log path references
