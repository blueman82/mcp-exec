"""
maintenance_checker.py

Service for checking if instances are under scheduled maintenance.
"""

from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore

logger = setup_logger(__name__)


class MaintenanceChecker:
    """
    Checks if instances are under scheduled maintenance.

    Handles instance name normalization and matching against
    cached maintenance data.
    """

    def __init__(self, dynamodb_store: DynamoDBStore):
        """
        Initialize the maintenance checker.

        Args:
            dynamodb_store: DynamoDB store for cache access
        """
        self.db_store = dynamodb_store

    @staticmethod
    def normalize_instance_name(url_or_name: str) -> str:
        """
        Normalize instance name for matching.

        Handles:
        - URL extraction: https://samsungcis-mkt-prod3.campaign.adobe.com → samsungcis_mkt_prod3
        - Hyphen to underscore conversion: samsungcis-mkt-prod3 → samsungcis_mkt_prod3

        Args:
            url_or_name: Instance URL or name

        Returns:
            Normalized instance name with underscores

        Examples:
            >>> MaintenanceChecker.normalize_instance_name("https://samsungcis-mkt-prod3.campaign.adobe.com")
            'samsungcis_mkt_prod3'
            >>> MaintenanceChecker.normalize_instance_name("totalenergies-mkt-stage7")
            'totalenergies_mkt_stage7'
        """
        instance_name = url_or_name

        # Extract hostname if URL
        if url_or_name.startswith("http"):
            parsed = urlparse(url_or_name)
            hostname = parsed.hostname
            if hostname:
                # Remove .campaign.adobe.com suffix
                instance_name = hostname.replace(".campaign.adobe.com", "")

        # Replace hyphens with underscores for SOAP data matching
        return instance_name.replace("-", "_")

    @staticmethod
    def denormalize_instance_url(instance_name: str) -> str:
        """
        Convert normalized instance name back to URL format.

        Args:
            instance_name: Normalized instance name (with underscores)

        Returns:
            Full instance URL with hyphens

        Examples:
            >>> MaintenanceChecker.denormalize_instance_url("samsungcis_mkt_prod3")
            'https://samsungcis-mkt-prod3.campaign.adobe.com'
        """
        # Replace underscores with hyphens
        instance_with_hyphens = instance_name.replace("_", "-")
        return f"https://{instance_with_hyphens}.campaign.adobe.com"

    async def check_maintenance(
        self, instance_url: str, date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Check if an instance is under scheduled maintenance.

        Args:
            instance_url: Instance URL from JIRA ticket
            date: Date to check (YYYY-MM-DD). Defaults to today.

        Returns:
            Maintenance info dict if match found, None otherwise.
            Dict contains: {customer_name, instance_name, starts_at}

        Example:
            >>> checker = MaintenanceChecker(db_store)
            >>> result = await checker.check_maintenance("https://samsungcis-mkt-prod3.campaign.adobe.com")
            >>> result
            {
                'customer_name': 'Samsung CIS',
                'instance_name': 'samsungcis_mkt_prod3',
                'starts_at': '2025-10-06T04:30:00Z'
            }
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # Normalize instance name
        normalized_name = self.normalize_instance_name(instance_url)
        logger.info(f"Checking maintenance for instance: {normalized_name} on {date}")

        # Get maintenance cache
        maintenance_records = await self.db_store.get_maintenance_cache(date)
        if not maintenance_records:
            logger.info(f"No maintenance cache found for date: {date}")
            return None

        # Search for matching instance
        match = self._find_instance_match(normalized_name, maintenance_records)

        if match:
            logger.info(f"Maintenance found for {normalized_name}: {match}")
        else:
            logger.info(f"No maintenance found for {normalized_name}")

        return match

    def _find_instance_match(
        self, normalized_name: str, maintenance_records: List[Dict]
    ) -> Optional[Dict]:
        """
        Find exact match for instance name in maintenance records.

        Args:
            normalized_name: Normalized instance name (with underscores)
            maintenance_records: List of maintenance records from SOAP API

        Returns:
            Dict with maintenance info if found, None otherwise
        """
        for record in maintenance_records:
            customer = record.get("customer", "")

            for release in record.get("releases", []):
                for instance in release.get("instances", []):
                    instance_name = instance.get("instance_name", "")

                    # Exact match only (case-insensitive)
                    if instance_name.lower() == normalized_name.lower():
                        return {
                            "customer_name": customer,
                            "instance_name": instance_name,
                            "starts_at": instance.get("starts_at", ""),
                            "release": release.get("release", ""),
                            "release_url": release.get("release_url", "")
                        }

        return None

    @staticmethod
    def format_maintenance_start_time(iso_timestamp: str) -> str:
        """
        Format ISO timestamp to DD-MM-YYYY HH:MM:SS.

        Args:
            iso_timestamp: ISO format timestamp (e.g., "2025-10-06T04:30:00Z")

        Returns:
            Formatted timestamp (e.g., "06-10-2025 04:30:00")

        Examples:
            >>> MaintenanceChecker.format_maintenance_start_time("2025-10-06T04:30:00Z")
            '06-10-2025 04:30:00'
        """
        try:
            # Parse ISO timestamp
            dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
            # Format to DD-MM-YYYY HH:MM:SS
            return dt.strftime("%d-%m-%Y %H:%M:%S")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to format timestamp {iso_timestamp}: {e}")
            return iso_timestamp  # Return original if parsing fails
