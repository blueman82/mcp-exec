#!/usr/bin/env python3
"""
PAT expiry monitor for JIRA authentication tokens.

Monitors the expiry date of JIRA Personal Access Tokens (PATs) and
determines if rotation is needed based on a 75-day threshold.

Reads JIRA_PAT_EXPIRY from AWS Secrets Manager and calculates
days remaining until expiry.
"""

from datetime import datetime
from typing import Optional

import boto3
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Threshold for triggering PAT rotation (days)
ROTATION_THRESHOLD_DAYS = 75


class PatMonitor:
    """Monitor JIRA PAT expiry and determine rotation needs."""

    def __init__(self):
        """Initialize the PAT monitor."""
        self.secrets_client = boto3.client("secretsmanager")
        self.secret_name = "jira-pat-secret"

    def _get_pat_expiry_from_secrets(self) -> Optional[str]:
        """
        Retrieve JIRA_PAT_EXPIRY from AWS Secrets Manager.

        Returns:
            ISO 8601 formatted expiry date string, or None if not found.

        Raises:
            Exception: If there's an error retrieving from Secrets Manager.
        """
        try:
            response = self.secrets_client.get_secret_value(
                SecretId=self.secret_name
            )

            secret_string = response.get("SecretString")
            if not secret_string:
                logger.warning("Secret does not contain SecretString")
                return None

            # Parse JSON if the secret is in JSON format
            import json
            try:
                secret_dict = json.loads(secret_string)
                expiry = secret_dict.get("JIRA_PAT_EXPIRY")
                return expiry
            except json.JSONDecodeError:
                # If not JSON, treat as raw string
                return secret_string

        except Exception as e:
            logger.error(f"Failed to retrieve PAT expiry from Secrets Manager: {e}")
            return None

    def _calculate_days_remaining(self, expiry_date_iso: str) -> int:
        """
        Calculate days remaining until PAT expiry.

        Args:
            expiry_date_iso: ISO 8601 formatted expiry date string.

        Returns:
            Number of days remaining until expiry (negative if already expired).

        Raises:
            ValueError: If date string cannot be parsed.
        """
        try:
            # Parse ISO 8601 date string
            # Handle both with and without timezone info
            expiry_date_str = expiry_date_iso.rstrip("Z")

            # Try parsing with timezone first
            try:
                expiry_date = datetime.fromisoformat(expiry_date_str)
            except ValueError:
                # Fallback for other ISO formats
                expiry_date = datetime.fromisoformat(expiry_date_iso)

            # Calculate days remaining
            now = datetime.utcnow()
            time_remaining = expiry_date - now
            days_remaining = time_remaining.days

            return days_remaining

        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to parse expiry date '{expiry_date_iso}': {e}")
            raise ValueError(f"Invalid date format: {expiry_date_iso}") from e

    def get_days_remaining(self) -> Optional[int]:
        """
        Get the number of days remaining until PAT expiry.

        Returns:
            Number of days remaining, or None if expiry date cannot be retrieved.
        """
        expiry_iso = self._get_pat_expiry_from_secrets()

        if expiry_iso is None:
            logger.warning("JIRA_PAT_EXPIRY not found in Secrets Manager")
            return None

        try:
            days = self._calculate_days_remaining(expiry_iso)
            logger.info(f"PAT expires in {days} days")
            return days
        except ValueError as e:
            logger.error(f"Failed to calculate days remaining: {e}")
            return None

    def should_rotate(self) -> bool:
        """
        Determine if PAT rotation is needed.

        Returns rotation needed based on:
        - True if expiry is within 75 days or already expired
        - True if expiry date cannot be retrieved (safety measure)
        - False if expiry is more than 75 days away

        Returns:
            True if rotation is needed, False otherwise.
        """
        expiry_iso = self._get_pat_expiry_from_secrets()

        if expiry_iso is None:
            logger.warning(
                "JIRA_PAT_EXPIRY not found - triggering rotation for safety"
            )
            return True

        try:
            days_remaining = self._calculate_days_remaining(expiry_iso)

            # Rotation needed if <= 75 days remaining
            needs_rotation = days_remaining <= ROTATION_THRESHOLD_DAYS

            if needs_rotation:
                logger.warning(
                    f"PAT rotation needed: {days_remaining} days remaining "
                    f"(threshold: {ROTATION_THRESHOLD_DAYS} days)"
                )
            else:
                logger.info(
                    f"PAT rotation not needed: {days_remaining} days remaining"
                )

            return needs_rotation

        except ValueError as e:
            logger.error(f"Failed to determine rotation need: {e}")
            # Return True (trigger rotation) on error for safety
            return True
