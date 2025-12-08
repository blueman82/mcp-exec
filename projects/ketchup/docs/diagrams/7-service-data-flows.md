# Service Data Flows

## 1. Status Updater Service Flow

```mermaid
graph TD
    Timer["BaseScheduler<br/>Every 55 min"]

    Timer -->|Trigger| Fetch["Fetch all<br/>active channels<br/>from DDB"]

    Fetch -->|Get list| Channels["Channel List<br/>{<br/>channel_id,<br/>owner,<br/>status<br/>}"]

    Channels -->|Iterate| ForEach["For each channel"]

    ForEach -->|Query| GetStatus["Get latest<br/>status messages"]

    GetStatus -->|Retrieve| StatusData["Last 24h status<br/>data"]

    StatusData -->|Analyze| AnalyzeStatus["Analyze:<br/>- Changes<br/>- Blockers<br/>- Risks"]

    AnalyzeStatus -->|Generate| Report["Generate<br/>Status Report<br/>Text"]

    Report -->|Format| BlockKit["Format as<br/>Slack Block Kit<br/>JSON"]

    BlockKit -->|Send| PostSlack["Post to channel<br/>chat.postMessage"]

    PostSlack -->|Response| SlackChannel["Slack<br/>Channel<br/>Status appears"]

    PostSlack -->|Also update| SaveDB["Save timestamp<br/>to DDB"]

    SaveDB -->|Next hour| Timer

    style Timer fill:#ff9900
    style Channels fill:#0099cc
    style Report fill:#99ff99
    style PostSlack fill:#99ccff
    style SlackChannel fill:#36c5f0
```

## 2. JIRA Reporter Service Flow

```mermaid
graph TD
    Monitor["Monitor channels<br/>every 15 minutes"]

    Monitor -->|Scan| ScanChannels["Scan all channels<br/>with JIRA enabled"]

    ScanChannels -->|Get| ChannelConfig["Channel config:<br/>- JIRA project<br/>- status field<br/>- auto-reporting"]

    ChannelConfig -->|For each| CheckUpdates["Check for<br/>new/updated<br/>status"]

    CheckUpdates -->|Compare| Compare["Compare with<br/>last sync"]

    Compare -->|If changed| CreateTicket["Create/Update<br/>JIRA ticket"]

    CreateTicket -->|Build request| JiraPayload["JIRA Payload:<br/>- title<br/>- description<br/>- priority<br/>- labels"]

    JiraPayload -->|Call MCP| MCPServer["MCP JIRA<br/>Server<br/>Port 8081"]

    MCPServer -->|Execute| JiraAPI["Jira Cloud<br/>REST API"]

    JiraAPI -->|Return| TicketID["Ticket created<br/>e.g., PROJ-1234"]

    TicketID -->|Post| NotifySlack["Post notification<br/>to channel"]

    NotifySlack -->|Update| DDB["Update DDB:<br/>ticket_id<br/>sync_timestamp"]

    DDB -->|Next scan| Monitor

    alt "No changes"
        Compare -->|No change| Skip["Skip<br/>No action needed"]
        Skip -->|Next scan| Monitor
    end

    style Monitor fill:#ff9900
    style MCPServer fill:#ff9900
    style CreateTicket fill:#cc99ff
    style JiraAPI fill:#0052cc
    style NotifySlack fill:#99ccff
```

## 3. Channel Metadata Updater Flow

```mermaid
graph TD
    Hourly["BaseScheduler<br/>Every 15 min"]

    Hourly -->|Fetch| GetChannels["List all<br/>Slack channels"]

    GetChannels -->|Get list| Channels["Channels:<br/>- id<br/>- name<br/>- topic<br/>- description"]

    Channels -->|Iterate| EachChannel["For each channel"]

    EachChannel -->|Fetch| GetMetadata["Fetch channel<br/>metadata from<br/>Slack API"]

    GetMetadata -->|Retrieve| Metadata["Channel metadata:<br/>- topic<br/>- description<br/>- created_at<br/>- creator<br/>- member_count<br/>- is_archived"]

    Metadata -->|Extract| ParseMetadata["Parse metadata<br/>fields"]

    ParseMetadata -->|Transform| Transform["Transform to<br/>Ketchup format:<br/>- sanitize text<br/>- extract tags<br/>- categorize"]

    Transform -->|Check| Compare["Compare with<br/>stored metadata"]

    Compare -->|If changed| Update["Update in<br/>DynamoDB"]

    Update -->|Trigger| OnMetadataChange["Trigger<br/>metadata-changed<br/>event"]

    OnMetadataChange -->|Notify| PostEvent["Post to<br/>event queue"]

    PostEvent -->|Log| Completion["Log update<br/>completion"]

    Completion -->|Next hour| Hourly

    alt "No change"
        Compare -->|No change| Skip["Skip<br/>No update"]
        Skip -->|Next hour| Hourly
    end

    style Hourly fill:#ff9900
    style Metadata fill:#0099cc
    style Update fill:#cc99ff
    style PostEvent fill:#99ccff
```

