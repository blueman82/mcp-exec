"""
utils.py

Utility functions for text formatting in Slack messages.
"""

import re

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text by escaping or removing problematic markdown characters,
    while preserving URLs.

    Args:
        text (str): The text to normalize.

    Returns:
        str: The sanitized text.
    """
    logger.info("Normalizing text")
    # Step 1: Find and temporarily replace URLs
    # Adjusted regex that looks for an optional '<' at the start, allows for an optional colon, and stops at a '>' or whitespace
    url_pattern = r"<?(https?[:]?//[^\s>]+)>?"
    urls = re.findall(url_pattern, text)

    # Replace each URL with a placeholder that includes an index
    for i, url in enumerate(urls):
        placeholder = f"__URL_PLACEHOLDER_{i}__"
        text = text.replace(url, placeholder)

    # Step 2: Apply normalization to the rest of the text
    # Remove backticks entirely
    text = re.sub(r"`+", "", text)
    # Remove unwanted markdown markers (for example, tildes and bold markers)
    text = re.sub(r"[~]", "", text)
    # Convert markdown bold (**text**) to Slack bold (*text*)
    # Use DOTALL flag to handle newlines and more flexible pattern
    text = re.sub(r"\*\*([^\*]+)\*\*", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"\#\#\#", "", text)
    # Step 3: Restore URLs
    for i, url in enumerate(urls):
        placeholder = f"__URL_PLACEHOLDER_{i}__"
        text = text.replace(placeholder, url)

    return text


def enhance_structured_text(text: str) -> str:
    """
    Enhance the structure and readability of text for better presentation in Slack,
    especially when falling back to plain text mode.

    This function is aware of markdown structure and improves formatting of section breaks,
    headings, and other structured content to make plain text more readable.

    Args:
        text: The text to enhance

    Returns:
        Text with enhanced structure and formatting
    """
    logger.info("Enhancing structured text")
    if not text:
        return text

    # First convert markdown bold (**text**) to Slack bold (*text*)
    # This needs to happen before other processing
    text = re.sub(r"\*\*([^\*]+)\*\*", r"*\1*", text, flags=re.DOTALL)

    # First, convert all list items using hyphens to bullet points
    # This needs to be done before splitting so we don't miss any
    # Convert standard list items with hyphens to bullet points
    text = re.sub(r"(\n|^)\s*-\s+", r"\1• ", text)

    # Also handle list items after section headers
    text = re.sub(r"(\n[A-Za-z0-9&\s]+:)\s*-\s+", r"\1 • ", text)

    # Catch any remaining hyphens used as bullet points
    text = re.sub(r"(\n\s+)-\s+", r"\1• ", text)

    # Split the text into sections based on headers
    section_pattern = r"(^|\n)(#+ [^\n]+)(\n|$)"
    sections = re.split(section_pattern, text, flags=re.MULTILINE)

    # Process each section to enhance formatting
    enhanced_sections = []

    for i, section in enumerate(sections):
        # Add extra formatting to headings (at positions 1, 4, 7, etc. in the split)
        heading_level_match = re.match(r"^(#+)", section.strip())
        if heading_level_match:
            heading_level = len(heading_level_match.group(1))
            heading_text = section.strip()[heading_level:].strip()

            if heading_level == 1:
                # For top-level headings (# Heading)
                enhanced_sections.append(
                    f"\n\n:page_facing_up: *{heading_text.upper()}*\n"
                )
            elif heading_level == 2:
                # For second-level headings (## Heading)
                enhanced_sections.append(f"\n\n:bookmark_tabs: *{heading_text}*\n")
            else:
                # For other headings (### Heading or deeper)
                enhanced_sections.append(f"\n*{heading_text}*\n")
        else:
            # Regular text - apply basic paragraph formatting
            if section.strip():
                # Add paragraph breaks between sections
                if i > 0 and not section.startswith("\n"):
                    section = section.replace("\n\n", "\n")
                enhanced_sections.append(section)

    # Join the processed sections
    result = "".join(enhanced_sections)

    # Double-check for any remaining hyphens used as bullet points
    # This catches any hyphens that might have been missed in the initial pass
    # or introduced during processing
    result = re.sub(
        r"(\n|^)\s*-\s+", r"\1• ", result
    )  # Beginning of line or after newline
    result = re.sub(
        r"(\n[A-Za-z0-9&\s]+:)\s*-\s+", r"\1 • ", result
    )  # After section labels
    result = re.sub(r"(\n\s+)-\s+", r"\1• ", result)  # Indented list items

    # Add an extra line before blockquotes for better separation
    result = re.sub(r"(\n)>\s+", r"\1\n> ", result)

    # Remove horizontal rules (---, ***, ___) only from beginning and end of text
    # First, trim any leading/trailing whitespace
    result = result.strip()

    # Remove horizontal rule at the beginning if present
    result = re.sub(r"^[-*_]{3,}\s*\n+", "", result)

    # Remove horizontal rule at the end if present
    result = re.sub(r"\n+\s*[-*_]{3,}\s*$", "", result)

    return result
