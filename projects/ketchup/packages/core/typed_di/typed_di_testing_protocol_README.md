# TypedDI Integration Testing Protocol

## How to use in tests

- For new services, add tests in tests/unit/core/typed_di/:
   - Smoke resolution
   - Dependency injection
   - Error code validation (if applicable)
   - Constructor signature validation
- Use the helpers to avoid real infra:
   - from tests.unit.core.typed_di.utils import patch_core_dependencies
   - with patch_core_dependencies(): register + initialize + resolve

## Run the tests
- TypedDI-only: make test-typed-di
- Or target a file: .venv/bin/pytest tests/unit/core/typed_di/test_factory_constructor_validation.py -q

This document defines the mandatory testing protocol for all services registered via the TypedDI system, plus optional helpers to reduce boilerplate and increase test reliability.

## 1 Mandatory Test Coverage for New TypedDI Services

Add tests to `tests/unit/core/typed_di/test_factory_constructor_validation.py` (or a service‑specific test file colocated in `tests/unit/core/typed_di/`) that cover:

1. Smoke Resolution Test
   - Resolve the new service through the real TypedDI registration path.
   - Assert the returned instance is not `None`.

2. Dependency Injection Test
   - Assert that all constructor dependencies are injected and not `None`.
   - For negative paths, verify that resolution fails or unresolved deps remain `None`.

3. Error Code Validation (when applicable)
   - Validate internal error codes map to expected enum values.

4. Constructor Signature Validation
   - Verify the factory’s invocation matches the service constructor’s signature.

Example (abbreviated):

```python
async def test_your_new_service_resolution(self):
    from packages.your.module import YourNewService
    from tests.unit.core.typed_di.utils import patch_core_dependencies

    with patch_core_dependencies():
        service_registrations.register_all_services(self.registry)
        await self.registry.initialize_all()

        service = await self.registry.aget(YourNewService)
        assert service is not None
        assert service.your_dependency is not None
```

## 2 What These Tests Prevent

- Factory–constructor mismatches (missing factory params)
- Missing dependencies (not listed in `dependencies=[...]`)
- Import path errors in service registrations
- Error code/enum mismatches
- Protocol vs. concrete alias registration drift

## 3 Test Categories To Always Run

1. Smoke resolution
2. Dependency injection
3. Error code validation (if applicable)
4. Constructor signature alignment

Suggested command (venv-backed):

```bash
make test-typed-di
```

## 4 DI Implementation Checklist

### Code Implementation
- [ ] Service class implemented with constructor
- [ ] Protocol interface defined in `service_protocols.py`
- [ ] Factory created in `service_registrations.py`
- [ ] `dependencies=[...]` lists ALL constructor params (non-optional)
- [ ] Protocol‑first registration used (protocol + concrete alias)

### Testing (Mandatory)
- [ ] Smoke resolution test
- [ ] Constructor signature validation test
- [ ] Dependency injection verification test
- [ ] Error code enum mapping test (if applicable)
- [ ] All TypedDI tests passing: `pytest tests/unit/core/typed_di -v`

### Verification
- [ ] Service resolves without errors
- [ ] All dependencies properly injected and not `None`
- [ ] Error codes match enum values
- [ ] No factory–constructor signature mismatches

## 5 Optional Helpers (Recommended)

Use the shared helpers to reduce boilerplate and avoid hitting real infrastructure in tests. See `tests/unit/core/typed_di/utils.py`.

### Provided Helpers

- `MockSecretsManager` — async methods used by SlackConfig
- `MockSlackConfig` — async `create()`, `get_headers()`, `get_api_base_url()`
- `MockDynamoDBAsyncClient` — constructor + minimal async methods
- `MockOpenAIHandler` — permissive `__init__(**kwargs)`
- `patch_core_dependencies()` — context manager that patches the core classes where `service_registrations` references them

Example:

```python
from tests.unit.core.typed_di.utils import patch_core_dependencies

async def test_resolve_service(self):
    with patch_core_dependencies():
        service_registrations.register_all_services(self.registry)
        await self.registry.initialize_all()
        svc = await self.registry.aget(YourServiceProtocol)
        assert svc is not None
```

## 6 Notes & Conventions

- Always patch at `packages.core.typed_di.service_registrations.<ClassName>` so factories use the mocks.
- Resolve via protocol types from `analysis.protocol_definitions` when the registry registers the protocol key.
- Use proper mock classes (not `Mock()`) to ensure `__qualname__` and constructors exist.

## 7 Rationale

These integration tests exercise the real production DI path and catch the exact failures that static analysis may miss (missing deps, incorrect factory calls, import mistakes, and runtime constructor errors). For TypedDI, runtime resolution testing is the gold standard.

