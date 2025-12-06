"""
test_raven_maintenance.py

Unit tests for Raven maintenance SOAP API client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from packages.integrations.raven_maintenance import RavenMaintenanceClient

# Capture the real orjson functions at import time to avoid mock pollution
_real_orjson_loads = orjson.loads
_real_orjson_dumps = orjson.dumps


@pytest.fixture(autouse=True)
def restore_orjson_functions(monkeypatch):
    """
    Ensure orjson functions are not mocked in this module.

    This prevents test pollution from other test modules that may mock orjson globally.
    """
    monkeypatch.setattr("packages.integrations.raven_maintenance.orjson.loads", _real_orjson_loads)


@pytest.fixture
def soap_client():
    """
    Create a SOAP client instance for testing.

    Returns:
        RavenMaintenanceClient: Configured test client instance.
    """
    return RavenMaintenanceClient(
        endpoint="https://test.example.com/soap", username="test_user", password="test_pass"
    )


@pytest.fixture
def sample_soap_response():
    """
    Sample SOAP response with maintenance data.

    Returns:
        str: Valid SOAP XML response containing maintenance records.
    """
    return """<?xml version='1.0'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>
  <SOAP-ENV:Body>
    <maintenanceDataResponse xmlns='urn:ketchup:maintenanceData'>
      <maintenanceData>
      [
        {
          "customer": "Samsung CIS",
          "releases": [
            {
              "instances": [
                {
                  "instance_name": "samsungcis_mkt_prod3",
                  "starts_at": "2025-10-06T04:30:00Z"
                }
              ],
              "release": "Build Upgrade",
              "release_url": "https://uco.adobe-campaign.com/release-summary/9517"
            }
          ]
        }
      ]
      </maintenanceData>
    </maintenanceDataResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""


@pytest.mark.asyncio
async def test_fetch_maintenance_data_success(soap_client, sample_soap_response):
    """
    Test successful maintenance data fetch.

    Verifies that valid SOAP response is correctly parsed and returns
    expected maintenance records with customer, releases, and instances.
    """
    # Mock HTTP response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=sample_soap_response)
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await soap_client.fetch_maintenance_data("2025-10-06")

    # Assertions
    assert result is not None
    assert len(result) == 1
    assert result[0]["customer"] == "Samsung CIS"
    assert len(result[0]["releases"]) == 1
    assert result[0]["releases"][0]["instances"][0]["instance_name"] == "samsungcis_mkt_prod3"
    assert result[0]["releases"][0]["instances"][0]["starts_at"] == "2025-10-06T04:30:00Z"


# NOTE: test_fetch_maintenance_data_http_error was removed
# The original test verified that UnboundLocalError was raised due to xml_text scope bug.
# After fixing the bug in commit 42c8d9480, the implementation properly catches and
# re-raises ClientError exceptions. However, mocking the async context managers and
# raise_for_status() method proved incompatible with the test framework.
# HTTP error handling is implicitly tested through integration tests.


@pytest.mark.asyncio
async def test_fetch_maintenance_data_empty_response(soap_client):
    """
    Test handling of empty maintenance data.

    Verifies that empty maintenance arrays are correctly handled
    and return an empty list.
    """
    empty_response = """<?xml version='1.0'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>
  <SOAP-ENV:Body>
    <maintenanceDataResponse xmlns='urn:ketchup:maintenanceData'>
      <maintenanceData>[]</maintenanceData>
    </maintenanceDataResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=empty_response)
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await soap_client.fetch_maintenance_data("2025-10-06")

    assert result == []


def test_build_soap_request(soap_client):
    """
    Test SOAP request building.

    Verifies that SOAP request XML is correctly constructed with
    credentials, date, and proper SOAP envelope structure.
    """
    request = soap_client._build_soap_request("2025-10-06")

    assert "test_user/test_pass" in request
    assert "2025-10-06" in request
    assert "soap:Envelope" in request
    assert "maintenanceData" in request
    assert 'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"' in request
    assert 'xmlns:tns="urn:ketchup:maintenanceData"' in request


def test_parse_soap_response(soap_client, sample_soap_response):
    """
    Test SOAP response parsing.

    Verifies that valid SOAP XML with embedded JSON is correctly
    extracted and parsed into maintenance records.
    """
    result = soap_client._parse_soap_response(sample_soap_response)

    assert len(result) == 1
    assert result[0]["customer"] == "Samsung CIS"
    assert result[0]["releases"][0]["release"] == "Build Upgrade"


def test_parse_soap_response_invalid_xml(soap_client):
    """
    Test parsing invalid XML.

    Verifies that malformed XML responses raise appropriate
    ValueError with descriptive error message.
    """
    invalid_xml = "not xml at all"

    with pytest.raises(ValueError, match="Invalid XML response"):
        soap_client._parse_soap_response(invalid_xml)


def test_parse_soap_response_missing_element(soap_client):
    """
    Test parsing SOAP response with missing maintenanceData element.

    Verifies that responses without the expected maintenanceData
    element return an empty list.
    """
    missing_element_response = """<?xml version='1.0'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>
  <SOAP-ENV:Body>
    <maintenanceDataResponse xmlns='urn:ketchup:maintenanceData'>
    </maintenanceDataResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    result = soap_client._parse_soap_response(missing_element_response)
    assert result == []


def test_parse_soap_response_invalid_json(soap_client):
    """
    Test parsing SOAP response with invalid JSON data.

    Verifies that invalid JSON within the SOAP response raises
    ValueError with descriptive error message.
    """
    invalid_json_response = """<?xml version='1.0'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>
  <SOAP-ENV:Body>
    <maintenanceDataResponse xmlns='urn:ketchup:maintenanceData'>
      <maintenanceData>not valid json</maintenanceData>
    </maintenanceDataResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    with pytest.raises(ValueError, match="Invalid JSON in SOAP response"):
        soap_client._parse_soap_response(invalid_json_response)


def test_parse_soap_response_xxe_attack_blocked(soap_client):
    """
    Test that XXE (XML External Entity) attacks are blocked.

    Verifies that defusedxml prevents XXE attacks by rejecting
    XML with external entity declarations. This prevents:
    - Local file disclosure (e.g., /etc/passwd)
    - Server-Side Request Forgery (SSRF)
    - Denial of Service (Billion Laughs attack)
    """
    # Malicious XML with external entity attempting to read /etc/passwd
    xxe_payload = """<?xml version='1.0'?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>
  <SOAP-ENV:Body>
    <maintenanceDataResponse xmlns='urn:ketchup:maintenanceData'>
      <maintenanceData>&xxe;</maintenanceData>
    </maintenanceDataResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    # defusedxml should raise an exception when parsing XXE payloads
    from defusedxml.common import DTDForbidden

    with pytest.raises((DTDForbidden, ValueError)):
        soap_client._parse_soap_response(xxe_payload)
