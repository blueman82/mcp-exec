# Command & Event Routing Architecture

## Slash Command Routing

```mermaid
graph TD
    SlackUser["User Types<br/>/status arg1 arg2"]

    SlackUser -->|HTTP POST| FastAPI["FastAPI<br/>@app.post'/slack/commands'"]

    FastAPI -->|Verify Signature| Verify["signature_verifier"]

    Verify -->|Parse| Parser["Extract:<br/>command_name<br/>args<br/>user_id<br/>channel_id"]

    Parser -->|Route| Router["Command Router<br/>Match command_name"]

    Router -->|/status| StatusCmd["StatusCommand<br/>Handler"]
    Router -->|/report| ReportCmd["ReportCommand<br/>Handler"]
    Router -->|/jira-sync| JiraSyncCmd["JiraSyncCommand<br/>Handler"]
    Router -->|/access| AccessCmd["AccessCommand<br/>Handler"]
    Router -->|/help| HelpCmd["HelpCommand<br/>Handler"]
    Router -->|Unknown| HelpCmd

    StatusCmd -->|Parse args| StatusLogic["Get latest status<br/>from DDB"]
    ReportCmd -->|Parse args| ReportLogic["Generate on-demand<br/>report"]
    JiraSyncCmd -->|Parse args| JiraLogic["Sync channel tickets"]
    AccessCmd -->|Parse args| AccessLogic["Handle access<br/>requests"]
    HelpCmd -->|Format| HelpLogic["Build help text"]

    StatusLogic -->|Query| DDB["DynamoDB"]
    ReportLogic -->|Query| DDB
    JiraLogic -->|Query| Jira["JIRA API<br/>via MCP"]
    AccessLogic -->|Query| DDB

    DDB -->|Return| Result["Response Data"]
    Jira -->|Return| Result
    Result -->|Format| Response["Build Slack<br/>Message Block"]

    Response -->|Post| Slack["Slack API<br/>chat.postMessage"]
    Slack -->|Send| User["Channel<br/>Display Result"]

    style FastAPI fill:#36c5f0
    style Router fill:#ff9900
    style StatusCmd fill:#0099cc
    style ReportCmd fill:#0099cc
    style JiraSyncCmd fill:#0099cc
    style AccessCmd fill:#0099cc
    style HelpCmd fill:#0099cc
```

## Event Routing & Handler Registration

