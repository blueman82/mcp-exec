"""
constants.py

This module contains constants used across the application.
"""

import os
import re

import aiohttp

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ketchup_channel_information")
AWS_SECRET_NAME = os.environ.get("AWS_SECRET_NAME", "Ketchup_Token_Secrets")

# Azure OpenAI Configuration
OPENAI_API_VERSION = "2024-12-01-preview"
DEFAULT_AZURE_OPENAI_ENDPOINT = f"https://ketchup-prod1.openai.azure.com/openai/deployments/gpt-5.4-mini/chat/completions?api-version={OPENAI_API_VERSION}"
# Allow override via environment variable
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", DEFAULT_AZURE_OPENAI_ENDPOINT)

# Azure OpenAI Embeddings Configuration
EMBEDDINGS_API_VERSION = "2023-05-15"
AZURE_OPENAI_EMBEDDINGS_ENDPOINT = (
    "https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings"
)
AZURE_OPENAI_EMBEDDINGS_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_EMBEDDINGS_ENDPOINT", AZURE_OPENAI_EMBEDDINGS_ENDPOINT
)

MAX_PROCESSABLE_TOKENS = 50000  # Maximum number of tokens that can be processed at once

# Token Tracker Configuration
INPUT_COST_PER_MILLION = 0.75  # $0.75 per 1M tokens (gpt-5.4-mini)
OUTPUT_COST_PER_MILLION = 4.50  # $4.50 per 1M tokens (gpt-5.4-mini)


# Slack Configuration
SLACK_API_TIMEOUT_SECONDS = 120  # Timeout in seconds for Slack API calls
SLACK_API_TIMEOUT = aiohttp.ClientTimeout(
    total=SLACK_API_TIMEOUT_SECONDS
)  # aiohttp ClientTimeout object

# General Configuration
MAX_RETRIES = 10  # Maximum number of retries for API calls
BATCH_SIZE = 100  # Batch size for fetching messages

# Feature Flags
USE_PIPELINE_PROCESSING = (
    os.environ.get("USE_PIPELINE_PROCESSING", "false").lower() == "true"
)  # Enable pipeline processing for message retrieval

# Keep-Alive Connection Tuning
# Enable optimized keep-alive settings for HTTP connections to reduce overhead
KEEPALIVE_ENABLED = os.environ.get("KETCHUP_KEEPALIVE_ENABLED", "false").lower() == "true"

# Keep-alive timeout in seconds (default: 60s vs aiohttp default 15s)
# Connections are kept alive longer to reduce TCP handshake overhead
KEEPALIVE_TIMEOUT = int(os.environ.get("KETCHUP_KEEPALIVE_TIMEOUT", "60"))

# DNS cache TTL in seconds (default: 300s/5min vs aiohttp default 10s)
# Reduces DNS lookup overhead for frequently accessed endpoints like Azure OpenAI
DNS_CACHE_TTL = int(os.environ.get("KETCHUP_DNS_CACHE_TTL", "300"))

# DynamoDB Sort Keys (Using constants for maintainability)
DYNAMODB_SK_RESTORE_STATE = "RESTORE_STATE"
RESTORE_STATE_TTL_SECONDS = 180

# MAX BATCH SIZE FOR DYNAMODB BATCH GET ITEM
MAX_BATCH_SIZE = 100

# Functional Constants
CHANNEL_KEYWORD_TO_PRODUCT = {
    "acc": "campaign",
    "acs": "campaign",
    "campaign": "campaign",
    "camp": "campaign",
    "ajo": "ajo",
    "adobe_journey": "ajo",
    "adobe-journeys": "ajo",
}
ELIGIBILITY_MAX_CHANNEL_AGE_DAYS = 30
ELIGIBILITY_REASON_PREFIX_AGE = "Channel is over"

# Metrics and Monitoring Configuration - using file-based metrics storage

# Regular expression to validate Slack channel IDs (C or G followed by 8-11 alphanumeric chars)
SLACK_CHANNEL_ID_REGEX = re.compile(r"^(C|G)[A-Z0-9]{8,11}$")

# Regular expression to parse Slack channel mentions <#CHANNEL_ID|channel-name>
SLACK_CHANNEL_MENTION_REGEX = re.compile(r"^<#([CG][A-Z0-9]{8,11})\|([^>]+)>$")

# Regular expression to validate channel names (starting with # followed by valid chars)
SLACK_CHANNEL_NAME_REGEX = re.compile(r"^#([a-z0-9][a-z0-9_-]{0,80})$")

# Slack Feedback Channel
FEEDBACK_CHANNEL = "C08CQN1JCSC"

# Test Channel for auto-status testing
TEST_CHANNEL = "C094DQY7HLH"

# Archive/Slack Fallback Batching Constants
TEXT_BATCH_CHAR_LIMIT = 39000  # Maximum characters per text batch message
MAX_TEXT_BATCHES = 4  # Maximum number of fallback text batches to send
MAX_CHANNELS_PER_TEXT_BATCH = 65  # Maximum channels per batch, regardless of character count

# Access Request Configuration
ACCESS_REQUEST_CHANNEL = "C090V88CB1N"  # ketchup_access (for admin approvals)
KETCHUP_ALERTS_CHANNEL = "C0957H8ASH2"  # ketchup-alerts (for monitoring and errors)
ACCESS_REQUEST_TTL_HOURS = 24
ACCESS_REQUEST_RATE_LIMIT_PER_HOUR = 3
ACCESS_REQUEST_LOCK_TIMEOUT = 60  # seconds
KETCHUP_WIKI_URL = "https://wiki.corp.adobe.com/display/neolane/Ketchup+How-To"

# Trust Endorsement Configuration
TRUST_ENABLED_CHANNELS = {
    "C094DQY7HLH",  # Test channel (for testing trust endorsement functionality)
    "C08CQN1JCSC",  # Feedback channel
    # Add more channel IDs here as needed
}

# Access Request Status Values
ACCESS_REQUEST_STATUS = {
    "PENDING": "pending",
    "APPROVED": "approved",
    "REJECTED": "rejected",
    "EXPIRED": "expired",
}

# Local Metrics Configuration
ACCESS_REQUEST_METRICS_LOG_FILE = "/var/log/ketchup/access_requests.log"
ACCESS_REQUEST_STATS_FILE = "/var/log/ketchup/access_request_stats.json"

# Metrics Names for local logging
ACCESS_REQUEST_METRICS = {
    "CREATED": "access_request_created",
    "APPROVED": "access_request_approved",
    "REJECTED": "access_request_rejected",
    "RATE_LIMITED": "access_request_rate_limited",
    "DUPLICATE": "access_request_duplicate",
    "EXPIRED": "access_request_expired",
    "ERROR": "access_request_error",
}
