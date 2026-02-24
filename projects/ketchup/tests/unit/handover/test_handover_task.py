"""
Unit tests for handover summary task configuration.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from ketchup_unified_scheduler.tasks.handover_summary_task import (
    get_handover_task_configs,
    handover_summary_task,
)


class TestHandoverTask:
    """Test cases for handover task configuration"""

    def test_get_handover_task_configs_returns_correct_count_default(self):
        """Test default schedule produces two task configs"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "09:00,17:00"}):
            # Re-import to pick up env
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            configs = get_handover_task_configs()

            assert len(configs) == 2

    def test_get_handover_task_configs_single_time_produces_single_config(self):
        """Test single schedule time produces single task config"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "14:00"}):
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            import ketchup_unified_scheduler.tasks.handover_summary_task as task_module

            importlib.reload(task_module)

            configs = task_module.get_handover_task_configs()

            assert len(configs) == 1

    def test_get_handover_task_configs_multiple_times_produces_multiple_configs(self):
        """Test multiple schedule times produce multiple task configs"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "08:00,12:00,16:00,20:00"}):
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            import ketchup_unified_scheduler.tasks.handover_summary_task as task_module

            importlib.reload(task_module)

            configs = task_module.get_handover_task_configs()

            assert len(configs) == 4

    def test_each_config_has_unique_name(self):
        """Test each task config has unique name with index"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "09:00,17:00"}):
            # Re-import to pick up env
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            configs = get_handover_task_configs()

            assert configs[0].name == "handover_0"
            assert configs[1].name == "handover_1"

    def test_all_configs_share_same_handler(self):
        """Test all task configs use the same handler function"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "09:00,17:00,21:00"}):
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            import ketchup_unified_scheduler.tasks.handover_summary_task as task_module

            importlib.reload(task_module)

            configs = task_module.get_handover_task_configs()

            assert all(config.handler == task_module.handover_summary_task for config in configs)

    def test_all_configs_share_same_feature_flag(self):
        """Test all task configs use the same feature flag"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "09:00,17:00"}):
            # Re-import to pick up env
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            configs = get_handover_task_configs()

            assert all(
                config.feature_flag == "KETCHUP_HANDOVER_SUMMARY_ENABLED" for config in configs
            )

    def test_all_configs_enabled_by_default(self):
        """Test all task configs are enabled by default"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "09:00,17:00"}):
            # Re-import to pick up env
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            configs = get_handover_task_configs()

            assert all(config.enabled is True for config in configs)

    def test_configs_have_correct_schedule_times(self):
        """Test task configs have correct schedule times"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "08:30,14:45"}):
            import importlib

            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            import ketchup_unified_scheduler.tasks.handover_summary_task as task_module

            importlib.reload(task_module)

            configs = task_module.get_handover_task_configs()

            assert configs[0].schedule_time == "08:30"
            assert configs[1].schedule_time == "14:45"

    @pytest.mark.asyncio
    async def test_handover_summary_task_calls_generator(self):
        """Test handover_summary_task calls generate_and_post_handover"""
        mock_container = AsyncMock()

        with patch(
            "ketchup_unified_scheduler.tasks.handover_summary_task.generate_and_post_handover"
        ) as mock_generator:
            mock_generator.return_value = {"status": "success", "channel_count": 3}

            await handover_summary_task(container=mock_container)

            mock_generator.assert_called_once_with(container=mock_container)

    @pytest.mark.asyncio
    async def test_handover_summary_task_raises_on_error_status(self):
        """Test handover_summary_task raises RuntimeError on error status"""
        mock_container = AsyncMock()

        with patch(
            "ketchup_unified_scheduler.tasks.handover_summary_task.generate_and_post_handover"
        ) as mock_generator:
            mock_generator.return_value = {
                "status": "error",
                "message": "Test error message",
            }

            with pytest.raises(RuntimeError, match="Handover summary generation failed"):
                await handover_summary_task(container=mock_container)

    @pytest.mark.asyncio
    async def test_handover_summary_task_succeeds_on_disabled_status(self):
        """Test handover_summary_task succeeds when feature is disabled"""
        mock_container = AsyncMock()

        with patch(
            "ketchup_unified_scheduler.tasks.handover_summary_task.generate_and_post_handover"
        ) as mock_generator:
            mock_generator.return_value = {"status": "disabled"}

            # Should not raise
            await handover_summary_task(container=mock_container)
