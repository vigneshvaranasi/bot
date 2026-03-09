"""Golden Response Generator Service.

This module provides a scalable service for generating improved AI responses
based on user feedback. It uses the configured LLM with full RAG tool access,
letting the LLM decide when to use tools for additional context.

Features:
- Specialized prompt for response improvement
- Full RAG tool access (LLM decides when to use)
- Configurable limits for scalability (timeout, max iterations, concurrency)
- Async with timeout protection
- Bypasses golden example search to ensure fresh generation
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

GOLDEN_RESPONSE_SYSTEM_PROMPT = """
You are an AI Response Improvement Specialist.
Your task is to generate a better, more accurate response based on user feedback about a previous AI response.

## Context
You will receive:
1. The user's original question
2. The AI's original response (which had issues)
3. The user's feedback explaining what was wrong or could be improved

## Your Tools
You have access to incident lookup tools:
- search_similar_incidents: Search incidents by description, error message, or keywords
- lookup_incident_by_id: Get specific incident details by ID (e.g., INC-2025-08-24-001)
- get_incidents_by_application: Find incidents affecting a specific application
- get_recent_incidents: Get recent incidents from the last N days

## Instructions
1. Analyze the feedback to understand what went wrong with the original response
2. If the issue is missing or incorrect data, USE THE TOOLS to get accurate information
3. If the issue is about formatting, clarity, or tone, improve without using tools
4. Generate a response that DIRECTLY addresses the user's original question
5. Be accurate, helpful, and well-formatted

## Important Guidelines
- Always cite incident IDs when referencing specific incidents (e.g., "Based on incident INC-2025-08-24-001...")
- If no relevant incidents exist in the database, say so clearly
- Focus on being helpful and accurate
- Use markdown formatting for better readability (bullet points, headers, code blocks)
- Keep the response concise but complete
- DO NOT use emojis in the response - keep it professional and clean
- Use plain text markers like "Step 1:", "Note:", "Important:" instead of emoji symbols

Generate the improved response now."""


@dataclass
class GenerationResult:
    """Result of golden response generation."""
    generated_response: str
    tool_calls_made: int
    generation_time_ms: int
    success: bool
    error: Optional[str] = None


class GoldenResponseGenerator:
    """
    Scalable service for generating improved AI responses.
    
    This service uses the configured LLM with tool access to generate
    better responses based on user feedback. The LLM decides autonomously
    whether to use RAG tools for additional context.

    Important: This generator deliberately bypasses golden example search
    to ensure fresh generation. Existing golden responses are only passed
    in so the LLM can avoid reproducing them.

    Scalability features:
    - Semaphore to limit concurrent generations
    - Timeout protection for hung requests
    - Max iteration limit to prevent infinite tool loops
    """
    
    MAX_TOOL_ITERATIONS = 5
    GENERATION_TIMEOUT = 60
    MAX_CONCURRENT = 5
    
    _semaphore: Optional[asyncio.Semaphore] = None
    
    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """Get or create the semaphore (lazy initialization for async context)."""
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(cls.MAX_CONCURRENT)
        return cls._semaphore
    
    def __init__(self):
        """Initialize the generator."""
        self._tools = None

    def _get_llm(self, llm_config: Optional[dict] = None) -> BaseChatModel:
        """Get the LLM instance based on provider config.

        Args:
            llm_config: Provider configuration from get_provider_config_for_chat().
                        If provided and contains a valid provider, uses that provider.
                        Otherwise falls back to default Ollama.
        """
        from src.copilot.graph import create_llm_for_request
        if llm_config and llm_config.get("provider_type") and llm_config.get("model_id"):
            return create_llm_for_request(
                provider_type=llm_config["provider_type"],
                model_id=llm_config["model_id"],
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                provider_config=llm_config.get("provider_config"),
                temperature=llm_config.get("temperature"),
            )
        from src.copilot.llm_factory import get_default_llm
        return get_default_llm()
    
    def _get_tools(self) -> list:
        """Get the available RAG tools."""
        if self._tools is None:
            from src.copilot.tools import available_tools
            self._tools = available_tools
        return self._tools
    
    def _get_llm_with_tools(self, llm_config: Optional[dict] = None) -> BaseChatModel:
        """Get LLM with tools bound."""
        llm = self._get_llm(llm_config)
        tools = self._get_tools()
        return llm.bind_tools(tools)
    
    async def generate(
        self,
        original_query: str,
        original_response: str,
        feedback_reason: Optional[str],
        feedback_type: str,
        llm_config: Optional[dict] = None,
        existing_golden_responses: Optional[List[str]] = None,
    ) -> GenerationResult:
        """
        Generate an improved response based on feedback.

        This method bypasses golden example search -- existing golden responses
        are passed in only so the LLM can avoid reproducing them.

        This method is protected by:
        - Semaphore for concurrency control
        - Timeout for hung requests
        
        Args:
            original_query: The user's original question
            original_response: The AI's original response
            feedback_reason: Why the user gave feedback (optional)
            feedback_type: 'positive' or 'negative'
            llm_config: Provider configuration dict from get_provider_config_for_chat().
            existing_golden_responses: Previously approved golden responses for this
                query that should NOT be reproduced -- ensures fresh generation.

        Returns:
            GenerationResult with the generated response and metadata
        """
        semaphore = self._get_semaphore()
        start_time = time.time()
        
        try:
            async with semaphore:
                logger.info(f"Starting golden response generation (feedback_type={feedback_type})")
                
                result = await asyncio.wait_for(
                    self._generate_internal(
                        original_query=original_query,
                        original_response=original_response,
                        feedback_reason=feedback_reason,
                        feedback_type=feedback_type,
                        llm_config=llm_config,
                    ),
                    timeout=self.GENERATION_TIMEOUT
                )
                
                elapsed_ms = int((time.time() - start_time) * 1000)
                result.generation_time_ms = elapsed_ms
                
                logger.info(
                    f"Golden response generated successfully "
                    f"(tool_calls={result.tool_calls_made}, time={elapsed_ms}ms)"
                )
                
                return result
                
        except asyncio.TimeoutError:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Golden response generation timed out after {elapsed_ms}ms")
            return GenerationResult(
                generated_response="",
                tool_calls_made=0,
                generation_time_ms=elapsed_ms,
                success=False,
                error=f"Generation timed out after {self.GENERATION_TIMEOUT} seconds"
            )
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Error generating golden response: {e}")
            return GenerationResult(
                generated_response="",
                tool_calls_made=0,
                generation_time_ms=elapsed_ms,
                success=False,
                error=str(e)
            )
    
    async def _generate_internal(
        self,
        original_query: str,
        original_response: str,
        feedback_reason: Optional[str],
        feedback_type: str,
        llm_config: Optional[dict] = None,
        existing_golden_responses: Optional[List[str]] = None,
    ) -> GenerationResult:
        """
        Internal generation logic with tool loop.

        Bypasses golden example search -- does NOT pull from golden examples.
        If existing golden responses are provided, they are included only so
        the LLM avoids reproducing them.
        """
        feedback_text = feedback_reason or "User was not satisfied with the response"
        if feedback_type == "positive":
            feedback_text = feedback_reason or "User liked the response but it could be improved"
        
        user_message = f"""
        ## Original User Question
        {original_query}

        ## Original AI Response
        {original_response}

        ## User Feedback ({feedback_type})
        {feedback_text}
