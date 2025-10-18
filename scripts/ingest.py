import os
import json
from dotenv import load_dotenv
load_dotenv()
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from sentence_transformers import SentenceTransformer

try:
    qdrant_client = QdrantClient(host="localhost", port=6333)
    # Test connection
    qdrant_client.get_collections()
    print("Qdrant connection successful")
except Exception as e:
    print(f"Qdrant connection failed: {e}")
    print("Please make sure Qdrant is running on localhost:6333")

model = SentenceTransformer('all-MiniLM-L6-v2')

# Load incidents from JSON file
def load_incidents():
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'incidents.json')
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)

incidents = load_incidents() 

# Create Qdrant collection
collection_name = "past_issues"
try:
    if qdrant_client.collection_exists(collection_name):
        qdrant_client.delete_collection(collection_name)
        print("Deleted existing collection")
    
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )
    print("✓ Qdrant collection created successfully")
except Exception as e:
    print(f"✗ Failed to create Qdrant collection: {e}")
    exit(1)

# Ingest data
print(f"Starting to ingest {len(incidents)} incidents...")

for i, incident in enumerate(incidents):
    # Create text for embedding (combining incident text and response)
    text = f"{incident['text']} {incident['response']}"
    
    # Generate embedding
    vector = model.encode(text).tolist()
    
    # Insert into Qdrant
    try:
        qdrant_client.upsert(
            collection_name=collection_name,
            points=[
                {
                    "id": i + 1,
                    "vector": vector,
                    "payload": {
                        "incident_id": incident["Incident ID"],
                        "main_issue": incident["Main Issue"],
                        "text": incident["text"],
                        "response": incident["response"]
                    }
                }
            ]
        )
    except Exception as e:
        print(f"Error inserting incident {incident['Incident ID']} into Qdrant: {e}")
        continue
    
    if (i + 1) % 100 == 0:
        print(f"Processed {i + 1} incidents...")

print(f"Successfully ingested {len(incidents)} incident transcripts into Qdrant database.")