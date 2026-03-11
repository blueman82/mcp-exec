"""
Integration tests for Agent system prompt — validates LLM response structure
against the XML-tagged section contracts in agent_system.py.

These tests hit the REAL Azure OpenAI endpoint (gpt-4.1). They are NOT mocked.
Run with: pytest tests/integration/test_agent_prompt_structure.py -v -s

Requires:
    - AWS credentials (aws sso login --profile campaign_prod_v7)
    - Network access to Azure OpenAI endpoint
"""

import json
import os
import re
import sys

import aiohttp
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from packages.agent.prompts.agent_system import AGENT_SYSTEM_PROMPT
from packages.core.constants import AZURE_OPENAI_ENDPOINT
from packages.secrets.manager import SecretsManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYNTHETIC_CONTEXT = (
    "You are answering questions in Slack channel <#C0TEST123>.\n\n"
    "Here is relevant context from the channel's message history:\n\n"
    "[2026-03-10 13:15 UTC] <@U0R2K1>: Getting 502 errors on /api/v2 — anyone else seeing this?\n\n"
    "[2026-03-10 13:22 UTC] <@U0F3P2Q>: Confirmed. `curl https://api.internal/v2/health` returns "
    "`HTTP 502 Bad Gateway`. ALB shows 0 healthy targets.\n\n"
    "[2026-03-10 13:35 UTC] <@U0F3P2Q>: ALB access logs attached (screenshot). "
    "All 3 upstream pods returning 503.\n\n"
    "[2026-03-10 13:40 UTC] <@U0L8M3>: Root cause: upstream connection pool exhausted. "
    "Error from envoy sidecar:\n```\nupstream connect error or disconnect/reset before headers. "
    "reset reason: overflow, 0 healthy endpoints\n```\n\n"
    "[2026-03-10 14:02 UTC] <@U0L8M3>: Scaled pods from 3 to 6. "
    "Health checks passing now. CPGNCX-4521 raised for capacity planning.\n\n"
    "[2026-03-10 14:10 UTC] <@U0R2K1>: Confirmed — 502s resolved. Monitoring.\n\n"
    "---\n\n"
)


@pytest.fixture(scope="module")
def api_key():
    """Load Azure OpenAI API key from AWS Secrets Manager."""
    os.environ.setdefault("AWS_PROFILE", "campaign_prod_v7")
    os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")

    import asyncio

    async def _get_key():
        sm = SecretsManager()
        return await sm.get_azure_openai_lb_api_key()

    return asyncio.get_event_loop().run_until_complete(_get_key())


