import itertools
import os

def get_gemini_api_key():
    """
    Returns a Gemini API key from the GEMINI_API_KEYS env variable (comma-separated if multiple).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No GEMINI_API_KEY found in environment.")
    return api_key
