# Integration Test Framework

This directory contains integration tests that use the full DI container with real service connections.

## Overview

The `base_integration_test.py` module provides a reusable framework for creating integration tests that need access to real services like:
- DynamoDB
- Slack API
- OpenAI API
- JIRA (via MCP)
- AWS Secrets Manager
- CloudWatch

## Usage

### Method 1: Class-Based Tests

Create a subclass of `BaseIntegrationTest`:

```python
from base_integration_test import BaseIntegrationTest

class MyIntegrationTest(BaseIntegrationTest):
    def __init__(self):
        super().__init__(
            test_name="my_test",
            env_vars={"MY_FEATURE_FLAG": "true"}
        )
    
    async def run_test(self) -> bool:
        # Get services you need
        service = self.get_service("service_name")
        
        # Run your test logic
        result = await service.some_method()
        
        return True  # or False if test failed
```

### Method 2: Functional Tests

Use `run_simple_integration_test` for simpler tests:

```python
from base_integration_test import run_simple_integration_test

async def test_something(services, logger):
    """Your test function."""
    service = services["service_name"]
    
    # Test logic here
    result = await service.some_method()
    
    return True  # or False

# Run it
success = await run_simple_integration_test(
    test_name="my_simple_test",
    test_func=test_something,
    required_services=["service_name", "other_service"]
)
```

## Available Services

Services you can request from the DI container:

- `dynamodb_store` - DynamoDB operations
- `slack_posting` - Post messages to Slack
- `channel_operations` - Channel metadata operations
- `info_ops` - Slack channel info operations
- `msg_ops` - Fetch Slack messages
- `user_ops` - Slack user operations
- `openai` - OpenAI API handler
- `mcp_client` - JIRA MCP client
- `secrets_manager` - AWS Secrets Manager
- `slack_config` - Slack configuration
- `cloud_watch` - CloudWatch metrics

## Examples

See the example files:
- `test_status_update_implementation.py` - Status updater test (class-based)
- `test_jira_integration_example.py` - JIRA operations (both methods)
- `test_slack_integration_example.py` - Slack operations (functional)
- `test_ai_integration_example.py` - OpenAI operations (functional)

## Running Tests

```bash
# Run individual test
python tests/integration/test_status_update_implementation.py

# Run with pytest
pytest tests/integration/test_*.py -v
```

## Environment Variables

The base class automatically sets:
- `AWS_PROFILE=campaign_prod_v7`
- `AWS_DEFAULT_REGION=eu-west-1`

You can add more via the `env_vars` parameter.

## Best Practices

1. **Service Selection**: Only request services you actually need
2. **Error Handling**: Tests should catch and log errors appropriately
3. **Cleanup**: The framework handles container cleanup automatically
4. **Logging**: Use the provided logger for consistent output
5. **Return Values**: Return `True` for pass, `False` for fail

## Creating New Tests

1. Decide if you need a class (complex setup) or function (simple test)
2. Identify which services you need from the DI container
3. Set any required environment variables
4. Implement your test logic
5. Return boolean indicating success/failure

The framework handles all the container initialization, environment setup, and cleanup for you!