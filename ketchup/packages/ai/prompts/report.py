"""
Report prompt generation function.
"""

from typing import Any, Dict, Optional

from packages.core.config.feature_flags import FeatureFlags


def get_report_prompt(
    report_text: str = "generate full incident report with all details captured",
    user_prefs: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Get the report prompt, optionally adapting to user preferences.

    Args:
        report_text: The specific report text to use in the prompt
        user_prefs: Optional dictionary of user preferences (role, product_focus, detail_level, etc.)

    Returns:
        str: The report prompt
    """
    # Set defaults if no preferences
    if not user_prefs:
        user_prefs = {}

    # Extract normalized preferences (these should already be normalized by home.py)
    role = "incident response analyst"
    detail_level = user_prefs.get("detail_level", "balanced")
    time_window = user_prefs.get(
        "time_window", "past_24_hours"
    )  # Changed from "past 24 hours"

    # Build instruction based on detail level
    if detail_level == "high-level":
        instruction = (
            f"As a {role}, prepare a high-level business-focused incident report. "
            f"Focus on business impact, executive summary, and key outcomes. "
            f"Keep technical details minimal unless critical for understanding."
        )
    elif detail_level == "technical":
        instruction = (
            f"As a {role}, prepare a detailed technical incident report. "
            f"Include comprehensive technical details, error logs, system diagnostics, "
            f"configuration issues, and detailed remediation steps."
        )
    else:  # balanced
        instruction = (
            f"As a {role}, prepare a balanced incident report. "
            f"Include both business context and important technical details. "
            f"Balance executive summary with technical specifics."
        )

    # Adjust technical content based on detail level
    technical_content = ""
    if detail_level == "technical":
        technical_content = """
• For the Technical Analysis section: Provide extensive details on system errors, configurations, code issues, and diagnostic results
• For the Resolution section: Include specific technical steps taken with commands/configs where relevant
• Add a "Technical Specifications" bullet under each relevant section
"""
    elif detail_level == "high-level":
        technical_content = """
• Keep technical details minimal and focus on business impact
• Emphasize customer experience and business metrics
• Use business-friendly language throughout
"""

    # Add time window note if relevant
    time_window_note = ""
    if "last" in time_window or "past" in time_window:
        time_window_note = (
            f"\n• Focus on events from the {time_window.replace('_', ' ')} if relevant"
        )
    elif "complete" in time_window:
        time_window_note = (
            "\n• Include all relevant information from the entire channel history"
        )
    else:
        time_window_note = "\n• Focus on the most recent and relevant information"

    prompt = f"""
#################################################
BEGINNING OF REPORT INSTRUCTIONS - DO NOT INCLUDE IN OUTPUT
#################################################
:memo: Comprehensive Incident Report Instructions:
{instruction}

• The report focus is: \"{report_text}\""
• Use **British English**, and refer to unknown customers as "the customer".
• Create a professional, comprehensive report suitable for executive review and customer distribution.
• Focus on **facts**, not speculation. Prioritise **clarity**, **completeness**, and **structure**.
• Keep the report under **600 words**. IMPORTANT: Summarize JIRA data concisely.{time_window_note}
• JIRA Formatting Rules:
  1. JIRA Description:
     - Extract key information from descriptions (especially table format) into 3-5 bullet points
     - Focus on: Issue summary, Customer impact, Root cause, Technical scope, Current findings
     - Convert technical details into business-relevant summaries
     - Limit description summary to 5 lines maximum
  2. JIRA Comments:
     - IMPORTANT: The timestamp and commenter name MUST be in bold using ** formatting
     - Format EXACTLY as: - **DD-MMM-YYYY, HH:MM UTC - [Name]:**
     - Summarize each comment to 2-3 lines maximum
     - Focus on: work done, findings, solutions, outcomes, decisions made
     - Exclude implementation details unless critical to understanding
     - Remove greetings, signatures, and redundant information
     - Start each summary line with proper indentation (2 spaces)
• Use only Slack-compatible formatting:
  - Bullet points: '•'
  - Bold text: *text*
  - Emojis: only in section headings
  - Timeline timestamps must NOT use brackets: use "**DD-MMM-YYYY, HH:MM UTC:**" format (bold timestamps)
• If data is missing, use these fallbacks:
  - **CSO Phase**: **Unknown**
  - **Status**: **Pending**
  - **Root Cause**: **Not yet identified**
  - **Metrics**: **Not available**
  - **Next Steps**: **None identified**
{technical_content}
:bookmark_tabs: *Output Format Template*:

:page_facing_up: **Executive Summary:**
• **Brief overview of the incident**
• **Current status and CSO Phase**
• **Key impacts and business implications** (1-2 bullets)

:busts_in_silhouette: **People Involved:**
• **[Name]**: [Role and key contributions]
• **[Name]**: [Role and key contributions]

:calendar: **Incident Timeline:**
• **DD-MMM-YYYY, HH:MM UTC:** First detection/report
• **DD-MMM-YYYY, HH:MM UTC:** [Major milestone or event]
• **DD-MMM-YYYY, HH:MM UTC:** [Major milestone or event]
• **DD-MMM-YYYY, HH:MM UTC:** [Resolution activities if any]

:mag: **Technical Analysis:**
• **Root cause**: [If known, else use fallback]
• **Systems affected**: [Applications, infrastructure, etc.]
• **Error patterns and behaviours**: [If applicable]

:chart_with_downwards_trend: **Impact Assessment:**
• **Customer experience impact**: [End-user symptoms]
• **Service/feature availability**: [Outages, degradation]
• **Performance metrics**: [If available, else fallback]

:wrench: **Resolution & Mitigation:**
• **Actions taken**: [Steps by support/engineering]
• **Workarounds implemented**: [If any]
• **Permanent fixes**: [If deployed]

:jira-logo: **JIRA Tickets & Work Done:**
• <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]> - [Summary]
  - **Status:** [Current Status] | **Priority:** [Priority] | **Assignee:** [Name]
  - **Issue Details:**
    • [Key point 1 from description - customer impact]
    • [Key point 2 from description - technical scope/systems affected]
    • [Key point 3 from description - root cause/findings]
  - **Work Done (from comments):**
    - **DD-MMM-YYYY, HH:MM UTC - [Commenter]:**
      [Summarize comment to 2-3 lines focusing on work done and outcomes]
      [Include: actions taken, findings, solutions implemented, issues resolved]
