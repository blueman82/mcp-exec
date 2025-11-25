# ketchup_maintenance_fetcher/CLAUDE.md

Service-specific guidance for the Ketchup Maintenance Fetcher service. For shared patterns and repository-wide conventions, see [/projects/ketchup/CLAUDE.md](../CLAUDE.md).

## Service Overview

The Maintenance Fetcher service detects Adobe Campaign maintenance events by polling the Raven SOAP API daily and propagating maintenance data to downstream systems. This is the **ONLY** service in the Ketchup ecosystem using SOAP - all other services use REST APIs.

**Core Responsibilities**:
- Fetch daily maintenance schedules from Adobe's Raven SOAP API
- Parse SOAP XML responses containing embedded JSON maintenance data
- Cache maintenance records in DynamoDB with 24-hour TTL
- Run as scheduled singleton service on prod1 only
- Provide file-based health monitoring for Docker healthchecks

**Key Characteristics**:
- **LOC**: ~290 lines total (main.py: ~100, scheduler.py: ~190)
- **Files**: 2 Python files + 1 Dockerfile
- **Schedule**: Daily at 1:30 AM UTC
- **Unique**: Only SOAP-based service (manual SOAP with aiohttp/defusedxml)
- **Deployment**: Singleton on prod1 only (excluded from prod2)

## Architecture

### File Structure

```
ketchup_maintenance_fetcher/
├── __init__.py                # Package marker (64 bytes)
├── main.py                    # Maintenance fetch logic (~100 LOC)
├── scheduler.py               # Daily scheduler with health monitoring (~190 LOC)
└── CLAUDE.md                  # This file

Related files:
├── infrastructure/
│   ├── Dockerfile.maintenance_fetcher           # Multi-stage Docker build
│   ├── requirements-maintenance-fetcher.txt     # Python dependencies (includes zeep)
│   ├── healthcheck-maintenance-fetcher.sh       # Health check script
│   └── docker-compose.yml                       # Container configuration
├── packages/
│   ├── integrations/
│   │   └── raven_maintenance.py                 # SOAP client implementation (~144 LOC)
│   └── core/typed_di/service_registrations/
│       ├── protocols/maintenance_protocols.py   # Protocol definitions
│       └── registrations/maintenance_registrations.py  # TypedDI registration
└── tests/
    └── unit/integrations/
        └── test_raven_maintenance.py            # SOAP client unit tests
```

### Data Flow

```
┌──────────────────────┐
│  Scheduler (1:30 AM) │
│    scheduler.py      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Fetch Orchestration │
│      main.py         │
└──────────┬───────────┘
           │
           ├─────────────────────────────────────┐
           │                                     │
           ▼                                     ▼
┌──────────────────────┐              ┌──────────────────┐
│  TypedDI Container   │              │  Health Monitor  │
│  (Protocol Resolution)│              │  (File-based)    │
└──────────┬───────────┘              └──────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│         RavenMaintenanceClient (SOAP)                │
│  packages/integrations/raven_maintenance.py          │
└──────────┬───────────────────────────────────────────┘
           │
           ├─── Build SOAP XML Request
           ├─── POST to Adobe Raven API
           ├─── Parse SOAP XML Response
           └─── Extract JSON from XML
           │
           ▼
┌──────────────────────┐
│  DynamoDB Cache      │
│  (24-hour TTL)       │
└──────────────────────┘
```

### Component Interaction

1. **Scheduler** (`scheduler.py`):
   - Calculates time until 1:30 AM UTC daily
   - Updates health status every minute during idle
   - Triggers maintenance fetch at scheduled time
   - Handles graceful shutdown on SIGTERM/SIGINT

2. **Fetch Orchestration** (`main.py`):
   - Checks `KETCHUP_MAINTENANCE_FETCHER_ENABLED` feature flag
   - Initializes TypedDI container
   - Resolves `RavenMaintenanceClientProtocol` and `DynamoDBStoreProtocol`
   - Coordinates fetch and storage operations
   - Ensures cleanup on exit

