"""
token_utils.py

Provides utility functions for counting tokens using tiktoken
and truncating text based on token limits for OpenAI models.
Designed for English-only text and GPT-4o (o200k_base encoding).
"""

from typing import Callable, List

import tiktoken

from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Pre-initialize the tokenizer at module import time
logger.info("Initializing tiktoken tokenizer (o200k_base) at module import...")
_TOKENIZER_ENCODING = tiktoken.get_encoding("o200k_base")
logger.info("Tiktoken tokenizer initialized successfully.")


def get_tokenizer() -> tuple[Callable[[str], List[int]], Callable[[List[int]], str], bool]:
    """
    Returns the pre-initialized tokenizer functions.

    Returns:
        tuple containing:
            - The token encoding function (returns list of token IDs)
            - The token decoding function (returns string from token IDs)
            - True (always using tiktoken now)
    """
    return _TOKENIZER_ENCODING.encode, _TOKENIZER_ENCODING.decode, True


# --- Core Token Functions ---


def count_tokens(text: str) -> int:
    """
    Counts the number of tokens in the given text using the configured tokenizer.

    Args:
        text: The input string.

    Returns:
        The estimated number of tokens.
    """
    tokenizer_func, _, _ = get_tokenizer()

    try:
        tokens = tokenizer_func(text)
        return len(tokens) if isinstance(tokens, list) else 0
    except Exception as e:
        logger.error("Error counting tokens for text snippet: %s... Error: %s", text[:100], e)
        return 0


def tokens_to_words(token_count: int) -> int:
    """
    Roughly converts token count to word count (approx. 0.75 words/token).
    """
    return int(token_count * 0.75)
