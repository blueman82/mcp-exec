"""
Unit tests for handover configuration module.
"""

import os
from unittest.mock import patch

import pytest


class TestHandoverConfig:
    """Test cases for handover configuration"""

    def test_default_schedule_times_parsing(self):
        """Test default schedule times are parsed correctly"""
        with patch.dict(os.environ, {}, clear=True):
            # Re-import module to trigger default parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_SCHEDULE_TIMES == ["09:00", "17:00"]

    def test_custom_schedule_times_env_override(self):
        """Test custom schedule times from environment variable"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "08:00,12:00,20:00"}):
            # Re-import module to trigger env parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_SCHEDULE_TIMES == ["08:00", "12:00", "20:00"]

    def test_single_schedule_time_produces_one_element_list(self):
        """Test single schedule time produces one-element list"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": "14:30"}):
            # Re-import module to trigger env parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_SCHEDULE_TIMES == ["14:30"]

    def test_schedule_times_strips_whitespace(self):
        """Test schedule times parsing strips whitespace"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SCHEDULE_TIMES": " 09:00 , 17:00 "}):
            # Re-import module to trigger env parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_SCHEDULE_TIMES == ["09:00", "17:00"]

    def test_target_channel_default(self):
        """Test target channel has correct default value"""
        with patch.dict(os.environ, {}, clear=True):
            # Re-import module to trigger default parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_TARGET_CHANNEL == "C03PWLW9P5H"

    def test_target_channel_env_override(self):
        """Test target channel can be overridden via environment"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_TARGET_CHANNEL": "C12345678"}):
            # Re-import module to trigger env parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_TARGET_CHANNEL == "C12345678"

    def test_message_window_hours_default(self):
        """Test message window hours has correct default value"""
        with patch.dict(os.environ, {}, clear=True):
            # Re-import module to trigger default parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_MESSAGE_WINDOW_HOURS == 12

    def test_message_window_hours_env_override(self):
        """Test message window hours can be overridden via environment"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_MESSAGE_WINDOW_HOURS": "24"}):
            # Re-import module to trigger env parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert config_module.HANDOVER_MESSAGE_WINDOW_HOURS == 24

    def test_message_window_hours_type_conversion(self):
        """Test message window hours is converted to integer"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_MESSAGE_WINDOW_HOURS": "6"}):
            # Re-import module to trigger env parsing
            import importlib
            import packages.core.config.handover_config as config_module

            importlib.reload(config_module)

            assert isinstance(config_module.HANDOVER_MESSAGE_WINDOW_HOURS, int)
            assert config_module.HANDOVER_MESSAGE_WINDOW_HOURS == 6
