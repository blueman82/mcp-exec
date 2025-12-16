"""
Tests for UnifiedSchedulerEngine.

Verifies:
- Concurrent task execution
- Error isolation between tasks
- Graceful shutdown handling
- Health status updates
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ketchup_unified_scheduler.engine import UnifiedSchedulerEngine
from ketchup_unified_scheduler.task_config import TaskConfig
from ketchup_unified_scheduler.task_registry import TaskRegistry


class TestEngineInitialization:
    """Tests for engine initialization."""

    def test_engine_initializes_with_registry(self):
        """Test engine initializes with registry and default settings."""
        registry = TaskRegistry()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(registry=registry, health_file_path=health_file)

        assert engine._registry is registry
        assert engine.running is True
        assert engine._container is None
        assert engine.health_file == Path(health_file)

    def test_engine_initializes_with_container(self):
        """Test engine initializes with optional container."""
        registry = TaskRegistry()
        container = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(
            registry=registry, container=container, health_file_path=health_file
        )

        assert engine._container is container


class TestEngineHealthStatus:
    """Tests for engine health status updates."""

    def test_update_health_status_writes_file(self):
        """Test that health status is written to file."""
        registry = TaskRegistry()

        with tempfile.TemporaryDirectory() as tmpdir:
            health_file = Path(tmpdir) / "health"
            engine = UnifiedSchedulerEngine(registry=registry, health_file_path=str(health_file))

            engine._update_health_status("running")

            assert health_file.exists()
            content = health_file.read_text()
            assert ":running" in content

    def test_update_health_status_creates_parent_dirs(self):
        """Test that health status creates parent directories."""
        registry = TaskRegistry()

        with tempfile.TemporaryDirectory() as tmpdir:
            health_file = Path(tmpdir) / "subdir" / "health"
            engine = UnifiedSchedulerEngine(registry=registry, health_file_path=str(health_file))

            engine._update_health_status("starting")

            assert health_file.exists()


class TestEngineSleeCalculation:
    """Tests for sleep duration calculation."""

    def test_calculate_sleep_for_interval_based_task(self):
        """Test sleep calculation for interval-based tasks."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        engine = UnifiedSchedulerEngine(registry=registry)

        config = TaskConfig(name="interval_task", handler=handler, interval_minutes=15)

        sleep_seconds = engine._calculate_sleep_seconds(config)
        assert sleep_seconds == 15 * 60  # 900 seconds

    def test_calculate_sleep_for_time_based_task(self):
        """Test sleep calculation for time-based tasks returns positive value."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        engine = UnifiedSchedulerEngine(registry=registry)

        config = TaskConfig(name="time_task", handler=handler, schedule_time="01:30")

        sleep_seconds = engine._calculate_sleep_seconds(config)
        # Should return a positive number of seconds
        assert sleep_seconds > 0
        # Should be less than 24 hours (86400 seconds)
        assert sleep_seconds <= 86400


class TestEngineConcurrentExecution:
    """Tests for concurrent task execution."""

    @pytest.mark.asyncio
    async def test_engine_runs_multiple_tasks_concurrently(self):
        """Test that multiple tasks run concurrently."""
        execution_log = []

        async def task1_handler(container=None):
            execution_log.append(("task1", "start"))
            await asyncio.sleep(0.01)
            execution_log.append(("task1", "end"))

        async def task2_handler(container=None):
            execution_log.append(("task2", "start"))
            await asyncio.sleep(0.01)
            execution_log.append(("task2", "end"))

        registry = TaskRegistry()
        registry.register(TaskConfig(name="task1", handler=task1_handler, interval_minutes=60))
        registry.register(TaskConfig(name="task2", handler=task2_handler, interval_minutes=60))

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(registry=registry, health_file_path=health_file)

        # Start engine and stop after a short time
        async def stop_engine():
            await asyncio.sleep(0.1)
            engine.running = False

        await asyncio.gather(
            engine.start(),
            stop_engine(),
        )

        # Both tasks should have started
        assert ("task1", "start") in execution_log
        assert ("task2", "start") in execution_log

    @pytest.mark.asyncio
    async def test_engine_handles_no_enabled_tasks(self):
        """Test engine handles case with no enabled tasks."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(
            TaskConfig(name="disabled", handler=handler, interval_minutes=15, enabled=False)
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(registry=registry, health_file_path=health_file)

        async def stop_engine():
            await asyncio.sleep(0.05)
            engine.running = False

        await asyncio.gather(
            engine.start(),
            stop_engine(),
        )

        # Should have set idle status
        content = Path(health_file).read_text()
        # Final status should be stopped
        assert ":stopped" in content or ":idle" in content


