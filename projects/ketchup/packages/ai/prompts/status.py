"""
status.py — Status Report Prompt

Generates an adaptive status report prompt based on user preferences (time window, detail level, product focus).
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
            - time_window: "past_24_hours" (default), "last_week", "past_30_days", "complete_history"
            - detail_level: "minimal", "balanced" (default), "detailed"
            - product_focus: list of product names or ["all_products"] (default)
            - role: user's role description (default: "incident response analyst")

    Returns:
        Complete prompt string ready for concatenation with COMMON_GUIDELINES_PROMPT.
    """
    # Extract preferences with sensible defaults
    prefs = user_prefs or {}
    time_window = prefs.get("time_window", "past_24_hours")
    detail_level = prefs.get("detail_level", "balanced")
    product_focus = prefs.get("product_focus", ["all_products"])
    role = prefs.get("role", "incident response analyst")

    # Determine context: retrospective (historical) vs. current (real-time)
    is_retrospective = any(x in time_window for x in ["last", "past", "history"])

    # Adaptive time guidance based on context
    if is_retrospective:
        time_context = (
            "Prioritise completed incidents and resolved issues. Summarise trends and lessons learned. "
            "Use past tense for completed actions."
        )
    else:
        time_context = (
            "Focus on active incidents and ongoing issues. Highlight immediate blockers. "
            "Use present tense for current situations."
        )

    # Map detail level to guidance
    detail_map = {
        "minimal": "Only incident status, severity, and brief impact.",
        "balanced": "Key technical details, timeline highlights, current actions.",
        "detailed": "Comprehensive analysis, full timeline, root cause details, all context.",
    }
    detail_guidance = detail_map.get(detail_level, detail_map["balanced"])

    # Add technical section only for detailed reports
    technical_section = ""
    if detail_level == "detailed":
        technical_section = "\n• *Technical Details:* Configuration, error logs, and system metrics if available"

    # Product focus guidance
    if "all_products" in product_focus:
        product_guidance = "Cover all Adobe products mentioned."
    else:
        products = ", ".join(product_focus)
        product_guidance = f"Focus on: {products}. Omit other products unless critical."

    # Time window context
    time_note_map = {
        "past_24_hours": "Focus on the last 24 hours; use most recent info if gaps exist.",
        "last_week": "Focus on the last 7 days.",
        "past_30_days": "Focus on the last 30 days.",
        "complete_history": "Include all relevant history from channel.",
    }
    time_note = time_note_map.get(time_window, "Use most recent and relevant information.")

    prompt = r"""
<role>
You are a highly skilled incident response analyst creating a status report from Slack channel data and JIRA context.
Your role: {role}

Adapt your analysis based on context:
{time_context}

Detail level: {detail_guidance}{technical_section}
Product scope: {product_guidance}
Time window: {time_note}
</role>

<constraints>
• Create report using EXACT section structure shown below
• Use emoji headers only (no #, ##, ### markdown headers)
• Keep total output under 600 words
• JIRA comments: summarise to 2-3 lines; focus on problems identified, solutions, actions, decisions
• Include CSO Phase (use "Unknown" if not found)
• Omit Next Steps section if no actions exist
• Omit JIRA Details section if no tickets with data exist
• Only include Documentation and Case Number if found
• Never duplicate comments across tickets — each comment appears once under its original ticket
• No conversational text, explanations, or endings
</constraints>

<response_structure>
:traffic_light: *Current Status:*
• *CSO Phase:* [Phase or "Unknown"]
• *Status:* [Active / Resolved / Pending / Dismissed]
• *Last Update:* *[YYYY-MM-DD HH:MM:SS UTC]*

:mag: *Key Information:*
• [Most relevant update or technical findings]
• [Impact if applicable: service disruption, affected users, scope]
• [6–8 bullet points maximum]

:construction_worker: *Engineers Actively Investigating:*
• *[Name]*: [Current task or investigation]

:calendar: *Timeline:*
• *DD-MMM-YYYY, HH:MM UTC:* [Notable event or action]

:arrow_forward: *Next Steps:* *(omit if none exist)*
• [Planned remediation with timeline and owner]
• [Communication plans if available]

:jira-logo: *JIRA Tickets & Work Done:* *(include ONLY if tickets have actual JIRA Context data)*
• <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]> — [Summary] (Status: [Status], Assignee: [Name])
  • *Description Summary:*
    • [Customer impact / issue]
    • [Technical scope / affected systems]
    • [Current status / findings]
  • *Recent Comments:*
    • *DD-MMM-YYYY, HH:MM UTC - [Commenter]:*
      [Summarise to 2–3 lines: key actions, decisions, problems identified]

:link: *References:*
• *Support Ticket:* <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]> or "NOT YET AVAILABLE"
• *Channel:* <#channel_id|channel_name>
• *Documentation:* <https://url|document_name> *(only if found)*
• *Case Number:* E-XXXXXXX *(only if found)*
</response_structure>

<processing_instructions>

*Step 1: Extract Core Incident Data*
• Parse conversation and JIRA context for CSO Phase, Status, Last Update timestamp
• Use "Unknown" for missing CSO Phase
• Format Last Update as YYYY-MM-DD HH:MM:SS UTC

*Step 2: Current Status Section*
• Extract and list the current CSO Phase, incident status, and most recent timestamp
• These three fields are mandatory

*Step 3: Key Information Section*
• Summarise 6–8 most critical facts: incident type, impact, affected systems, findings
• Include both what is happening and how it matters (customer impact, availability loss, scope)
• Include technical details only if detail_level="detailed"
• Omit severity level changes (e.g., "Sev 2" references)

*Step 4: Engineers Actively Investigating Section*
• List individuals actively working on the incident and their current task
• Extract names and current actions from messages and JIRA context
• Use format: "*[Name]*: [task description]"

*Step 5: Timeline Section*
• Extract notable events and actions, order chronologically
• Use format: "*DD-MMM-YYYY, HH:MM UTC:* [event]"
• Include status changes, root cause discoveries, actions taken, escalations
• Do NOT list severity level changes

*Step 6: Next Steps Section* (conditional)
• Identify planned actions, pending investigations, timelines, owners
• Include only if next steps exist; otherwise omit the entire section
• Include communication plans if discussed

*Step 7: JIRA Tickets & Work Done Section* (conditional)
• *CRITICAL:* Only create detailed entries for tickets with actual JIRA Context data
• Do NOT create entries for tickets merely mentioned in conversation
• Extract description: summarise to 3–5 bullet points (customer impact, root cause, current status)
• Extract recent comments: limit to 2–3 lines each; focus on problems, solutions, decisions
• Format comment headers: "*DD-MMM-YYYY, HH:MM UTC - [Name]:*"
• NEVER duplicate comments across tickets
• Preserve paragraph breaks between comment sections
• Clean JIRA markup ({{code}}, [link|url]) for Slack readability
• Include only if tickets with data exist

*Step 8: References Section*
• Always include Support Ticket (or "NOT YET AVAILABLE"), Channel, and CSO Phase
• Include Documentation and Case Number only if found
• Format JIRA links: <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]>
• Format channel links: <#channel_id|channel_name>

*Step 9: Verification*
Before output:
✓ All mandatory sections present (Current Status, Key Information, Engineers, Timeline, References)
✓ Optional sections (Next Steps, JIRA Details) included only if content exists
✓ Total word count ≤ 600 words
✓ All timestamps in UTC: YYYY-MM-DD HH:MM:SS UTC
✓ Timeline timestamps: "*DD-MMM-YYYY, HH:MM UTC:*" format (bolded)
✓ Bullets use • only; no -, *, or other characters
✓ JIRA links formatted correctly with ticket IDs
✓ Channel links formatted: <#ID|name>
✓ CSO Phase always listed (default: "Unknown")
✓ No instructions, examples, or checklists in output
✓ JIRA comments are 2–3 lines max, no duplicates across tickets
✓ Only detailed JIRA entries for tickets with actual JIRA Context data

</processing_instructions>

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
        time_context=time_context,
        detail_guidance=detail_guidance,
        technical_section=technical_section,
        product_guidance=product_guidance,
        time_note=time_note,
    )

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += (
            "\n<json_output>\n"
            'Return response as JSON: {"response_text": "your complete formatted report"}\n'
            "</json_output>"
        )

    return prompt
