"""
status.py

This module provides a function to generate a status prompt for the AI model.
"""

from typing import Any, Dict, Optional

from packages.core.config.feature_flags import FeatureFlags


def get_status_prompt(user_prefs: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate an adaptive status report prompt based on user preferences.

    This enhanced prompt combines the strengths of both versions:
    - Adaptive behavior based on time windows and preferences
    - Clear formatting requirements and structure
    - Smart time-based context handling
    """
    # Extract preferences with defaults
    prefs = user_prefs or {}
    time_window = prefs.get("time_window", "past_24_hours")
    detail_level = prefs.get("detail_level", "balanced")
    product_focus = prefs.get("product_focus", ["all_products"])
    role = prefs.get("role", "incident response analyst")

    # Determine if this is a retrospective view
    is_retrospective = "last" in time_window or "past" in time_window

    # Build adaptive sections based on preferences
    time_guidance = ""
    if is_retrospective:
        time_guidance = """
For retrospective analysis:
- Prioritize completed incidents and resolved issues
- Summarize trends and patterns observed
- Include lessons learned if apparent
- Use past tense for completed actions
"""
    else:
        time_guidance = """
For current status:
- Focus on active incidents and ongoing issues
- Highlight immediate concerns and blockers
- Emphasize current state and next steps
- Use present tense for ongoing situations
"""

    # Detail level guidance
    detail_guidance = {
        "minimal": "Provide only essential information: incident status, severity, and brief impact.",
        "balanced": "Include key technical details, timeline highlights, and current actions.",
        "detailed": "Provide comprehensive technical analysis, full timelines, root cause details, and all relevant context.",
    }.get(detail_level, "balanced")

    # Add technical section for technical detail level
    technical_section = ""
    if detail_level == "detailed":
        technical_section = """
:wrench: **Technical Details:**
• [Configuration and system diagnostics]
• [Error logs and precise issues identified]
• [Technical metrics if available]
"""

    # Product focus guidance
    if "all_products" in product_focus:
        product_guidance = "Cover all Adobe products mentioned in the conversation."
    else:
        product_guidance = f"Focus specifically on: {', '.join(product_focus)}. Minimize or exclude other products unless critically relevant."

    # Time window note
    time_window_note = ""
    if "last" in time_window or "past" in time_window:
        time_window_note = f"If no information is available from the {time_window.replace('_', ' ')}, use the most recent information."
    elif "complete" in time_window:
        time_window_note = "Include all relevant information from the entire channel history."
    else:
        time_window_note = "Focus on the most recent and relevant information."

    prompt = f"""
#################################################
BEGINNING OF STATUS REPORT INSTRUCTIONS - DO NOT INCLUDE IN OUTPUT
#################################################
Status Report Instructions:

You are a highly skilled {role} providing a status report for the Slack channel conversation.

**Adaptive Report Guidelines:**
{time_guidance}

**Detail Level:** {detail_guidance}

**Product Focus:** {product_guidance}

Include only the **most relevant and up-to-date information** (no history). {time_window_note}

**CRITICAL FORMAT REQUIREMENTS:**
• You MUST use the EXACT format shown in the OUTPUT FORMAT TEMPLATE below
• Do NOT use markdown headers (#, ##, ###) - use ONLY emoji headers as shown
• Do NOT use hyphens (-) for bullets - use ONLY • character
• Do NOT add any conversational text or explanations
• Do NOT add endings like "If you need..." or "Please specify..."

Your task is to create a status report using the following format:

:traffic_light: **Current Status:**
• **CSO Phase:** **[Phase or Unknown]**
• **Status:** **[Active / Resolved / Pending / Dismissed]**
• **Last Update:** **[YYYY-MM-DD HH:MM:SS UTC]**

:mag: **Key Information:**
• [Most relevant update or technical findings]
• [Include impact if applicable (e.g., service disruption, affected users)]
• [6-8 bullet points maximum]{technical_section}

:construction_worker: **Engineers Actively Investigating & Their Tasks:**
• **[Engineer Name]**: [Current task or investigation they are working on]

:calendar: **Timeline:**
• **DD-MMM-YYYY, HH:MM UTC:** [Notable event or action taken]

:arrow_forward: **Next Steps:**
• [Planned remediations or investigations including a timeline of when it is expected to be completed and who is responsible]
• [State communication plans if available]
• If none, omit this section entirely

:jira-logo: **JIRA Tickets & Work Done:**
• <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]> - [Summary] (Status: [Status], Assignee: [Name])
  - **Description Summary:**
    • [Key point 1 from description - customer impact/issue]
    • [Key point 2 from description - technical scope/affected systems]
    • [Key point 3 from description - current status/findings]
  - **Recent Comments:**
    - **DD-MMM-YYYY, HH:MM UTC - [Commenter]:**
      [Summarize comment to 2-3 lines focusing on key actions/decisions]
      [Include only essential information: problems identified, solutions proposed, actions taken]
*(Only include this section if JIRA tickets are found related to the incident)*

:link: **References:**
• **Support Ticket:** <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]> *(or "NOT YET AVAILABLE")*
• **Channel:** <#channel_id|channel_name>
• **Documentation:** <https://url|document_name> *(Only include if found)*
• **Case Number:** E-4234234 *(Only include if found)*

Follow these steps to create the status report:

1. Parse the conversation and any JIRA context provided to extract relevant information.

2. For the Current Status section:
   - Determine the CSO Phase, Status, and Last Update from the incident details.
   - Use "Unknown" for CSO Phase if not specified.
   - Use the most recent timestamp for Last Update in YYYY-MM-DD HH:MM:SS UTC format.

