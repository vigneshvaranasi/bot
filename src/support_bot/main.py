#!/usr/bin/env python
from support_bot.crew import support_crew
from support_bot.utils.formatting import sanitize_markdown_output
from support_bot.prompt_guardrail import PromptGuardrail
from support_bot.utils.cache import get_from_cache, add_to_cache  # ⬅️ import cache utils

def run():
    """
    Run the crew.
    """
    print("-" * 60)
    user_query = input("\nHello, how can I help you today?\n>> ").strip()
    context = input("\nPlease provide the context for your query:\n>> ").strip()

    # Prompt Validation
    if not user_query:
        print("No query provided. Using default query.")
        user_query = 'I am getting a status code 499 when connecting to PayU Service, how to solve it?'

    # Context Validation
    if not context:
        print("No context provided. Using default context.")
        context = ""

    # Check cache first
    cached_response = get_from_cache(user_query, context)
    if cached_response:
        print("\n[From Cache]")
        return cached_response

    # Prompt Guardrail Filter
    guard = PromptGuardrail()
    is_valid, reject_msg = guard.validate_or_reject(user_query)
    if not is_valid:
        return reject_msg

    # Kick off crew
    result = support_crew.kickoff(inputs={'user_prompt': user_query, 'context': context})

    # Ensure clean markdown without fenced code blocks
    try:
        cleaned = sanitize_markdown_output(str(result))
    except Exception:
        cleaned = str(result)

    # Save response to cache
    add_to_cache(user_query, context, cleaned)

    return cleaned
