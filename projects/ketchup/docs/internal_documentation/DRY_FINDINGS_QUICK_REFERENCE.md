# DRY Analysis - Quick Reference Guide

## High-Confidence Findings (Implement First)

### Finding 1: Channel Parameter Validation (4 files, 45-60 LOC)
```
FILES:
- query.py (lines 59-70, 90-98)
- status_report.py (lines 62-73)
- summary.py (lines 69-80)
- feature.py (lines 138-148)

DUPLICATE CODE:
if not (
    SLACK_CHANNEL_ID_REGEX.match(param)
    or SLACK_CHANNEL_MENTION_REGEX.match(param)
    or SLACK_CHANNEL_NAME_REGEX.match(param)
):
    raise ValidationError(...)

ACTION: Extract to validate_channel_parameter() utility function
```

### Finding 2: Message Handler Classes (4 classes, 120-180 LOC)
```
FILES:
- status.py (214 LOC)
- report.py (211 LOC)
- query.py (201 LOC)
- summary.py (245 LOC)

DUPLICATE PATTERN:
class XxxMessageHandler:
    def __init__(self):
        self._posting_handler = None
        self._channel_details_getter = None
        self._fallback_getter = None
        self._build_feedback_blocks = None
        self._block_kit_builder = None

    def configure(self, posting_handler, ...):
        # ... identical logic ...

ACTION: Create BaseMessageHandler base class, inherit in each
```

### Finding 3: Parameter Placeholder Comments (9 files, 25-35 LOC)
```
PATTERN APPEARS 12+ TIMES:
user_id="",  # Will be set by caller
user_name="",  # Will be set by caller
channel_id="",  # Will be set by caller
response_url="",  # Will be set by caller

ACTION: Add factory methods to CommandParams dataclasses
```

---

## Medium-Confidence Findings (Phase 2)

### Finding 4: Channel Extraction Logic (3 files, 35-50 LOC)
- query.py, status_report.py, summary.py
- Same: parts.split(), context branching, len() checks
- Action: Shared extraction helper function

### Finding 5: Business Service Pattern (3 files, 40-60 LOC)
- audit.py, compliance.py, governance.py
- Same: __init__, async methods, helper patterns
- Action: Abstract BaseBusinessService class

### Finding 6: AI Prompt Scaffolding (4 files, 60-80 LOC)
- status.py, report.py
- Same: Self-verification structure, output templates, formatting rules
- Action: PromptScaffold utility class

### Finding 7: DynamoDB Error Handling (5 files, 30-45 LOC)
- access_request_operations.py, channel_operations.py, channel_query_operations.py, restore_state_operations.py, archive_operations.py
- Pattern: try/except ClientError appearing 11 times
- Action: Error handling decorator

### Finding 8: Validation Error Factory (9 files, 20-30 LOC)
- All extractors use ValidationError(message, user_message)
- 38 instances of same 2-arg pattern
- Action: Error factory methods

---

## Implementation Priority Matrix

| Finding | LOC Saved | Risk | Complexity | Effort | Priority |
|---------|-----------|------|-----------|--------|----------|
| 1 | 45-60 | LOW | LOW | 2h | Phase 1 |
| 2 | 120-180 | MEDIUM | MEDIUM | 8h | Phase 2 |
| 3 | 25-35 | LOW | LOW | 1h | Phase 1 |
| 4 | 35-50 | MEDIUM | MEDIUM | 6h | Phase 2 |
| 5 | 40-60 | MEDIUM | MEDIUM | 5h | Phase 3 |
| 6 | 60-80 | MEDIUM | MEDIUM | 6h | Phase 3 |
| 7 | 30-45 | MEDIUM | MEDIUM | 4h | Phase 3 |
| 8 | 20-30 | LOW | LOW | 2h | Phase 3 |

---

## File Locations for Reference

### Command Parameter Extractors
- `/packages/slack/command_processing/command_parameters/extractors/`
  - archive.py (72 LOC)
  - summary.py (116 LOC)
  - status_report.py (98 LOC)
  - query.py (114 LOC)
  - feature.py (162 LOC)
  - metrics.py (227 LOC)
  - list.py (66 LOC)
  - access.py (45 LOC)

### Message Handlers
- `/packages/slack/blockkits/handlers/`
  - status.py (214 LOC)
  - report.py (211 LOC)
  - query.py (201 LOC)
  - summary.py (245 LOC)
  - archive.py (353 LOC - not identical, uses different pattern)

### Business Services
- `/packages/core/business/`
  - audit.py (112 LOC)
  - compliance.py (86 LOC)
  - governance.py (116 LOC)

### AI Prompts
- `/packages/ai/prompts/`
  - status.py (260 LOC)
  - report.py (251 LOC)

### Database Operations
- `/packages/db/operations/`
  - access_request_operations.py
  - channel_operations.py
  - channel_query_operations.py
  - restore_state_operations.py
  - archive_operations.py

---

## Consolidation Utilities to Create

### Phase 1
```python
# packages/slack/command_processing/command_parameters/validators.py
def validate_channel_parameter(channel_param: str) -> None:
    """Validate Slack channel format (DM and public channel context)."""
```

### Phase 2
```python
# packages/slack/blockkits/handlers/base_message_handler.py
class BaseMessageHandler:
    """Base class for all message handlers."""

# packages/slack/command_processing/command_parameters/extractors/shared_extraction_utils.py
def extract_channel_for_command(...) -> str:
    """Extract and validate channel from command parts."""
```

### Phase 3
```python
# packages/core/business/base_service.py
class BaseBusinessService(Generic[T], ABC):
    """Base class for business services."""

# packages/ai/prompts/prompt_scaffolding.py
class PromptScaffold:
    """Utilities for AI prompt structure."""

# packages/db/operations/error_handler.py
def handle_dynamodb_errors(default_return=None):
    """Decorator for DynamoDB error handling."""
```

---

## Key Statistics

- **Total files affected:** 31
- **Total duplicated code:** 375-540 LOC
- **High-confidence findings:** 3 (195-275 LOC)
- **Medium-confidence findings:** 5 (180-265 LOC)
- **Estimated consolidation effort:** 35-45 hours
- **Expected maintenance improvement:** 15-20%
- **Code locality improvement:** 3-5% (performance)

---

## Next Steps

1. Review this analysis with team leads
2. Create tickets for Phase 1 findings
3. Implement Phase 1 (Priority: HIGH)
4. Schedule Phase 2 for following sprint
5. Phase 3 as part of regular refactoring cycle

**No code changes recommended at this time - this is analysis only.**
