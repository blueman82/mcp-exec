#!/usr/bin/env python3
"""
Integration tests for scheduler migrations to BaseScheduler.

Tests verify:
1. All scheduler classes can be imported and instantiated
2. Health file paths are correct for backward compatibility
3. Intervals/schedules are correct
4. All schedulers inherit from BaseScheduler properly
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from channel_metadata_updater.scheduler import MetadataUpdaterScheduler
from ketchup_jira_pat_rotator.scheduler import PatRotationScheduler
from ketchup_maintenance_fetcher.scheduler import MaintenanceFetcherScheduler

# Import all migrated schedulers
from ketchup_status_updater.scheduler import StatusUpdaterScheduler

# Import BaseScheduler
from packages.core.schedulers import BaseScheduler

# Mark all tests in this module as not requiring AWS
pytestmark = pytest.mark.no_aws_required


@pytest.mark.no_aws_required
class TestSchedulerImports:
    """Test that all scheduler classes can be imported."""

    def test_basescheduler_import(self):
        """Test BaseScheduler can be imported from packages.core.schedulers."""
        assert BaseScheduler is not None
        assert hasattr(BaseScheduler, "start")
        assert hasattr(BaseScheduler, "run_task")
        assert hasattr(BaseScheduler, "get_sleep_seconds")

    def test_status_updater_scheduler_import(self):
        """Test StatusUpdaterScheduler can be imported."""
        assert StatusUpdaterScheduler is not None
        assert issubclass(StatusUpdaterScheduler, BaseScheduler)

    def test_metadata_updater_scheduler_import(self):
        """Test MetadataUpdaterScheduler can be imported."""
        assert MetadataUpdaterScheduler is not None
        assert issubclass(MetadataUpdaterScheduler, BaseScheduler)

    def test_maintenance_fetcher_scheduler_import(self):
        """Test MaintenanceFetcherScheduler can be imported."""
        assert MaintenanceFetcherScheduler is not None
        assert issubclass(MaintenanceFetcherScheduler, BaseScheduler)

    def test_pat_rotation_scheduler_import(self):
        """Test PatRotationScheduler can be imported."""
        assert PatRotationScheduler is not None
        assert issubclass(PatRotationScheduler, BaseScheduler)


@pytest.mark.no_aws_required
class TestSchedulerInstantiation:
    """Test that all schedulers can be instantiated."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_instantiation(self, mock_run):
        """Test StatusUpdaterScheduler can be instantiated."""
        scheduler = StatusUpdaterScheduler()
        assert scheduler is not None
        assert isinstance(scheduler, BaseScheduler)
        assert scheduler.running is True

    @patch("channel_metadata_updater.scheduler.run_metadata_update", new_callable=AsyncMock)
    def test_metadata_updater_instantiation(self, mock_run):
        """Test MetadataUpdaterScheduler can be instantiated."""
        scheduler = MetadataUpdaterScheduler()
        assert scheduler is not None
        assert isinstance(scheduler, BaseScheduler)
        assert scheduler.running is True

    @patch(
        "ketchup_maintenance_fetcher.scheduler.fetch_and_store_maintenance_data",
        new_callable=AsyncMock,
    )
    def test_maintenance_fetcher_instantiation(self, mock_run):
        """Test MaintenanceFetcherScheduler can be instantiated."""
        scheduler = MaintenanceFetcherScheduler()
        assert scheduler is not None
        assert isinstance(scheduler, BaseScheduler)
        assert scheduler.running is True

    def test_pat_rotation_instantiation(self):
        """Test PatRotationScheduler can be instantiated."""
        scheduler = PatRotationScheduler()
        assert scheduler is not None
        assert isinstance(scheduler, BaseScheduler)
        assert scheduler.running is True


