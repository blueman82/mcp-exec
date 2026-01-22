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

        subgraph "Unified Scheduler (prod1 ONLY)"
            UnifiedScheduler["unified-scheduler<br/>Runs 5 tasks internally:<br/>• metadata-updater (15min)<br/>• status-updater (55min)<br/>• jira-reporter (continuous)<br/>• maintenance-fetcher (1:30 UTC)<br/>• jira-pat-rotator (24hr)"]
        end

        subgraph "CSOPM Notifier (prod1 ONLY)"
            CSOPMNotifier["csopm-notifier<br/>Schedule: 08:00 & 16:00 UTC<br/>• JIRA CSOPM polling<br/>• Slack DM notifications<br/>• RCA/closure reminders"]
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

    UnifiedScheduler -->|Pull Tasks| SQS
    UnifiedScheduler -->|Import| Packages
    UnifiedScheduler -->|Post Responses| SlackAPI

    CSOPMNotifier -->|Import| Packages
    CSOPMNotifier -->|MCP Tunnel| MCP
    CSOPMNotifier -->|Send DMs| SlackAPI
    CSOPMNotifier -->|Query/Update| DDB
    CSOPMNotifier -->|Get Secrets| Secrets["Slack API"]

    App1 -->|Query/Update| DDB
    App2 -->|Query/Update| DDB
    UnifiedScheduler -->|Query/Update| DDB

    App1 -->|Get Secrets| Secrets
    App2 -->|Get Secrets| Secrets
    MCP -->|Get Secrets| Secrets
    UnifiedScheduler -->|Get Secrets| Secrets

    AccessMonitor -->|Monitor| App1
    AccessMonitor -->|Monitor| App2

    style Nginx1 fill:#0066cc
    style App1 fill:#36c5f0
    style App2 fill:#36c5f0
    style MCP fill:#ff9900
    style UnifiedScheduler fill:#cc99ff
    style CSOPMNotifier fill:#cc99ff
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
            DisabledServices["❌ unified-scheduler<br/>❌ csopm-notifier<br/><br/>Stopped during deployment<br/>to prevent duplicate jobs<br/>(singletons run on prod1 only)"]
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
        P1_Unified["Unified Scheduler<br/>5 tasks"]
        P1_CSOPM["CSOPM Notifier<br/>2x daily"]
        P1_Monitor["Monitoring<br/>access-monitor"]
    end

    subgraph "prod2 (Core Only)"
        P2_FastAPI["FastAPI<br/>2 replicas"]
        P2_MCP["MCP Server<br/>JIRA"]
        P2_Monitor["Monitoring<br/>access-monitor"]
        P2_Disabled["Unified Scheduler<br/>CSOPM Notifier<br/>(disabled)"]
    end

    P1_FastAPI -->|Handles requests| Slack
    P1_Unified -->|Background jobs| Slack
    P1_CSOPM -->|DM notifications| Slack
    P2_FastAPI -->|Handles requests| Slack

    style P1_Unified fill:#cc99ff
    style P1_CSOPM fill:#cc99ff
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

    App1a -.->|Background<br/>Jobs| Singleton["Unified Scheduler<br/>(prod1 only)"]
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
        CPU1["7 Containers<br/>Total CPU: ~2.5 cores shared"]
        Memory1["Memory allocation:<br/>nginx: 256MB<br/>app-1: 512MB<br/>app-2: 512MB<br/>mcp-jira: 256MB<br/>unified-scheduler: 512MB<br/>csopm-notifier: 256MB<br/>access-monitor: 128MB"]
        Storage1["Logs:<br/>10MB max per<br/>container<br/>3 file retention<br/>Total ~400MB"]
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

## Deployment Strategy: Why Unified Scheduler Only on prod1?

**Problem**:
- Scheduled jobs (metadata updates, status reports, JIRA automation) cannot run on multiple servers
- Would create duplicate messages, duplicate tickets, race conditions
- Data conflicts in DynamoDB

**Solution**:
- Run unified scheduler **only** on prod1
- Explicitly **stop and remove** this container from prod2
- deployment script (deploy-ketchup.sh):
  ```bash
  # Remove unified scheduler from prod2
  ssh prod2 "docker-compose rm -f unified-scheduler"
  ```

**Benefits**:
- ✅ No duplicate scheduled jobs
- ✅ No race conditions on shared resources
- ✅ Clear "source of truth" for scheduled work
- ✅ Reduces load on prod2 to core request handling
- ✅ Failover ready: if prod1 fails, can manually run unified scheduler on prod2
- ✅ Single healthcheck for all scheduled tasks

---

**Total Containers**: 11 (6 on prod1, 5 on prod2)
**Total Services**: 6 (FastAPI x2, MCP, unified-scheduler, access-monitor x2)
