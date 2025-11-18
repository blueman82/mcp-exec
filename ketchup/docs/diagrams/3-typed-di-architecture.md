# TypedDI Dependency Injection Architecture

## Service Container & Resolution Flow

```mermaid
graph TB
    subgraph "TypedDI Container"
        Registry["TypedServiceRegistry<br/>Service Container"]

        subgraph "Protocol Definitions"
            SlackProto["SlackClientProtocol<br/>interface"]
            JiraProto["JiraClientProtocol<br/>interface"]
            DBProto["ChannelRepositoryProtocol<br/>interface"]
            AIProto["AIClientProtocol<br/>interface"]
            SecretProto["SecretsClientProtocol<br/>interface"]
        end

        subgraph "Implementations"
            SlackImpl["SlackClient<br/>async aiohttp"]
            JiraImpl["JiraClient<br/>MCP bridge"]
            DBImpl["ChannelRepository<br/>DynamoDB"]
            AIImpl["AzureOpenAIClient<br/>async"]
            SecretImpl["AWSSecretsClient<br/>boto3"]
        end

        subgraph "Service Registration"
            Registration["register_services()<br/>Topological Sort"]
        end
    end

    subgraph "Business Logic Layer"
        CommandHandlers["Command Handlers<br/>/status, /report, /jira-sync"]
        EventHandlers["Event Handlers<br/>@mention, reactions, messages"]
        BackgroundServices["Background Services<br/>status-updater, jira-reporter"]
    end

    subgraph "Event Handlers Request Services"
        Handler1["Handler<br/>resolve SlackClientProtocol"]
        Handler2["Handler<br/>resolve JiraClientProtocol"]
        Handler3["Handler<br/>resolve ChannelRepositoryProtocol"]
    end

    subgraph "DI Resolution Process"
        Resolve1["1. Request service<br/>by Protocol"]
        Resolve2["2. Check cache<br/>for singleton"]
        Resolve3["3. Resolve dependencies<br/>recursively"]
        Resolve4["4. Instantiate<br/>with injected deps"]
        Resolve5["5. Return fully<br/>initialized service"]
    end

    Registry -->|Defines| SlackProto
    Registry -->|Defines| JiraProto
    Registry -->|Defines| DBProto
    Registry -->|Defines| AIProto
    Registry -->|Defines| SecretProto

    SlackProto -->|Implemented by| SlackImpl
    JiraProto -->|Implemented by| JiraImpl
    DBProto -->|Implemented by| DBImpl
    AIProto -->|Implemented by| AIImpl
    SecretProto -->|Implemented by| SecretImpl

    Registration -->|Registers all| SlackImpl
    Registration -->|Registers all| JiraImpl
    Registration -->|Registers all| DBImpl
    Registration -->|Registers all| AIImpl
    Registration -->|Registers all| SecretImpl

    CommandHandlers -->|Request from| Registry
    EventHandlers -->|Request from| Registry
    BackgroundServices -->|Request from| Registry

    Handler1 -->|Needs| SlackProto
    Handler2 -->|Needs| JiraProto
    Handler3 -->|Needs| DBProto

    Handler1 -->|Triggers| Resolve1
    Resolve1 -->|→| Resolve2
    Resolve2 -->|→| Resolve3
    Resolve3 -->|→| Resolve4
    Resolve4 -->|→| Resolve5
    Resolve5 -->|Returns SlackClient| Handler1

    style Registry fill:#00cc99
    style SlackProto fill:#0099cc
    style JiraProto fill:#0099cc
    style DBProto fill:#0099cc
    style AIProto fill:#0099cc
    style SecretProto fill:#0099cc
    style SlackImpl fill:#00ffcc
    style JiraImpl fill:#00ffcc
    style DBImpl fill:#00ffcc
    style AIImpl fill:#00ffcc
    style SecretImpl fill:#00ffcc
```

## Dependency Graph Example: Slack Event Handler

