"""Unit tests for monthly aggregate operations in DynamoDB store."""

import pytest
from unittest.mock import Mock, AsyncMock

from packages.db.dynamodb_store import DynamoDBStore
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient


@pytest.fixture
def mock_client():
    """Create a mock DynamoDB async client."""
    client = Mock(spec=DynamoDBAsyncClient)
    client.update_item = AsyncMock()
    client.get_item = AsyncMock()
    client.put_item = AsyncMock()
    return client


@pytest.fixture
def db_store(mock_client):
    """Create DynamoDB store with mock client."""
    return DynamoDBStore(client=mock_client, table_name="test_table")


class TestIncrementMonthlyCounter:
    """Test increment_monthly_counter method."""
    
    @pytest.mark.asyncio
    async def test_increment_auto_status_posts(self, db_store, mock_client):
        """Test incrementing auto_status_posts counter."""
        result = await db_store.increment_monthly_counter(
            "auto_status_posts", "2025_10", 1
        )
        
        assert result is True
        mock_client.update_item.assert_called_once()
        
        # Verify call arguments
        call_args = mock_client.update_item.call_args
        assert call_args[1]["table_name"] == "test_table"
        assert call_args[1]["key"] == {
            "PK": {"S": "METRICS_SUMMARY"},
            "SK": {"S": "AGGREGATES"}
        }
        assert call_args[1]["update_expression"] == "ADD #field :inc"
        assert call_args[1]["expression_attribute_names"] == {
            "#field": "auto_status_posts_2025_10"
        }
        assert call_args[1]["expression_attribute_values"] == {
            ":inc": {"N": "1"}
        }
    
    @pytest.mark.asyncio
    async def test_increment_war_room_sent(self, db_store, mock_client):
        """Test incrementing war_room_sent counter."""
        result = await db_store.increment_monthly_counter(
            "war_room_sent", "2025_09", 5
        )
        
        assert result is True
        
        # Verify field name and increment value
        call_args = mock_client.update_item.call_args
        assert call_args[1]["expression_attribute_names"] == {
            "#field": "war_room_sent_2025_09"
        }
        assert call_args[1]["expression_attribute_values"] == {
            ":inc": {"N": "5"}
        }
    
    @pytest.mark.asyncio
    async def test_increment_default_value(self, db_store, mock_client):
        """Test default increment value is 1."""
        result = await db_store.increment_monthly_counter(
            "auto_status_posts", "2025_10"
        )
        
        assert result is True
        
        call_args = mock_client.update_item.call_args
        assert call_args[1]["expression_attribute_values"] == {
            ":inc": {"N": "1"}
        }
    
    @pytest.mark.asyncio
    async def test_increment_error_handling(self, db_store, mock_client):
        """Test error handling when increment fails."""
        mock_client.update_item.side_effect = Exception("DynamoDB error")
        
        result = await db_store.increment_monthly_counter(
            "auto_status_posts", "2025_10", 1
        )
        
        assert result is False


class TestGetMonthlyAggregates:
    """Test get_monthly_aggregates method."""
    
    @pytest.mark.asyncio
    async def test_get_single_month(self, db_store, mock_client):
        """Test retrieving aggregates for single month."""
        # Mock DynamoDB response
        mock_client.get_item.return_value = {
            "Item": {
                "PK": {"S": "METRICS_SUMMARY"},
                "SK": {"S": "AGGREGATES"},
                "auto_status_posts_2025_10": {"N": "45"},
                "war_room_sent_2025_10": {"N": "450"},
                "war_room_success_2025_10": {"N": "445"},
                "war_room_failed_2025_10": {"N": "5"},
                "war_room_unique_users_2025_10": {"N": "128"}
            }
        }
        
        result = await db_store.get_monthly_aggregates(["2025_10"])
        
        assert "2025_10" in result
        assert result["2025_10"]["auto_status_posts"] == 45
        assert result["2025_10"]["war_room_sent"] == 450
        assert result["2025_10"]["war_room_success"] == 445
        assert result["2025_10"]["war_room_failed"] == 5
        assert result["2025_10"]["war_room_unique_users"] == 128
    
    @pytest.mark.asyncio
    async def test_get_multiple_months(self, db_store, mock_client):
        """Test retrieving aggregates for multiple months."""
        mock_client.get_item.return_value = {
            "Item": {
                "PK": {"S": "METRICS_SUMMARY"},
                "SK": {"S": "AGGREGATES"},
                "auto_status_posts_2025_09": {"N": "52"},
                "auto_status_posts_2025_10": {"N": "45"},
                "war_room_sent_2025_09": {"N": "380"},
                "war_room_sent_2025_10": {"N": "450"}
            }
        }
        
        result = await db_store.get_monthly_aggregates(["2025_09", "2025_10"])
        
        assert "2025_09" in result
        assert "2025_10" in result
        assert result["2025_09"]["auto_status_posts"] == 52
        assert result["2025_10"]["auto_status_posts"] == 45
    
    @pytest.mark.asyncio
    async def test_get_missing_counters(self, db_store, mock_client):
        """Test handling of missing counter fields."""
        mock_client.get_item.return_value = {
            "Item": {
                "PK": {"S": "METRICS_SUMMARY"},
                "SK": {"S": "AGGREGATES"},
                "auto_status_posts_2025_10": {"N": "45"}
                # Other counters missing
            }
        }
        
        result = await db_store.get_monthly_aggregates(["2025_10"])
        
        assert result["2025_10"]["auto_status_posts"] == 45
        assert result["2025_10"]["war_room_sent"] == 0
        assert result["2025_10"]["war_room_success"] == 0
        assert result["2025_10"]["war_room_failed"] == 0
        assert result["2025_10"]["war_room_unique_users"] == 0
    
    @pytest.mark.asyncio
    async def test_get_record_not_found(self, db_store, mock_client):
        """Test handling when METRICS_SUMMARY record doesn't exist."""
        mock_client.get_item.return_value = {}
        
        result = await db_store.get_monthly_aggregates(["2025_10"])
        
        assert "2025_10" in result
        assert result["2025_10"] == {}
    
    @pytest.mark.asyncio
    async def test_get_error_handling(self, db_store, mock_client):
        """Test error handling when retrieval fails."""
        mock_client.get_item.side_effect = Exception("DynamoDB error")
        
        result = await db_store.get_monthly_aggregates(["2025_10"])
        
        assert "2025_10" in result
        assert result["2025_10"] == {}
    
    @pytest.mark.asyncio
    async def test_get_correct_key_used(self, db_store, mock_client):
        """Test that correct DynamoDB key is used."""
        mock_client.get_item.return_value = {"Item": {"PK": {"S": "METRICS_SUMMARY"}}}
        
        await db_store.get_monthly_aggregates(["2025_10"])
        
        call_args = mock_client.get_item.call_args
        assert call_args[1]["key"] == {
            "PK": {"S": "METRICS_SUMMARY"},
            "SK": {"S": "AGGREGATES"}
        }