• <https://jira.corp.adobe.com/browse/[ticket_id2]|[ticket_id2]> - [Summary]
  - **Status:** [Current Status] | **Priority:** [Priority] | **Assignee:** [Name]
  - **Issue Details:**
    • [Key point 1 from description]
    • [Key point 2 from description]
  - **Work Done (from comments):**
    - **DD-MMM-YYYY, HH:MM UTC - [Commenter]:**
      [Summarize comment to 2-3 lines focusing on work done and outcomes]
      [Include: actions taken, findings, solutions implemented, issues resolved]
*(Only include this section if JIRA tickets are found related to the incident)*

:arrow_forward: **Next Steps:**
• **Pending actions**: [Ongoing efforts or *None identified*]
• **Follow-up investigations**: [If any]
• **Preventative measures**: [Process or platform changes]

:link: **References:**
• **Support Ticket**: <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]> *(or "NOT YET AVAILABLE")*
• **Channel**: <#channel_id|channel_name>
• **Documentation**: [If found, include it; otherwise DO NOT include this bullet]
• **Case Number:** E-4234234 *(Only include Case Number if it is found else DO NOT INCLUDE THAT BULLET)*

#################################################
END OF REPORT INSTRUCTIONS - DO NOT INCLUDE IN OUTPUT
#################################################

