---
paths:
  - "tests/**/*.py"
---
# Testing Rules

## TDD Approach
1. Write test FIRST
2. Write minimal code to pass
3. Refactor while green

## Async Tests
- Use `pytest-asyncio` with `asyncio_mode="auto"` (configured in pyproject.toml)
- All async test functions are auto-detected — no `@pytest.mark.asyncio` needed
- Use `AsyncMock` for async context managers and coroutines

## Coverage
- Minimum 80% (`fail_under = 80`)
- Run: `pytest tests/unit/ --cov=src/asksplunk --cov-report=html`

## Test Organization
- `tests/unit/` — Fast, isolated, mock all external services
- `tests/integration/` — Marked with `@pytest.mark.integration`, may hit real services
- Use `moto` for AWS service mocking (DynamoDB, Secrets Manager)

## Privacy in Tests
- **No real message content** in test fixtures — use generic placeholders
- **No real user IDs** — use `U_TEST_USER`, `C_TEST_CHANNEL` etc.
- **No real tokens** — use `xoxb-test-token-placeholder`

## Naming
- Test files: `test_<module>.py`
- Test functions: `test_<behavior>_<condition>` (e.g., `test_delete_session_verifies_removal`)
- Fixtures: descriptive, scoped appropriately (`session`, `module`, `function`)
