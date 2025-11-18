"""
Service Registration Manager

Provides ServiceRegistrationManager class for protocol-first service registration
with concrete class aliasing for backward compatibility.
"""

import inspect
from typing import Any, Dict, List, Optional, Type

from packages.core.logging import setup_logger

from ..registry import TypedServiceRegistry
from ..types import DependencySpec

logger = setup_logger(__name__)


class ServiceRegistrationManager:
    """
    Manages protocol-first service registration with concrete class aliasing.

    Implements the enhanced Phase 1 requirements:
    - Register protocols first, add concrete-class aliases where call sites still use classes
    - Call register_before initialize_all() then freeze_after_init()
    - Preserve qualifiers and list all DependencySpec dependencies
    """

    def __init__(self, registry: TypedServiceRegistry):
        self.registry = registry
        self.registered_services: Dict[str, Dict[str, Any]] = {}
        self.protocol_to_concrete_mapping: Dict[Type, Type] = {}
        self.frozen = False

    def register_protocol_with_concrete_alias(
        self,
        protocol_type: Type,
        concrete_type: Type,
        factory,
        dependencies: List[DependencySpec],
        lifetime: str = "singleton",
        qualifier: Optional[str] = None,
        essential: bool = False,
    ) -> None:
        """
        Register a protocol first, then add concrete class alias.

        This ensures both protocol-based access and legacy concrete class access work.
        """
        if self.frozen:
            raise RuntimeError("Cannot register services after registry is frozen")

        # Register the protocol first (preferred access method)
        if protocol_type is not concrete_type:
            self.registry.register(
                service_type=protocol_type,
                factory=factory,
                dependencies=dependencies,
                lifetime=lifetime,
                qualifier=qualifier,
                lazy=not essential,  # Essential services are not lazy
                essential=essential,
            )

        # Add concrete class alias for legacy call sites
        self.registry.register(
            service_type=concrete_type,
            factory=factory,
            dependencies=dependencies,
            lifetime=lifetime,
            qualifier=qualifier,
            lazy=not essential,  # Essential services are not lazy
            essential=essential,
        )

        # Track the mapping for validation
        self.protocol_to_concrete_mapping[protocol_type] = concrete_type

        # Record registration details for monitoring
        service_key = f"{protocol_type.__name__}:{qualifier or 'default'}"
        self.registered_services[service_key] = {
            "protocol_type": protocol_type.__name__,
            "concrete_type": concrete_type.__name__,
            "dependencies": [
                getattr(dep.type, "__name__", str(dep.type)) for dep in dependencies
            ],
            "lifetime": lifetime,
            "qualifier": qualifier,
            "factory_type": type(factory).__name__,
        }

        logger.info(
            f"Registered protocol {protocol_type.__name__} with concrete alias {concrete_type.__name__}"
        )

    def validate_protocol_compatibility(
        self, protocol_type: Type, concrete_type: Type
    ) -> bool:
        """Validate that concrete type is compatible with protocol."""
        try:
            return isinstance(concrete_type(), protocol_type)
        except Exception as e:
            logger.warning(
                f"Protocol compatibility check failed for {protocol_type.__name__}: {e}"
            )
            return inspect.isclass(concrete_type)  # Basic fallback check

    def freeze_registry(self) -> None:
        """Freeze the registry after all services are registered."""
        self.frozen = True
        logger.info(
            f"Service registry frozen with {len(self.registered_services)} services registered"
        )

    def get_registration_summary(self) -> Dict[str, Any]:
        """Get comprehensive registration summary for monitoring."""
        return {
            "total_services": len(self.registered_services),
            "services": self.registered_services.copy(),
            "protocol_mappings": {
                proto.__name__: concrete.__name__
                for proto, concrete in self.protocol_to_concrete_mapping.items()
            },
            "frozen": self.frozen,
        }