"""Per-user Jira PAT encrypted storage service."""

import structlog
from cryptography.fernet import Fernet, InvalidToken

from bravo.db import queries

logger = structlog.get_logger(__name__)


class PATService:
    """Encrypt, store, retrieve, and delete per-user Jira PATs."""

    def __init__(self, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())

    async def store_pat(self, slack_user_id: str, raw_pat: str) -> None:
        """Encrypt and persist a PAT."""
        encrypted = self._fernet.encrypt(raw_pat.encode())
        await queries.store_assignee_pat(slack_user_id, encrypted)
        logger.info("pat_stored", slack_user_id=slack_user_id)

    async def get_pat(self, slack_user_id: str) -> str | None:
        """Retrieve and decrypt a PAT, or None if not found."""
        encrypted = await queries.get_assignee_pat(slack_user_id)
        if encrypted is None:
            return None
        try:
            return self._fernet.decrypt(encrypted).decode()
        except InvalidToken:
            logger.error("pat_decrypt_failed", slack_user_id=slack_user_id)
            return None

    async def delete_pat(self, slack_user_id: str) -> bool:
        """Delete a stored PAT. Returns True if deleted."""
        deleted = await queries.delete_assignee_pat(slack_user_id)
        if deleted:
            logger.info("pat_deleted", slack_user_id=slack_user_id)
        return deleted

    async def has_pat(self, slack_user_id: str) -> bool:
        """Check if a PAT exists without decrypting."""
        encrypted = await queries.get_assignee_pat(slack_user_id)
        return encrypted is not None