3. **SOAP Client** (`raven_maintenance.py`):
   - Manually constructs SOAP XML requests (not using zeep library)
   - Sends HTTP POST with SOAP envelope
   - Parses SOAP XML responses using defusedxml (prevents XXE attacks)
   - Extracts JSON data embedded in XML
   - Returns structured maintenance records

## SOAP Integration

### Why SOAP? (Unique in Ketchup)

The Maintenance Fetcher is the **ONLY** service using SOAP protocol. All other Ketchup services use modern REST APIs. This is because:
- Adobe's Raven maintenance system predates REST and only exposes SOAP endpoints
- Legacy Adobe Campaign infrastructure requires SOAP for maintenance data
- SOAP envelope format embeds JSON data within XML (hybrid approach)

**Important**: Despite `zeep` being in `requirements-maintenance-fetcher.txt`, the implementation uses **manual SOAP** with `aiohttp` + `defusedxml`, not the zeep library.

### SOAP Client Implementation

#### Manual SOAP Request Construction

```python
# From raven_maintenance.py:_build_soap_request()
soap_body = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <tns:maintenanceData xmlns:tns="urn:ketchup:maintenanceData">
      <tns:sessiontoken>{username}/{password}</tns:sessiontoken>
      <tns:maintenanceDate>{date}</tns:maintenanceDate>
    </tns:maintenanceData>
  </soap:Body>
</soap:Envelope>'''
```

#### HTTP POST with SOAP Headers

```python
headers = {
    "Content-Type": "application/xml",
    "SOAPAction": "ketchup:maintenanceData#maintenanceData"
}

async with aiohttp.ClientSession() as session:
    async with session.post(
        endpoint,
        data=soap_body,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=30)
    ) as response:
        xml_text = await response.text()
```

#### Secure XML Parsing (XXE Prevention)

```python
# Uses defusedxml to prevent XXE attacks
from defusedxml import ElementTree as ET

root = ET.fromstring(xml_text)  # Disables external entities, DTD processing

# Find maintenanceData element with namespace handling
namespaces = {
    'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
    'ns': 'urn:ketchup:maintenanceData'
}
maintenance_elem = root.find('.//ns:maintenanceData', namespaces)
```

#### JSON Extraction from SOAP Response

```python
# SOAP response embeds JSON within XML tags
json_text = maintenance_elem.text
maintenance_records = orjson.loads(json_text)

# Returns: [{"customer": "...", "releases": [{"instances": [...]}]}]
```

### Adobe Raven API Endpoints

**Base URL**: Retrieved from AWS Secrets Manager
- Key: `raven_maintenance_endpoint`
- Default: `https://raven-rt-prod2.campaign.adobe.com`
- Path appended: `/nl/jsp/soaprouter.jsp`

**Full Endpoint**: `https://raven-rt-prod2.campaign.adobe.com/nl/jsp/soaprouter.jsp`

**Authentication**:
- Method: Session token in SOAP body
- Format: `{username}/{password}`
- Credentials stored in AWS Secrets Manager:
  - `raven_maintenance_email_username`
  - `raven_maintenance_email_password`

**Request Format**:
- Method: `POST`
- Content-Type: `application/xml`
- SOAPAction: `ketchup:maintenanceData#maintenanceData`
- Timeout: 30 seconds

**Response Format**:
- SOAP XML envelope containing JSON data
- JSON structure:
  ```json
  [
    {
      "customer": "Samsung CIS",
      "releases": [
        {
          "instances": [
            {
              "instance_name": "samsungcis_mkt_prod3",
              "starts_at": "2025-10-06T04:30:00Z"
            }
          ],
          "release": "Build Upgrade",
          "release_url": "https://uco.adobe-campaign.com/release-summary/9517"
        }
      ]
    }
  ]
  ```

### Security Considerations

1. **XXE Attack Prevention**: Uses `defusedxml` instead of standard `xml.etree.ElementTree`
   - Disables external entity resolution
   - Prevents DTD processing
   - Blocks entity expansion attacks (Billion Laughs)

2. **Credential Management**: All credentials from AWS Secrets Manager, never hardcoded

3. **Timeout Protection**: 30-second timeout prevents hanging connections

4. **Error Handling**: Proper exception catching for `ClientError`, `ParseError`, `JSONDecodeError`

## Environment Variables

