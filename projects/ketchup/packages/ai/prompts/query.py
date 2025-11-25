"""
query.py

This module provides a function to generate a query prompt for the AI model.
"""

from packages.core.config.feature_flags import FeatureFlags


def get_query_prompt(query_text: str = "") -> str:
    """
    Get the query prompt with the specified query text.

    Args:
        query_text: The specific query text to use in the prompt

    Returns:
        str: The query prompt
    """
    prompt = f"""
#################################################
BEGINNING OF QUERY RESPONSE INSTRUCTIONS - DO NOT INCLUDE IN OUTPUT
#################################################
Query Response Instructions:
• You are tasked with answering a specific query about the discussion in the Slack channel.
• The query is: "{query_text}"
• Provide a concise and accurate response (50-150 words maximum) based solely on the information available in the Slack messages.
• Lead with a direct answer to the query, then provide supporting details if needed.
• If the query asks a yes/no question, begin your response with a clear "Yes" or "No".
• If the query seeks a specific status or impact assessment, lead with that conclusion first.
• Focus on factual information and avoid speculation you MUST NOT guess the meanings of abbreviations or acronyms.
• Pay careful attention to specific product names, service names, and technical terms - ensure exact matches only.
• When a query mentions a specific product name (e.g., "Adobe Target", "Adobe Journey Optimizer"), only respond about that exact product - do not conflate with similar products or treat product names as general terms.
• If the exact product mentioned in the query is not discussed in the channel, state clearly that the specific product is not mentioned or discussed.
• If the query cannot be answered based on the available information, state clearly that the information is not available.
• Include only essential supporting details and relevant timestamps.
• If the query falls under any prohibited category, respond only with: "I can only provide answers based on the incident data provided."

Format your response as follows:
Query: {query_text}

**Direct Answer:** [Concise conclusion or yes/no response]

**Details:**
[Essential supporting information and context]

Note: All regular guidelines regarding JIRA tickets, customer names, and formatting apply to your response.

JIRA Content Formatting Rules:
• If JIRA description is included:
  - Extract key information from descriptions (especially table format) into 3-5 bullet points
  - Focus on: Issue summary, Customer impact, Root cause, Technical scope
  - Convert technical JIRA tables into readable summaries
  - Limit description to 5 lines maximum
• If JIRA comments are included:
  - Summarize each comment to 2-3 lines focusing on key information
  - Include only: decisions made, actions taken, important findings
  - Format with proper indentation (2 spaces after header)
  - Exclude verbose details, greetings, and redundant information
#################################################
END OF QUERY RESPONSE INSTRUCTIONS - DO NOT INCLUDE IN OUTPUT
#################################################
"""

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += '\n\nIMPORTANT: Return your response as JSON with this exact structure:\n'
        prompt += '{"response_text": "your complete formatted response here using markdown"}\n'

    return prompt