```mermaid
graph TD
    SlackEvent["Slack Event<br/>JSON Payload"]

    SlackEvent -->|HTTP POST| FastAPI["FastAPI<br/>@app.post'/slack/events'"]

    FastAPI -->|Verify + Retry| Verify["Challenge Handler<br/>First-time setup"]

    Verify -->|Extract type| ExtractType["event.type<br/>= ?"]

    ExtractType -->|app_mention| MentionRouter["@mention<br/>Router"]
    ExtractType -->|message| MessageRouter["Message<br/>Router"]
    ExtractType -->|reaction_added| ReactionRouter["Reaction<br/>Router"]
    ExtractType -->|channel_created| ChannelRouter["Channel Created<br/>Router"]
    ExtractType -->|member_joined_channel| JoinRouter["Member Join<br/>Router"]

    MentionRouter -->|Extract text<br/>& sender| MentionHandler["MentionHandler<br/>@ketchup <query>"]
    MessageRouter -->|Check thread| MessageHandler["MessageHandler<br/>Archive/log"]
    ReactionRouter -->|Check emoji| ReactionHandler["ReactionHandler<br/>Track usage"]
    ChannelRouter -->|Scan metadata| ChannelHandler["ChannelHandler<br/>Store in DDB"]
    JoinRouter -->|Add to team| JoinHandler["JoinHandler<br/>Initialize user"]

    MentionHandler -->|Needs| DIContainer["TypedDI<br/>Container"]
    MessageHandler -->|Needs| DIContainer
    ReactionHandler -->|Needs| DIContainer
    ChannelHandler -->|Needs| DIContainer
    JoinHandler -->|Needs| DIContainer

    DIContainer -->|Resolves| SlackClient["SlackClient"]
    DIContainer -->|Resolves| AIClient["AIClient"]
    DIContainer -->|Resolves| DBRepo["ChannelRepository"]
    DIContainer -->|Resolves| JiraClient["JiraClient"]

    MentionHandler -->|Logic| MentionLogic["Extract query<br/>from @mention text"]
    MessageHandler -->|Logic| MessageLogic["Parse message<br/>metadata"]
    ReactionHandler -->|Logic| ReactionLogic["Count reaction<br/>usage"]
    ChannelHandler -->|Logic| ChannelLogic["Store channel<br/>info"]
    JoinHandler -->|Logic| JoinLogic["Initialize<br/>user data"]

    MentionLogic -->|Generate| AIQuery["AI Summary<br/>Query"]
    AIQuery -->|Call| AIClient
    AIClient -->|Return| AIResult["AI Response"]

    MessageLogic -->|Save| DBRepo
    ReactionLogic -->|Update| DBRepo
    ChannelLogic -->|Save| DBRepo
    JoinLogic -->|Create| DBRepo

    AIResult -->|Build| Response["Slack Response<br/>Message"]
    DBRepo -->|Return| Response

    Response -->|Post| PostMessage["Slack API<br/>chat.postMessage"]
    PostMessage -->|Send| Channel["Channel<br/>Display"]

    style FastAPI fill:#36c5f0
    style DIContainer fill:#00cc99
    style MentionRouter fill:#ff9900
    style MessageRouter fill:#ff9900
    style ReactionRouter fill:#ff9900
    style ChannelRouter fill:#ff9900
    style JoinRouter fill:#ff9900
    style MentionHandler fill:#0099cc
    style MessageHandler fill:#0099cc
    style ReactionHandler fill:#0099cc
    style ChannelHandler fill:#0099cc
    style JoinHandler fill:#0099cc
```

## Command Handler Registration Pattern

```mermaid
graph TB
    subgraph "Handler Registration"
        Protocol["SlackCommandProtocol<br/>interface"]
        StatusImpl["StatusCommand<br/>class"]
        ReportImpl["ReportCommand<br/>class"]
        JiraImpl["JiraSyncCommand<br/>class"]
        AccessImpl["AccessCommand<br/>class"]
    end

    subgraph "Service Registration"
        Registry["register_services()"]
    end

    subgraph "Runtime Routing"
        Router["CommandRouter"]
        Registry -->|Register| StatusImpl
        Registry -->|Register| ReportImpl
        Registry -->|Register| JiraImpl
        Registry -->|Register| AccessImpl

        StatusImpl -->|Implements| Protocol
        ReportImpl -->|Implements| Protocol
        JiraImpl -->|Implements| Protocol
        AccessImpl -->|Implements| Protocol

        Router -->|Lookup| StatusImpl
        Router -->|Lookup| ReportImpl
        Router -->|Lookup| JiraImpl
        Router -->|Lookup| AccessImpl
    end

    subgraph "Handler Execution"
        Route1["/status → StatusCommand.handle()"]
        Route2["/report → ReportCommand.handle()"]
        Route3["/jira-sync → JiraSyncCommand.handle()"]
        Route4["/access → AccessCommand.handle()"]
    end

    Router -->|Route /status| Route1
    Router -->|Route /report| Route2
    Router -->|Route /jira-sync| Route3
    Router -->|Route /access| Route4

    style Protocol fill:#0099cc
    style StatusImpl fill:#00ffcc
    style ReportImpl fill:#00ffcc
    style JiraImpl fill:#00ffcc
    style AccessImpl fill:#00ffcc
```

## Request Flow: /status Command Example

