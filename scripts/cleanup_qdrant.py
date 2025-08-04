#!/usr/bin/env python3
"""
Clean up Qdrant collections for testing different embedding types
"""
import os
from dotenv import load_dotenv
import sys

# Add the src directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "..", "src")
sys.path.insert(0, src_dir)

try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    print("Qdrant client not available.")
    QDRANT_AVAILABLE = False

def cleanup_collections():
    """Delete existing collections to start fresh"""
    if not QDRANT_AVAILABLE:
        print("Qdrant client not available. Cannot proceed.")
        return
        
    load_dotenv()
    
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    
    if not qdrant_url or not qdrant_api_key:
        print("Error: QDRANT_URL and QDRANT_API_KEY must be set in .env file")
        return
    
    # Initialize Qdrant client
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    try:
        # List all collections
        collections = client.get_collections()
        print(f"Found {len(collections.collections)} collections:")
        
        for collection in collections.collections:
            collection_name = collection.name
            print(f"  - {collection_name}")
            
            # Delete each collection
            try:
                client.delete_collection(collection_name)
                print(f"    ✅ Deleted collection: {collection_name}")
            except Exception as e:
                print(f"    ❌ Failed to delete {collection_name}: {e}")
                
    except Exception as e:
        print(f"Error accessing collections: {e}")

if __name__ == "__main__":
    print("🧹 Cleaning up Qdrant collections...")
    cleanup_collections()
    print("✨ Cleanup completed!")