### Required Variables

| Variable | Purpose | Example Value | Source |
|----------|---------|---------------|--------|
| `AWS_REGION` | AWS services region | `eu-west-1` | docker-compose.yml |
| `DYNAMODB_TABLE_NAME` | DynamoDB table for cache | `ketchup_channel_information` | docker-compose.yml |
| `AWS_SECRET_NAME` | Secrets Manager secret name | `Ketchup_Token_Secrets` | docker-compose.yml |
| `TZ` | Timezone for scheduler | `UTC` | **CRITICAL** - Must be UTC |

### Feature Flags

| Variable | Purpose | Default | Impact |
|----------|---------|---------|--------|
| `KETCHUP_MAINTENANCE_FETCHER_ENABLED` | Enable/disable fetching | `true` | If `false`, service runs but skips fetch |
| `KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START` | Run fetch on startup | `true` | If `false`, waits until 1:30 AM |

### Optional Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `LOG_LEVEL` | Logging verbosity | `INFO` | Options: DEBUG, INFO, WARNING, ERROR |
| `PYTHONPATH` | Python module search path | `/app` | Required for package imports |

### Critical: TZ=UTC Requirement

**Why UTC is Critical**:
- Scheduler calculates "1:30 AM" based on system timezone
- Docker containers may default to host timezone or container timezone
- Inconsistent timezone causes schedule drift (e.g., 1:30 AM PST ≠ 1:30 AM UTC)
- Adobe's maintenance schedules are in UTC

**Impact of Missing TZ=UTC**:
- Scheduler runs at wrong time (off by timezone offset)
- Maintenance detection misses time-sensitive events
- Health checks may fail due to unexpected schedule

**Configuration** (from docker-compose.yml):
```yaml
ketchup-maintenance-fetcher:
  environment:
    - TZ=UTC  # Always set this!
```

## TypedDI Integration

The Maintenance Fetcher uses TypedDI for dependency resolution. All dependencies are resolved through protocol interfaces, not concrete classes.

### Required Protocols

#### RavenMaintenanceClientProtocol

**Definition**: `packages/core/typed_di/service_registrations/protocols/maintenance_protocols.py`

```python
@runtime_checkable
class RavenMaintenanceClientProtocol(Protocol):
    """Protocol for Raven SOAP API client operations."""

    async def fetch_maintenance_data(self, date: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch maintenance data for specific date (YYYY-MM-DD format)."""
        ...
```

**Implementation**: `packages/integrations/raven_maintenance.py:RavenMaintenanceClient`

**Registration**: `packages/core/typed_di/service_registrations/registrations/maintenance_registrations.py`

```python
manager.register_protocol_with_concrete_alias(
    protocol_type=RavenMaintenanceClientProtocol,
    concrete_type=RavenMaintenanceClient,
    factory=create_raven_client,
    dependencies=[DependencySpec(SecretsManagerProtocol)],
    lifetime="singleton",
)
```

**Factory Dependencies**:
- `SecretsManagerProtocol` - Retrieves Raven API credentials

#### DynamoDBStoreProtocol

**Purpose**: Store maintenance cache in DynamoDB

**Method Used**:
```python
async def store_maintenance_cache(self, date: str, data: List[Dict]) -> bool:
    """Store maintenance data with 24-hour TTL."""
```

**Cache Key**: `MAINTENANCE_CACHE_{date}` (e.g., `MAINTENANCE_CACHE_2025-10-06`)

**TTL**: 24 hours (86400 seconds) from insertion

### Dependency Resolution in main.py

```python
# Initialize TypedDI container
container = await get_unified_container()

# Resolve protocols (not concrete classes!)
soap_client = await resolve_typed(RavenMaintenanceClientProtocol)
db_store = await resolve_typed(DynamoDBStoreProtocol)

# Use resolved services
maintenance_data = await soap_client.fetch_maintenance_data(date_today)
success = await db_store.store_maintenance_cache(date=date_today, data=maintenance_data)

# Always cleanup
await cleanup_unified_container()
```

### Why TypedDI?

