"""
raven_maintenance.py

SOAP API client for fetching daily maintenance data from Raven.
"""

from typing import Dict, List, Optional

import aiohttp
import orjson
from defusedxml import ElementTree as ET

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class RavenMaintenanceClient:
    """
    Client for fetching maintenance data from Raven SOAP API.

    The API provides maintenance schedules for Adobe Campaign instances.
    Data is fetched daily and cached in DynamoDB with 24-hour TTL.
    """

    def __init__(self, endpoint: str, username: str, password: str):
        """
        Initialize the SOAP client.

        Args:
            endpoint: SOAP API endpoint URL
            username: Authentication username
            password: Authentication password
        """
        self.endpoint = endpoint
        self.username = username
        self.password = password

    async def fetch_maintenance_data(self, date: str) -> Optional[List[Dict]]:
        """
        Fetch maintenance data for a specific date.

        Args:
            date: Date in YYYY-MM-DD format (e.g., "2025-10-06")

        Returns:
            List of maintenance records, or None if fetch fails.
            Each record contains: {customer, releases: [{instances: [{instance_name, starts_at}]}]}

        Raises:
            aiohttp.ClientError: If HTTP request fails
            ValueError: If response parsing fails
        """
        logger.info(f"Fetching maintenance data for date: {date}")

        # Build SOAP request
        soap_body = self._build_soap_request(date)

        headers = {
            "Content-Type": "application/xml",
            "SOAPAction": "ketchup:maintenanceData#maintenanceData",
        }

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.endpoint,
                    data=soap_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response,
            ):
                response.raise_for_status()
                xml_text = await response.text()

                # Parse response
                maintenance_data = self._parse_soap_response(xml_text)
                logger.info(f"Successfully fetched {len(maintenance_data)} maintenance records")
                return maintenance_data

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching maintenance data: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching maintenance data: {e}", exc_info=True)
            raise

    def _build_soap_request(self, date: str) -> str:
        """Build SOAP XML request body."""
        credentials = f"{self.username}/{self.password}"

        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <tns:maintenanceData xmlns:tns="urn:ketchup:maintenanceData">
      <tns:sessiontoken>{credentials}</tns:sessiontoken>
      <tns:maintenanceDate>{date}</tns:maintenanceDate>
    </tns:maintenanceData>
  </soap:Body>
</soap:Envelope>"""

    def _parse_soap_response(self, xml_text: str) -> List[Dict]:
        """
        Parse SOAP XML response to extract JSON maintenance data.

        The response contains JSON embedded within XML tags.

        Security: Uses defusedxml to prevent XXE attacks by disabling:
        - External entity resolution
        - DTD processing
        - Entity expansion attacks
        """
        try:
            # Parse XML securely using defusedxml (prevents XXE vulnerabilities)
            root = ET.fromstring(xml_text)

            # Find the maintenanceData element (contains JSON)
            # Namespace handling for SOAP envelope
            namespaces = {
                "soap": "http://schemas.xmlsoap.org/soap/envelope/",
                "ns": "urn:ketchup:maintenanceData",
            }

            maintenance_elem = root.find(".//ns:maintenanceData", namespaces)
            if maintenance_elem is None:
                logger.warning("No maintenanceData element found in SOAP response")
                return []

            # Extract JSON text from the element
            json_text = maintenance_elem.text
            if not json_text:
                logger.warning("Empty maintenanceData in SOAP response")
                return []

            # Parse JSON
            maintenance_records = orjson.loads(json_text)
            return maintenance_records

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            raise ValueError(f"Invalid XML response: {e}")
        except orjson.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            raise ValueError(f"Invalid JSON in SOAP response: {e}")
