"""Agent orchestrator managing query generation workflow.

State machine orchestrator that coordinates between DocumentRetriever,
SessionManager, and OpenAI to process natural language questions into SPL queries.
"""

import json
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog

from asksplunk.agent.content_filter import (
    REFUSAL_MESSAGE,
    check_content_safety,
    check_output_safety,
)
from asksplunk.retriever.retriever import DocumentRetriever
from asksplunk.secrets import SecretsManager
from asksplunk.session.manager import SessionManager
from asksplunk.usage import UsageTracker

logger = structlog.get_logger()


# GPT-5 function definitions for agent
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "assess_confidence",
            "description": "Assess confidence level for generating SPL query based on available documentation",
            "parameters": {
                "type": "object",
                "properties": {
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Confidence percentage (0-100) that you can generate an accurate query",
                    },
                    "missing_info": {
                        "type": "string",
                        "description": "What information is missing or unclear (if confidence < 70)",
                    },
                    "clarification_needed": {
                        "type": "string",
                        "description": "What clarification to ask user (if 70 <= confidence < 90)",
                    },
                },
                "required": ["confidence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_spl_query",
            "description": "Generate SPL query from user question and field documentation",
            "parameters": {
                "type": "object",
                "properties": {
                    "spl_query": {
                        "type": "string",
                        "description": "The SPL query to search Adobe Campaign logs",
                    },
                    "plain_explanation": {
                        "type": "string",
                        "description": "Simple language explanation for non-technical users",
                    },
                    "technical_explanation": {
                        "type": "string",
                        "description": "Technical details about fields and commands used (in brackets)",
                    },
                },
                "required": ["spl_query", "plain_explanation", "technical_explanation"],
            },
        },
    },
]


class AgentState(Enum):
    """Agent state machine states.

    State flow:
        INITIALIZE → EVALUATE → (CLARIFY → WAIT → REFINE)* → GENERATE → COMPLETE

    States:
        INITIALIZE: New conversation, retrieve docs
        EVALUATE: Assess confidence, decide next action
        CLARIFY: Ask clarifying question (low confidence)
        WAIT: Waiting for user response to clarification
        REFINE: Process user answer, re-retrieve docs
        GENERATE: Generate SPL query (high confidence)
        COMPLETE: Query sent, session deleted
        UNCERTAIN: Cannot generate query (honest unknown)
    """

    INITIALIZE = "INITIALIZE"
    EVALUATE = "EVALUATE"
    CLARIFY = "CLARIFY"
    WAIT = "WAIT"
    REFINE = "REFINE"
    GENERATE = "GENERATE"
    COMPLETE = "COMPLETE"
    UNCERTAIN = "UNCERTAIN"