1. **Protocol-First Design**: Depend on interfaces, not implementations
2. **Testability**: Easy to mock protocols in unit tests
3. **Flexibility**: Swap implementations without changing main.py
4. **Type Safety**: Runtime type checking with `@runtime_checkable`
5. **Lifecycle Management**: Singleton pattern ensures single instance

## Health Checks

The Maintenance Fetcher uses **file-based health monitoring** instead of HTTP endpoints. This is because it's a scheduled service, not a web server.

### Health File Format

**Primary Health File**: `/app/health/maintenance_fetcher_health`

**Format**: `{timestamp}:{status}`

**Example**: `1730736000:idle`

**Status Values**:
- `starting` - Service initializing
- `idle` - Waiting for next scheduled run
- `running` - Currently fetching maintenance data
- `error` - Last fetch failed
- `stopped` - Service shutting down

**Update Frequency**: Every 60 seconds during idle

### Last Run Tracking

**File**: `/app/health/maintenance_fetcher_last_run`

**Format**: `{timestamp}` (Unix epoch seconds)

**Example**: `1730736000`

**Purpose**: Track when last successful fetch completed

**Updated**: After each successful maintenance fetch

### Docker Healthcheck Configuration

**Script**: `infrastructure/healthcheck-maintenance-fetcher.sh`

**Docker Configuration** (from docker-compose.yml):
```yaml
healthcheck:
  test: ["CMD", "test", "-f", "/app/health/maintenance_fetcher_health"]
  interval: 5m       # Check every 5 minutes
  timeout: 10s       # Healthcheck timeout
  retries: 3         # 3 failures = unhealthy
  start_period: 30s  # Grace period during startup
```

### Healthcheck Logic

The healthcheck script validates:

1. **Health File Exists**: `/app/health/maintenance_fetcher_health` present
2. **Recent Update**: Health file updated within last 5 minutes (300 seconds)
3. **Not in Error State**: Status is not `error`
4. **Last Fetch Recency**: Last fetch within 25 hours (90000 seconds)
   - Allows for schedule drift and retry delays
   - Daily schedule + 1-hour buffer
5. **Startup Grace Period**: 15 minutes before requiring last_fetch file

**Failure Conditions**:
- Health file missing or empty
- Health timestamp stale (>5 minutes old)
- Status is `error`
- Last fetch >25 hours ago (after startup period)

**Exit Codes**:
- `0` - Healthy
- `1` - Unhealthy (triggers Docker restart after 3 retries)

### Monitoring Health Manually

```bash
# SSH to prod1
ssh ketchup-prod1.campaign.adobe.com

# Check health status
docker exec ketchup-maintenance-fetcher cat /app/health/maintenance_fetcher_health
# Output: 1730736000:idle

# Check last run
docker exec ketchup-maintenance-fetcher cat /app/health/maintenance_fetcher_last_run
# Output: 1730736000

# Decode timestamp
date -d @1730736000
# Output: Mon Oct  6 01:30:00 UTC 2025

# View logs
docker logs -f ketchup-maintenance-fetcher
```

## Deployment

### Docker Image Build

**Dockerfile**: `infrastructure/Dockerfile.maintenance_fetcher`

**Build Strategy**: Multi-stage build
- Stage 1: Builder with gcc, g++, make for compiling dependencies
- Stage 2: Runtime with minimal dependencies

**Key Steps**:
```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y gcc g++ make curl git
RUN python -m venv /opt/venv
COPY infrastructure/requirements-maintenance-fetcher.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim
COPY --from=builder /opt/venv /opt/venv
COPY packages/ ./packages/
COPY ketchup_maintenance_fetcher/ ./ketchup_maintenance_fetcher/
CMD ["python", "/app/ketchup_maintenance_fetcher/scheduler.py"]
```

### Dependencies

**Requirements File**: `infrastructure/requirements-maintenance-fetcher.txt`

**Key Dependencies**:
- `aiohttp` - Async HTTP client for SOAP requests
- `aioboto3` - Async AWS SDK for DynamoDB
- `defusedxml` - Secure XML parsing (prevents XXE attacks)
- `orjson` - Fast JSON parsing
- `zeep` - SOAP library (listed but not used in current implementation)

