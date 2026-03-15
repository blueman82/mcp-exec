"""
Tests for individual task wrappers.

Verifies:
- Each task can be called with mocked container
- Task handlers correctly wrap underlying service calls
- TaskConfig generators return valid configurations
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_unified_scheduler.task_config import TaskConfig


class TestMaintenanceFetchTask:
    """Tests for MaintenanceFetchTask wrapper."""

    @pytest.mark.asyncio
    async def test_maintenance_fetch_task_calls_underlying_service(self):
        """Test that maintenance_fetch_task calls fetch_and_store_maintenance_data."""
        mock_container = MagicMock()
        mock_result = {"status": "success", "message": "Fetched maintenance data"}

        with patch(
            "ketchup_unified_scheduler.tasks.maintenance_fetch_task.fetch_and_store_maintenance_data",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fetch:
            from ketchup_unified_scheduler.tasks.maintenance_fetch_task import (
                maintenance_fetch_task,
            )

            await maintenance_fetch_task(container=mock_container)

            mock_fetch.assert_called_once_with(container=mock_container)

    @pytest.mark.asyncio
    async def test_maintenance_fetch_task_raises_on_error_result(self):
        """Test that maintenance_fetch_task raises on error result."""
        mock_container = MagicMock()
        mock_result = {"status": "error", "message": "Failed to fetch"}

        with patch(
            "ketchup_unified_scheduler.tasks.maintenance_fetch_task.fetch_and_store_maintenance_data",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from ketchup_unified_scheduler.tasks.maintenance_fetch_task import (
                maintenance_fetch_task,
            )

            with pytest.raises(RuntimeError, match="Maintenance fetch failed"):
                await maintenance_fetch_task(container=mock_container)

    @pytest.mark.asyncio
    async def test_maintenance_fetch_task_propagates_exceptions(self):
        """Test that maintenance_fetch_task propagates exceptions."""
        mock_container = MagicMock()

        with patch(
            "ketchup_unified_scheduler.tasks.maintenance_fetch_task.fetch_and_store_maintenance_data",
            new_callable=AsyncMock,
            side_effect=ValueError("Connection error"),
        ):
            from ketchup_unified_scheduler.tasks.maintenance_fetch_task import (
                maintenance_fetch_task,
            )

            with pytest.raises(ValueError, match="Connection error"):
                await maintenance_fetch_task(container=mock_container)

    def test_get_maintenance_fetch_task_config_returns_valid_config(self):
        """Test that get_maintenance_fetch_task_config returns valid TaskConfig."""
        from ketchup_unified_scheduler.tasks.maintenance_fetch_task import (
            get_maintenance_fetch_task_config,
        )

        config = get_maintenance_fetch_task_config()

        assert isinstance(config, TaskConfig)
        assert config.name == "maintenance_fetcher"
        assert config.schedule_time == "01:30"
        assert config.is_time_based is True
        assert config.feature_flag == "KETCHUP_MAINTENANCE_FETCHER_ENABLED"
        assert config.enabled is True


class TestPatRotationTask:
    """Tests for PatRotationTask wrapper."""

    @pytest.mark.asyncio
    async def test_pat_rotation_task_calls_rotator(self):
        """Test that pat_rotation_task calls PATRotator.rotate()."""
        mock_container = MagicMock()
        mock_result = {"status": "success", "action": "rotated"}

        with patch("ketchup_unified_scheduler.tasks.pat_rotation_task.PATRotator") as MockRotator:
            mock_rotator_instance = MockRotator.return_value
            mock_rotator_instance.rotate = AsyncMock(return_value=mock_result)

            from ketchup_unified_scheduler.tasks.pat_rotation_task import pat_rotation_task

            await pat_rotation_task(container=mock_container)

            MockRotator.assert_called_once_with(container=mock_container)
            mock_rotator_instance.rotate.assert_called_once()

    @pytest.mark.asyncio
    async def test_pat_rotation_task_handles_skipped_status(self):
        """Test that pat_rotation_task handles skipped status gracefully."""
        mock_container = MagicMock()
        mock_result = {"status": "skipped", "action": "no_rotation_needed"}

        with patch("ketchup_unified_scheduler.tasks.pat_rotation_task.PATRotator") as MockRotator:
            mock_rotator_instance = MockRotator.return_value
            mock_rotator_instance.rotate = AsyncMock(return_value=mock_result)

            from ketchup_unified_scheduler.tasks.pat_rotation_task import pat_rotation_task

            # Should not raise
            await pat_rotation_task(container=mock_container)

    @pytest.mark.asyncio
    async def test_pat_rotation_task_propagates_exceptions(self):
        """Test that pat_rotation_task propagates exceptions."""
        mock_container = MagicMock()

        with patch("ketchup_unified_scheduler.tasks.pat_rotation_task.PATRotator") as MockRotator:
            mock_rotator_instance = MockRotator.return_value
            mock_rotator_instance.rotate = AsyncMock(side_effect=Exception("MCP error"))

            from ketchup_unified_scheduler.tasks.pat_rotation_task import pat_rotation_task

            with pytest.raises(Exception, match="MCP error"):
                await pat_rotation_task(container=mock_container)

    def test_get_pat_rotation_task_config_returns_valid_config(self):
        """Test that get_pat_rotation_task_config returns valid TaskConfig."""
        from ketchup_unified_scheduler.tasks.pat_rotation_task import get_pat_rotation_task_config

        config = get_pat_rotation_task_config()

        assert isinstance(config, TaskConfig)
        assert config.name == "pat_rotator"
        assert config.interval_minutes == 1440  # 24 hours
        assert config.is_interval_based is True
        assert config.feature_flag == "KETCHUP_JIRA_PAT_ROTATOR_FEATURE"
        assert config.enabled is True


class TestMetadataUpdateTask:
    """Tests for MetadataUpdateTask wrapper."""

    @pytest.mark.asyncio
    async def test_metadata_update_task_calls_process_channels(self):
        """Test that metadata_update_task calls process_channels."""
        mock_container = MagicMock()
        mock_result = {"statusCode": 200, "body": "Processed channels"}

        with patch(
            "ketchup_unified_scheduler.tasks.metadata_update_task.process_channels",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_process:
            from ketchup_unified_scheduler.tasks.metadata_update_task import metadata_update_task

            await metadata_update_task(container=mock_container)

            mock_process.assert_called_once_with(
                container=mock_container,
            )

    @pytest.mark.asyncio
    async def test_metadata_update_task_handles_non_200_status(self):
        """Test that metadata_update_task handles non-200 status gracefully."""
        mock_container = MagicMock()
        mock_result = {"statusCode": 500, "body": "Error"}

        with patch(
            "ketchup_unified_scheduler.tasks.metadata_update_task.process_channels",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from ketchup_unified_scheduler.tasks.metadata_update_task import metadata_update_task

            # Should not raise, just log warning
            await metadata_update_task(container=mock_container)

    @pytest.mark.asyncio
    async def test_metadata_update_task_propagates_exceptions(self):
        """Test that metadata_update_task propagates exceptions."""
        mock_container = MagicMock()

        with patch(
            "ketchup_unified_scheduler.tasks.metadata_update_task.process_channels",
            new_callable=AsyncMock,
            side_effect=ValueError("DynamoDB error"),
        ):
            from ketchup_unified_scheduler.tasks.metadata_update_task import metadata_update_task

            with pytest.raises(ValueError, match="DynamoDB error"):
                await metadata_update_task(container=mock_container)

    def test_get_metadata_update_task_config_returns_valid_config(self):
        """Test that get_metadata_update_task_config returns valid TaskConfig."""
        from ketchup_unified_scheduler.tasks.metadata_update_task import (
            get_metadata_update_task_config,
        )

        config = get_metadata_update_task_config()

        assert isinstance(config, TaskConfig)
        assert config.name == "metadata_updater"
        assert config.interval_minutes == 15
        assert config.is_interval_based is True
        assert config.feature_flag == "KETCHUP_METADATA_UPDATER_FEATURE"
        assert config.enabled is True


class TestStatusUpdateTask:
    """Tests for StatusUpdateTask wrapper."""

    @pytest.mark.asyncio
    async def test_status_update_task_calls_run_auto_status(self):
        """Test that status_update_task calls run_auto_status."""
        mock_container = MagicMock()

        with patch(
            "ketchup_unified_scheduler.tasks.status_update_task.run_auto_status",
            new_callable=AsyncMock,
        ) as mock_run:
            from ketchup_unified_scheduler.tasks.status_update_task import status_update_task

            await status_update_task(container=mock_container)

            mock_run.assert_called_once_with(container=mock_container)

    @pytest.mark.asyncio
    async def test_status_update_task_propagates_exceptions(self):
        """Test that status_update_task propagates exceptions."""
        mock_container = MagicMock()

        with patch(
            "ketchup_unified_scheduler.tasks.status_update_task.run_auto_status",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Slack API error"),
        ):
            from ketchup_unified_scheduler.tasks.status_update_task import status_update_task

            with pytest.raises(RuntimeError, match="Slack API error"):
                await status_update_task(container=mock_container)

    def test_get_status_update_task_config_returns_valid_config(self):
        """Test that get_status_update_task_config returns valid TaskConfig."""
        from ketchup_unified_scheduler.tasks.status_update_task import get_status_update_task_config

        config = get_status_update_task_config()

        assert isinstance(config, TaskConfig)
        assert config.name == "status_updater"
        assert config.interval_minutes == 55
        assert config.is_interval_based is True
        assert config.feature_flag == "KETCHUP_STATUS_UPDATER_FEATURE"
        assert config.enabled is True


class TestJiraReportTask:
    """Tests for JiraReportTask wrapper."""

    @pytest.mark.asyncio
    async def test_jira_report_task_calls_run_reporting_cycle(self):
        """Test that jira_report_task calls run_reporting_cycle."""
        mock_container = MagicMock()

        with patch(
            "ketchup_unified_scheduler.tasks.jira_report_task.run_reporting_cycle",
            new_callable=AsyncMock,
        ) as mock_run:
            from ketchup_unified_scheduler.tasks.jira_report_task import jira_report_task

            await jira_report_task(container=mock_container)

            mock_run.assert_called_once_with(container=mock_container)

    @pytest.mark.asyncio
    async def test_jira_report_task_propagates_exceptions(self):
        """Test that jira_report_task propagates exceptions."""
        mock_container = MagicMock()

        with patch(
            "ketchup_unified_scheduler.tasks.jira_report_task.run_reporting_cycle",
            new_callable=AsyncMock,
            side_effect=Exception("JIRA API error"),
        ):
            from ketchup_unified_scheduler.tasks.jira_report_task import jira_report_task

            with pytest.raises(Exception, match="JIRA API error"):
                await jira_report_task(container=mock_container)

    def test_get_jira_report_task_config_returns_valid_config(self):
        """Test that get_jira_report_task_config returns valid TaskConfig."""
        from ketchup_unified_scheduler.tasks.jira_report_task import get_jira_report_task_config

        config = get_jira_report_task_config()

        assert isinstance(config, TaskConfig)
        assert config.name == "jira_reporter"
        assert config.interval_minutes == 15
        assert config.is_interval_based is True
        assert config.feature_flag == "KETCHUP_JIRA_REPORTER_FEATURE"
        assert config.enabled is True


class TestTaskModuleExports:
    """Tests for task module exports."""

    def test_tasks_init_exports_all_tasks(self):
        """Test that tasks __init__ exports all expected functions."""
        from ketchup_unified_scheduler import tasks

        # Check task handlers
        assert hasattr(tasks, "maintenance_fetch_task")
        assert hasattr(tasks, "pat_rotation_task")
        assert hasattr(tasks, "metadata_update_task")
        assert hasattr(tasks, "status_update_task")
        assert hasattr(tasks, "jira_report_task")

        # Check config getters
        assert hasattr(tasks, "get_maintenance_fetch_task_config")
        assert hasattr(tasks, "get_pat_rotation_task_config")
        assert hasattr(tasks, "get_metadata_update_task_config")
        assert hasattr(tasks, "get_status_update_task_config")
        assert hasattr(tasks, "get_jira_report_task_config")

    def test_all_config_getters_return_task_configs(self):
        """Test that all config getters return TaskConfig instances."""
        from ketchup_unified_scheduler.tasks import (
            get_jira_report_task_config,
            get_maintenance_fetch_task_config,
            get_metadata_update_task_config,
            get_pat_rotation_task_config,
            get_status_update_task_config,
        )

        configs = [
            get_maintenance_fetch_task_config(),
            get_pat_rotation_task_config(),
            get_metadata_update_task_config(),
            get_status_update_task_config(),
            get_jira_report_task_config(),
        ]

        for config in configs:
            assert isinstance(config, TaskConfig)
            assert config.name is not None
            assert config.handler is not None
            assert (config.interval_minutes is not None) or (config.schedule_time is not None)


class TestHealthMonitor:
    """Tests for PerTaskHealthMonitor."""

    def test_health_monitor_update_and_get_status(self):
        """Test updating and getting task status."""
        import tempfile

        from ketchup_unified_scheduler.health_monitor import PerTaskHealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = PerTaskHealthMonitor(base_path=tmpdir)

            monitor.update_task_status("test_task", "running")
            status = monitor.get_task_status("test_task")

            assert status is not None
            assert status["status"] == "running"
            assert "timestamp" in status

    def test_health_monitor_update_last_run(self):
        """Test updating last run timestamp."""
        import tempfile

        from ketchup_unified_scheduler.health_monitor import PerTaskHealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = PerTaskHealthMonitor(base_path=tmpdir)

            monitor.update_task_last_run("test_task")
            last_run = monitor.get_last_run("test_task")

            assert last_run is not None
            assert isinstance(last_run, int)

    def test_health_monitor_get_all_statuses(self):
        """Test getting all task statuses."""
        import tempfile

        from ketchup_unified_scheduler.health_monitor import PerTaskHealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = PerTaskHealthMonitor(base_path=tmpdir)

            monitor.update_task_status("task1", "running")
            monitor.update_task_status("task2", "success")

            statuses = monitor.get_all_task_statuses()

            assert "task1" in statuses
            assert "task2" in statuses
            assert statuses["task1"]["status"] == "running"
            assert statuses["task2"]["status"] == "success"

    def test_health_monitor_clear_task_status(self):
        """Test clearing task status files."""
        import tempfile

        from ketchup_unified_scheduler.health_monitor import PerTaskHealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = PerTaskHealthMonitor(base_path=tmpdir)

            monitor.update_task_status("test_task", "running")
            assert monitor.get_task_status("test_task") is not None

            monitor.clear_task_status("test_task")
            assert monitor.get_task_status("test_task") is None

    def test_health_monitor_register_task(self):
        """Test registering a task sets initial status."""
        import tempfile

        from ketchup_unified_scheduler.health_monitor import PerTaskHealthMonitor
        from ketchup_unified_scheduler.task_config import TaskConfig

        async def handler(container=None):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = PerTaskHealthMonitor(base_path=tmpdir)
            config = TaskConfig(name="new_task", handler=handler, interval_minutes=15)

            monitor.register_task(config)
            status = monitor.get_task_status("new_task")

            assert status is not None
            assert status["status"] == "registered"
