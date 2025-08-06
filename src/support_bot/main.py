#!/usr/bin/env python
from support_bot.crew import support_crew

def run():
    """
    Run the crew.
    """
    # Ask user for input
    # print("="*60)
    # print("SUPPORT BOT - INCIDENT ANALYSIS SYSTEM")
    # print("="*60)
    # print("\nSearch for similar incidents by entering keywords such as:")
    # print("• HTTP error codes (499, 400, 429, etc.)")
    # print("• Issue types (timeout, latency, outage, etc.)")
    # print("• Specific problems (carding attack, rate limit, etc.)")
    # print("• General terms (performance, authentication, etc.)")
    # print("\nExamples: 'HTTP 499', 'timeout', 'latency issue', 'carding attack'")
    print("-" * 60)
    
    # Get user input
    user_query = input("\nEnter your search query: ").strip()
    
    # Validate input
    if not user_query:
        print("No query provided. Using default query: 'HTTP 499 timeout errors'")
        user_query = 'HTTP 499 timeout errors'
    
    print(f"\nSearching for incidents related to: '{user_query}'")
    print("="*60)
    
    # Define the inputs for your crew here.
    # The data_query will be passed to the Researcher Agent to search for relevant incidents
    inputs = {
        'data_query': user_query
    }
    
    # Kick off the crew's work
    result = support_crew.kickoff(inputs=inputs)
    return result

# This is the standard entry point for a Python script.
if __name__ == "__main__":
    result = run()
    print("\n" + "="*80)
    print("CREW EXECUTION COMPLETED")
    print("="*80)