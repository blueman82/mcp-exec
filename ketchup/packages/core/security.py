"""
Security utilities for the Ketchup application.

This module provides input sanitization, validation, and security
functions to prevent injection attacks and ensure safe operation.
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Maximum allowed result sizes for different operations
MAX_RESULTS = 100
MAX_AGGREGATION_SIZE = 50
MAX_PHRASE_SLOP = 10

# Whitelisted fields for Elasticsearch operations
ALLOWED_ES_FIELDS = {
    "summary",
    "description",
    "comments.body",
    "assignee",
    "project",
    "status",
    "priority",
    "created",
    "updated",
    "key",
    "type",
    "labels",
    "reporter",
    "resolution",
    "components",
    "fixVersions",
    "affectedVersions",
}

# Whitelisted project codes
ALLOWED_PROJECT_CODES = {
    "CPGNREQ",
    "CSOPM",
    "TECHOPS",
    "CAMPAIGN",
    "CSO",
    "SECURITY",
    "INFRA",
    "DEVOPS",
    "PLATFORM",
    "API",
}

# Whitelisted status values
ALLOWED_STATUS_VALUES = {
    "Open",
    "In Progress",
    "Resolved",
    "Closed",
    "Done",
    "To Do",
    "In Review",
    "Testing",
    "Blocked",
    "Cancelled",
}

# Whitelisted priority values
ALLOWED_PRIORITY_VALUES = {
    "P0",
    "P1",
    "P2",
    "P3",
    "P4",
    "Blocker",
    "Critical",
    "Major",
    "Minor",
    "Trivial",
    "Highest",
    "High",
    "Medium",
    "Low",
    "Lowest",
}


def sanitize_query_string(query: str) -> str:
    """
    Sanitize user input query string to prevent ES injection attacks.

    Args:
        query: Raw query string from user input

    Returns:
        Sanitized query string safe for ES operations

    Raises:
        ValueError: If query is empty or too long
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")

    # Limit query length
    if len(query) > 1000:
        raise ValueError("Query too long (max 1000 characters)")

    # Remove dangerous ES special characters and operators
    # Allow basic search but prevent script injection
    dangerous_patterns = [
        r"<script[^>]*>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"data:",  # Data URLs
        r"vbscript:",  # VBScript URLs
        r"onload=",  # Event handlers
        r"onerror=",
        r"onclick=",
        r"\${.*?}",  # Template injection
        r"<%.*?%>",  # Server-side includes
        r"{{.*?}}",  # Template expressions
    ]

    sanitized = query
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    # Escape ES special characters that could be used for injection
    es_special_chars = [
        "\\",
        "+",
        "-",
        "=",
        "&&",
        "||",
        ">",
        "<",
        "!",
        "(",
        ")",
        "{",
        "}",
        "[",
        "]",
        "^",
        '"',
        "~",
        "*",
        "?",
        ":",
    ]
    for char in es_special_chars:
        if char in ["*", "?"]:  # Allow wildcards but escape others
            continue
        sanitized = sanitized.replace(char, f"\\{char}")

    # Normalize whitespace
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    if not sanitized:
        raise ValueError("Query becomes empty after sanitization")

    return sanitized


def validate_field_list(fields: List[str]) -> List[str]:
    """
    Validate and filter field list to only allowed ES fields.

    Args:
        fields: List of field names to validate

    Returns:
        List of validated field names

    Raises:
        ValueError: If no valid fields remain
    """
    if not fields or not isinstance(fields, list):
        return ["summary", "description", "comments.body"]  # Safe defaults

    # Filter to only allowed fields
    validated_fields = []
    for field in fields:
        if isinstance(field, str):
            # Remove boost syntax (e.g., "summary^3" -> "summary")
            base_field = field.split("^")[0].strip()
            if base_field in ALLOWED_ES_FIELDS:
                validated_fields.append(field)  # Keep original with boost

    if not validated_fields:
        logger.warning(f"No valid fields in list: {fields}, using defaults")
        return ["summary", "description", "comments.body"]

    return validated_fields


