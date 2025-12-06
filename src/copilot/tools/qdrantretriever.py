from langchain_core.tools import tool
from langchain.schema import Document
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue
from langchain_qdrant import QdrantVectorStore
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import (
    AttributeInfo,
    StructuredQueryOutputParser,
)
from langchain_community.query_constructors.qdrant  import QdrantTranslator
from langgraph.config import get_stream_writer
import logging
import re
import traceback
# logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

metadata_field_info = [
    AttributeInfo(
        name="incident_id",
        description="The unique identifier for an incident, e.g., 'INC-2025-08-24-001'",
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

document_content_description = "A chunk of text from an incident report, containing details, actions taken, and analysis."

try:
    llm = ChatOllama(
        model="gpt-oss:20b",
        temperature=0,
        base_url="http://ollama.trackcode.in",
        max_retries=2,
        disable_streaming=True
    )

    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

    client = QdrantClient(url="http://localhost:6333")

    vector_store = QdrantVectorStore(
        client=client,
        collection_name="past_issues_v2",
        embedding=embeddings
    )
    
    retriever = SelfQueryRetriever.from_llm(
        llm=llm,
        vectorstore=vector_store,
        document_contents=document_content_description,
        metadata_field_info=metadata_field_info,
        structured_query_translator=QdrantTranslator(metadata_key="metadata"),
        structured_query_parser=StructuredQueryOutputParser.from_components(),
    )
    
except Exception as e:
    traceback.print_exc()
    logging.error(f"Error initializing components: {e}")
    retriever = None

@tool
def get_incident_report(message: str) -> str:
    """
    Searches the internal knowledge base for technical incident reports.
    Use this to answer questions about error resolutions, root causes, mitigations,
    known issues, fixes, and workarounds.
    The input should be the message which is reconstructed user's message with the relevant context.
    include specific incident IDs, root causes, or application names.
    """
    writer = get_stream_writer()
    
    if retriever is None:
        error_msg = "Error: The knowledge base retriever is not initialized."
        logging.error(error_msg)
        return "Error Occurred"

    try: 
        writer({"status": f"Parsing query and searching incidents..."})
        
        normalized_query = message.replace('‑','-')
        print(f"DEBUG: Normalized query: {normalized_query}")

        docs: list[Document] = []

        incident_id_pattern = r"\bINC-\d{4}-\d{2}-\d{2}-\d{3,}\b"
        explicit_incident_ids = {
            match for match in re.findall(incident_id_pattern, normalized_query)
        }

        if explicit_incident_ids:
            writer({
                "status": "Fetching incident details by ID..."
            })

            for incident_id in explicit_incident_ids:
                qdrant_filter = Filter(
                    must=[
                        FieldCondition(
                            key="metadata.incident_id",
                            match=MatchValue(value=incident_id)
                        )
                    ]
                )

                try:
                    next_page = None
                    seen_points = set()
                    while True:
                        points, next_page = vector_store.client.scroll(
                            collection_name=vector_store.collection_name,
                            scroll_filter=qdrant_filter,
                            with_payload=True,
                            with_vectors=False,
                            limit=64,
                            offset=next_page,
                        )

                        if not points:
                            break

                        for point in points:
                            if point.id in seen_points:
                                continue
                            seen_points.add(point.id)

                            payload = point.payload or {}
                            metadata = payload.get("metadata", {})
                            page_content = payload.get("page_content", "")
                            docs.append(
                                Document(
                                    page_content=page_content,
                                    metadata=metadata,
                                )
                            )

                        if next_page is None:
                            break

                except Exception as scroll_error:
                    logging.error(
                        "Error fetching incident %s via direct lookup: %s",
                        incident_id,
                        scroll_error,
                    )

        if not docs:
            docs = retriever.invoke(
                input=normalized_query,
                config={
                    "stream":False
                }
            )
        
        if not docs:
            return "No relevant incident reports found in the knowledge base."

        context_blocks = []
        incident_ids = set()
        
        for doc in docs:
            page_content = doc.page_content
            metadata = doc.metadata
            
            incident_id = metadata.get('incident_id', 'N/A')
            incident_ids.add(incident_id)
            
            root_cause = metadata.get('root_cause', 'N/A')
            mitigation = metadata.get('mitigation', 'N/A')
            impacted_application = metadata.get('impacted_application', 'N/A')
            accountable_party = metadata.get('accountable_party', 'N/A')
            
            context_block = f"""
            ---
            Incident ID: {incident_id}
            Title: {metadata.get('incident_title', 'N/A')}
            Root Cause: {root_cause}
            Mitigation: {mitigation}
            Impacted Application: {impacted_application}
            Accountable Party: {accountable_party}

            Details and Actions Taken and Steps and Fixes:
            {page_content}
            ---
            """
            context_blocks.append(context_block)
        
        writer({
            "status":f"Found {len(incident_ids)} relevant incidents..."
        })
        print(f"DEBUG: Retrieved incident IDs: {', '.join(incident_ids)}")
        # print(f"DEBUG: Context blocks retrieved: {context_blocks}")
        
        return "\n\n".join(context_blocks)

    except Exception as e:
        logging.error(f"Error in get_incident_report (Self-Query): {e}")
        return f"An error occurred while searching for incident reports. This may be due to a malformed query. Error: {e}"

available_tools = [get_incident_report]