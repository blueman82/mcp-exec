---
paths:
  - "packages/**/*.py"
  - "ketchup_*/**/*.py"
---
# Import Conventions

## Import order (enforced by isort, auto-fixed by hook)
1. Standard library
2. Third-party packages
3. Local/project imports

## CRITICAL: Barrel export prohibition

**NEVER** import protocols from barrel exports in service code:
```python
# WRONG — causes circular imports at container startup
from packages.core.typed_di.service_registrations.protocols import MyProtocol
```

**ALWAYS** import from the specific protocol file:
```python
# CORRECT
from packages.core.typed_di.service_registrations.protocols.my_protocols import MyProtocol
```

**Why**: Barrel exports (`__init__.py` re-exports) create circular import chains that fail silently — no error at import time, crash at container startup in production. Proven by commit `f35857e0` (circular import in metrics_data_collector.py).

**When barrel exports ARE safe**: Only in DI container setup code (`registrations/__init__.py`), never in service implementation code.

## Other rules
- No star imports (`from module import *`)
- No `TYPE_CHECKING` blocks — fix the architecture if circular imports exist
- No lazy imports — import at module level
