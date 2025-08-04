from crewai.tools import BaseTool
from typing import List, Dict, Any
import os
import json
from dotenv import load_dotenv

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

    def __init__(self, use_gemini=False):
        super().__init__()
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
                print(f"Qdrant client initialized successfully with {embedding_type} embeddings")
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

    def _run(self, argument: str) -> str:
        print(f"--- Searching for incidents matching: {argument} ---")
        
        # Use Qdrant if available, otherwise fall back to JSON search
        if self._use_qdrant and self._client and self._embedding_generator:
            return self._search_qdrant(argument)
        else:
            return self._search_json_fallback(argument)
    
    def _search_qdrant(self, argument: str) -> str:
        """Search using Qdrant vector database"""
        try:
            # Generate embedding for the search query using RETRIEVAL_QUERY task type
            query_embedding = self._embedding_generator.generate_embedding(
                argument, 
                task_type="RETRIEVAL_QUERY"
            )
            
            if not query_embedding:
                return f"Error: Could not generate embedding for query: '{argument}'"
            
            # Search in Qdrant
            search_results = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_embedding,
                limit=5,  # Return top 5 most similar incidents
                score_threshold=0.3  # Only return results with similarity > 0.3
            )
            
            if not search_results:
                return f"No relevant incidents found for query: '{argument}'"
            
            # Format the results
            result = f"Found {len(search_results)} relevant incident(s) for '{argument}' (Vector Search):\n\n"
            
            for i, hit in enumerate(search_results, 1):
                payload = hit.payload
                similarity_score = hit.score
                
                result += f"=== INCIDENT {i} (Similarity: {similarity_score:.3f}) ===\n"
                result += f"ID: {payload.get('incident_id', 'N/A')}\n"
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
                return f"No incidents found matching query: '{argument}'"
            
            # Format the results
            result = f"Found {len(matching_incidents)} incident(s) matching '{argument}' (JSON Search):\n\n"
            
            for i, incident in enumerate(matching_incidents, 1):
                result += f"=== INCIDENT {i} ===\n"
                result += f"ID: {incident['Incident ID']}\n"
                result += f"Main Issue: {incident['Main Issue']}\n"
                result += f"Details:\n{incident['text']}\n"
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
