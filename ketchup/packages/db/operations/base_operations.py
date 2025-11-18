"""
base_operations.py

This module contains the base class for DynamoDB operations.
"""

from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

logger = setup_logger(__name__)


class BaseOperations:
    """Base class for DynamoDB operations with shared functionality."""

    def __init__(self, client: DynamoDBAsyncClient, table_name: str):
        """
        Initialize the base operations.

        Args:
            client: The DynamoDB async client
            table_name: The DynamoDB table name
        """
        self.client = client
        self.table_name = table_name

    def _normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB attribute format to a normal Python dictionary.

        Args:
            item: DynamoDB formatted item

        Returns:
            Normalized dictionary
        """
        result = {}
        for key, value in item.items():
            # Handle different DynamoDB types
            if "S" in value:
                result[key] = value["S"]
            elif "N" in value:
                num_str = value["N"]
                # Treat values containing a decimal point or scientific notation as float
                if "." in num_str or "e" in num_str or "E" in num_str:
                    result[key] = float(num_str)
                else:
                    result[key] = int(num_str)
            elif "BOOL" in value:
                result[key] = value["BOOL"]
            elif "L" in value:
                # Recursively normalize each element, but flatten if it's a single-value dict
                norm_list = []
                for v in value["L"]:
                    if "S" in v:
                        norm_list.append(v["S"])
                    elif "N" in v:
                        num_str = v["N"]
                        if "." in num_str or "e" in num_str or "E" in num_str:
                            norm_list.append(float(num_str))
                        else:
                            norm_list.append(int(num_str))
                    elif "BOOL" in v:
                        norm_list.append(v["BOOL"])
                    elif "M" in v:
                        norm_list.append(self._normalize_item(v["M"]))
                    else:
                        norm_list.append(self._normalize_item(v))
                result[key] = norm_list
            elif "M" in value:
                result[key] = self._normalize_item(value["M"])
        return result

    async def cleanup(self) -> None:
        """
        Clean up any resources used by this operations instance.

        Base implementation doesn't need to clean up anything directly,
        as the DynamoDB client is managed by the parent store.
        Subclasses should override this if they maintain their own resources.
        """
        logger.info("Cleaning up %s instance", self.__class__.__name__)
        # No specific resources to clean up in the base class
        # The DynamoDB client is cleaned up by the parent DynamoDBStore
