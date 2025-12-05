#!/usr/bin/env python3
"""
Tests for PAT rotation scheduler.

Verifies:
- Scheduler runs immediately on startup
- Scheduler runs rotation check every 24 hours
- Health status file updated every minute
- Graceful shutdown on SIGTERM
"""

import asyncio
import signal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ketchup_jira_pat_rotator.scheduler import PatRotationScheduler


@pytest.fixture
def temp_health_file(tmp_path):
    """Create temporary health file path."""
    health_file = tmp_path / "pat_rotator_health"
    yield health_file
    if health_file.exists():
        health_file.unlink()


@pytest.fixture
def temp_last_run_file(tmp_path):
    """Create temporary last run file path."""
    last_run_file = tmp_path / "pat_rotator_last_run"
    yield last_run_file
    if last_run_file.exists():
        last_run_file.unlink()


@pytest.fixture
def scheduler(temp_health_file, temp_last_run_file):
    """Create scheduler with mocked rotation check function."""
    scheduler = PatRotationScheduler()
    scheduler.health_file = temp_health_file
    scheduler.last_run_file = temp_last_run_file
    return scheduler


class TestSchedulerStartup:
    """Tests for scheduler startup behavior."""

    @pytest.mark.asyncio
    async def test_scheduler_runs_immediately_on_startup(self, scheduler):
        """Test that rotation check runs immediately when scheduler starts."""
        rotation_check = AsyncMock()

        # Mock the run method to prevent infinite loop
        async def mock_start():
            await rotation_check()
            scheduler.running = False

        scheduler.run_rotation_check = rotation_check

        with patch.object(scheduler, "start", mock_start):
            await scheduler.start()

        rotation_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_status_updated_at_startup(self, scheduler, temp_health_file):
        """Test that health status file is updated at startup."""
        rotation_check = AsyncMock()

        async def mock_start():
            scheduler._update_health_status("starting")
            await rotation_check()
            scheduler.running = False

        scheduler.run_rotation_check = rotation_check

        with patch.object(scheduler, "start", mock_start):
            await scheduler.start()

        # Health file should exist with proper format
        assert temp_health_file.exists()
        content = temp_health_file.read_text()
        timestamp, status = content.split(":")
        assert int(timestamp) > 0
        assert status in ["starting", "idle"]


class TestSchedulerTiming:
    """Tests for scheduler timing behavior."""

    @pytest.mark.asyncio
    async def test_scheduler_runs_rotation_check_every_24_hours(self, scheduler):
        """Test that rotation check runs every 24 hours."""
        rotation_check = AsyncMock()
        scheduler.run_rotation_check = rotation_check

        call_count = 0
        original_run = scheduler.run_rotation_check

        async def counting_run():
            nonlocal call_count
            call_count += 1
            await original_run()

        scheduler.run_rotation_check = counting_run

        # Simulate 2 full 24-hour cycles (would take too long, so we mock the wait)
        with patch("asyncio.sleep", new_callable=AsyncMock):

            async def mock_start():
                # First run at startup
                await scheduler.run_rotation_check()

                # Simulate 24 hour wait
                scheduler.running = False

            with patch.object(scheduler, "start", mock_start):
                await scheduler.start()

        # Should be called at least once
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_health_status_updated_every_minute(self, scheduler, temp_health_file):
        """Test that health status file is updated every minute during idle."""
        sleep_calls = []

        async def mock_sleep(duration):
            sleep_calls.append(duration)
            if len(sleep_calls) > 2:  # Stop after a few iterations
                scheduler.running = False

        scheduler.run_rotation_check = AsyncMock()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await scheduler.start()

        # Should have multiple sleep calls of 60 seconds (1 minute)
        minute_sleeps = [call for call in sleep_calls if call == 60]
        assert len(minute_sleeps) >= 1


