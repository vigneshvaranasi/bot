#!/usr/bin/env python
from support_bot.crew import support_crew

def run():
    """
    Run the crew.
    """
    print("-" * 60)
    user_query = input("\nHello, how can I help you today?\n>>").strip()
    
    # Prompt Validation
    if not user_query:
        print("No query provided. Using default query: 'HTTP 499 timeout errors'")
        user_query = 'I am getting a status code 499 when connecting to PayU Service, how to solve it?'
    
    # Prompt passed to crew
    inputs = {
        'user_prompt': user_query,
        'context':""
    }
    
    # Kick off Crew
    result = support_crew.kickoff(inputs=inputs)
    return result

# Entry Point
if __name__ == "__main__":
    result = run()