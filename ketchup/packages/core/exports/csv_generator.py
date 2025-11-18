"""
csv_generator.py

This module provides functionality to generate CSV exports of command usage data.
It formats the data into sections for easier analysis in spreadsheet applications.
"""

import csv
import io
from datetime import datetime
from typing import Any, Dict

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class CommandUsageCSVGenerator:
    """
    Generates CSV exports from command usage data.

    This class handles formatting and organizing the data into a well-structured
    CSV file with sections for top users, command trends, and user breakdown.
    """

    def __init__(self):
        """Initialize the CSV generator."""
        logger.info("CommandUsageCSVGenerator initialized")

    async def generate_csv(self, export_data: Dict[str, Any]) -> str:
        """
        Generate CSV content from export data.

        Args:
            export_data: Dictionary containing command usage export data

        Returns:
            String containing CSV content
        """
        try:
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)

            # Add header section
            self._write_header_section(writer, export_data)

            # Add top users section
            self._write_top_users_section(writer, export_data)

            # Add command trends section
            self._write_command_trends_section(writer, export_data)

            # Add user breakdown section
            self._write_user_breakdown_section(writer, export_data)

            # Add report metadata section
            self._write_report_metadata_section(writer, export_data)

            # Return the CSV content as a string
            output.seek(0)
            return output.getvalue()

        except Exception as e:
            logger.error(f"Error generating CSV: {str(e)}")
            return "Error generating CSV report"

    def _write_header_section(
        self, writer: csv.writer, export_data: Dict[str, Any]
    ) -> None:
        """Write the header section of the CSV file."""
        # Write metadata
        writer.writerow(["Ketchup Command Usage Report"])
        writer.writerow(
            [
                "Generated:",
                export_data.get("export_timestamp", datetime.now().isoformat()),
            ]
        )
        writer.writerow(["Period", f"{export_data.get('period_days', 7)} days"])
        writer.writerow(["Current Week", export_data.get("current_week_range", "")])
        writer.writerow(["Previous Week", export_data.get("previous_week_range", "")])

        # Add summary statistics
        trends = export_data.get("trends", {})
        total_usage = trends.get("trends", {}).get("total_usage", {})

        writer.writerow([""])
        writer.writerow(["Summary Statistics"])
        writer.writerow(["Total Commands", total_usage.get("current", 0)])
        writer.writerow(
            [
                "Change from Previous Week",
                f"{total_usage.get('delta', 0)} ({total_usage.get('percent', 0):.1f}%)",
            ]
        )
        writer.writerow(["Active Users", len(export_data.get("user_breakdown", {}))])
        writer.writerow([""])

    def _write_top_users_section(
        self, writer: csv.writer, export_data: Dict[str, Any]
    ) -> None:
        """Write the top users section of the CSV file."""
        writer.writerow(["TOP 10 USERS"])
        writer.writerow(["Rank", "User ID", "User Name", "Command Count"])

        top_users = export_data.get("top_users", [])
        if not top_users:
            writer.writerow(["No user data available"])
        else:
            for i, (user_id, user_name, count) in enumerate(top_users, 1):
                writer.writerow([i, user_id, user_name, count])

        writer.writerow([""])

    def _write_command_trends_section(
        self, writer: csv.writer, export_data: Dict[str, Any]
    ) -> None:
        """Write the command trends section of the CSV file."""
        writer.writerow(["COMMAND TRENDS"])
        writer.writerow(
            ["Command", "Current Week", "Previous Week", "Change", "Percent Change", "Trend"]
        )

        trends = export_data.get("trends", {}).get("trends", {}).get("commands", {})
        for cmd, data in sorted(
            trends.items(), key=lambda x: x[1].get("current", 0), reverse=True
        ):
            delta = data.get("delta", 0)
            trend_indicator = "Up" if delta > 0 else "Down" if delta < 0 else "Stable"
            writer.writerow(
                [
                    cmd,
                    data.get("current", 0),
                    data.get("previous", 0),
                    data.get("delta", 0),
                    f"{data.get('percent', 0):.1f}%",
                    trend_indicator,
                ]
            )

        # Add total row
        total_usage = (
            export_data.get("trends", {}).get("trends", {}).get("total_usage", {})
        )
        writer.writerow(
            [
                "TOTAL",
                total_usage.get("current", 0),
                total_usage.get("previous", 0),
                total_usage.get("delta", 0),
                f"{total_usage.get('percent', 0):.1f}%",
            ]
        )

        writer.writerow([""])

    def _write_user_breakdown_section(
        self, writer: csv.writer, export_data: Dict[str, Any]
    ) -> None:
        """Write the user breakdown section of the CSV file."""
        writer.writerow(["USER COMMAND BREAKDOWN"])
        writer.writerow(
            [
                "User ID",
                "User Name",
                "Total Commands",
                "Command Type",
                "Count",
                "Percentage of User's Commands",
            ]
        )

        breakdown = export_data.get("user_breakdown", {})

        # Sort users by total command count (descending)
        sorted_users = sorted(
            breakdown.items(), key=lambda x: x[1].get("total_count", 0), reverse=True
        )

        for user_id, data in sorted_users:
            user_name = data.get("user_name", "unknown")
            total_count = data.get("total_count", 0)
            commands = data.get("commands", {})

            # Sort commands by count (descending)
            sorted_commands = sorted(commands.items(), key=lambda x: x[1], reverse=True)

            # Write first command with user details
            if sorted_commands:
                cmd_type, count = sorted_commands[0]
                percentage = (count / total_count * 100) if total_count > 0 else 0
                writer.writerow(
                    [
                        user_id,
                        user_name,
                        total_count,
                        cmd_type,
                        count,
                        f"{percentage:.1f}%",
                    ]
                )

                # Write remaining commands without repeating user details
                for cmd_type, count in sorted_commands[1:]:
                    percentage = (count / total_count * 100) if total_count > 0 else 0
                    writer.writerow(
                        [
                            "",  # Empty user_id cell
                            "",  # Empty user_name cell
                            "",  # Empty total_count cell
                            cmd_type,
                            count,
                            f"{percentage:.1f}%",
                        ]
                    )
            else:
                # No commands, just write user info
                writer.writerow([user_id, user_name, total_count, "N/A", 0, "0.0%"])

            # Add empty row between users for readability
            writer.writerow([""])

    def _write_report_metadata_section(
        self, writer: csv.writer, export_data: Dict[str, Any]
    ) -> None:
        """Write the report metadata section of the CSV file."""
        writer.writerow(["REPORT METADATA"])
        writer.writerow(["Export Timestamp", export_data.get("export_timestamp", "")])
        writer.writerow(["Period Days", export_data.get("period_days", 7)])
        writer.writerow([""])
