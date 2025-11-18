# Container Topology: Production Deployment

## Production Server 1 (Singletons Included)

```mermaid
graph TB
    subgraph "prod1.campaign.adobe.com"
        subgraph "HTTP Routing Layer"
            Nginx1["nginx<br/>Port 80<br/>Reverse Proxy"]
        end

        subgraph "FastAPI Application Replicas"
            App1["ketchup-app-1<br/>Port 8001<br/>FastAPI Instance"]
            App2["ketchup-app-2<br/>Port 8001<br/>FastAPI Instance"]
        end

        subgraph "JIRA Integration"
            MCP["mcp-jira<br/>Port 8081<br/>Node.js MCP Server"]
        end

        subgraph "Singleton Services (prod1 ONLY)"
            MetaUpdater["metadata-updater<br/>Channel Scanner<br/>Runs hourly"]
            StatusUpdater["status-updater<br/>Status Reporter<br/>Runs hourly"]
            JiraReporter["jira-reporter<br/>JIRA Automation<br/>Runs every 15m"]
            MaintenanceFetcher["maintenance-fetcher<br/>Maintenance Detector<br/>Runs every 5m"]
        end

        subgraph "Monitoring & Logging"
            AccessMonitor["access-monitor<br/>Request Tracking"]
        end

        subgraph "Shared Dependencies"
            Packages["packages/<br/>ai, core, db,<br/>integrations,<br/>secrets, slack"]
        end
    end

    subgraph "AWS Services"
        DDB["DynamoDB<br/>ketchup_channel_information"]
        Secrets["Secrets Manager<br/>Ketchup_Token_Secrets"]
        SQS["SQS Queue<br/>ketchup-events-queue"]
    end

    Input1["Slack<br/>Events"]
    Input1 -->|HTTP POST :80| Nginx1

    Nginx1 -->|Balance :8001| App1
    Nginx1 -->|Balance :8001| App2

    App1 -->|Import| Packages
    App2 -->|Import| Packages

    App1 -->|MCP Tunnel| MCP
    App2 -->|MCP Tunnel| MCP

    MCP -->|HTTP| JiraCloud["Jira Cloud"]

    MetaUpdater -->|Pull Tasks| SQS
    MetaUpdater -->|Import| Packages
    MetaUpdater -->|Post Responses| SlackAPI["Slack API"]

    StatusUpdater -->|Pull Tasks| SQS
    StatusUpdater -->|Import| Packages
    StatusUpdater -->|Post Responses| SlackAPI

    JiraReporter -->|Pull Tasks| SQS
    JiraReporter -->|Import| Packages
    JiraReporter -->|Post Responses| SlackAPI

    MaintenanceFetcher -->|Pull Tasks| SQS
    MaintenanceFetcher -->|Import| Packages
    MaintenanceFetcher -->|Post Responses| SlackAPI

    App1 -->|Query/Update| DDB
    App2 -->|Query/Update| DDB
    MetaUpdater -->|Query/Update| DDB
    StatusUpdater -->|Query/Update| DDB
    JiraReporter -->|Query/Update| DDB
    MaintenanceFetcher -->|Query/Update| DDB

    App1 -->|Get Secrets| Secrets
    App2 -->|Get Secrets| Secrets
    MCP -->|Get Secrets| Secrets
    MetaUpdater -->|Get Secrets| Secrets
    StatusUpdater -->|Get Secrets| Secrets
    JiraReporter -->|Get Secrets| Secrets
    MaintenanceFetcher -->|Get Secrets| Secrets

    AccessMonitor -->|Monitor| App1
    AccessMonitor -->|Monitor| App2

    style Nginx1 fill:#0066cc
    style App1 fill:#36c5f0
    style App2 fill:#36c5f0
    style MCP fill:#ff9900
    style MetaUpdater fill:#cc99ff
    style StatusUpdater fill:#cc99ff
    style JiraReporter fill:#cc99ff
    style MaintenanceFetcher fill:#cc99ff
    style AccessMonitor fill:#ffcc99
    style DDB fill:#527fff
    style Secrets fill:#527fff
    style SQS fill:#527fff
```