3. For the Key Information section:
   - Summarize the most critical and up-to-date information about the incident.
   - Include impact, affected systems, and any significant findings.
   - Use 6-8 bullet points maximum.

4. For the Engineers Actively Investigating section:
   - Identify key individuals working on the incident from the conversation and JIRA context.
   - List their names and current tasks or investigations.

5. For the Timeline section:
   - Extract notable events and actions from the conversation and JIRA context.
   - Order them chronologically.
   - Use the format "**DD-MMM-YYYY, HH:MM UTC:**" for timestamps (bold).
   - Do NOT mention or describe Severity level changes (e.g., "Sev 2", "Severity 4").

6. For the Next Steps section:
   - Identify planned actions or pending investigations from the conversation and JIRA context.
   - Include timeline and responsible person when available.
   - If no next steps are identified, omit this section entirely.

7. For the JIRA Tickets & Work Done section:
   - **CRITICAL**: Only create detailed entries for tickets that have actual data in the JIRA Context system message
   - If JIRA context is provided in a separate system message, extract and format ONLY that information
   - Do NOT create detailed entries for tickets that are merely mentioned in the conversation
   - Do NOT duplicate or copy comments from one ticket to another
   - Each comment must be unique to its specific ticket as provided in the JIRA context
   - If multiple tickets are mentioned but only one has JIRA data:
     * Create a detailed entry ONLY for the ticket with data
     * Other tickets should only appear in the References section
   - Follow the detailed JIRA formatting rules below.
   - Only include if JIRA tickets are found with actual data.

8. For the References section:
   - Include the Support Ticket, Channel, Documentation, and Case Number if available.
   - Use the specified formatting for links.
   - Only include Documentation and Case Number bullets if they are found.
   - If additional tickets are mentioned in the conversation but have no JIRA data, they can be listed here as references only.

**CRITICAL JIRA FORMATTING RULES:**
1. JIRA Description Formatting:
   - If description contains tables (|| and | format), extract key information into 3-5 bullet points
   - Focus on: Issue summary, Customer impact, Root cause, Current status
   - Summarize technical details into business-relevant information
   - Limit description summary to 5 lines maximum

2. JIRA Comment Formatting:
   - **CRITICAL**: NEVER duplicate comments across tickets - each comment belongs to only ONE ticket
   - IMPORTANT: The timestamp and commenter name MUST be in bold using ** formatting
   - Format EXACTLY as: - **DD-MMM-YYYY, HH:MM UTC - [Name]:**
   - Summarize each comment to 2-3 lines maximum
   - Focus on: problems identified, solutions proposed, actions taken, decisions made
   - Remove technical jargon and implementation details unless critical
   - Start each summary line with 2 spaces after the header
   - Exclude greetings, signatures, and redundant information
   - For numbered lists in comments: Use exactly 5 spaces before the number
   - For continuation lines within numbered lists: Use exactly 7 spaces
   - For bullet points within numbered lists: Use exactly 7 spaces before the bullet
   - Preserve paragraph breaks (empty lines) between sections
   - Clean up any JIRA markup (like {{code}}, [links|url], **bold**) for Slack readability
   - If you see the same comment on multiple tickets, only include it under the first ticket where it appears

**Important formatting rules:**
- Use only '•' for bullet points (NOT - or * or any other character).
- Headers MUST use emojis as shown in template (e.g. :traffic_light: for Current Status).
- Timestamp in UTC: YYYY-MM-DD HH:MM:SS UTC.
- Timeline timestamps must NOT use brackets: use "**DD-MMM-YYYY, HH:MM UTC:**" format (bold timestamps).
- Limit output to 600 words. IMPORTANT: Summarize JIRA comments to key points (2-3 lines max per comment).
- Do not join multi-line content into a single line.

#################################################
SELF-VERIFICATION CHECKLIST (must be followed before submitting output):
#################################################
• All 6-7 main sections are included (Current Status, Engineers Actively Investigating, Timeline, Key Information, Next Steps if applicable, JIRA Tickets if found, References)
• Bullet count is controlled (6-8 under Key Info, 1-3 under Next Steps)
• Total output is under 600 words (JIRA comments are summarized to 2-3 lines each)
• Timestamps MUST follow UTC format: YYYY-MM-DD HH:MM:SS UTC
• Timeline timestamps must use "**DD-MMM-YYYY, HH:MM UTC:**" format exactly (bold timestamps)
• JIRA tickets MUST be formatted as <https://jira.corp.adobe.com/browse/[ticket_id]|[ticket_id]>
• Only include Documentation and Case Number if they are found
• Channel links MUST be formatted as <#channel_id|channel_name>
• CSO Phase is always listed — use "Unknown" if needed
• Timeline events are chronologically ordered with proper UTC timestamps
• DO NOT include any of the EXAMPLES or INSTRUCTIONS in your output
• JIRA comment timestamps and names are properly bolded
• NO duplicate comments across JIRA tickets - each comment appears only once under its original ticket
• Only create detailed JIRA entries for tickets with actual data in the JIRA Context system message

If any requirement is not met, regenerate your output. Do not include the Self-Verification Checklist in the output.

Generate the status report based on these instructions, ensuring all formatting and content requirements are met.

**Accuracy Requirements:**
- Only include information explicitly found in the conversation
- Use "NOT YET AVAILABLE" for missing critical data
- Distinguish between confirmed facts and assumptions
- Include uncertainty where appropriate (e.g., "possibly", "appears to be")
"""

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += "\n\nIMPORTANT: Return your response as JSON with this exact structure:\n"
        prompt += '{"response_text": "your complete formatted response here using markdown"}\n'

    return prompt