## 4. Maintenance Fetcher Service Flow

```mermaid
graph TD
    Timer["BaseScheduler<br/>Daily 1:30 UTC"]

    Timer -->|Check| FetchMaintenanceAPI["Fetch from<br/>Adobe Maintenance<br/>Calendar API"]

    FetchMaintenanceAPI -->|Retrieve| MaintData["Maintenance events:<br/>- service<br/>- start_time<br/>- end_time<br/>- status<br/>- impact"]

    MaintData -->|Filter| FilterUpcoming["Filter for<br/>upcoming<br/>in next 24h"]

    FilterUpcoming -->|Get| UpcomingList["Upcoming maintenance<br/>events"]

    UpcomingList -->|Iterate| EachEvent["For each event"]

    EachEvent -->|Check| IsNew{"Is new<br/>event?"}

    IsNew -->|Yes| CreateAlert["Create alert<br/>entry in DDB"]

    IsNew -->|No| CheckStatus["Check status<br/>change"]

    CreateAlert -->|Post| AlertSlack["Post to<br/>#maintenance<br/>channel"]

    CheckStatus -->|If updated| UpdateAlert["Update alert<br/>in DDB"]

    UpdateAlert -->|Post| UpdateSlack["Post update<br/>to channel"]

    AlertSlack -->|Format| Message["Message:<br/>Service: XXX<br/>Start: <time><br/>End: <time><br/>Status: <status>"]

    UpdateSlack -->|Format| UpdateMsg["Updated: <new_status>"]

    Message -->|Send| Slack["Slack API<br/>chat.postMessage"]

    UpdateMsg -->|Send| Slack

    Slack -->|Notification| Channel["#maintenance<br/>channel"]

    Channel -->|Next check| Timer

    style Timer fill:#ff9900
    style MaintData fill:#0099cc
    style AlertSlack fill:#cc99ff
    style Message fill:#99ff99
    style Channel fill:#36c5f0
```

## 5. Access Request Monitor Flow

```mermaid
graph TD
    Monitor["Continuously<br/>monitor SQS"]

    Monitor -->|Poll| CheckQueue["Check SQS queue<br/>for access requests"]

    CheckQueue -->|Get messages| Request["Access request<br/>message:<br/>- user_id<br/>- resource<br/>- reason<br/>- requester"]

    Request -->|Dequeue| Parse["Parse request"]

    Parse -->|Extract| Details["Request details:<br/>- type: READ/WRITE/ADMIN<br/>- resource: channel/doc<br/>- urgency: LOW/MED/HIGH"]

    Details -->|Validate| CheckEligibility["Check user<br/>eligibility"]

    CheckEligibility -->|Query| DDB["Query DDB<br/>user_profile"]

    DDB -->|Get| UserData["User data:<br/>- dept<br/>- manager<br/>- permissions"]

    UserData -->|Verify| IsEligible{"Eligible<br/>?"}

    IsEligible -->|Yes| AutoApprove["Auto-approve"]
    IsEligible -->|No| NeedsReview["Route to<br/>manager review"]

    AutoApprove -->|Post| ApproveMsg["Post approval<br/>to Slack"]

    NeedsReview -->|Notify| ReviewNotify["Notify manager<br/>for approval"]

    ApproveMsg -->|Format| ApproveBlock["Block: ✅ APPROVED"]

    ReviewNotify -->|Format| ReviewBlock["Block: ⏳ PENDING REVIEW"]

    ApproveBlock -->|Send| Slack["Slack API<br/>chat.postMessage"]

    ReviewBlock -->|Send| Slack

    Slack -->|Post| UserNotif["Notify user<br/>in DM or channel"]

    UserNotif -->|Log| UpdateDB["Update request<br/>status in DDB"]

    UpdateDB -->|Continue| Monitor

    style Monitor fill:#ff9900
    style Request fill:#0099cc
    style IsEligible fill:#ffcc99
    style AutoApprove fill:#99ff99
    style NeedsReview fill:#ff9999
    style UserNotif fill:#36c5f0
```

## 6. Command Handler: /status Flow

