"""
Tests for TaskRegistry and TaskConfig.

Verifies:
- TaskConfig validation for interval and time-based scheduling
- TaskRegistry register, get_task, list_tasks functionality
- Feature flag evaluation in get_enabled_tasks
"""

import os
from unittest.mock import patch

import pytest

from ketchup_unified_scheduler.task_config import TaskConfig
from ketchup_unified_scheduler.task_registry import TaskRegistry


class TestTaskConfigValidation:
    """Tests for TaskConfig validation."""

    def test_valid_interval_based_config(self):
        """Test creating a valid interval-based task config."""

        async def handler(container=None):
            pass

        config = TaskConfig(
            name="test_task",
            handler=handler,
            interval_minutes=15,
        )

        assert config.name == "test_task"
        assert config.interval_minutes == 15
        assert config.schedule_time is None
        assert config.is_interval_based is True
        assert config.is_time_based is False

    def test_valid_time_based_config(self):
        """Test creating a valid time-based task config."""

        async def handler(container=None):
            pass

        config = TaskConfig(
            name="test_task",
            handler=handler,
            schedule_time="01:30",
        )

        assert config.name == "test_task"
        assert config.schedule_time == "01:30"
        assert config.interval_minutes is None
        assert config.is_time_based is True
        assert config.is_interval_based is False

    def test_config_requires_scheduling(self):
        """Test that config requires either interval_minutes or schedule_time."""

        async def handler(container=None):
            pass

        with pytest.raises(
            ValueError, match="must specify either interval_minutes or schedule_time"
        ):
            TaskConfig(
                name="invalid_task",
                handler=handler,
            )

    def test_config_rejects_both_scheduling_modes(self):
        """Test that config rejects having both scheduling modes."""

        async def handler(container=None):
            pass

        with pytest.raises(ValueError, match="cannot have both interval_minutes and schedule_time"):
            TaskConfig(
                name="invalid_task",
                handler=handler,
                interval_minutes=15,
                schedule_time="01:30",
            )

    def test_config_rejects_non_positive_interval(self):
        """Test that config rejects zero or negative interval."""

        async def handler(container=None):
            pass

        with pytest.raises(ValueError, match="interval_minutes must be positive"):
            TaskConfig(
                name="invalid_task",
                handler=handler,
                interval_minutes=0,
            )

        with pytest.raises(ValueError, match="interval_minutes must be positive"):
            TaskConfig(
                name="invalid_task",
                handler=handler,
                interval_minutes=-10,
            )

    def test_config_validates_schedule_time_format(self):
        """Test that config validates schedule_time format."""

        async def handler(container=None):
            pass

        # Invalid formats - hour out of range
        with pytest.raises(ValueError, match="must be in HH:MM format"):
            TaskConfig(name="invalid", handler=handler, schedule_time="25:00")

        # Invalid formats - minute out of range
        with pytest.raises(ValueError, match="must be in HH:MM format"):
            TaskConfig(name="invalid", handler=handler, schedule_time="12:60")

        # Invalid formats - not a time string
        with pytest.raises(ValueError, match="must be in HH:MM format"):
            TaskConfig(name="invalid", handler=handler, schedule_time="invalid")

        # Invalid formats - missing separator
        with pytest.raises(ValueError, match="must be in HH:MM format"):
            TaskConfig(name="invalid", handler=handler, schedule_time="1230")

        # Valid single-digit hour should work (H:MM format is valid)
        config = TaskConfig(name="valid_single_digit", handler=handler, schedule_time="1:30")
        assert config.schedule_time == "1:30"

    def test_config_with_feature_flag(self):
        """Test config with feature flag."""

        async def handler(container=None):
            pass

        config = TaskConfig(
            name="test_task",
            handler=handler,
            interval_minutes=15,
            feature_flag="TEST_FEATURE_FLAG",
        )

        assert config.feature_flag == "TEST_FEATURE_FLAG"

    def test_config_with_enabled_false(self):
        """Test config with enabled set to False."""

        async def handler(container=None):
            pass

        config = TaskConfig(
            name="test_task",
            handler=handler,
            interval_minutes=15,
            enabled=False,
        )

        assert config.enabled is False


