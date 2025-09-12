#!/usr/bin/env python
from support_bot.crew import support_crew
from support_bot.utils.formatting import sanitize_markdown_output
from support_bot.prompt_guardrail import PromptGuardrail

def run():
    """
    Run the crew.
    """
    print("-" * 60)
    user_query = input("\nHello, how can I help you today?\n>>").strip()
    context = input("\nPlease provide the context for your query:\n>>").strip()

    # Prompt Validation
    if not user_query:
        print("No query provided. Using default query: 'HTTP 499 timeout errors'")
        user_query = 'I am getting a status code 499 when connecting to PayU Service, how to solve it?'

    # Context Validation
    if not context:
        print("No context provided. Using default context.")
        context = ""


    # Prompt and Context passed to crew
    inputs = {
        'user_prompt': user_query,
        'context': context
    }
    
    # Prompt Guardrail Filter
    guard = PromptGuardrail()
    is_valid, reject_msg = guard.validate_or_reject(user_query)
    if not is_valid:
        return reject_msg

    # Kick off Crew
    result = support_crew.kickoff(inputs=inputs)
    # Ensure clean markdown without fenced code blocks
    try:
        cleaned = sanitize_markdown_output(str(result))
        return cleaned
    except Exception:
        return result

# Entry Point
if __name__ == "__main__":
    result = run()