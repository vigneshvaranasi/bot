"""Test LLM-based context detection accuracy on edge cases."""

from cache import _is_context_dependent

test_cases = [
    ("Can you give me the related incident from the database", True, "Your screenshot example"),
    ("What about that other solution", True, "Vague reference"),
    ("Tell me if that is the correct approach", True, "Ambiguous context"),
    ("Explain what that HTTP 500 error means", False, "Specific with clarification"),
    ("How do deadlocks occur in databases", False, "Completely self-contained"),
    ("Show me the corresponding issue", True, "Context-dependent reference"),
    ("What causes HTTP 500 errors in production", False, "Self-contained technical query"),
    ("Give me more information", True, "Incomplete request"),
    ("Describe the OAuth 2.0 authentication flow", False, "Complete topic"),
    ("Apply that fix to production", True, "References previous fix"),
]

print("\n" + "="*80)
print("  LLM-BASED CONTEXT DETECTION ACCURACY TEST")
print("="*80)

passed = 0
failed = 0

for query, expected, description in test_cases:
    result = _is_context_dependent(query)
    match = result == expected
    
    if match:
        passed += 1
        symbol = "✅"
    else:
        failed += 1
        symbol = "❌"
    
    print(f"\n{symbol} {description}")
    print(f"   Query: '{query}'")
    print(f"   Expected: {expected}, Got: {result}")

print("\n" + "="*80)
print(f"  Results: {passed}/{len(test_cases)} passed ({100*passed//len(test_cases)}% accuracy)")
print("="*80)
