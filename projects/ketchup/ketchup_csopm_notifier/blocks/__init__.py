"""
CSOPM Notifier Block Kit Builders.

This package re-exports Block Kit message builders from the shared packages/
location for backward compatibility.

The actual implementation lives in packages/slack/csopm/blocks.py.
"""

from packages.slack.csopm.blocks import CSOPMNotificationBlocks

__all__ = ["CSOPMNotificationBlocks"]