class TestTaskRegistryBasicOperations:
    """Tests for TaskRegistry basic operations."""

    def test_register_and_get_task(self):
        """Test registering and retrieving a task."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        config = TaskConfig(name="test_task", handler=handler, interval_minutes=15)

        registry.register(config)

        retrieved = registry.get_task("test_task")
        assert retrieved is config

    def test_register_duplicate_raises_error(self):
        """Test that registering duplicate task name raises error."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        config = TaskConfig(name="test_task", handler=handler, interval_minutes=15)

        registry.register(config)

        with pytest.raises(ValueError, match="is already registered"):
            registry.register(config)

    def test_get_task_not_found_raises_error(self):
        """Test that getting non-existent task raises error."""
        registry = TaskRegistry()

        with pytest.raises(KeyError, match="is not registered"):
            registry.get_task("non_existent")

    def test_list_tasks_returns_all_tasks(self):
        """Test listing all registered tasks."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        config1 = TaskConfig(name="task1", handler=handler, interval_minutes=15)
        config2 = TaskConfig(name="task2", handler=handler, schedule_time="01:30")

        registry.register(config1)
        registry.register(config2)

        tasks = registry.list_tasks()
        assert len(tasks) == 2
        assert config1 in tasks
        assert config2 in tasks

    def test_unregister_task(self):
        """Test unregistering a task."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        config = TaskConfig(name="test_task", handler=handler, interval_minutes=15)

        registry.register(config)
        assert "test_task" in registry

        result = registry.unregister("test_task")
        assert result is True
        assert "test_task" not in registry

    def test_unregister_non_existent_returns_false(self):
        """Test that unregistering non-existent task returns False."""
        registry = TaskRegistry()
        result = registry.unregister("non_existent")
        assert result is False

    def test_clear_removes_all_tasks(self):
        """Test clearing all tasks."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(TaskConfig(name="task1", handler=handler, interval_minutes=15))
        registry.register(TaskConfig(name="task2", handler=handler, interval_minutes=30))

        assert len(registry) == 2

        registry.clear()

        assert len(registry) == 0

    def test_len_returns_task_count(self):
        """Test __len__ returns correct count."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        assert len(registry) == 0

        registry.register(TaskConfig(name="task1", handler=handler, interval_minutes=15))
        assert len(registry) == 1

        registry.register(TaskConfig(name="task2", handler=handler, interval_minutes=30))
        assert len(registry) == 2

    def test_contains_checks_task_name(self):
        """Test __contains__ checks task name."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(TaskConfig(name="test_task", handler=handler, interval_minutes=15))

        assert "test_task" in registry
        assert "non_existent" not in registry


class TestTaskRegistryFeatureFlags:
    """Tests for TaskRegistry feature flag evaluation."""

    def test_get_enabled_tasks_without_feature_flags(self):
        """Test get_enabled_tasks returns all enabled tasks without feature flags."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(TaskConfig(name="task1", handler=handler, interval_minutes=15))
        registry.register(TaskConfig(name="task2", handler=handler, interval_minutes=30))

        enabled = registry.get_enabled_tasks()
        assert len(enabled) == 2

    def test_get_enabled_tasks_respects_enabled_flag(self):
        """Test get_enabled_tasks respects enabled=False."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(
            TaskConfig(name="enabled_task", handler=handler, interval_minutes=15, enabled=True)
        )
        registry.register(
            TaskConfig(name="disabled_task", handler=handler, interval_minutes=30, enabled=False)
        )

        enabled = registry.get_enabled_tasks()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled_task"

    def test_get_enabled_tasks_with_feature_flag_true(self):
        """Test get_enabled_tasks when feature flag is true."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(
            TaskConfig(
                name="flagged_task",
                handler=handler,
                interval_minutes=15,
                feature_flag="TEST_FEATURE",
            )
        )

        with patch.dict(os.environ, {"TEST_FEATURE": "true"}):
            enabled = registry.get_enabled_tasks()
            assert len(enabled) == 1
            assert enabled[0].name == "flagged_task"

    def test_get_enabled_tasks_with_feature_flag_false(self):
        """Test get_enabled_tasks when feature flag is false."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(
            TaskConfig(
                name="flagged_task",
                handler=handler,
                interval_minutes=15,
                feature_flag="TEST_FEATURE",
            )
        )

        with patch.dict(os.environ, {"TEST_FEATURE": "false"}):
            enabled = registry.get_enabled_tasks()
            assert len(enabled) == 0

    def test_get_enabled_tasks_feature_flag_defaults_to_true(self):
        """Test that missing feature flag defaults to true (backward compatibility)."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        registry.register(
            TaskConfig(
                name="flagged_task",
                handler=handler,
                interval_minutes=15,
                feature_flag="NONEXISTENT_FEATURE",
            )
        )

        # Ensure the env var doesn't exist
        with patch.dict(os.environ, {}, clear=True):
            # Force clear the specific key if it exists
            os.environ.pop("NONEXISTENT_FEATURE", None)
            enabled = registry.get_enabled_tasks()
            assert len(enabled) == 1

    def test_get_enabled_tasks_mixed_scenarios(self):
        """Test get_enabled_tasks with mixed enabled states and feature flags."""

        async def handler(container=None):
            pass

        registry = TaskRegistry()
        # No flag - enabled
        registry.register(TaskConfig(name="no_flag", handler=handler, interval_minutes=15))
        # Flag true - enabled
        registry.register(
            TaskConfig(
                name="flag_true", handler=handler, interval_minutes=15, feature_flag="TRUE_FLAG"
            )
        )
        # Flag false - disabled
        registry.register(
            TaskConfig(
                name="flag_false", handler=handler, interval_minutes=15, feature_flag="FALSE_FLAG"
            )
        )
        # Enabled=False - disabled
        registry.register(
            TaskConfig(name="static_disabled", handler=handler, interval_minutes=15, enabled=False)
        )

        with patch.dict(os.environ, {"TRUE_FLAG": "true", "FALSE_FLAG": "false"}):
            enabled = registry.get_enabled_tasks()
            names = [t.name for t in enabled]
            assert "no_flag" in names
            assert "flag_true" in names
            assert "flag_false" not in names
            assert "static_disabled" not in names
            assert len(enabled) == 2