class TestEngineErrorIsolation:
    """Tests for error isolation between tasks."""

    @pytest.mark.asyncio
    async def test_task_error_does_not_stop_other_tasks(self):
        """Test that one task's error doesn't stop other tasks."""
        task1_runs = []
        task2_runs = []

        async def failing_handler(container=None):
            task1_runs.append(True)
            raise ValueError("Task 1 intentional failure")

        async def succeeding_handler(container=None):
            task2_runs.append(True)

        registry = TaskRegistry()
        registry.register(
            TaskConfig(name="failing_task", handler=failing_handler, interval_minutes=60)
        )
        registry.register(
            TaskConfig(name="succeeding_task", handler=succeeding_handler, interval_minutes=60)
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(registry=registry, health_file_path=health_file)

        async def stop_engine():
            await asyncio.sleep(0.1)
            engine.running = False

        # Should not raise despite one task failing
        await asyncio.gather(
            engine.start(),
            stop_engine(),
        )

        # Both tasks should have been executed at least once
        assert len(task1_runs) >= 1
        assert len(task2_runs) >= 1


class TestEngineGracefulShutdown:
    """Tests for graceful shutdown handling."""

    @pytest.mark.asyncio
    async def test_signal_handler_sets_running_false(self):
        """Test that signal handler sets running to False."""
        registry = TaskRegistry()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(registry=registry, health_file_path=health_file)

        assert engine.running is True

        # Simulate signal
        engine._signal_handler(15, None)  # SIGTERM

        assert engine.running is False

    @pytest.mark.asyncio
    async def test_graceful_shutdown_stops_all_tasks(self):
        """Test that graceful shutdown stops all running tasks."""
        task_stopped = []

        async def long_running_handler(container=None):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                task_stopped.append(True)
                raise

        registry = TaskRegistry()
        registry.register(
            TaskConfig(name="long_task", handler=long_running_handler, interval_minutes=60)
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(registry=registry, health_file_path=health_file)

        async def stop_engine():
            await asyncio.sleep(0.05)
            engine.running = False

        await asyncio.gather(
            engine.start(),
            stop_engine(),
        )

        # Health file should show stopped
        content = Path(health_file).read_text()
        assert ":stopped" in content


class TestEngineTaskStatus:
    """Tests for task status reporting."""

    @pytest.mark.asyncio
    async def test_get_task_status_shows_running_tasks(self):
        """Test get_task_status shows status of managed tasks."""

        async def slow_handler(container=None):
            await asyncio.sleep(10)

        registry = TaskRegistry()
        registry.register(TaskConfig(name="slow_task", handler=slow_handler, interval_minutes=60))

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(registry=registry, health_file_path=health_file)

        async def check_and_stop():
            await asyncio.sleep(0.05)
            status = engine.get_task_status()
            assert "slow_task" in status
            assert status["slow_task"] == "running"
            engine.running = False

        await asyncio.gather(
            engine.start(),
            check_and_stop(),
        )


class TestEngineTaskExecution:
    """Tests for task execution with container."""

    @pytest.mark.asyncio
    async def test_task_receives_container(self):
        """Test that task handler receives container parameter."""
        received_container = []

        async def handler(container=None):
            received_container.append(container)

        registry = TaskRegistry()
        registry.register(TaskConfig(name="test_task", handler=handler, interval_minutes=60))

        mock_container = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            health_file = f.name

        engine = UnifiedSchedulerEngine(
            registry=registry, container=mock_container, health_file_path=health_file
        )

        async def stop_engine():
            await asyncio.sleep(0.05)
            engine.running = False

        await asyncio.gather(
            engine.start(),
            stop_engine(),
        )

        # Task should have received the container
        assert len(received_container) >= 1
        assert received_container[0] is mock_container