## Production Server 2 (Core Services Only)

```mermaid
graph TB
    subgraph "prod2.campaign.adobe.com"
        subgraph "HTTP Routing Layer"
            Nginx2["nginx<br/>Port 80<br/>Reverse Proxy"]
        end

        subgraph "FastAPI Application Replicas"
            App3["ketchup-app-1<br/>Port 8001<br/>FastAPI Instance"]
            App4["ketchup-app-2<br/>Port 8001<br/>FastAPI Instance"]
        end

        subgraph "JIRA Integration"
            MCP2["mcp-jira<br/>Port 8081<br/>Node.js MCP Server"]
        end

        subgraph "Monitoring & Logging"
            AccessMonitor2["access-monitor<br/>Request Tracking"]
        end

        subgraph "Shared Dependencies"
            Packages2["packages/<br/>ai, core, db,<br/>integrations,<br/>secrets, slack"]
        end

        subgraph "⛔ EXPLICITLY DISABLED"
            DisabledServices["❌ metadata-updater<br/>❌ status-updater<br/>❌ jira-reporter<br/>❌ maintenance-fetcher<br/><br/>Stopped during deployment<br/>to prevent duplicate jobs"]
        end
    end

    subgraph "AWS Services"
        DDB2["DynamoDB<br/>ketchup_channel_information"]
        Secrets2["Secrets Manager<br/>Ketchup_Token_Secrets"]
        SQS2["SQS Queue<br/>ketchup-events-queue"]
    end

    Input2["Slack<br/>Events"]
    Input2 -->|HTTP POST :80| Nginx2

    Nginx2 -->|Balance :8001| App3
    Nginx2 -->|Balance :8001| App4

    App3 -->|Import| Packages2
    App4 -->|Import| Packages2

    App3 -->|MCP Tunnel| MCP2
    App4 -->|MCP Tunnel| MCP2

    MCP2 -->|HTTP| JiraCloud2["Jira Cloud"]

    App3 -->|Query/Update| DDB2
    App4 -->|Query/Update| DDB2

    App3 -->|Get Secrets| Secrets2
    App4 -->|Get Secrets| Secrets2

    AccessMonitor2 -->|Monitor| App3
    AccessMonitor2 -->|Monitor| App4

    style Nginx2 fill:#0066cc
    style App3 fill:#36c5f0
    style App4 fill:#36c5f0
    style MCP2 fill:#ff9900
    style AccessMonitor2 fill:#ffcc99
    style DDB2 fill:#527fff
    style Secrets2 fill:#527fff
    style DisabledServices fill:#ff6666
```

## Service Comparison: prod1 vs prod2

```mermaid
graph LR
    subgraph "prod1 (Full Stack)"
        P1_FastAPI["FastAPI<br/>2 replicas"]
        P1_MCP["MCP Server<br/>JIRA"]
        P1_Singleton["Singleton Services<br/>4 services"]
        P1_Monitor["Monitoring<br/>access-monitor"]
    end

    subgraph "prod2 (Core Only)"
        P2_FastAPI["FastAPI<br/>2 replicas"]
        P2_MCP["MCP Server<br/>JIRA"]
        P2_Monitor["Monitoring<br/>access-monitor"]
        P2_Disabled["Disabled<br/>(stopped)"]
    end

    P1_FastAPI -->|Handles requests| Slack
    P1_Singleton -->|Background jobs| Slack
    P2_FastAPI -->|Handles requests| Slack

    style P1_Singleton fill:#cc99ff
    style P2_Disabled fill:#ff6666

    P1_MCP -.->|2 servers| Jira
    P2_MCP -.->|2 servers| Jira
```

## Load Balancing Across Servers

