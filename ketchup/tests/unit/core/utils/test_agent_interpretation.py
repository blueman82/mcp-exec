"""
test_agent_interpretation.py

Test to identify patterns that might cause the agent to interpret as multiple queries.
"""

from packages.core.utils import normalize_prompt_for_agent


def test_identify_problematic_patterns():
    """Identify patterns in the normalized text that might cause issues."""
    test_input = """Search for JIRA tickets using this JQL query and format the results according to the template below:  
JQL: project in (CPGNREQ, CPGNTT, AMSE, CPGNCX, CSOPM) AND assignee in membersOf("ORG-VALLET-ALL") AND resolved >= startOfWeek() AND resolved <= now() ORDER BY created DESC  

Format the results as "MSE & MSPE EMEA – Weekly Highlights" following this exact structure:  

MSE & MSPE EMEA – Weekly Highlights  
Total issues resolved: [count] | CPGNREQ: [count] | CPGNTT: [count] | AMSE: [count] | CPGNCX: [count] | CSOPM: [count]"""

    normalized = normalize_prompt_for_agent(test_input)

    # Check for imperative phrases that might trigger multiple actions
    problematic_phrases = [
        "Search for",
        "format the results",
        "Format the results",
        "following this",
        "JQL:",
        "Requirements:",
    ]

    print("\nChecking for potentially problematic phrases:")
    for phrase in problematic_phrases:
        count = normalized.count(phrase)
        if count > 0:
            print(f"  '{phrase}': {count} occurrence(s)")
            # Find positions
            start = 0
            while True:
                pos = normalized.find(phrase, start)
                if pos == -1:
                    break
                # Show context around the phrase
                context_start = max(0, pos - 20)
                context_end = min(len(normalized), pos + len(phrase) + 20)
                print(
                    f"    Position {pos}: ...{normalized[context_start:context_end]}..."
                )
                start = pos + 1

    # Check for action words at the beginning of "sentences" (after periods or colons)
    import re

    # Find all positions after period/colon followed by space and a capital letter
    sentence_starts = re.finditer(r"[.:]\s+([A-Z])", normalized)
    print("\nPotential sentence starts that might be interpreted as new commands:")
    for match in sentence_starts:
        start_pos = match.start() + 2  # Skip the punctuation and space
        end_pos = min(start_pos + 50, len(normalized))
        print(f"  Position {start_pos}: {normalized[start_pos:end_pos]}...")

    # Check for specific pattern that might cause issues
    if "Search for" in normalized and "Format the results" in normalized:
        search_pos = normalized.find("Search for")
        format_pos = normalized.find("Format the results")
        print(
            f"\nDistance between 'Search for' and 'Format the results': {format_pos - search_pos} characters"
        )


if __name__ == "__main__":
    test_identify_problematic_patterns()
