# Ketchup Infrastructure Architecture

This diagram shows the complete AWS infrastructure for the Ketchup Slack application using a C4 Container diagram style. The system uses a dual-server architecture with an Application Load Balancer distributing traffic. **prod1** runs all 9 containers including 4 singleton services (highlighted in red), while **prod2** runs only the 5 core containers for load distribution without duplicating scheduled jobs.

```mermaid
graph TB
    subgraph External["External Systems"]
        Users["👥 Slack Users"]
        SlackAPI["Slack API<br/>(Webhook Source)"]
    end

    ALB["⚖️ Application Load Balancer<br/>(AWS ALB)<br/>eu-west-1"]

    subgraph prod1["🖥️ prod1: ketchup-prod1.campaign.adobe.com"]
        nginx1["nginx<br/>Port 80<br/>(Reverse Proxy)"]
        
        subgraph CoreServices1["Core Services"]
            app1_1["ketchup-app-1<br/>Port 8001<br/>(FastAPI)"]
            app1_2["ketchup-app-2<br/>Port 8001<br/>(FastAPI)"]
            mcp1["mcp-jira<br/>Port 8081<br/>(JIRA MCP)"]
            access1["ketchup-access-monitor<br/>(Access Requests)"]
        end
        
        subgraph Singletons1["🔴 Singleton Services (prod1 ONLY)"]
            metadata["ketchup-metadata-updater<br/>(Channel Scanner)"]
            status["ketchup-status-updater<br/>(Hourly Updates)"]
            jira["ketchup-jira-reporter<br/>(JIRA Automation)"]
            maintenance["ketchup-maintenance-fetcher<br/>(Maintenance Detection)"]
        end
    end

    subgraph prod2["🖥️ prod2: ketchup-prod2.campaign.adobe.com"]
        nginx2["nginx<br/>Port 80<br/>(Reverse Proxy)"]
        
        subgraph CoreServices2["Core Services"]
            app2_1["ketchup-app-1<br/>Port 8001<br/>(FastAPI)"]
            app2_2["ketchup-app-2<br/>Port 8001<br/>(FastAPI)"]
            mcp2["mcp-jira<br/>Port 8081<br/>(JIRA MCP)"]
            access2["ketchup-access-monitor<br/>(Access Requests)"]
        end
    end

    subgraph AWS["☁️ AWS Services (eu-west-1)"]
        DDB[("DynamoDB<br/>ketchup_channel_information")]
        Secrets["🔐 Secrets Manager<br/>Ketchup_Token_Secrets"]
        SQS["📨 SQS Queue<br/>ketchup-events-queue"]
        ECR["🐳 ECR Registry<br/>483013340174.dkr.ecr.eu-west-1"]
    end

    Users -->|"Slash Commands<br/>Interactions"| SlackAPI
    SlackAPI -->|"Webhooks<br/>POST Requests"| ALB
    
    ALB -->|"Round Robin"| nginx1
    ALB -->|"Round Robin"| nginx2
    
    nginx1 -->|"Proxy to"| app1_1
    nginx1 -->|"Proxy to"| app1_2
    nginx1 -->|"Proxy to"| mcp1
    
    nginx2 -->|"Proxy to"| app2_1
    nginx2 -->|"Proxy to"| app2_2
    nginx2 -->|"Proxy to"| mcp2
    
    app1_1 -.->|"Read/Write"| DDB
    app1_2 -.->|"Read/Write"| DDB
    app2_1 -.->|"Read/Write"| DDB
    app2_2 -.->|"Read/Write"| DDB
    
    app1_1 -.->|"Get Secrets"| Secrets
    app1_2 -.->|"Get Secrets"| Secrets
    app2_1 -.->|"Get Secrets"| Secrets
    app2_2 -.->|"Get Secrets"| Secrets
    
    metadata -.->|"Update Metadata"| DDB
    status -.->|"Read Channels"| DDB
    jira -.->|"Read Channels"| DDB
    
    status -->|"Post Updates"| SlackAPI
    jira -->|"Post Tickets"| SlackAPI
    maintenance -->|"Post Alerts"| SlackAPI
    
    mcp1 <-.->|"JIRA API"| jira
    mcp2 <-.->|"JIRA API"| jira
    
    access1 -.->|"Poll Messages"| SQS
    access2 -.->|"Poll Messages"| SQS
    
    ECR -.->|"Pull Images<br/>v2.360.344"| prod1
    ECR -.->|"Pull Images<br/>v2.360.344"| prod2

    classDef userFacing fill:#4A90E2,stroke:#2E5C8A,stroke-width:2px,color:#fff
    classDef background fill:#50C878,stroke:#2D7A4A,stroke-width:2px,color:#fff
    classDef aws fill:#FF9500,stroke:#CC7700,stroke-width:2px,color:#fff
    classDef singleton fill:#E74C3C,stroke:#A93226,stroke-width:3px,color:#fff
    classDef proxy fill:#9B59B6,stroke:#6C3483,stroke-width:2px,color:#fff

    class Users,SlackAPI,app1_1,app1_2,app2_1,app2_2,mcp1,mcp2 userFacing
    class metadata,status,jira,maintenance,access1,access2 background
    class DDB,Secrets,SQS,ECR aws
    class metadata,status,jira,maintenance singleton
    class nginx1,nginx2,ALB proxy
```

## Key Architecture Points

**Load Distribution:**
- ALB distributes incoming Slack webhooks across both servers
- nginx on each server proxies to local ketchup-app replicas (2 per server)

**Singleton Pattern:**
- 4 services run ONLY on prod1 to prevent duplicate scheduled operations
- These services are explicitly stopped/removed on prod2 during deployment
- Prevents race conditions and duplicate Slack posts

**Container Count:**
- **prod1:** 9 containers (5 core + 4 singletons)
- **prod2:** 5 containers (5 core only)
- **Total:** 14 containers across 2 servers

**Port Mapping:**
- Port 80: nginx (external access)
- Port 8001: ketchup-app containers (internal)
- Port 8081: mcp-jira service (internal)

**AWS Resource Access:**
- All ketchup-app containers read/write to DynamoDB
- All services fetch credentials from Secrets Manager
- Both access-monitor instances poll the same SQS queue
- All images versioned identically and pulled from ECR
