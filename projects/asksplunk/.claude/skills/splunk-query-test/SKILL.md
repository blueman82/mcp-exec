---
name: splunk-query-test
description: Test SPL query generation and retrieval quality against Adobe Campaign schema. Use when validating query generation, testing retrieval, or checking schema compliance. Triggers on "test query", "validate SPL", "check retrieval", or explicit /splunk-query-test.
allowed-tools: Read, Bash, Grep, Glob
---
# Splunk Query Test

Test the SPL query generation pipeline against the Adobe Campaign schema.

## Test Steps

### 1. Schema Validation
Read the schema definitions in `docs/schema/` and verify they are complete and correctly formatted. Cross-reference with the indexed chunks in ChromaDB.

### 2. Retrieval Quality Test
Run the retrieval CLI with test queries to evaluate chunk relevance:
```bash
python -m asksplunk.cli.test_retrieval
```

Test with standard queries:
- "Show me failed deliveries in the last 24 hours"
- "Count of broadlog entries by status"
- "Which workflows failed this week"

### 3. Field Name Validation
Verify that the agent orchestrator's GPT-5 system prompt and function definitions reference field names that exist in the schema:
```bash
# Extract field references from orchestrator
rg "index=|sourcetype=|field=" src/asksplunk/agent/orchestrator.py
```

Cross-check against `docs/schema/` for correctness.

### 4. SPL Syntax Validation
Review any example SPL queries in the codebase for syntax correctness:
- Proper `index=` and `sourcetype=` specifications
- Valid `stats`, `eval`, `where`, `rex` usage
- Appropriate time range modifiers (`earliest=`, `latest=`)
- No deprecated SPL commands

### 5. Confidence Evaluation
Review the confidence assessment logic in the orchestrator:
- Does it correctly identify when clarification is needed?
- Are the confidence thresholds appropriate?
- Does it handle ambiguous queries gracefully?

Reference @SCHEMA_REFERENCE.md for field definitions and valid patterns.

## Output
Report findings in categories: SCHEMA, SYNTAX, RETRIEVAL, PROMPT with severity and recommendations.
