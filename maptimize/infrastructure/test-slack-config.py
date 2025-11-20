#!/usr/bin/env python3
"""
Test Slack app configuration and connectivity.
Run this script to verify Slack tokens and app configuration.
"""

import json
import os
import sys

import boto3
import requests


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50 + "\n")


def get_secret():
    """Fetch secret from AWS Secrets Manager."""
    secret_id = os.getenv("SLACK_TOKENS_SECRET_ID", "maptimize/slack-tokens")
    region = os.getenv("AWS_REGION", "eu-west-1")
    
    print(f"Fetching secret: {secret_id}")
    print(f"Region: {region}")
    
    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        secret = json.loads(response["SecretString"])
        print("✓ Secret fetched successfully")
        return secret
    except Exception as e:
        print(f"✗ Failed to fetch secret: {e}")
        return None


def test_bot_token(token):
    """Test bot token validity."""
    print_section("Testing Bot Token")
    
    if not token:
        print("✗ Bot token not provided")
        return False
    
    if not token.startswith("xoxb-"):
        print(f"✗ Bot token should start with 'xoxb-', got: {token[:10]}...")
        return False
    
    print(f"Token format: {token[:10]}...")
    
    # Test auth
    response = requests.post(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"✗ HTTP error: {response.status_code}")
        return False
    
    data = response.json()
    
    if not data.get("ok"):
        print(f"✗ Auth failed: {data.get('error')}")
        return False
    
    print("✓ Bot token is valid")
    print(f"  Bot ID: {data.get('user_id')}")
    print(f"  Bot name: {data.get('user')}")
    print(f"  Team: {data.get('team')}")
    print(f"  Team ID: {data.get('team_id')}")
    
    return True


def test_app_token(token):
    """Test app token validity."""
    print_section("Testing App Token")
    
    if not token:
        print("✗ App token not provided")
        return False
    
    if not token.startswith("xapp-"):
        print(f"✗ App token should start with 'xapp-', got: {token[:10]}...")
        return False
    
    print(f"Token format: {token[:10]}...")
    print("✓ App token format looks correct")
    print("  (Cannot test app token via REST API, requires Socket Mode connection)")
    
    return True


def check_signing_secret(secret):
    """Check signing secret."""
    print_section("Checking Signing Secret")
    
    if not secret:
        print("✗ Signing secret not provided")
        print("\nGet it from:")
        print("https://api.slack.com/apps -> Your App -> Basic Information -> Signing Secret")
        return False
    
    if len(secret) < 32:
        print(f"✗ Signing secret seems too short (length: {len(secret)})")
        return False
    
    print(f"✓ Signing secret present (length: {len(secret)})")
    return True


def check_socket_mode_scopes(bot_token):
    """Check if bot has required scopes."""
    print_section("Checking Bot Scopes")
    
    response = requests.post(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {bot_token}"}
    )
    
    if response.status_code != 200 or not response.json().get("ok"):
        print("✗ Cannot check scopes (auth test failed)")
        return False
    
    # Get bot info to check scopes
    response = requests.post(
        "https://slack.com/api/apps.permissions.info",
        headers={"Authorization": f"Bearer {bot_token}"}
    )
    
    if response.status_code == 200 and response.json().get("ok"):
        data = response.json()
        scopes = data.get("info", {}).get("bot", {}).get("scopes", [])
        print(f"Bot scopes: {', '.join(scopes)}")
        
        required_scopes = ["app_mentions:read", "chat:write", "commands"]
        missing = [s for s in required_scopes if s not in scopes]
        
        if missing:
            print(f"✗ Missing required scopes: {', '.join(missing)}")
            return False
        
        print("✓ All required scopes present")
        return True
    else:
        print("⚠ Cannot check scopes (API call failed)")
        print("  This might be normal if the bot doesn't have apps.permissions.info scope")
        return None


def check_slack_app_config():
    """Check Slack app configuration."""
    print_section("Slack App Configuration Checklist")
    
    print("Please verify these settings at: https://api.slack.com/apps")
    print("\n1. Socket Mode:")
    print("   - Navigate to: Socket Mode")
    print("   - Toggle should be: ON")
    print("   - Status should show: 'Socket Mode is enabled'")
    
    print("\n2. Event Subscriptions:")
    print("   - Navigate to: Event Subscriptions")
    print("   - Toggle should be: ON")
    print("   - Subscribe to bot events:")
    print("     • app_mention")
    print("     • message.channels")
    print("     • message.groups")
    print("     • message.im")
    
    print("\n3. Slash Commands:")
    print("   - Navigate to: Slash Commands")
    print("   - Command: /maptimize")
    print("   - Request URL: (leave blank for Socket Mode)")
    
    print("\n4. OAuth & Permissions:")
    print("   - Bot Token Scopes:")
    print("     • app_mentions:read")
    print("     • chat:write")
    print("     • commands")
    print("     • users:read")
    print("     • channels:read")
    
    print("\n5. App-Level Tokens:")
    print("   - Navigate to: Basic Information -> App-Level Tokens")
    print("   - Token name: socket-mode-token")
    print("   - Scopes:")
    print("     • connections:write")
    print("     • authorizations:read")


def main():
    """Run all tests."""
    print("=" * 50)
    print("Maptimize Slack Configuration Test")
    print("=" * 50)
    
    # Get secret
    print_section("Fetching Secret from AWS Secrets Manager")
    secret = get_secret()
    
    if not secret:
        print("\n✗ Cannot proceed without secret")
        sys.exit(1)
    
    # Check secret structure
    print_section("Checking Secret Structure")
    required_keys = ["bot_token", "app_token", "signing_secret"]
    
    for key in required_keys:
        if key in secret and secret[key]:
            print(f"✓ {key}: present")
        else:
            print(f"✗ {key}: MISSING")
    
    missing = [k for k in required_keys if k not in secret or not secret[k]]
    if missing:
        print(f"\n✗ Missing required keys: {', '.join(missing)}")
        print("\nRun the fix-secret-structure.sh script to fix this.")
        sys.exit(1)
    
    # Test tokens
    bot_ok = test_bot_token(secret.get("bot_token"))
    app_ok = test_app_token(secret.get("app_token"))
    signing_ok = check_signing_secret(secret.get("signing_secret"))
    
    if bot_ok:
        check_socket_mode_scopes(secret.get("bot_token"))
    
    # Show Slack app config checklist
    check_slack_app_config()
    
    # Summary
    print_section("Summary")
    
    all_ok = bot_ok and app_ok and signing_ok
    
    if all_ok:
        print("✓ All token tests passed!")
        print("\nIf the bot still doesn't work, check:")
        print("1. Socket Mode is enabled in Slack app")
        print("2. Events are properly subscribed")
        print("3. Docker container is running: docker ps")
        print("4. Container logs: docker logs -f maptimize-bot")
    else:
        print("✗ Some tests failed. Fix the issues above.")
        print("\nCommon fixes:")
        print("1. Update secret structure: ./fix-secret-structure.sh")
        print("2. Get signing secret from Slack app settings")
        print("3. Regenerate tokens if they're invalid")
    
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
