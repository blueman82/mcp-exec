"""
JIRA-related constants used across the application.

These constants are used across the application for JIRA ticket processing
and validation.
"""

# Prefixes for valid JIRA ticket keys, used to filter out false positives.
VALID_JIRA_PROJECTS = [
    "CPGNREQ",
    "CPGNTT",
    "NEO",
    "CPGNPROV",
    "PLATIR",
    "CSOPM",
    "CPGNCX",
    "CPGNCC",
    "AMSE",
    "CAMP",
]
