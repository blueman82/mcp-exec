"""
handover_summary.py

This module provides prompts for on-call shift handover summary generation.
"""

from packages.core.config.feature_flags import FeatureFlags


def get_handover_system_prompt() -> str:
    """
    Get the system prompt for handover summary generation.

    Returns:
        str: The system prompt
    """
    return """You are an AI assistant specialized in generating ultra-compact incident summaries for on-call shift handover.

Your ONLY job is to:
1. Analyze the provided Slack messages and JIRA comments
2. Extract the current state and immediate next action
3. Output EXACTLY 1-2 bullet points using • character
4. Maximum 50 words total

Focus on:
- Current state of the incident
- Immediate next action required

DO NOT include:
- Raw messages or timestamps
- Channel information
- Speculation or assumptions

The context provided is for your analysis only - do not reproduce it in your output."""


def get_handover_channel_prompt(
    channel_name: str,
    customer_name: str,
    jira_ticket: str,
    messages: str,
    jira_comments: str,
) -> str:
    """
    Get the handover summary prompt for a specific channel.

    Args:
        channel_name: Name of the Slack channel
        customer_name: Name of the customer
        jira_ticket: JIRA ticket identifier
        messages: Slack messages text
        jira_comments: JIRA comments text

    Returns:
        str: The formatted prompt for handover summary generation
    """
    prompt = f"""
Generate a shift handover summary for #{channel_name}.
Customer: {customer_name}
JIRA: {jira_ticket}

SLACK MESSAGES:
{messages}

JIRA COMMENTS:
{jira_comments}

**INSTRUCTIONS:**
Generate 1-2 bullet points summarizing the current state and next action for this incident.
- Maximum 50 words total
- Use • for bullets
- Focus on: what's happening now + what needs to happen next

**CRITICAL ACCURACY REQUIREMENTS:**
• Use ONLY technical details that appear verbatim in the source material above
• Never substitute, fabricate, or modify any technical terms, system names, or technology references
• When uncertain about specific technical details, use generic descriptive terms instead
• Every technical claim must be directly traceable to the source content

**OUTPUT RULES:**
• Output ONLY 1-2 bullet points, no more
• Use • character for bullets (not - or *)
• Maximum 50 words total
• Each bullet: current state OR next action
• DO NOT include timestamps, raw messages, or message content
• DO NOT add any other sections or content
"""

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += "\n\nIMPORTANT: Return your response as JSON with this exact structure:\n"
        prompt += '{"response_text": "your complete formatted response here using markdown"}\n'

    return prompt