**Note**: The service doesn't actually use the `zeep` library. It manually constructs SOAP requests with `aiohttp` and parses responses with `defusedxml`. The `zeep` dependency may be vestigial or reserved for future use.

### Deployment Process

**Script**: `infrastructure/deploy-ketchup.sh`

**Deploy to Prod1 Only**:
```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/projects/ketchup/infrastructure
./deploy-ketchup.sh --prod1-only
```

**Deployment Steps**:
1. Auto-increment version (e.g., `v2.360.344` → `v2.360.345`)
2. Build Docker image with new version tag
3. Push to ECR: `483013340174.dkr.ecr.eu-west-1.amazonaws.com/ketchup-maintenance-fetcher:v2.360.345`
4. Update `docker-compose.yml` on prod1 with new image tag
5. Pull new image on prod1
6. Restart container with zero downtime
7. Verify health status

**Singleton Enforcement**:
The deployment script explicitly stops/removes maintenance-fetcher on prod2:
```bash
# From deploy-ketchup.sh (lines 505-506)
docker stop ketchup-maintenance-fetcher 2>/dev/null || true
docker rm ketchup-maintenance-fetcher 2>/dev/null || true
```

This prevents duplicate scheduled jobs and conflicting maintenance fetches.

### Container Configuration

**Image**: `483013340174.dkr.ecr.eu-west-1.amazonaws.com/ketchup-maintenance-fetcher:v2.360.344`

**Restart Policy**: `unless-stopped` (restart on failure, not on manual stop)

**Logging**:
- Driver: `json-file`
- Max size: `10m` per log file
- Max files: `3` (30MB total)
- Location: `/opt/ketchup/logs/` on host

**Entry Point**: `python /app/ketchup_maintenance_fetcher/scheduler.py`

### Production Verification

```bash
# Check container status
docker ps | grep maintenance-fetcher

# View logs
docker logs -f ketchup-maintenance-fetcher

# Check health status
docker exec ketchup-maintenance-fetcher cat /app/health/maintenance_fetcher_health

# Verify DynamoDB cache
aws dynamodb get-item \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --table-name ketchup_channel_information \
  --key '{"PK": {"S": "MAINTENANCE_CACHE_2025-10-06"}}'
```

## Testing

### Unit Tests

**Location**: `tests/unit/integrations/test_raven_maintenance.py`

**Coverage**: SOAP client implementation (~266 LOC of tests)

**Test Fixtures**:
```python
@pytest.fixture
def soap_client():
    return RavenMaintenanceClient(
        endpoint="https://test.example.com/soap",
        username="test_user",
        password="test_pass"
    )

@pytest.fixture
def sample_soap_response():
    # Returns valid SOAP XML with embedded JSON
    return '''<?xml version='1.0'?>
    <SOAP-ENV:Envelope>
      <SOAP-ENV:Body>
        <maintenanceDataResponse>
          <maintenanceData>[{"customer": "..."}]</maintenanceData>
        </maintenanceDataResponse>
      </SOAP-ENV:Body>
    </SOAP-ENV:Envelope>'''
```

**Test Categories**:

1. **Successful Fetch** (`test_fetch_maintenance_data_success`)
   - Mocks aiohttp session and response
   - Verifies correct SOAP request construction
   - Validates JSON extraction from XML
   - Asserts maintenance record structure

2. **Empty Response** (`test_fetch_maintenance_data_empty_response`)
   - Tests handling of empty maintenance arrays
   - Verifies `[]` return value

3. **SOAP Request Building** (`test_build_soap_request`)
   - Validates SOAP envelope structure
   - Checks credential embedding
   - Verifies namespace declarations

4. **Response Parsing** (`test_parse_soap_response`)
   - Tests XML to JSON extraction
   - Validates namespace handling

5. **Invalid XML** (`test_parse_soap_response_invalid_xml`)
   - Verifies `ValueError` on malformed XML
   - Tests error message clarity

6. **Missing Elements** (`test_parse_soap_response_missing_element`)
   - Handles SOAP responses without maintenanceData
   - Returns empty list gracefully

7. **Invalid JSON** (`test_parse_soap_response_invalid_json`)
   - Tests JSON parsing errors
   - Validates error messages

