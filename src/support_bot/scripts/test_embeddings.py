"""
Test different embedding implementations.

This script tests and compares the performance of different embedding models
including Sentence Transformers and Gemini embeddings.
"""

import os
import time
from typing import List, Dict, Any

from dotenv import load_dotenv
from ..utils.embeddings import EmbeddingGenerator


def test_embedding_performance(texts: List[str], embedding_type: str = "auto") -> Dict[str, Any]:
    """
    Test embedding performance for a list of texts.
    
    Args:
        texts: List of texts to embed
        embedding_type: "sentence-transformers", "gemini", or "auto"
    
    Returns:
        Dictionary with performance metrics
    """
    load_dotenv()
    
    # Determine embedding preference
    use_gemini = embedding_type == "gemini" or (
        embedding_type == "auto" and 
        (os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))
    )
    
    # Initialize generator
    generator = EmbeddingGenerator(prefer_gemini=use_gemini)
    
    # Get actual embedding type used
    actual_type = (
        "Gemini" if generator.use_gemini
        else "Sentence Transformers" if generator.use_sentence_transformers
        else "Simple Hash"
    )
    
    print(f"🧠 Testing {actual_type} embeddings...")
    
    # Test single embedding
    start_time = time.time()
    single_embedding = generator.generate_embedding(texts[0], task_type="RETRIEVAL_DOCUMENT")
    single_time = time.time() - start_time
    
    # Test batch embeddings
    start_time = time.time()
    batch_embeddings = generator.generate_embeddings_batch(texts, task_type="RETRIEVAL_DOCUMENT")
    batch_time = time.time() - start_time
    
    # Calculate metrics
    dimensions = len(single_embedding) if single_embedding else 0
    total_embeddings = len(batch_embeddings)
    avg_time_per_embedding = batch_time / total_embeddings if total_embeddings > 0 else 0
    
    return {
        "type": actual_type,
        "dimensions": dimensions,
        "single_time": single_time,
        "batch_time": batch_time,
        "total_embeddings": total_embeddings,
        "avg_time_per_embedding": avg_time_per_embedding,
        "sample_values": single_embedding[:5] if single_embedding else [],
        "embeddings": batch_embeddings
    }


def test_similarity_search(query: str, documents: List[str]) -> None:
    """
    Test similarity search capabilities.
    
    Args:
        query: Search query
        documents: List of documents to search through
    """
    import numpy as np
    from numpy.linalg import norm
    
    load_dotenv()
    
    print(f"\n🔍 Testing similarity search for query: '{query}'")
    
    # Test with different embedding types
    for embedding_type in ["sentence-transformers", "gemini"]:
        try:
            use_gemini = embedding_type == "gemini"
            
            # Skip Gemini if no API key
            if use_gemini and not (os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')):
                print(f"⚠️ Skipping {embedding_type} - no API key found")
                continue
            
            generator = EmbeddingGenerator(prefer_gemini=use_gemini)
            
            actual_type = (
                "Gemini" if generator.use_gemini
                else "Sentence Transformers" if generator.use_sentence_transformers
                else "Simple Hash"
            )
            
            print(f"\n📊 Results with {actual_type}:")
            
            # Generate embeddings
            query_embedding = generator.generate_embedding(query, task_type="RETRIEVAL_QUERY")
            doc_embeddings = generator.generate_embeddings_batch(documents, task_type="RETRIEVAL_DOCUMENT")
            
            if not query_embedding or not doc_embeddings:
                print("   ❌ Failed to generate embeddings")
                continue
            
            # Calculate similarities
            query_vec = np.array(query_embedding)
            similarities = []
            
            for i, doc_embedding in enumerate(doc_embeddings):
                if doc_embedding:
                    doc_vec = np.array(doc_embedding)
                    similarity = np.dot(query_vec, doc_vec) / (norm(query_vec) * norm(doc_vec))
                    similarities.append((i, similarity, documents[i]))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Display top results
            for rank, (doc_idx, similarity, doc_text) in enumerate(similarities[:3], 1):
                truncated_text = doc_text[:60] + "..." if len(doc_text) > 60 else doc_text
                print(f"   {rank}. Similarity: {similarity:.3f} - {truncated_text}")
                
        except Exception as e:
            print(f"   ❌ Error with {embedding_type}: {e}")


def main():
    """Entry point for the test-embeddings script."""
    print("🧪 Testing Embedding Implementations\n")
    
    # Test texts
    test_texts = [
        "HTTP 499 client timeout error with payment processing system failure",
        "Database connection timeout causing transaction rollback",
        "SSL certificate expired leading to authentication failures",
        "Rate limiting activated due to suspicious activity patterns",
        "Memory leak in application server causing performance degradation"
    ]
    
    search_query = "payment timeout issues"
    
    # Test different embedding types
    for embedding_type in ["sentence-transformers", "gemini"]:
        try:
            print(f"\n{'='*60}")
            print(f"Testing {embedding_type.title()} Embeddings")
            print(f"{'='*60}")
            
            # Skip Gemini if no API key
            if embedding_type == "gemini":
                api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
                if not api_key:
                    print("⚠️ Skipping Gemini embeddings - no API key found")
                    print("   Set GOOGLE_API_KEY or GEMINI_API_KEY in .env file to test Gemini")
                    continue
            
            # Performance test
            results = test_embedding_performance(test_texts, embedding_type)
            
            print(f"📈 Performance Metrics:")
            print(f"   • Model: {results['type']}")
            print(f"   • Dimensions: {results['dimensions']}")
            print(f"   • Single embedding time: {results['single_time']:.3f}s")
            print(f"   • Batch embedding time: {results['batch_time']:.3f}s")
            print(f"   • Average time per embedding: {results['avg_time_per_embedding']:.3f}s")
            print(f"   • Sample values: {results['sample_values']}")
            
            # Similarity search test
            test_similarity_search(search_query, test_texts)
            
        except Exception as e:
            print(f"❌ Error testing {embedding_type}: {e}")
    
    # Test comparison
    print(f"\n{'='*60}")
    print("Embedding Comparison Summary")
    print(f"{'='*60}")
    
    print("💡 Key Differences:")
    print("   • Sentence Transformers: Fast, local, 384 dimensions")
    print("   • Gemini Embeddings: High-quality, API-based, 3072 dimensions")
    print("   • Simple Hash: Fallback only, deterministic, configurable dimensions")
    
    print("\n🎯 Recommendations:")
    print("   • Use Sentence Transformers for: Fast prototyping, offline usage")
    print("   • Use Gemini for: Production systems, highest quality semantic search")
    print("   • Use Simple Hash for: Testing, when other models unavailable")
    
    print("\n✨ Testing completed!")


if __name__ == "__main__":
    main()
