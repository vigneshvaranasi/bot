#!/usr/bin/env python
"""
Test script to demonstrate different query types for the support bot
"""

from support_bot.crew import support_crew

def run_analysis(query: str):
    """
    Run the crew analysis with a specific query
    """
    print(f"\n{'='*80}")
    print(f"RUNNING ANALYSIS FOR: {query}")
    print(f"{'='*80}")
    
    inputs = {
        'user_prompt': query
    }
    
    try:
        result = support_crew.kickoff(inputs=inputs)
        print(f"\n{'='*80}")
        print("ANALYSIS COMPLETED SUCCESSFULLY")
        print(f"{'='*80}")
        return result
    except Exception as e:
        print(f"Error running analysis: {str(e)}")
        return None

def main():
    """
    Run different test scenarios
    """
    
    # Test scenarios based on the incidents.json data
    test_queries = [
        "HTTP 499",           # Will find timeout-related incidents
        "HTTP 400",           # Will find bad request incidents  
        "latency",            # Will find performance issues
        "timeout",            # Will find timeout-related problems
        "rate limit",         # Will find HTTP 429 incidents
        "carding attack",     # Will find security incidents
    ]
    
    print("Support Bot Analysis - Test Scenarios")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\nTest {i}/{len(test_queries)}: {query}")
        print("-" * 40)
        
        # Uncomment the line below to run the actual analysis
        # result = run_analysis(query)
        
        # For now, just show what would be analyzed
        print(f"Would analyze incidents related to: '{query}'")
    
    print(f"\n{'='*50}")
    print("To run actual analysis, uncomment the run_analysis() call in main()")
    print("Example usage:")
    print("  python test_scenarios.py")
    print("  Or run specific query:")
    print("  result = run_analysis('HTTP 499')")

if __name__ == "__main__":
    main()
