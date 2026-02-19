"""Slack Block Kit formatters and modal builders for survey feature.

Provides formatters for survey DM messages, reminder nudges,
the interactive modal with 4 questions, and admin results display.
"""

from typing import Any


def _survey_button_block(survey_id: str) -> dict[str, Any]:
    """Build the 'Take Survey' actions block with primary button."""
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Take Survey"},
                "style": "primary",
                "action_id": f"survey_open_{survey_id}",
            }
        ],
    }


def format_survey_message(survey_id: str) -> list[dict[str, Any]]:
    """Format initial survey DM with 'Take Survey' button.

    Args:
        survey_id: Survey identifier embedded in action_id

    Returns:
        List of Slack Block Kit blocks
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":clipboard: *AskSplunk Feedback Survey*\n\n"
                    "We'd love your feedback on AskSplunk! "
                    "This short survey (4 questions) helps us improve the bot "
                    "for the Adobe Campaign Operations team."
                ),
            },
        },
        {"type": "divider"},
        _survey_button_block(survey_id),
    ]


def format_survey_reminder(survey_id: str, reminder_number: int) -> list[dict[str, Any]]:
    """Format survey reminder nudge message.

    Args:
        survey_id: Survey identifier
        reminder_number: Which reminder this is (1-3)

    Returns:
        List of Slack Block Kit blocks
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":bell: *Friendly reminder* (reminder {reminder_number}/3)\n\n"
                    "You haven't completed the AskSplunk feedback survey yet. "
                    "It only takes a minute!"
                ),
            },
        },
        _survey_button_block(survey_id),
    ]


def build_survey_modal(survey_id: str) -> dict[str, Any]:
    """Build Slack modal view with 4 survey questions.

    Q1: Usefulness (radio buttons — 3 choices)
    Q2: Accuracy (radio buttons — 3 choices)
    Q3: Feature request (plain text input)
    Q4: Sourcetype request (plain text input)

    Args:
        survey_id: Survey identifier embedded in callback_id

    Returns:
        Slack modal view definition dict
    """
    return {
        "type": "modal",
        "callback_id": f"survey_submit_{survey_id}",
        "title": {"type": "plain_text", "text": "AskSplunk Survey"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "q1_block",
                "label": {"type": "plain_text", "text": "How useful is AskSplunk for your work?"},
                "element": {
                    "type": "radio_buttons",
                    "action_id": "question_1",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Very useful"},
                            "value": "Very useful",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Somewhat useful"},
                            "value": "Somewhat useful",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Not useful"},
                            "value": "Not useful",
                        },
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "q2_block",
                "label": {
                    "type": "plain_text",
                    "text": "How accurate are the generated SPL queries?",
                },
                "element": {
                    "type": "radio_buttons",
                    "action_id": "question_2",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Usually correct"},
                            "value": "Usually correct",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Sometimes correct"},
                            "value": "Sometimes correct",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Rarely correct"},
                            "value": "Rarely correct",
                        },
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "q3_block",
                "label": {
                    "type": "plain_text",
                    "text": "What feature would you most like to see added?",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "question_3",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., multi-turn conversations, saved queries...",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "q4_block",
                "label": {
                    "type": "plain_text",
                    "text": "What additional sourcetypes would you like AskSplunk to support?",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "question_4",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., workflow logs, web tracking logs...",
                    },
                },
            },
        ],
    }


def format_survey_results(results: dict[str, Any]) -> str:
    """Format aggregated survey results as plain text for admin response.

    Args:
        results: Dict from SurveyManager.get_results()

    Returns:
        Formatted results string
    """
    lines = [
        f"*Survey Results: {results['survey_id']}*",
        f"Sent: {results['total_sent']} | Completed: {results['total_completed']} | "
        f"Rate: {results['completion_rate']}%",
        "",
    ]

    question_labels = {
        "question_1": "Usefulness",
        "question_2": "Accuracy",
        "question_3": "Feature Requests",
        "question_4": "Sourcetype Requests",
    }

    for q_key, label in question_labels.items():
        answers = results.get("answers", {}).get(q_key, {})
        if not answers:
            lines.append(f"*{label}:* No responses yet")
            continue

        lines.append(f"*{label}:*")
        for answer, count in sorted(answers.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {answer}: {count}")

    return "\n".join(lines)
