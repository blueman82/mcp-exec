"""
logging.py

This module provides a consistent logging setup for the application.
"""

import logging
import os
import sys
from typing import Optional


def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Set up and return a logger with the specified name and log level.

    Args:
        name: The name for the logger (typically __name__ from the module)
        level: The logging level (defaults to INFO if not specified)

    Returns:
        A configured logger instance
    """
    if level is None:
        # Read log level from environment variable, default to INFO
        log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        level = level_map.get(log_level_str, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if handlers are already configured to avoid duplicate handlers
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if not logging.getLogger().handlers:
        logging.basicConfig(stream=sys.stdout, level=level)

    logger.propagate = False
    return logger
