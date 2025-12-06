"""
Unit tests for ChannelQueryOperations pagination functionality.

Tests the get_all_active_channels method with various pagination scenarios.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.db.operations.channel_query_operations import ChannelQueryOperations


@pytest.mark.asyncio
class TestChannelQueryOperationsPagination:
    """Test pagination functionality in ChannelQueryOperations."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock DynamoDB client."""
        client = MagicMock()
        client.scan = AsyncMock()
        return client

    @pytest.fixture
    def channel_query_ops(self, mock_client):
        """Create ChannelQueryOperations instance with mocked client."""
        return ChannelQueryOperations(client=mock_client, table_name="test-table")

    async def test_get_all_active_channels_single_page(self, mock_client, channel_query_ops):
        """Test get_all_active_channels with single page of results (no pagination needed)."""
        # Setup - single page response with no LastEvaluatedKey
        mock_client.scan.return_value = {
            "Items": [
                {
                    "PK": {"S": "CHANNEL#C001"},
                    "SK": {"S": "CSO_DETAILS"},
                    "channel_id": {"S": "C001"},
                    "channel_name": {"S": "channel-1"},
                    "archived": {"BOOL": False},
                },
                {
                    "PK": {"S": "CHANNEL#C002"},
                    "SK": {"S": "CSO_DETAILS"},
                    "channel_id": {"S": "C002"},
                    "channel_name": {"S": "channel-2"},
                    "archived": {"BOOL": False},
                },
            ]
        }

        # Execute
        result = await channel_query_ops.get_all_active_channels()

        # Verify
        assert len(result) == 2
        assert result[0]["channel_id"] == "C001"
        assert result[1]["channel_id"] == "C002"

        # Verify scan was called only once (no pagination)
        assert mock_client.scan.call_count == 1

        # Verify scan parameters
        call_args = mock_client.scan.call_args[1]
        assert call_args["table_name"] == "test-table"
        assert "SK = :sk" in call_args["filter_expression"]
        assert call_args["expression_attribute_values"][":sk"]["S"] == "CSO_DETAILS"
        assert call_args["expression_attribute_values"][":not_archived"]["BOOL"] is False
        assert "exclusive_start_key" not in call_args

    async def test_get_all_active_channels_multiple_pages(self, mock_client, channel_query_ops):
        """Test get_all_active_channels with multiple pages requiring pagination."""
        # Setup - simulate pagination with 3 pages
        mock_client.scan.side_effect = [
            # First page
            {
                "Items": [
                    {
                        "PK": {"S": "CHANNEL#C001"},
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": "C001"},
                        "channel_name": {"S": "channel-1"},
                    },
                    {
                        "PK": {"S": "CHANNEL#C002"},
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": "C002"},
                        "channel_name": {"S": "channel-2"},
                    },
                ],
                "LastEvaluatedKey": {"PK": {"S": "CHANNEL#C002"}},
            },
            # Second page
            {
                "Items": [
                    {
                        "PK": {"S": "CHANNEL#C003"},
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": "C003"},
                        "channel_name": {"S": "channel-3"},
                    },
                    {
                        "PK": {"S": "CHANNEL#C09C20PLH7C"},  # The missing channel from production
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": "C09C20PLH7C"},
                        "channel_name": {"S": "problem-channel"},
                    },
                ],
                "LastEvaluatedKey": {"PK": {"S": "CHANNEL#C09C20PLH7C"}},
            },
            # Third page (final)
            {
                "Items": [
                    {
                        "PK": {"S": "CHANNEL#C005"},
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": "C005"},
                        "channel_name": {"S": "channel-5"},
                    }
                ]
                # No LastEvaluatedKey - this is the last page
            },
        ]

        # Execute
        result = await channel_query_ops.get_all_active_channels()

        # Verify all items from all pages are returned
        assert len(result) == 5
        channel_ids = [ch["channel_id"] for ch in result]
        assert "C001" in channel_ids
        assert "C002" in channel_ids
        assert "C003" in channel_ids
        assert "C09C20PLH7C" in channel_ids  # The problematic channel
        assert "C005" in channel_ids

        # Verify scan was called 3 times (for 3 pages)
        assert mock_client.scan.call_count == 3

        # Verify first call has no exclusive_start_key
        first_call = mock_client.scan.call_args_list[0][1]
        assert "exclusive_start_key" not in first_call

        # Verify second call has exclusive_start_key from first response
        second_call = mock_client.scan.call_args_list[1][1]
        assert second_call["exclusive_start_key"]["PK"]["S"] == "CHANNEL#C002"

        # Verify third call has exclusive_start_key from second response
        third_call = mock_client.scan.call_args_list[2][1]
        assert third_call["exclusive_start_key"]["PK"]["S"] == "CHANNEL#C09C20PLH7C"

    async def test_get_all_active_channels_empty_results(self, mock_client, channel_query_ops):
        """Test get_all_active_channels with no channels found."""
        # Setup - empty response
        mock_client.scan.return_value = {"Items": []}

        # Execute
        result = await channel_query_ops.get_all_active_channels()

        # Verify
        assert result == []
        assert mock_client.scan.call_count == 1

    async def test_get_all_active_channels_filters_archived(self, mock_client, channel_query_ops):
        """Test that get_all_active_channels properly filters archived channels."""
        # Setup
        mock_client.scan.return_value = {
            "Items": [
                {
                    "PK": {"S": "CHANNEL#C001"},
                    "SK": {"S": "CSO_DETAILS"},
                    "channel_id": {"S": "C001"},
                    "archived": {"BOOL": False},
                }
            ]
        }

        # Execute
        await channel_query_ops.get_all_active_channels()

        # Verify filter expression includes archived check
        call_args = mock_client.scan.call_args[1]
        assert "archived" in call_args["filter_expression"]
        assert ":not_archived" in call_args["expression_attribute_values"]
        assert call_args["expression_attribute_values"][":not_archived"]["BOOL"] is False

    async def test_get_all_active_channels_error_handling(self, mock_client, channel_query_ops):
        """Test error handling in get_all_active_channels."""
        # Setup - simulate DynamoDB error
        mock_client.scan.side_effect = Exception("DynamoDB unavailable")

        # Execute
        result = await channel_query_ops.get_all_active_channels()

        # Verify - should return empty list on error
        assert result == []
        assert mock_client.scan.call_count == 1

    async def test_get_all_active_channels_pagination_with_8_channels(
        self, mock_client, channel_query_ops
    ):
        """
        Test the exact production scenario: 8 channels with pagination.
        This simulates the bug where channel C09C20PLH7C was on page 2.
        """
        # Setup - simulate the exact production scenario
        mock_client.scan.side_effect = [
            # First page with 7 channels
            {
                "Items": [
                    {
                        "PK": {"S": f"CHANNEL#C{i:03d}"},
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": f"C{i:03d}"},
                        "channel_name": {"S": f"channel-{i}"},
                    }
                    for i in range(1, 8)  # C001 through C007
                ],
                "LastEvaluatedKey": {"PK": {"S": "CHANNEL#C007"}},
            },
            # Second page with the 8th channel (C09C20PLH7C)
            {
                "Items": [
                    {
                        "PK": {"S": "CHANNEL#C09C20PLH7C"},
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": "C09C20PLH7C"},
                        "channel_name": {"S": "problematic-channel"},
                    }
                ]
                # No LastEvaluatedKey - this is the last page
            },
        ]

        # Execute
        result = await channel_query_ops.get_all_active_channels()

        # Verify all 8 channels are returned
        assert len(result) == 8

        # Verify the first 7 channels
        for i in range(7):
            assert result[i]["channel_id"] == f"C{i+1:03d}"

        # Verify the 8th channel (the one that was missing before the fix)
        assert result[7]["channel_id"] == "C09C20PLH7C"
        assert result[7]["channel_name"] == "problematic-channel"

        # Verify pagination occurred
        assert mock_client.scan.call_count == 2

    async def test_get_all_active_channels_normalization(self, mock_client, channel_query_ops):
        """Test that items are properly normalized after retrieval."""
        # Setup - response with various field types
        mock_client.scan.return_value = {
            "Items": [
                {
                    "PK": {"S": "CHANNEL#C001"},
                    "SK": {"S": "CSO_DETAILS"},
                    "channel_id": {"S": "C001"},
                    "channel_name": {"S": "test-channel"},
                    "archived": {"BOOL": False},
                    "created_at": {"N": "1234567890"},
                    "custom_field": {"S": "custom_value"},
                }
            ]
        }

        # Execute
        result = await channel_query_ops.get_all_active_channels()

        # Verify normalization occurred
        assert len(result) == 1
        normalized = result[0]

        # Check that DynamoDB type descriptors are removed
        assert isinstance(normalized["channel_id"], str)
        assert normalized["channel_id"] == "C001"
        assert isinstance(normalized["channel_name"], str)
        assert normalized["channel_name"] == "test-channel"
        assert isinstance(normalized["archived"], bool)
        assert normalized["archived"] is False

        # Check number conversion
        assert isinstance(normalized.get("created_at"), (int, float))
        assert normalized.get("created_at") == 1234567890

    async def test_get_all_active_channels_large_dataset(self, mock_client, channel_query_ops):
        """Test pagination with a large dataset spanning many pages."""
        # Setup - simulate 5 pages with 20 channels each (100 total)
        pages = []
        for page_num in range(5):
            start_idx = page_num * 20
            end_idx = start_idx + 20
            items = [
                {
                    "PK": {"S": f"CHANNEL#C{i:04d}"},
                    "SK": {"S": "CSO_DETAILS"},
                    "channel_id": {"S": f"C{i:04d}"},
                    "channel_name": {"S": f"channel-{i}"},
                }
                for i in range(start_idx, end_idx)
            ]

            response = {"Items": items}
            if page_num < 4:  # Add LastEvaluatedKey for all but the last page
                response["LastEvaluatedKey"] = {"PK": {"S": f"CHANNEL#C{end_idx-1:04d}"}}

            pages.append(response)

        mock_client.scan.side_effect = pages

        # Execute
        result = await channel_query_ops.get_all_active_channels()

        # Verify all 100 channels are returned
        assert len(result) == 100

        # Verify pagination occurred 5 times
        assert mock_client.scan.call_count == 5

        # Verify channels are in order
        for i, channel in enumerate(result):
            assert channel["channel_id"] == f"C{i:04d}"
