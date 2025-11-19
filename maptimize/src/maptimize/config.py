"""Configuration module for Maptimize.

Fetches Slack tokens from AWS Secrets Manager at runtime and loads
process configuration from JSON files.

Supports both EC2 (IAM role) and local development (AWS CLI profiles).
"""

import json
import os
from pathlib import Path
from typing import Any, Tuple

import boto3  # type: ignore

__all__ = [
    "get_slack_tokens",
    "load_processes",
]


def get_slack_tokens() -> Tuple[str, str]:
    """Fetch Slack bot and app tokens from AWS Secrets Manager.

    Retrieves Slack bot token and app token from AWS Secrets Manager.
    Supports both EC2 (IAM role) and local development (AWS CLI profiles).

    Environment variables:
        AWS_PROFILE: AWS CLI profile name for local development
        AWS_REGION: AWS region (default: eu-west-1)
        SLACK_TOKENS_SECRET_ID: Secrets Manager secret ID (default: maptimize/slack-tokens)

    Returns:
        Tuple of (bot_token, app_token)

    Raises:
        RuntimeError: If token retrieval fails or required keys are missing

    Example:
        >>> bot_token, app_token = get_slack_tokens()
    """
    region = os.getenv("AWS_REGION", "eu-west-1")
    secret_id = os.getenv("SLACK_TOKENS_SECRET_ID", "maptimize/slack-tokens")
    profile = os.getenv("AWS_PROFILE", None)

    try:
        # Create session with optional profile for local development
        if profile:
            session = boto3.Session(profile_name=profile)
        else:
            # EC2 instances use IAM role automatically
            session = boto3.Session()

        # Get Secrets Manager client
        client = session.client("secretsmanager", region_name=region)

        # Fetch secret from Secrets Manager
        response = client.get_secret_value(SecretId=secret_id)

        # Parse JSON secret
        secret = json.loads(response["SecretString"])

        # Extract tokens
        bot_token = secret["bot_token"]
        app_token = secret["app_token"]

        return bot_token, app_token

    except KeyError as e:
        raise RuntimeError(
            f"Failed to fetch Slack tokens: Missing key {e} in secret"
        )
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to fetch Slack tokens: Invalid JSON in secret - {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Slack tokens: {e}")


def load_processes() -> dict[Any, Any]:
    """Load process configuration from JSON file.

    Loads the process configuration from a hardcoded JSON file that defines
    the structure and metadata for various business processes.

    Returns:
        Dictionary containing process configuration

    Raises:
        RuntimeError: If configuration file cannot be loaded

    Example:
        >>> processes = load_processes()
        >>> print(processes["Service Review Process"])
    """
    try:
        # Construct path to processes.json (relative to this module)
        config_dir = Path(__file__).parent.parent.parent / "config"
        processes_file = config_dir / "processes.json"

        # Load and parse JSON file
        with open(processes_file, "r") as f:
            processes: dict[Any, Any] = json.load(f)

        return processes

    except FileNotFoundError as e:
        raise RuntimeError(
            f"Failed to load process configuration: File not found at {processes_file}"
        )
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Failed to load process configuration: Invalid JSON in {processes_file} - {e}"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to load process configuration: {e}")
