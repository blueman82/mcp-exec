#!/usr/bin/env python3
"""
Dependency coverage validation for TypedDI registrations.

Ensures that for each registered concrete class, the registry's declared
dependencies cover the required constructor parameter types. This guards
against missing dependency specs that would cause runtime resolution failures.

Strategy:
- Get constructor signature and determine required params (no default).
- Collect type hints for the constructor where available; if missing, fall back
  to analysis/service_interface_catalog.json to map parameter names to types.
- Compare required param type names to the registry's DependencySpec types.
  If any required param type name is not present among dependencies, fail.

This test is intentionally name-based to avoid importing extra modules purely
for typing; it’s robust enough for regression prevention while not overfitting.
"""

from __future__ import annotations

import inspect
import json
import os
import sys
import unittest
from typing import Dict, List, Optional

sys.path.insert(0, os.getcwd())

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations import register_all_services
from tests.unit.core.typed_di.utils import patch_core_dependencies

logger = setup_logger(__name__)


def _load_service_interface_index() -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    """Load analysis/service_interface_catalog.json and index by module+class name."""
    path = os.path.join("analysis", "service_interface_catalog.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("classes", []) if isinstance(data, dict) else []

    index: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for cls in entries:
        class_name = cls.get("class_name")
        module_path = cls.get(
            "module_path"
        )  # e.g., "slack.command_processing.archive_command"
        ctor_params = cls.get("constructor_params", [])
        if not class_name or not module_path:
            continue
        key = f"{module_path}:{class_name}"
        index[key] = {"constructor_params": ctor_params}
    return index


def _get_required_param_type_names_from_analysis(
    service_type,
) -> Dict[str, Optional[str]]:
    """Best-effort mapping of required param name -> type name using analysis JSON."""
    idx = _load_service_interface_index()
    module_path = service_type.__module__.removeprefix("packages.")
    key = f"{module_path}:{service_type.__name__}"
    info = idx.get(key)
    if not info:
        return {}
    result: Dict[str, Optional[str]] = {}
    for p in info.get("constructor_params", []):
        name = p.get("name")
        default = p.get("default")
        type_ann = p.get("type_annotation")
        # Treat params without defaults as required
        if name and default is None:
            # Normalize quoted annotations like "'SecretsManager'"
            if (
                isinstance(type_ann, str)
                and type_ann.startswith("'")
                and type_ann.endswith("'")
            ):
                type_ann = type_ann.strip("'")
            result[name] = type_ann
    return result


class TestDependencyCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Reset registration manager to avoid cross-test pollution
        import packages.core.typed_di.service_registrations as svc_reg  # noqa: F401

        if hasattr(svc_reg, "_registration_manager"):
            svc_reg._registration_manager = None  # type: ignore[attr-defined]
        cls._core_patches = patch_core_dependencies()
        cls._core_patches.__enter__()
        cls.registry = TypedServiceRegistry()
        register_all_services(cls.registry)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "_core_patches"):
            cls._core_patches.__exit__(None, None, None)

    def test_required_constructor_types_are_declared_as_dependencies(self):
        errors: List[str] = []
        seen = set()

        for _, reg in self.registry._registrations.items():  # type: ignore[attr-defined]
            service_type = getattr(reg, "service_type", None)
            if service_type is None or not inspect.isclass(service_type):
                continue
            if getattr(service_type, "__name__", "").endswith("Protocol"):
                continue
            key = (service_type, id(reg.factory))
            if key in seen:
                continue
            seen.add(key)

            # Determine required params (no default) via signature
            try:
                sig = inspect.signature(service_type.__init__)
            except (TypeError, ValueError):
                continue

            required_param_names: List[str] = [
                n
                for n, p in sig.parameters.items()
                if n != "self"
                and p.default is inspect._empty
                and p.kind
                not in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                )
            ]

            if not required_param_names:
                continue

            # Resolve param types: prefer type hints, fallback to analysis JSON
            type_hints = {}
            try:
                from typing import get_type_hints  # py3.13 available

                type_hints = get_type_hints(service_type.__init__)
            except Exception:
                type_hints = {}

            required_param_types: Dict[str, Optional[str]] = {}
            for name in required_param_names:
                hinted = type_hints.get(name)
                if hinted is not None:
                    # Convert to a name for comparison (handle typing.Optional etc.)
                    type_name = getattr(hinted, "__name__", None)
                    if (
                        type_name is None
                        and hasattr(hinted, "__args__")
                        and hinted.__args__
                    ):
                        # Optional[T] or Union[T, None]
                        first = hinted.__args__[0]
                        type_name = getattr(first, "__name__", None)
                    required_param_types[name] = type_name
                else:
                    required_param_types[name] = None

            # Fill gaps from analysis where hints missing
            if any(v is None for v in required_param_types.values()):
                from_analysis = _get_required_param_type_names_from_analysis(
                    service_type
                )
                for name, typ in from_analysis.items():
                    if (
                        name in required_param_types
                        and required_param_types[name] is None
                    ):
                        required_param_types[name] = typ

            # Build set of dependency type names declared in registry
            # Include both Protocol and concrete names for compatibility
            dep_type_names = set()
            for dep in reg.dependencies:
                dep_name = getattr(dep.type, "__name__", str(dep.type))
                dep_type_names.add(dep_name)
                # If it's a Protocol, also add the concrete name
                if dep_name.endswith("Protocol"):
                    dep_type_names.add(dep_name[:-8])  # Add name without Protocol suffix
                # If it's not a Protocol, also add the Protocol name
                else:
                    dep_type_names.add(dep_name + "Protocol")

            # Validate each required param has a matching dependency type name
            PRIMITIVES = {
                "str",
                "int",
                "float",
                "bool",
                "dict",
                "list",
                "set",
                "tuple",
                "callable",
            }
            for pname, tname in required_param_types.items():
                if tname is None:
                    # If we cannot resolve type, skip (avoid false positives)
                    continue
                # Normalize potential quoted names from analysis
                if isinstance(tname, str):
                    norm = tname.strip("'")
                else:
                    norm = str(tname)
                # Skip primitives and collections; only enforce DI for service types
                if norm.lower() in PRIMITIVES:
                    continue
                if norm not in dep_type_names:
                    errors.append(
                        f"{service_type.__name__}: missing DependencySpec for required param '{pname}' type '{norm}'"
                    )

        if errors:
            self.fail(
                "Missing required DependencySpec for constructor params:\n"
                + "\n".join(sorted(set(errors)))
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
