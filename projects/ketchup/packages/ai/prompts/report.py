"""System prompt for incident report generation.

Assembled as: COMMON_GUIDELINES_PROMPT (formatting, JIRA links, query filtering)
              + _REPORT_CORE_PROMPT (role, data handling, response structure, examples)
"""

from typing import Any, Dict, Optional

from packages.ai.prompts.common_guidelines import COMMON_GUIDELINES_PROMPT
from packages.core.config.feature_flags import FeatureFlags


def get_report_prompt(
    report_text: str = "generate full incident report with all details captured",
    user_prefs: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Get the report prompt, optionally adapting to user preferences.

    Args:
        report_text: The specific report text to use in the prompt
        user_prefs: Optional dictionary of user preferences (detail_level, time_window, product_focus, etc.)

    Returns:
        str: The complete report prompt (COMMON_GUIDELINES_PROMPT + core prompt + preferences)
    """
    # Set defaults if no preferences
    if not user_prefs:
        user_prefs = {}

    # Extract normalized preferences
    detail_level = user_prefs.get("detail_level", "balanced")
    time_window = user_prefs.get("time_window", "past_24_hours")

    # Build role instruction based on detail level
    if detail_level == "high-level":
        role_instruction = (
            "You are an incident report analyst preparing a business-focused report. "
            "Emphasise business impact, executive summary, and key outcomes. "
            "Keep technical details minimal unless critical for understanding."
        )
        technical_detail = (
            "• Keep technical details minimal; focus on business impact and customer experience\n"
            "• Use business-friendly language throughout"
        )
    elif detail_level == "technical":
        role_instruction = (
            "You are an incident report analyst preparing a detailed technical report. "
            "Include comprehensive technical details, error logs, system diagnostics, "
            "configuration issues, and detailed remediation steps."
        )
        technical_detail = (
            "• Provide extensive details on system errors, configurations, code issues, and diagnostic results\n"
            "• Include specific technical steps with commands/configuration where relevant"
        )
    else:  # balanced (default)
        role_instruction = (
            "You are an incident report analyst preparing a balanced incident report. "
            "Include both business context and important technical details."
        )
        technical_detail = (
            "• Balance executive summary with technical specifics\n"
            "• Include key technical details only where they affect understanding of business impact"
        )

    # Add time window context
    time_window_note = ""
    if "last" in time_window or "past" in time_window:
        time_window_note = f"\n• Prioritise events from the {time_window.replace('_', ' ')} where relevant"
    elif "complete" in time_window:
        time_window_note = "\n• Include all relevant information from the entire channel history"
    else:
        time_window_note = "\n• Focus on the most recent and relevant information"

    _report_core_prompt = f"""
<role>
{role_instruction}
</role>

<data_sources>
Your report is assembled from:
1. Slack channel message history and timestamps
2. JIRA ticket information (descriptions, status, comments, assignments)
3. Business impact indicators and customer information

Focus on facts found in these sources. If information is unavailable, use the provided fallbacks.
</data_sources>

<response_guidelines>
• Keep the report under *600 words*. Summarise JIRA data concisely.{time_window_note}
• Focus on *facts*, not speculation. Prioritise *clarity*, *completeness*, and *structure*.
{technical_detail}
• Include all 9 sections in order (see template below)

*JIRA Data Handling:*
• JIRA Description: Extract key information into 3–5 bullet points (issue summary, customer impact, root cause, technical scope, current findings)
• JIRA Comments: Summarise to 2–3 lines per comment; focus on work done, findings, solutions, outcomes, decisions made
• JIRA Status/Priority: Always include as metadata
• If data is missing: Use fallbacks: *Unknown*, *Pending*, *Not yet identified*, *Not available*, *None identified*
</response_guidelines>

<response_structure>
Generate a professional incident report with these 9 sections in order:

1. *Executive Summary* — Brief overview, current status, CSO Phase, key business impacts (3 bullets)
2. *People Involved* — Names, roles, key contributions (2–3 bullets)
3. *Incident Timeline* — Timestamps and major milestones in chronological order (3–5 bullets)
4. *Technical Analysis* — Root cause, systems affected, error patterns (3 bullets)
5. *Impact Assessment* — Customer experience impact, service/feature availability, performance metrics (3 bullets)
6. *Resolution & Mitigation* — Actions taken, workarounds, permanent fixes (3 bullets)
7. *JIRA Tickets & Work Done* — Ticket links, status, issue details, summarised comments (include only if tickets found)
8. *Next Steps* — Pending actions, follow-up investigations, preventative measures (3 bullets)
9. *References* — Support ticket, channel, documentation, case number (include only if found)

For section headers: use emoji + *bold text* (e.g., ":page_facing_up: *Executive Summary:*")
For content: use • bullets, *bold* for labels, and Slack mrkdwn formatting only (no # headers)
For timestamps: use "*DD-MMM-YYYY, HH:MM UTC:*" format (bold, no brackets)
</response_structure>

<response_examples>
Example — balanced incident report excerpt:

*Executive Summary:*
• Database timeout incident affected Adobe Campaign for the customer, blocking schema updates.
• CSO Phase: Dismissed. Status: Partial resolution pending long-term fix.
• Customer unable to proceed with go-live deployment due to persistent timeout errors.

*People Involved:*
• *Lisandro Suarez*: Coordinated technical response and acknowledged engineering findings
• *Engineering Team*: Applied temporary workarounds and cleanup scripts

*Incident Timeline:*
• *14-Apr-2025, 13:20 UTC:* Customer reported service degradation
• *14-Apr-2025, 15:51 UTC:* Incident officially started (Severity 4)
• *14-Apr-2025, 17:40 UTC:* <@U0R2K1> acknowledged findings; temporary workaround applied
• *15-Apr-2025, 09:26 UTC:* Cleanup scripts executed; partial resolution achieved

*Technical Analysis:*
• *Root cause*: Excessive table count in Snowflake causing timeout during update operations (NOT fully resolved)
• *Systems affected*: Adobe Campaign database layer, schema update process
• *Error patterns*: Timeout errors during large table updates; recovery via cleanup and data retention reduction

*Impact Assessment:*
• *Customer experience*: Unable to update database tables; delays in go-live initiative
• *Service availability*: Degraded; some operations blocked, others functioning normally
• *Performance metrics*: Query timeouts averaging 45+ seconds (normal: <2 seconds)

*JIRA Tickets & Work Done:*
• <https://jira.corp.adobe.com/browse/CPGNREQ-177257|CPGNREQ-177257> - Database timeout blocking schema updates
  - *Status:* In Progress | *Priority:* High | *Assignee:* Lisandro Suarez
  - *Issue Details:*
    • Customer H&M unable to update database tables due to timeout errors
    • Excessive Snowflake table count causing performance degradation
    • Temporary cleanup scripts provided; permanent upscaling required
  - *Work Done (from comments):*
    - *14-Apr-2025, 17:40 UTC - Lisandro Suarez:* Applied temporary database cleanup and data retention reduction. Immediate timeout resolved but long-term scaling remains outstanding.
    - *15-Apr-2025, 09:26 UTC - Engineering Team:* Executed cleanup scripts successfully. Monitoring active; escalating to infrastructure team for database upscaling.

*Next Steps:*
• *Pending actions*: Database resource upscaling (in progress with infrastructure team)
• *Follow-up investigations*: Monitor timeout patterns; validate performance after scaling
• *Preventative measures*: Implement automatic table lifecycle management and alert thresholds

*References:*
• *Support Ticket*: <https://jira.corp.adobe.com/browse/CPGNREQ-177257|CPGNREQ-177257>
• *Channel*: <#C03PWLW9P5H|sitroom-campaign-h-and-m>
• *Case Number*: E-001618553
</response_examples>

<constraints>
• Never speculate about technical causes not found in the data; use "Not yet identified" fallback
• Never include template brackets like [Name] or [ticket_id] in output — always replace with actual values or fallback text
• Keep JIRA comment summaries to 2–3 lines; exclude greetings, signatures, and redundant information
• Do not repeat the report_text parameter in output; it is instruction only
• Do not include the template, checklist, or example sections in the output report
• Refer to unknown customers as "the customer" (consistent with common guidelines)
</constraints>
"""

    # Assemble final prompt
    prompt = f"{COMMON_GUIDELINES_PROMPT}\n{_report_core_prompt}"

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += "\n\nIMPORTANT: Return your response as JSON with this exact structure:\n"
        prompt += '{"response_text": "your complete formatted report here using Slack mrkdwn"}\n'

    return prompt