#################################################
BEGINNING OF EXAMPLE OUTPUT - DO NOT INCLUDE IN OUTPUT
#################################################
:page_facing_up: **Executive Summary:**
• A critical incident was initiated due to service degradation issues with Adobe Campaign for H&M, linked to database timeout errors.
• Current status: The CSO has been dismissed, but the issue is not fully resolved. CSO Phase: Dismissed.
• Key impacts include the inability for H&M to update database tables, affecting important go-live initiatives.
:busts_in_silhouette: **People Involved:**
• **Lisandro Suarez**: Acknowledged work notes and coordinated technical response
• **Engineering Team**: Applied temporary database updates and cleanup scripts
:calendar: **Incident Timeline:**
• **14-Apr-2025, 13:20 UTC:** First detection/report
• **14-Apr-2025, 15:51 UTC:** Incident officially started with Sev 4 classification
• **14-Apr-2025, 17:40 UTC:** Lisandro Suarez acknowledged the work notes
• **14-Apr-2025, 18:36 UTC:** Channel renamed indicating the CSO dismissal
• **15-Apr-2025, 09:26 UTC:** Successful temporary database update applied
:mag: **Technical Analysis:**
• **Root cause**: Not yet identified.
• **Systems affected**: Adobe Campaign, specifically the database update process.
• **Error patterns and behaviours**: Timeout errors during database update due to excessive tables in Snowflake.
:chart_with_downwards_trend: **Impact Assessment:**
• **Customer experience impact**: H&M unable to update database tables, causing delays in schema changes.
• **Service/feature availability**: Service degradation due to database timeout.
• **Performance metrics**: Not available.
:wrench: **Resolution & Mitigation:**
• **Actions taken**: Cleanup scripts were run, and temporary database updates were applied.
• **Workarounds implemented**: Suggested reducing data retention periods to allow table deletion.
• **Permanent fixes**: Not yet deployed.
:arrow_forward: **Next Steps:**
• **Pending actions**: Determine long-term solutions, possibly involving database upscaling.
• **Follow-up investigations**: Continued monitoring and potential coordination with engineering.
• **Preventative measures**: Consideration of upsizing database resources temporarily.
:link: **References:**
• **Support Ticket**: <https://jira.corp.adobe.com/browse/CPGNREQ-177257|CPGNREQ-177257>
• **Channel**: #sitroom_202504140040_acc_h-and-m_74440
• **Documentation**: Cleanup Guide
• **Case Number**: E-001618553

#################################################
END OF EXAMPLE OUTPUT - DO NOT INCLUDE IN OUTPUT
#################################################
:white_check_mark: *Self-Verification Checklist* (Internal Use Only):
• All 8-9 main sections are included in order (Executive Summary, People Involved, Timeline, Technical Analysis, Impact Assessment, Resolution & Mitigation, JIRA Tickets if found, Next Steps, References)
• CSO Phase and Status use placeholders if missing
• Documentation and Case Number MUST be included if found else DO NOT INCLUDE THOSE BULLETS
• Timeline timestamps must NOT use brackets: use "**DD-MMM-YYYY, HH:MM UTC:**" format exactly (bold timestamps)
• JIRA tickets MUST be formatted as <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]>.
• Channel links MUST be formatted as <#channel_id|channel_name>.
• Bullet count is controlled (1-3 for most sections, 2-5 for Timeline)
• Total word count under 500
• Uses only '•', *bold*, and emojis in section headings
• No abbreviations' meanings are guessed
• Uses British English
• Refers to unknown customers as "the customer"
• People Involved section lists key contributors and their roles
• DO NOT include any of the EXAMPLES in your output
If any requirement is not met, regenerate your output. Do not include the Self-Verification Checklist in the output.
"""

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += '\n\nIMPORTANT: Return your response as JSON with this exact structure:\n'
        prompt += '{"response_text": "your complete formatted response here using markdown"}\n'

    return prompt
