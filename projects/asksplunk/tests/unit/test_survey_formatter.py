"""Unit tests for survey formatter.

Tests Block Kit message builders, modal structure, and results formatter.
"""

from asksplunk.survey.formatter import (
    build_survey_modal,
    format_survey_message,
    format_survey_reminder,
    format_survey_results,
)


class TestFormatSurveyMessage:
    """Test format_survey_message."""

    def test_returns_blocks_with_button(self) -> None:
        blocks = format_survey_message("survey_2026_q1")

        assert len(blocks) == 3
        assert blocks[0]["type"] == "section"
        assert "AskSplunk" in blocks[0]["text"]["text"]
        assert blocks[1]["type"] == "divider"
        assert blocks[2]["type"] == "actions"

        button = blocks[2]["elements"][0]
        assert button["type"] == "button"
        assert button["action_id"] == "survey_open_survey_2026_q1"
        assert button["style"] == "primary"

    def test_embeds_survey_id_in_action(self) -> None:
        blocks = format_survey_message("test_id")
        button = blocks[2]["elements"][0]
        assert button["action_id"] == "survey_open_test_id"


class TestFormatSurveyReminder:
    """Test format_survey_reminder."""

    def test_includes_reminder_number(self) -> None:
        blocks = format_survey_reminder("survey_2026_q1", 2)

        assert "reminder 2/3" in blocks[0]["text"]["text"]

    def test_includes_survey_button(self) -> None:
        blocks = format_survey_reminder("survey_2026_q1", 1)

        button = blocks[1]["elements"][0]
        assert button["action_id"] == "survey_open_survey_2026_q1"


class TestBuildSurveyModal:
    """Test build_survey_modal."""

    def test_modal_structure(self) -> None:
        modal = build_survey_modal("survey_2026_q1")

        assert modal["type"] == "modal"
        assert modal["callback_id"] == "survey_submit_survey_2026_q1"
        assert modal["title"]["text"] == "AskSplunk Survey"
        assert modal["submit"]["text"] == "Submit"
        assert modal["close"]["text"] == "Cancel"

    def test_has_four_questions(self) -> None:
        modal = build_survey_modal("survey_2026_q1")
        blocks = modal["blocks"]

        assert len(blocks) == 4

    def test_q1_radio_buttons(self) -> None:
        modal = build_survey_modal("survey_2026_q1")
        q1 = modal["blocks"][0]

        assert q1["type"] == "input"
        assert q1["block_id"] == "q1_block"
        element = q1["element"]
        assert element["type"] == "radio_buttons"
        assert element["action_id"] == "question_1"
        assert len(element["options"]) == 3
        values = [opt["value"] for opt in element["options"]]
        assert "Very useful" in values
        assert "Somewhat useful" in values
        assert "Not useful" in values

    def test_q2_radio_buttons(self) -> None:
        modal = build_survey_modal("survey_2026_q1")
        q2 = modal["blocks"][1]

        assert q2["block_id"] == "q2_block"
        element = q2["element"]
        assert element["type"] == "radio_buttons"
        assert element["action_id"] == "question_2"
        assert len(element["options"]) == 3

    def test_q3_text_input(self) -> None:
        modal = build_survey_modal("survey_2026_q1")
        q3 = modal["blocks"][2]

        assert q3["block_id"] == "q3_block"
        element = q3["element"]
        assert element["type"] == "plain_text_input"
        assert element["action_id"] == "question_3"
        assert element["multiline"] is True

    def test_q4_text_input(self) -> None:
        modal = build_survey_modal("survey_2026_q1")
        q4 = modal["blocks"][3]

        assert q4["block_id"] == "q4_block"
        element = q4["element"]
        assert element["type"] == "plain_text_input"
        assert element["action_id"] == "question_4"
        assert element["multiline"] is True


class TestFormatSurveyResults:
    """Test format_survey_results."""

    def test_format_with_data(self) -> None:
        results = {
            "survey_id": "survey_2026_q1",
            "total_sent": 10,
            "total_responses": 5,
            "total_completed": 5,
            "completion_rate": 50.0,
            "answers": {
                "question_1": {"Very useful": 3, "Somewhat useful": 2},
                "question_2": {"Usually correct": 4, "Sometimes correct": 1},
                "question_3": {"More features": 2, "Better docs": 1},
                "question_4": {},
            },
        }

        text = format_survey_results(results)

        assert "survey_2026_q1" in text
        assert "Sent: 10" in text
        assert "Completed: 5" in text
        assert "50.0%" in text
        assert "Very useful: 3" in text
        assert "Sourcetype Requests" in text
        assert "No responses yet" in text

    def test_format_empty_results(self) -> None:
        results = {
            "survey_id": "empty",
            "total_sent": 0,
            "total_responses": 0,
            "total_completed": 0,
            "completion_rate": 0,
            "answers": {
                "question_1": {},
                "question_2": {},
                "question_3": {},
                "question_4": {},
            },
        }

        text = format_survey_results(results)

        assert "empty" in text
        assert "Sent: 0" in text