@pytest.mark.no_aws_required
class TestHealthFilePaths:
    """Test health file paths for backward compatibility."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_health_file_path(self, mock_run):
        """Test StatusUpdaterScheduler uses correct health file path."""
        scheduler = StatusUpdaterScheduler()
        # Health file: /tmp/scheduler_health
        assert scheduler.health_file == Path("/tmp/scheduler_health")
        # Last run file: /tmp/last_run (backward compatible override)
        assert scheduler.last_run_file == Path("/tmp/last_run")

    @patch("channel_metadata_updater.scheduler.run_metadata_update", new_callable=AsyncMock)
    def test_metadata_updater_health_file_path(self, mock_run):
        """Test MetadataUpdaterScheduler uses correct health file path."""
        scheduler = MetadataUpdaterScheduler()
        # Health file: /tmp/metadata_scheduler_health
        assert scheduler.health_file == Path("/tmp/metadata_scheduler_health")
        # Last run file: /tmp/metadata_scheduler_last_run
        assert scheduler.last_run_file == Path("/tmp/metadata_scheduler_last_run")

    @patch(
        "ketchup_maintenance_fetcher.scheduler.fetch_and_store_maintenance_data",
        new_callable=AsyncMock,
    )
    def test_maintenance_fetcher_health_file_path(self, mock_run):
        """Test MaintenanceFetcherScheduler uses correct health file path."""
        scheduler = MaintenanceFetcherScheduler()
        # Health file: /app/health/maintenance_fetcher_health
        assert scheduler.health_file == Path("/app/health/maintenance_fetcher_health")
        # Last run file: /app/health/maintenance_fetcher_last_run
        assert scheduler.last_run_file == Path("/app/health/maintenance_fetcher_last_run")

    def test_pat_rotation_health_file_path(self):
        """Test PatRotationScheduler uses correct health file path."""
        scheduler = PatRotationScheduler()
        # Health file: /tmp/pat_rotator_health
        assert scheduler.health_file == Path("/tmp/pat_rotator_health")
        # Last run file: /tmp/pat_rotator_last_run
        assert scheduler.last_run_file == Path("/tmp/pat_rotator_last_run")


@pytest.mark.no_aws_required
class TestSchedulerIntervals:
    """Test scheduler intervals are correct."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_interval(self, mock_run):
        """Test StatusUpdaterScheduler uses 55-minute interval."""
        scheduler = StatusUpdaterScheduler()
        assert scheduler.interval_minutes == 55
        assert scheduler.get_sleep_seconds() == 55 * 60  # 3300 seconds

    @patch("channel_metadata_updater.scheduler.run_metadata_update", new_callable=AsyncMock)
    def test_metadata_updater_interval(self, mock_run):
        """Test MetadataUpdaterScheduler uses 15-minute interval."""
        scheduler = MetadataUpdaterScheduler()
        assert scheduler.interval_minutes == 15
        assert scheduler.get_sleep_seconds() == 15 * 60  # 900 seconds

    @patch(
        "ketchup_maintenance_fetcher.scheduler.fetch_and_store_maintenance_data",
        new_callable=AsyncMock,
    )
    def test_maintenance_fetcher_time_based_scheduling(self, mock_run):
        """Test MaintenanceFetcherScheduler uses time-based scheduling."""
        scheduler = MaintenanceFetcherScheduler()
        # MaintenanceFetcherScheduler overrides get_sleep_seconds for daily scheduling at 1:30 AM UTC
        sleep_seconds = scheduler.get_sleep_seconds()
        # Should return a positive number of seconds until next 1:30 AM UTC
        assert sleep_seconds > 0
        # Should be at most ~24 hours (86400 seconds)
        assert sleep_seconds <= 86400

    def test_pat_rotation_interval(self):
        """Test PatRotationScheduler uses 24-hour interval."""
        scheduler = PatRotationScheduler()
        assert scheduler.interval_minutes == 1440  # 24 hours
        assert scheduler.get_sleep_seconds() == 1440 * 60  # 86400 seconds


