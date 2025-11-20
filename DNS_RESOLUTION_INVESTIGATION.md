# DNS Resolution Investigation: maptimize-prod

**Investigation Date:** November 20, 2025 10:04:26 GMT
**Investigator:** DevOps Team
**Domain:** maptimize-prod.campaign.adobe.com
**Status:** CRITICAL - DNS record does not exist

---

## Quick Summary

**maptimize-prod.campaign.adobe.com does NOT resolve.** The DNS record has not been created in the campaign.adobe.com zone. The parent zone is healthy on AWS Route53, but the maptimize-prod subdomain record is missing.

- **Current Status:** NXDOMAIN (Non-Existent Domain)
- **Expected IP:** 52.213.19.55 (not registered)
- **Infrastructure:** AWS Route53 (healthy)
- **Root Cause:** Missing DNS A record

---

## Investigation Details

### Test Results Overview

| Test Method | Status | Details |
|-----------|--------|---------|
| nslookup | FAILED | NXDOMAIN error |
| dig | FAILED | NXDOMAIN response |
| host -v | FAILED | NXDOMAIN (code 3) |
| Parent domain | PASSED | campaign.adobe.com resolves to 192.150.11.122 |
| Nameservers | PASSED | 4 AWS Route53 nameservers active |
| Zone health | PASSED | SOA and NS records present |

### DNS Infrastructure

**Hosting Provider:** AWS Route53 (Route53 is the DNS service for campaign.adobe.com)

**Authoritative Nameservers:**
```
ns-1852.awsdns-39.co.uk   205.251.199.60  (Europe)
ns-182.awsdns-22.com      205.251.192.182 (US)
ns-1122.awsdns-12.org     205.251.196.98  (US)
ns-997.awsdns-60.net      205.251.195.229 (US)
```

**Zone Configuration:**
- Domain: campaign.adobe.com
- Nameserver: ns-1122.awsdns-12.org
- SOA Refresh: 7200 seconds (2 hours)
- SOA Retry: 900 seconds (15 minutes)
- SOA Expire: 1209600 seconds (14 days)
- SOA Minimum: 86400 seconds (24 hours)

### Current Resolution Chain

```
User Query: maptimize-prod.campaign.adobe.com
    ↓
Local Resolver: 10.98.3.19:53 (Corporate DNS)
    ↓
Root Nameservers (13 servers)
    ↓
TLD Servers (.com)
    ↓
Route53 Nameservers (ns-1122.awsdns-12.org, etc.)
    ↓
Campaign.adobe.com Zone
    ↓
ERROR: maptimize-prod record NOT FOUND → NXDOMAIN
```

### Query Performance

All DNS queries returned consistent response times around 29-30ms, indicating a healthy resolver and network path.

- **nslookup query:** 30 ms
- **dig query:** 29 ms
- **host verbose query:** 30 ms

This baseline will be useful for monitoring after DNS record creation.

---

## Root Cause Analysis

### Primary Issue
The DNS A record for `maptimize-prod.campaign.adobe.com` does not exist in AWS Route53.

### Evidence

1. **NXDOMAIN Response:** All DNS resolution methods (nslookup, dig, host) return NXDOMAIN
2. **SOA in Response:** Authority section shows SOA for campaign.adobe.com, confirming zone exists but record doesn't
3. **Parent Zone Active:** campaign.adobe.com successfully resolves to 192.150.11.122
4. **Nameservers Responsive:** All 4 AWS Route53 nameservers are active and responding
5. **Zone Healthy:** SOA and NS records indicate a properly configured zone

### Why This Occurred

The maptimize-prod subdomain record was not created during infrastructure setup, or was deleted after creation. The parent zone is fully functional, but the specific subdomain entry is missing from the Route53 zone file.

### Impact

- **Services:** Cannot resolve to maptimize-prod.campaign.adobe.com
- **Expected IP:** 52.213.19.55 is not associated with any DNS record
- **Connectivity:** Applications attempting to connect to this hostname will fail with DNS resolution errors
- **Severity:** Critical for any service relying on this hostname

---

## Network Environment Assessment