8. **XXE Attack Prevention** (`test_parse_soap_response_xxe_attack_blocked`)
   - Verifies defusedxml blocks external entity attacks
   - Tests DTD injection prevention
   - Critical security test!

**Running Unit Tests**:
```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/projects/ketchup/tests/setup
make test-unit

# Or specifically for maintenance tests
pytest tests/unit/integrations/test_raven_maintenance.py -v
```

### Integration Tests

**Location**: `tests/integration/test_maintenance_mcp_integration.py`

**Purpose**: Test full maintenance detection workflow with MCP integration

**Scope**: End-to-end testing of:
- SOAP client → DynamoDB → Maintenance Checker → MCP → Slack

**Running Integration Tests**:
```bash
cd tests/setup
make test-integration

# Requires AWS profile: campaign_prod_v7
# Requires valid AWS credentials
```

### AI Component Tests

**Location**: `tests/unit/ai/test_maintenance_checker.py`

**Purpose**: Test maintenance instance matching and normalization logic

**Coverage**: MaintenanceChecker protocol implementation

### Test Pollution Prevention

**Issue**: Some tests globally mock `orjson.loads`, affecting other tests

**Solution** (from `test_raven_maintenance.py`):
```python
# Capture real functions at import time
_real_orjson_loads = orjson.loads
_real_orjson_dumps = orjson.dumps

@pytest.fixture(autouse=True)
def restore_orjson_functions(monkeypatch):
    """Prevent test pollution from global mocks."""
    monkeypatch.setattr(
        'packages.integrations.raven_maintenance.orjson.loads',
        _real_orjson_loads
    )
```

### Manual Testing

**Trigger Manual Fetch**:
```bash
# SSH to prod1
ssh ketchup-prod1.campaign.adobe.com

# Run one-time fetch
docker exec -it ketchup-maintenance-fetcher python /app/ketchup_maintenance_fetcher/main.py

# Check result
echo $?  # 0 = success, 1 = failure

# Verify DynamoDB
aws dynamodb get-item \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --table-name ketchup_channel_information \
  --key '{"PK": {"S": "MAINTENANCE_CACHE_2025-11-04"}}'
```

**Scheduler Testing**:
```bash
# Test RUN_ON_START behavior
docker run --rm \
  -e KETCHUP_MAINTENANCE_FETCHER_ENABLED=true \
  -e KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START=true \
  -e AWS_REGION=eu-west-1 \
  ketchup-maintenance-fetcher:latest
```

## Common Issues

### SOAP API Connectivity

**Symptom**: `aiohttp.ClientError` or connection timeout

**Possible Causes**:
1. **Network Connectivity**: VPN required to reach Adobe internal APIs
2. **Endpoint URL**: Incorrect or missing `/nl/jsp/soaprouter.jsp` path
3. **Firewall Rules**: Port 443 blocked or restricted
4. **DNS Resolution**: Cannot resolve `raven-rt-prod2.campaign.adobe.com`

**Debugging**:
```bash
# Test DNS resolution
nslookup raven-rt-prod2.campaign.adobe.com

# Test connectivity
curl -v https://raven-rt-prod2.campaign.adobe.com/nl/jsp/soaprouter.jsp

# Check from container
docker exec ketchup-maintenance-fetcher curl -v https://raven-rt-prod2.campaign.adobe.com/nl/jsp/soaprouter.jsp
```

**Solutions**:
- Verify VPN connection
- Check AWS security groups allow outbound HTTPS
- Verify endpoint URL in Secrets Manager
- Check container network mode (should be `bridge` or `host`)

### Authentication Failures

**Symptom**: SOAP response with authentication error or empty result

**Possible Causes**:
1. **Incorrect Credentials**: Username/password in Secrets Manager expired or wrong
2. **Session Token Format**: Must be `{username}/{password}` format
3. **Credentials Not Loaded**: Secrets Manager retrieval failed

**Debugging**:
```bash
# Check Secrets Manager
aws secretsmanager get-secret-value \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --secret-id Ketchup_Token_Secrets \
  --query 'SecretString' \
  --output text | jq '.raven_maintenance_email_username, .raven_maintenance_email_password'

# Check logs for secret loading errors
docker logs ketchup-maintenance-fetcher | grep -i "secret\|credential"
```

