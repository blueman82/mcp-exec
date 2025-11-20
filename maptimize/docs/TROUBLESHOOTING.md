# Maptimize Troubleshooting Guide

Common issues, debugging techniques, and solutions for the Maptimize Slack bot.

## Table of Contents

1. [Connection Issues](#connection-issues)
2. [Slack Bot Problems](#slack-bot-problems)
3. [AWS Integration Issues](#aws-integration-issues)
4. [Docker and Container Issues](#docker-and-container-issues)
5. [Performance Issues](#performance-issues)
6. [Configuration Issues](#configuration-issues)
7. [Logging and Debugging](#logging-and-debugging)
8. [Getting Help](#getting-help)

## Connection Issues

### Bot Not Responding to Messages

**Symptoms**:
- Bot doesn't respond to mentions in Slack
- Slash commands are not executed
- No error messages visible

**Debugging Steps**:

```bash
# Check if container is running
docker ps | grep maptimize

# Check container logs
docker logs maptimize-bot

# Look for specific errors
docker logs maptimize-bot | grep -i "error\|exception\|slack"

# Check if Socket Mode is connected
docker logs maptimize-bot | grep -i "socket"
```

**Solutions**:

1. **Verify Slack tokens are correct**
   ```bash
   # Check token in Secrets Manager
   aws secretsmanager get-secret-value \
     --secret-id maptimize/slack-tokens

   # Token format should be: xapp-1-... for app token, xoxb-... for bot token
   ```

2. **Check Slack app configuration**
   - Go to Slack app settings
   - Verify Socket Mode is enabled
   - Confirm bot token has required scopes
   - Check Event Subscriptions are set up

3. **Restart the bot**
   ```bash
   docker restart maptimize-bot

   # Wait for startup
   sleep 10

   # Verify health
   docker inspect --format='{{.State.Health.Status}}' maptimize-bot
   ```

4. **Check network connectivity**
   ```bash
   # From inside container
   docker exec maptimize-bot curl -I https://slack.com

   # Check if DNS resolution works
   docker exec maptimize-bot nslookup slack.com
   ```

### Socket Mode Connection Failures

**Symptoms**:
- Logs show "Socket Mode connection failed"
- Bot crashes repeatedly
- Slow startup process

**Debugging**:

```bash
# Check logs for Socket Mode errors
docker logs maptimize-bot | grep -i "socket\|connect"

# Check token validity
docker logs maptimize-bot | grep -i "token"
```

**Solutions**:

1. **Verify Socket Mode is enabled**
   - Slack App → Socket Mode → Toggle "Enable Socket Mode"
   - Confirm toggle is ON (blue)

2. **Check app token format**
   ```bash
   # App token should start with xapp-1-
   aws secretsmanager get-secret-value \
     --secret-id maptimize/slack-tokens \
     | grep -o '"app_token":"[^"]*"'
   ```

3. **Regenerate tokens if needed**
   - Go to Slack app settings
   - Generate new app token
   - Update AWS Secrets Manager
   - Restart bot

4. **Check firewall/network rules**
   ```bash
   # Verify outbound HTTPS connections allowed
   docker exec maptimize-bot curl -v https://wss-primary.slack.com
   ```

## Slack Bot Problems

### Bot Can't Create Tasks in Jira

**Symptoms**:
- Task creation requests fail silently
- Error messages about Jira connection
- Logs show API call failures

**Debugging**:

```bash
# Check Jira configuration
docker logs maptimize-bot | grep -i "jira"

# Check for API errors
docker logs maptimize-bot | grep -i "401\|403\|404"
```

**Solutions**:

1. **Verify Jira credentials**
   ```bash
   # Check Jira token in Secrets Manager
   aws secretsmanager get-secret-value \
     --secret-id maptimize/slack-tokens

   # Ensure Jira URL is correct in configuration
   ```

2. **Check Jira project configuration**
   - Verify project key matches configuration
   - Confirm user has permission to create issues
   - Check issue type is available in project

3. **Test Jira connection manually**
   ```bash
   # From inside container
   docker exec maptimize-bot python -c "
   import httpx
   import json

   headers = {'Authorization': 'Bearer YOUR_TOKEN'}
   response = httpx.get('https://jira.example.com/rest/api/3/projects')
   print(response.status_code)
   print(response.text[:200])
   "
   ```

4. **Check Jira API permissions**
   - Go to Jira → Personal Settings → API Tokens
   - Regenerate token if needed
   - Ensure token has project access

### Message Formatting Issues

**Symptoms**:
- Messages appear incorrectly formatted in Slack
- Block Kit elements not rendering
- Links or buttons not appearing

**Debugging**:

```bash
# Check formatter logs
docker logs maptimize-bot | grep -i "format"

# Test formatter directly
docker exec maptimize-bot python -c "
from maptimize.formatter import format_response
result = format_response('Title', 'Content', 'https://example.com')
print(result)
"
```

**Solutions**:

1. **Verify Block Kit syntax**
   - Check Slack Block Kit documentation
   - Use Slack's Block Kit Builder to validate

2. **Check required fields**
   - Ensure title and content are non-empty
   - Validate URL format if provided
   - Check for special characters needing escaping

3. **Test with Slack API directly**
   ```bash
   # Use Slack's API tester
   # Go to api.slack.com/methods/chat.postMessage
   ```

### Slash Command Not Recognized

**Symptoms**:
- "Command not found" error in Slack
- Slash command doesn't trigger bot
- Different command partially works

**Debugging**:

```bash
# Check handler logs
docker logs maptimize-bot | grep -i "slash\|command"

# Check registered commands
docker exec maptimize-bot python -c "
from maptimize.bot import app
for handler in app._handlers:
    print(handler)
"
```

**Solutions**:

1. **Verify command is registered**
   - Go to Slack app settings → Slash Commands
   - Check command name matches code
   - Verify request URL is correct

2. **Check command scope**
   - Ensure command is available to workspace
   - Verify users have permission to use command

3. **Restart bot after changing commands**
   ```bash
   docker restart maptimize-bot
   ```

4. **Test command in Slack**
   - Type `/maptimize --help`
   - Check for error messages
   - Verify command syntax

## AWS Integration Issues

### Can't Access AWS Secrets Manager

**Symptoms**:
- Logs show "Failed to retrieve secrets"
- Bot crashes on startup
- "Access Denied" errors

**Debugging**:

```bash
# Check AWS credentials
docker exec maptimize-bot python -c "
import boto3
try:
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()
    print('AWS Identity:', identity)
except Exception as e:
    print('Error:', e)
"

# Check IAM role
aws iam get-role --role-name ec2-maptimize-role
```

**Solutions**:

1. **Verify IAM role permissions**
   ```bash
   # Check role has Secrets Manager access
   aws iam get-role-policy \
     --role-name ec2-maptimize-role \
     --policy-name SecretsManagerReadOnlyAccess
   ```

2. **Check instance profile**
   ```bash
   # EC2 instance should have role attached
   aws ec2 describe-instances \
     --instance-ids INSTANCE_ID \
     --query 'Reservations[0].Instances[0].IamInstanceProfile'
   ```

3. **Test Secrets Manager access**
   ```bash
   # From container
   docker exec maptimize-bot python -c "
   import boto3
   client = boto3.client('secretsmanager', region_name='eu-west-1')
   try:
       secret = client.get_secret_value(
           SecretId='maptimize/slack-tokens'
       )
       print('Secret retrieved successfully')
   except Exception as e:
       print(f'Error: {e}')
   "
   ```

4. **Verify secret name and region**
   ```bash
   # Confirm secret exists
   aws secretsmanager list-secrets --region eu-west-1 | grep maptimize

   # Check secret value
   aws secretsmanager get-secret-value \
     --secret-id maptimize/slack-tokens \
     --region eu-west-1
   ```

### AWS Region Mismatch

**Symptoms**:
- "Resource not found" errors
- Secrets Manager lookups fail
- EC2 operations not working

**Debugging**:

```bash
# Check configured region
docker exec maptimize-bot env | grep AWS_REGION

# Check environment variable
docker inspect maptimize-bot | grep AWS_REGION
```

**Solutions**:

1. **Verify region setting**
   ```bash
   # Should match where resources are created
   # Check with:
   aws configure get region
   ```

2. **Update region if needed**
   ```bash
   # Stop container
   docker stop maptimize-bot

   # Update environment variable
   # Edit docker-compose.yml or run command with correct region

   # Restart
   docker run -d \
     -e AWS_REGION=eu-west-1 \
     ... maptimize-bot
   ```

3. **Verify resource exists in region**
   ```bash
   # Check secret in correct region
   aws secretsmanager describe-secret \
     --secret-id maptimize/slack-tokens \
     --region eu-west-1
   ```

## Docker and Container Issues

### Container Exits Immediately

**Symptoms**:
- Container starts then stops
- Exit code non-zero
- No logs generated

**Debugging**:

```bash
# Check exit code
docker inspect maptimize-bot | grep ExitCode

# View last logs
docker logs maptimize-bot

# Try running interactively
docker run -it \
  -e SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens \
  -e AWS_REGION=eu-west-1 \
  maptimize:latest
```

**Solutions**:

1. **Check Python errors**
   ```bash
   # Look for Python traceback
   docker logs maptimize-bot | tail -50
   ```

2. **Verify all dependencies installed**
   ```bash
   # Rebuild image
   docker build --tag maptimize:latest .

   # Check for build errors
   ```

3. **Check environment variables**
   ```bash
   # Ensure all required variables set
   docker inspect maptimize-bot | grep Env
   ```

4. **Test import manually**
   ```bash
   docker run --rm maptimize:latest python -c "import maptimize"
   ```

### High Memory Usage

**Symptoms**:
- Container using excessive memory
- Container gets killed by system
- Out of Memory errors

**Debugging**:

```bash
# Check memory usage
docker stats maptimize-bot

# Check container limit
docker inspect maptimize-bot | grep Memory

# Check process memory
docker exec maptimize-bot ps aux
```

**Solutions**:

1. **Set memory limit**
   ```bash
   # Stop container
   docker stop maptimize-bot

   # Set memory limit
   docker update --memory 512m maptimize-bot

   # Restart
   docker start maptimize-bot
   ```

2. **Check for memory leaks**
   ```bash
   # Monitor memory over time
   docker stats --no-stream

   # If constantly increasing, check for leaks in code
   ```

3. **Reduce image size**
   ```bash
   # Multi-stage build helps (already in Dockerfile)
   docker history maptimize:latest
   ```

### Health Check Failing

**Symptoms**:
- Health check shows "unhealthy"
- Container gets restarted repeatedly
- Services depend on unhealthy container

**Debugging**:

```bash
# Check health status
docker inspect --format='{{.State.Health}}' maptimize-bot

# Run health check manually
docker exec maptimize-bot python -c "import maptimize; print('healthy')"

# Check logs around restart times
docker logs maptimize-bot --timestamps | tail -50
```

**Solutions**:

1. **Increase health check timeout**
   ```bash
   # Edit docker-compose.yml
   # Increase timeout value in healthcheck section

   # Rebuild and restart
   docker-compose up -d
   ```

2. **Check dependencies are available**
   - Verify AWS Secrets Manager accessible
   - Check network connectivity to Slack
   - Ensure database/cache connections work

3. **Verify health check command**
   ```bash
   # Test the command
   docker exec maptimize-bot python -c "import maptimize; print('healthy')"
   ```

## Performance Issues

### Slow Message Processing

**Symptoms**:
- Bot takes long time to respond
- Users report delays in Slack
- High latency in logs

**Debugging**:

```bash
# Check response times in logs
docker logs maptimize-bot | grep "processed in\|duration"

# Monitor CPU usage
docker stats maptimize-bot

# Check for blocking operations
docker exec maptimize-bot python -c "
import sys
sys.settrace(lambda *args: print(args[2]))
from maptimize import bot
"
```

**Solutions**:

1. **Check AWS API latency**
   ```bash
   # Measure Secrets Manager retrieval time
   time docker exec maptimize-bot python -c "
   import boto3
   client = boto3.client('secretsmanager', region_name='eu-west-1')
   secret = client.get_secret_value(SecretId='maptimize/slack-tokens')
   "
   ```

2. **Optimize database queries**
   - Check process configuration for inefficiencies
   - Profile slow functions
   - Add caching where appropriate

3. **Scale resources**
   ```bash
   # Increase container resources
   docker update --cpus 2 maptimize-bot
   docker update --memory 1g maptimize-bot
   ```

### High CPU Usage

**Symptoms**:
- CPU utilization consistently high
- Instance becomes unresponsive
- Increased costs

**Debugging**:

```bash
# Check CPU usage
docker stats maptimize-bot

# Get top processes
docker exec maptimize-bot top -b -n 1

# Profile CPU usage
docker exec maptimize-bot python -m cProfile -s cumtime /path/to/bot.py
```

**Solutions**:

1. **Identify CPU-intensive operations**
   - Check for infinite loops
   - Look for inefficient algorithms
   - Review recent changes

2. **Optimize code**
   - Use faster algorithms
   - Cache expensive computations
   - Reduce unnecessary processing

3. **Scale horizontally**
   - Run multiple bot instances
   - Use load balancer
   - Implement message queue

## Configuration Issues

### Wrong Environment Variables

**Symptoms**:
- Bot starts but can't find configuration
- "Variable not found" errors
- Default values used instead of intended

**Debugging**:

```bash
# Check environment variables
docker inspect maptimize-bot | grep Env

# Check specific variable
docker exec maptimize-bot env | grep SLACK

# Print configuration
docker exec maptimize-bot python -c "
from maptimize.config import Config
config = Config()
print('Environment:', config.environment)
print('Region:', config.aws_region)
"
```

**Solutions**:

1. **Set missing variables**
   ```bash
   # Update docker-compose.yml or run command
   docker run -e SLACK_TOKENS_SECRET_ID=... -e AWS_REGION=... maptimize
   ```

2. **Verify variable format**
   ```bash
   # Ensure correct format
   export SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens
   echo $SLACK_TOKENS_SECRET_ID  # Should print: maptimize/slack-tokens
   ```

3. **Check for typos**
   - Variable names are case-sensitive
   - Verify exact spelling

### Invalid Configuration Values

**Symptoms**:
- Bot starts then crashes with config error
- "Invalid configuration" messages
- Unexpected behavior

**Debugging**:

```bash
# Validate configuration
docker exec maptimize-bot python -c "
from maptimize.config import Config
from pydantic import ValidationError
try:
    config = Config()
    print('Configuration valid')
except ValidationError as e:
    print('Validation errors:')
    print(e)
"

# Check config file
docker exec maptimize-bot cat /app/config/processes.yml
```

**Solutions**:

1. **Validate YAML files**
   ```bash
   # Check syntax
   python -c "import yaml; yaml.safe_load(open('config/processes.yml'))"
   ```

2. **Check required fields**
   - Consult configuration schema
   - Add missing required fields
   - Verify field types match schema

3. **Update configuration**
   ```bash
   # Edit config file
   nano config/processes.yml

   # Restart bot
   docker restart maptimize-bot
   ```

## Logging and Debugging

### Enable Debug Logging

```bash
# Set log level to DEBUG
docker run -e LOG_LEVEL=DEBUG maptimize:latest

# Or update running container's environment
docker exec maptimize-bot python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
"
```

### View Detailed Logs

```bash
# View all logs with timestamps
docker logs --timestamps maptimize-bot

# Follow logs in real-time
docker logs -f maptimize-bot

# View last N lines
docker logs --tail 100 maptimize-bot

# Filter logs
docker logs maptimize-bot | grep "ERROR"
docker logs maptimize-bot | grep "2024-11-19"
```

### Capture Logs for Analysis

```bash
# Save logs to file
docker logs maptimize-bot > maptimize-logs.txt 2>&1

# Compress for storage
gzip maptimize-logs.txt

# Upload for analysis
```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `socket.error: Connection refused` | Slack not reachable | Check network, firewall |
| `Access Denied` | AWS credentials invalid | Verify IAM role, region |
| `Secret not found` | Secrets Manager lookup failed | Check secret name, region |
| `TimeoutError` | Operation took too long | Check network, increase timeout |
| `ConnectionError: Jira API unavailable` | Jira service down | Check Jira status, credentials |
| `Token expired` | Slack/Jira token invalid | Regenerate token |

## Getting Help

### Collect Debug Information

When reporting issues, include:

```bash
# System information
docker --version
python --version
uname -a

# Container information
docker inspect maptimize-bot

# Recent logs (last 200 lines)
docker logs --tail 200 maptimize-bot > debug-logs.txt

# Environment variables
docker inspect maptimize-bot | grep -A 20 Env

# AWS information
aws sts get-caller-identity
aws ec2 describe-instances --instance-ids INSTANCE_ID

# Docker stats
docker stats --no-stream maptimize-bot
```

### Contact Information

- Email: team@campops.com
- Slack: #maptimize-support
- GitHub Issues: https://github.com/camp-ops-emea/maptimize/issues

### Additional Resources

- [README.md](../README.md) - Project overview and quick start
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment instructions
- [AWS_SETUP.md](AWS_SETUP.md) - AWS configuration
- [SLACK_APP_SETUP.md](SLACK_APP_SETUP.md) - Slack app setup

### Running Tests to Verify Installation

```bash
# Run all tests
docker-compose exec maptimize pytest -v

# Run specific test category
docker-compose exec maptimize pytest -m unit -v
docker-compose exec maptimize pytest -m integration -v

# Run with coverage
docker-compose exec maptimize pytest --cov=src/maptimize --cov-report=term
```
