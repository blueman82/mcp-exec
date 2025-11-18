"""Simple test to debug import issues"""


def test_import_jira_reporter():
    """Test if we can import jira_reporter"""
    import jira_reporter

    assert jira_reporter is not None


def test_import_channel_monitor():
    """Test if we can import channel_monitor"""
    from jira_reporter.channel_monitor import ChannelMonitor

    assert ChannelMonitor is not None
