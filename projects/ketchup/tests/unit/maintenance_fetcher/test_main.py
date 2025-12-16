"""Unit tests for maintenance fetcher main module."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_fetch_and_store_success():
    """Test successful maintenance data fetch and store."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import fetch_and_store_maintenance_data

    # Mock SOAP client
    mock_soap = AsyncMock()
    mock_soap.fetch_maintenance_data.return_value = [
        {"id": "1", "status": "active"},
        {"id": "2", "status": "scheduled"},
    ]

    # Mock DB store
    mock_db = AsyncMock()
    mock_db.store_maintenance_cache.return_value = True

    # Mock container with aget method
    mock_container = AsyncMock()
    async def aget_side_effect(protocol):
        protocol_name = str(protocol)
        if "Raven" in protocol_name:
            return mock_soap
        if "DynamoDB" in protocol_name:
            return mock_db
        return AsyncMock()
    mock_container.aget = aget_side_effect

    with (
        patch("os.getenv", return_value="true"),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.datetime") as mock_datetime,
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.get_unified_container", return_value=mock_container),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.cleanup_unified_container", new_callable=AsyncMock),
    ):

        mock_datetime.now.return_value.strftime.return_value = "2025-10-06"

        # Execute
        result = await fetch_and_store_maintenance_data()

        # Assert
        assert result["status"] == "success"
        assert result["records"] == 2
        assert result["date"] == "2025-10-06"


@pytest.mark.asyncio
async def test_fetch_and_store_soap_failure():
    """Test when SOAP API returns None."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import fetch_and_store_maintenance_data

    # Mock SOAP client to return None (failure)
    mock_soap = AsyncMock()
    mock_soap.fetch_maintenance_data.return_value = None

    # Mock container with aget method
    mock_container = AsyncMock()
    async def aget_side_effect(protocol):
        protocol_name = str(protocol)
        if "Raven" in protocol_name:
            return mock_soap
        return AsyncMock()
    mock_container.aget = aget_side_effect

    with (
        patch("os.getenv", return_value="true"),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.datetime") as mock_datetime,
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.get_unified_container", return_value=mock_container),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.cleanup_unified_container", new_callable=AsyncMock),
    ):

        mock_datetime.now.return_value.strftime.return_value = "2025-10-06"

        # Execute
        result = await fetch_and_store_maintenance_data()

        # Assert
        assert result["status"] == "error"
        assert result["message"] == "Fetch failed"


@pytest.mark.asyncio
async def test_fetch_and_store_db_failure():
    """Test when DB storage returns False."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import fetch_and_store_maintenance_data

    # Mock SOAP client
    mock_soap = AsyncMock()
    mock_soap.fetch_maintenance_data.return_value = [{"id": "1"}]

    # Mock DB store to return False (failure)
    mock_db = AsyncMock()
    mock_db.store_maintenance_cache.return_value = False

    # Mock container with aget method
    mock_container = AsyncMock()
    async def aget_side_effect(protocol):
        protocol_name = str(protocol)
        if "Raven" in protocol_name:
            return mock_soap
        if "DynamoDB" in protocol_name:
            return mock_db
        return AsyncMock()
    mock_container.aget = aget_side_effect

    with (
        patch("os.getenv", return_value="true"),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.datetime") as mock_datetime,
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.get_unified_container", return_value=mock_container),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.cleanup_unified_container", new_callable=AsyncMock),
    ):

        mock_datetime.now.return_value.strftime.return_value = "2025-10-06"

        # Execute
        result = await fetch_and_store_maintenance_data()

        # Assert
        assert result["status"] == "error"
        assert result["message"] == "Store failed"


@pytest.mark.asyncio
async def test_feature_flag_disabled():
    """Test behavior when feature flag is disabled."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import fetch_and_store_maintenance_data

    with (
        patch("os.getenv", return_value="false"),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.cleanup_unified_container", new_callable=AsyncMock),
    ):
        # Execute
        result = await fetch_and_store_maintenance_data()

        # Assert
        assert result["status"] == "disabled"


@pytest.mark.asyncio
async def test_fetch_and_store_exception_handling():
    """Test exception handling in fetch_and_store."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import fetch_and_store_maintenance_data

    with (
        patch(
            "ketchup_unified_scheduler.services.maintenance.fetcher.get_unified_container",
            side_effect=Exception("DI container failed"),
        ),
        patch("os.getenv", return_value="true"),
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.cleanup_unified_container", new_callable=AsyncMock),
    ):
        # Execute
        result = await fetch_and_store_maintenance_data()

        # Assert
        assert result["status"] == "error"
        assert "DI container failed" in result["message"]


@pytest.mark.asyncio
async def test_cleanup_exception_handling():
    """Test that cleanup exceptions are handled gracefully."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import fetch_and_store_maintenance_data

    with (
        patch(
            "ketchup_unified_scheduler.services.maintenance.fetcher.cleanup_unified_container",
            side_effect=Exception("Cleanup failed"),
        ),
        patch("os.getenv", return_value="false"),
    ):
        # Execute
        result = await fetch_and_store_maintenance_data()

        # Assert - should still return result despite cleanup failure
        assert result["status"] == "disabled"


def test_main_entry_point_success():
    """Test main() returns exit code 0 on success."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import main

    with (
        patch(
            "ketchup_unified_scheduler.services.maintenance.fetcher.asyncio.run",
            return_value={"status": "success", "records": 5},
        ),
        patch("sys.exit") as mock_exit,
    ):
        # Execute
        main()

        # Assert
        mock_exit.assert_called_once_with(0)


def test_main_entry_point_failure():
    """Test main() returns exit code 1 on failure."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import main

    with (
        patch(
            "ketchup_unified_scheduler.services.maintenance.fetcher.asyncio.run",
            return_value={"status": "error", "message": "Test error"},
        ),
        patch("sys.exit") as mock_exit,
    ):
        # Execute
        main()

        # Assert
        mock_exit.assert_called_once_with(1)


def test_main_entry_point_exception():
    """Test main() returns exit code 1 on exception."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import main

    with (
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.asyncio.run", side_effect=Exception("Fatal error")),
        patch("sys.exit") as mock_exit,
    ):
        # Execute
        main()

        # Assert
        mock_exit.assert_called_once_with(1)


def test_main_entry_point_disabled():
    """Test main() returns exit code 1 when disabled."""
    from ketchup_unified_scheduler.services.maintenance.fetcher import main

    with (
        patch("ketchup_unified_scheduler.services.maintenance.fetcher.asyncio.run", return_value={"status": "disabled"}),
        patch("sys.exit") as mock_exit,
    ):
        # Execute
        main()

        # Assert
        mock_exit.assert_called_once_with(1)
