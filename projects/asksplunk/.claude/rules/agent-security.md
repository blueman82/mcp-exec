---
paths:
  - "src/asksplunk/agent/**"
---
# Agent Security Rules

## Content Filter
- All user input passes through OWASP prompt injection filter BEFORE reaching the agent
- Filter runs in `content_filter.py` — never bypass it for "convenience"
- Reject input that matches known injection patterns (role manipulation, instruction override)

## GPT Output is Untrusted
- Never insert GPT responses directly into Slack without sanitization
- Never use GPT output in shell commands, SQL queries, or file paths
- Never log GPT response content (privacy rule)

## State Machine Discipline
- Agent uses 7-state enum: INITIALIZE, EVALUATE, CLARIFY, WAIT, REFINE, GENERATE, COMPLETE
- No ad-hoc state additions without updating the enum and state transition documentation
- Confidence evaluation must use tool calling, not inline text parsing

## Function Definitions
- GPT-5 function/tool definitions must have explicit parameter descriptions
- Required parameters must be marked as required in the schema
- Never add optional parameters that change security behavior
