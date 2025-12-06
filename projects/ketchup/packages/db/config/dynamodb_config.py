"""
DynamoDB configuration module.

This module provides configuration for DynamoDB operations.
"""

from packages.core.constants import AWS_REGION, DYNAMODB_TABLE_NAME


class DynamoDBConfig:
    """Configuration for DynamoDB operations."""

    def __init__(self, table_name: str = DYNAMODB_TABLE_NAME, region: str = AWS_REGION) -> None:
        """Initialize the configuration.

        Args:
            table_name: The DynamoDB table name
            region: The AWS region
        """
        self.table_name = table_name
        self.region = region

    def get_table_name(self) -> str:
        """Get the table name.

        Returns:
            The DynamoDB table name
        """
        return self.table_name

    def get_region(self) -> str:
        """Get the AWS region.

        Returns:
            The AWS region
        """
        return self.region
