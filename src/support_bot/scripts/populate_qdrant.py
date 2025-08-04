"""
Populate Qdrant vector database with incident data.

This script loads incident data from JSON files and creates vector embeddings
using either Sentence Transformers or Gemini embeddings, then stores them
in a Qdrant vector database for semantic search.
"""

import json
import os
import hashlib
import struct
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    print("Qdrant client not available. Please install with: uv add qdrant-client")
    QDRANT_AVAILABLE = False

try:
    from ..utils.embeddings import EmbeddingGenerator
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    print("Embeddings module not available.")
    EMBEDDINGS_AVAILABLE = False

# Legacy imports for fallback
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


def simple_text_embedding(text: str, dimensions: int = 384) -> List[float]:
    """Create a simple hash-based embedding for text as fallback."""
    text_hash = hashlib.md5(text.encode()).digest()
    
    embedding = []
    for i in range(0, len(text_hash), 4):
        chunk = text_hash[i:i+4]
        if len(chunk) == 4:
            num = struct.unpack('I', chunk)[0]
            embedding.append((num % 1000000) / 1000000.0)
    
    # Pad or truncate to desired dimensions
    while len(embedding) < dimensions:
        embedding.extend(embedding[:min(len(embedding), dimensions - len(embedding))])
    
    return embedding[:dimensions]


def get_incidents_data_path() -> Path:
    """Get the path to the incidents data file."""
    current_dir = Path(__file__).parent
    # Navigate from src/support_bot/scripts/ to data/
    data_path = current_dir.parent.parent.parent / "data" / "incidents.json"
    return data_path


def populate_qdrant_with_incidents(
    use_gemini: bool = False,
    collection_name: str = "incident_data",
    recreate: bool = False,
    data_file: Optional[str] = None
) -> bool:
    """
    Populate Qdrant database with incident data.
    
    Args:
        use_gemini: Whether to use Gemini embeddings
        collection_name: Name of the Qdrant collection
        recreate: Whether to recreate the collection if it exists
        data_file: Path to custom data file (optional)
    
    Returns:
        True if successful, False otherwise
    """
    if not QDRANT_AVAILABLE:
        print("❌ Qdrant client not available. Cannot proceed.")
        return False
    
    # Load environment variables
    load_dotenv()
    
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    
    if not qdrant_url or not qdrant_api_key:
        print("❌ Error: QDRANT_URL and QDRANT_API_KEY must be set in .env file")
        return False
    
    print(f"🔗 Connecting to Qdrant at {qdrant_url}")
    
    # Initialize Qdrant client
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        return False
    
    # Initialize embedding system
    embedding_generator = None
    use_sentence_transformers = False
    embedding_dimensions = 384
    
    if EMBEDDINGS_AVAILABLE:
        try:
            embedding_generator = EmbeddingGenerator(prefer_gemini=use_gemini)
            embedding_dimensions = embedding_generator.get_embedding_dimensions()
            embedding_type = (
                "Gemini" if embedding_generator.use_gemini
                else "Sentence Transformers" if embedding_generator.use_sentence_transformers
                else "Simple Hash"
            )
            print(f"🧠 Using {embedding_type} for embeddings (dimensions: {embedding_dimensions})")
        except Exception as e:
            print(f"⚠️ Failed to initialize embedding generator: {e}")
            return False
    elif SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            print("🧠 Using sentence transformers for embeddings")
            use_sentence_transformers = True
            embedding_dimensions = 384
        except Exception as e:
            print(f"⚠️ Failed to initialize sentence transformer: {e}")
            print("🔄 Using simple text embedding fallback")
            use_sentence_transformers = False
            embedding_dimensions = 3072 if use_gemini else 384
    else:
        print("🔄 Using simple text embedding fallback")
        use_sentence_transformers = False
        embedding_dimensions = 3072 if use_gemini else 384
    
    try:
        # Handle collection creation/recreation
        collection_exists = False
        try:
            collection_info = client.get_collection(collection_name)
            collection_exists = True
            current_dimensions = collection_info.config.params.vectors.size
            
            if recreate:
                print(f"🗑️ Deleting existing collection '{collection_name}'")
                client.delete_collection(collection_name)
                collection_exists = False
            elif current_dimensions != embedding_dimensions:
                print(f"⚠️ Dimension mismatch: collection has {current_dimensions}, need {embedding_dimensions}")
                print(f"🗑️ Deleting and recreating collection '{collection_name}'")
                client.delete_collection(collection_name)
                collection_exists = False
            else:
                print(f"✅ Collection '{collection_name}' already exists with correct dimensions")
        except Exception:
            # Collection doesn't exist
            collection_exists = False
        
        if not collection_exists:
            print(f"🆕 Creating collection '{collection_name}' with {embedding_dimensions} dimensions")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE)
            )
        
        # Load incidents data
        if data_file:
            incidents_path = Path(data_file)
        else:
            incidents_path = get_incidents_data_path()
        
        if not incidents_path.exists():
            print(f"❌ Data file not found: {incidents_path}")
            return False
        
        print(f"📂 Loading incident data from {incidents_path}")
        with open(incidents_path, 'r', encoding='utf-8') as file:
            incidents_data = json.load(file)
        
        print(f"📊 Processing {len(incidents_data)} incidents...")
        
        # Prepare points for insertion
        points = []
        for i, incident in enumerate(incidents_data):
            # Create searchable text by combining all relevant fields
            searchable_text = f"""
            Incident ID: {incident.get('Incident ID', '')}
            Main Issue: {incident.get('Main Issue', '')}
            Details: {incident.get('text', '')}
            """.strip()
            
            # Generate embedding
            embedding = None
            if EMBEDDINGS_AVAILABLE and embedding_generator:
                embedding = embedding_generator.generate_embedding(
                    searchable_text, 
                    task_type="RETRIEVAL_DOCUMENT"
                )
            elif use_sentence_transformers:
                embedding = model.encode(searchable_text).tolist()
            else:
                embedding = simple_text_embedding(searchable_text, embedding_dimensions)
            
            if embedding:
                point = PointStruct(
                    id=i,
                    vector=embedding,
                    payload={
                        "incident_id": incident.get('Incident ID', ''),
                        "main_issue": incident.get('Main Issue', ''),
                        "text": incident.get('text', ''),
                        "searchable_text": searchable_text
                    }
                )
                points.append(point)
                print(f"✅ Prepared point {i}: {incident.get('Incident ID', '')}")
            else:
                print(f"⚠️ Failed to generate embedding for incident {i}")
        
        # Insert points into Qdrant
        if points:
            print(f"💾 Inserting {len(points)} incidents into Qdrant...")
            client.upsert(collection_name=collection_name, points=points)
            print(f"✅ Successfully inserted {len(points)} incidents into Qdrant")
            return True
        else:
            print("❌ No valid points to insert")
            return False
            
    except Exception as e:
        print(f"❌ Error populating Qdrant: {str(e)}")
        return False