class Agent:
    """Orchestrates query generation using GPT-5 agent with RAG.

    Manages state machine for processing natural language questions into
    SPL queries. Retrieves relevant documentation, asks clarifying questions
    when needed, and generates queries with dual explanations.

    This class implements the orchestration layer. Task 16 will add GPT-5
    evaluation and query generation logic.

    Attributes:
        retriever: DocumentRetriever for RAG
        session_manager: SessionManager for DynamoDB
        openai_client: AsyncAzureOpenAI client for GPT-5

    Example:
        from openai import AsyncAzureOpenAI
        import chromadb

        openai_client = AsyncAzureOpenAI(...)
        chroma_client = chromadb.HttpClient(...)

        retriever = DocumentRetriever(openai_client, chroma_client)

        async with SessionManager() as session_manager:
            agent = Agent(retriever, session_manager, openai_client)
            result = await agent.process_question(
                "show me bounces",
                "thread-123",
                "U123",
                "C456"
            )
    """

    def __init__(
        self,
        retriever: DocumentRetriever,
        session_manager: SessionManager,
        openai_client: Any,  # AsyncAzureOpenAI
        chat_model: str = "gpt-5",
        usage_tracker: UsageTracker | None = None,
    ):
        """Initialize agent with dependencies.

        Args:
            retriever: DocumentRetriever instance for RAG
            session_manager: SessionManager for session state
            openai_client: Configured AsyncAzureOpenAI client
            chat_model: Azure OpenAI deployment name for chat completions
            usage_tracker: Optional UsageTracker for admin usage reporting
        """
        self.retriever = retriever
        self.chat_model = chat_model
        self.session_manager = session_manager
        self.openai_client = openai_client
        self.usage_tracker = usage_tracker
        # Store callbacks per thread_id to handle concurrent requests
        self._status_callbacks: dict[str, Any] = {}

    async def _send_status(self, thread_id: str, message: str) -> None:
        """Send status update via callback if available for the given thread."""
        callback = self._status_callbacks.get(thread_id)
        if callback:
            try:
                await callback(message)
            except Exception as e:
                logger.warning("status_callback_failed", error=str(e), thread_id=thread_id)

    def _is_usage_query(self, question: str) -> bool:
        """Detect if question is asking for usage data."""
        question_lower = question.lower()
        usage_keywords = ["usage", "how many", "requests", "queries"]
        time_keywords = ["day", "hour", "week", "minute", "yesterday", "today"]
        return any(uk in question_lower for uk in usage_keywords) and any(
            tk in question_lower for tk in time_keywords
        )

    def _parse_time_range(self, question: str) -> tuple[datetime, datetime]:
        """Parse time range from natural language question.

        Supports: X days, X hours, X weeks, X minutes, yesterday, today
        Returns (start, end) datetime tuple.
        """
        now = datetime.utcnow()
        question_lower = question.lower()

        # Match patterns like "7 days", "24 hours", "2 weeks", "30 minutes"
        match = re.search(r"(\d+)\s*(day|hour|week|minute)s?", question_lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "day":
                delta = timedelta(days=amount)
            elif unit == "hour":
                delta = timedelta(hours=amount)
            elif unit == "week":
                delta = timedelta(weeks=amount)
            elif unit == "minute":
                delta = timedelta(minutes=amount)
            else:
                delta = timedelta(days=7)  # default
            return (now - delta, now)

        # Handle "yesterday"
        if "yesterday" in question_lower:
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            return (start, end)

        # Handle "today"
        if "today" in question_lower:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return (start, now)

        # Default: last 7 days
        return (now - timedelta(days=7), now)

    async def process_question(
        self,
        question: str,
        thread_id: str,
        user_id: str,
        channel_id: str,
        status_callback=None,
    ) -> dict[str, Any]:
        """Process new question or continuation of existing conversation.

        Determines if this is new conversation or continuation, loads/creates
        session accordingly, and orchestrates state machine to generate query.

        Args:
            question: User's natural language question or answer to clarification
            thread_id: Slack thread_ts for session key
            user_id: Slack user ID
            channel_id: Slack channel ID
            status_callback: Optional async function to send status updates

        Returns:
            Dictionary with:
                - action (str): "clarify" or "query_generated" or "uncertain"
                - content (dict): Message content (query or question)
                - state (str): Current agent state
                - ... other session fields

        Example:
            result = await agent.process_question(
                "show me delivery failures",
                "1234.5678",
                "U123",
                "C456"
            )

            if result["action"] == "query_generated":
                # Display query to user
                query = result["content"]["spl_query"]
                explanation = result["content"]["plain_explanation"]
        """
        # Store callback per thread_id for concurrent request safety
        if status_callback:
            self._status_callbacks[thread_id] = status_callback

        # Check for usage query (admin only)
        if self._is_usage_query(question):
            if not UsageTracker.is_admin(user_id):
                logger.info("non_admin_usage_query_rejected", user=user_id)
                return {
                    "action": "blocked",
                    "state": AgentState.COMPLETE.value,
                    "content": {"message": "Usage data is only available to administrators."},
                }

            if self.usage_tracker:
                start, end = self._parse_time_range(question)
                count = await self.usage_tracker.get_usage(start, end)
                return {
                    "action": "usage_report",
                    "state": AgentState.COMPLETE.value,
                    "content": {
                        "message": f"Usage report: {count} queries from {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')} UTC"
                    },
                }
            else:
                return {
                    "action": "blocked",
                    "state": AgentState.COMPLETE.value,
                    "content": {"message": "Usage tracking is not configured."},
                }

        # Check for harmful content / prompt injection before processing
        safety_check = check_content_safety(question)
        if not safety_check.is_safe:
            logger.warning(
                "content_filtered",
                thread_id=thread_id,
                reason=safety_check.reason,
            )
            return {
                "action": "blocked",
                "state": AgentState.COMPLETE.value,
                "content": {"message": REFUSAL_MESSAGE},
            }

        # Get or create session
        session = await self.session_manager.get_session(thread_id)

        if not session:
            # New conversation - INITIALIZE
            logger.info("agent_initializing", thread_id=thread_id)
            await self._send_status(thread_id, ":mag: Searching documentation...")
            session = await self._initialize_session(thread_id, user_id, channel_id, question)

        # Process based on current state
        current_state = AgentState(session["agent_state"])
        logger.info("agent_processing", thread_id=thread_id, state=current_state.value)

        try:
            return await self._dispatch_state(current_state, session, question)
        finally:
            # Clean up callback to prevent memory leaks
            self._status_callbacks.pop(thread_id, None)

    async def _dispatch_state(
        self, state: AgentState, session: dict[str, Any], question: str
    ) -> dict[str, Any]:
        """Dispatch to appropriate state handler.

        Args:
            state: Current agent state
            session: Session dictionary
            question: User's question (used for WAIT/REFINE states)

        Returns:
            Result from the state handler
        """
        if state == AgentState.INITIALIZE:
            return await self._handle_initialize(session)
        elif state == AgentState.EVALUATE:
            # Check if user sent a NEW question (different from original)
            # Only applies when original_question exists (not first evaluation)
            original_question = session.get("original_question", "")
            if original_question and question and question != original_question:
                # User is trying again with a new question - update and re-retrieve
                logger.info(
                    "evaluate_new_question",
                    thread_id=session["thread_id"],
                    original_len=len(original_question),
                    new_len=len(question),
                )
                await self._send_status(session["thread_id"], ":mag: Searching documentation...")
                docs = await self.retriever.retrieve(question, top_k=5)
                await self.session_manager.update_session(
                    session["thread_id"],
                    {
                        "original_question": question,
                        "retrieved_docs": [{"content": doc["content"]} for doc in docs],
                    },
                )
                # Refresh session with updated data
                refreshed = await self.session_manager.get_session(session["thread_id"])
                if refreshed is None:
                    logger.error("session_lost_during_refresh", thread_id=session["thread_id"])
                    return session
                session = refreshed
            return await self._handle_evaluate(session)
        elif state == AgentState.WAIT:
            return await self._handle_wait(session, question)
        elif state == AgentState.REFINE:
            return await self._handle_refine(session, question)
        elif state == AgentState.GENERATE:
            return await self._handle_generate(session)
        elif state == AgentState.COMPLETE:
            return await self._handle_complete(session)
        elif state == AgentState.CLARIFY:
            return session
        else:
            logger.error("unknown_agent_state", state=state.value)
            return session

    async def _initialize_session(
        self, thread_id: str, user_id: str, channel_id: str, question: str
    ) -> dict[str, Any]:
        """Create new session in INITIALIZE state.

        Creates session in DynamoDB, performs initial RAG retrieval,
        and transitions to EVALUATE state.

        Args:
            thread_id: Session identifier
            user_id: Slack user ID
            channel_id: Slack channel ID
            question: Original user question

        Returns:
            Created session dictionary with retrieved docs

        Note:
            Question is stored temporarily in session for query generation.
            Session is deleted immediately in COMPLETE state for privacy.
        """
        # Create session with original question
        await self.session_manager.create_session(
            thread_id=thread_id,
            user_id=user_id,
            channel_id=channel_id,
            question=question,
        )

        logger.info("agent_retrieving_docs", thread_id=thread_id)

        # Initial RAG retrieval
        docs = await self.retriever.retrieve(question, top_k=5)

        # Update session with retrieved docs and transition to EVALUATE
        # Note: Don't store float scores - DynamoDB requires Decimal
        await self.session_manager.update_session(
            thread_id,
            {
                "agent_state": AgentState.EVALUATE.value,
                "retrieved_docs": [{"content": doc["content"]} for doc in docs],
            },
        )

        logger.info(
            "agent_initialized",
            thread_id=thread_id,
            docs_retrieved=len(docs),
        )

        result = await self.session_manager.get_session(thread_id)
        if result is None:
            raise RuntimeError(f"Session lost after initialization: {thread_id}")
        return result

    async def _handle_initialize(self, session: dict[str, Any]) -> dict[str, Any]:
        """Handle INITIALIZE state.

        Note: This should not be called directly - _initialize_session handles
        initialization and transitions to EVALUATE. This method exists for
        completeness of state machine.

        Args:
            session: Current session state

        Returns:
            Session dict
        """
        logger.warning(
            "initialize_state_handler_called",
            thread_id=session["thread_id"],
            message="Initialization should be handled by _initialize_session",
        )
        return session

    async def _handle_evaluate(self, session: dict[str, Any]) -> dict[str, Any]:
        """Handle EVALUATE state: Assess confidence and route accordingly.

        Calls GPT to assess confidence level based on retrieved docs.
        Routes to appropriate action based on confidence thresholds:
        - >= 50%: Generate query (user gave enough detail)
        - 30-49%: Ask ONE clarifying question (only if genuinely ambiguous)
        - < 30%: Admit uncertainty (very rare)

        Also breaks clarification loops after 2 attempts.

        Args:
            session: Current session state with retrieved_docs

        Returns:
            Action dictionary with:
                - action: "query_generated", "need_clarification", or "uncertain"
                - content: Query dict, clarification request, or missing info
                - state: COMPLETE, CLARIFY, or UNCERTAIN
                - confidence: Confidence score (0-100)

        Example:
            result = await agent._handle_evaluate(session)
            if result["confidence"] >= 90:
                print(result["content"]["spl_query"])
        """
        logger.info(
            "agent_evaluating",
            thread_id=session["thread_id"],
            docs_count=len(session.get("retrieved_docs", [])),
        )

        # Check for clarification loop - if we've asked 2+ times, just generate
        clarifying_history = session.get("clarifying_history", [])
        if len(clarifying_history) >= 2:
            logger.info(
                "breaking_clarification_loop",
                thread_id=session["thread_id"],
                clarifications_count=len(clarifying_history),
            )
            context = "\n\n".join(
                [f"**{doc['content']}**" for doc in session.get("retrieved_docs", [])[:5]]
            )
            return await self._generate_query(session, context)

        # Build context from retrieved docs
        context = "\n\n".join(
            [f"**{doc['content']}**" for doc in session.get("retrieved_docs", [])[:5]]
        )

        # Build messages for GPT-5 confidence assessment
        messages = [
            {"role": "system", "content": self._get_confidence_system_prompt()},
            {
                "role": "user",
                "content": f"Question: {session.get('original_question', '')}\n\nAvailable documentation:\n{context}",
            },
        ]

        # Step 1: Assess confidence
        await self._send_status(session["thread_id"], ":thinking_face: Evaluating your question...")
        logger.info("assessing_confidence", thread_id=session["thread_id"])
        response = await self.openai_client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice={"type": "function", "function": {"name": "assess_confidence"}},
        )

        # Parse confidence assessment
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "assess_confidence":
                assessment = json.loads(tool_call.function.arguments)
                confidence = assessment.get("confidence", 0)

                logger.info(
                    "confidence_assessed",
                    thread_id=session["thread_id"],
                    confidence=confidence,
                )

                # Step 2: Route based on confidence threshold
                if confidence >= 70:
                    # Confident enough - generate query
                    await self._send_status(
                        session["thread_id"], ":sparkles: Generating SPL query..."
                    )
                    logger.info(
                        "confident_generate", thread_id=session["thread_id"], confidence=confidence
                    )
                    return await self._generate_query(session, context)

                elif confidence >= 50:
                    # Medium confidence - ask ONE clarifying question
                    logger.info(
                        "low_confidence_clarify",
                        thread_id=session["thread_id"],
                        confidence=confidence,
                    )
                    clarification_type = assessment.get(
                        "clarification_needed", "Need more information"
                    )

                    return await self._request_clarification(session, context, clarification_type)

                else:
                    # Low confidence - admit uncertainty
                    logger.info("low_confidence_uncertain", thread_id=session["thread_id"])
                    missing_info = assessment.get(
                        "missing_info", "Insufficient information to generate query"
                    )

                    return {
                        "action": "uncertain",
                        "state": AgentState.UNCERTAIN.value,
                        "confidence": confidence,
                        "content": {"missing_info": missing_info},
                    }

        # Fallback: No confidence assessment (shouldn't happen with tool_choice)
        logger.warning("no_confidence_assessment", thread_id=session["thread_id"])
        return {"action": "need_clarification", "state": AgentState.CLARIFY.value}

    async def _generate_query(self, session: dict[str, Any], context: str) -> dict[str, Any]:
        """Generate SPL query with high confidence.

        Called when confidence >= 90%. Uses generate_spl_query function.

        Args:
            session: Current session state
            context: Formatted context from retrieved docs

        Returns:
            Action dict with generated query and explanations

        Example:
            result = await agent._generate_query(session, context)
            print(result["content"]["spl_query"])
        """
        # Build messages for query generation
        original_question = session.get("original_question", "")
        messages = [
            {"role": "system", "content": self._get_query_generation_system_prompt()},
            {
                "role": "user",
                "content": f"""Generate a Splunk query for this question:

"{original_question}"

Field documentation:
{context}""",
            },
        ]

        # Call GPT to generate query
        response = await self.openai_client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice={"type": "function", "function": {"name": "generate_spl_query"}},
        )

        # Parse generated query
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "generate_spl_query":
                result = json.loads(tool_call.function.arguments)

                # Validate output for potential system prompt leakage (OWASP)
                output_text = " ".join(str(v) for v in result.values())
                output_check = check_output_safety(output_text)
                if not output_check.is_safe:
                    logger.warning(
                        "output_filtered",
                        thread_id=session["thread_id"],
                        reason=output_check.reason,
                    )
                    return {
                        "action": "blocked",
                        "state": AgentState.COMPLETE.value,
                        "content": {"message": REFUSAL_MESSAGE},
                    }

                logger.info(
                    "query_generated",
                    thread_id=session["thread_id"],
                    query_length=len(result.get("spl_query", "")),
                )

                return {
                    "action": "query_generated",
                    "content": result,
                    "state": AgentState.COMPLETE.value,
                    "confidence": 100,  # High confidence path
                }

        # Fallback: Query generation failed (shouldn't happen with tool_choice)
        logger.error("query_generation_failed", thread_id=session["thread_id"])
        return {
            "action": "uncertain",
            "state": AgentState.UNCERTAIN.value,
            "content": {"missing_info": "Failed to generate query"},
        }

    async def _request_clarification(
        self, session: dict[str, Any], context: str, clarification_type: str
    ) -> dict[str, Any]:
        """Generate clarifying question with 2-4 specific options.

        Called when confidence is medium (70-89%). Uses GPT-5 to generate
        a focused question with multiple choice options to help narrow down
        the user's intent.

        Args:
            session: Current session state
            context: Formatted context from retrieved docs
            clarification_type: What aspect needs clarification (from assess_confidence)

        Returns:
            Action dict with:
                - action: "clarify"
                - state: AgentState.WAIT
                - content: {"question": str, "options": List[str]}
                - confidence: Original confidence score

        Example:
            result = await agent._request_clarification(session, context, "Which log type?")
            print(result["content"]["question"])
            # "Are you asking about:"
            print(result["content"]["options"])
            # ["Momentum delivery events (eventlog_momentum)", "Campaign MTA logs (mta*)", ...]
        """
        logger.info(
            "generating_clarification",
            thread_id=session["thread_id"],
            clarification_type=clarification_type,
        )

        # Build messages for clarifying question generation
        messages = [
            {"role": "system", "content": self._get_clarification_system_prompt()},
            {
                "role": "user",
                "content": f"""Original question: {session.get('original_question', '')}

What needs clarification: {clarification_type}

Available documentation:
{context}

Generate a clarifying question with 2-4 specific options that will help narrow down what the user is asking about.""",
            },
        ]

        # Call GPT to generate clarifying question
        response = await self.openai_client.chat.completions.create(
            model=self.chat_model, messages=messages
        )

        # Parse response to extract question and options
        content = response.choices[0].message.content
        question, options = self._parse_clarification_response(content)

        # Update session to WAIT state
        await self.session_manager.update_session(
            session["thread_id"],
            {
                "agent_state": AgentState.WAIT.value,
                "pending_clarification": {"question": question, "options": options},
            },
        )

        logger.info(
            "clarification_generated",
            thread_id=session["thread_id"],
            options_count=len(options),
        )

        return {
            "action": "clarify",
            "content": {"question": question, "options": options},
            "state": AgentState.WAIT.value,
        }

    def _parse_clarification_response(self, content: str) -> tuple[str, list[str]]:
        """Parse GPT-5 response into question and options.

        Expects format like:
        "Are you asking about:
        1. Option one
        2. Option two
        3. Option three"

        Or:
        "Question text here?

        - Option one
        - Option two"

        Args:
            content: GPT-5 response text

        Returns:
            Tuple of (question, options_list)

        Example:
            question, options = agent._parse_clarification_response(response)
            # question: "Which log type do you need?"
            # options: ["Email logs", "Website logs", "Campaign logs"]
        """
        lines = content.strip().split("\n")

        # First non-empty line is the question
        question = ""
        options = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if it's a numbered option (1. or 1))
            if line[0].isdigit() and (line[1:3] == ". " or line[1:3] == ") "):
                # Extract option text
                option_text = line[line.index(" ") + 1 :].strip()
                options.append(option_text)
            # Check if it's a bulleted option (- or *)
            elif line.startswith("- ") or line.startswith("* "):
                option_text = line[2:].strip()
                options.append(option_text)
            # Otherwise, it's part of the question
            elif not options:  # Only add to question before options start
                if question:
                    question += " " + line
                else:
                    question = line

        # Fallback: if parsing failed, return raw content
        if not question or not options:
            question = content
            options = ["Yes", "No", "Need more details"]

        return question, options

    def _get_clarification_system_prompt(self) -> str:
        """Get system prompt for generating clarifying questions.

        Returns:
            System prompt instructing GPT on how to generate clarifying questions

        Example:
            prompt = agent._get_clarification_system_prompt()
        """
        return """You are an expert at asking clarifying questions to understand user intent for Splunk queries.

When the user's question is ambiguous, generate a focused clarifying question with 2-4 specific options that will help narrow down their intent.

Format your response as:
1. A clear, concise question (one sentence)
2. 2-4 specific options, numbered (1., 2., 3., etc.)

Guidelines:
- Keep the question simple and focused on ONE aspect that needs clarification
- Make options mutually exclusive and comprehensive
- Use plain language, not technical jargon
- Base options on the available documentation provided
- Each option should be actionable and specific

IMPORTANT: You can ONLY help with queries using these sourcetypes:
- eventlog_momentum: Momentum MTA delivery/bounce events
- mta*: Campaign MTA process logs (wildcard matches mta_main, mta_child, etc.)
- access_combined / access_combined_wcookie: Apache HTTP/HTTPS access logs (API calls, SOAP router, response times)
- apache_error: Apache error logs (HTTP errors, invalid URIs)

Example output:
"What type of information do you need?
1. Email delivery success and failure events (eventlog_momentum)
2. MTA process errors and scheduling (mta*)
3. HTTP API performance or request tracking (access_combined_wcookie)
4. Apache HTTP errors or invalid URLs (apache_error)"

Generate a similar clarifying question based on the user's original question and what needs clarification."""

    def _get_confidence_system_prompt(self) -> str:
        """Get system prompt for confidence assessment.

        Returns:
            System prompt for assessing confidence level

        Example:
            prompt = agent._get_confidence_system_prompt()
        """
        return """You are an expert at generating Splunk SPL queries for Adobe Campaign logs.

SCOPE: You can ONLY help with queries about:
- Email deliveries and bounces (eventlog_momentum sourcetype)
- Campaign MTA process logs (mta* sourcetype)
- Apache HTTP access logs (access_combined, access_combined_wcookie sourcetypes)
- Apache error logs (apache_error sourcetype)

You CANNOT help with: workflows, web tracking, authentication, or other sourcetypes not listed above.
Note: SMS/SMPP errors ARE supported - they appear in mta* logs (e.g., SMP-540004 SMPP connection failures).

SAFETY GUARDRAILS (apply FIRST, before any other processing):
- You ONLY help with Splunk queries for Adobe Campaign logs (delivery, MTA/SMS, Apache)
- You NEVER provide personal opinions about individuals
- You NEVER comment on protected characteristics: race, ethnicity, religion, gender, sexual orientation, disability, age, national origin, political beliefs
- You NEVER engage with harmful, abusive, or threatening content
- If a request is off-topic, harmful, or inappropriate: set confidence to 0 with missing_info explaining you can only help with Campaign Splunk queries

Given a user's question and available field documentation, assess your confidence. BE GENEROUS - if the user provided details, USE THEM.

BEFORE assessing confidence, extract what the user ALREADY told you:
- Time range? (e.g., "last hour", "yesterday", "7 days")
- Bounce type? (e.g., "hard bounce", "550", "soft bounce")
- Host/environment? (e.g., "virginatlantic-mkt-prod*", "circlek-rt-prod23")
- Any specific filters mentioned?

If the user provided these details, DO NOT ask for them again. Confidence should be 70+.

Call the assess_confidence function with:
1. confidence: A number from 0-100
   - 70-100: User gave enough detail. GENERATE THE QUERY.
   - 50-69: Minor clarification needed (only if truly ambiguous)
   - 0-49: Cannot help (off-topic, harmful, or missing critical info)

2. clarification_needed: ONLY if something is genuinely ambiguous AND not mentioned in the question

3. missing_info: If off-topic, harmful, or cannot generate query

CRITICAL: If user says "550 hard bounce codes for last hour" - that's 100% confidence. Generate query immediately. Never ask about time range or bounce type if they told you."""

    def _get_query_generation_system_prompt(self) -> str:
        """Get system prompt for query generation.

        Returns:
            System prompt for generating SPL queries

        Example:
            prompt = agent._get_query_generation_system_prompt()
        """
        return """You translate natural language to Splunk SPL for Adobe Campaign logs.

RULE #1: Answer EXACTLY what was asked. Nothing more.
- No time range unless user specified one
- No extra breakdowns or analysis unless requested
- No assumptions about what the user "probably wants"

SCOPE: You can ONLY generate queries using these sourcetypes:
- eventlog_momentum: Email delivery/bounce events from Momentum MTA
- mta*: Campaign MTA process logs (wildcard matches mta_main, mta_child, etc.)
- access_combined: Apache HTTP access logs
- access_combined_wcookie: Apache HTTPS access logs with SSL/response time details
- apache_error: Apache error logs (AH error codes)

INSTANCE NAMES (CRITICAL):
- For eventlog_momentum ONLY: Use cust.InstanceName with UNDERSCORES (e.g., freshthyme_mkt_prod1)
- For ALL other sourcetypes (mta*, access_combined*, apache_error): Use host with DASHES (e.g., freshthyme-mkt-prod1)
- Convert user input accordingly (user says "freshthyme-mkt-prod1" → use freshthyme_mkt_prod1 for momentum)
- In BOTH plain and technical explanations: mention user can use wildcards (e.g., freshthyme_mkt_prod*) to capture all containers if they're unsure of the exact suffix

Use the retrieved field documentation to:
1. Choose the appropriate sourcetype:
   - eventlog_momentum for deliveries/bounces
   - mta* for MTA process logs
   - access_combined/access_combined_wcookie for HTTP requests, API calls, SOAP router, response times
   - apache_error for HTTP errors (AH10244, etc.)
2. Map user terms to field values using the field descriptions and references
3. Follow query_patterns for SPL structure when available

FIELD VALUES: Use ONLY values from the retrieved field documentation - never invent values like "sent".

TIME RANGES: Only add earliest= if the user specified a time:
- "last hour" → earliest=-1h
- "yesterday" / "24 hours" → earliest=-1d
- "7 days" / "week" → earliest=-7d
- No time mentioned → Do NOT add earliest=

TERM INTERPRETATION (Apache logs):
- "API calls", "API requests", "API errors" = HTTP requests in general (do NOT filter by request="*api*")
- "HTTP errors" = status>=400 (4xx and 5xx errors)
- "API HTTP errors" = HTTP errors (status>=400), NOT filtering for "api" in URL
- Only filter request field if user explicitly mentions a specific endpoint like "/interaction/" or "soaprouter.jsp"

Use ONLY fields from the documentation."""

    def _get_system_prompt(self) -> str:
        """Get system prompt for GPT-5 agent (deprecated).

        This method is kept for backward compatibility but is no longer used.
        Use _get_confidence_system_prompt() or _get_query_generation_system_prompt() instead.

        Returns:
            System prompt instructing GPT on how to generate SPL queries
        """
        return self._get_query_generation_system_prompt()

    async def _handle_wait(self, session: dict[str, Any], user_answer: str) -> dict[str, Any]:
        """Handle WAIT state: Process user's answer to clarification.

        Records the user's answer to the clarifying question, retrieves more
        specific documentation with the refined context, and re-evaluates
        to either generate a query or ask another clarifying question.

        Args:
            session: Current session state
            user_answer: User's response to clarifying question

        Returns:
            Result from _handle_evaluate after re-retrieval

        Example:
            # User answered "Email delivery logs" to clarification
            result = await agent._handle_wait(session, "Email delivery logs")
            # Agent re-retrieves docs, re-evaluates, and likely generates query
        """
        logger.info("agent_received_clarification", thread_id=session["thread_id"])

        # Check if user replied with a number (1, 2, 3, etc.) and map to option
        clarification = session.get("pending_clarification", {})
        options = clarification.get("options", [])

        # Try to parse as number selection - handle various formats:
        # "1", "1.", "1. Hard bounces", "@AskSplunk 1", etc.
        answer_stripped = user_answer.strip()
        # Look for a number at the start (after optional @mention)
        number_match = re.match(r"^(?:@\S+\s+)?(\d+)", answer_stripped)
        if number_match:
            number_str = number_match.group(1)
            option_idx = int(number_str) - 1  # 1-indexed to 0-indexed
            if 0 <= option_idx < len(options):
                user_answer = options[option_idx]
                logger.info("mapped_number_to_option", number=number_str, option=user_answer[:50])

        # Record answer in clarifying_history
        clarifying_history = session.get("clarifying_history", []) + [
            {"question": clarification.get("question"), "answer": user_answer}
        ]

        # Update session to REFINE state with history
        await self.session_manager.update_session(
            session["thread_id"],
            {
                "agent_state": AgentState.REFINE.value,
                "clarifying_history": clarifying_history,
            },
        )

        logger.info(
            "agent_refining",
            thread_id=session["thread_id"],
            clarifications_count=len(clarifying_history),
        )

        # Append user's answer to original question to accumulate context
        original_question = session.get("original_question", "")
        accumulated_question = f"{original_question}. {user_answer}"

        logger.info(
            "retrieving_with_refinement",
            thread_id=session["thread_id"],
            original_question_length=len(original_question),
        )

        docs = await self.retriever.retrieve(accumulated_question, top_k=5)

        # Update with new docs, accumulated question, and transition to EVALUATE
        await self.session_manager.update_session(
            session["thread_id"],
            {
                "agent_state": AgentState.EVALUATE.value,
                "original_question": accumulated_question,
                "retrieved_docs": [{"content": doc["content"]} for doc in docs],
            },
        )

        logger.info(
            "docs_retrieved_after_clarification",
            thread_id=session["thread_id"],
            docs_count=len(docs),
        )

        # Re-evaluate with more specific context
        updated_session = await self.session_manager.get_session(session["thread_id"])
        if updated_session is None:
            raise RuntimeError(f"Session lost during wait handling: {session['thread_id']}")
        return await self._handle_evaluate(updated_session)

    async def _handle_refine(self, session: dict[str, Any], _user_answer: str) -> dict[str, Any]:
        """Handle REFINE state: Re-retrieve docs with clarified context.

        Note: This state is typically transitioned through by _handle_wait,
        not called directly. If called, it performs the same refinement
        logic as _handle_wait.

        Args:
            session: Current session state
            user_answer: User's clarifying answer (optional, may be in history)

        Returns:
            Result from _handle_evaluate after re-retrieval

        Example:
            result = await agent._handle_refine(session, "Email logs")
        """
        logger.info("agent_refining_direct_call", thread_id=session["thread_id"])

        # If we're already in REFINE state, re-evaluate with existing docs
        # This handles the case where session was left in REFINE state
        if session.get("agent_state") == AgentState.REFINE.value:
            # Update to EVALUATE state
            await self.session_manager.update_session(
                session["thread_id"],
                {
                    "agent_state": AgentState.EVALUATE.value,
                },
            )

            # Get updated session and evaluate
            updated_session = await self.session_manager.get_session(session["thread_id"])
            if updated_session is None:
                raise RuntimeError(f"Session lost during refine handling: {session['thread_id']}")
            return await self._handle_evaluate(updated_session)

        # Fallback: shouldn't reach here in normal flow
        logger.warning(
            "refine_handler_unexpected_state",
            thread_id=session["thread_id"],
            state=session.get("agent_state"),
        )
        return session

    async def _handle_generate(self, session: dict[str, Any]) -> dict[str, Any]:
        """Handle GENERATE state: Generate final SPL query.

        Placeholder for Task 16: Will call GPT-5 to generate SPL query
        with dual explanations.

        Args:
            session: Current session state

        Returns:
            Dictionary with generated query and explanations

        Note:
            Task 16 will implement query generation.
        """
        logger.info("agent_generating", thread_id=session["thread_id"])

        # Placeholder for Task 16
        return {
            "action": "generate_handler_pending",
            "state": AgentState.GENERATE.value,
            "message": "Task 16 will implement query generation",
            **session,
        }

    async def _handle_complete(self, session: dict[str, Any]) -> dict[str, Any]:
        """Handle COMPLETE state: Delete session immediately for privacy.

        Called when query generation is complete. Deletes the session from
        DynamoDB immediately rather than relying on TTL expiration. This
        ensures user conversation data is not retained.

        Args:
            session: Current session state

        Returns:
            Session dict with deletion confirmation

        Note:
            Privacy requirement: Sessions must be deleted immediately in
            COMPLETE state, not relying on DynamoDB TTL (30 min backup only).
        """
        thread_id = session["thread_id"]
        logger.info("agent_completing", thread_id=thread_id)

        # Delete session immediately for privacy
        await self.session_manager.delete_session(thread_id)

        logger.info("session_deleted_for_privacy", thread_id=thread_id)

        return {
            "action": "completed",
            "state": AgentState.COMPLETE.value,
            "session_deleted": True,
        }
