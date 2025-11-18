"""
Typed DI System Exceptions

Named error types for clear exception handling in the TypedServiceRegistry.
"""


class MissingDependencyError(Exception):
    """Raised when a required dependency is not registered."""

    pass


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""

    pass


class NotInitializedError(Exception):
    """Raised by get() before initialize_all() is called."""

    pass


class DuplicateRegistrationError(Exception):
    """Raised when attempting to register a service twice."""

    pass


class AmbiguousResolutionError(Exception):
    """Raised when multiple services match a resolution request."""

    pass


class FrozenRegistryError(Exception):
    """Raised when attempting to modify a frozen registry."""

    pass