```mermaid
graph TD
    User["User types<br/>/status"]

    User -->|POST| Slack["Slack API"]

    Slack -->|HTTP| FastAPI["FastAPI<br/>@app.post'/slack/commands'"]

    FastAPI -->|Parse| Extract["Extract:<br/>- command: 'status'<br/>- args: [...]<br/>- user_id<br/>- channel_id"]

    Extract -->|Route| Router["Command Router"]

    Router -->|Match| Handler["Get StatusCommand<br/>handler from DI"]

    Handler -->|Call| Execute["handler.handle(args)"]

    Execute -->|Parse args| ParseArgs["Parse arguments:<br/>- arg[0]: filter/channel<br/>- arg[1]: date range"]

    ParseArgs -->|Query| DDB["Query DynamoDB<br/>channel_status<br/>table"]

    DDB -->|Retrieve| Status["Latest status:<br/>- channel_id<br/>- status text<br/>- timestamp<br/>- updated_by"]

    Status -->|Check args| FilterStatus["Apply filters<br/>if provided"]

    FilterStatus -->|Get| Filtered["Filtered status<br/>records"]

    Filtered -->|Format| BlockKit["Format as<br/>Slack Block Kit:<br/>- Title<br/>- Status blocks<br/>- Timestamp<br/>- Buttons"]

    BlockKit -->|Return| Response["HTTP 200<br/>+ formatted response"]

    Response -->|Send| FastAPI

    FastAPI -->|Enqueue| BG["Background task"]

    BG -->|Post async| PostMessage["Slack API<br/>chat.postMessage"]

    PostMessage -->|Display| Channel["Channel<br/>Shows status"]

    style User fill:#ff6666
    style Handler fill:#00cc99
    style DDB fill:#0099cc
    style BlockKit fill:#99ff99
    style Channel fill:#36c5f0
```

## Data Model: DynamoDB Tables

```mermaid
graph TD
    subgraph "ketchup_channel_information"
        ChannelTable["Channel Table<br/>PK: channel_id<br/>SK: status_type"]

        Attrs1["Attributes:<br/>- channel_name<br/>- owner_id<br/>- description<br/>- created_at<br/>- last_updated<br/>- status_text<br/>- metadata<br/>- jira_project<br/>- tags"]
    end

    subgraph "user_profiles"
        UserTable["User Table<br/>PK: user_id<br/>SK: timestamp"]

        Attrs2["Attributes:<br/>- email<br/>- dept<br/>- manager_id<br/>- permissions<br/>- access_level"]
    end

    subgraph "access_requests"
        AccessTable["Access Table<br/>PK: request_id<br/>SK: created_at"]

        Attrs3["Attributes:<br/>- user_id<br/>- resource<br/>- status<br/>- approver_id<br/>- expires_at"]
    end

    subgraph "jira_sync_log"
        JiraTable["Sync Log Table<br/>PK: channel_id<br/>SK: sync_timestamp"]

        Attrs4["Attributes:<br/>- ticket_id<br/>- status<br/>- last_error<br/>- retry_count"]
    end

    ChannelTable --> Attrs1
    UserTable --> Attrs2
    AccessTable --> Attrs3
    JiraTable --> Attrs4

    style ChannelTable fill:#527fff
    style UserTable fill:#527fff
    style AccessTable fill:#527fff
    style JiraTable fill:#527fff
```

---

## Service Interaction Summary

| Service | Trigger | Input | Processing | Output | Success Indicator |
|---------|---------|-------|-----------|--------|------------------|
| **Status Updater** | Every 55 min (BaseScheduler) | All channels | Fetch status → Analyze → Format | Slack message | Posted to all channels |
| **JIRA Reporter** | Continuous (BaseScheduler) | Channels with JIRA | Compare state → Create/update ticket | JIRA ticket + Slack notification | Ticket ID saved in DDB |
| **Metadata Updater** | Every 15 min (BaseScheduler) | Slack channels | Fetch metadata → Parse → Compare | Updated DDB records | Row updated in DDB |
| **Maintenance Fetcher** | Daily 1:30 UTC (BaseScheduler) | Adobe API | Fetch events → Filter → Alert | Slack notifications | Posted to #maintenance |
| **PAT Rotator** | Every 24 hours (BaseScheduler) | JIRA PATs | Check expiry → Rotate if needed | New PAT in Secrets Manager | Expiry date updated |
| **Access Monitor** | Continuous SQS | SQS queue | Parse request → Validate → Approve/Route | Slack notification | Status updated in DDB |
| **Command Handlers** | User command | /command args | Parse → Query → Format | Slack response | Message posted |
| **Event Handlers** | Slack event | Event payload | Extract → Process → Update | Slack response | DDB updated |