def validate_project_filter(project: str) -> str:
    """
    Validate project filter to prevent injection.

    Args:
        project: Project code to validate

    Returns:
        Validated project code

    Raises:
        ValueError: If project code is invalid
    """
    if not project or not isinstance(project, str):
        raise ValueError("Project must be a non-empty string")

    # Normalize to uppercase
    project = project.upper().strip()

    # Remove non-alphanumeric characters except dash and underscore
    project = re.sub(r"[^A-Z0-9_-]", "", project)

    if not project:
        raise ValueError("Project code becomes empty after validation")

    # Allow known project codes or reasonable patterns
    if len(project) > 20:
        raise ValueError("Project code too long (max 20 characters)")

    # Basic pattern validation (letters, numbers, dash, underscore)
    if not re.match(r"^[A-Z0-9_-]+$", project):
        raise ValueError("Invalid project code format")

    return project


def validate_size_parameter(size: int, max_allowed: int = MAX_RESULTS) -> int:
    """
    Validate and bound size parameter to prevent resource exhaustion.

    Args:
        size: Requested result size
        max_allowed: Maximum allowed size

    Returns:
        Bounded size value
    """
    if not isinstance(size, int) or size < 1:
        return 10  # Default safe size

    return min(size, max_allowed)


def validate_status_filter(status: str) -> str:
    """
    Validate status filter value.

    Args:
        status: Status value to validate

    Returns:
        Validated status value

    Raises:
        ValueError: If status is invalid
    """
    if not status or not isinstance(status, str):
        raise ValueError("Status must be a non-empty string")

    # Normalize case and whitespace
    status = status.strip()

    # Remove dangerous characters
    status = re.sub(r'[<>"\'\\/]', "", status)

    if not status:
        raise ValueError("Status becomes empty after validation")

    if len(status) > 50:
        raise ValueError("Status value too long (max 50 characters)")

    return status


def validate_hours_parameter(hours: int) -> int:
    """
    Validate hours parameter for time-based queries.

    Args:
        hours: Hours value to validate

    Returns:
        Validated hours value (bounded between 1 and 8760 - one year)
    """
    if not isinstance(hours, int) or hours < 1:
        return 24  # Default to 24 hours

    # Limit to reasonable range (max 1 year)
    return min(hours, 8760)


def validate_slop_parameter(slop: int) -> int:
    """
    Validate slop parameter for phrase queries.

    Args:
        slop: Slop value to validate

    Returns:
        Validated slop value (bounded between 0 and MAX_PHRASE_SLOP)
    """
    if not isinstance(slop, int) or slop < 0:
        return 2  # Default slop

    return min(slop, MAX_PHRASE_SLOP)


def sanitize_error_message(error: Exception, include_type: bool = False) -> str:
    """
    Sanitize error messages to prevent information leakage.

    Args:
        error: Exception to sanitize
        include_type: Whether to include exception type in message

    Returns:
        Safe error message for client consumption
    """
    # Generic error messages for different exception types
    safe_messages = {
        "ConnectionError": "Service temporarily unavailable",
        "TimeoutError": "Request timed out",
        "PermissionError": "Access denied",
        "FileNotFoundError": "Resource not found",
        "ValueError": "Invalid input provided",
        "KeyError": "Required field missing",
        "TypeError": "Invalid data type",
    }

    error_type = type(error).__name__
    error_msg = str(error)

    # Log full error for debugging
    logger.error(f"Error occurred: {error_type}: {error_msg}")

    # Return safe message
    safe_msg = safe_messages.get(error_type, "An error occurred")

    if include_type:
        return f"{error_type}: {safe_msg}"

    return safe_msg


