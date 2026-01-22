"""
ServiceSpec - Declarative service registration system.

Reduces boilerplate in service registration files by providing a declarative
alternative to manual factory functions. Each ServiceSpec defines a service's
protocol, concrete implementation, dependencies, and lifetime.

Example:
    # Before (15-25 lines):
    async def create_shortcut_handler(resolver) -> ShortcutHandler:
        logger.info("Creating ShortcutHandler instance via TypedDI")
        feedback = await resolver.aget(FeedbackReportHandlerProtocol)
        posting = await resolver.aget(SlackPostingHandlerProtocol)
        return ShortcutHandler(
            feedback_report_handler=feedback,
            posting_handler=posting
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ShortcutHandlerProtocol,
        concrete_type=ShortcutHandler,
        factory=create_shortcut_handler,
        dependencies=[...],
        lifetime="singleton",
    )

    # After (3-5 lines):
    ServiceSpec(
        protocol=ShortcutHandlerProtocol,
        concrete=ShortcutHandler,
        deps={"feedback_report_handler": FeedbackReportHandlerProtocol,
              "posting_handler": SlackPostingHandlerProtocol},
    )
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Type, Union

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

logger = setup_logger(__name__)


@dataclass
class ServiceSpec:
    """
    Declarative specification for service registration.

    Attributes:
        protocol: The protocol/interface type this service implements.
        concrete: The concrete implementation class.
        deps: Mapping of constructor parameter names to protocol types.
              Use tuple (Protocol, True) for optional dependencies.
        lifetime: Service lifetime - "singleton", "scoped", or "transient".
        factory: Optional custom factory function for complex initialization.
                 If provided, deps are still used for DependencySpec list.
        log_creation: Whether to log service creation (default True).
    """

    protocol: Type
    concrete: Type
    deps: Dict[str, Union[Type, tuple]] = field(default_factory=dict)
    lifetime: Literal["singleton", "scoped", "transient"] = "singleton"
    factory: Optional[Callable] = None
    log_creation: bool = True

    def get_dependency_specs(self) -> List[DependencySpec]:
        """Convert deps dict to list of DependencySpec objects."""
        specs = []
        for dep_info in self.deps.values():
            if isinstance(dep_info, tuple):
                # (Protocol, optional=True)
                protocol_type, optional = dep_info
                specs.append(DependencySpec(protocol_type, optional=optional))
            else:
                # Just Protocol
                specs.append(DependencySpec(dep_info))
        return specs

    def create_factory(self) -> Callable:
        """
        Generate a factory function from the deps specification.

        Returns:
            An async factory function that resolves dependencies and
            constructs the service.
        """
        if self.factory:
            return self.factory

        # Capture spec attributes for closure
        concrete = self.concrete
        deps = self.deps
        log_creation = self.log_creation

        async def generated_factory(resolver) -> Any:
            """Auto-generated factory function."""
            if log_creation:
                logger.info(
                    "Creating %s instance via TypedDI (ServiceSpec)",
                    concrete.__name__,
                )

            # Resolve all dependencies
            resolved_deps = {}
            for param_name, dep_info in deps.items():
                if isinstance(dep_info, tuple):
                    # Optional dependency
                    protocol_type, _ = dep_info
                    try:
                        resolved_deps[param_name] = await resolver.aget(protocol_type)
                    except Exception:
                        resolved_deps[param_name] = None
                else:
                    # Required dependency
                    resolved_deps[param_name] = await resolver.aget(dep_info)

            return concrete(**resolved_deps)

        return generated_factory


def register_from_specs(
    manager: Any,
    specs: List[ServiceSpec],
    module_name: str = "",
) -> int:
    """
    Register multiple services from ServiceSpec list.

    Args:
        manager: ServiceRegistrationManager instance.
        specs: List of ServiceSpec objects to register.
        module_name: Optional module name for logging.

    Returns:
        Number of services registered.
    """
    if module_name:
        logger.info("Registering %d services from %s via ServiceSpec", len(specs), module_name)

    for spec in specs:
        manager.register_protocol_with_concrete_alias(
            protocol_type=spec.protocol,
            concrete_type=spec.concrete,
            factory=spec.create_factory(),
            dependencies=spec.get_dependency_specs(),
            lifetime=spec.lifetime,
        )

    return len(specs)
