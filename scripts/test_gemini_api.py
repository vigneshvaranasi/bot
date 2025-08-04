#!/usr/bin/env python3
"""
Direct test of Google Gemini API for embeddings
"""
import os
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types

def test_gemini_api():
    load_dotenv()
    
    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in .env file")
        return
    
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        print(f"✅ Client initialized with key: {api_key[:10]}...")
        
        # Try basic embedding
        test_text = "This is a test document for embedding"
        
        print(f"🧪 Testing embedding for: '{test_text}'")
        
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=[test_text]
        )
        
        print(f"✅ Success! Embedding generated")
        print(f"📊 Type: {type(result)}")
        print(f"📋 Attributes: {[attr for attr in dir(result) if not attr.startswith('_')]}")
        
        if hasattr(result, 'embeddings'):
            print(f"🔢 Number of embeddings: {len(result.embeddings)}")
            if result.embeddings:
                first_embedding = result.embeddings[0]
                print(f"📐 First embedding type: {type(first_embedding)}")
                print(f"📋 First embedding attributes: {[attr for attr in dir(first_embedding) if not attr.startswith('_')]}")
                
                if hasattr(first_embedding, 'values'):
                    values = first_embedding.values
                    print(f"🎯 Embedding dimensions: {len(values)}")
                    print(f"🔢 Sample values: {values[:5]}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_gemini_api()