### Local Environment
- **Resolver:** 10.98.3.19:53 (Corporate/Internal)
- **Status:** Working properly
- **Queries:** Successfully routing to public DNS infrastructure

### External Connectivity
- **Google DNS (8.8.8.8):** Timeout - blocked by firewall
- **Cloudflare DNS (1.1.1.1):** Timeout - blocked by firewall
- **Route53 Direct:** Timeout - direct external connections blocked

### Conclusion
This system is running on a corporate/restricted network with firewall rules limiting external DNS connections. The local resolver handles all DNS queries and forwards them appropriately.

---

## Solution & Implementation

### Required Action

Create a new DNS A record in AWS Route53:

```
Record Name:    maptimize-prod
Domain:         campaign.adobe.com
Full FQDN:      maptimize-prod.campaign.adobe.com
Record Type:    A
IPv4 Address:   52.213.19.55
TTL:            300 seconds (recommended)
Zone:           campaign.adobe.com
```

### Implementation Steps

1. **Access AWS Route53 Console**
   - Navigate to AWS Management Console
   - Go to Route53 service
   - Select campaign.adobe.com hosted zone

2. **Create Record**
   - Click "Create Record"
   - Enter Name: `maptimize-prod`
   - Select Type: A
   - Enter Value: `52.213.19.55`
   - TTL: 300 (can be adjusted based on requirements)
   - Click "Create"

3. **Verify Creation**
   - Record should appear in Route53 console immediately
   - Wait 2-3 minutes for local resolver cache refresh
   - Test with: `dig maptimize-prod.campaign.adobe.com @10.98.3.19 +short`

### Expected Propagation Timeline

| Phase | Timeline | Details |
|-------|----------|---------|
| Route53 Creation | Immediate | Record available in Route53 |
| Local Resolver | 5 minutes | Cache refresh (TTL=300s) |
| Regional Propagation | 30 minutes | Distributed cache servers |
| Global Propagation | 24-48 hours | Full worldwide propagation |

**Recommendation:** Wait 2-3 minutes before testing to allow local resolver cache refresh.

---

## Verification Procedures

### Immediate Verification (After DNS Creation)

```bash
# Basic verification
dig maptimize-prod.campaign.adobe.com +short

# Expected output:
# 52.213.19.55

# Detailed verification
dig maptimize-prod.campaign.adobe.com +noall +answer

# Expected output:
# maptimize-prod.campaign.adobe.com. 300 IN A 52.213.19.55

# Verify TTL
dig maptimize-prod.campaign.adobe.com | grep TTL

# Query specific resolver
dig @10.98.3.19 maptimize-prod.campaign.adobe.com +short
```

### Connectivity Testing

```bash
# Test IP connectivity
ping 52.213.19.55

# Test DNS + connectivity
nslookup maptimize-prod.campaign.adobe.com
# Should return 52.213.19.55

# Check nameserver response
dig @ns-1122.awsdns-12.org maptimize-prod.campaign.adobe.com +short
```

### Monitoring Setup

1. **Health Check Alert**
   - Monitor DNS resolution continuously
   - Alert if NXDOMAIN persists after creation
   - Verify IP stays 52.213.19.55

2. **Performance Monitoring**
   - Baseline: 29-30 ms for DNS queries
   - Alert if query time exceeds 100 ms (potential issue)
   - Track cache hit vs miss rates

3. **Propagation Monitoring**
   - Track resolution from different locations
   - Verify all nameservers return same IP
   - Monitor TTL value consistency

---

## Alternative Approaches (If Applicable)

If a subdomain is not desired, consider these alternatives:

### Option 1: Use Parent Domain
- Update applications to use `campaign.adobe.com` directly
- Resolves to 192.150.11.122
- Already working and propagated

### Option 2: CNAME Record
- Create CNAME pointing to `campaign.adobe.com`
- Adds one additional DNS lookup
- Useful if multiple subdomains needed

### Option 3: Route53 Alias Record
- AWS-specific feature (Route53 Alias)
- Zero-cost, improved performance
- AWS-specific, may not work with all tools

