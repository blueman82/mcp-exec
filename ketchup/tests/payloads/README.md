# Test Payloads for Local Development

This directory contains sample Slack payloads for testing Ketchup locally without needing a real Slack workspace.

## Usage

Start your local development stack:
```bash
cd infrastructure/
docker-compose -f docker-compose.yml -f docker-compose.local.yml up
```

Then test with curl:
```bash
# Test a slash command
curl -X POST http://localhost:80/slack/events \
  -H "Content-Type: application/json" \
  -d @test-payloads/sample-command.json

# Test an @mention
curl -X POST http://localhost:80/slack/events \
  -H "Content-Type: application/json" \
  -d @test-payloads/app-mention.json

# Test channel creation event
curl -X POST http://localhost:80/slack/events \
  -H "Content-Type: application/json" \
  -d @test-payloads/channel-created.json

# Test interactive button click
curl -X POST http://localhost:80/slack/events \
  -H "Content-Type: application/json" \
  -d @test-payloads/interactive-button.json
```

## Available Payloads

### sample-command.json
Simulates a `/ketchup status C1234567890` command

### app-mention.json  
Simulates an @Ketchup mention asking for channel status

### channel-created.json
Simulates a new channel being created (tests eligibility logic)

### interactive-button.json
Simulates a user clicking a feedback button

## Creating Custom Payloads

You can modify these payloads or create new ones. Key fields to update:
- `channel_id` / `channel.id`: The channel ID
- `user_id` / `user.id`: The user ID
- `text`: The command text or message content
- `response_url`: Where Slack would send responses (not used locally)

## Notes

- These payloads bypass Slack signature verification for local testing
- The `token` field is ignored in local development
- Response URLs won't work locally unless you mock the Slack API
- For full integration testing, use ngrok with a real Slack workspace