@pytest.mark.no_aws_required
class TestRunOnStartConfiguration:
    """Test run_on_start configuration for each scheduler."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_run_on_start(self, mock_run):
        """Test StatusUpdaterScheduler runs on start."""
        scheduler = StatusUpdaterScheduler()
        assert scheduler.run_on_start is True

    @patch("channel_metadata_updater.scheduler.run_metadata_update", new_callable=AsyncMock)
    def test_metadata_updater_run_on_start(self, mock_run):
        """Test MetadataUpdaterScheduler runs on start."""
        scheduler = MetadataUpdaterScheduler()
        assert scheduler.run_on_start is True

    @patch(
        "ketchup_maintenance_fetcher.scheduler.fetch_and_store_maintenance_data",
        new_callable=AsyncMock,
    )
    def test_maintenance_fetcher_run_on_start(self, mock_run):
        """Test MaintenanceFetcherScheduler does not run on start by default."""
        scheduler = MaintenanceFetcherScheduler()
        # Default is False, controlled by env var KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START
        assert scheduler.run_on_start is False

    @patch.dict("os.environ", {"KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START": "true"})
    @patch(
        "ketchup_maintenance_fetcher.scheduler.fetch_and_store_maintenance_data",
        new_callable=AsyncMock,
    )
    def test_maintenance_fetcher_run_on_start_env_override(self, mock_run):
        """Test MaintenanceFetcherScheduler respects env var for run_on_start."""
        scheduler = MaintenanceFetcherScheduler()
        assert scheduler.run_on_start is True

    def test_pat_rotation_run_on_start(self):
        """Test PatRotationScheduler uses default run_on_start (True)."""
        scheduler = PatRotationScheduler()
        assert scheduler.run_on_start is True


@pytest.mark.no_aws_required
class TestSchedulerNames:
    """Test scheduler names are set correctly."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_name(self, mock_run):
        """Test StatusUpdaterScheduler has correct name."""
        scheduler = StatusUpdaterScheduler()
        assert scheduler.scheduler_name == "Status Updater Scheduler"

    @patch("channel_metadata_updater.scheduler.run_metadata_update", new_callable=AsyncMock)
    def test_metadata_updater_name(self, mock_run):
        """Test MetadataUpdaterScheduler has correct name."""
        scheduler = MetadataUpdaterScheduler()
        assert scheduler.scheduler_name == "Metadata Updater Scheduler"

    @patch(
        "ketchup_maintenance_fetcher.scheduler.fetch_and_store_maintenance_data",
        new_callable=AsyncMock,
    )
    def test_maintenance_fetcher_name(self, mock_run):
        """Test MaintenanceFetcherScheduler has correct name."""
        scheduler = MaintenanceFetcherScheduler()
        assert scheduler.scheduler_name == "Maintenance Fetcher Scheduler"

    def test_pat_rotation_name(self):
        """Test PatRotationScheduler uses default class name."""
        scheduler = PatRotationScheduler()
        # Uses default (class name) since no scheduler_name provided
        assert scheduler.scheduler_name == "PatRotationScheduler"


@pytest.mark.no_aws_required
class TestSignalHandling:
    """Test signal handling for graceful shutdown."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_signal_handling(self, mock_run):
        """Test StatusUpdaterScheduler responds to signals."""
        scheduler = StatusUpdaterScheduler()
        assert scheduler.running is True
        scheduler._signal_handler(15, None)  # SIGTERM
        assert scheduler.running is False

    @patch("channel_metadata_updater.scheduler.run_metadata_update", new_callable=AsyncMock)
    def test_metadata_updater_signal_handling(self, mock_run):
        """Test MetadataUpdaterScheduler responds to signals."""
        scheduler = MetadataUpdaterScheduler()
        assert scheduler.running is True
        scheduler._signal_handler(2, None)  # SIGINT
        assert scheduler.running is False


@pytest.mark.no_aws_required
class TestHealthFileUpdates:
    """Test health file update functionality."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_health_update(self, mock_run, tmp_path):
        """Test StatusUpdaterScheduler can update health file."""
        scheduler = StatusUpdaterScheduler()
        # Override health file to tmp_path for testing
        scheduler.health_file = tmp_path / "test_health"
        scheduler._update_health_status("idle")

        assert scheduler.health_file.exists()
        content = scheduler.health_file.read_text()
        assert ":idle" in content

    def test_pat_rotation_health_update(self, tmp_path):
        """Test PatRotationScheduler can update health file."""
        scheduler = PatRotationScheduler()
        # Override health file to tmp_path for testing
        scheduler.health_file = tmp_path / "test_health"
        scheduler._update_health_status("running")

        assert scheduler.health_file.exists()
        content = scheduler.health_file.read_text()
        assert ":running" in content


