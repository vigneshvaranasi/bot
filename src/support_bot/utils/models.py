import itertools
import os

def get_gemini_api_key():
    """
    put multiple keys in the GEMINI_API_KEYS env variable separated by commas
    """
    keys = os.getenv("GEMINI_API_KEYS", "").split(",")
    keys = [k.strip() for k in keys if k.strip()]
    if not keys:
        raise ValueError("No GEMINI_API_KEYS found in environment.")
    if not hasattr(get_gemini_api_key, "key_cycle"):
        get_gemini_api_key.key_cycle = itertools.cycle(keys)
    return next(get_gemini_api_key.key_cycle)