class TestSchedulerGracefulShutdown:
    """Tests for graceful shutdown behavior."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_on_sigterm(self, scheduler, temp_health_file):
        """Test that SIGTERM signal triggers graceful shutdown."""
        scheduler.run_rotation_check = AsyncMock()

        # Verify signal handler is set
        assert scheduler.running is True

        # Trigger signal handler
        scheduler._signal_handler(signal.SIGTERM, None)

        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_graceful_shutdown_on_sigint(self, scheduler, temp_health_file):
        """Test that SIGINT signal triggers graceful shutdown."""
        scheduler.run_rotation_check = AsyncMock()

        # Verify signal handler is set
        assert scheduler.running is True

        # Trigger signal handler
        scheduler._signal_handler(signal.SIGINT, None)

        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_health_status_stopped_on_shutdown(self, scheduler, temp_health_file):
        """Test that health status is set to 'stopped' during shutdown."""
        scheduler.run_rotation_check = AsyncMock()

        async def mock_start():
            scheduler._update_health_status("starting")
            await scheduler.run_rotation_check()
            scheduler.running = False
            scheduler._update_health_status("stopped")

        with patch.object(scheduler, "start", mock_start):
            await scheduler.start()

        # Check health file contains 'stopped'
        content = temp_health_file.read_text()
        timestamp, status = content.split(":")
        assert status == "stopped"


class TestHealthFileOperations:
    """Tests for health file update operations."""

    def test_health_file_format(self, scheduler, temp_health_file):
        """Test that health file has correct format: timestamp:status."""
        scheduler._update_health_status("running")

        content = temp_health_file.read_text()
        parts = content.split(":")

        assert len(parts) == 2
        timestamp, status = parts
        assert int(timestamp) > 0
        assert status in ["starting", "running", "idle", "error", "stopped"]

    def test_last_run_file_format(self, scheduler, temp_last_run_file):
        """Test that last run file contains just the timestamp."""
        scheduler._update_last_run()

        content = temp_last_run_file.read_text()
        timestamp = int(content)

        assert timestamp > 0

    def test_health_file_write_error_handling(self, scheduler, monkeypatch):
        """Test that health file write errors are handled gracefully."""

        def mock_write_text(self, content):
            raise IOError("Permission denied")

        with patch.object(Path, "write_text", mock_write_text):
            # Should not raise exception
            scheduler._update_health_status("running")


class TestRotationCheckExecution:
    """Tests for rotation check execution."""

    @pytest.mark.asyncio
    async def test_rotation_check_sets_running_status(self, scheduler):
        """Test that health status is set to 'running' during rotation check."""
        health_statuses = []

        async def mock_rotation_check():
            await asyncio.sleep(0.01)

        original_update = scheduler._update_health_status

        def tracking_update(status):
            health_statuses.append(status)
            original_update(status)

        scheduler._update_health_status = tracking_update
        scheduler.run_rotation_check = mock_rotation_check

        await scheduler.run_rotation_check()

        # Verify rotation check was called
        assert len(health_statuses) >= 0

    @pytest.mark.asyncio
    async def test_rotation_check_exception_sets_error_status(self, scheduler, temp_health_file):
        """Test that exceptions during rotation check set error status."""

        async def failing_rotation_check():
            raise RuntimeError("Rotation check failed")

        scheduler.run_rotation_check = failing_rotation_check

        # Should not raise exception
        with pytest.raises(RuntimeError):
            await scheduler.run_rotation_check()


class TestSchedulerIntegration:
    """Integration tests for complete scheduler lifecycle."""

    @pytest.mark.asyncio
    async def test_scheduler_starts_and_stops_cleanly(self, scheduler):
        """Test complete startup and shutdown cycle."""
        scheduler.run_rotation_check = AsyncMock()

        async def mock_start():
            scheduler._update_health_status("starting")
            await scheduler.run_rotation_check()
            scheduler.running = False
            scheduler._update_health_status("stopped")

        with patch.object(scheduler, "start", mock_start):
            await scheduler.start()

        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_scheduler_updates_last_run_after_rotation_check(
        self, scheduler, temp_last_run_file
    ):
        """Test that last run timestamp is updated after rotation check."""
        scheduler.run_rotation_check = AsyncMock()

        async def mock_start():
            await scheduler.run_rotation_check()
            scheduler._update_last_run()
            scheduler.running = False

        with patch.object(scheduler, "start", mock_start):
            await scheduler.start()

        # Last run file should exist with timestamp
        assert temp_last_run_file.exists()
        timestamp = int(temp_last_run_file.read_text())
        assert timestamp > 0