@pytest.mark.no_aws_required
class TestLastRunTracking:
    """Test last run file tracking."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    def test_status_updater_last_run_update(self, mock_run, tmp_path):
        """Test StatusUpdaterScheduler can update last run file."""
        scheduler = StatusUpdaterScheduler()
        # Override last run file to tmp_path for testing
        scheduler.last_run_file = tmp_path / "test_last_run"
        scheduler._update_last_run()

        assert scheduler.last_run_file.exists()
        content = scheduler.last_run_file.read_text()
        # Should be a unix timestamp
        assert content.isdigit()


@pytest.mark.no_aws_required
@pytest.mark.asyncio
class TestAsyncExecution:
    """Test async execution of scheduler tasks."""

    @patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock)
    async def test_status_updater_task_execution(self, mock_run, tmp_path):
        """Test StatusUpdaterScheduler can execute task."""
        scheduler = StatusUpdaterScheduler()
        scheduler.health_file = tmp_path / "health"
        scheduler.last_run_file = tmp_path / "last_run"

        await scheduler._execute_task_with_tracking()

        mock_run.assert_called_once()
        assert scheduler.health_file.exists()
        assert scheduler.last_run_file.exists()

    async def test_pat_rotation_task_execution(self, tmp_path):
        """Test PatRotationScheduler can execute task."""
        scheduler = PatRotationScheduler()
        scheduler.health_file = tmp_path / "health"
        scheduler.last_run_file = tmp_path / "last_run"

        await scheduler._execute_task_with_tracking()

        assert scheduler.health_file.exists()
        assert scheduler.last_run_file.exists()
        assert ":idle" in scheduler.health_file.read_text()


@pytest.mark.no_aws_required
class TestAllSchedulersInheritFromBaseScheduler:
    """Verify all migrated schedulers properly inherit from BaseScheduler."""

    def test_all_schedulers_have_required_methods(self):
        """Test all schedulers have methods from BaseScheduler."""
        required_methods = [
            "start",
            "run_task",
            "get_sleep_seconds",
            "_signal_handler",
            "_update_health_status",
            "_update_last_run",
            "_execute_task_with_tracking",
        ]

        scheduler_classes = [
            StatusUpdaterScheduler,
            MetadataUpdaterScheduler,
            MaintenanceFetcherScheduler,
            PatRotationScheduler,
        ]

        for cls in scheduler_classes:
            for method in required_methods:
                assert hasattr(cls, method), f"{cls.__name__} missing method {method}"

    def test_all_schedulers_have_required_attributes(self):
        """Test all scheduler instances have required attributes."""
        required_attrs = [
            "running",
            "health_file",
            "last_run_file",
            "interval_minutes",
            "run_on_start",
            "scheduler_name",
            "logger",
        ]

        # Create instances with mocked dependencies
        with patch("ketchup_status_updater.scheduler.run_auto_status", new_callable=AsyncMock):
            with patch(
                "channel_metadata_updater.scheduler.run_metadata_update", new_callable=AsyncMock
            ):
                with patch(
                    "ketchup_maintenance_fetcher.scheduler.fetch_and_store_maintenance_data",
                    new_callable=AsyncMock,
                ):
                    schedulers = [
                        StatusUpdaterScheduler(),
                        MetadataUpdaterScheduler(),
                        MaintenanceFetcherScheduler(),
                        PatRotationScheduler(),
                    ]

                    for scheduler in schedulers:
                        for attr in required_attrs:
                            assert hasattr(
                                scheduler, attr
                            ), f"{scheduler.__class__.__name__} missing attr {attr}"
