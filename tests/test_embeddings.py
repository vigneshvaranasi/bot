#!/usr/bin/env python3
"""
Test script to validate Gemini embeddings implementation
"""
import os
import sys
from dotenv import load_dotenv

# Add the src directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "..", "src")
sys.path.insert(0, src_dir)


def test_embeddings():
    """Test both Sentence Transformers and Gemini embeddings"""
    load_dotenv()
    
    from support_bot.utils.embeddings import EmbeddingGenerator
    
    print("Testing Embedding Implementations\n")
    
    test_text = "HTTP 499 client timeout error with payment processing"
    
    # Test 1: Sentence Transformers (default)
    print("Testing Sentence Transformers Embeddings:")
    try:
        st_generator = EmbeddingGenerator(prefer_gemini=False)
        st_embedding = st_generator.generate_embedding(test_text)
        print(f"   ✅ Generated embedding with {len(st_embedding)} dimensions")
        print(f"   🔧 Model type: {'Sentence Transformers' if st_generator.use_sentence_transformers else 'Simple Hash'}")
        print(f"   📊 Sample values: {st_embedding[:5]}...")
        print()
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 2: Gemini Embeddings (if API key available)
    print("Testing Gemini Embeddings:")
    gemini_api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    
    if gemini_api_key:
        try:
            gemini_generator = EmbeddingGenerator(prefer_gemini=True)
            
            # Test document embedding
            doc_embedding = gemini_generator.generate_embedding(
                test_text, 
                task_type="RETRIEVAL_DOCUMENT"
            )
            print(f"Document embedding: {len(doc_embedding)} dimensions")
            
            # Test query embedding
            query_embedding = gemini_generator.generate_embedding(
                "payment timeout issues", 
                task_type="RETRIEVAL_QUERY"
            )
            print(f"Query embedding: {len(query_embedding)} dimensions")
            
            print(f"Model type: {'Gemini' if gemini_generator.use_gemini else 'Fallback'}")
            print(f"Sample values: {doc_embedding[:5]}...")
            print()
        except Exception as e:
            print(f"Error: {e}\n")
    else:
        print("No Gemini API key found (GOOGLE_API_KEY or GEMINI_API_KEY)")
        print("To test Gemini embeddings, set your API key in .env file\n")

    # Test 3: Batch embeddings
    print("Testing Batch Embeddings:")
    try:
        generator = EmbeddingGenerator(prefer_gemini=bool(gemini_api_key))
        test_texts = [
            "HTTP 499 timeout error",
            "Payment processing failure",
            "Database connection timeout"
        ]
        
        batch_embeddings = generator.generate_embeddings_batch(
            test_texts, 
            task_type="RETRIEVAL_DOCUMENT"
        )
        print(f"Generated {len(batch_embeddings)} embeddings")
        print(f"Each embedding has {len(batch_embeddings[0]) if batch_embeddings else 0} dimensions")
        print()
    except Exception as e:
        print(f"Error: {e}\n")

    print("✨ Embedding tests completed!")


if __name__ == "__main__":
    test_embeddings()
