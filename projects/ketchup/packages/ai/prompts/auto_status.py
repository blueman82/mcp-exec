"""
auto_status.py

This module provides prompts for automated status report generation.
"""

from typing import Any, Dict

from packages.ai.prompts.common_guidelines import COMMON_GUIDELINES_PROMPT
from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def get_auto_status_prompt(channel_info: Dict[str, Any]) -> str:
    """
    Get the automated status report prompt using ultra-concise format.

    Args:
        channel_info: Dictionary containing channel_name, customer_name, jira_ticket, product

    Returns:
        str: The formatted prompt for auto-status generation
    """
    prompt = f"""
{COMMON_GUIDELINES_PROMPT}

Generate a status update for <#{channel_info['channel_name']}|{channel_info['channel_id']}>.
Customer: {channel_info.get('customer_name', 'Unknown')}
JIRA: {channel_info.get('jira_ticket', 'None')}
Product: {channel_info.get('product', 'Unknown')}


#################################################
BEGINNING OF OUTPUT FORMAT - FOLLOW EXACTLY
#################################################

*Overview:* [1-2 sentences describing the current situation]

*What's been done / What's next:*
• [Action 1 - completed or planned]
• [Action 2 - completed or planned]
• [Action 3 - completed or planned]
• [Action 4 - completed or planned]

(DO NOT INCLUDE THE LINES BELOW IN YOUR OUTPUT - THEY ARE INSTRUCTIONS ONLY)
#################################################
END OF OUTPUT FORMAT - DO NOT OUTPUT THIS LINE OR THE LINES ABOVE/BELOW IT
#################################################

**CRITICAL RULES:**
• NEVER include the delimiter lines (#####) or "END OF OUTPUT FORMAT" in your response
• Output EXACTLY 2 sections: Overview and What's been done / What's next
• Overview: 1-2 sentences maximum
• Bullets: EXACTLY 4 bullets, no more, no less
• Each bullet: One clear action (past tense for completed, future tense for planned)
• Total length: Under 150 words
• Use ONLY • character for bullets (not - or *)
• DO NOT include timestamps, raw messages, or message content
• DO NOT add any other sections or content
• If instructed that there are no new messages, start Overview with "No new activity since the last update."
• IMPORTANT: DO NOT include JIRA ticket information in your output - it will be added automatically if needed

**Self-Verification Checklist (MANDATORY before submitting output):**
• Output has exactly 2 sections (Overview + What's been done / What's next)
• Overview is 1-2 sentences only
• Exactly 4 bullet points under What's been done / What's next
• No raw messages or timestamps included
• No extra sections added beyond the 2 required
• Total output under 150 words
• **TECHNICAL ACCURACY CHECK:** All technical terms, system names, and technology references in your output MUST appear verbatim in the source JIRA ticket or Slack messages
• **NO SUBSTITUTION RULE:** Never replace or substitute technical terms with similar alternatives - use exact names from source material only
• **FACT SOURCE VALIDATION:** Every technical claim can be traced back to provided JIRA or Slack content

If ANY requirement is not met, you MUST regenerate your output. Do not include this checklist in your final response.
"""

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += "\n\nIMPORTANT: Return your response as JSON with this exact structure:\n"
        prompt += '{"response_text": "your complete formatted response here using markdown"}\n'

    return prompt


def get_auto_status_system_prompt() -> str:
    """
    Get the system prompt for auto-status generation.

    Returns:
        str: The system prompt
    """
    return """You are an AI assistant specialized in generating ultra-concise channel status reports.

Your ONLY job is to:
1. Analyze the provided channel messages and JIRA comments
2. Extract the key situation and actions
3. Output EXACTLY 2 sections: Overview (1-2 sentences) and What's been done / What's next (4 bullets)

CRITICAL ACCURACY REQUIREMENTS:
- Use ONLY technical details that appear verbatim in the provided source material
- Never substitute, create, or modify any technical terms, system names, or technology references
- When uncertain about specific technical details, use generic descriptive terms instead
- Every technical claim must be directly traceable to the source content

DO NOT include:
- Raw messages or timestamps
- Channel information lines
- CSO Phase or Customer lines
- Any other sections or content beyond the required sections
- Technical details not found in source material

The context provided is for your analysis only - do not reproduce it in your output."""