```mermaid
graph TD
    FastAPI["FastAPI Event<br/>Endpoint"]

    FastAPI -->|Request from DI| DI["TypedDI Container"]

    DI -->|Resolve| SlackHandler["SlackEventHandler<br/>Protocol"]
    DI -->|Resolve| SlackClient["SlackClient<br/>Implementation"]
    DI -->|Resolve| ChannelRepo["ChannelRepository<br/>Implementation"]
    DI -->|Resolve| JiraClient["JiraClient<br/>Implementation"]
    DI -->|Resolve| AIClient["AzureOpenAIClient<br/>Implementation"]

    SlackHandler -->|Depends on| SlackClient
    SlackHandler -->|Depends on| ChannelRepo
    SlackHandler -->|Depends on| JiraClient
    SlackHandler -->|Depends on| AIClient

    SlackClient -->|Depends on| SecretsClient["SecretsClient<br/>async boto3"]
    ChannelRepo -->|Depends on| DDB["DynamoDB<br/>Resource"]
    JiraClient -->|Depends on| MCPServer["MCP Server<br/>connection"]
    AIClient -->|Depends on| AzureConfig["Azure Config<br/>from Secrets"]

    SecretsClient -->|Loads| Creds["AWS Secrets<br/>Manager"]
    DDB -->|Queries| DynamoDB["DynamoDB Table"]
    MCPServer -->|Connects| JiraAPI["Jira Cloud API"]
    AzureConfig -->|Authenticates| AzureAI["Azure OpenAI<br/>API"]

    DI -->|Injects into| SlackHandler
    SlackHandler -->|Returns to| FastAPI

    style FastAPI fill:#36c5f0
    style DI fill:#00cc99
    style SlackHandler fill:#0099cc
    style SlackClient fill:#00ffcc
    style ChannelRepo fill:#00ffcc
    style JiraClient fill:#00ffcc
    style AIClient fill:#00ffcc
```

## Service Registration Order (Topological Sort)

```mermaid
graph LR
    subgraph "Dependency Layers"
        Layer0["Layer 0:<br/>Base Clients<br/>SecretsClient<br/>HttpClient"]
        Layer1["Layer 1:<br/>Configured Clients<br/>SlackClient<br/>JiraClient<br/>AIClient"]
        Layer2["Layer 2:<br/>Repositories<br/>ChannelRepository<br/>UserRepository"]
        Layer3["Layer 3:<br/>Business Logic<br/>CommandHandlers<br/>EventHandlers"]
        Layer4["Layer 4:<br/>Services<br/>StatusUpdater<br/>JiraReporter"]
    end

    Layer0 -->|Injected into| Layer1
    Layer1 -->|Injected into| Layer2
    Layer2 -->|Injected into| Layer3
    Layer3 -->|Injected into| Layer4

    style Layer0 fill:#ffcccc
    style Layer1 fill:#ffddcc
    style Layer2 fill:#ffffcc
    style Layer3 fill:#ddffcc
    style Layer4 fill:#ccffdd
```

## Singleton vs Transient Services

```mermaid
graph TB
    subgraph "Singleton Services (created once, reused)"
        SingletonSlack["SlackClient<br/>Reused connection pool"]
        SingletonDB["ChannelRepository<br/>Single DB connection"]
        SingletonSecrets["SecretsClient<br/>Cached credentials"]
    end

    subgraph "Transient Services (new instance each time)"
        TransientHandler["Command Handler<br/>New per request"]
        TransientEvent["Event Handler<br/>New per event"]
    end

    subgraph "Requests"
        Req1["Request 1<br/>GET /status"]
        Req2["Request 2<br/>POST /event"]
        Req3["Request 3<br/>PUT /jira"]
    end

    Req1 -->|Gets same| SingletonSlack
    Req2 -->|Gets same| SingletonSlack
    Req3 -->|Gets same| SingletonSlack

    Req1 -->|Creates new| TransientHandler
    Req2 -->|Creates new| TransientEvent
    Req3 -->|Creates new| TransientHandler

    TransientHandler -->|Uses| SingletonSlack
    TransientEvent -->|Uses| SingletonSlack

    style SingletonSlack fill:#cc99ff
    style SingletonDB fill:#cc99ff
    style SingletonSecrets fill:#cc99ff
    style TransientHandler fill:#99ccff
    style TransientEvent fill:#99ccff
```

## File Structure

```
packages/core/typed_di/
├── typed_service_registry.py     # Main DI container with topological sort
├── protocols.py                  # Protocol definitions (interfaces)
├── service_registration.py       # Register all services with dependencies
├── decorators.py                 # @injectable, @singleton decorators
└── exceptions.py                 # DI resolution errors

packages/slack/
├── handlers/
│   ├── command_handlers.py      # Implement SlackCommandProtocol
│   └── event_handlers.py        # Implement SlackEventProtocol
└── clients/
    └── slack_client.py          # Implement SlackClientProtocol

packages/integrations/
├── jira_client.py               # Implement JiraClientProtocol
├── ai_client.py                 # Implement AIClientProtocol
└── async_client.py              # Base class for all async clients

packages/db/
└── repositories/
    └── channel_repository.py    # Implement RepositoryProtocol
```

## Key Advantages

✅ **Type Safety**: Protocol-first design catches errors at development time
✅ **Testability**: Easy to mock services by providing test implementations
✅ **Loose Coupling**: Services depend on interfaces, not implementations
✅ **Dependency Resolution**: No string-based lookups (100% compile-time safe)
✅ **Circular Dependency Prevention**: Topological sort detects cycles early
✅ **Singleton Management**: Automatic lifecycle management of shared resources

---

**Migration Status**: 100% complete - all 7 production services use pure TypedDI (no legacy string-based DI)
