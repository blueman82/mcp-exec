# Ketchup Auto-Status Updater Tests

This directory contains unit tests for the Ketchup Auto-Status Updater feature.

## Running Tests

From the `tests/setup/` directory:

```bash
# Run all auto-status tests
make test-unit ARGS="-k test_ketchup_status_updater"

# Run specific test files
make test-unit ARGS="-k test_processor"
make test-unit ARGS="-k test_status_generator"
make test-unit ARGS="-k test_auto_status_prompt"

# Run specific test methods
make test-unit ARGS="-k test_should_process_channel_first_run"
make test-unit ARGS="-k test_generate_and_post_status_with_jira"

# Run with verbose output
make test-unit ARGS="-k test_ketchup_status_updater -v"

# Run with coverage
make test-unit ARGS="-k test_ketchup_status_updater --cov=ketchup_status_updater"
```

## Test Structure

- `test_processor.py`: Tests for the AutoStatusProcessor class
  - Channel eligibility logic
  - Pause functionality
  - Error handling and retries
  - Fallback mechanisms

- `test_status_generator.py`: Tests for the AutoStatusGenerator class
  - Message fetching and preparation
  - JIRA comment integration
  - AI response generation
  - Slack posting

- `test_auto_status_prompt.py`: Tests for prompt generation
  - System prompt formatting
  - User prompt generation
  - Default value handling