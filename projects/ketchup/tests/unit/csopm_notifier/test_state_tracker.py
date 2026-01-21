#!/usr/bin/env python3
"""
DEPRECATED: CSOPMStateTracker tests have been moved.

The CSOPMStateTracker tests have been relocated to align with the new package structure:
- Old location: tests/unit/csopm_notifier/test_state_tracker.py
- New location: tests/unit/slack/csopm/test_state.py

This file is kept for backwards compatibility and re-exports tests from the new location.
Run tests using: python -m pytest tests/unit/slack/csopm/test_state.py
"""

# Re-export all test classes from the new location for backwards compatibility
from tests.unit.slack.csopm.test_state import (
    MockDynamoDBAsyncClient,
    TestCSOPMStateTrackerCreateNotificationRecord,
    TestCSOPMStateTrackerDynamoDBTypeDescriptors,
    TestCSOPMStateTrackerGetAllActiveNotifications,
    TestCSOPMStateTrackerGetNotificationRecord,
    TestCSOPMStateTrackerGetPendingNotifications,
    TestCSOPMStateTrackerHandleReassignment,
    TestCSOPMStateTrackerIncrementPingCount,
    TestCSOPMStateTrackerItemParsing,
    TestCSOPMStateTrackerKeyGeneration,
    TestCSOPMStateTrackerProtocolCompliance,
    TestCSOPMStateTrackerRecordFollowup,
    TestCSOPMStateTrackerReminderMethods,
    TestCSOPMStateTrackerUpdateNotificationStatus,
)

__all__ = [
    "MockDynamoDBAsyncClient",
    "TestCSOPMStateTrackerProtocolCompliance",
    "TestCSOPMStateTrackerKeyGeneration",
    "TestCSOPMStateTrackerItemParsing",
    "TestCSOPMStateTrackerGetNotificationRecord",
    "TestCSOPMStateTrackerCreateNotificationRecord",
    "TestCSOPMStateTrackerUpdateNotificationStatus",
    "TestCSOPMStateTrackerIncrementPingCount",
    "TestCSOPMStateTrackerReminderMethods",
    "TestCSOPMStateTrackerGetPendingNotifications",
    "TestCSOPMStateTrackerRecordFollowup",
    "TestCSOPMStateTrackerGetAllActiveNotifications",
    "TestCSOPMStateTrackerHandleReassignment",
    "TestCSOPMStateTrackerDynamoDBTypeDescriptors",
]

if __name__ == "__main__":
    import unittest

    unittest.main()
