#!/usr/bin/env python3
"""
Integration tests for the unified scheduler architecture.

Tests verify:
1. TaskConfig classes can be created and validated
2. Task handler functions can be imported
3. UnifiedSchedulerEngine can be instantiated
4. TaskRegistry properly manages tasks
5. Health monitoring functionality

Note: Legacy BaseScheduler classes (StatusUpdaterScheduler, PatRotationScheduler)
were removed as dead code - production uses TaskRegistry + TaskConfig pattern.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Import core unified scheduler components
from ketchup_unified_scheduler.engine import UnifiedSchedulerEngine
from ketchup_unified_scheduler.health_monitor import PerTaskHealthMonitor
from ketchup_unified_scheduler.task_config import TaskConfig
from ketchup_unified_scheduler.task_registry import TaskRegistry

# Import task configs and handlers
from ketchup_unified_scheduler.tasks.maintenance_fetch_task import (
    get_maintenance_fetch_task_config,
    maintenance_fetch_task,
)
from ketchup_unified_scheduler.tasks.metadata_update_task import (
    get_metadata_update_task_config,
    metadata_update_task,
)

# Import BaseScheduler for reference
from packages.core.schedulers import BaseScheduler

pytestmark = pytest.mark.no_aws_required


class TestTaskConfigValidation:
    """Test TaskConfig dataclass validation and properties."""

    def test_interval_based_task_config(self):
        """Test creating an interval-based task config."""
        config = TaskConfig(
            name="test_task",
            handler=AsyncMock(),
            interval_minutes=15,
        )
        assert config.name == "test_task"
        assert config.interval_minutes == 15
        assert config.is_interval_based is True
        assert config.is_time_based is False

    def test_time_based_task_config(self):
        """Test creating a time-based task config."""
        config = TaskConfig(
            name="test_task",
            handler=AsyncMock(),
            schedule_time="01:30",
        )
        assert config.name == "test_task"
        assert config.schedule_time == "01:30"
        assert config.is_interval_based is False
        assert config.is_time_based is True

    def test_task_config_requires_schedule(self):
        """Test that TaskConfig requires either interval or time."""
        with pytest.raises(ValueError, match="must specify either"):
            TaskConfig(name="test", handler=AsyncMock())

    def test_task_config_rejects_both_schedules(self):
        """Test that TaskConfig rejects both interval and time."""
        with pytest.raises(ValueError, match="cannot have both"):
            TaskConfig(
                name="test",
                handler=AsyncMock(),
                interval_minutes=15,
                schedule_time="01:30",
            )

    def test_task_config_validates_time_format(self):
        """Test that TaskConfig validates HH:MM format."""
        with pytest.raises(ValueError, match="HH:MM format"):
            TaskConfig(name="test", handler=AsyncMock(), schedule_time="invalid")

    def test_task_config_validates_positive_interval(self):
        """Test that TaskConfig requires positive interval."""
        with pytest.raises(ValueError, match="must be positive"):
            TaskConfig(name="test", handler=AsyncMock(), interval_minutes=0)


class TestTaskHandlerImports:
    """Test that task handler functions can be imported and have correct configs."""

    def test_metadata_update_task_import(self):
        """Test metadata_update_task can be imported."""
        assert metadata_update_task is not None
        assert callable(metadata_update_task)

    def test_metadata_update_task_config(self):
        """Test metadata update task config is correct."""
        config = get_metadata_update_task_config()
        assert config.name == "metadata_updater"
        assert config.interval_minutes == 15
        assert config.is_interval_based is True
        assert config.feature_flag == "KETCHUP_METADATA_UPDATER_FEATURE"

    def test_maintenance_fetch_task_import(self):
        """Test maintenance_fetch_task can be imported."""
        assert maintenance_fetch_task is not None
        assert callable(maintenance_fetch_task)

    def test_maintenance_fetch_task_config(self):
        """Test maintenance fetch task config is correct."""
        config = get_maintenance_fetch_task_config()
        assert config.name == "maintenance_fetcher"
        assert config.schedule_time == "01:30"
        assert config.is_time_based is True
        assert config.feature_flag == "KETCHUP_MAINTENANCE_FETCHER_ENABLED"


class TestTaskRegistry:
    """Test TaskRegistry functionality."""

    def test_registry_creation(self):
        """Test TaskRegistry can be created."""
        registry = TaskRegistry()
        assert registry is not None

    def test_registry_register_task(self):
        """Test registering a task with the registry."""
        registry = TaskRegistry()
        config = TaskConfig(
            name="test_task",
            handler=AsyncMock(),
            interval_minutes=10,
        )
        registry.register(config)
        assert "test_task" in registry

    def test_registry_get_task(self):
        """Test retrieving a task from the registry."""
        registry = TaskRegistry()
        config = TaskConfig(
            name="test_task",
            handler=AsyncMock(),
            interval_minutes=10,
        )
        registry.register(config)
        retrieved = registry.get_task("test_task")
        assert retrieved is not None
        assert retrieved.name == "test_task"

    def test_registry_list_tasks(self):
        """Test listing all tasks in registry."""
        registry = TaskRegistry()
        registry.register(TaskConfig(name="task1", handler=AsyncMock(), interval_minutes=10))
        registry.register(TaskConfig(name="task2", handler=AsyncMock(), interval_minutes=20))
        tasks = registry.list_tasks()
        assert len(tasks) == 2
        task_names = [t.name for t in tasks]
        assert "task1" in task_names
        assert "task2" in task_names


class TestUnifiedSchedulerEngine:
    """Test UnifiedSchedulerEngine functionality."""

    def test_engine_instantiation(self):
        """Test UnifiedSchedulerEngine can be instantiated."""
        registry = TaskRegistry()
        engine = UnifiedSchedulerEngine(registry)
        assert engine is not None
        assert engine.running is True

    def test_engine_with_health_monitor(self):
        """Test engine with custom health monitor."""
        registry = TaskRegistry()
        monitor = PerTaskHealthMonitor()
        engine = UnifiedSchedulerEngine(
            registry,
            task_health_monitor=monitor,
        )
        assert engine is not None

    def test_engine_health_file_path(self):
        """Test engine respects custom health file path."""
        registry = TaskRegistry()
        engine = UnifiedSchedulerEngine(
            registry,
            health_file_path="/tmp/test_health",
        )
        assert engine.health_file == Path("/tmp/test_health")


class TestPerTaskHealthMonitor:
    """Test PerTaskHealthMonitor functionality."""

    def test_health_monitor_creation(self):
        """Test PerTaskHealthMonitor can be created."""
        monitor = PerTaskHealthMonitor()
        assert monitor is not None

    def test_health_monitor_update_task_status(self):
        """Test updating task status."""
        monitor = PerTaskHealthMonitor()
        monitor.update_task_status("test_task", "success")
        status = monitor.get_task_status("test_task")
        assert status is not None
        assert status.get("status") == "success"

    def test_health_monitor_update_task_error(self):
        """Test updating task with error status."""
        monitor = PerTaskHealthMonitor()
        monitor.update_task_status("test_task", "error")
        status = monitor.get_task_status("test_task")
        assert status is not None
        assert status.get("status") == "error"

    def test_health_monitor_update_last_run(self):
        """Test updating last run timestamp."""
        monitor = PerTaskHealthMonitor()
        monitor.update_task_last_run("test_task")
        last_run = monitor.get_last_run("test_task")
        assert last_run is not None
        assert isinstance(last_run, int)


class TestBaseSchedulerExists:
    """Test that BaseScheduler is available for subclassing."""

    def test_basescheduler_import(self):
        """Test BaseScheduler can be imported from packages.core.schedulers."""
        assert BaseScheduler is not None
        assert hasattr(BaseScheduler, "start")
        assert hasattr(BaseScheduler, "run_task")
        assert hasattr(BaseScheduler, "get_sleep_seconds")


class TestUnifiedSchedulerIntegration:
    """Integration tests for the unified scheduler architecture."""

    def test_full_registry_with_all_tasks(self):
        """Test creating a registry with all production tasks."""
        registry = TaskRegistry()

        # Register metadata and maintenance tasks
        registry.register(get_metadata_update_task_config())
        registry.register(get_maintenance_fetch_task_config())

        # Use list_tasks() to get all registered tasks
        tasks = registry.list_tasks()
        task_names = [t.name for t in tasks]
        assert "metadata_updater" in task_names
        assert "maintenance_fetcher" in task_names

    def test_engine_with_full_registry(self):
        """Test engine with full task registry."""
        registry = TaskRegistry()
        registry.register(get_metadata_update_task_config())
        registry.register(get_maintenance_fetch_task_config())

        engine = UnifiedSchedulerEngine(registry)
        assert engine is not None
        assert engine.running is True