def main():
    """Entry point for the populate-qdrant script."""
    parser = argparse.ArgumentParser(
        description='Populate Qdrant database with incident data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run populate-qdrant                    # Use Sentence Transformers
  uv run populate-qdrant --gemini           # Use Gemini embeddings
  uv run populate-qdrant --gemini --recreate # Recreate collection with Gemini
  uv run populate-qdrant --collection mydata # Use custom collection name
        """
    )
    
    parser.add_argument(
        '--gemini', 
        action='store_true',
        help='Use Gemini embeddings instead of Sentence Transformers'
    )
    parser.add_argument(
        '--collection', 
        default='incident_data',
        help='Qdrant collection name (default: incident_data)'
    )
    parser.add_argument(
        '--recreate', 
        action='store_true',
        help='Recreate the collection if it exists'
    )
    parser.add_argument(
        '--data-file',
        type=str,
        help='Path to custom incidents JSON file'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        print("🚀 Starting Qdrant population process...")
        print(f"   • Embedding type: {'Gemini' if args.gemini else 'Sentence Transformers'}")
        print(f"   • Collection: {args.collection}")
        print(f"   • Recreate: {args.recreate}")
        if args.data_file:
            print(f"   • Data file: {args.data_file}")
    
    success = populate_qdrant_with_incidents(
        use_gemini=args.gemini,
        collection_name=args.collection,
        recreate=args.recreate,
        data_file=args.data_file
    )
    
    if success:
        print("🎉 Qdrant population completed successfully!")
        exit(0)
    else:
        print("💥 Qdrant population failed!")
        exit(1)


if __name__ == "__main__":
    main()