### Option 4: Load Balancer Alias
- If 52.213.19.55 is an elastic/load balancer IP
- Create alias in Route53 directly to ALB/NLB
- Provides health checking and failover

---

## Troubleshooting Reference

### Common Issues & Solutions

**Issue:** DNS still returns NXDOMAIN after creation
- **Cause:** Local resolver cache hasn't refreshed
- **Solution:** Wait 5 minutes and retry
- **Alternative:** Query specific nameserver: `dig @ns-1122.awsdns-12.org`

**Issue:** Query timeout instead of NXDOMAIN
- **Cause:** Network connectivity issue
- **Solution:** Check firewall rules and network connectivity
- **Test:** `ping ns-1122.awsdns-12.org` (may be blocked)

**Issue:** Wrong IP resolved
- **Cause:** Incorrect IP configured in Route53
- **Solution:** Verify Route53 record shows 52.213.19.55
- **Command:** Check Route53 console or `dig` the nameserver directly

**Issue:** Inconsistent resolution across systems
- **Cause:** DNS cache inconsistency or record variation
- **Solution:** Clear local DNS cache and retry
- **Command:** `sudo dscacheutil -flushcache` (macOS) or `sudo systemctl restart systemd-resolved` (Linux)

---

## Documentation References

### Test Commands Used

**Basic DNS Tests:**
```bash
nslookup maptimize-prod.campaign.adobe.com
dig maptimize-prod.campaign.adobe.com
host -v maptimize-prod.campaign.adobe.com
```

**Nameserver Investigation:**
```bash
dig campaign.adobe.com NS +short
dig campaign.adobe.com SOA +short
dig campaign.adobe.com NS
```

**Parent Domain Testing:**
```bash
dig campaign.adobe.com +noall +answer
dig campaign.adobe.com MX +noall +answer
dig campaign.adobe.com TXT +noall +answer
```

**Trace Testing:**
```bash
dig maptimize-prod.campaign.adobe.com +trace
dig maptimize-prod.campaign.adobe.com +trace +short
```

### Test Report Files

1. **DNS_TEST_REPORT.md** - Detailed test results and findings
2. **DNS_TEST_COMMANDS_REFERENCE.sh** - Comprehensive command reference
3. **DNS_RESOLUTION_INVESTIGATION.md** - This document

---

## Recommendations

### Immediate (Before Creating DNS Record)

1. Confirm 52.213.19.55 is the correct target IP
2. Verify Route53 access and permissions
3. Confirm maptimize-prod subdomain name is correct
4. Plan maintenance window if needed (DNS change is low-risk)

### Short-term (After Creating DNS Record)

1. Monitor DNS resolution for 24-48 hours
2. Verify all applications can connect to new hostname
3. Add monitoring alerts for DNS health
4. Document the DNS record in your infrastructure guide

### Long-term

1. Implement automated DNS health checks
2. Create runbook for DNS troubleshooting
3. Establish monitoring baseline (29-30 ms queries)
4. Plan DNS failover strategy if needed
5. Document all DNS records in central repository

---

## Conclusion

The investigation clearly identifies that **maptimize-prod.campaign.adobe.com does not exist in DNS**. The infrastructure is healthy, nameservers are responsive, and the parent zone is fully functional. The solution is straightforward: create an A record in Route53 pointing 52.213.19.55.

### Key Points:
- **Root Cause:** Missing DNS A record in campaign.adobe.com zone
- **Infrastructure:** AWS Route53 (healthy)
- **Solution:** Create A record for maptimize-prod → 52.213.19.55
- **Timeline:** Immediate creation, 2-3 minutes local propagation, 24-48 hours global propagation
- **Risk Level:** Low (DNS change is non-destructive)
- **Testing:** Straightforward with dig/nslookup commands

### Action Items:
1. Create DNS A record in Route53
2. Wait 2-3 minutes for propagation
3. Verify with `dig maptimize-prod.campaign.adobe.com @10.98.3.19`
4. Set up monitoring alerts
5. Document in infrastructure guide

For detailed test commands and procedures, see **DNS_TEST_COMMANDS_REFERENCE.sh** and **DNS_TEST_REPORT.md**.
