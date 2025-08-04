"""
Test Gemini API connectivity and functionality.

This script tests the Gemini API connection and embedding generation
to ensure everything is configured correctly.
"""

import os
import sys
from typing import Optional, List, Dict, Any

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv not installed. Environment variables should be set manually.")


def test_api_connection() -> bool:
    """
    Test basic Gemini API connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        import google.genai as genai
        
        # Get API key
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("❌ No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in environment.")
            return False
        
        # Configure Gemini
        client = genai.Client(api_key=api_key)
        
        # Test with a simple embedding
        print("🔗 Testing API connection...")
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=["Hello, this is a test."]
        )
        
        if result and hasattr(result, 'embeddings') and result.embeddings and len(result.embeddings) > 0:
            embedding_values = result.embeddings[0].values
            print(f"✅ API connection successful! Embedding dimensions: {len(embedding_values)}")
            return True
        else:
            print("❌ API connection failed - no embedding returned")
            return False
            
    except ImportError as e:
        print(f"❌ Missing google-genai package: {e}")
        return False
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False


def test_embedding_generation(texts: List[str]) -> Dict[str, Any]:
    """
    Test embedding generation for multiple texts.
    
    Args:
        texts: List of texts to generate embeddings for
    
    Returns:
        Dictionary with test results
    """
    try:
        import google.genai as genai
        import time
        
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        client = genai.Client(api_key=api_key)
        
        print(f"\n🧠 Testing embedding generation for {len(texts)} texts...")
        
        results = {
            "successful": 0,
            "failed": 0,
            "embeddings": [],
            "errors": [],
            "total_time": 0,
            "avg_time": 0
        }
        
        start_time = time.time()
        
        for i, text in enumerate(texts, 1):
            try:
                print(f"   Processing text {i}/{len(texts)}...")
                
                # Generate embedding
                result = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=[text]
                )
                
                if result and hasattr(result, 'embeddings') and result.embeddings and len(result.embeddings) > 0:
                    embedding_values = result.embeddings[0].values
                    results["successful"] += 1
                    results["embeddings"].append({
                        "text": text[:50] + "..." if len(text) > 50 else text,
                        "dimensions": len(embedding_values),
                        "sample_values": embedding_values[:5]
                    })
                    print(f"      ✅ Success - {len(embedding_values)} dimensions")
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Text {i}: No embedding returned")
                    print(f"      ❌ Failed - No embedding returned")
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Text {i}: {str(e)}")
                print(f"      ❌ Failed - {e}")
        
        results["total_time"] = time.time() - start_time
        results["avg_time"] = results["total_time"] / len(texts)
        
        return results
        
    except Exception as e:
        return {
            "successful": 0,
            "failed": len(texts),
            "embeddings": [],
            "errors": [f"Setup error: {e}"],
            "total_time": 0,
            "avg_time": 0
        }


def test_different_task_types(test_text: str) -> None:
    """
    Test different task types for embeddings.
    
    Args:
        test_text: Text to test with different task types
    """
    try:
        import google.generativeai as genai
        
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        genai.configure(api_key=api_key)
        
        print(f"\n🎯 Testing different task types with text: '{test_text[:50]}...'")
        
        task_types = [
            ("RETRIEVAL_QUERY", "For search queries"),
            ("RETRIEVAL_DOCUMENT", "For documents to be searched"),
            ("SEMANTIC_SIMILARITY", "For similarity comparisons"),
            ("CLASSIFICATION", "For classification tasks"),
            ("CLUSTERING", "For clustering tasks")
        ]
        
        for task_type, description in task_types:
            try:
                print(f"   Testing {task_type} ({description})...")
                
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=test_text,
                    task_type=task_type
                )
                
                if result and hasattr(result, 'embedding') and result.embedding:
                    dimensions = len(result.embedding)
                    sample_values = result.embedding[:3]
                    print(f"      ✅ Success - {dimensions} dimensions, sample: {sample_values}")
                else:
                    print(f"      ❌ Failed - No embedding returned")
                    
            except Exception as e:
                print(f"      ❌ Failed - {e}")
                
    except Exception as e:
        print(f"❌ Task type testing failed: {e}")


def test_rate_limiting() -> None:
    """Test API rate limiting behavior."""
    try:
        import google.generativeai as genai
        import time
        
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        genai.configure(api_key=api_key)
        
        print(f"\n⏱️ Testing rate limiting (rapid requests)...")
        
        test_text = "This is a rate limiting test message."
        successful_requests = 0
        failed_requests = 0
        
        start_time = time.time()
        
        # Make 10 rapid requests
        for i in range(1, 11):
            try:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=f"{test_text} Request #{i}",
                    task_type="RETRIEVAL_DOCUMENT"
                )
                
                if result and hasattr(result, 'embedding') and result.embedding:
                    successful_requests += 1
                    print(".", end="", flush=True)
                else:
                    failed_requests += 1
                    print("X", end="", flush=True)
                    
            except Exception as e:
                failed_requests += 1
                print("E", end="", flush=True)
        
        total_time = time.time() - start_time
        
        print(f"\n   Results: {successful_requests}/10 successful, {failed_requests}/10 failed")
        print(f"   Total time: {total_time:.2f}s, Avg time per request: {total_time/10:.2f}s")
        
        if failed_requests > 0:
            print("   ⚠️ Some requests failed - this might indicate rate limiting")
        else:
            print("   ✅ All requests successful - no apparent rate limiting")
            
    except Exception as e:
        print(f"❌ Rate limiting test failed: {e}")


def display_configuration_info() -> None:
    """Display current configuration information."""
    print("\n📋 Current Configuration:")
    
    # Check API key
    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    if api_key:
        masked_key = api_key[:8] + "*" * (len(api_key) - 12) + api_key[-4:] if len(api_key) > 12 else "*" * len(api_key)
        print(f"   • API Key: {masked_key}")
    else:
        print("   • API Key: ❌ Not found")
    
    # Check package installation
    try:
        import google.genai as genai
        print(f"   • google-genai: ✅ Installed")
    except ImportError:
        print(f"   • google-genai: ❌ Not installed")
    
    # Check environment file
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        print(f"   • .env file: ✅ Found at {env_file}")
    else:
        print(f"   • .env file: ❌ Not found")


def main():
    """Entry point for the test-gemini-api script."""
    print("🤖 Testing Gemini API Integration\n")
    
    # Display configuration
    display_configuration_info()
    
    # Test basic connection
    if not test_api_connection():
        print("\n❌ Basic API connection failed. Please check your configuration.")
        return
    
    # Test embedding generation
    test_texts = [
        "HTTP 500 internal server error occurred during payment processing",
        "Database connection timeout after 30 seconds of waiting",
        "SSL certificate verification failed for external API call",
        "Memory usage exceeded threshold causing application slowdown",
        "Rate limiting activated due to too many requests per minute"
    ]
    
    results = test_embedding_generation(test_texts)
    
    print(f"\n📊 Embedding Generation Results:")
    print(f"   • Successful: {results['successful']}/{len(test_texts)}")
    print(f"   • Failed: {results['failed']}/{len(test_texts)}")
    print(f"   • Total time: {results['total_time']:.2f}s")
    print(f"   • Average time per embedding: {results['avg_time']:.2f}s")
    
    if results['errors']:
        print(f"   • Errors encountered:")
        for error in results['errors']:
            print(f"     - {error}")
    
    if results['embeddings']:
        print(f"   • Sample embedding info:")
        for i, emb in enumerate(results['embeddings'][:2], 1):
            print(f"     {i}. Text: {emb['text']}")
            print(f"        Dimensions: {emb['dimensions']}")
            print(f"        Sample values: {emb['sample_values']}")
    
    # Test different task types
    test_different_task_types(test_texts[0])
    
    # Test rate limiting
    test_rate_limiting()
    
    # Final summary
    print(f"\n{'='*60}")
    print("Gemini API Test Summary")
    print(f"{'='*60}")
    
    if results['successful'] == len(test_texts):
        print("✅ All tests passed! Gemini API is working correctly.")
    elif results['successful'] > 0:
        print("⚠️ Some tests passed, but there were issues. Check the errors above.")
    else:
        print("❌ All tests failed. Please check your API key and configuration.")
    
    print(f"\n💡 Tips:")
    print(f"   • Make sure GOOGLE_API_KEY or GEMINI_API_KEY is set in your .env file")
    print(f"   • Install with: uv add google-generativeai")
    print(f"   • Check API quotas at: https://console.cloud.google.com/")
    
    print(f"\n✨ Testing completed!")


if __name__ == "__main__":
    main()
