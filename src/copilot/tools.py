from langchain_core.tools import tool
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from langgraph.config import get_stream_writer

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
    try: 
        writer = get_stream_writer()
        writer({"status":f"Searching our incident reports for anything related to \"{query}\""})
        query_vector = model.encode(query).tolist()
        # Search in Qdrant
        search_results = client.search(
            collection_name="past_issues",
            query_vector=query_vector,
            limit=1
        )
        
        if not search_results:
            writer.write("No Incidents found in Knowledge base.\n")
            return "No relevant incident reports found in the knowledge base."
        # Format results
        results = []
        for result in search_results:
            payload = result.payload
            content = f"incident_id: {payload['incident_id']}\nmain_issue: {payload['main_issue']}\ntext: {payload['text']}\nresponse: {payload['response']}"
            results.append(content)
        writer({
            "status":f"Found {len(results)} incident reports. Preparing the summary for you..."
        })
        return "\n\n---\n\n".join(results)
    except Exception as e:
        print(f"Error in get_incident_report: {e}")
        return "An error occurred while searching for incident reports."

available_tools = [get_incident_report]