```mermaid
sequenceDiagram
    participant User as Slack User
    participant Slack as Slack API
    participant ALB as AWS ALB
    participant FastAPI as FastAPI<br/>8001
    participant Router as CommandRouter
    participant DI as TypedDI
    participant Handler as StatusCommand
    participant DDB as DynamoDB
    participant Response as Response Builder

    User->>Slack: 1. /status <args>
    Slack->>ALB: 2. POST /slack/commands<br/>text=/status<br/>args=...
    ALB->>FastAPI: 3. Route to replica

    FastAPI->>FastAPI: 4. Verify signature

    FastAPI->>Router: 5. Extract command_name<br/>= "status"

    Router->>Router: 6. Match to<br/>StatusCommand

    Router->>DI: 7. Get StatusCommand<br/>handler instance

    DI->>DI: 8. Resolve dependencies<br/>ChannelRepository<br/>SlackClient<br/>ConfigService

    DI->>Handler: 9. Inject dependencies

    Handler->>Handler: 10. Parse arguments

    Handler->>DDB: 11. Query latest status<br/>for channel

    DDB->>Handler: 12. Return status data

    Handler->>Response: 13. Format response<br/>as Block Kit

    Response->>Handler: 14. Return message JSON

    Handler->>Response: 15. Queue response task

    Handler->>FastAPI: 16. Return control

    FastAPI->>Slack: 17. Immediate HTTP 200

    Note over Slack: User sees "searching..."

    Response->>Slack: 18. Async: post_message<br/>with status blocks

    Slack->>User: 19. Display status<br/>in channel
```

## Event Handler Registration Pattern

```mermaid
graph TB
    subgraph "Event Handlers"
        MentionHandler["MentionEventHandler"]
        MessageHandler["MessageEventHandler"]
        ReactionHandler["ReactionEventHandler"]
        ChannelHandler["ChannelEventHandler"]
    end

    subgraph "Service Registry"
        Registry["register_event_handlers()"]
    end

    subgraph "Event Router"
        EventRouter["EventTypeRouter"]
    end

    subgraph "Slack Event Types"
        MentionEvent["event_type='app_mention'"]
        MessageEvent["event_type='message'"]
        ReactionEvent["event_type='reaction_added'"]
        ChannelEvent["event_type='channel_created'"]
    end

    Registry -->|Register| MentionHandler
    Registry -->|Register| MessageHandler
    Registry -->|Register| ReactionHandler
    Registry -->|Register| ChannelHandler

    EventRouter -->|Lookup by type| MentionHandler
    EventRouter -->|Lookup by type| MessageHandler
    EventRouter -->|Lookup by type| ReactionHandler
    EventRouter -->|Lookup by type| ChannelHandler

    MentionEvent -->|Route to| MentionHandler
    MessageEvent -->|Route to| MessageHandler
    ReactionEvent -->|Route to| ReactionHandler
    ChannelEvent -->|Route to| ChannelHandler

    style MentionHandler fill:#0099cc
    style MessageHandler fill:#0099cc
    style ReactionHandler fill:#0099cc
    style ChannelHandler fill:#0099cc
    style EventRouter fill:#ff9900
```

---

## Adding a New Slash Command

To add `/newcommand`:

1. **Create handler**: `packages/slack/commands/new_command.py`
   ```python
   class NewCommand(SlackCommandProtocol):
       async def handle(self, args: List[str]) -> SlackResponse:
           # implementation
   ```

2. **Implement protocol**: Must implement `SlackCommandProtocol` interface

3. **Register in DI**: Add to `packages/core/typed_di/service_registration.py`
   ```python
   registry.register(SlackCommandProtocol, NewCommand)
   ```

4. **Route in FastAPI**: Router will automatically discover via DI

5. **Test**: Write unit test with mocked dependencies

---

## Adding a New Event Handler

To handle a new Slack event type:

1. **Create handler**: `packages/slack/handlers/new_event_handler.py`
2. **Implement protocol**: `SlackEventProtocol`
3. **Register in router**: Add mapping in event router
4. **Get dependencies from DI**: Request needed services
5. **Test**: Mock Slack API responses