**Solutions**:
- Verify credentials in AWS Secrets Manager
- Confirm credentials work with manual SOAP request
- Check IAM role has `secretsmanager:GetSecretValue` permission
- Rotate credentials if expired

### XML Parsing Errors

**Symptom**: `ValueError: Invalid XML response` or `ParseError`

**Possible Causes**:
1. **Malformed XML**: SOAP response is not well-formed XML
2. **Unexpected Response**: API returns HTML error page instead of SOAP
3. **Encoding Issues**: Response has incorrect character encoding
4. **Namespace Changes**: Adobe changed SOAP namespace URIs

**Debugging**:
```bash
# Enable DEBUG logging
docker exec ketchup-maintenance-fetcher \
  sed -i 's/LOG_LEVEL=INFO/LOG_LEVEL=DEBUG/g' /etc/environment

# Restart to apply
docker restart ketchup-maintenance-fetcher

# Check raw response in logs
docker logs ketchup-maintenance-fetcher | grep -A 50 "SOAP response"
```

**Solutions**:
- Verify API is returning SOAP XML, not HTML error
- Check for API version changes or deprecations
- Validate XML with external parser
- Update namespace URIs if changed

### JSON Extraction Failures

**Symptom**: `ValueError: Invalid JSON in SOAP response` or `JSONDecodeError`

**Possible Causes**:
1. **Empty maintenanceData**: SOAP response has no data (valid but returns `[]`)
2. **Malformed JSON**: JSON within XML is invalid
3. **Unexpected Structure**: API changed response format
4. **Character Escaping**: JSON contains unescaped XML special chars

**Debugging**:
```python
# Add debug logging in raven_maintenance.py
logger.debug(f"Raw JSON text: {json_text}")
logger.debug(f"JSON length: {len(json_text)}")
```

**Solutions**:
- Check if `maintenanceData` element exists
- Validate JSON separately with `jq` or JSON validator
- Handle empty arrays gracefully (returns `[]`)
- Update JSON parsing if format changed

### Schedule Drift

**Symptom**: Fetch not running at 1:30 AM UTC, or running at wrong time

**Possible Causes**:
1. **Missing TZ=UTC**: Container using wrong timezone
2. **System Clock Drift**: Container or host time incorrect
3. **Scheduler Logic Bug**: Calculation error in `_seconds_until_target_time`
4. **Container Restart**: Missed scheduled time during restart

**Debugging**:
```bash
# Check container timezone
docker exec ketchup-maintenance-fetcher date
# Should show UTC

# Check environment variables
docker exec ketchup-maintenance-fetcher env | grep TZ
# Should output: TZ=UTC

# Check scheduler logs
docker logs ketchup-maintenance-fetcher | grep "Next run in"
# Shows calculated wait time
```

**Solutions**:
- Always set `TZ=UTC` in docker-compose.yml
- Verify host system time is correct (`ntpdate -q pool.ntp.org`)
- Check Docker daemon time sync
- Set `KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START=true` to catch up

### Health Check Failures

**Symptom**: Docker marks container as unhealthy, restarts container

**Possible Causes**:
1. **Stale Health File**: Scheduler not updating health status
2. **Last Fetch Too Old**: No successful fetch in 25 hours
3. **Filesystem Issues**: Cannot write to `/app/health/`
4. **Scheduler Crashed**: Scheduler stopped but container still running

**Debugging**:
```bash
# Manually run healthcheck
docker exec ketchup-maintenance-fetcher ./scripts/healthcheck-maintenance-fetcher.sh
echo $?  # 0=healthy, 1=unhealthy

# Check health file age
docker exec ketchup-maintenance-fetcher stat /app/health/maintenance_fetcher_health

# Check last fetch age
docker exec ketchup-maintenance-fetcher cat /app/health/maintenance_fetcher_last_run
```

**Solutions**:
- Verify scheduler is running (`docker logs` shows periodic updates)
- Check filesystem permissions on `/app/health/` directory
- Manually trigger fetch to reset last_run timestamp
- Increase healthcheck interval if frequent restarts

### DynamoDB Storage Failures

