import json
import os
from dotenv import load_dotenv
import sys
import argparse

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
    EMBEDDINGS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


def simple_text_embedding(text, dimensions=384):
    import hashlib, struct
    text_hash = hashlib.md5(text.encode()).digest()
    embedding = []
    for i in range(0, len(text_hash), 4):
        chunk = text_hash[i:i+4]
        if len(chunk) == 4:
            num = struct.unpack('I', chunk)[0]
            embedding.append((num % 1000000) / 1000000.0)
    while len(embedding) < dimensions:
        embedding.extend(embedding[:min(len(embedding), dimensions - len(embedding))])
    return embedding[:dimensions]


def populate_qdrant_with_incidents(use_gemini=False):
    if not QDRANT_AVAILABLE:
        print("Qdrant client not available. Cannot proceed.")
        return

    load_dotenv()
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url or not qdrant_api_key:
        print("Error: QDRANT_URL and QDRANT_API_KEY must be set in .env file")
        return

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    if EMBEDDINGS_AVAILABLE:
        embedding_generator = EmbeddingGenerator(prefer_gemini=use_gemini)
        embedding_dimensions = embedding_generator.get_embedding_dimensions()
    elif SENTENCE_TRANSFORMERS_AVAILABLE:
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        embedding_dimensions = 384
    else:
        embedding_dimensions = 384

    collection_name = "incident_data"

    try:
        try:
            client.get_collection(collection_name)
            print(f"Collection '{collection_name}' already exists")
        except:
            print(f"Creating collection '{collection_name}'")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE),
            )

        # Load all JSON files from /data
        data_dir = os.path.join(current_dir, "..", "data")
        incidents_data = []

        for fname in os.listdir(data_dir):
            if fname.endswith(".json"):
                file_path = os.path.join(data_dir, fname)
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        data = json.load(infile)
                        if isinstance(data, list):
                            incidents_data.extend(data)
                        else:
                            incidents_data.append(data)
                        print(f"Loaded {len(data) if isinstance(data, list) else 1} records from {fname}")
                except Exception as e:
                    print(f"Skipping {fname}, invalid JSON: {e}")

        # Insert into Qdrant
        points = []
        for i, incident in enumerate(incidents_data):
            searchable_text = " ".join([str(v) for v in incident.values()])

            if EMBEDDINGS_AVAILABLE:
                embedding = embedding_generator.generate_embedding(searchable_text, task_type="RETRIEVAL_DOCUMENT")
            elif SENTENCE_TRANSFORMERS_AVAILABLE:
                embedding = model.encode(searchable_text).tolist()
            else:
                embedding = simple_text_embedding(searchable_text, embedding_dimensions)

            points.append(
                PointStruct(
                    id=i,
                    vector=embedding,
                    payload={**incident, "searchable_text": searchable_text},
                )
            )

        if points:
            client.upsert(collection_name=collection_name, points=points)
            print(f"✅ Inserted {len(points)} records into Qdrant")
        else:
            print("No valid points to insert")

    except Exception as e:
        print(f"Error populating Qdrant: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate Qdrant database with incident data")
    parser.add_argument("--gemini", action="store_true", help="Use Gemini embeddings instead of Sentence Transformers")
    args = parser.parse_args()
    populate_qdrant_with_incidents(use_gemini=args.gemini)
