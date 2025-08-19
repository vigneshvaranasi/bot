from crewai.tools import BaseTool
from typing import List, Dict, Any
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field

try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    from ..utils.embeddings import EmbeddingGenerator
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

class QdrantIncidentDataTool(BaseTool):
    name: str = "Qdrant Incident Data Retriever"
    description: str = (
        "Retrieves past incident data from Qdrant vector database using semantic search. "
        "Search for incidents by providing keywords like HTTP codes (499, 400, 429), "
        "issue types (latency, outage, carding), or any natural language query. "
        "Returns the most relevant incident information including root cause and mitigation steps.")

    class ArgsSchema(BaseModel):
        argument: Any = Field(
            ..., description="Search query text (plain string). If a dict is provided, the tool will attempt to extract a text field."
        )

    args_schema = ArgsSchema

    def __init__(self, use_gemini=False, emitter=None):
        super().__init__()
        self._emit = emitter
        load_dotenv()
        
        # Initialize client and embedding generator without setting as instance attributes
        qdrant_url = os.getenv('QDRANT_URL')
        qdrant_api_key = os.getenv('QDRANT_API_KEY')
        
        if QDRANT_AVAILABLE and EMBEDDINGS_AVAILABLE and qdrant_url and qdrant_api_key:
            try:
                self._client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
                self._embedding_generator = EmbeddingGenerator(prefer_gemini=use_gemini)
                self._use_qdrant = True
                embedding_type = "Gemini" if self._embedding_generator.use_gemini else "Sentence Transformers" if self._embedding_generator.use_sentence_transformers else "Simple Hash"
                # print(f"Qdrant client initialized successfully with {embedding_type} embeddings")
            except Exception as e:
                print(f"Failed to initialize Qdrant client: {e}")
                self._client = None
                self._embedding_generator = None
                self._use_qdrant = False
        else:
            print("Qdrant not configured or dependencies missing. Using fallback JSON search.")
            self._client = None
            self._embedding_generator = None
            self._use_qdrant = False
        
        self._collection_name = "incident_data"

        # If connected to Qdrant, auto-align embedding dimensions with the collection
        try:
            if self._use_qdrant and self._client:
                info = self._client.get_collection(self._collection_name)
                # Not all client versions expose the same path; try common ones
                size = None
                try:
                    size = info.config.params.vectors.size  # qdrant-client >=1.7
                except Exception:
                    try:
                        size = info.vectors_count  # older/alternative
                    except Exception:
                        size = None

                if size in (3072, 384):
                    desired_gemini = (size == 3072)
                    # Recreate embedding generator if preference mismatches
                    if self._embedding_generator and getattr(self._embedding_generator, 'prefer_gemini', None) != desired_gemini:
                        self._embedding_generator = EmbeddingGenerator(prefer_gemini=desired_gemini)
                        src = "Gemini" if desired_gemini else "Sentence Transformers/Simple"
                        print(f"Aligned embedding generator to collection size {size} ({src}).")
        except Exception as _e:
            # Non-fatal; fall back to existing generator and JSON
            pass

    def _run(self, argument: Any) -> str:
        """
        Run the tool. Accepts either a plain string or a dict-like payload and
        normalizes it to a search string to be resilient to LLM/tool-caller quirks.
        """
        # Normalize input into a plain string query
        query = self._normalize_argument(argument)
        if self._emit:
            try:
                self._emit("tool:start", {"tool": "qdrant", "query": query})
            except Exception:
                pass
        else:
            print(f"--- Searching for incidents matching: {query} ---")

        if not query:
            return "Error: No valid search query provided to Qdrant Incident Data Retriever."

        # Use Qdrant if available, otherwise fall back to JSON search
        if self._use_qdrant and self._client and self._embedding_generator:
            result = self._search_qdrant(query)
        else:
            result = self._search_json_fallback(query)

        if self._emit:
            try:
                self._emit("tool:end", {"tool": "qdrant"})
            except Exception:
                pass
        return result

    def _normalize_argument(self, argument: Any) -> str:
        """
        Best-effort normalization of various input shapes into a string query.
        Handles cases where the caller accidentally passes a dict like
        {"description": "...", "type": "str"} or {"query": "..."}.
        """
        try:
            # If it's already a string, trim and return
            if isinstance(argument, str):
                return argument.strip()

            # If it's a dict-like, try common keys in order
            if isinstance(argument, dict):
                for key in (
                    "query",
                    "search_query",
                    "search",
                    "text",
                    "description",
                    "argument",
                    "value",
                    "input",
                ): 
                    val = argument.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()

                # If dict contains a single string value somewhere, pick the first
                for val in argument.values():
                    if isinstance(val, str) and val.strip():
                        return val.strip()

                # Fallback: stringify
                return str(argument)

            # List/tuple: join strings
            if isinstance(argument, (list, tuple)):
                parts = [str(x) for x in argument if x is not None]
                return " ".join(parts).strip()

            # Anything else: coerce to string
            return str(argument).strip()
        except Exception:
            return ""
    
    def _search_qdrant(self, argument: str) -> str:
        """Search using Qdrant vector database"""
        try:
            # Determine collection vector size to match dimensions
            collection_size = None
            try:
                info = self._client.get_collection(self._collection_name)
                try:
                    collection_size = info.config.params.vectors.size
                except Exception:
                    collection_size = None
            except Exception:
                collection_size = None

            # Generate embedding for the search query with matching dimensions
            if collection_size in (3072, 384) and hasattr(self._embedding_generator, 'generate_embedding_with_dimensions'):
                query_embedding = self._embedding_generator.generate_embedding_with_dimensions(
                    argument,
                    collection_size,
                    task_type="RETRIEVAL_QUERY",
                )
            else:
                query_embedding = self._embedding_generator.generate_embedding(
                    argument,
                    task_type="RETRIEVAL_QUERY",
                )
            
            if not query_embedding:
                return f"Error: Could not generate embedding for query: '{argument}'"
            
            # Search in Qdrant
            search_results = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_embedding,
                limit=8,  # get more to allow date-sorting and trim to 3-4 later
                score_threshold=0.15  # lower threshold to reduce sensitivity
            )
            
            if not search_results:
                return f"No relevant incidents found for query: '{argument}'"
            
            # Format the results
            # Sort by date extracted from incident_id (PAYU-INC-YYYY-MM-DD-XXX) if possible
            def _extract_date(payload):
                import re
                iid = payload.get('incident_id') or payload.get('Incident ID') or payload.get('incidentId') or ''
                m = re.search(r'(\d{4}-\d{2}-\d{2})', str(iid))
                return m.group(1) if m else '0000-00-00'

            # sort by date desc while keeping similarity secondary
            search_results_sorted = sorted(
                search_results,
                key=lambda h: (_extract_date(h.payload), h.score),
                reverse=True,
            )

            # Keep most recent top 4
            top_hits = search_results_sorted[:4]
            if self._emit:
                try:
                    self._emit("tool:results", {"tool": "qdrant", "count": len(top_hits)})
                except Exception:
                    pass

            result = f"Found {len(top_hits)} relevant incident(s) for '{argument}' (Vector Search):\n\n"
            
            for i, hit in enumerate(top_hits, 1):
                payload = hit.payload
                similarity_score = hit.score
                
                result += f"=== INCIDENT {i} (Similarity: {similarity_score:.3f}) ===\n"
                result += f"ID: {payload.get('incident_id', payload.get('Incident ID', payload.get('incidentId', 'N/A')))}\n"
                result += f"Main Issue: {payload.get('main_issue', 'N/A')}\n"
                result += f"Details:\n{payload.get('text', 'N/A')}\n"
                result += "=" * 50 + "\n\n"
            
            return result
            
        except Exception as e:
            print(f"Qdrant search failed: {e}, falling back to JSON search")
            return self._search_json_fallback(argument)
    
    def _search_json_fallback(self, argument: str) -> str:
        """Fallback to JSON file search when Qdrant is not available"""
        try:
            # Get the path to incidents.json relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            incidents_path = os.path.join(current_dir, "..", "..", "..", "data", "incidents.json")
            
            # Load incidents data
            with open(incidents_path, 'r', encoding='utf-8') as file:
                incidents_data = json.load(file)
            
            # Search for matching incidents
            matching_incidents = self._search_incidents(incidents_data, argument)
            
            if not matching_incidents:
                # loosen: return nearest by simple keyword overlap if any; else say none
                # fall back to last 4 incidents by date to still provide nearest context
                try:
                    import re
                    def _date(i):
                        iid = i.get('Incident ID', '')
                        m = re.search(r'(\d{4}-\d{2}-\d{2})', iid)
                        return m.group(1) if m else '0000-00-00'
                    recent = sorted(incidents_data, key=_date, reverse=True)[:4]
                    matching_incidents = recent
                except Exception:
                    return f"No incidents found matching query: '{argument}'"
            
            # Format the results
            # Keep most recent top 4
            try:
                import re
                def _date(i):
                    iid = i.get('Incident ID', '')
                    m = re.search(r'(\d{4}-\d{2}-\d{2})', iid)
                    return m.group(1) if m else '0000-00-00'
                matching_incidents = sorted(matching_incidents, key=_date, reverse=True)[:4]
            except Exception:
                matching_incidents = matching_incidents[:4]

            if self._emit:
                try:
                    self._emit("tool:results", {"tool": "json_fallback", "count": len(matching_incidents)})
                except Exception:
                    pass

            result = f"Found {len(matching_incidents)} incident(s) matching '{argument}' (JSON Search):\n\n"
            
            for i, incident in enumerate(matching_incidents, 1):
                result += f"=== INCIDENT {i} ===\n"
                result += f"ID: {incident.get('Incident ID', 'N/A')}\n"
                result += f"Main Issue: {incident.get('Main Issue', 'N/A')}\n"
                result += f"Details:\n{incident.get('text', 'N/A')}\n"
                result += "=" * 50 + "\n\n"
            
            return result
            
        except FileNotFoundError:
            return f"Error: incidents.json file not found at {incidents_path}"
        except json.JSONDecodeError:
            return "Error: Could not parse incidents.json file"
        except Exception as e:
            return f"Error fetching incident data: {str(e)}"
    
    def _search_incidents(self, incidents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Search incidents based on the query string"""
        query_lower = query.lower()
        matching_incidents = []
        
        for incident in incidents:
            # Search in all text fields
            search_text = f"{incident.get('Incident ID', '')} {incident.get('Main Issue', '')} {incident.get('text', '')}"
            search_text_lower = search_text.lower()
            
            # Check if query matches any part of the incident
            if query_lower in search_text_lower:
                matching_incidents.append(incident)
        
        return matching_incidents

    def _search_by_keywords(self, keywords: List[str], limit: int = 3) -> str:
        """Alternative method to search by specific keywords"""
        try:
            # Combine keywords into a search query
            query = " ".join(keywords)
            return self._run(query)
        except Exception as e:
            return f"Error in keyword search: {str(e)}"
