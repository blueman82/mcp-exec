"""Session management for Slack bot conversations.

Provides DynamoDB-backed session storage with automatic TTL management.
Implements privacy-first design with immediate deletion after query generation.
"""

from asksplunk.session.manager import SessionManager


class SessionDeletionError(Exception):
    """Raised when session deletion verification fails after all retries.

    This exception indicates a critical privacy violation where a session
    could not be confirmed as deleted from DynamoDB after multiple attempts.
    """

    pass


__all__ = ["SessionManager", "SessionDeletionError"]