**Symptom**: Fetch succeeds but data not in DynamoDB, or `Store failed` error

**Possible Causes**:
1. **IAM Permissions**: Container role missing `dynamodb:PutItem` permission
2. **Table Name Wrong**: `DYNAMODB_TABLE_NAME` environment variable incorrect
3. **Region Mismatch**: Table in different region than `AWS_REGION`
4. **Capacity Exceeded**: DynamoDB throttling writes (unlikely with daily writes)

**Debugging**:
```bash
# Check IAM role
aws sts get-caller-identity --profile campaign_prod_v7

# Verify table exists
aws dynamodb describe-table \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --table-name ketchup_channel_information

# Check for throttling
aws dynamodb describe-table \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --table-name ketchup_channel_information \
  --query 'Table.ProvisionedThroughput'

# Check logs for boto3 errors
docker logs ketchup-maintenance-fetcher | grep -i "boto\|dynamodb"
```

**Solutions**:
- Verify IAM role has necessary DynamoDB permissions
- Confirm `DYNAMODB_TABLE_NAME=ketchup_channel_information`
- Ensure `AWS_REGION=eu-west-1`
- Check CloudWatch for DynamoDB throttling metrics
- Verify container has AWS credentials (IAM role or environment)

### Feature Flag Issues

**Symptom**: Service runs but doesn't fetch data

**Cause**: `KETCHUP_MAINTENANCE_FETCHER_ENABLED=false`

**Solution**:
```yaml
# In docker-compose.yml, ensure:
environment:
  - KETCHUP_MAINTENANCE_FETCHER_ENABLED=true
```

**Debugging**:
```bash
# Check environment variables
docker exec ketchup-maintenance-fetcher env | grep KETCHUP_MAINTENANCE_FETCHER

# Check logs for "disabled" message
docker logs ketchup-maintenance-fetcher | grep -i "disabled\|enabled"
# Should NOT see: "Maintenance fetcher disabled by feature flag"
```

### TypedDI Resolution Errors

**Symptom**: `RuntimeError: Protocol not registered` or `ResolutionError`

**Possible Causes**:
1. **Protocol Not Registered**: `RavenMaintenanceClientProtocol` missing from service_registrations
2. **Import Error**: `raven_maintenance.py` import failed silently
3. **Dependency Missing**: `SecretsManagerProtocol` not registered
4. **Container Not Initialized**: `get_unified_container()` failed

**Debugging**:
```python
# Add debug logging in main.py
logger.debug("Available protocols:")
for protocol in container.list_registered_protocols():
    logger.debug(f"  - {protocol}")
```

**Solutions**:
- Verify `maintenance_registrations.py` is imported
- Check for import errors in logs
- Ensure all protocol dependencies are registered first
- Test TypedDI with: `make test-typed-di`

## Additional Resources

### Related Services

- **ketchup-app**: Consumes maintenance data for AI-powered detection
- **MaintenanceChecker**: Matches JIRA instances against maintenance data
- **JiraPromptHandler**: Orchestrates maintenance prompt workflow

### Related Documentation

- **[Parent CLAUDE.md](../CLAUDE.md)**: Repository-wide patterns and conventions
- **[TypedDI Migration Summary](../docs/TYPEDDI_MIGRATION_SUMMARY.md)**: TypedDI architecture
- **[High-Level Architecture](../code_docs/ketchup_high_level.md)**: System design overview

### External Resources

- **defusedxml Documentation**: https://github.com/tiran/defusedxml
- **aiohttp Documentation**: https://docs.aiohttp.org/
- **SOAP Specification**: https://www.w3.org/TR/soap12/
- **XXE Attack Prevention**: https://owasp.org/www-community/vulnerabilities/XML_External_Entity_(XXE)_Processing

### Key Contacts

- **AWS Secrets**: Campaign Ops team manages `Ketchup_Token_Secrets`
- **Adobe Raven API**: Adobe Campaign infrastructure team
- **DynamoDB**: Ketchup table managed by Campaign Ops

---

**Remember**: This is the ONLY SOAP-based service in Ketchup. All other services use REST. When debugging, consider SOAP-specific issues like XML namespaces, SOAP headers, and embedded JSON extraction.
