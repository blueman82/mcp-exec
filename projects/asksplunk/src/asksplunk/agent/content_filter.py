"""Content filtering and input sanitization for harmful/malicious requests.

Implements OWASP LLM Prompt Injection Prevention recommendations:
- Input validation with pattern matching
- Typoglycemia attack detection (scrambled words)
- Base64 encoding detection
- Output validation for system prompt leakage

Reference: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
"""

import base64
import re
from dataclasses import dataclass

# Prompt injection patterns (case-insensitive)
INJECTION_PATTERNS = [
    r"\bignore\b.{0,20}\binstructions?\b",
    r"\bdisregard\b.{0,20}\binstructions?\b",
    r"\bforget\b.{0,20}(everything|all|previous)",
    r"\bpretend\b.{0,20}(you\s+are|to\s+be|you're)",
    r"\bact\s+as\s+(if|a|an)\b",
    r"\byou\s+are\s+now\b",
    r"\bnew\s+persona\b",
    r"\bjailbreak\b",
    r"\bDAN\s+mode\b",
    r"\bbypass\b.{0,20}(filter|safety|content)",
    r"\boverride\b.{0,20}(system|safety|instructions?)",
    r"\breveal\b.{0,20}(system|prompt|instructions?)",
    r"\bwhat\s+are\s+your\s+instructions\b",
    r"\brepeat\b.{0,20}(system\s+)?prompt",
    r"\bdeveloper\s+mode\b",
    r"\bsystem\s+override\b",
]

# Keywords to check for typoglycemia variants (OWASP recommendation)
FUZZY_KEYWORDS = [
    "ignore",
    "bypass",
    "override",
    "reveal",
    "delete",
    "system",
    "instructions",
    "jailbreak",
]

# Compiled patterns for efficiency
_INJECTION_REGEX = re.compile(
    "|".join(f"({p})" for p in INJECTION_PATTERNS),
    re.IGNORECASE,
)

# Output patterns indicating successful injection (system prompt leakage)
OUTPUT_SUSPICIOUS_PATTERNS = [
    r"SYSTEM\s*[:]\s*You\s+are",
    r"API[_\s]?KEY\s*[:=]\s*\w+",
    r"\bmy\s+instructions?\s+(are|were)\b",
    r"\bI\s+was\s+instructed\s+to\b",
]

_OUTPUT_SUSPICIOUS_REGEX = re.compile(
    "|".join(f"({p})" for p in OUTPUT_SUSPICIOUS_PATTERNS),
    re.IGNORECASE,
)


@dataclass
class ContentFilterResult:
    """Result of content filtering check."""

    is_safe: bool
    reason: str | None = None
    matched_pattern: str | None = None


def _is_typoglycemia_variant(word: str, target: str) -> bool:
    """Check if word is a typoglycemia variant of target.

    Typoglycemia: scrambled middle letters with same first/last letters.
    Example: "ignroe" is a variant of "ignore"

    Args:
        word: Word to check
        target: Target word to match against

    Returns:
        True if word appears to be a scrambled variant of target
    """
    if len(word) != len(target) or len(word) < 4:
        return False
    # Same first and last letter, scrambled middle
    return (
        word[0].lower() == target[0].lower()
        and word[-1].lower() == target[-1].lower()
        and sorted(word[1:-1].lower()) == sorted(target[1:-1].lower())
        and word.lower() != target.lower()  # Not exact match
    )


def _check_typoglycemia(text: str) -> ContentFilterResult:
    """Check for typoglycemia attacks (scrambled words).

    Args:
        text: User input text to check

    Returns:
        ContentFilterResult with is_safe=False if typoglycemia detected
    """
    words = re.findall(r"\b\w+\b", text.lower())
    for word in words:
        for keyword in FUZZY_KEYWORDS:
            if _is_typoglycemia_variant(word, keyword):
                return ContentFilterResult(
                    is_safe=False,
                    reason="typoglycemia_attack",
                    matched_pattern=f"{word} (variant of {keyword})",
                )
    return ContentFilterResult(is_safe=True)


def _check_base64_injection(text: str) -> ContentFilterResult:
    """Check for Base64 encoded injection attempts.

    Args:
        text: User input text to check

    Returns:
        ContentFilterResult with is_safe=False if encoded injection detected
    """
    # Look for Base64-like strings (at least 20 chars, valid Base64 alphabet)
    base64_pattern = r"[A-Za-z0-9+/]{20,}={0,2}"
    matches = re.findall(base64_pattern, text)

    for match in matches:
        try:
            decoded = base64.b64decode(match).decode("utf-8", errors="ignore").lower()
            # Check if decoded content contains injection patterns
            if _INJECTION_REGEX.search(decoded):
                return ContentFilterResult(
                    is_safe=False,
                    reason="encoded_injection",
                    matched_pattern=f"Base64: {match[:20]}...",
                )
        except Exception:
            continue

    return ContentFilterResult(is_safe=True)


def check_prompt_injection(text: str) -> ContentFilterResult:
    """Check if text contains prompt injection attempts.

    Checks for:
    - Direct injection patterns
    - Typoglycemia attacks (scrambled words)
    - Base64 encoded injections

    Args:
        text: User input text to check

    Returns:
        ContentFilterResult with is_safe=False if injection detected
    """
    # Check direct patterns
    match = _INJECTION_REGEX.search(text)
    if match:
        return ContentFilterResult(
            is_safe=False,
            reason="prompt_injection",
            matched_pattern=match.group(0),
        )

    # Check typoglycemia attacks
    typo_result = _check_typoglycemia(text)
    if not typo_result.is_safe:
        return typo_result

    # Check Base64 encoded injections
    base64_result = _check_base64_injection(text)
    if not base64_result.is_safe:
        return base64_result

    return ContentFilterResult(is_safe=True)


def check_output_safety(output: str) -> ContentFilterResult:
    """Check if LLM output contains signs of successful injection.

    Monitors for system prompt leakage or API key exposure.

    Args:
        output: LLM generated output to check

    Returns:
        ContentFilterResult with is_safe=False if suspicious output detected
    """
    match = _OUTPUT_SUSPICIOUS_REGEX.search(output)
    if match:
        return ContentFilterResult(
            is_safe=False,
            reason="output_leakage",
            matched_pattern=match.group(0),
        )
    return ContentFilterResult(is_safe=True)


def check_content_safety(text: str) -> ContentFilterResult:
    """Check if content is appropriate for processing.

    Combines injection detection with basic content checks.

    Args:
        text: User input text to check

    Returns:
        ContentFilterResult indicating if content is safe
    """
    return check_prompt_injection(text)


# Standard refusal message for harmful content
REFUSAL_MESSAGE = (
    "I can only help with Adobe Campaign Splunk queries. "
    "I cannot respond to requests that are off-topic, contain harmful content, "
    "or attempt to manipulate my responses. "
    "Please ask about bounces, deliveries, workflows, or other log data."
)
