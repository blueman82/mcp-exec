"""Tests for message formatter (per-message embedding)."""

from packages.agent.embeddings.chunker import format_messages


class TestFormatMessages:
    def test_empty_messages(self):
        assert format_messages([], "C123") == []

    def test_single_message(self):
        msgs = [{"user": "U1", "text": "hello", "ts": "1.0"}]
        docs = format_messages(msgs, "C123")
        assert len(docs) == 1
        assert docs[0].channel_id == "C123"
        assert docs[0].doc_id == "C123:1.0"
        assert "<@U1>" in docs[0].text
        assert "hello" in docs[0].text

    def test_multiple_messages(self):
        msgs = [
            {"user": "U1", "text": "hello", "ts": "1.0"},
            {"user": "U2", "text": "hi there", "ts": "2.0"},
            {"user": "U1", "text": "how are you", "ts": "3.0"},
        ]
        docs = format_messages(msgs, "C123")
        # One document per message — no windowing
        assert len(docs) == 3
        assert docs[0].user_id == "U1"
        assert docs[1].user_id == "U2"
        assert docs[2].user_id == "U1"

    def test_skips_empty_text(self):
        msgs = [
            {"user": "U1", "text": "hello", "ts": "1.0"},
            {"user": "U2", "text": "", "ts": "2.0"},
            {"user": "U3", "text": "   ", "ts": "3.0"},
        ]
        docs = format_messages(msgs, "C123")
        assert len(docs) == 1

    def test_doc_id_format(self):
        msgs = [{"user": "U1", "text": "test", "ts": "100.500"}]
        docs = format_messages(msgs, "CTEST")
        assert docs[0].doc_id == "CTEST:100.500"

    def test_thread_detection(self):
        msgs = [
            {"user": "U1", "text": "parent", "ts": "1.0", "thread_ts": "1.0", "reply_count": 3},
            {"user": "U2", "text": "reply", "ts": "2.0"},
        ]
        docs = format_messages(msgs, "C123")
        assert docs[0].has_thread_replies is True
        assert docs[1].has_thread_replies is False

    def test_includes_timestamp_in_text(self):
        msgs = [{"user": "U1", "text": "hello world", "ts": "1234.5678"}]
        docs = format_messages(msgs, "C123")
        assert "[1970-01-01 00:20 UTC]" in docs[0].text

    def test_includes_user_in_text(self):
        msgs = [{"user": "U42", "text": "testing", "ts": "1.0"}]
        docs = format_messages(msgs, "C123")
        assert "<@U42>" in docs[0].text