def validate_es_query_dict(query_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize Elasticsearch query dictionary.

    Args:
        query_dict: ES query dictionary to validate

    Returns:
        Sanitized query dictionary

    Raises:
        ValueError: If query contains dangerous patterns
    """
    if not isinstance(query_dict, dict):
        raise ValueError("Query must be a dictionary")

    # Convert to string for pattern checking
    query_str = str(query_dict)

    # Check for dangerous patterns in query
    # Note: Be more specific to avoid false positives with legitimate ES features
    dangerous_patterns = [
        "<script",  # HTML script tags
        "javascript:",  # JavaScript URLs
        "vbscript:",  # VBScript URLs
        "data:text/html",  # HTML data URLs
        "onload=",  # Event handlers
        "onerror=",  # Event handlers
        "onclick=",  # Event handlers
        "${java",  # Java code injection
        "<%=",  # Server-side includes
        "{{#",  # Handlebars helpers that could be dangerous
    ]

    for pattern in dangerous_patterns:
        if pattern.lower() in query_str.lower():
            logger.warning(
                f"Potentially dangerous pattern detected in query: {pattern}"
            )
            raise ValueError(f"Query contains potentially dangerous pattern: {pattern}")

    # Check query size to prevent DoS
    if len(query_str) > 10000:  # 10KB limit
        raise ValueError("Query too large (max 10KB)")

    return query_dict


def sanitize_aggregation_field(field: str) -> str:
    """
    Sanitize field name for aggregation queries.

    Args:
        field: Field name to sanitize

    Returns:
        Sanitized field name

    Raises:
        ValueError: If field is invalid
    """
    if not field or not isinstance(field, str):
        raise ValueError("Field must be a non-empty string")

    # Remove .keyword suffix for validation, will be re-added later
    base_field = field.replace(".keyword", "").strip()

    if base_field not in ALLOWED_ES_FIELDS:
        logger.warning(f"Invalid aggregation field: {field}")
        raise ValueError(f"Field '{base_field}' not allowed for aggregation")

    # Ensure clean field name
    field = re.sub(r"[^a-zA-Z0-9._-]", "", field)

    if not field:
        raise ValueError("Field becomes empty after sanitization")

    return field


def sanitize_jql_value(value: str) -> str:
    """
    Sanitize JQL value to prevent injection attacks.

    This function provides comprehensive protection against JQL injection by:
    - Escaping all dangerous JQL special characters
    - Detecting and rejecting malicious injection patterns
    - Validating organization format where applicable
    - Logging potential security incidents

    Args:
        value: Raw value to be used in JQL query

    Returns:
        Sanitized value safe for JQL queries

    Raises:
        ValueError: If the input contains clear injection attempts or is invalid
    """
    if not value or not isinstance(value, str):
        return ""

    # Store original for logging
    original_value = value
    value = value.strip()

    # Check for obvious injection patterns first (before any sanitization)
    injection_patterns = [
        r"\b(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|EXEC|EXECUTE)\s+\w+",  # SQL commands
        r"\b(OR|AND)\s+\d+\s*=\s*\d+",  # OR 1=1, AND 2=2 patterns
        r"(--|\*\/|\/\*)",  # SQL comments
        r'[\'"]\s*;\s*[\'""]',  # Quote-semicolon-quote patterns
        r"\bunion\s+select\b",  # UNION SELECT
        r"\bselect\s+.*\bfrom\b",  # SELECT FROM
        r'[\'"]\s*(OR|AND)\s+[\'""].*[\'"]',  # Quote OR/AND quote patterns
        r";\s*(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER)",  # Semicolon + command
        r"<script[^>]*>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"data:text/html",  # Data URLs
        r"on\w+\s*=",  # Event handlers (onload=, onclick=, etc.)
        r"\bAND\b.*\bpassword\b",  # AND password patterns
        r"\bOR\b.*\bpassword\b",  # OR password patterns
    ]

    for pattern in injection_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(
                f"JQL injection attempt detected: pattern='{pattern}' value='{original_value[:100]}'"
            )
            raise ValueError("Input contains potentially malicious content")

    # Check for excessive special character density (potential obfuscation)
    special_char_count = len(re.findall(r"[^\w\s\-.]", value))
    if len(value) > 0 and (special_char_count / len(value)) > 0.3:
        logger.warning(
            f"High special character density detected: value='{original_value[:100]}'"
        )
        raise ValueError("Input contains excessive special characters")

    # For organization names, validate format if it looks like an org pattern
    if re.match(r"^[Oo][Rr][Gg]-.*-[Aa][Ll][Ll]$", value):
        # This looks like an organization name - validate format
        if not re.match(r"^[Oo][Rr][Gg]-[a-zA-Z0-9_-]+-[Aa][Ll][Ll]$", value):
            logger.warning(f"Invalid organization format: '{original_value}'")
            raise ValueError("Invalid organization name format")

    # Comprehensive character escaping for JQL safety
    # Focus on the most dangerous characters, allow some legitimate ones
    jql_escape_map = {
        '"': '\\"',  # Escape double quotes
        "'": "\\'",  # Escape single quotes
        "\\": "\\\\",  # Escape backslashes
        "\n": " ",  # Replace newlines with space
        "\r": " ",  # Replace carriage returns with space
        "\t": " ",  # Replace tabs with space
        ";": "",  # Remove semicolons completely (very dangerous)
        "&": "\\&",  # Escape ampersands
        "|": "\\|",  # Escape pipes
        "<": "\\<",  # Escape less than
        ">": "\\>",  # Escape greater than
        "(": "\\(",  # Escape open parenthesis
        ")": "\\)",  # Escape close parenthesis
        "[": "\\[",  # Escape open bracket
        "]": "\\]",  # Escape close bracket
        "{": "\\{",  # Escape open brace
        "}": "\\}",  # Escape close brace
        "*": "\\*",  # Escape asterisk
        "?": "\\?",  # Escape question mark
        "+": "\\+",  # Escape plus
        "=": "\\=",  # Escape equals
        "!": "\\!",  # Escape exclamation
        "^": "\\^",  # Escape caret
        "$": "\\$",  # Escape dollar
        "%": "\\%",  # Escape percent
        "~": "\\~",  # Escape tilde
        "`": "\\`",  # Escape backtick
        ":": "\\:",  # Escape colon
        # Note: Dots (.) are NOT escaped to allow usernames like user.name
    }

    sanitized = value
    for char, escaped in jql_escape_map.items():
        sanitized = sanitized.replace(char, escaped)

    # Remove any remaining control characters
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", sanitized)

    # Normalize whitespace (preserve single spaces)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    # Strict length limit to prevent DoS
    if len(sanitized) > 200:
        logger.warning(
            f"Input too long, truncating: original_length={len(original_value)}"
        )
        sanitized = sanitized[:200].rstrip()

    # Final validation - ensure we haven't accidentally created dangerous patterns
    if re.search(
        r"(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|UNION|SELECT)",
        sanitized,
        re.IGNORECASE,
    ):
        logger.error(f"Dangerous pattern found after sanitization: '{sanitized}'")
        raise ValueError("Sanitization failed - dangerous pattern detected")

    # Log successful sanitization if input was modified
    if sanitized != original_value:
        logger.info(
            f"JQL value sanitized: input_length={len(original_value)} output_length={len(sanitized)}"
        )

    return sanitized


# Export all security functions
__all__ = [
    "sanitize_query_string",
    "validate_field_list",
    "validate_project_filter",
    "validate_size_parameter",
    "validate_status_filter",
    "validate_hours_parameter",
    "validate_slop_parameter",
    "sanitize_error_message",
    "validate_es_query_dict",
    "sanitize_aggregation_field",
    "sanitize_jql_value",
    "MAX_RESULTS",
    "MAX_AGGREGATION_SIZE",
    "ALLOWED_ES_FIELDS",
    "ALLOWED_PROJECT_CODES",
    "ALLOWED_STATUS_VALUES",
    "ALLOWED_PRIORITY_VALUES",
]
