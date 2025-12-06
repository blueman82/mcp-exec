"""
customer_extraction.py

This module provides a function to generate a customer name and JIRA ticket extraction prompt for the AI model.
"""

from packages.core.config.feature_flags import FeatureFlags


def get_customer_name_extraction_prompt() -> str:
    """
    Get the customer name and JIRA ticket extraction prompt.
    """
    prompt = r"""
#################################################
BEGINNING OF CUSTOMER NAME AND JIRA TICKET EXTRACTION INSTRUCTIONS - DO NOT INCLUDE IN OUTPUT
#################################################
You are tasked with extracting customer names and JIRA ticket information from the conversation text that will be provided in the next message. Follow these instructions carefully to provide accurate and consistent results.

Step 1: Extract Customer Names
- Read the conversation text provided by the user and identify customer names explicitly mentioned in the conversation context.
- Do not extract customer names if only a product name is mentioned.
- Extract customer names that appear in actual conversation content, including incident reports, system notifications, and team discussions.
- Look for patterns like 'customer: [NAME]', 'working with [NAME] team', '[NAME] is experiencing issues', 'degradation for [NAME]', 'Customer [NAME] is experiencing'.
- Pay special attention to incident reports and system notifications that mention specific customer names.
- If a company name appears in both conversation AND URLs/system references, extract it only if the conversation context clearly indicates it's the customer.
- Convert each name to uppercase.
- If multiple names are found, list them separated by commas.
- Be aware that customers are occasionally abbreviated (e.g., MSFT for MICROSOFT).
- Customer names may be surrounded by brackets [], (), {}, or ##EXAMPLE tags.
- If you cannot determine the customer name, use the fallback response 'NOT YET AVAILABLE'.

Step 2: Extract JIRA Ticket
- Scan the conversation text provided by the user for JIRA ticket references.
- Select the first ticket based on the oldest timestamp.
- If no JIRA ticket is found, use the fallback response 'NOT YET AVAILABLE'.
- Format the selected ticket as the ticket ID only (e.g., CPGNREQ-12345).

Output Format:
Provide your output in exactly two lines:
1. First line: Customer name(s) in uppercase format or fallback.
2. Second line: JIRA ticket ID or fallback.

Ensure no additional text is included in your output.

Examples (do not include these in your output):
Example 1:
HYUNDAI CAPITAL AMERICA, MCAFEE
CPGNREQ-12345

Example 2:
NOT YET AVAILABLE
NEO-8526

Example 3:
[ELECTRIC WORLD]
CPGNNTT-44444

Self-Verification Checklist:
Before submitting your output, verify that:
1. Customer names are extracted and uppercased; if multiple, joined with commas; if none, fallback is used.
2. JIRA ticket is extracted according to the criteria or fallback is used.
3. Output is formatted into exactly two lines.
4. No additional text or details from examples are included.
5. The final output has exactly two lines.

Provide your final output as plain text with no additional formatting or tags.
"""

    # Add JSON schema instruction when feature flag enabled
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += "\n\nIMPORTANT: Return your response as JSON with this exact structure:\n"
        prompt += '{"response_text": "Line 1: Customer name\\nLine 2: JIRA ticket"}\n'

    return prompt
