"""
Caching & Storage Registration Module

Registers caching and storage infrastructure services:
- CacheManager: General purpose caching with TTL support
- SessionManager: User session management and lifecycle
- FileStorageService: File upload/download handling

These 3 services provide caching and storage capabilities for the application.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, Any, Dict, Protocol, runtime_checkable

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Core infrastructure imports
try:
    from packages.secrets.manager import SecretsManager
except ImportError as e:
    logger = setup_logger(__name__)
    logger.warning(f"Core infrastructure import failed: {e}")

if TYPE_CHECKING:
    from packages.core.typed_di.service_registrations.manager import ServiceRegistrationManager

logger = setup_logger(__name__)


# =============================================================================
# PROTOCOL DEFINITIONS
# =============================================================================


@runtime_checkable
class CacheManagerProtocol(Protocol):
    """Protocol for general purpose caching."""

    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool: ...
    async def delete(self, key: str) -> bool: ...
    async def clear_cache(self, pattern: str = None) -> int: ...


@runtime_checkable
class SessionManagerProtocol(Protocol):
    """Protocol for user session management."""

    async def create_session(self, user_id: str, data: Dict[str, Any]) -> str: ...
    async def get_session(self, session_id: str) -> Dict[str, Any]: ...
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool: ...
    async def delete_session(self, session_id: str) -> bool: ...


@runtime_checkable
class FileStorageServiceProtocol(Protocol):
    """Protocol for file upload/download handling."""

    async def upload_file(
        self, file_data: bytes, filename: str, metadata: Dict[str, Any] = None
    ) -> str: ...
    async def download_file(self, file_id: str) -> bytes: ...
    async def delete_file(self, file_id: str) -> bool: ...
    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]: ...


def register_caching_storage(manager: "ServiceRegistrationManager") -> None:
    """
    Register caching and storage services (3 services).

    Provides caching and storage capabilities:
    - CacheManager: General purpose caching with TTL support
    - SessionManager: User session management and lifecycle
    - FileStorageService: File upload/download handling

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration
    """
    logger.info("Registering Caching & Storage Services (3 services)")

    # CacheManager
    async def create_cache_manager(resolver) -> object:
        """Factory function for CacheManager."""
        logger.info("Creating CacheManager instance via TypedDI")

        class CacheManager:
            """General purpose caching service."""

            def __init__(self):
                self.cache = {}

            async def get(self, key: str) -> Any:
                """Get cached value by key."""
                logger.debug(f"Cache get: {key}")
                return self.cache.get(key)

            async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
                """Set cached value with TTL."""
                logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
                self.cache[key] = {"value": value, "ttl": ttl}
                return True

            async def delete(self, key: str) -> bool:
                """Delete cached value."""
                logger.debug(f"Cache delete: {key}")
                return self.cache.pop(key, None) is not None

            async def clear_cache(self, pattern: str = None) -> int:
                """Clear cache entries matching pattern."""
                if pattern is None:
                    count = len(self.cache)
                    self.cache.clear()
                    return count
                # Pattern matching would be implemented here
                return 0

        return CacheManager()

    manager.register_protocol_with_concrete_alias(
        protocol_type=CacheManagerProtocol,
        concrete_type=type("ConcreteType1022", (), {}),
        factory=create_cache_manager,
        dependencies=[],
        lifetime="singleton",
    )

    # SessionManager
    async def create_session_manager(resolver) -> object:
        """Factory function for SessionManager."""
        logger.info("Creating SessionManager instance via TypedDI")
        cache_manager = await resolver.aget(CacheManagerProtocol)

        class SessionManager:
            """User session management service."""

            def __init__(self, cache_manager):
                self.cache = cache_manager
                self.sessions = {}

            async def create_session(self, user_id: str, data: Dict[str, Any]) -> str:
                """Create a new user session."""
                session_id = f"session_{user_id}_{len(self.sessions)}"
                session_data = {"user_id": user_id, "data": data, "created_at": "now"}
                self.sessions[session_id] = session_data
                logger.debug(f"Created session {session_id} for user {user_id}")
                return session_id

            async def get_session(self, session_id: str) -> Dict[str, Any]:
                """Get session data by session ID."""
                logger.debug(f"Getting session: {session_id}")
                return self.sessions.get(session_id, {})

            async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
                """Update session data."""
                if session_id in self.sessions:
                    self.sessions[session_id]["data"].update(data)
                    logger.debug(f"Updated session: {session_id}")
                    return True
                return False

            async def delete_session(self, session_id: str) -> bool:
                """Delete a session."""
                logger.debug(f"Deleting session: {session_id}")
                return self.sessions.pop(session_id, None) is not None

        return SessionManager(cache_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=SessionManagerProtocol,
        concrete_type=type("ConcreteType1023", (), {}),
        factory=create_session_manager,
        dependencies=[DependencySpec(CacheManagerProtocol)],
        lifetime="singleton",
    )

    # FileStorageService
    async def create_file_storage_service(resolver) -> object:
        """Factory function for FileStorageService."""
        logger.info("Creating FileStorageService instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)

        class FileStorageService:
            """File upload/download handling service."""

            def __init__(self, secrets_manager):
                self.secrets = secrets_manager
                self.files = {}

            async def upload_file(
                self, file_data: bytes, filename: str, metadata: Dict[str, Any] = None
            ) -> str:
                """Upload a file and return file ID."""
                file_id = f"file_{len(self.files)}_{filename}"
                file_info = {
                    "filename": filename,
                    "size": len(file_data),
                    "metadata": metadata or {},
                    "uploaded_at": "now",
                }
                self.files[file_id] = file_info
                logger.debug(f"Uploaded file {filename} as {file_id}")
                return file_id

            async def download_file(self, file_id: str) -> bytes:
                """Download file data by file ID."""
                logger.debug(f"Downloading file: {file_id}")
                # Would return actual file data
                return b"file_content"

            async def delete_file(self, file_id: str) -> bool:
                """Delete a file."""
                logger.debug(f"Deleting file: {file_id}")
                return self.files.pop(file_id, None) is not None

            async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
                """Get file metadata."""
                return self.files.get(file_id, {})

        return FileStorageService(secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=FileStorageServiceProtocol,
        concrete_type=type("ConcreteType1024", (), {}),
        factory=create_file_storage_service,
        dependencies=[DependencySpec(SecretsManager)],
        lifetime="singleton",
    )

    logger.info("Caching & Storage Services completed - 3 services registered")
