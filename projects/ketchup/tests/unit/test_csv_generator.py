"""
test_csv_generator.py

Unit tests for the CommandUsageCSVGenerator class.
"""

import pytest

from packages.core.exports.csv_generator import CommandUsageCSVGenerator


@pytest.fixture
def csv_generator():
    """Create a CommandUsageCSVGenerator instance."""
    return CommandUsageCSVGenerator()


@pytest.fixture
def sample_export_data():
    """Create sample export data for testing."""
    return {
        "trends": {
            "current_period": {
                "start": 1234567890,
                "end": 1234654290,
                "commands": {"status": 45, "report": 32, "list": 28},
                "users": {"U12345": 20, "U67890": 15},
            },
            "previous_period": {
                "start": 1234481490,
                "end": 1234567890,
                "commands": {"status": 40, "report": 35, "list": 25},
                "users": {"U12345": 18, "U67890": 12},
            },
            "trends": {
                "commands": {
                    "status": {
                        "current": 45,
                        "previous": 40,
                        "delta": 5,
                        "percent": 12.5,
                    },
                    "report": {
                        "current": 32,
                        "previous": 35,
                        "delta": -3,
                        "percent": -8.6,
                    },
                    "list": {
                        "current": 28,
                        "previous": 25,
                        "delta": 3,
                        "percent": 12.0,
                    },
                },
                "total_usage": {
                    "current": 105,
                    "previous": 100,
                    "delta": 5,
                    "percent": 5.0,
                },
            },
        },
        "user_breakdown": {
            "U12345": {
                "user_name": "harrison",
                "commands": {"status": 20, "report": 15, "list": 10},
                "total_count": 45,
            },
            "U67890": {
                "user_name": "sarah",
                "commands": {"status": 15, "report": 10, "list": 8},
                "total_count": 33,
            },
        },
        "top_users": [
            ("U12345", "harrison", 45),
            ("U67890", "sarah", 33),
            ("U11111", "michael", 28),
        ],
        "export_timestamp": "2025-06-21T15:30:00Z",
        "period_days": 7,
    }


@pytest.mark.asyncio
async def test_generate_csv_with_full_data(csv_generator, sample_export_data):
    """Test CSV generation with complete data."""
    csv_content = await csv_generator.generate_csv(sample_export_data)

    # Check that CSV content is generated
    assert csv_content
    assert isinstance(csv_content, str)

    # Check for key sections
    assert "Ketchup Command Usage Report" in csv_content
    assert "COMMAND TRENDS" in csv_content
    assert "USER COMMAND BREAKDOWN" in csv_content
    assert "TOP 10 USERS" in csv_content
    assert "REPORT METADATA" in csv_content

    # Check for specific data
    assert "harrison" in csv_content
    assert "sarah" in csv_content
    assert "status" in csv_content
    assert "45" in csv_content  # harrison's total
    assert "12.5%" in csv_content  # status percent change


@pytest.mark.asyncio
async def test_generate_csv_with_empty_data(csv_generator):
    """Test CSV generation with empty data."""
    empty_data = {
        "trends": {},
        "user_breakdown": {},
        "top_users": [],
        "export_timestamp": "2025-06-21T15:30:00Z",
        "period_days": 7,
    }

    csv_content = await csv_generator.generate_csv(empty_data)

    # Should still generate a report
    assert csv_content
    assert "Ketchup Command Usage Report" in csv_content
    assert "No user data available" in csv_content


@pytest.mark.asyncio
async def test_generate_csv_with_missing_sections(csv_generator):
    """Test CSV generation with missing data sections."""
    partial_data = {"export_timestamp": "2025-06-21T15:30:00Z", "period_days": 7}

    csv_content = await csv_generator.generate_csv(partial_data)

    # Should handle missing sections gracefully
    assert csv_content
    assert "Ketchup Command Usage Report" in csv_content


@pytest.mark.asyncio
async def test_csv_formatting(csv_generator, sample_export_data):
    """Test that CSV is properly formatted."""
    csv_content = await csv_generator.generate_csv(sample_export_data)

    lines = csv_content.split("\n")

    # Check header
    assert "Ketchup Command Usage Report" in lines[0]
    assert "Generated:" in lines[1] and "2025-06-21T15:30:00Z" in lines[1]

    # Check for proper CSV structure (commas)
    trend_lines = [line for line in lines if "status," in line.lower()]
    assert len(trend_lines) > 0

    # Check a data line has the right number of columns
    for line in trend_lines:
        if line.startswith("status"):
            parts = line.split(",")
            assert len(parts) >= 5  # Command, Current, Previous, Change, % Change


@pytest.mark.asyncio
async def test_trend_indicators(csv_generator, sample_export_data):
    """Test that trend indicators are correctly shown."""
    csv_content = await csv_generator.generate_csv(sample_export_data)

    # Check for trend indicators
    assert "Up" in csv_content  # for positive trends
    assert "Down" in csv_content  # for negative trends


@pytest.mark.asyncio
async def test_error_handling(csv_generator):
    """Test error handling during CSV generation."""
    # Pass invalid data that will cause an error
    invalid_data = "not a dict"

    csv_content = await csv_generator.generate_csv(invalid_data)

    # Should return error message instead of crashing
    assert csv_content == "Error generating CSV report"
