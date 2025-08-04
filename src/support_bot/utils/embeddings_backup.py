from typing import List
import logging
import hashlib
import struct

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

class EmbeddingGenerator:
    def __init__(self):
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                self.available = True
                self.use_sentence_transformers = True
                logging.info("Using sentence transformers for embeddings")
            except Exception as e:
                logging.warning(f"Failed to load sentence transformer model: {e}")
                self.available = True
                self.use_sentence_transformers = False
        else:
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
        
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a given text"""
        if not self.available:
            logging.error("Embedding model not available")
            return []
            
        try:
            if self.use_sentence_transformers:
                embedding = self.model.encode(text)
                return embedding.tolist()
            else:
                return self._simple_text_embedding(text)
        except Exception as e:
            logging.error(f"Error generating embedding: {str(e)}")
            return []
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if not self.available:
            return []
            
        try:
            if self.use_sentence_transformers:
                embeddings = self.model.encode(texts)
                return [emb.tolist() for emb in embeddings]
            else:
                return [self._simple_text_embedding(text) for text in texts]
        except Exception as e:
            logging.error(f"Error generating batch embeddings: {str(e)}")
            return []
