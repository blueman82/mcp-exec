"""
status.py — Status Report Prompt

Generates an adaptive status report prompt based on user preferences (detail level, product focus).
Uses XML-tagged sections and few-shot examples following the agent_system.py reference pattern.

Note: COMMON_GUIDELINES_PROMPT is prepended at runtime in model_prompts.py.
"""

from typing import Any, Dict, Optional

from packages.core.config.feature_flags import FeatureFlags


def get_status_prompt(user_prefs: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate an adaptive status report prompt based on user preferences.

    Args:
        user_prefs: Optional dictionary with keys:
            - detail_level: "minimal", "balanced" (default), "detailed"
            - product_focus: list of product names or ["all_products"] (default)
            - role: user's role description (default: "incident response analyst")

    Returns:
        Complete prompt string ready for concatenation with COMMON_GUIDELINES_PROMPT.
    """
    # Extract preferences with sensible defaults
    prefs = user_prefs or {}
    detail_level = prefs.get("detail_level", "balanced")
    product_focus = prefs.get("product_focus", ["all_products"])
    role = prefs.get("role", "incident response analyst")

    # Product focus guidance
    if "all_products" in product_focus:
        product_guidance = "Cover all Adobe products mentioned."
    else:
        products = ", ".join(product_focus)
        product_guidance = f"Focus on: {products}. Omit other products unless critical."

    # Build per-level prompt sections
    if detail_level == "high-level":
        prompt = _build_high_level_status_prompt(role, product_guidance)
    elif detail_level == "technical":
        prompt = _build_technical_status_prompt(role, product_guidance)
    else:
        prompt = _build_balanced_status_prompt(role, product_guidance)

<response_example>
*Example: Production database connectivity incident*

:traffic_light: *Current Status:*
• *CSO Phase:* Phase 2
• *Status:* *Active*
• *Last Update:* *2026-03-10 14:32:00 UTC*

:mag: *Key Information:*
• Database connection pool exhaustion affecting all API services
• ~15% request failure rate; monitoring shows recovery in progress
• <@U0F3P2Q> identified stale connection cleanup process hung on primary DB node
• Secondary failover delayed due to replication lag (8 minutes behind)
• Load balancer draining connections; estimated resolution within 30 minutes

:construction_worker: *Engineers Actively Investigating:*
• *<@U0F3P2Q>*: Diagnosing connection cleanup process hang
• *<@U2K1L9>*: Monitoring replication lag and failover readiness

:calendar: *Timeline:*
• *10-Mar-2026, 14:10 UTC:* API error rate spike detected (5xx responses)
• *10-Mar-2026, 14:15 UTC:* DBA identified connection pool at 98% capacity
• *10-Mar-2026, 14:20 UTC:* Cleanup process found hung; manual restart initiated
• *10-Mar-2026, 14:32 UTC:* Pool returning to normal; monitoring active

:arrow_forward: *Next Steps:*
• Monitor connection pool metrics; if lag >5min, trigger failover (estimated 14:45 UTC)
• Implement automated cleanup timeout (owner: <@U0F3P2Q>, target: EOD 2026-03-10)

:jira-logo: *JIRA Tickets & Work Done:*
• <https://jira.corp.adobe.com/browse/CPGNTT-5642|CPGNTT-5642> — Database connection pool exhaustion during peak load (Status: In Progress, Assignee: <@U0F3P2Q>)
  • *Description Summary:*
    • Connection cleanup process hangs under peak load, exhausting pool
    • Affects all APIs; ~15% request failures observed
    • Workaround: manual process restart; permanent fix: implement timeout
  • *Recent Comments:*
    • *10-Mar-2026, 14:20 UTC - <@U0F3P2Q>:*
      Identified hung cleanup process; restarted manually. Root cause: missing timeout on subprocess.call(). Implementing timeout wrapper for permanent fix.
    • *10-Mar-2026, 14:28 UTC - <@U2K1L9>:*
      Replication lag at 8 minutes; secondary ready for failover if needed. Monitoring connection pool; recovery progressing.

:link: *References:*
• *Support Ticket:* <https://jira.corp.adobe.com/browse/CPGNREQ-9201|CPGNREQ-9201>
• *Channel:* <#C03PWLW9P5H|incidents>
</response_example>

""".format(
        role=role,
        detail_guidance=detail_guidance,
        technical_section=technical_section,
        product_guidance=product_guidance,
    )

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += (
            "\n<json_output>\n"
            'Return response as JSON: {"response_text": "your complete formatted report"}\n'
            "</json_output>"
        )

    return prompt
