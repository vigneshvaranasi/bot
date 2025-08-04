import json
import os
from dotenv import load_dotenv
import sys
import argparse

# Add the src directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "..", "src")
sys.path.insert(0, src_dir)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    print("Qdrant client not available. Please install with: pip install qdrant-client")
    QDRANT_AVAILABLE = False

try:
    from support_bot.utils.embeddings import EmbeddingGenerator
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    print("Embeddings module not available.")
    EMBEDDINGS_AVAILABLE = False

# Legacy imports for fallback
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    print("Sentence transformers not available. Using basic text embedding...")
    SENTENCE_TRANSFORMERS_AVAILABLE = False

def simple_text_embedding(text, dimensions=384):
    """Create a simple hash-based embedding for text"""
    import hashlib
    import struct
    
    # Create a hash of the text
    text_hash = hashlib.md5(text.encode()).digest()
    
    # Convert hash to numbers and normalize
    embedding = []
    for i in range(0, len(text_hash), 4):
        chunk = text_hash[i:i+4]
        if len(chunk) == 4:
            num = struct.unpack('I', chunk)[0]
            embedding.append((num % 1000000) / 1000000.0)  # Normalize to 0-1
    
    # Pad or truncate to desired dimensions
    while len(embedding) < dimensions:
        embedding.extend(embedding[:min(len(embedding), dimensions - len(embedding))])
    
    return embedding[:dimensions]

def populate_qdrant_with_incidents(use_gemini=False):
    if not QDRANT_AVAILABLE:
        print("Qdrant client not available. Cannot proceed.")
        return
        
    # Load environment variables
    load_dotenv()
    
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    
    if not qdrant_url or not qdrant_api_key:
        print("Error: QDRANT_URL and QDRANT_API_KEY must be set in .env file")
        return
    
    # Initialize Qdrant client
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    # Initialize embedding generator
    if EMBEDDINGS_AVAILABLE:
        try:
            embedding_generator = EmbeddingGenerator(prefer_gemini=use_gemini)
            embedding_dimensions = embedding_generator.get_embedding_dimensions()
            embedding_type = "Gemini" if embedding_generator.use_gemini else "Sentence Transformers" if embedding_generator.use_sentence_transformers else "Simple Hash"
            print(f"Using {embedding_type} for embeddings (dimensions: {embedding_dimensions})")
        except Exception as e:
            print(f"Failed to initialize embedding generator: {e}")
            return
    # Legacy fallback
    elif SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            print("Using sentence transformers for embeddings")
            use_sentence_transformers = True
            embedding_dimensions = 384
        except Exception as e:
            print(f"Failed to initialize sentence transformer: {e}")
            print("Using simple text embedding")
            use_sentence_transformers = False
            embedding_dimensions = 3072 if use_gemini else 384
    else:
        print("Using simple text embedding")
        use_sentence_transformers = False
        embedding_dimensions = 3072 if use_gemini else 384
    
    # Collection name
    collection_name = "incident_data"
    
    try:
        # Create collection if it doesn't exist
        try:
            client.get_collection(collection_name)
            print(f"Collection '{collection_name}' already exists")
        except:
            print(f"Creating collection '{collection_name}'")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE)
            )
        
        # Load incidents data
        incidents_path = os.path.join(current_dir, "..", "data", "incidents.json")
        with open(incidents_path, 'r', encoding='utf-8') as file:
            incidents_data = json.load(file)
        
        # Prepare points for insertion
        points = []
        for i, incident in enumerate(incidents_data):
            # Create searchable text by combining all relevant fields
            searchable_text = f"""
            Incident ID: {incident.get('Incident ID', '')}
            Main Issue: {incident.get('Main Issue', '')}
            Details: {incident.get('text', '')}
            """
            
            # Generate embedding
            if EMBEDDINGS_AVAILABLE:
                # Use RETRIEVAL_DOCUMENT task type for document embeddings
                embedding = embedding_generator.generate_embedding(
                    searchable_text, 
                    task_type="RETRIEVAL_DOCUMENT"
                )
            elif use_sentence_transformers:
                embedding = model.encode(searchable_text).tolist()
            else:
                embedding = simple_text_embedding(searchable_text, embedding_dimensions)
            
            if embedding:  # Only add if embedding generation was successful
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
                print(f"Prepared point {i}: {incident.get('Incident ID', '')}")
        
        # Insert points into Qdrant
        if points:
            client.upsert(collection_name=collection_name, points=points)
            print(f"Successfully inserted {len(points)} incidents into Qdrant")
        else:
            print("No valid points to insert")
            
    except Exception as e:
        print(f"Error populating Qdrant: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Populate Qdrant database with incident data')
    parser.add_argument('--gemini', action='store_true', 
                       help='Use Gemini embeddings instead of Sentence Transformers')
    args = parser.parse_args()
    
    populate_qdrant_with_incidents(use_gemini=args.gemini)
