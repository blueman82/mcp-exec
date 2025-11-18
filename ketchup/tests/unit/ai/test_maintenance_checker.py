"""
test_maintenance_checker.py

Unit tests for maintenance checker service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from packages.ai.maintenance_checker import MaintenanceChecker
from packages.db.dynamodb_store import DynamoDBStore


@pytest.fixture
def mock_db_store():
    """Create a mock DynamoDB store."""
    store = MagicMock(spec=DynamoDBStore)
    store.get_maintenance_cache = AsyncMock()
    return store


@pytest.fixture
def maintenance_checker(mock_db_store):
    """Create a maintenance checker instance."""
    return MaintenanceChecker(dynamodb_store=mock_db_store)


@pytest.fixture
def sample_maintenance_data():
    """Sample maintenance records."""
    return [
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
        },
        {
            "customer": "PFA PENSION",
            "releases": [
                {
                    "instances": [
                        {
                            "instance_name": "pfa_mkt_stage4",
                            "starts_at": "2025-10-06T02:30:00Z"
                        }
                    ],
                    "release": "Build Upgrade",
                    "release_url": "https://uco.adobe-campaign.com/release-summary/9518"
                }
            ]
        }
    ]


def test_normalize_instance_name_from_url():
    """Test instance name normalization from URL."""
    result = MaintenanceChecker.normalize_instance_name(
        "https://samsungcis-mkt-prod3.campaign.adobe.com"
    )
    assert result == "samsungcis_mkt_prod3"


def test_normalize_instance_name_with_hyphens():
    """Test instance name normalization with hyphens."""
    result = MaintenanceChecker.normalize_instance_name("totalenergies-mkt-stage7")
    assert result == "totalenergies_mkt_stage7"


def test_normalize_instance_name_with_underscores():
    """Test instance name already has underscores."""
    result = MaintenanceChecker.normalize_instance_name("pfa_mkt_prod1")
    assert result == "pfa_mkt_prod1"


def test_denormalize_instance_url():
    """Test converting normalized name back to URL."""
    result = MaintenanceChecker.denormalize_instance_url("samsungcis_mkt_prod3")
    assert result == "https://samsungcis-mkt-prod3.campaign.adobe.com"


@pytest.mark.asyncio
async def test_check_maintenance_found(maintenance_checker, mock_db_store, sample_maintenance_data):
    """Test finding maintenance for an instance."""
    mock_db_store.get_maintenance_cache.return_value = sample_maintenance_data

    result = await maintenance_checker.check_maintenance(
        "https://samsungcis-mkt-prod3.campaign.adobe.com",
        date="2025-10-06"
    )

    assert result is not None
    assert result["customer_name"] == "Samsung CIS"
    assert result["instance_name"] == "samsungcis_mkt_prod3"
    assert result["starts_at"] == "2025-10-06T04:30:00Z"


@pytest.mark.asyncio
async def test_check_maintenance_not_found(maintenance_checker, mock_db_store, sample_maintenance_data):
    """Test when instance is not in maintenance."""
    mock_db_store.get_maintenance_cache.return_value = sample_maintenance_data

    result = await maintenance_checker.check_maintenance(
        "https://unknown-instance.campaign.adobe.com",
        date="2025-10-06"
    )

    assert result is None


@pytest.mark.asyncio
async def test_check_maintenance_no_cache(maintenance_checker, mock_db_store):
    """Test when no maintenance cache exists."""
    mock_db_store.get_maintenance_cache.return_value = None

    result = await maintenance_checker.check_maintenance(
        "https://samsungcis-mkt-prod3.campaign.adobe.com",
        date="2025-10-06"
    )

    assert result is None


@pytest.mark.asyncio
async def test_check_maintenance_empty_cache(maintenance_checker, mock_db_store):
    """Test when maintenance cache is empty."""
    mock_db_store.get_maintenance_cache.return_value = []

    result = await maintenance_checker.check_maintenance(
        "https://samsungcis-mkt-prod3.campaign.adobe.com",
        date="2025-10-06"
    )

    assert result is None


def test_format_maintenance_start_time():
    """Test timestamp formatting."""
    result = MaintenanceChecker.format_maintenance_start_time("2025-10-06T04:30:00Z")
    assert result == "06-10-2025 04:30:00"


def test_format_maintenance_start_time_invalid():
    """Test handling invalid timestamps."""
    result = MaintenanceChecker.format_maintenance_start_time("invalid")
    assert result == "invalid"  # Should return original on error


def test_find_instance_match_case_insensitive(maintenance_checker, sample_maintenance_data):
    """Test case-insensitive matching."""
    result = maintenance_checker._find_instance_match(
        "SAMSUNGCIS_MKT_PROD3",  # Uppercase
        sample_maintenance_data
    )

    assert result is not None
    assert result["customer_name"] == "Samsung CIS"
