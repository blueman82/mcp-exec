"""Tests for re-evaluation queue CRUD queries."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from bravo.db import queries


@pytest.fixture()
def _mock_pool():
    """Patch get_pool() to return a mock asyncpg pool."""
    pool = AsyncMock()
    with patch("bravo.db.queries.get_pool", return_value=pool):
        yield pool


class TestEnqueueReEvaluation:
    """Tests for queries.enqueue_re_evaluation()."""

    async def test_enqueue_inserts_row(self, _mock_pool) -> None:
        nudge_id = uuid4()
        expected = {"id": uuid4(), "ticket_key": "TEST-1", "status": "PENDING"}
        _mock_pool.fetchrow.return_value = expected

        result = await queries.enqueue_re_evaluation(
            "TEST-1", nudge_id, "C123", "1234567890.123456",
        )

        assert result == expected
        _mock_pool.fetchrow.assert_awaited_once()
        call_sql = _mock_pool.fetchrow.call_args[0][0]
        assert "INSERT INTO re_evaluation_queue" in call_sql
        assert "ON CONFLICT DO NOTHING" in call_sql

    async def test_enqueue_dedup_returns_none(self, _mock_pool) -> None:
        _mock_pool.fetchrow.return_value = None

        result = await queries.enqueue_re_evaluation(
            "TEST-1", uuid4(), "C123", "1234567890.123456",
        )

        assert result is None


class TestDequeueReEvaluation:
    """Tests for queries.dequeue_re_evaluation()."""

    async def test_dequeue_claims_pending_job(self, _mock_pool) -> None:
        expected = {
            "id": uuid4(),
            "ticket_key": "TEST-1",
            "status": "PROCESSING",
        }
        _mock_pool.fetchrow.return_value = expected

        result = await queries.dequeue_re_evaluation()

        assert result == expected
        call_sql = _mock_pool.fetchrow.call_args[0][0]
        assert "FOR UPDATE SKIP LOCKED" in call_sql
        assert "status = 'PENDING'" in call_sql

    async def test_dequeue_empty_queue_returns_none(self, _mock_pool) -> None:
        _mock_pool.fetchrow.return_value = None

        result = await queries.dequeue_re_evaluation()

        assert result is None


class TestCompleteReEvaluation:
    """Tests for queries.complete_re_evaluation()."""

    async def test_complete_sets_status_and_result(self, _mock_pool) -> None:
        queue_id = uuid4()
        expected = {"id": queue_id, "status": "COMPLETED", "result": "All checks passed"}
        _mock_pool.fetchrow.return_value = expected

        result = await queries.complete_re_evaluation(queue_id, "All checks passed")

        assert result == expected
        call_sql = _mock_pool.fetchrow.call_args[0][0]
        assert "COMPLETED" in call_sql
        assert "processed_at" in call_sql


class TestFailReEvaluation:
    """Tests for queries.fail_re_evaluation()."""

    async def test_fail_sets_error(self, _mock_pool) -> None:
        queue_id = uuid4()
        expected = {"id": queue_id, "status": "FAILED", "last_error": "boom"}
        _mock_pool.fetchrow.return_value = expected

        result = await queries.fail_re_evaluation(queue_id, "boom")

        assert result == expected
        call_sql = _mock_pool.fetchrow.call_args[0][0]
        assert "FAILED" in call_sql
        assert "last_error" in call_sql


class TestReapStaleJobs:
    """Tests for queries.reap_stale_jobs()."""

    async def test_reap_returns_count(self, _mock_pool) -> None:
        _mock_pool.execute.return_value = "UPDATE 3"

        count = await queries.reap_stale_jobs(timeout_minutes=10)

        assert count == 3
        call_sql = _mock_pool.execute.call_args[0][0]
        assert "status = 'PROCESSING'" in call_sql
        assert "PENDING" in call_sql

    async def test_reap_zero_rows(self, _mock_pool) -> None:
        _mock_pool.execute.return_value = "UPDATE 0"

        count = await queries.reap_stale_jobs()

        assert count == 0

    async def test_reap_custom_timeout(self, _mock_pool) -> None:
        _mock_pool.execute.return_value = "UPDATE 1"

        await queries.reap_stale_jobs(timeout_minutes=30)

        call_args = _mock_pool.execute.call_args[0]
        assert call_args[1] == "30"
