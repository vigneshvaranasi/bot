#!/usr/bin/env python3
"""
Comprehensive Cache Testing Suite
Tests basic cache functionality and various similarity threshold scenarios
"""
import sys
import os
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from api.utils.cache import (
    add_to_cache,
    get_from_cache,
    _normalize_text,
    _extract_topics,
    _calculate_similarity,
    _create_cache_key,
    _get_redis_client,
    USE_REDIS,
    SIMILARITY_THRESHOLD
)

class CacheTestSuite:
    """Comprehensive cache testing suite"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = time.time()
        print("🧪 COMPREHENSIVE CACHE TEST SUITE")
        print("=" * 60)
        print(f"Redis enabled: {USE_REDIS}")
        print(f"Similarity threshold: {SIMILARITY_THRESHOLD}")
        print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    def log_test(self, test_name, passed, details=""):
        """Log test results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append((test_name, passed, details))
        print(f"{status}: {test_name}")
        if details:
            print(f"    Details: {details}")

    def test_basic_functionality(self):
        """Test basic cache add, retrieve, and normalization"""
        print("\n🔧 BASIC FUNCTIONALITY TESTS")
        print("-" * 40)
        
        # Test 1: Text normalization
        test_cases = [
            ("Hello, World!", "hello world"),
            ("  Multiple   Spaces  ", "multiple spaces"),
            ("UPPERCASE text!", "uppercase text"),
            ("Punctuation: @#$%", "punctuation "),
            ("", ""),
            ("   ", "")
        ]
        
        for input_text, expected in test_cases:
            result = _normalize_text(input_text)
            passed = result == expected
            self.log_test(f"Normalize '{input_text}' → '{expected}'", passed, f"Got: '{result}'")

        # Test 2: Topic extraction
        topic_tests = [
            ("How to reset my password?", {"how", "reset", "password"}),
            ("I need help with login", {"need", "help", "login"}),
            ("Account number is 12345", {"account", "number", "12345"}),
            ("", set()),
            ("a an the", set())
        ]
        
        for query, expected_topics in topic_tests:
            result = _extract_topics(query)
            passed = result == expected_topics
            self.log_test(f"Extract topics from '{query}'", passed, f"Expected: {expected_topics}, Got: {result}")

        # Test 3: Cache key creation
        key_tests = [
            ("How do I reset my password?", "how do i reset my password"),
            ("I'm having trouble with login!", "im having trouble with login"),
            ("What are the system requirements?", "what are the system requirements")
        ]
        
        for query, expected_key in key_tests:
            result = _create_cache_key(query)
            passed = result == expected_key
            self.log_test(f"Create cache key for '{query}'", passed, f"Expected: '{expected_key}', Got: '{result}'")

    def test_similarity_calculations(self):
        """Test similarity calculation with various thresholds"""
        print("\n📊 SIMILARITY CALCULATION TESTS")
        print("-" * 40)
        
        similarity_tests = [
            # Exact matches
            ("hello world", "hello world", 1.0),
            ("reset password", "reset password", 1.0),
            
            # High similarity
            ("reset my password", "reset password", 0.8),  # Should be high
            ("login issues", "login problems", 0.7),       # Should be moderate-high
            
            # Medium similarity  
            ("how to login", "login help", 0.5),           # Should be medium
            ("account problems", "account issues", 0.8),   # Should be high
            
            # Low similarity
            ("reset password", "create account", 0.1),     # Should be low
            ("login help", "system requirements", 0.0),    # Should be very low
            
            # Edge cases
            ("", "", 1.0),                                 # Empty strings
            ("a", "b", 0.0),                              # Single different chars
            ("the", "a", 0.0),                            # Stopwords only
        ]
        
        for query1, query2, min_expected in similarity_tests:
            result = _calculate_similarity(query1, query2)
            # For testing, we expect results to be at least close to expected
            passed = abs(result - min_expected) < 0.3  # Allow some variance
            self.log_test(f"Similarity '{query1}' vs '{query2}'", passed, f"Expected: ~{min_expected}, Got: {result:.3f}")

    def test_threshold_scenarios(self):
        """Test cache matching with different similarity scenarios"""
        print("\n🎯 THRESHOLD MATCHING TESTS")
        print("-" * 40)
        
        # Clear any existing cache for clean testing
        timestamp = str(int(time.time()))
        
        base_queries = [
            f"How do I reset my password {timestamp}?",
            f"I need help with login issues {timestamp}",
            f"What are the system requirements {timestamp}?",
            f"How to create new account {timestamp}?",
            f"Billing questions and support {timestamp}"
        ]
        
        responses = [
            "Password reset: Go to login page, click forgot password, enter email",
            "Login help: Check credentials, clear cache, try incognito mode", 
            "Requirements: Windows 10+, 4GB RAM, modern browser",
            "Account creation: Click signup, fill form, verify email",
            "Billing: Contact support at billing@company.com or call 1-800-123-4567"
        ]
        
        # Add base queries to cache
        print("  Adding base queries to cache...")
        for query, response in zip(base_queries, responses):
            add_to_cache(query, response)
            
        # Test similar queries that should match (above threshold)
        should_match = [
            (f"how do i reset password {timestamp}", "Should match password reset query"),
            (f"need help logging in {timestamp}", "Should match login help query"),
            (f"what are system requirements {timestamp}", "Should match requirements query"),
            (f"how create account {timestamp}", "Should match account creation query")
        ]
        
        print("  Testing queries that should match (above threshold)...")
        for test_query, description in should_match:
            cached_result = get_from_cache(test_query)
            passed = cached_result is not None
            self.log_test(f"Match test: {description}", passed, f"Query: '{test_query[:50]}...'")
        
        # Test different queries that should NOT match (below threshold)
        should_not_match = [
            (f"weather forecast today {timestamp}", "Should NOT match any cached query"),
            (f"how to cook pasta {timestamp}", "Should NOT match any cached query"),
            (f"stock market prices {timestamp}", "Should NOT match any cached query"),
            (f"random unrelated content {timestamp}", "Should NOT match any cached query")
        ]
        
        print("  Testing queries that should NOT match (below threshold)...")
        for test_query, description in should_not_match:
            cached_result = get_from_cache(test_query)
            passed = cached_result is None
            self.log_test(f"No-match test: {description}", passed, f"Query: '{test_query[:50]}...'")

    def test_edge_cases(self):
        """Test edge cases and special scenarios"""
        print("\n⚠️  EDGE CASE TESTS")
        print("-" * 40)
        
        timestamp = str(int(time.time()))
        
        edge_cases = [
            # Empty and whitespace
            ("", "Empty query test"),
            ("   ", "Whitespace-only query test"),
            ("\n\t\r", "Special whitespace characters test"),
            
            # Very long queries
            ("This is a very long query " * 20 + timestamp, "Very long query test"),
            
            # Special characters
            (f"Query with émojis 😀🎉 {timestamp}", "Unicode emoji test"),
            (f"Spëcial châractërs tëst {timestamp}", "Accented characters test"),
            (f"Mixed languages 测试 тест {timestamp}", "Mixed languages test"),
            
            # Numbers and symbols
            (f"Account #12345 $$$$ {timestamp}", "Numbers and symbols test"),
            (f"Email: user@domain.com {timestamp}", "Email format test"),
            (f"URL: https://example.com/path?param=value {timestamp}", "URL format test"),
            
            # Cache bypass keywords
            (f"Normal query {timestamp} no cache", "Cache bypass test"),
            (f"Another query {timestamp} don't cache", "Cache bypass variation test"),
        ]
        
        for query, description in edge_cases:
            try:
                # Test normalization doesn't break
                normalized = _normalize_text(query)
                
                # Test cache key creation
                cache_key = _create_cache_key(query)
                
                # Test adding to cache (if not bypass)
                if "cache" not in query.lower() or "no" not in query.lower():
                    add_to_cache(query, f"Test response for: {description}")
                    
                    # Test retrieval
                    cached = get_from_cache(query)
                    passed = cached is not None
                else:
                    # For bypass tests, should return None
                    cached = get_from_cache(query)
                    passed = cached is None
                    
                self.log_test(description, passed, f"Query length: {len(query)}")
                
            except Exception as e:
                self.log_test(description, False, f"Exception: {str(e)}")

    def test_performance(self):
        """Test cache performance with multiple operations"""
        print("\n⚡ PERFORMANCE TESTS")
        print("-" * 40)
        
        timestamp = str(int(time.time()))
        
        # Generate test data
        test_queries = []
        test_responses = []
        
        for i in range(50):
            query = f"Performance test query {i} {timestamp} - topic {i % 5}"
            response = f"Response for performance test {i} with some content to simulate real responses"
            test_queries.append(query)
            test_responses.append(response)
        
        # Test bulk add performance
        start_time = time.time()
        for query, response in zip(test_queries, test_responses):
            add_to_cache(query, response)
        add_time = time.time() - start_time
        
        add_passed = add_time < 5.0  # Should complete within 5 seconds
        self.log_test(f"Bulk add (50 items)", add_passed, f"Time: {add_time:.3f}s, Avg: {(add_time/50)*1000:.1f}ms/item")
        
        # Test bulk retrieve performance
        start_time = time.time()
        hits = 0
        for query in test_queries:
            cached = get_from_cache(query)
            if cached:
                hits += 1
        retrieve_time = time.time() - start_time
        
        retrieve_passed = retrieve_time < 3.0 and hits >= 45  # Should be fast and find most items
        self.log_test(f"Bulk retrieve (50 items)", retrieve_passed, f"Time: {retrieve_time:.3f}s, Hits: {hits}/50")
        
        # Test fuzzy matching performance
        fuzzy_queries = [f"performance test query {i} {timestamp}" for i in range(10)]  # Slightly different
        
        start_time = time.time()
        fuzzy_hits = 0
        for query in fuzzy_queries:
            cached = get_from_cache(query)
            if cached:
                fuzzy_hits += 1
        fuzzy_time = time.time() - start_time
        
        fuzzy_passed = fuzzy_time < 2.0  # Fuzzy matching should still be reasonably fast
        self.log_test(f"Fuzzy matching (10 items)", fuzzy_passed, f"Time: {fuzzy_time:.3f}s, Hits: {fuzzy_hits}/10")

    def test_cache_bypass(self):
        """Test cache bypass functionality"""
        print("\n🚫 CACHE BYPASS TESTS")
        print("-" * 40)
        
        timestamp = str(int(time.time()))
        
        # Add a query to cache first
        base_query = f"Cache bypass test query {timestamp}"
        base_response = f"This is a cached response for bypass testing {timestamp}"
        add_to_cache(base_query, base_response)
        
        # Verify it's cached
        cached = get_from_cache(base_query)
        self.log_test("Base query cached", cached is not None, "Setting up bypass test")
        
        # Test various bypass keywords
        bypass_variations = [
            f"{base_query} no cache",
            f"{base_query} don't cache", 
            f"{base_query} bypass cache",
            f"{base_query} skip cache",
            f"{base_query} fresh response"
        ]
        
        for bypass_query in bypass_variations:
            result = get_from_cache(bypass_query)
            passed = result is None
            bypass_keyword = bypass_query.split()[-2:]  # Get last 2 words
            self.log_test(f"Bypass with '{' '.join(bypass_keyword)}'", passed, "Should return None")

    def run_all_tests(self):
        """Run all test suites"""
        print("\n🚀 Starting comprehensive cache test suite...\n")
        
        # Run all test categories
        self.test_basic_functionality()
        self.test_similarity_calculations()
        self.test_threshold_scenarios()
        self.test_edge_cases()
        self.test_performance()
        self.test_cache_bypass()
        
        # Generate summary report
        self.generate_summary()

    def generate_summary(self):
        """Generate test summary report"""
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY REPORT")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total tests run: {total_tests}")
        print(f"Tests passed: {passed_tests}")
        print(f"Tests failed: {failed_tests}")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Total time: {time.time() - self.start_time:.2f} seconds")
        
        # Show failed tests if any
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for test_name, passed, details in self.test_results:
                if not passed:
                    print(f"  • {test_name}")
                    if details:
                        print(f"    {details}")
        
        # Overall result
        print(f"\n" + "=" * 60)
        if success_rate >= 95:
            print("🎉 EXCELLENT! Cache system is working perfectly!")
        elif success_rate >= 85:
            print("👍 GOOD! Cache system is working well with minor issues.")
        elif success_rate >= 70:
            print("⚠️  MODERATE! Cache system has some issues that need attention.")
        else:
            print("❌ POOR! Cache system has significant issues that need fixing.")
        
        print("=" * 60)


def main():
    """Main test execution"""
    print("Initializing Cache Test Suite...")
    
    # Check if cache dependencies are available
    try:
        redis_client = _get_redis_client()
        if USE_REDIS and redis_client:
            print("✅ Redis connection verified")
        elif USE_REDIS:
            print("⚠️  Redis enabled but connection failed - will test JSON fallback")
        else:
            print("ℹ️  Redis disabled - testing JSON cache only")
            
    except Exception as e:
        print(f"⚠️  Cache setup issue: {e}")
    
    # Run the test suite
    test_suite = CacheTestSuite()
    test_suite.run_all_tests()


if __name__ == "__main__":
    main()