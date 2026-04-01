---
paths:
  - "packages/core/typed_di/**"
  - "ketchup_*/container.py"
---
# TypedDI Service Registration

## ServiceSpec (preferred — 80% less boilerplate)
```python
ServiceSpec(
    protocol=MyProtocol,
    concrete=MyService,
    deps={"dep_name": DepProtocol},
)
# Optional deps: deps={"name": (Protocol, True)}
# Batch: register_from_specs(manager, specs_list)
```

## Manual factory (complex initialization only)
```python
def register_my_service(manager):
    async def factory(registry):
        dep = await registry.get(DepProtocol)
        return MyService(dep)
    manager.register(MyProtocol, factory)
```

## Feature-flag gating (at registration time)
```python
def register_my_service(manager):
    if os.environ.get("KETCHUP_MY_FEATURE_ENABLED", "false").lower() != "true":
        return
    # ... register services
```

## Registration checklist — ALL steps required
1. Define protocol in `service_registrations/protocols/`
2. Implement concrete class
3. Create ServiceSpec or factory in `service_registrations/registrations/`
4. Add registration function to role map in `registrations/__init__.py`
5. Update ALL Mock*/Fake* classes in tests
6. Add protocol compliance test
7. Feature-flag gate if conditional
8. Import from specific protocol file, never barrel exports

## Canonical example
CSOPM notifier: `ketchup_csopm_notifier/container.py` — full wiring of state tracker, JIRA poller, Slack notifier, reminder service with parent registry integration.

## Common mistakes
- Adding read path without write path (snooze bug, PR #282)
- Updating protocol without updating mock classes
- Forgetting to add registration to role map in `__init__.py`
