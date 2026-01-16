import json
import logging
from typing import List, Dict, Any, Generator

from config import (
    EMBEDDING_SETTINGS, 
    QDRANT_SETTINGS, 
    DATA_SETTINGS, 
    SPLITTER_SETTINGS
)

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_incidents(json_path: str) -> List[Dict[str, Any]]:
    """Loads the list of incident JSON objects from a file."""
    logging.info(f"Loading incidents from {json_path}...")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            incidents = json.load(f)
        logging.info(f"Successfully loaded {len(incidents)} incidents.")
        return incidents
    except FileNotFoundError:
        logging.error(f"Error: The file {json_path} was not found.")
        exit(1)
    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from {json_path}.")
        exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading data: {e}")
        exit(1)

def parse_description_metadata(description: str) -> Dict[str, str]:
    """
    Parses the newline-separated key-value pairs in the incident_description
    field into a flat dictionary.
    """
    metadata = {}
    for line in description.split('\n'):
        if ':' in line:
            try:
                key, value = line.split(':', 1)
                metadata_key = key.strip()
                metadata[metadata_key] = value.strip()
            except ValueError:
                logging.warning(f"Could not parse line: {line}")
    return metadata

def create_documents_from_incidents(
    incidents: List[Dict[str, Any]], 
    chunk_size: int, 
    chunk_overlap: int
) -> Generator[Document, None, None]:
    """
    Processes each incident, creates chunks, and yields Document objects
    ready for embedding.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    for incident in incidents:
        try:
            source_text = f"""
            Incident Title: {incident.get('incident_title', 'N/A')}
            Incident Description: {incident.get('incident_description', 'N/A')}
            Action Taken and Resolution: {incident.get('action_taken', 'N/A')}
            """
            
            desc_metadata = parse_description_metadata(incident.get('incident_description', ''))
            
            doc_metadata = {
                "incident_id": incident.get('incident_id', 'N/A'),
                "incident_title": incident.get('incident_title', 'N/A'),
                "impacted_application": desc_metadata.get('impactedApplication', 'N/A'),
                "root_cause": desc_metadata.get('rootCause', 'N/A'),
                "mitigation": desc_metadata.get('mitigation', 'N/A'),
                "accountable_party": desc_metadata.get('accountableParty', 'N/A'),
                "source_system": desc_metadata.get('sourceSystem', 'N/A'),
                "repeat_incident": desc_metadata.get('repeatIncident', 'False'),
                "source_file": "data/tmp.json"
            }

            chunks = text_splitter.split_text(source_text)
            
            for i, chunk in enumerate(chunks):
                chunk_metadata = doc_metadata.copy()
                chunk_metadata['chunk_number'] = i
                yield Document(page_content=chunk, metadata=chunk_metadata)
                
        except Exception as e:
            logging.warning(f"Skipping incident {incident.get('incident_id')}: Error {e}")


def main():
    """Main function to run the ingestion pipeline using settings from config.py."""
    
    # 1. Load data
    incidents = load_incidents("data/tmp.json")

    # 2. Create documents
    logging.info("Creating documents and chunks...")
    documents = list(create_documents_from_incidents(
        incidents,
        chunk_size=SPLITTER_SETTINGS.CHUNK_SIZE,
        chunk_overlap=SPLITTER_SETTINGS.CHUNK_OVERLAP
    ))
    logging.info(f"Created {len(documents)} chunks from {len(incidents)} incidents.")

    if not documents:
        logging.warning("No documents were created. Exiting.")
        return

    # 3. Initialize embedding model
    logging.info(f"Loading embedding model: {EMBEDDING_SETTINGS.MODEL_NAME} on device: {EMBEDDING_SETTINGS.DEVICE}")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_SETTINGS.MODEL_NAME,
        model_kwargs=EMBEDDING_SETTINGS.MODEL_KWARGS,
        encode_kwargs=EMBEDDING_SETTINGS.ENCODE_KWARGS
    )

    # 4. Ingest into Qdrant
    logging.info(f"Ingesting documents into Qdrant at {QDRANT_SETTINGS.URL} (collection: {QDRANT_SETTINGS.COLLECTION_NAME})...")
    
    # --- START OF FIX ---
    
    # Determine URL or location from config
    url = None
    location = None
    if QDRANT_SETTINGS.URL == ":memory:":
        location = QDRANT_SETTINGS.URL
    else:
        url = QDRANT_SETTINGS.URL

    # Pass the arguments directly to the method
    # The 'embeddings' variable (our model) satisfies the 'embedding' argument
    Qdrant.from_documents(
        documents,
        embeddings,  # This is the 2nd positional argument, 'embedding'
        url=url,
        location=location,
        collection_name=QDRANT_SETTINGS.COLLECTION_NAME
    )
    
    # --- END OF FIX ---
    
    logging.info("Ingestion complete. Vector store is ready.")

if __name__ == "__main__":
    main()