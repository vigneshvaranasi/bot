from langchain_core.documents import Document
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Initialize Qdrant client and embedding model
client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer('all-MiniLM-L6-v2')

@tool
def get_incident_report(query: str) -> str:
    """
    Searches the internal knowledge base for technical incident reports.
    Use this to answer questions about error resolutions, known issues, fixes, and workarounds.
    The input should be a descriptive search query.
    """
    # Generate embedding for the query
    query_vector = model.encode(query).tolist()
    
    # Search in Qdrant
    search_results = client.search(
        collection_name="past_issues",
        query_vector=query_vector,
        limit=1
    )
    
    if not search_results:
        return "No relevant incident reports found in the knowledge base."
    
    # Format results
    results = []
    for result in search_results:
        payload = result.payload
        content = f"Incident ID: {payload['incident_id']}\nIssue: {payload['issue']}\nResolution: {payload['resolution']}\nEscalation Path: {payload['escalation_path']}\nTools Used: {payload['tools_used']}"
        results.append(content)
    
    return "\n\n---\n\n".join(results)

available_tools = [get_incident_report]