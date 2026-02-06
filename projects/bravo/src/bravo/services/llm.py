"""LLM scoring service.

This module provides LLM-based ticket documentation quality scoring,
evaluating clarity, completeness, root cause analysis, and actionability.
"""

from dataclasses import dataclass

import structlog

from bravo.config import LLMSettings

logger = structlog.get_logger(__name__)


@dataclass
class LLMScore:
    """LLM scoring result.

    Attributes:
        clarity: Score for how clearly the issue is described (1-5).
        completeness: Score for information completeness (1-5).
        root_cause: Score for root cause identification (1-5).
        actionability: Score for clarity of next steps (1-5).
    """

    clarity: float
    completeness: float
    root_cause: float
    actionability: float

    @property
    def average(self) -> float:
        """Calculate average score.

        Returns:
            The mean of all four scoring dimensions.
        """
        return (self.clarity + self.completeness + self.root_cause + self.actionability) / 4

    def below_threshold(self, threshold: float) -> bool:
        """Check if average is below threshold.

        Args:
            threshold: The minimum acceptable average score.

        Returns:
            True if the average score is below the threshold.
        """
        return self.average < threshold


class LLMService:
    """Service for LLM-based ticket scoring.

    Evaluates Jira ticket documentation quality using an LLM to score
    four dimensions: clarity, completeness, root cause, and actionability.

    Attributes:
        settings: LLM configuration settings.
    """

    def __init__(self, settings: LLMSettings) -> None:
        """Initialize the LLM service.

        Args:
            settings: LLM configuration including model and threshold.
        """
        self.settings = settings

    async def score_ticket(
        self,
        ticket_key: str,
        summary: str,
        comments: list[str],
    ) -> LLMScore:
        """Score a ticket's documentation quality using LLM.

        Args:
            ticket_key: The Jira ticket key.
            summary: The ticket summary text.
            comments: List of comment texts from the ticket.

        Returns:
            LLMScore with scores for each dimension.
        """
        logger.info("scoring_ticket", ticket_key=ticket_key, model=self.settings.model)

        # TODO: Implement actual LLM call using self.build_prompt(summary, comments)
        _ = summary, comments  # Will be used when LLM integration is added
        score = LLMScore(
            clarity=3.0,
            completeness=3.0,
            root_cause=3.0,
            actionability=3.0,
        )

        logger.info(
            "ticket_scored",
            ticket_key=ticket_key,
            average=score.average,
            below_threshold=score.below_threshold(self.settings.threshold),
        )

        return score

    def build_prompt(self, summary: str, comments: list[str]) -> str:
        """Build scoring prompt for LLM.

        Args:
            summary: The ticket summary text.
            comments: List of comment texts from the ticket.

        Returns:
            The formatted prompt string for the LLM.
        """
        comments_text = "\n\n".join(comments) if comments else "No comments yet."

        return f"""Evaluate this Jira ticket for documentation quality.

Summary: {summary}

Comments:
{comments_text}

Score each dimension from 1-5:
1. Clarity: How clearly is the issue described?
2. Completeness: Is all necessary information provided?
3. Root Cause: Is the root cause identified or being investigated?
4. Actionability: Are next steps clear?

Respond in JSON format:
{{"clarity": X, "completeness": X, "root_cause": X, "actionability": X}}"""
