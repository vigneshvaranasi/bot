#!/usr/bin/env python
from support_bot.crew import support_crew
from support_bot.utils.formatting import sanitize_markdown_output
from support_bot.prompt_guardrail import PromptGuardrail
last_user_query = None
last_context = None

def handle_query(user_query: str, context: str):
    global last_user_query, last_context
    retry_phrases = ["retry", "search again", "try again", "better answer"]

    if any(p in user_query.lower() for p in retry_phrases):
        if last_user_query:
            # Re-run using the last query + context
            return support_crew.kickoff(inputs={
                "user_prompt": last_user_query,
                "context": last_context or ""
            })
        else:
            return "⚠️ No previous query found to retry."
    else:
        # Save new query + context
        last_user_query = user_query
        last_context = context
        return support_crew.kickoff(inputs={
            "user_prompt": user_query,
            "context": context
        })

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
    # result = support_crew.kickoff(inputs=inputs)
    result = handle_query(user_query, context)
    # Ensure clean markdown without fenced code blocks
    try:
        cleaned = sanitize_markdown_output(str(result))
        return cleaned
    except Exception:
        return result

# Entry Point
if __name__ == "__main__":
    result = run()