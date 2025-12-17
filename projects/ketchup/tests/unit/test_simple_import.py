"""Simple test to debug import issues"""


def test_import_jira_reporter():
    """Test if we can import jira_reporter"""
    import ketchup_unified_scheduler.services.jira_reporter as jira_reporter

    assert jira_reporter is not None


def test_import_channel_monitor():
    """Test if we can import channel_monitor"""
    from ketchup_unified_scheduler.services.jira_reporter.channel_monitor import ChannelMonitor

    assert ChannelMonitor is not None
