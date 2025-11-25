#!/usr/bin/env python3
"""
Comprehensive constructor signature validation for all TypedDI registrations.

Goal: Ensure every factory that directly constructs a class uses keyword names that
match the target class constructor's required parameters. This prevents runtime
breakages due to mismatched or missing kwargs.

Notes:
- Uses AST parsing of the factory function to find `return ClassName(...)` calls
  and collect the keyword names provided.
- Skips factories that do not directly call the constructor (e.g., `return await Class.create(...)`).
- Ignores known optional/infra parameters (e.g., `max_concurrent_requests`).
- Runs with project root added to `sys.path` so imports resolve consistently.
"""

from __future__ import annotations

import ast
import inspect
import os
import sys
import unittest

# Ensure project root is on PYTHONPATH for imports
sys.path.insert(0, os.getcwd())

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations import register_all_services

logger = setup_logger(__name__)


def _extract_ctor_kwargs(source: str, class_name: str) -> set[str]:
    """Parse factory source and return keyword names used in a `return ClassName(...)` call."""
    import textwrap

    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return set()

    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            call = node.value

            # Identify called name: supports `ClassName(...)` and `module.ClassName(...)`
            func_name = None
            if isinstance(call.func, ast.Name):
                func_name = call.func.id
            elif isinstance(call.func, ast.Attribute):
                func_name = call.func.attr

            if func_name == class_name:
                for kw in call.keywords:
                    if kw.arg:  # ignore **kwargs
                        used.add(kw.arg)

    return used


class TestAllFactoryConstructorSignatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Reset registration manager to avoid cross-test pollution
        import packages.core.typed_di.service_registrations as svc_reg  # noqa: F401

        if hasattr(svc_reg, "_registration_manager"):
            svc_reg._registration_manager = None  # type: ignore[attr-defined]
        # Build a registry and register services once
        cls.registry = TypedServiceRegistry()
        register_all_services(cls.registry)

    def test_service_registrations_module_importable(self):
        """Sanity: service_registrations should import with project root on PYTHONPATH."""
        try:
            import packages.core.typed_di.service_registrations as svc_reg  # noqa: F401
        except Exception as e:
            self.fail(f"Failed to import service_registrations: {e}")

    def test_all_factories_match_required_constructor_params(self):
        """Every factory should pass required constructor kwargs matching the class __init__ signature."""
        errors: list[str] = []
        seen: set[tuple[type, int]] = set()

        for _, reg in self.registry._registrations.items():  # type: ignore[attr-defined]
            service_type = getattr(reg, "service_type", None)
            if service_type is None:
                continue

            # Skip Protocol registrations; concrete aliases are also present
            if getattr(service_type, "__name__", "").endswith("Protocol"):
                continue

            if not inspect.isclass(service_type):
                continue

            # De-duplicate by (class, factory function id)
            key = (service_type, id(reg.factory))
            if key in seen:
                continue
            seen.add(key)

            # Collect required constructor params (excluding self and known optional)
            try:
                sig = inspect.signature(service_type.__init__)
            except (TypeError, ValueError):
                # Builtins or special callables — skip
                continue

            required_params: list[str] = []
            for name, param in sig.parameters.items():
                if name == "self":
                    continue
                # Ignore varargs/kwargs-only entries
                if param.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue
                if param.default is inspect._empty:
                    required_params.append(name)

            # Get factory source
            try:
                factory_src = inspect.getsource(reg.factory)
            except OSError:
                # Likely a lambda or C-accelerated; skip
                continue

            used_kwargs = _extract_ctor_kwargs(factory_src, service_type.__name__)
            if not used_kwargs:
                # Not a direct constructor call (e.g., await Class.create(...)) — skip
                continue

            for req in required_params:
                if req not in used_kwargs:
                    errors.append(
                        f"{service_type.__name__}: factory missing kwarg '{req}=' in constructor call"
                    )

        if errors:
            self.fail(
                "Factory constructor kwarg mismatches (required kwargs not passed):\n"
                + "\n".join(sorted(set(errors)))
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
