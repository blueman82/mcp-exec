# TDD RED PHASE: iPaaS x-authorization Header - COMPLETE ✅

## Summary

Following TDD methodology, we have successfully completed the **RED phase** by writing failing tests that document the expected behavior for PAT authentication through iPaaS.

---

## Context

We've manually verified that PAT operations work through iPaaS when using these headers:

```bash
Authorization: {IMS_TOKEN}
x-authorization: Bearer {PAT_TOKEN}
Api_key: {IPAAS_API_KEY}
```

**Current implementation (WRONG):**
- Sends `Username` and `Password` headers
- Function signature: `constructIpaasHeaders(imsToken, apiKey, username?, password?)`

**Expected implementation (CORRECT):**
- Sends `x-authorization: Bearer {PAT}` header
- Function signature: `constructIpaasHeaders(imsToken, apiKey, pat?, username?, password?)`
- PAT takes precedence over Username/Password

---

## Test File Created

**Location:** `/Users/harrison/Documents/Github/camp-ops-emea/ketchup-jira-pat-migration/ketchup/corp_jira_mcp/tests/constructIpaasHeaders.test.ts`

---

## Test Results (RED PHASE - Expected Failures)

```
Test Suites: 1 failed, 1 total
Tests:       4 failed, 2 passed, 6 total
```

### FAILING Tests (Expected ❌)

1. **"should include x-authorization Bearer header when PAT is provided"**
   - Expected: `headers['x-authorization']` = `"Bearer test-pat-token-12345"`
   - Received: `undefined`
   - Reason: x-authorization header doesn't exist in current implementation

2. **"should NOT include Username header when PAT is provided"**
   - Expected: `headers['Username']` = `undefined`
   - Received: `"test-pat-token"` (3rd parameter is treated as username)
   - Reason: Current implementation uses 3rd param as username, not PAT

3. **"should format x-authorization with Bearer prefix correctly"**
   - Expected: `headers['x-authorization']` = `"Bearer my-super-secret-pat-abc123xyz"`
   - Received: `undefined`
   - Reason: x-authorization header doesn't exist

4. **"should NOT include Username/Password when both PAT and credentials are provided"**
   - Expected: PAT should take precedence, no Username/Password headers
   - Received: `undefined` for x-authorization
   - Reason: Function doesn't support PAT parameter yet

### PASSING Tests (Control Tests ✅)

5. **"should NOT include x-authorization header when PAT is not provided"**
   - This validates that x-authorization should only exist when PAT is provided
   - Passes because x-authorization doesn't exist yet (expected behavior when no PAT)

6. **"should use Username/Password headers when PAT is not provided but username/password are"**
   - This validates backward compatibility
   - Current implementation correctly uses Username/Password when provided
   - This behavior must be preserved after implementing PAT support

---

## Implementation Changes Required

### File to Modify
`/Users/harrison/Documents/Github/camp-ops-emea/ketchup-jira-pat-migration/ketchup/corp_jira_mcp/common/utils.ts`

### Function to Update
`constructIpaasHeaders()`

### Required Changes

**Current signature:**
```typescript
export function constructIpaasHeaders(
  imsToken: string,
  apiKey: string,
  username?: string,
  password?: string
): Record<string, string>
```

**New signature:**
```typescript
export function constructIpaasHeaders(
  imsToken: string,
  apiKey: string,
  pat?: string,           // NEW: PAT takes precedence
  username?: string,
  password?: string
): Record<string, string>
```

**Logic changes:**
1. If `pat` is provided:
   - Set `x-authorization: Bearer {pat}` header
   - Do NOT set `Username` or `Password` headers
2. If `pat` is NOT provided:
   - Fall back to current behavior (use Username/Password if provided)
   - Do NOT set `x-authorization` header

---

## Next Steps (GREEN PHASE)

1. **Implement the fix** in `constructIpaasHeaders()`
2. **Update all call sites** to pass PAT parameter
3. **Run tests** - they should now PASS
4. **Verify integration** with real JIRA operations

---

## Test Command

```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/ketchup-jira-pat-migration/ketchup/corp_jira_mcp
npm test -- tests/constructIpaasHeaders.test.ts
```

---

## TDD Phases

- ✅ **RED**: Write failing tests (COMPLETE)
- ⏳ **GREEN**: Implement code to make tests pass (NEXT)
- ⏳ **REFACTOR**: Clean up and optimize (AFTER GREEN)

---

## Manual Verification Context

We've already confirmed via manual testing that these headers work:

```typescript
{
  Authorization: 'IMS_TOKEN',
  'x-authorization': 'Bearer PAT_TOKEN',
  Api_key: 'IPAAS_API_KEY'
}
```

The tests now encode this manual verification into automated tests, following TDD best practices.
