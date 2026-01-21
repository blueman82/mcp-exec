"""
csopm package

Shared CSOPM (Customer Service Operations and Performance Management) components
for notifications and state tracking. Used by both ketchup-app (interactive handlers)
and ketchup_csopm_notifier service (scheduled notifications).

Components:
- CSOPMNotificationBlocks: Slack Block Kit components for notifications
- CSOPMStateTracker: DynamoDB state persistence for notification tracking
- CSOPMButtonActionHandler: Handler for interactive button actions
"""

from packages.slack.csopm.actions import CSOPMButtonActionHandler
from packages.slack.csopm.blocks import CSOPMNotificationBlocks
from packages.slack.csopm.state import CSOPMStateTracker

__all__ = [
    "CSOPMNotificationBlocks",
    "CSOPMStateTracker",
    "CSOPMButtonActionHandler",
]
