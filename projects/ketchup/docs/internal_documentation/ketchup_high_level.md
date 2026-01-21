# High Level Ketchup Codebase Guide

## Table of Contents

1. [Introduction](#introduction)
2. [What is Ketchup?](#what-is-ketchup)
3. [How the System Works: Key Concepts](#how-the-system-works-key-concepts)
   - [Two-Phase Processing](#two-phase-processing)
   - [What is Dependency Injection (DI)?](#what-is-dependency-injection-di)
   - [What is a Factory?](#what-is-a-factory)
   - [What are Async Clients?](#what-are-async-clients)
4. [Event Handling & Eligibility](#event-handling--eligibility)
   - [Event Handling](#event-handling)
   - [Channel Eligibility](#channel-eligibility)
   - [What Happens When the Bot Joins an Ineligible Channel](#what-happens-when-the-bot-joins-an-ineligible-channel)
   - [Edge Cases and Special Scenarios](#edge-cases-and-special-scenarios)
   - [User Feedback and Logging](#user-feedback-and-logging)
   - [Summary Table: What Happens When...](#summary-table-what-happens-when)
5. [Codebase Organization](#codebase-organization)
   - [Core Module](#core-module-packagescore)
   - [AI Module](#ai-module-packagesai)
   - [MCP JIRA Service](#mcp-jira-service)
   - [Database Module](#database-module-packagesdb)
   - [Secrets Module](#secrets-module-packagessecrets)
   - [Slack Module](#slack-module-packagesslack)
6. [Key Async Clients in the Codebase](#key-async-clients-in-the-codebase)
7. [How a Slack Command Works: Step by Step](#how-a-slack-command-works-step-by-step)
8. [How the Slack Home Tab Works](#how-the-slack-home-tab-works)
9. [Command Usage Tracking and Metrics](#command-usage-tracking-and-metrics)
10. [Feature Flags and Controlled Rollouts](#feature-flags-and-controlled-rollouts)
   - [How Feature Flags Work](#how-feature-flags-work)
   - [Three-Tier Control System](#three-tier-control-system)
   - [Managing Feature Access](#managing-feature-access)
   - [Adding New Features](#adding-new-features)
11. [Common Development Tasks](#common-development-tasks)
   - [How to Add a New Slack Command](#how-to-add-a-new-slack-command)
   - [How to Create a New Async Client](#how-to-create-a-new-async-client)
   - [How to Add a New Slack Event Handler](#how-to-add-a-new-slack-event-handler)
   - [How to Modify Home Tab Content](#how-to-modify-home-tab-content)
   - [How to Add a Feature Behind a Flag](#how-to-add-a-feature-behind-a-flag)
12. [Common Code Patterns to Know](#common-code-patterns-to-know)
13. [Debugging Tips](#debugging-tips)
14. [Best Practices](#best-practices)
15. [Where to Start](#where-to-start)
16. [Eligibility Logic Example](#eligibility-logic-example)
17. [Event Flow Diagram](#event-flow-diagram)
18. [Error Handling Examples](#error-handling-examples)
19. [Code Mapping: High-Level Step to Code](#code-mapping-high-level-step-to-code)
20. [Testing and Observability](#testing-and-observability)
21. [Configuration Reference](#configuration-reference)
22. [Real Container Log Output](#real-container-log-output)

## Introduction

This guide provides a simplified overview of the Ketchup codebase, designed to help you understand how the system works and where to find important components. We'll use clear explanations and avoid complex jargon.

> **⚠️ ARCHITECTURE UPDATE (June 2025):** Ketchup now runs on EC2 with Docker containers instead of AWS Lambda. The core business logic remains the same, but the infrastructure has been modernized for better performance and cost efficiency (from $450-800/month to ~$150/month).

## What is Ketchup?

Ketchup is a Slack bot that helps summarize and manage Slack channels. The application:
- Runs on AWS EC2 instances with Docker containers (nginx, FastAPI app, and metadata updater)
- Integrates with Slack for user interaction through webhook endpoints
- Stores data in DynamoDB (a NoSQL database)
- Uses Azure OpenAI for AI-powered summarization features
- Provides a Home tab interface for personalized user preferences and settings
- Deployed behind an Application Load Balancer (ALB) for high availability

## How the System Works: Key Concepts

### Two-Phase Processing

Slack requires quick responses (under 3 seconds), but our operations often take longer. To solve this, we use a two-phase approach with FastAPI:

1. **Quick Response Phase**: 
   - FastAPI endpoint immediately acknowledges the Slack request (within 3 seconds)
   - Returns a "processing" message to the user via HTTP 200 response
   - Slack receives confirmation that the request was received

2. **Background Processing Phase**: 
   - FastAPI's `BackgroundTasks` handles the actual work asynchronously
   - Performs operations without time constraints (AI calls, database updates, etc.)
   - Sends the final result back to Slack using the response URL when complete

This is like telling someone "I got your message, working on it now" and then getting back to them with the full answer later.

**EC2 Architecture Flow:**
```
Slack → ALB → Nginx → FastAPI → Background Task → Process → Response to Slack
```

### What is Dependency Injection (DI)?

Dependency Injection is a technique where a component receives its dependencies from outside rather than creating them internally.

**Simple explanation:**
- Instead of a component creating what it needs inside itself
- Someone else creates those things and gives them to the component

**Benefits:**
- Makes testing easier (you can provide test versions of dependencies)
- Allows components to be more flexible
- Prevents tight coupling between different parts of the system

In our codebase, the DI (Dependency Injection) container (`di_container.py`) is like a central registry that knows how to create and provide all the components our system needs.

**EC2 Benefit:** Unlike Lambda which creates a new container for each invocation, our FastAPI application maintains a persistent DI container. This means:
- Connections to services (Slack, DynamoDB, OpenAI) are reused
- No cold start delays
- Better performance and lower latency

#### Visual: How DI/Factories Provide Dependencies


This diagram shows how factory modules create service instances, which are registered in the DI container. The DI container then provides these dependencies to command handlers or other consumers.

### What is a Factory?

A Factory is a function or class that creates other objects. It's like a workshop that produces specific components.

**Simple explanation:**
- Instead of directly creating objects with `new Object()`
- You use a specialized function that knows how to properly build that object

**Benefits:**
- Centralizes complex object creation logic
- Handles dependencies and configuration
- Makes it easier to ensure objects are created consistently

In our code, factories (like `slack_factory.py` or `db_factory.py`) know how to create specific types of components with all their required dependencies and configuration.

### What are Async Clients?

Async Clients are specialized classes that handle communication with external services (like Slack API, DynamoDB, or Azure OpenAI) in an asynchronous way.

**Simple explanation:**
- They allow us to make requests to external services without blocking execution
- They use Python's `async`/`await` features to manage operations that take time
- They provide consistent error handling, retries, and resource management

**Why are they important?**

1. **Efficiency**: They allow our application to handle many operations at the same time without getting stuck. While waiting for one API call to complete, the application can work on other tasks.

2. **Resource Management**: They handle opening and closing connections properly, preventing resource leaks.

3. **Resilience**: They implement retry logic for when API calls fail temporarily.

4. **Standardization**: They provide a consistent way to interact with all external services.

**What problems do they solve?**

1. **Performance and Efficiency**: Long-running operations can be handled asynchronously without blocking the main thread. This allows us to process multiple requests concurrently.

2. **External API Timeout Handling**: Async clients can better manage timeouts when external services are slow to respond.

3. **Connection Pooling**: They manage HTTP connections efficiently, reusing them when possible.

4. **Error Recovery**: They can automatically retry failed operations with backoff strategies.

**How they work in our codebase:**

- Most async clients inherit from `AsyncClient` in `core/async_client.py`
- They implement specific methods for their service (e.g., `get_channel_info()` in Slack clients)
- They handle authentication, request formatting, and response parsing
- They use `aiohttp` for making HTTP requests asynchronously
- When making API calls with async clients, you always use the `await` keyword:

```python
# Example of using an async client
async def get_channel_summary(channel_id):
    slack_client = get_slack_client()
    channel_info = await slack_client.get_channel_info(channel_id)
    messages = await slack_client.get_channel_messages(channel_id, count=100)
    
    openai_client = get_openai_client()
    summary = await openai_client.generate_summary(messages)
    
    return summary
```

In this example, we're doing multiple API calls without blocking. Each `await` tells Python "this might take time, but keep processing other tasks if possible while you wait."

## Event Handling & Eligibility

### Event Handling

When something happens in Slack—like a channel is created, a user joins, or a channel is archived—the bot receives an event and processes it. Each event type has a dedicated handler that:
- Logs what's happening for traceability.
- Checks if the event is relevant (e.g., is the bot being added? Is this a supported channel?).
- Takes the appropriate action, such as joining, leaving, or updating channel metadata.

**Key events the bot handles:**
- **Channel Created:** Checks if the new channel is eligible, then invites the bot and stores metadata.
- **Member Joined Channel:** If the bot is the one joining, checks eligibility and either stays or leaves.
- **Channel Archived/Unarchived:** Updates the channel's status in the database and manages bot membership. 
  - When a channel is unarchived, the bot updates the channel's record in DynamoDB (sets `archived=False`, clears `archived_at`), and re-invites itself to the channel. All state changes are tracked in the database for auditability and future operations.
- **App Mention (@Ketchup):** Responds with a fallback message directing users to slash commands (MessageAnalyzer functionality was removed). When disabled, responds with a fallback message directing users to slash commands.
- **Temporary Unarchive Tracking:** When a channel is temporarily unarchived (for example, to run a command), the bot marks this in DynamoDB with a TTL (time-to-live) attribute. This ensures the temporary state is automatically cleaned up after a set period, and allows the bot to check if a channel is eligible for special handling during this window. This is part of robust state management and auditability.

### Channel Eligibility

Not every channel is eligible for bot operations. The bot uses a set of business rules to decide:

- **Naming Convention:** The channel name must match approved patterns (e.g., contain certain keywords).
- **Creator:** Only channels created by specific users are eligible (We can specify us as engineers but by default Exigence).
- **Channel Age:** Channels older than 30 days are usually ineligible, unless they've been temporarily unarchived for a special reason.
- **Token Count:** If a channel has more than 50,000 tokens (messages, words, or characters), the bot will process only the last 50,000 tokens, truncating the rest. The user is notified about this truncation. This ensures the bot remains efficient and within API limits.


### What Happens When the Bot Joins an Ineligible Channel

If the bot is added to a channel that doesn't meet the rules:
- The bot will send an ephemereal message to the person who invited them, stating the reason why the bot can't join and then leave automatically. The code will trigger a deletion of the channel in DynamoDB (if one exists).
- If the channel is old but has been temporarily unarchived (for example, for a review), the bot may stay as an exception.
- All these decisions are logged for auditability.

### Edge Cases and Special Scenarios

- **Temporary Unarchive:** If a channel is too old but has been temporarily unarchived, the bot checks the database and may stay.
- **Missing Metadata:** If the bot joins a channel and can't find its metadata, it tries to fetch info from the Slack messages and store it.
- **Invite Failures:** If the bot can't be invited (e.g., missing permissions), the creator is notified directly in Slack.
- **Malformed Events:** If required information is missing from an event, the bot logs the error and skips processing.

### User Feedback and Logging

- **User Notifications:** If something goes wrong (like the bot can't join or store metadata), the user who triggered the event is notified via direct message in Slack.
- **Comprehensive Logging:** Every major action, decision, and error is logged. This makes it easy to trace what happened and why, which is crucial for debugging and audits.

### Summary Table: What Happens When...

| Scenario                                 | What the Bot Does                                      | User Notified? | Logged? |
|-------------------------------------------|--------------------------------------------------------|---------------|---------|
| New eligible channel created              | Joins, stores metadata                                 | No            | Yes     |
| New ineligible channel created            | Ignores, does not join                                 | No            | Yes     |
| Bot added to ineligible channel           | Leaves immediately                                     | No            | Yes     |
| Bot added to old but temporarily unarchived channel | Stays as exception                              | No            | Yes     |
| Channel archived                          | If a command is run, notifies user that channel is unarchived and bot is invited; after command, notifies user when room is re-archived; updates DB | Yes           | Yes     |
| Channel unarchived                        | Updates DB (archived=False, clears archived_at), re-invites bot, tracks all state changes | No            | Yes     |
| Metadata storage fails                    | Notifies channel creator                               | Yes           | Yes     |
| Invite fails                              | Notifies channel creator                               | Yes           | Yes     |
| Channel has >50k tokens                   | Truncates to last 50k tokens, notifies user about truncation | Yes           | Yes     |

## Codebase Organization

The code is organized into logical packages, each with a specific purpose. Let's look at each one with key files:

### Core Module (`packages/core/`)

This module contains fundamental utilities and infrastructure used throughout the application:

- **`di_container.py`**: The central registry for dependency injection. It manages all components and their dependencies.

- **`async_client.py`**: Base class for asynchronous API clients. Provides retry logic and connection management.

- **`client_factory/` directory**:
  - **`slack_factory.py`**: Creates Slack-related components like channel operations or message handlers
  - **`db_factory.py`**: Creates database-related components
  - **`ai_factory.py`**: Creates AI service components
  - **`secrets_factory.py`**: Creates components for accessing secure data
  - **`cloud_factory.py`**: Creates AWS service clients

- **`resilience/backoff.py`**: Implements retry logic when operations fail temporarily

- **`constants.py`**: Global constants like timeouts, API endpoints, and configuration values

- **`config/` directory**:
  - **`feature_flags.py`**: Manages feature flag environment variables and global checks

- **`exceptions.py`**: Custom exception classes for specific error scenarios

- **`cleanup_utils.py`**: Functions for cleaning up resources to prevent memory leaks

- **`http/session_management.py`**: Creates and manages HTTP client sessions

- **`time_utils.py`**: Helper functions for working with dates and times

### AI Module (`packages/ai/`)

This module handles interaction with AI services and manages prompts:

- **`core/openai_handler.py`**: Main interface for interacting with Azure OpenAI API

- **`core/azure_async_client.py`**: Client for making API calls to Azure OpenAI

- **`core/token_utils.py`**: Functions for counting and managing tokens for AI models

- **`prompts/` directory**: Contains prompt templates for different tasks:
  - **`status.py`**: Prompts for generating channel status reports
  - **`query.py`**: Prompts for answering user queries
  - **`summary.py`**: Prompts for creating channel summaries
  - **`common_guidelines.py`**: Shared instructions for all AI prompts

- **`cost_calculator.py`**: Tracks token usage for monitoring costs

### @Ketchup Mention Feature (Deprecated)

**Note:** The MessageAnalyzer component and advanced natural language processing have been removed from Ketchup. @Ketchup mentions now show a simple fallback message directing users to slash commands.

#### Current Behavior

When someone mentions @Ketchup in a channel, the bot responds with a helpful message directing users to available slash commands:

```
Thanks for mentioning me! Please use slash commands to interact with Ketchup:
• `/ketchup status #channel` - Get channel status
• `/ketchup report #channel` - Get channel report  
• `/ketchup query #channel "question"` - Ask questions about channel content
```

#### Historical Context

Previously, Ketchup included advanced AI-powered message analysis through the MessageAnalyzer component, which could:
- Parse natural language queries from @mentions
- Determine appropriate commands to execute
- Provide conversational responses

This functionality was removed as part of the LangChain cleanup to simplify the architecture and reduce dependencies.

#### Configuration

The feature is controlled by the `ENABLE_MESSAGE_ANALYSIS` environment variable:
- `false` (recommended): @Ketchup mentions show fallback message with slash command guidance
- `true` (deprecated): Would attempt to use MessageAnalyzer (no longer available)

### MCP JIRA Service
The Model Context Protocol (MCP) JIRA service is a separate Docker container that provides JIRA integration capabilities:

#### Architecture

- **Separate Service**: Runs as `mcp-jira` Docker container
- **HTTP API**: Exposes endpoints on port 8081
- **Integration**: Main app communicates via `MCP_BASE_URL`
- **Authentication**: Uses iPaaS credentials from AWS Secrets Manager

#### Key Features

1. **Natural Language to JQL**: Converts queries like "show me recent P1 bugs" to proper JQL
2. **Smart Caching**: Reduces API calls to JIRA with intelligent result caching
3. **Self-Healing**: Automatically corrects common query errors
4. **Rate Limiting**: Respects JIRA API limits

#### Communication Flow


#### Configuration

MCP JIRA service is configured via environment variables:
- `MCP_BASE_URL`: URL of the MCP service (default: `http://mcp-jira:8081`)
- `USE_IPAAS`: Enable iPaaS authentication (default: `true`)
- `JIRA_TOOL_PERSIST_CORRECTIONS`: Enable query correction caching

### Database Module (`packages/db/`)

This module manages all database operations:

- **`dynamodb_store.py`**: Main interface for storing and retrieving data from DynamoDB

- **`user_store.py`**: Specialized store for user-related data

- **`operations/` directory**: Specialized database operations
  - **`channel_operations.py`**: Functions for working with channel data
  - **`archive_operations.py`**: Functions for archiving channel information
  - **`feedback_operations.py`**: Functions for storing user feedback

- **`models/channel_metadata.py`**: Defines the structure of channel data

- **`core/dynamodb_async_client.py`**: Low-level async client for DynamoDB

### Secrets Module (`packages/secrets/`)

This module handles secure access to credentials:

- **`manager.py`**: Provides secure access to API keys and tokens

### Slack Module (`packages/slack/`)

This module contains all Slack-specific functionality:

- **`authorisation/`**:
  - **`auth.py`**: Verifies Slack request signatures
  - **`user_verification.py`**: Checks if users are authorized for actions

- **`blockkits/`**: Creates Slack UI components
  - **`base.py`**: Base classes for Slack message builders
  - **`formatters.py`**: Helper functions for formatting text
  - **`handlers/`**: Specialized message builders for different commands
    - **`status.py`**: Creates status report messages
    - **`query.py`**: Creates query response messages
    - **`summary.py`**: Creates summary messages
    - **`archive.py`**: Creates archive confirmation messages

- **`channel_events/`**:
  - **`events.py`**: Handles Slack events (channel created, user joined, etc.)
  - **`incoming_events.py`**: Main entry point for processing Slack requests
  - **`eligibility/`**: Determines which channels are eligible for the bot
  - **`processing/`**: Processes different types of events

- **`channel_operations/`**:
  - **`channel_info_ops.py`**: Gets channel information from Slack
  - **`channel_msg_ops.py`**: Retrieves messages from channels
  - **`channel_archive_ops.py`**: Archives channels in Slack
  - **`channel_restore_ops.py`**: Restores archived channels
  - **`channel_name_resolver.py`**: Resolves channel names and mentions to IDs

- **`command_processing/`**:
  - **`command_router.py`**: Routes commands to the appropriate handler
  - **`status_report_command.py`**: Handles status and report commands
  - **`query_command.py`**: Handles query commands
  - **`archive_command.py`**: Handles archive commands
  - **`list_command.py`**: Handles list commands
  - **`feature_command.py`**: Handles feature flag management commands (admin only)
  - **`feature_service.py`**: Service for checking and managing user feature flags
  - **`command_parameters/`**: Extracts and validates command parameters

- **`interactive_elements/`**:
  - **`feedback_reactions.py`**: Handles thumbs up/down reactions
  - **`payload_processor.py`**: Processes interactive messages

- **`messages/posting.py`**: Sends messages to Slack

- **`home/`**: Manages the Slack Home tab interface.
  - **`home.py`**: Orchestrates Home tab operations and event handling.
  - **`home_publish.py`**: Handles constructing and publishing the Home tab view.
  - **`home_preferences.py`**: Manages user preference retrieval and defaults.
  - **`home_modals.py`**: Builds and publishes modals (like success confirmations).
  - **`home_utils.py`**: Provides stateless helpers for UI blocks and preference management.

- **`csopm/`**: CSOPM (Customer Support Operations Management) shared components used by both the scheduler container and main app.
  - **`blocks.py`**: Slack Block Kit notification components for assignment alerts.
  - **`state.py`**: DynamoDB state tracking for notification status (CSOPM_NOTIFICATION# prefix).
  - **`actions.py`**: Interactive button action handlers (acknowledge/done/snooze) for callbacks.

## Key Async Clients in the Codebase

Let's look at the most important async clients in our codebase:

### 1. Base AsyncClient (`core/async_client.py`)

This is the foundation for all other async clients. It provides:

- **Connection management**: Creates and manages HTTP sessions
- **Retry logic**: Automatically retries failed requests
- **Backoff strategy**: Increases delay between retries
- **Request batching**: Groups multiple small requests together
- **Error handling**: Consistent error handling across all clients

### 2. DynamoDB Async Client (`db/core/dynamodb_async_client.py`)

This client handles all database operations:

- **Database queries**: Runs queries against DynamoDB
- **Item operations**: Creates, reads, updates, and deletes items
- **Batch operations**: Performs operations on multiple items at once
- **Transaction support**: Ensures all-or-nothing operations
- **Connection pooling**: Efficiently manages database connections

### 3. Slack Async Client (`slack/core/slack_async_client.py`)

This client interacts with the Slack API:

- **API requests**: Makes calls to various Slack API endpoints
- **Rate limiting**: Respects Slack's API rate limits
- **Authentication**: Handles Slack token management
- **Webhook support**: Sends messages to response URLs
- **Error parsing**: Understands Slack-specific error messages

### 4. Azure OpenAI Async Client (`ai/core/azure_async_client.py`)

This client communicates with Azure OpenAI:

- **API requests**: Makes calls to Azure's OpenAI API
- **Model selection**: Configures which AI model to use
- **Token management**: Tracks token usage for billing
- **Response parsing**: Extracts useful data from AI responses
- **Error handling**: Manages AI-specific error conditions

## How a Slack Command Works: Step by Step

When a user types a command like `/ketchup status #incident-response`:

1. **Request Received**:
   - Slack sends the command to our Application Load Balancer (ALB)
   - ALB forwards it to nginx, which proxies to our FastAPI application
   - `ketchup-app/main.py` receives this request at the `/slack/events` endpoint

2. **Quick Acknowledgment**:
   - FastAPI immediately acknowledges the request to Slack (HTTP 200)
   - This prevents Slack from showing a timeout error
   - The request is added to a background task queue

3. **Background Processing**:
   - FastAPI's `BackgroundTasks` handles the actual processing
   - This runs asynchronously without blocking the response

4. **Command Routing**:
   - `incoming_events.py` identifies this as a Slack command
   - `command_router.py` determines which handler should process it
   - For `/status`, it routes to the `SlackReports` handler

5. **Channel Resolution**:
   - The handler validates the channel parameter format
   - If it's a channel name (like `#incident-response`), the `ChannelNameResolver` converts it to a channel ID
   - Also supports channel mentions (`<#C123|incident-response>`) and direct IDs (`C1234567890`)
   - Validates the channel exists and the user has access

6. **Command Execution**:
   - The handler uses the resolved channel ID
   - It retrieves channel data from the database using the DynamoDB async client
   - It fetches channel messages using the Slack async client
   - It calls Azure OpenAI to generate a status report using the OpenAI async client
   - It formats the response into a nice Slack message

7. **Response**:
   - The formatted response is sent back to Slack using the Slack posting client
   - The user sees the result in their Slack channel


## How the Slack Home Tab Works

Slack provides each app with a dedicated "Home tab" - a personal space where users can interact with the app. In Ketchup, this space is used for personalization, user preferences, and displaying command usage statistics.

When a user opens the Ketchup Home tab in Slack, the following process occurs: 

1. **Event Received**:
   - Slack sends an `app_home_opened` event to our Application Load Balancer
   - ALB forwards to nginx, which proxies to our FastAPI application
   - `ketchup-app/main.py` receives this event at the `/slack/events` endpoint

2. **Quick Acknowledgment**:
   - FastAPI immediately acknowledges the request to Slack (HTTP 200)
   - This is required to meet Slack's response time requirements

3. **Home Tab Processing**:
   - The request is processed in a FastAPI background task
   - The event routes to the `HomeTabHandler` in `home.py`
   - `HomeTabHandler` orchestrates the process, keeping business logic in specialized modules

4. **User Preferences and Information Retrieval**:
   - `HomeTabHandler._get_user_preferences` fetches the user's stored preferences from DynamoDB
   - The user's first name is extracted from their profile for personalization
   - If no preferences exist, default values are provided
   - These preferences include settings like role, product focus, detail level, and time window for summaries

5. **Home Tab Construction**:
   - `home_utils.py` builds the Block Kit UI elements based on user preferences and first name
   - A personalized greeting ("Hi [FirstName]!") is displayed at the top of the Home tab
   - The UI includes options for setting product focus, detail levels, time windows, and more
   - Command usage statistics are displayed showing personal usage for all users and team-wide stats for admins
   - A dedicated "Support & Feedback" section provides documentation links and a direct "Report Feedback / Suggest Idea" button

6. **Publishing to Slack**:
   - `home_publish.py` sends the constructed Home tab to Slack
   - It calls the Slack API's `views.publish` method
   - The user sees the personalized Home tab with their name and preferences in Slack

7. **Handling Interactions**:
   - When the user interacts with the Home tab (e.g., clicks "Save Preferences" or "Report Feedback")
   - Slack sends a `block_actions` payload to our FastAPI endpoint
   - `payload_processor.py` routes actions based on action_id to the appropriate handler
   - For saving preferences:
     - User selections are extracted from the payload
     - Preferences are saved to DynamoDB
     - A confirmation modal is shown via `home_modals.py`
   - For reporting feedback:
     - The feedback modal is opened via `FeedbackReportHandler.open_feedback_report_modal`
     - User can submit ideas, suggestions, or report issues directly from the Home tab

This modular approach makes the system maintainable and testable, with clean separation of concerns between orchestration (`home.py`), data access, UI building (`home_utils.py`), and API interactions (`home_publish.py` and `home_modals.py`).

## Event Flow Diagram


## Command Usage Tracking and Metrics

Ketchup tracks command usage to provide insights into how users interact with the bot. This feature helps teams understand usage patterns and identify power users.

### How Command Tracking Works

1. **Automatic Logging**: Every valid command execution is automatically logged by the CommandRouter
2. **DynamoDB Storage**: Command data is stored using a dedicated schema in the existing table
3. **Real-time Statistics**: Usage stats are calculated on-demand when users view the Home tab
4. **Admin Visibility**: Admin users see team-wide statistics in addition to their personal stats
5. **CSV Export**: Users can export their usage data via the Home tab export button

### DynamoDB Schema for Tracking

Commands are stored with the following structure:
- **Partition Key (PK)**: `USER#<user_id>` - Groups all commands by user
- **Sort Key (SK)**: `COMMAND#<timestamp>#<command_type>` - Enables time-based queries
- **Attributes**: 
  - `user_id`, `user_name`: User identification
  - `command_type`: Type of command (status, report, query, etc.)
  - `timestamp`: Unix timestamp of execution
  - `channel_id`: Channel where command was executed
  - `command_text`: Full command text
  - `execution_date`, `execution_time`: Human-readable timestamps

### Usage Statistics Display

The Home tab displays usage statistics based on user permissions:

#### Non-Admin View
All users see their personal command usage for the past 7 days:
```
📊 Your Usage Stats (Past 7 Days)
• status: 12
• report: 8
• query: 6
• analyze: 4

[Export Usage Data] <- Button to export as CSV
```

#### Admin View
Admin users additionally see team-wide statistics:
```
👥 Team Usage (Past 7 Days)
Top 5 Users:
1. harrison: 45 commands
2. omeara: 38 commands
3. jbloggs: 27 commands
4. sarah: 19 commands
5. michael: 15 commands

[Export Usage Data] <- Button to export as CSV
```

### CSV Export Feature

Users can export their command usage data as a CSV file directly from the Home tab:

1. **Export Button**: Located in the Usage Stats section of the Home tab
2. **Data Format**: CSV includes command breakdown, timestamps, and usage trends
3. **Delivery**: The CSV file is sent via direct message to the user
4. **Time Range**: Export covers the past 7 days of usage data

#### CSV Contents
The exported CSV includes:
- Command type breakdown (status, report, query, etc.)
- Daily usage trends
- Peak usage times
- Most used channels
- Comparison to previous week (percentage change)

#### Implementation
The export functionality uses Slack's new file upload API:
1. User clicks "Export Usage Data" button
2. System generates CSV with usage statistics
3. File is uploaded using `files.getUploadURLExternal` API
4. File is shared to user's DM using `files.completeUploadExternal`
5. User receives the CSV file in their Slack DM

### Implementation Details

1. **Command Logging Integration**:
   - The `CommandRouter` checks if a command is valid before logging
   - Only known command types are tracked (unknown/invalid commands are ignored)
   - Logging happens asynchronously to avoid impacting command response time

2. **Admin Detection**:
   - Admin users are defined in AWS Secrets Manager under `usage_stats_admin_users`
   - The system performs case-insensitive matching to handle Slack's lowercase usernames
   - Admin list supports both "FirstName LastName" and "firstname lastname" formats

3. **Query Optimization**:
   - User stats use efficient partition key queries
   - Team stats require table scans but are filtered to only command records
   - Both queries respect the time window (default: 7 days)

4. **CSV Export Processing**:
   - Export request handled by `UsageExportHandler`
   - CSV generation performed by `CommandUsageCSVGenerator`
   - File upload handled asynchronously to avoid timeouts
   - Supports both user IDs starting with 'U' and 'W' through DM channel resolution

### Configuration

Admin users are managed via AWS Secrets Manager:
```json
{
  "usage_stats_admin_users": "[\"Harrison Barnes\", \"John Doe\", \"Emma Wilson\"]"
}
```

Note: The value must be a JSON string (not an array) due to AWS Secrets Manager requirements.

### Key Files

- **`packages/db/operations/command_tracking_operations.py`**: Core database operations for tracking
- **`packages/slack/command_processing/command_logger.py`**: Command logging utilities
- **`packages/slack/command_processing/command_router.py`**: Integration point for automatic logging
- **`packages/slack/home/home.py`**: Home tab handler that displays usage statistics
- **`packages/slack/interactive_elements/usage_export_handler.py`**: Handles CSV export requests
- **`packages/core/exports/csv_generator.py`**: Generates CSV content from usage data

## Feature Flags and Controlled Rollouts

Ketchup includes a sophisticated feature flag system that enables controlled rollout of new functionality. This system allows developers to:
- Test new features with specific beta users
- Gradually roll out features to all users
- Quickly disable features if issues arise
- Manage feature access without code deployments

**For a comprehensive reference of all 40+ feature flags and environment variables, see [Feature Flags Reference](./ketchup_feature_flags.md)**.

### How Feature Flags Work

The feature flag system uses a three-tier control mechanism that provides flexibility in how features are rolled out:

1. **Development & Testing**: Enable features locally via environment variables
2. **Beta Testing**: Grant access to specific users for real-world testing
3. **Global Rollout**: Enable features for all users when ready

**Current Implementation: NLP Feature**

The NLP (Natural Language Processing) feature allows users to interact with Ketchup using natural language through @mentions. This feature is currently managed through the feature flag system as an example of controlled rollout.

### Three-Tier Control System


**The Three Tiers Explained:**

1. **Global Enable** (`KETCHUP_NLP_GLOBAL`)
   - When `true`, the feature is available to all users
   - Overrides per-user settings
   - Used for full production rollout

2. **Per-User Beta** (Database flag)
   - Stored in DynamoDB under user's `features.nlp_enabled` attribute
   - Allows specific users to test features
   - Managed via admin commands

3. **Master Switch** (`KETCHUP_NLP_FEATURE`)
   - Must be `true` for any access (beta or global)
   - Acts as an emergency shutoff
   - Can disable feature instantly without database changes

### Managing Feature Access

Feature access is managed through admin-only commands. Only users listed in the `usage_stats_admin_users` secret can manage features.

#### Feature Command Syntax

```bash
# Enable feature for a specific user
/ketchup feature nlp enable @username

# Disable feature for a specific user
/ketchup feature nlp disable @username

# List all users with the feature enabled
/ketchup feature nlp list

# Check feature status
/ketchup feature nlp status
```

#### Admin Configuration

Admins are defined in AWS Secrets Manager under `Ketchup_Token_Secrets`:
```json
{
  "usage_stats_admin_users": "[\"Harrison Barnes\", \"John Doe\", \"Emma Wilson\"]"
}
```

### Adding New Features

Adding a new feature behind a flag is straightforward and follows a consistent pattern:

#### 1. Define Environment Variables (Optional)

In `packages/core/config/feature_flags.py`:
```python
@staticmethod
def is_auto_summary_enabled() -> bool:
    """Check if auto-summary feature is enabled for beta testing."""
    return os.getenv("KETCHUP_AUTO_SUMMARY_FEATURE", "false").lower() == "true"

@staticmethod
def is_auto_summary_global() -> bool:
    """Check if auto-summary is enabled for all users."""
    return os.getenv("KETCHUP_AUTO_SUMMARY_GLOBAL", "false").lower() == "true"
```

#### 2. Add Feature Check in Service

In `packages/slack/command_processing/feature_service.py`:
```python
async def is_auto_summary_enabled_for_user(self, user_id: str) -> bool:
    """Check if auto-summary feature is enabled for user."""
    # Check global flag first
    if FeatureFlags.is_auto_summary_global():
        return True
    
    # Check user-specific beta flag
    try:
        return await self.user_store.get_user_feature(user_id, "auto_summary_enabled") is True
    except Exception as e:
        logger.error(f"Error checking auto-summary feature: {e}")
        return False
```

#### 3. Use Feature Check in Code

```python
# In your command handler or service
if await self.feature_service.is_auto_summary_enabled_for_user(user_id):
    # New feature code
    summary = await self.generate_auto_summary(channel_id)
    await post_message(channel_id, summary)
else:
    # Fallback behavior
    await post_message(channel_id, "Auto-summary is not enabled for your account.")
```

#### 4. That's It!

The feature is now:
- Controllable via environment variables
- Manageable through `/ketchup feature` commands
- Stored persistently in DynamoDB
- Ready for gradual rollout

### Feature Flag Best Practices

1. **Start with Master Switch Off**: Keep `KETCHUP_<FEATURE>_FEATURE=false` until ready for beta
2. **Test with Internal Users First**: Enable for team members before external beta
3. **Monitor Feature Usage**: Track how beta users interact with new features
4. **Gradual Rollout**: Start with a few users, expand gradually
5. **Have a Rollback Plan**: Ensure the master switch can instantly disable the feature
6. **Clean Up**: Once globally enabled and stable, consider removing the flag system

### Current Feature Flags

| Feature | Environment Variables | Description |
|---------|----------------------|-------------|
| NLP | `KETCHUP_NLP_FEATURE`<br/>`KETCHUP_NLP_GLOBAL` | Natural language processing for @mentions |
| Message Analysis | `ENABLE_MESSAGE_ANALYSIS` | Legacy flag for message analysis |

### Implementation Details

**Key Files:**
- **`packages/core/config/feature_flags.py`**: Environment variable checks
- **`packages/slack/command_processing/feature_service.py`**: User-level feature management
- **`packages/slack/command_processing/feature_command.py`**: Admin command handler
- **`packages/db/user_store.py`**: Database operations for user features

**Database Schema:**
Features are stored in the user's DynamoDB record:
```
PK: USER#<user_id>
SK: METADATA
features: {
    "nlp_enabled": true,
    "auto_summary_enabled": false
}
```

## Common Development Tasks

### How to Add a New Slack Command

1. **Define Command Parameters**:
   - Add a new class in `slack/command_processing/command_parameters/models.py`
   - This class defines what parameters your command needs

   ```python
   class MyNewCommandParams:
       # Define what parameters your command needs
       channel_id: str
       my_special_param: str
   ```

2. **Create Parameter Extractor**:
   - Add a new file in `slack/command_processing/command_parameters/extractors/`
   - This extracts parameters from the raw Slack command

   ```python
   def extract_my_command_params(command_text: str) -> MyNewCommandParams:
       # Extract parameters from command text like "/ketchup mycommand channel-id special-value"
       parts = command_text.split()
       return MyNewCommandParams(
           channel_id=parts[2],
           my_special_param=parts[3]
       )
   ```

3. **Validate Command Parameters** (Recommended):
   - After parameters are extracted, they should be validated to ensure they are correct and the command can proceed.
   - Your command handler might perform this validation, or you can centralize validation logic.
   - The `packages/slack/command_processing/command_parameters/validation.py` module provides a `ValidationError` class for consistent error handling and may contain other relevant utilities. Consider using or extending these for your new command.

4. **Create Command Handler**:
   - Add a new file in `slack/command_processing/`
   - This contains the main logic for your command

   ```python
   class MyNewCommandHandler(BaseCommandHandler):
       # Handle initialization and dependency injection
       def __init__(self, dependency1, dependency2):
           self.dependency1 = dependency1
           self.dependency2 = dependency2
       
       # Process the command
       async def process_command(self, params: MyNewCommandParams):
           # Your command logic here
           return {"result": "Command processed successfully"}
   ```

5. **Register in Command Router**:
   - Update `slack/command_processing/command_router.py`
   - This tells the system about your new command

   ```python
   # In the CommandRouter.route_command method:
   elif command_type == CommandType.MY_NEW_COMMAND:
       return await self.command_handlers[CommandType.MY_NEW_COMMAND].process_my_command(params)
   ```

6. **Create Response Formatter**:
   - Add a new handler in `slack/blockkits/handlers/`
   - This formats your command's response as a nice Slack message

### Channel Parameter Formats in Commands

Ketchup commands now support three ways to specify channels:

```bash
# Using channel ID (traditional method)
/ketchup query C1234567890 "What was the root cause?"
/ketchup status C1234567890
/ketchup report C1234567890

# Using channel mention (copy from Slack)
/ketchup query <#C1234567890|incident-response> "What was the root cause?"
/ketchup status <#C1234567890|incident-response>
/ketchup report <#C1234567890|incident-response>

# Using channel name (user-friendly)
/ketchup query #incident-response "What was the root cause?"
/ketchup status #incident-response
/ketchup report #incident-response
```

All formats work with: query, status, report, short, and long commands.

**Important Notes:**
- Channel names must follow Slack's naming rules (lowercase, no spaces)
- For private channels, the bot must be a member to resolve the name
- The channel name resolver searches both public and private channels
- If a channel isn't found, you'll get a helpful error message

### How to Add a New Slack Event Handler

Slack events (e.g., a user joining a channel, a reaction added to a message) are processed differently from slash commands. Here's a general guide to adding a handler for a new type of Slack event:

1.  **Identify the Slack Event Type and Payload:**
    *   Determine the exact event `type` string (e.g., `member_joined_channel`, `reaction_added`) as defined by the Slack API.
    *   Understand the structure of the event payload that Slack will send for this event.

2.  **Create an Event Processor Module/Function:**
    *   In the `packages/slack/channel_events/processing/` directory, create a new Python file for your event logic (e.g., `my_new_event_processor.py`).
    *   Define an asynchronous function within this file that will contain the core logic for handling the event. This function will typically accept the event payload and the DI container (for dependencies) as arguments.
    ```python
    # Example in packages/slack/channel_events/processing/my_new_event_processor.py
    async def process_my_new_event(event_payload: dict, dependencies: DIContainer):
        # event_type = event_payload.get("event", {}).get("type")
        # user_id = event_payload.get("event", {}).get("user")
        # ... extract other relevant data ...

        # Access dependencies
        # slack_ops = dependencies.get(SlackOperations) # Example
        # db_ops = dependencies.get(DatabaseOperations) # Example

        # ... your event handling logic here ...
        pass
    ```

3.  **Implement Core Event Handling Logic:**
    *   Inside your processor function, extract necessary data from the `event_payload`.
    *   Use services obtained from the `dependencies` (DIContainer) to perform actions:
        *   Interact with the database (e.g., log event details, update state).
        *   Call Slack APIs (e.g., post a message, update user info) via Slack operation clients.
        *   Invoke AI services if needed.
    *   Consider any eligibility checks. You might use or add utilities in `packages/slack/channel_events/eligibility/`.

4.  **Register the Event Handler in the Router/Dispatcher:**
    *   The incoming event needs to be routed to your new processor. This typically involves updating an event dispatcher or router.
    *   Locate the central event routing mechanism, often found in:
        *   `packages/slack/channel_events/request_processing/routing.py` (e.g., `EventDispatcher.dispatch_event`)
        *   Or a similar map or conditional block in `packages/slack/channel_events/events.py` (e.g., `handle_event_callback`).
    *   Add a condition or mapping that directs the specific Slack event `type` to your new `process_my_new_event` function.

    ```python
    # Example modification in an event router/dispatcher:
    # from packages.slack.channel_events.processing.my_new_event_processor import process_my_new_event
    # ...
    # elif event_type == "my_new_event_type_from_slack":
    #     await process_my_new_event(full_event_payload, self.dependencies)
    # ...
    ```

5.  **Logging and User Notifications (If Applicable):**
    *   Implement comprehensive logging throughout your event handler for debugging and traceability.
    *   If the event processing should result in a visible outcome or notification to a user (e.g., an error message, a confirmation), use the appropriate Slack messaging utilities.

6.  **Testing:**
    *   Write unit tests for your new event processor, mocking its dependencies.
    *   Consider integration tests if the event triggers a complex flow involving multiple services.

This provides a high-level framework. The exact implementation details, especially for routing and dependency access, will depend on the existing patterns in the `packages/slack/channel_events/` directory, which the `ketchup_code_walkthrough_documentation.md` should detail further.

### How to Create a New Async Client

If you need to interact with a new external service, you might need to create a new async client:

1. **Extend the Base Class**:
   ```python
   from packages.core.async_client import AsyncClient

   class MyServiceClient(AsyncClient):
       def __init__(self, config, secrets_manager):
           super().__init__(
               max_concurrent_requests=10,  # Set appropriate limits
               backoff_strategy=ExponentialBackoffStrategy()
           )
           self.config = config
           self.secrets_manager = secrets_manager
           self.base_url = "https://api.myservice.com"
   ```

2. **Implement API Methods**:
   ```python
   async def get_data(self, item_id):
       url = f"{self.base_url}/items/{item_id}"
       headers = {"Authorization": f"Bearer {await self._get_token()}"}
       
       response = await self._make_request(
           "GET",
           url,
           headers=headers
       )
       
       return await response.json()
   ```

3. **Add Error Handling**:
   ```python
   async def _handle_error(self, response):
       if response.status == 401:
           # Handle authentication errors
           # Maybe refresh token and retry
           raise AuthenticationError("Authentication failed")
       elif response.status >= 500:
           # Server error - can be retried
           raise RetryableError("Server error")
       else:
           # Other errors
           error_data = await response.json()
           raise ServiceError(f"Error: {error_data['message']}")
   ```

4. **Register in Factory**:
   - Add your client to the appropriate factory module
   - Make it available through the DI system

## Common Code Patterns to Know

### Async/Await Pattern

Most operations in the codebase use `async`/`await` to handle operations that might take time:

```python
async def process_command(params):
    # Wait for this operation to complete before continuing
    result = await long_running_operation()
    
    # Then proceed with the next steps
    return format_result(result)
```

This pattern allows the system to handle many operations efficiently without blocking.

### Try/Finally Pattern for Cleanup

We always ensure resources are properly cleaned up:

```python
try:
    # Do something that might raise an exception
    result = perform_operation()
    return result
finally:
    # This always runs, even if there was an error
    cleanup_resources()
```

### Factory Method Pattern

We use factory methods to create complex objects:

```python
def create_channel_info_ops(slack_config, secrets_manager):
    # Complex initialization logic here
    return ChannelInfoOps(slack_config, secrets_manager)
```

### Resilient API Calls

We wrap API calls with error handling and retries:

```python
@with_exponential_backoff(max_retries=3)
async def call_external_api(params):
    try:
        response = await make_api_call(params)
        return process_response(response)
    except TransientError:
        # This will be retried
        raise
    except PermanentError as e:
        # This won't be retried
        logger.error(f"Permanent error: {str(e)}")
        return fallback_response()
```

## Debugging Tips

1. **Check Container Logs**:
   - All application logs are written to the `./logs` volume on the EC2 instance
   - Access logs: `docker logs ketchup-app` or view files in `./logs` directory
   - Search for "ERROR" or "WARNING" to find issues

2. **Follow the Request Path**:
   - Start with the FastAPI endpoint in `ketchup-app/main.py`
   - Then `incoming_events.py`
   - Then the specific command handler
   - Check nginx logs for request routing: `docker logs nginx`

3. **Common Issues**:
   - Missing environment variables or secrets
   - Permissions problems with AWS services
   - Malformed responses to Slack
   - Timeouts for long-running operations

4. **Debugging Async Operations**:
   - Add logging before and after `await` statements
   - Check for unhandled exceptions in async functions
   - Look for operations that take too long
   - Ensure all async functions are properly awaited

## Best Practices

1. **Follow Existing Patterns**:
   - Look at similar code before implementing new features
   - Keep a consistent style and approach

2. **Error Handling**:
   - Always catch exceptions in public methods
   - Log errors with helpful context information
   - Return user-friendly error messages to Slack

3. **Resource Cleanup**:
   - Always clean up resources (database connections, HTTP sessions)
   - Use `try/finally` blocks to ensure cleanup happens

4. **Testing**:
   - Write unit tests for new functionality
   - Test both success and error cases

5. **When Working with Async Code**:
   - Always `await` async functions
   - Use `try/except` blocks around external API calls
   - Consider using timeouts for operations that might hang
   - Think about what happens if operations fail

## Eligibility Logic Example

Below is a simplified pseudocode example of how channel eligibility is determined:

```python
async def is_channel_eligible(channel_name, creator_id, channel_id, secrets_manager, dynamodb_store):
    # Check naming convention
    is_approved_name = any(keyword in channel_name.lower() for keyword in CHANNEL_KEYWORD_TO_PRODUCT)
    # Check creator (optional, logged)
    exigence_user_id = await secrets_manager.get_exigence_user_id_async()
    is_authorized_creator = creator_id in [exigence_user_id, "W7MGASQ2K"]
    # Check channel age
    channel_data = await dynamodb_store.get_channel_details(channel_id)
    is_too_old = False
    if channel_data:
        created_epoch = channel_data.get("date_created_epoch", 0)
        age_days = (now() - created_epoch) / 86400
        is_too_old = age_days > 30
    # Check token count (if available)
    token_count = channel_data.get("token_count", 0) if channel_data else 0
    is_too_many_tokens = token_count > 50000
    # Special: check for temporary unarchive
    is_temp_unarchived = await dynamodb_store.check_if_temporary_unarchive(channel_id)
    # Final eligibility
    eligible = is_approved_name and (not is_too_old or is_temp_unarchived) and not is_too_many_tokens
    return eligible
```

## Event Flow Diagram


## Error Handling Examples

**Sample log entry:**
```
ERROR [2024-06-01 12:34:56] Failed to invite bot to channel C12345: missing permissions (user_id=U67890, channel_name=incident-foo)
```

**Sample Slack DM notification:**
```
Hi! We tried to invite the bot to #incident-foo, but something went wrong (missing permissions). Please check your channel settings or contact support.
```

## Code Mapping: High-Level Step to Code

| Step                                 | File/Module/Class/Function                                      |
|-------------------------------------- |--------------------------------------------------------------- |
| Event received (creation/join/etc)    | `slack/channel_events/incoming_events.py:EventProcessor`        |
| Eligibility check                    | `slack/channel_events/eligibility/creation_checker.py:is_new_channel_eligible`<br>`slack/channel_operations/channel_eligibility.py:ChannelEligibilityService` |
| Archive/Unarchive event               | `slack/channel_events/processing/archive_processor.py:process_channel_archive`<br>`slack/channel_events/processing/unarchive_processor.py:invite_and_verify_bot_after_unarchive` |
| Metadata storage                      | `db/dynamodb_store.py:DynamoDBStore`<br>`db/models/channel_metadata.py:ChannelMetadata` |
| Temporary unarchive/restore state     | `db/operations/restore_state_operations.py`, `channel_operations/restore_state_manager.py` |
| Bot invitation                        | `channel_operations/channel_restore_ops.py`, `channel_operations/channel_bot_membership_ops.py` |
| Logging & user notification           | `core/logging.py` (logging setup)<br>`slack/blockkits/handlers/` (user messages) |
| Home tab display               | `slack/home/home.py:HomeTabHandler.handle_app_home_opened`     |
| User preferences retrieval     | `slack/home/home_preferences.py:get_user_preferences`          |
| Home tab UI construction       | `slack/home/home_utils.py:build_home_tab_blocks`               |
| Home tab publishing            | `slack/home/home_publish.py:publish_home_tab`                  |
| User preferences saving        | `slack/home/home_utils.py:save_user_preferences`               |
| Success modal display          | `slack/home/home_modals.py:open_success_modal`                 |

## Testing and Observability

- **Testing:**
  - All major flows (event handling, eligibility, archiving, unarchiving, bot join/leave) are covered by unit and integration tests in the `tests/` directory.
  - The project uses `pytest` as its test runner. Specific test categories like unit tests can be run using `make -C tests/setup test-unit`.
  - Custom `pytest` markers (e.g., `unit`) are defined in `tests/pytest.ini` to categorize tests.
  - Tests use fixtures and mocks for Slack and DynamoDB interactions.
  - Edge cases (e.g., ineligible channels, temporary unarchive, token limits) are explicitly tested.
- **Observability:**
  - All actions, decisions, and errors are logged with context (user, channel, action).
  - Temporary unarchive/restore state uses DynamoDB TTL for automatic cleanup and auditability.
  - Metrics (e.g., feedback, errors) are sent to AWS CloudWatch for monitoring.
  - User-facing errors are communicated via Slack DM for transparency.

*Note: If a channel exceeds the token limit, Ketchup will process only the last 50,000 tokens and notify the user about the truncation. See `packages/ai/core/operations/token_management.py:TokenManager.enforce_token_limit` for details.*

## Expanded Details on Key Behaviors

### Temporary Unarchive/Restore State (TTL)
- When a channel is temporarily unarchived (e.g., to run a command), the bot marks this in DynamoDB with a TTL (time-to-live) attribute, typically set to 180 seconds (`RESTORE_STATE_TTL_SECONDS`).
- This is managed by `RestoreStateOperations.set_restore_state` and ensures the temporary state is automatically cleaned up after the TTL expires.
- The bot checks for this state using `check_if_temporary_unarchive` to determine if special handling is needed.
- **Reference:** `db/operations/restore_state_operations.py`, `channel_operations/restore_state_manager.py`.

### User Notification Mechanisms
- The bot notifies users in Slack for the following scenarios:
  - **Failed bot invite:**
    - _Message:_ "Hi! We tried to invite the bot to #channel, but something went wrong (missing permissions). Please check your channel settings or contact support."
  - **Metadata storage failure:**
    - _Message:_ "Successfully invited bot to #channel, but failed to store channel metadata: <error details>"
  - **Command run on archived channel:**
    - _Message:_ "This channel was archived. Unarchiving and inviting the bot to run your command. The channel will be re-archived after the command completes."
    - _Follow-up:_ "The command has finished. The channel has been re-archived."
  - **Token truncation:**
    - _Message:_ "⚠️ The content provided exceeds the processing limit. Ketchup will proceed using only the last ~50,000 words. Content beyond this limit will be ignored."
- Notifications are sent via direct message or in-channel, depending on context.
- **Reference:** `packages/ai/core/operations/token_management.py`, `slack/blockkits/handlers/`, `channel_operations/channel_restore_ops.py`.

### Testing and Observability
- **Testing:**
  - Unit and integration tests cover all major flows, including:
    - Bot leaves ineligible channel
    - TTL cleanup after temporary unarchive
    - Token truncation and user notification
    - Archive/unarchive event handling
    - Metadata storage and error handling
  - Tests use fixtures and mocks for Slack and DynamoDB.
  - Example test: `test_restore_state_manager.py` verifies TTL cleanup.
- **Observability:**
  - All actions, decisions, and errors are logged with context (user, channel, action).
  - Metrics are sent to AWS CloudWatch (see below).
  - User-facing errors are communicated via Slack DM for transparency.
  - Dashboards and alerting can be configured in CloudWatch for key metrics (e.g., error rates, command execution times).

### Eligibility Logic: Keywords and Authorized Creators
- **Keywords:** The list of valid channel keywords is defined in `CHANNEL_KEYWORD_TO_PRODUCT` in `packages/core/constants.py` (e.g., 'acc', 'ajo', etc.).
- **Authorized Creators:** The authorized creator list includes the exigence user ID (fetched from secrets) and a hardcoded fallback (e.g., 'W7MGASQ2K'). This is checked in `is_new_channel_eligible`.
- Both are logged for auditability, but only the channel name pattern is strictly enforced for eligibility.

### Edge Case Handling
| Edge Case                                 | Bot Behavior                                                                 |
|-------------------------------------------|------------------------------------------------------------------------------|
| Channel missing in DynamoDB               | Logs warning, skips update or metadata storage                               |
| Channel already archived/unarchived       | Logs warning, skips redundant operation                                      |
| Slack API down or fails                   | Logs error, retries with backoff, notifies user if critical                  |
| DynamoDB write fails                      | Logs error, notifies user if metadata storage fails                          |
| Bot already a member of channel           | Skips invite, logs info                                                      |
| Invite fails (not permissions)            | Logs error, notifies user                                                    |
| Token count exceeds limit                 | Truncates to last 50k tokens, notifies user                                  |
| Temporary unarchive TTL expires           | State is auto-cleaned, channel may be re-archived if needed                  |
| Malformed event data                      | Logs error, skips processing                                                 |

### Bot Invitation Logic
- If the bot is already a member of the channel, the invite is skipped and this is logged.
- If the invite fails due to permissions or other errors, the user is notified and the error is logged.
- All invite attempts are handled by `SlackChannelRestoreOps` and `SlackChannelBotMembershipOps`.

### Metrics and Monitoring
- The following metrics are sent to AWS CloudWatch:
  - Number of archived/unarchived channels
  - Failed bot invites
  - Command execution times
  - Feedback events (e.g., thumbs up/down)
  - Error rates (e.g., failed metadata storage, API errors)
- These metrics are used for monitoring, alerting, and operational dashboards.
- **Reference:** Metrics are configured in `core/constants.py` (e.g., `FEEDBACK_CLOUDWATCH_NAMESPACE`) and sent via logging and monitoring utilities.

## Configuration Reference

### Environment Variables

Ketchup uses environment variables for configuration. These are set in the docker-compose.yml file:

#### Core Configuration
- **`AWS_REGION`**: AWS region for services (default: `eu-west-1`)
- **`DYNAMODB_TABLE_NAME`**: DynamoDB table name (default: `ketchup_channel_information`)
- **`AWS_SECRET_NAME`**: AWS Secrets Manager secret name (default: `Ketchup_Token_Secrets`)
- **`LOG_LEVEL`**: Logging level (default: `INFO`)
- **`PYTHONPATH`**: Python path (default: `/app`)

#### AI Configuration
- **`ENABLE_MESSAGE_ANALYSIS`**: Enable @Ketchup mention processing (default: `false`)
  - `true`: Previously processed mentions with AI analysis (deprecated - MessageAnalyzer removed)
  - `false`: Responds with fallback message
- **`OPENAI_API_VERSION`**: Azure OpenAI API version (default: `2024-08-01-preview`)
- **`AZURE_OPENAI_ENDPOINT`**: Azure OpenAI endpoint URL

#### MCP JIRA Service Configuration
- **`MCP_BASE_URL`**: URL of MCP JIRA service (default: `http://mcp-jira:8081`)
- **`JIRA_TOOL_PERSIST_CORRECTIONS`**: Enable JQL correction caching (default: `true`)
- **`JIRA_TOOL_CORRECTIONS_FILE`**: Path to corrections cache (default: `/tmp/jira_corrections_cache.json`)
- **`USE_IPAAS`**: Enable iPaaS authentication for JIRA (default: `true`)

#### Feature Flag Configuration
- **`KETCHUP_NLP_FEATURE`**: Master switch for NLP feature (default: `false`)
  - `true`: Enables NLP beta testing functionality
  - `false`: Disables NLP feature completely
- **`KETCHUP_NLP_GLOBAL`**: Enable NLP for all users (default: `false`)
  - `true`: All users have access to NLP features
  - `false`: Only beta users have access
- **Additional feature flags follow the pattern**:
  - `KETCHUP_<FEATURE>_FEATURE`: Master switch for the feature
  - `KETCHUP_<FEATURE>_GLOBAL`: Global enable for all users

#### Example Configuration
```yaml
environment:
  - AWS_REGION=eu-west-1
  - DYNAMODB_TABLE_NAME=ketchup_channel_information
  - AWS_SECRET_NAME=Ketchup_Token_Secrets
  - OPENAI_API_VERSION=2024-08-01-preview
  - AZURE_OPENAI_ENDPOINT=https://ketchup-prod.openai.azure.com/...
  - LOG_LEVEL=INFO
  - PYTHONPATH=/app
  - ENABLE_MESSAGE_ANALYSIS=true
  - MCP_BASE_URL=http://mcp-jira:8081
  - JIRA_TOOL_PERSIST_CORRECTIONS=true
  - KETCHUP_NLP_FEATURE=true
  - KETCHUP_NLP_GLOBAL=false
```

### Secrets Manager Configuration

Sensitive configuration is stored in AWS Secrets Manager:

- **Slack Tokens**: Bot user OAuth token, signing secret
- **Azure OpenAI Keys**: API keys for AI services
- **JIRA Credentials**: iPaaS authentication tokens
- **Admin Users**: List of admin users for usage statistics
- **Bot User ID**: Slack bot user ID for filtering

## Real Container Log Output

Below is a sample of real log output from the running FastAPI application in Docker containers. These logs show event processing, initialization, and error handling as they occur in production:

```
2025-06-16T17:28:53.933000+00:00 INFO:     Started server process [1]
2025-06-16T17:28:53.934000+00:00 INFO:     Waiting for application startup.
2025-06-16T17:28:53.935000+00:00 INFO:     Application startup complete.
2025-06-16T17:28:54.778000+00:00 - main - INFO - Received Slack event at /slack/events endpoint
2025-06-16T17:28:54.874000+00:00 - main - INFO - Request acknowledged, processing in background
2025-06-16T17:28:54.990000+00:00 - main - INFO - Background task started for event processing
2025-05-11T17:28:54,990 - packages.core.di_container - INFO - Initializing DIContainer with all modular clients
2025-05-11T17:28:54,990 - packages.core.client_factory.secrets_factory - INFO - Initializing core/global client instances (e.g., secrets_manager)
2025-05-11T17:28:54,998 - packages.core.client_factory.cloud_factory - INFO - All Cloud client instances initialized successfully: ['cloudwatch_metrics']
2025-05-11T17:28:54,998 - packages.core.client_factory.slack_factory - INFO - Initializing all Slack-related client instances using SLACK_CLIENT_MAP
2025-05-11T17:28:55,129 - packages.slack.config.slack_config - INFO - SlackConfig initialized with instance-specific token.
2025-05-11T17:28:55,599 - packages.slack.channel_events.request_processing.dependency_setup - INFO - Dependencies setup complete.
2025-05-11T17:28:55,600 - packages.slack.channel_events.incoming_events - INFO - Creating EventProcessor instance for the request.
2025-05-11T17:28:55,600 - packages.slack.channel_events.incoming_events - INFO - Processing incoming request within EventProcessor
2025-05-11T17:28:55,600 - packages.slack.authorisation.auth - INFO - Entering verify_slack_signature
2025-05-11T17:28:55,777 - packages.slack.authorisation.auth - INFO - Slack signing secret retrieved successfully.
2025-05-11T17:28:55,778 - packages.slack.authorisation.auth - INFO - Signature verification result: True
2025-05-11T17:28:55,778 - packages.slack.channel_events.request_processing.routing - INFO - Dispatching actual event type: channel_archive
2025-05-11T17:28:55,778 - packages.slack.channel_events.events - INFO - Starting handle_channel_archive function.
2025-05-11T17:28:55,778 - packages.slack.channel_events.processing.archive_processor - INFO - Checking if channel C08RYEAMT8C exists in DynamoDB for archive processing.
2025-05-11T17:28:55,893 - packages.db.operations.channel_query_operations - INFO - No channel found for ID: C08RYEAMT8C
2025-05-11T17:28:55,893 - packages.slack.channel_events.processing.archive_processor - WARNING - Channel C08RYEAMT8C not found in DynamoDB. Skipping archive update.
2025-05-11T17:28:55,894 - packages.core.di_container - INFO - Cleaning up DIContainer
2025-05-11T17:28:56.004 - packages.core.cleanup_utils - INFO - Resource cleanup completed
```

**Key points:**
- FastAPI application starts and waits for requests
- Events are received at the `/slack/events` endpoint and logged
- Requests are acknowledged immediately to meet Slack's 3-second timeout
- Background tasks handle the actual processing asynchronously
- Persistent DI container means no repeated initialization overhead
- Warnings and errors (e.g., channel not found) are clearly marked
- Logs are accessible via Docker commands or the `./logs` volume

These logs provide a real-world view of how the system operates and are invaluable for debugging and onboarding.

## Where to Start

If you're new to the Ketchup codebase, start by tracing a Slack command from end to end:
- Review **Section 7: How a Slack Command Works: Step by Step** for the high-level flow.
- Use **Section 5: Codebase Organization** to locate the relevant modules and files.
- For your first contribution, consider adding a new command or improving a test—see the "Common Development Tasks" section for guidance.

### Initial Setup and First Steps

The recommended way to set up your development environment and run tests is by using the `Makefile` located in the `tests/setup/` directory.

1.  **Prerequisites:**
    Ensure you have the following installed:
    *   Python 3.11+ (using [pyenv](https://github.com/pyenv/pyenv) is recommended for managing Python versions).
    *   `make` (standard on most Unix-like systems; may need to be installed on Windows).

2.  **Clone the Repository:**
    Open your terminal and clone the repository (replace `<repository-url>` with the actual URL):
    ```bash
    git clone <repository-url>
    cd ketchup-project-directory # Or your project's root directory
    ```

3.  **Set Up Environment and Install Dependencies:**
    Navigate to the project root in your terminal and run the following `make` command:
    ```bash
    make -C tests/setup setup
    ```
    This command will:
    *   Create a Python virtual environment inside `tests/setup/.venv/`.
    *   Activate it.
    *   Install all necessary dependencies listed in `tests/setup/requirements.txt`.

4.  **Run Tests:**
    To verify your setup and run all tests (unit, integration, and end-to-end), execute:
    ```bash
    make -C tests/setup test
    ```
    To run only unit tests:
    ```bash
    make -C tests/setup test-unit
    ```
    (Refer to `tests/setup/README-setup.md` for a full list of `make` targets, including integration and e2e tests.)

5.  **Basic Configuration (if applicable):**
    For general development and running most unit/integration tests, the Ketchup application might use a secrets management system for sensitive credentials, and local AWS configuration (e.g., `~/.aws/credentials` and `~/.aws/config`) for interacting with AWS services.

    However, be aware that:
    *   Some specific test scripts or components (like the concurrency test `tests/setup/test_con.py`) might handle their configuration differently, for example, by expecting system environment variables to be set (e.g., `AWS_PROFILE`, `AWS_DEFAULT_REGION`) or by having placeholder values directly within the script for specific test scenarios.
    *   For running integration tests that interact with live external services (Slack, Azure OpenAI), you will need to ensure your environment is correctly configured with the necessary API keys and tokens. These are typically managed via a secure secrets management solution and accessed by the application; direct use of `.env` files for these keys in production-like testing is generally discouraged for security reasons.
    *   Always refer to the specific README or comments within a test module (like `tests/setup/README-setup.md`) for detailed configuration requirements for that particular test or component.
    *   **Never commit actual secrets or sensitive API keys to version control.**

6.  **Explore the Code:**
    With the setup complete, you can activate the virtual environment manually if needed (`source tests/setup/.venv/bin/activate`) and start exploring the codebase using your preferred IDE. The sections above in this document, and the more detailed `ketchup_code_walkthrough_documentation.md`, will guide you further.

This initial setup should provide you with a functional development environment. For more advanced testing scenarios (like Docker-based concurrency tests) or troubleshooting, refer to `tests/setup/README-setup.md`.

---

### How to Modify Home Tab Content

If you need to update the Slack Home tab appearance or add new preference options:

1. **Update Block Builder**:
   - Modify `home_utils.py:build_home_tab_blocks()` to add new UI elements
   - Follow Slack's Block Kit format for UI components

   ```python
   # Example: Adding a new section to the Home tab
   blocks.append({
       "type": "section",
       "text": {
           "type": "mrkdwn",
           "text": "*New Setting*\nDescription of the new setting."
       }
   })
   
   # Example: Adding a new selector
   blocks.append({
       "type": "actions",
       "block_id": "new_setting_selection",
       "elements": [
           {
               "type": "static_select",
               "action_id": "new_setting_select",
               "placeholder": {
                   "type": "plain_text",
                   "text": "Select option",
               },
               "options": [
                   {
                       "text": {"type": "plain_text", "text": "Option 1"},
                       "value": "option_1"
                   },
                   {
                       "text": {"type": "plain_text", "text": "Option 2"},
                       "value": "option_2"
                   }
               ]
           }
       ]
   })
   ```

2. **Update Preference Extraction**:
   - Modify `home_utils.py:extract_preferences_from_state()` to handle new UI elements
   - Ensure your extraction logic matches the block_id and action_id used in the UI

   ```python
   # In extract_preferences_from_state function:
   new_setting = get_selected_option(
       state.get("new_setting_selection"), "new_setting_select"
   )
   # Add to returned preferences
   return {
       # Existing preferences...
       "new_setting": new_setting or "default_value",
   }
   ```

3. **Update Default Preferences**:
   - Modify `home_preferences.py:get_user_preferences()` to include defaults for new settings

   ```python
   default_prefs = {
       # Existing defaults...
       "new_setting": "default_value",
   }
   ```

4. **Test Updates**:
   - Test the Home tab in development environment
   - Verify that new settings are saved to DynamoDB correctly
   - Ensure the UI renders properly in various Slack clients

### How to Add a Feature Behind a Flag

When adding new functionality that needs controlled rollout, use the feature flag system:

1. **Define the Feature Check** (if using environment variables):
   ```python
   # In packages/core/config/feature_flags.py
   @staticmethod
   def is_my_feature_enabled() -> bool:
       """Check if my feature is enabled for beta testing."""
       return os.getenv("KETCHUP_MY_FEATURE_FEATURE", "false").lower() == "true"
   
   @staticmethod
   def is_my_feature_global() -> bool:
       """Check if my feature is enabled globally."""
       return os.getenv("KETCHUP_MY_FEATURE_GLOBAL", "false").lower() == "true"
   ```

2. **Add Feature Check Method**:
   ```python
   # In packages/slack/command_processing/feature_service.py
   async def is_my_feature_enabled_for_user(self, user_id: str) -> bool:
       """Check if my feature is enabled for a specific user."""
       # Check global flag first
       if FeatureFlags.is_my_feature_global():
           return True
       
       # Check user-specific flag
       try:
           return await self.user_store.get_user_feature(user_id, "my_feature_enabled") is True
       except Exception as e:
           logger.error(f"Error checking my feature flag: {e}")
           return False
   ```

3. **Use the Feature Flag in Your Code**:
   ```python
   # In your command handler or service
   async def process_command(self, user_id: str, params: CommandParams):
       # Check if feature is enabled for this user
       if await self.feature_service.is_my_feature_enabled_for_user(user_id):
           # New feature implementation
           result = await self.new_feature_logic(params)
           return self.format_new_response(result)
       else:
           # Existing behavior or message
           return "This feature is coming soon! Ask your admin for beta access."
   ```

4. **Test the Feature**:
   - Set `KETCHUP_MY_FEATURE_FEATURE=true` locally
   - Use `/ketchup feature my_feature enable @testuser` to add beta users
   - Test both enabled and disabled states
   - When ready, set `KETCHUP_MY_FEATURE_GLOBAL=true` for full rollout