"""

        # If golden responses already exist for this query, instruct the LLM to
        # generate something genuinely new -- not a rehash of existing answers.
        if existing_golden_responses:
            user_message += "\n## Existing Approved Responses (DO NOT REPRODUCE)\n"
            user_message += (
                "The following responses have already been approved for this query. "
                "You MUST generate a genuinely DIFFERENT and IMPROVED response. "
                "Do NOT copy, paraphrase, or closely mirror these:\n"
            )
            for i, resp in enumerate(existing_golden_responses, 1):
                user_message += f"\n### Existing Response {i}:\n{resp}\n"

        user_message += """
---
Please generate an improved response that addresses the user's original question while fixing the issues identified in the feedback.
Use the available tools if you need to look up incident information or verify details."""

        messages: List[BaseMessage] = [
            SystemMessage(content=GOLDEN_RESPONSE_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        llm_with_tools = self._get_llm_with_tools(llm_config)
        
        response, tool_calls_made = await self._execute_with_tools(
            messages=messages,
            llm_with_tools=llm_with_tools,
        )
        
        return GenerationResult(
            generated_response=response,
            tool_calls_made=tool_calls_made,
            generation_time_ms=0,
            success=True,
        )
    
    async def _execute_with_tools(
        self,
        messages: List[BaseMessage],
        llm_with_tools: BaseChatModel,
    ) -> tuple[str, int]:
        """
        Execute LLM with agentic tool loop.
        
        The LLM decides if tools are needed. If it makes tool calls,
        we execute them IN PARALLEL and continue until:
        - LLM returns a response without tool calls, OR
        - Max iterations reached
        
        Args:
            messages: The conversation messages
            llm_with_tools: LLM with tools bound
            
        Returns:
            Tuple of (response_content, tool_calls_count)
        """
        iterations = 0
        total_tool_calls = 0
        
        while iterations < self.MAX_TOOL_ITERATIONS:
            response: AIMessage = await llm_with_tools.ainvoke(messages)
            
            if not response.tool_calls:
                return response.content, total_tool_calls
            
            num_calls = len(response.tool_calls)
            logger.info(f"Iteration {iterations + 1}: Executing {num_calls} tool calls in parallel")
            
            messages.append(response)
            
            tool_results = await asyncio.gather(
                *[self._execute_single_tool(tool_call) for tool_call in response.tool_calls]
            )
            
            for tool_result in tool_results:
                messages.append(tool_result)
            
            total_tool_calls += num_calls
            iterations += 1
        
        logger.warning(
            f"Max tool iterations ({self.MAX_TOOL_ITERATIONS}) reached, "
            f"requesting final response"
        )
        
        messages.append(HumanMessage(
            content="Please provide your final improved response now based on the information gathered."
        ))
        
        final_response: AIMessage = await llm_with_tools.ainvoke(messages)
        return final_response.content, total_tool_calls
    
    async def _execute_single_tool(self, tool_call: dict) -> ToolMessage:
        """
        Execute a single tool call and return the result.
        
        Args:
            tool_call: The tool call from the LLM
            
        Returns:
            ToolMessage with the result
        """
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        logger.debug(f"Executing tool: {tool_name} with args: {tool_args}")
        
        try:
            tools = self._get_tools()
            tool_func = None
            for t in tools:
                if t.name == tool_name:
                    tool_func = t
                    break
            
            if tool_func is None:
                return ToolMessage(
                    content=f"Error: Unknown tool '{tool_name}'",
                    tool_call_id=tool_id,
                )
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: tool_func.invoke(tool_args)
            )
            
            return ToolMessage(
                content=str(result),
                tool_call_id=tool_id,
            )
            
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return ToolMessage(
                content=f"Error executing tool: {str(e)}",
                tool_call_id=tool_id,
            )


_generator_instance: Optional[GoldenResponseGenerator] = None


def get_golden_response_generator() -> GoldenResponseGenerator:
    """Get the singleton generator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = GoldenResponseGenerator()
    return _generator_instance