```mermaid
graph TD
    SlackEvents["Slack Events"]
    SlackEvents -->|ALB routing| LoadBalancer["AWS Application<br/>Load Balancer"]

    LoadBalancer -->|50% to prod1| Prod1["prod1.campaign.adobe.com"]
    LoadBalancer -->|50% to prod2| Prod2["prod2.campaign.adobe.com"]

    Prod1 -->|Nginx Load Balance| App1a["ketchup-app-1"]
    Prod1 -->|Nginx Load Balance| App1b["ketchup-app-2"]

    Prod2 -->|Nginx Load Balance| App2a["ketchup-app-1"]
    Prod2 -->|Nginx Load Balance| App2b["ketchup-app-2"]

    App1a -.->|Background<br/>Jobs| Singleton["Singleton Services<br/>(prod1 only)"]
    App1b -.->|Background<br/>Jobs| Singleton

    subgraph "All Query Same"
        DDB["DynamoDB<br/>ketchup_channel_information"]
        Secrets["Secrets Manager<br/>Ketchup_Token_Secrets"]
    end

    App1a -->|Query| DDB
    App1b -->|Query| DDB
    App2a -->|Query| DDB
    App2b -->|Query| DDB

    Singleton -->|Query| DDB

    style LoadBalancer fill:#ff9900
    style Prod1 fill:#ccddff
    style Prod2 fill:#ccddff
    style Singleton fill:#cc99ff
```

## Container Resource Allocation

```mermaid
graph TB
    subgraph "prod1 Resource Usage"
        CPU1["7 Containers<br/>Total CPU: ~2 cores shared"]
        Memory1["Memory allocation:<br/>nginx: 256MB<br/>app-1: 512MB<br/>app-2: 512MB<br/>mcp-jira: 256MB<br/>metadata-updater: 256MB<br/>status-updater: 256MB<br/>jira-reporter: 256MB<br/>maintenance-fetcher: 256MB<br/>access-monitor: 128MB"]
        Storage1["Logs:<br/>10MB max per<br/>container<br/>3 file retention<br/>Total ~500MB"]
    end

    subgraph "prod2 Resource Usage"
        CPU2["5 Containers<br/>Total CPU: ~1.5 cores shared"]
        Memory2["Memory allocation:<br/>nginx: 256MB<br/>app-1: 512MB<br/>app-2: 512MB<br/>mcp-jira: 256MB<br/>access-monitor: 128MB"]
        Storage2["Logs:<br/>10MB max per<br/>container<br/>3 file retention<br/>Total ~300MB"]
    end

    style CPU1 fill:#ffcccc
    style Memory1 fill:#ffffcc
    style Storage1 fill:#ccffcc
    style CPU2 fill:#ffcccc
    style Memory2 fill:#ffffcc
    style Storage2 fill:#ccffcc
```

## Deployment Strategy: Why Singletons Only on prod1?

**Problem**:
- Scheduled jobs (hourly status updates, JIRA reporting) cannot run on multiple servers
- Would create duplicate messages, duplicate tickets, race conditions
- Data conflicts in DynamoDB

**Solution**:
- Run singletons **only** on prod1
- Explicitly **stop and remove** these containers from prod2
- deployment script (deploy-ketchup.sh:505-506):
  ```bash
  # Remove singleton services from prod2
  ssh prod2 "docker-compose rm -f metadata-updater status-updater jira-reporter maintenance-fetcher"
  ```

**Benefits**:
- ✅ No duplicate scheduled jobs
- ✅ No race conditions on shared resources
- ✅ Clear "source of truth" for singleton work
- ✅ Reduces load on prod2 to core request handling
- ✅ Failover ready: if prod1 fails, can manually run singletons on prod2

---

**Total Containers**: 14 (7 on prod1, 5 on prod2, plus 2 monitoring)
**Total Services**: 9 (FastAPI, MCP, 4 singletons, 1 metadata updater, 1 access monitor, 1 jira reporter)