async def _call_agent(api_key: str, question: str) -> str:
    """Send a question through the agent system prompt to Azure OpenAI and return raw text."""
    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": SYNTHETIC_CONTEXT},
        {"role": "user", "content": question},
    ]

    payload = {
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.3,
        "top_p": 0.9,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            AZURE_OPENAI_ENDPOINT,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            assert resp.status == 200, f"Azure OpenAI returned {resp.status}: {await resp.text()}"
            data = await resp.json()

    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Structural validators
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    """Approximate word count (strips mrkdwn syntax)."""
    clean = re.sub(r"<[^>]+>", "LINK", text)  # collapse links
    clean = re.sub(r"[`*_~>•]", "", clean)     # strip mrkdwn chars
    return len(clean.split())


def assert_no_markdown_headers(text: str):
    """Agent must never use # headers — Slack doesn't render them."""
    lines = text.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        assert not re.match(r"^#{1,6}\s", stripped), (
            f"Response contains a Markdown header (Slack won't render this): '{stripped}'"
        )


def assert_no_double_asterisks(text: str):
    """Agent must use *bold* not **bold**."""
    assert "**" not in text, (
        "Response uses **double asterisks** — Slack mrkdwn uses single *asterisks* for bold"
    )


def assert_uses_bullet_character(text: str):
    """Agent should use • not - or * for bullets."""
    lines = text.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        # Lines starting with "- " (dash bullet) are wrong
        if re.match(r"^-\s", stripped):
            # Allow "---" dividers
            if stripped.startswith("---"):
                continue
            pytest.fail(
                f"Response uses '- ' dash bullets instead of '•': '{stripped}'"
            )


def assert_has_bold_first_line(text: str):
    """First line should contain *bold* text (the direct answer)."""
    first_line = text.strip().split("\n")[0]
    assert re.search(r"\*[^*]+\*", first_line), (
        f"First line lacks *bold* direct answer: '{first_line}'"
    )


def assert_has_bullets(text: str):
    """Response body should contain • bullets for supporting detail."""
    assert "•" in text, "Response has no • bullet points for supporting detail"


def assert_jira_tickets_are_links(text: str):
    """Any JIRA ticket reference should be a clickable <url|label> link."""
    # Find bare ticket references NOT inside a link
    bare_tickets = re.findall(
        r"(?<!\|)(?<!browse/)\b(CPGNCX|CPGNREQ|CPGNTT|NEO|PLATIR|CSOPM|AMSE|CPGNPROV)-\d+\b(?![^<]*>)",
        text,
    )
    assert not bare_tickets, (
        f"JIRA tickets not formatted as clickable links: {bare_tickets}"
    )


def assert_user_mentions_preserved(text: str):
    """Response should use <@U...> format for user attribution."""
    assert "<@U" in text, "Response doesn't attribute actions to users with <@U...> mentions"


def assert_word_count_under(text: str, limit: int):
    """Response should be under the word limit."""
    count = _count_words(text)
    assert count <= limit, (
        f"Response is {count} words — exceeds {limit}-word target"
    )


# ---------------------------------------------------------------------------
# Test cases — one per question type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_status_question_structure(api_key):
    """Status question: should produce bold first line + bullets + JIRA link."""
    response = await _call_agent(api_key, "What's the current status?")

    print(f"\n{'='*60}\nSTATUS RESPONSE ({_count_words(response)} words):\n{'='*60}")
    print(response)

    assert_no_markdown_headers(response)
    assert_no_double_asterisks(response)
    assert_has_bold_first_line(response)
    assert_has_bullets(response)
    assert_uses_bullet_character(response)
    assert_jira_tickets_are_links(response)
    assert_user_mentions_preserved(response)
    assert_word_count_under(response, 250)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_timeline_question_structure(api_key):
    """Timeline question: should produce chronological bullets with timestamps."""
    response = await _call_agent(api_key, "What happened? Give me the timeline.")

    print(f"\n{'='*60}\nTIMELINE RESPONSE ({_count_words(response)} words):\n{'='*60}")
    print(response)

    assert_no_markdown_headers(response)
    assert_no_double_asterisks(response)
    assert_has_bold_first_line(response)
    assert_has_bullets(response)
    assert_uses_bullet_character(response)
    assert_jira_tickets_are_links(response)
    assert_user_mentions_preserved(response)

    # Timeline should contain time references
    assert re.search(r"\d{1,2}:\d{2}", response), "Timeline response has no time references"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_technical_question_structure(api_key):
    """Technical question: should preserve code blocks from context."""
    response = await _call_agent(api_key, "What was the error message?")

    print(f"\n{'='*60}\nTECHNICAL RESPONSE ({_count_words(response)} words):\n{'='*60}")
    print(response)

    assert_no_markdown_headers(response)
    assert_no_double_asterisks(response)
    assert_has_bold_first_line(response)
    assert_user_mentions_preserved(response)

    # Should contain code formatting for the error
    has_code = "`" in response or "```" in response
    assert has_code, "Technical response doesn't use code formatting for error details"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_person_question_structure(api_key):
    """Person question: should attribute actions to a specific user."""
    response = await _call_agent(api_key, "What did <@U0L8M3> do?")

    print(f"\n{'='*60}\nPERSON RESPONSE ({_count_words(response)} words):\n{'='*60}")
    print(response)

    assert_no_markdown_headers(response)
    assert_no_double_asterisks(response)
    assert_has_bold_first_line(response)
    assert_has_bullets(response)
    assert_uses_bullet_character(response)

    # Should reference the specific user asked about
    assert "<@U0L8M3>" in response, "Response doesn't reference the specific user asked about"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_insufficient_context_structure(api_key):
    """Out-of-scope question: should acknowledge limitation clearly."""
    response = await _call_agent(api_key, "What's happening with the email delivery pipeline?")

    print(f"\n{'='*60}\nINSUFFICIENT CONTEXT RESPONSE ({_count_words(response)} words):\n{'='*60}")
    print(response)

    assert_no_markdown_headers(response)
    assert_no_double_asterisks(response)
    assert_word_count_under(response, 150)

    # Should indicate it doesn't have the answer
    limitation_signals = [
        "don't have", "no mention", "not found", "no messages",
        "doesn't appear", "isn't mentioned", "not discussed",
        "cannot find", "no context", "don't see", "not in",
    ]
    text_lower = response.lower()
    has_limitation = any(signal in text_lower for signal in limitation_signals)
    assert has_limitation, "Response doesn't acknowledge lack of context for out-of-scope question"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_question_parrot(api_key):
    """Agent should NOT repeat the user's question back."""
    question = "Who identified the root cause?"
    response = await _call_agent(api_key, question)

    print(f"\n{'='*60}\nPARROT CHECK ({_count_words(response)} words):\n{'='*60}")
    print(response)

    # First line shouldn't be the question repeated
    first_line = response.strip().split("\n")[0].lower()
    assert "who identified the root cause" not in first_line, (
        "Agent repeated the user's question in the first line"
    )
