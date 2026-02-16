"""Tests for PAT encrypted storage service and database queries."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from bravo.db import queries as pat_queries
from bravo.services.pat import PATService


# ============ FIXTURES ============


@pytest.fixture
def fernet_key() -> str:
    """Generate a fresh Fernet key for each test."""
    return Fernet.generate_key().decode()


@pytest.fixture
def pat_service(fernet_key: str) -> PATService:
    """Create a PATService with a fresh key."""
    return PATService(fernet_key)


@pytest.fixture
def mock_pool() -> MagicMock:
    """Create a mock asyncpg connection pool."""
    pool = MagicMock()
    pool.execute = AsyncMock()
    pool.fetchval = AsyncMock()
    return pool


# ============ ENCRYPTION TESTS ============


async def test_encrypt_decrypt_roundtrip(pat_service: PATService) -> None:
    """store then get returns original PAT."""
    raw_pat = "ATATT3xFfGF0_test_pat_token_12345"
    with patch.object(pat_queries, "store_assignee_pat", new_callable=AsyncMock) as mock_store:
        await pat_service.store_pat("U123", raw_pat)
        stored_bytes = mock_store.call_args[0][1]

    with patch.object(pat_queries, "get_assignee_pat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = stored_bytes
        result = await pat_service.get_pat("U123")

    assert result == raw_pat


async def test_decrypt_with_wrong_key_returns_none(fernet_key: str) -> None:
    """Encrypt with key A, decrypt with key B returns None."""
    service_a = PATService(fernet_key)
    service_b = PATService(Fernet.generate_key().decode())

    with patch.object(pat_queries, "store_assignee_pat", new_callable=AsyncMock) as mock_store:
        await service_a.store_pat("U123", "secret-pat")
        stored_bytes = mock_store.call_args[0][1]

    with patch.object(pat_queries, "get_assignee_pat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = stored_bytes
        result = await service_b.get_pat("U123")

    assert result is None


async def test_store_overwrites_existing(pat_service: PATService) -> None:
    """Two store calls, get returns latest."""
    with patch.object(pat_queries, "store_assignee_pat", new_callable=AsyncMock) as mock_store:
        await pat_service.store_pat("U123", "old-pat")
        await pat_service.store_pat("U123", "new-pat")
        stored_bytes = mock_store.call_args[0][1]

    with patch.object(pat_queries, "get_assignee_pat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = stored_bytes
        result = await pat_service.get_pat("U123")

    assert result == "new-pat"


async def test_get_nonexistent_returns_none(pat_service: PATService) -> None:
    """No stored PAT returns None."""
    with patch.object(pat_queries, "get_assignee_pat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        result = await pat_service.get_pat("U999")

    assert result is None


async def test_delete_returns_true(pat_service: PATService) -> None:
    """Stored PAT delete returns True."""
    with patch.object(pat_queries, "delete_assignee_pat", new_callable=AsyncMock) as mock_del:
        mock_del.return_value = True
        result = await pat_service.delete_pat("U123")

    assert result is True


async def test_delete_nonexistent_returns_false(pat_service: PATService) -> None:
    """No PAT delete returns False."""
    with patch.object(pat_queries, "delete_assignee_pat", new_callable=AsyncMock) as mock_del:
        mock_del.return_value = False
        result = await pat_service.delete_pat("U123")

    assert result is False


# ============ HAS_PAT TESTS ============


async def test_has_pat_true(pat_service: PATService) -> None:
    """After store, has_pat returns True."""
    with patch.object(pat_queries, "get_assignee_pat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = b"some-encrypted-bytes"
        result = await pat_service.has_pat("U123")

    assert result is True


async def test_has_pat_false(pat_service: PATService) -> None:
    """No PAT, has_pat returns False."""
    with patch.object(pat_queries, "get_assignee_pat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        result = await pat_service.has_pat("U123")

    assert result is False


# ============ DB QUERY TESTS ============


async def test_store_assignee_pat_upsert(mock_pool: MagicMock) -> None:
    """Executes UPSERT SQL with correct params."""
    mock_pool.execute.return_value = "INSERT 0 1"
    with patch.object(pat_queries, "get_pool", return_value=mock_pool):
        await pat_queries.store_assignee_pat("U123", b"encrypted-data")

    mock_pool.execute.assert_called_once()
    args = mock_pool.execute.call_args
    assert "ON CONFLICT" in args[0][0]
    assert args[0][1] == "U123"
    assert args[0][2] == b"encrypted-data"


async def test_get_assignee_pat_found(mock_pool: MagicMock) -> None:
    """Returns encrypted_pat from record."""
    mock_pool.fetchval.return_value = b"encrypted-data"
    with patch.object(pat_queries, "get_pool", return_value=mock_pool):
        result = await pat_queries.get_assignee_pat("U123")

    assert result == b"encrypted-data"
    mock_pool.fetchval.assert_called_once()


async def test_get_assignee_pat_not_found(mock_pool: MagicMock) -> None:
    """Returns None when no record."""
    mock_pool.fetchval.return_value = None
    with patch.object(pat_queries, "get_pool", return_value=mock_pool):
        result = await pat_queries.get_assignee_pat("U999")

    assert result is None


async def test_delete_assignee_pat_success(mock_pool: MagicMock) -> None:
    """Returns True on DELETE 1."""
    mock_pool.execute.return_value = "DELETE 1"
    with patch.object(pat_queries, "get_pool", return_value=mock_pool):
        result = await pat_queries.delete_assignee_pat("U123")

    assert result is True


# ============ INTEGRATION TESTS ============


async def test_service_store_calls_queries(pat_service: PATService) -> None:
    """store_pat calls queries.store_assignee_pat with encrypted bytes."""
    with patch.object(pat_queries, "store_assignee_pat", new_callable=AsyncMock) as mock_store:
        await pat_service.store_pat("U123", "my-secret-pat")

    mock_store.assert_called_once()
    slack_id, encrypted = mock_store.call_args[0]
    assert slack_id == "U123"
    assert isinstance(encrypted, bytes)
    assert encrypted != b"my-secret-pat"


async def test_service_get_decrypts(pat_service: PATService, fernet_key: str) -> None:
    """queries.get_assignee_pat returns encrypted, get_pat returns plaintext."""
    fernet = Fernet(fernet_key.encode())
    encrypted = fernet.encrypt(b"my-secret-pat")

    with patch.object(pat_queries, "get_assignee_pat", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = encrypted
        result = await pat_service.get_pat("U123")

    assert result == "my-secret-pat"
