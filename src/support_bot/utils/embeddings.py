from typing import List
import logging
import hashlib
import struct
import os

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import google.genai as genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

class EmbeddingGenerator:
    def __init__(self, prefer_gemini=False):
        self.prefer_gemini = prefer_gemini
        self.gemini_client = None
        self.model = None
        self.available = False
        self.use_sentence_transformers = False
        self.use_gemini = False
        
        # Initialize Gemini if available and preferred
        if GOOGLE_GENAI_AVAILABLE and prefer_gemini:
            try:
                api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
                if api_key:
                    # Initialize Gemini client with the new API
                    self.gemini_client = genai.Client(api_key=api_key)
                    self.available = True
                    self.use_gemini = True
                    logging.info("Using Gemini embeddings (gemini-embedding-001)")
                else:
                    logging.warning("Gemini API key not found in environment variables")
            except Exception as e:
                logging.warning(f"Failed to initialize Gemini embeddings: {e}")
        
        # Fallback to sentence transformers if Gemini not available or not preferred
        if not self.use_gemini and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                self.available = True
                self.use_sentence_transformers = True
                logging.info("Using sentence transformers for embeddings")
            except Exception as e:
                logging.warning(f"Failed to load sentence transformer model: {e}")
                self.available = True
                self.use_sentence_transformers = False
        elif not self.use_gemini:
            logging.info("sentence-transformers not available. Using simple text embedding")
            self.available = True
            self.use_sentence_transformers = False
    
    def _simple_text_embedding(self, text, dimensions=384):
        """Create a simple hash-based embedding for text"""
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
    
    def _gemini_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Create embedding using Gemini API"""
        try:
            if not self.gemini_client:
                raise Exception("Gemini client not initialized")
                
            result = self.gemini_client.models.embed_content(
                model="gemini-embedding-001",
                contents=[text]
            )
            
            if result.embeddings and len(result.embeddings) > 0:
                return result.embeddings[0].values
            else:
                raise Exception("No embeddings returned from API")
                
        except Exception as e:
            logging.error(f"Error generating Gemini embedding: {str(e)}")
            # Fallback to simple embedding
            return self._simple_text_embedding(text, dimensions=3072)  # Gemini uses 3072 dimensions
    
    def _gemini_embedding_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Create embeddings for multiple texts using Gemini API"""
        embeddings = []
        for text in texts:
            embedding = self._gemini_embedding(text, task_type)
            embeddings.append(embedding)
        return embeddings
        
    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Generate embedding for a given text
        
        Args:
            text: Text to embed
            task_type: For Gemini - RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING
        """
        if not self.available:
            logging.error("Embedding model not available")
            return []
            
        try:
            if self.use_gemini:
                return self._gemini_embedding(text, task_type)
            elif self.use_sentence_transformers:
                embedding = self.model.encode(text)
                return embedding.tolist()
            else:
                # Adjust dimensions based on model type
                dimensions = 3072 if self.prefer_gemini else 384
                return self._simple_text_embedding(text, dimensions)
        except Exception as e:
            logging.error(f"Error generating embedding: {str(e)}")
            return []
    
    def generate_embeddings_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            task_type: For Gemini - RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING
        """
        if not self.available:
            return []
            
    def generate_embedding_with_dimensions(self, text: str, dimensions: int, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """
        Generate an embedding with an exact target dimensionality, choosing the
        best available backend and falling back to simple embedding to match size.
        """
        try:
            # Prefer native backends only when their dimension matches
            if self.use_gemini and dimensions == 3072:
                vec = self._gemini_embedding(text, task_type)
                # Pad/truncate defensively
                if len(vec) != dimensions:
                    return (vec + [0.0] * dimensions)[:dimensions]
                return vec

            if self.use_sentence_transformers and dimensions == 384:
                vec = self.model.encode(text).tolist()
                if len(vec) != dimensions:
                    return (vec + [0.0] * dimensions)[:dimensions]
                return vec

            # Fallback: simple embedding with requested size
            return self._simple_text_embedding(text, dimensions)
        except Exception:
            return self._simple_text_embedding(text, dimensions)

        try:
            if self.use_gemini:
                return self._gemini_embedding_batch(texts, task_type)
            elif self.use_sentence_transformers:
                embeddings = self.model.encode(texts)
                return [emb.tolist() for emb in embeddings]
            else:
                # Adjust dimensions based on model type
                dimensions = 3072 if self.prefer_gemini else 384
                return [self._simple_text_embedding(text, dimensions) for text in texts]
        except Exception as e:
            logging.error(f"Error generating batch embeddings: {str(e)}")
            return []
    
    def get_embedding_dimensions(self) -> int:
        """Get the dimensions of embeddings produced by this generator"""
        if self.use_gemini:
            return 3072  # Gemini embedding dimensions
        elif self.use_sentence_transformers:
            return 384  # Sentence transformers all-MiniLM-L6-v2 dimensions
        else:
            return 3072 if self.prefer_gemini else 384  # Fallback dimensions
