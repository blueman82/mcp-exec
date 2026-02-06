"""Tests for the async retry with exponential backoff."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bravo.services.resilience import _calc_delay, retry_with_backoff

# Shared helpers
_REQUEST = httpx.Request("POST", "http://test")


def _ok_response(**kwargs) -> httpx.Response:
    return httpx.Response(200, json={"ok": True}, request=_REQUEST, **kwargs)


def _error_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=_REQUEST)


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch(
        "bravo.services.resilience.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        yield mock_sleep


class TestRetryWithBackoff:

    async def test_success_first_attempt(self, _no_sleep):
        fn = AsyncMock(return_value=_ok_response())
        resp = await retry_with_backoff(fn, max_retries=3, operation="test")
        assert resp.status_code == 200
        fn.assert_awaited_once()
        _no_sleep.assert_not_awaited()

    async def test_transport_error_recovery(self, _no_sleep):
        fn = AsyncMock(side_effect=[httpx.ConnectError("refused"), _ok_response()])
        resp = await retry_with_backoff(fn, max_retries=3, operation="test")
        assert resp.status_code == 200
        assert fn.await_count == 2

    async def test_timeout_recovery(self, _no_sleep):
        fn = AsyncMock(side_effect=[httpx.ReadTimeout("timeout"), _ok_response()])
        resp = await retry_with_backoff(fn, max_retries=3, operation="test")
        assert resp.status_code == 200
        assert fn.await_count == 2

    async def test_503_recovery(self, _no_sleep):
        fn = AsyncMock(side_effect=[_error_response(503), _ok_response()])
        resp = await retry_with_backoff(fn, max_retries=3, operation="test")
        assert resp.status_code == 200
        assert fn.await_count == 2

    async def test_no_retry_on_404(self, _no_sleep):
        fn = AsyncMock(return_value=_error_response(404))
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await retry_with_backoff(fn, max_retries=3, operation="test")
        assert exc_info.value.response.status_code == 404
        fn.assert_awaited_once()

    async def test_exhausted_retries(self, _no_sleep):
        fn = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(httpx.ConnectError):
            await retry_with_backoff(fn, max_retries=3, operation="test")
        assert fn.await_count == 3

    async def test_backoff_delays_verified(self, _no_sleep):
        fn = AsyncMock(
            side_effect=[
                httpx.ConnectError("fail"),
                httpx.ConnectError("fail"),
                _ok_response(),
            ]
        )
        await retry_with_backoff(
            fn, max_retries=3, base_delay=1.0, max_delay=10.0, operation="test"
        )
        assert _no_sleep.await_count == 2
        # First delay: 1.0 * uniform(0.8, 1.2) -> [0.8, 1.2]
        first_delay = _no_sleep.call_args_list[0][0][0]
        assert 0.8 <= first_delay <= 1.2
        # Second delay: 2.0 * uniform(0.8, 1.2) -> [1.6, 2.4]
        second_delay = _no_sleep.call_args_list[1][0][0]
        assert 1.6 <= second_delay <= 2.4

    async def test_429_retry(self, _no_sleep):
        fn = AsyncMock(side_effect=[_error_response(429), _ok_response()])
        resp = await retry_with_backoff(fn, max_retries=3, operation="test")
        assert resp.status_code == 200
        assert fn.await_count == 2


class TestCalcDelay:

    def test_exponential_growth(self):
        d1 = _calc_delay(1, 0.5, 10.0)
        d2 = _calc_delay(2, 0.5, 10.0)
        d3 = _calc_delay(3, 0.5, 10.0)
        assert 0.4 <= d1 <= 0.6  # 0.5 * [0.8, 1.2]
        assert 0.8 <= d2 <= 1.2  # 1.0 * [0.8, 1.2]
        assert 1.6 <= d3 <= 2.4  # 2.0 * [0.8, 1.2]

    def test_max_delay_cap(self):
        # attempt=100 should be capped at max_delay=5.0
        delay = _calc_delay(100, 0.5, 5.0)
        assert delay <= 5.0 * 1.2  # max_delay * max jitter
