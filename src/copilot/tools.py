from langchain_core.tools import tool
from langchain.schema import Document
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings # Fixed deprecation
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import (
    AttributeInfo,
    StructuredQueryOutputParser,
    get_query_constructor_prompt,
)
from langchain_community.query_constructors.qdrant import QdrantTranslator
from langgraph.config import get_stream_writer
import logging

# --- 1. Define Your Metadata Fields ---
metadata_field_info = [
    AttributeInfo(
        name="incident_id",
        description="The unique identifier for an incident, e.g., 'PAYU-INC-2025-08-24-001'",
        type="string",
    ),
    AttributeInfo(
        name="incident_title",
        description="The high-level title of the incident, e.g., 'Swift Transfer Delay' or 'HTTP 403'",
        type="string",
    ),
    AttributeInfo(
        name="impacted_application",
        description="The name of the software or system that was impacted, e.g., 'PayU Core Payments' or 'Settlement & Reporting'",
        type="string",
    ),
    AttributeInfo(
        name="root_cause",
        description="A summary of the root cause of the incident",
        type="string",
    ),
    AttributeInfo(
        name="mitigation",
        description="The steps taken to resolve or mitigate the incident",
        type="string",
    ),
    AttributeInfo(
        name="accountable_party",
        description="The team or entity responsible for the incident, e.g., 'DevOps/CI-CD' or 'Cloud Provider'",
        type="string",
    ),
    AttributeInfo(
        name="source_system",
        description="The system that reported the incident, e.g., 'Monitoring', 'PagerDuty', or 'ServiceNow'",
        type="string",
    ),
    AttributeInfo(
        name="repeat_incident",
        description="A boolean (as a string) indicating if this was a repeat incident, e.g., 'True.' or 'False.'",
        type="string",
    ),
]

# A description of what the document content is (page_content)
document_content_description = "A chunk of text from an incident report, containing details, actions taken, or post-mortem analysis."

# --- 2. Initialize All Components ---
try:
    llm = ChatOllama(
        model="gpt-oss:20b",
        temperature=0,
        base_url="http://ollama.trackcode.in",
        max_retries=2,
        disable_streaming=True
    )

    # Embedding model
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

    # Qdrant client
    client = QdrantClient(url="http://localhost:6333")

    # LangChain VectorStore wrapper
    vector_store = QdrantVectorStore(
        client=client,
        collection_name="past_issues_v2",
        embedding=embeddings
    )
    logging.info("Successfully connected to Qdrant and loaded embedding model.")
    
    # --- 3. Create the Self-Querying Retriever ---
    retriever = SelfQueryRetriever.from_llm(
        llm,
        vector_store,
        document_content_description,
        metadata_field_info,
        structured_query_translator=QdrantTranslator(metadata_key="metadata"),
        structured_query_parser=StructuredQueryOutputParser.from_components(),
        metadata_key="metadata",
        text_key="page_content",
        verbose=False
    )
    logging.info("Self-Querying Retriever created successfully.")

except Exception as e:
    logging.critical(f"Failed to initialize retriever components: {e}")
    retriever = None

# --- 4. Define the Tool ---
@tool
def get_incident_report(query: str) -> str:
    """
    Searches the internal knowledge base for technical incident reports.
    Use this to answer questions about error resolutions, root causes, mitigations,
    known issues, fixes, and workarounds.
    The input should be a descriptive natural language query, and can
    include specific incident IDs, root causes, or application names.
    """
    writer = get_stream_writer()
    
    if retriever is None:
        error_msg = "Error: The knowledge base retriever is not initialized."
        logging.error(error_msg)
        return "Error Occurred"

    try: 
        writer({"status": f"Parsing query and searching incident reports for: \"{query}\""})
        
        # 1. Invoke the Self-Querying Retriever
        # This one line now does all the magic:
        # - LLM parses query
        # - Builds filter
        # - Queries Qdrant
        docs = retriever.invoke(
            input=query,
            config={
                "stream":False
            }
        )
        
        if not docs:
            return "No relevant incident reports found in the knowledge base."

        # 2. Format results as context for the LLM
        context_blocks = []
        incident_ids = set()
        
        for doc in docs:
            # Access attributes directly from the Document object
            page_content = doc.page_content
            metadata = doc.metadata
            
            incident_id = metadata.get('incident_id', 'N/A')
            print(f"Retrieved Incident ID: {incident_id}")
            incident_ids.add(incident_id)
            
            context_block = f"""
            ---
            Source Incident ID: {incident_id}
            Source Title: {metadata.get('incident_title', 'N/A')}
            Source Root Cause: {metadata.get('root_cause', 'N/A')}
            
            Retrieved Context:
            {page_content}
            ---
            """
            context_blocks.append(context_block)
        
        writer({
            "status":f"Found {len(incident_ids)} relevant incidents..."
        })
        
        return "\n\n".join(context_blocks)

    except Exception as e:
        logging.error(f"Error in get_incident_report (Self-Query): {e}")
        return f"An error occurred while searching for incident reports. This may be due to a malformed query. Error: {e}"

available_tools = [get_incident_report]