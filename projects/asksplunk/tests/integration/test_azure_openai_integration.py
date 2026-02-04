"""Integration tests for Azure OpenAI connectivity.

These tests require:
1. .env.test file with AWS_PROFILE set
2. Valid AWS credentials configured
3. Azure OpenAI credentials in AWS Secrets Manager
4. Network access to Azure OpenAI endpoint
"""

import pytest
from openai import AsyncAzureOpenAI

from asksplunk.secrets import SecretsManager


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azure_openai_chat_completion():
    """Test GPT-5 chat completion with real Azure OpenAI endpoint."""
    # Get credentials from Secrets Manager
    async with SecretsManager() as manager:
        config = await manager.get_azure_openai_config()

    # Create Azure OpenAI client
    async with AsyncAzureOpenAI(
        api_key=config["api_key"],
        api_version=config["api_version"],
        azure_endpoint=config["endpoint"],
    ) as client:
        # Test chat completion
        # Note: GPT-5 uses max_completion_tokens (not max_tokens) and temperature must be default (1)
        # GPT-5 supports up to 128K output tokens, using 2048 for simple chat
        response = await client.chat.completions.create(
            model=config["chat_deployment"],
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'test successful' if you can read this."},
            ],
            max_completion_tokens=2048,
        )

        # Verify response
        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content) > 0

        # Verify model used (Azure returns full version like gpt-5-2025-08-07)
        assert response.model.startswith(config["chat_deployment"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azure_openai_embeddings():
    """Test ADA-002 embeddings with real Azure OpenAI endpoint."""
    # Get credentials from Secrets Manager
    async with SecretsManager() as manager:
        config = await manager.get_azure_openai_config()

    # Create Azure OpenAI client
    async with AsyncAzureOpenAI(
        api_key=config["api_key"],
        api_version=config["api_version"],
        azure_endpoint=config["endpoint"],
    ) as client:
        # Test embeddings
        response = await client.embeddings.create(
            model=config["embedding_deployment"],
            input="test embedding",
        )

        # Verify response
        assert response.data is not None
        assert len(response.data) > 0
        assert response.data[0].embedding is not None

        # ADA-002 embeddings are 1536 dimensions
        assert len(response.data[0].embedding) == 1536

        # Verify model used
        assert response.model == config["embedding_deployment"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azure_openai_with_rag_style_query():
    """Test GPT-5 with a RAG-style system prompt (simulates agent behavior)."""
    # Get credentials from Secrets Manager
    async with SecretsManager() as manager:
        config = await manager.get_azure_openai_config()

    # Create Azure OpenAI client
    async with AsyncAzureOpenAI(
        api_key=config["api_key"],
        api_version=config["api_version"],
        azure_endpoint=config["endpoint"],
    ) as client:
        # Simulate RAG agent prompt
        system_prompt = """You are an expert at translating natural language questions about Adobe Campaign logs into Splunk SPL queries.

Use the following field documentation:
- mRecipientId: Recipient identifier (NUMBER)
- sBroadLogId: Broad log identifier (STRING)
- tsEmailDate: Email send timestamp (TIMESTAMP)

Generate an SPL query for the user's question."""

        user_question = "Show me all emails sent to recipient 12345 in the last hour"

        # Test chat completion with RAG-style prompt
        # Note: GPT-5 uses max_completion_tokens (not max_tokens) and temperature must be default (1)
        # GPT-5 supports up to 128K output tokens, using 4096 for SPL query generation
        response = await client.chat.completions.create(
            model=config["chat_deployment"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
            max_completion_tokens=4096,
        )

        # Verify response
        assert response.choices is not None
        assert len(response.choices) > 0
        content = response.choices[0].message.content
        assert content is not None
        assert len(content) > 0

        # Verify SPL query characteristics (should contain Splunk syntax)
        # With 4096 tokens, GPT-5 should have enough headroom for reasoning + output
        content_lower = content.lower()
        assert any(
            keyword in content_lower
            for keyword in ["index=", "search", "where", "mrecipientid", "spl", "splunk", "query"]
        ), f"Response should contain Splunk-related content. Got: {content[:300]}"
