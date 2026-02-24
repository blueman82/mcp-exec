"""
Handover Summary Service Module.

This module provides functionality for generating and posting on-call shift handover
summaries to Slack. It analyzes active incident channels, collects messages and JIRA
comments from a configured time window, and uses AI to generate ultra-compact summaries.

Public Functions:
    generate_and_post_handover: Main entry point for handover summary generation
"""

from .generator import generate_and_post_handover

__all__ = ["generate_and_post_handover"]
