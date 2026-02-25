#!/usr/bin/env python3
"""
test_normalize_actual.py

Test normalization with actual problematic input from production.
"""

from packages.core.utils import normalize_prompt_for_agent


def test_actual_multiline_input():
    """Test with the actual input that caused double posting."""
    test_input = """Search for JIRA tickets using this JQL query and format the results according to the template below:
JQL: project in (CPGNREQ, CPGNTT, AMSE, CPGNCX, CSOPM) AND assignee in membersOf("ORG-VALLET-ALL") AND resolved >= startOfWeek() AND resolved <= now() ORDER BY created DESC

Format the results as "MSE & MSPE EMEA – Weekly Highlights" following this exact structure:

MSE & MSPE EMEA – Weekly Highlights
Total issues resolved: [count] | CPGNREQ: [count] | CPGNTT: [count] | AMSE: [count] | CPGNCX: [count] | CSOPM: [count]

Top 5 Highlights:
[Customer] – [Issue summary from latest comment or ticket summary] ([JIRA-KEY])
:arrow-green: Impact: [Impact description]
[Repeat for top 5 tickets, no duplicate customers]"""

    normalized = normalize_prompt_for_agent(test_input)

    # Print diagnostics
    print(f"\nOriginal length: {len(test_input)}")
    print(f"Normalized length: {len(normalized)}")
    print(f"Newlines in original: {test_input.count('\n')}")
    print(f"Newlines in normalized: {normalized.count('\n')}")
    print(f"\nFirst 200 chars of normalized: {repr(normalized[:200])}")
    print(
        f"\nChecking for 'Format the results' duplicates: {normalized.count('Format the results')}"
    )

    # Assertions
    assert normalized.count("\n") == 0, "Normalized text should not contain newlines"
    assert "Format the results" in normalized, "Key phrase should be preserved"
    assert normalized.count("Format the results") == 1, "No duplicate phrases"


def test_full_production_input():
    """Test with the complete production input including all sections."""
    test_input = """Search for JIRA tickets using this JQL query and format the results according to the template below:
JQL: project in (CPGNREQ, CPGNTT, AMSE, CPGNCX, CSOPM) AND assignee in membersOf("ORG-VALLET-ALL") AND resolved >= startOfWeek() AND resolved <= now() ORDER BY created DESC

Format the results as "MSE & MSPE EMEA – Weekly Highlights" following this exact structure:

MSE & MSPE EMEA – Weekly Highlights
Total issues resolved: [count] | CPGNREQ: [count] | CPGNTT: [count] | AMSE: [count] | CPGNCX: [count] | CSOPM: [count]

Top 5 Highlights:
[Customer] – [Issue summary from latest comment or ticket summary] ([JIRA-KEY])
:arrow-green: Impact: [Impact description]
[Repeat for top 5 tickets, no duplicate customers]

:white_check_mark:OPERATIONAL EXCELLENCE
[Summary line about production issues]
:arrow-green: Impact: [Impact summary]
Jiras: [List of CPGNTT and CPGNREQ tickets]

:white_check_mark:SCALABLE OPERATIONS
[Summary line about security/integration]
:arrow-green: Impact: [Impact summary]
Jiras: [List of AMSE tickets]

:white_check_mark:KNOWLEDGE SHARING
[Summary line about internal improvements]
:arrow-green: Impact: [Impact summary]
Jiras: [List of relevant CPGNCX tickets]

:white_check_mark:DELIVERABILITY
[Summary line about service reviews]
:arrow-green: Impact: [Impact summary]
Jiras: [List of CPGNREQ tickets related to deliverability]

:white_check_mark:ENHANCED DELIVERABILITY EXPERIENCE
[Summary line about customer support]
:arrow-green: Impact: [Impact summary]
Jiras: [List of CPGNCX customer care tickets]

:white_check_mark:SECURITY & RELIABILITY
[Summary line about security improvements]
:arrow-green: Impact: [Impact summary]
Jiras: [List of CPGNCX security tickets]

Requirements:
- Use latest comment for summary, fallback to ticket summary
- Omit sections with no matching tickets
- Use real JIRA keys from search results
- No assignee names or invented content"""

    normalized = normalize_prompt_for_agent(test_input)

    # Print full normalized output for inspection
    print(f"\n\nFULL NORMALIZED OUTPUT:\n{repr(normalized)}")

    # Check that it's truly a single line
    assert (
        normalized.count("\n") == 0
    ), f"Found {normalized.count('\n')} newlines in normalized text"

    # Check that key sections are preserved
    assert "OPERATIONAL EXCELLENCE" in normalized
    assert "SCALABLE OPERATIONS" in normalized
    assert "KNOWLEDGE SHARING" in normalized

    # Ensure no duplication of key phrases
    assert normalized.count("Search for JIRA tickets") == 1
    assert normalized.count("Format the results") == 1


if __name__ == "__main__":
    # Run tests directly for debugging
    test_actual_multiline_input()
    print("\n" + "=" * 50 + "\n")
    test_full_production_input()
