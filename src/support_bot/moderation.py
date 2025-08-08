import re
import os
import logging
try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

# List of fields or keywords to redact (can be extended)
DEFAULT_FIELDS_TO_REDACT = [
    'ssn', 'email', 'phone', 'address', 'credit_card', 'dob', 'passport', 'pan', 'aadhar', 'user_id', 'account', 'token', 'password', 'secret', 'api_key'
]

def redact_sensitive_fields(text, fields=None, anonymize_with='xxxxx', use_pii_lib=True, log_redacted=True):
    """
    Redact values for specified fields in a text blob. Optionally use PII detection library.
    """
    redacted_fields = set()
    original_text = text
    # Use Presidio for PII detection if available and requested
    if use_pii_lib and PRESIDIO_AVAILABLE:
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        results = analyzer.analyze(text=text, language='en')
        if results:
            redacted_fields.update([r.entity_type for r in results])
            anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators={
                r.entity_type: {"type": "replace", "new_value": anonymize_with} for r in results
            })
            text = anonymized.text
    # Fallback to field-based regex redaction
    if fields is None:
        fields = DEFAULT_FIELDS_TO_REDACT
    for field in fields:
        pattern = rf'(\b{field}\b\s*[:=]\s*)([^,;\n\r]+)'
        if re.search(pattern, text, flags=re.IGNORECASE):
            redacted_fields.add(field)
        text = re.sub(pattern, rf'\1{anonymize_with}', text, flags=re.IGNORECASE)
    # Logging
    if log_redacted and redacted_fields:
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Redacted fields: {sorted(redacted_fields)}")
    return text

def safe_send_to_llm(prompt, llm, enable_safe_send=None, fields_to_redact=None, anonymize_with='[REDACTED]', use_pii_lib=True, log_redacted=True, **kwargs):
    """
    Send prompt to LLM with optional PII redaction. Controlled by enable_safe_send.
    """
    # By default, enable safe send unless env disables it
    if enable_safe_send is None:
        enable_safe_send = os.getenv('ENABLE_SAFE_SEND', 'true').lower() == 'true'
    if enable_safe_send:
        prompt = redact_sensitive_fields(prompt, fields=fields_to_redact, anonymize_with=anonymize_with, use_pii_lib=use_pii_lib, log_redacted=log_redacted)
    return llm(prompt, **kwargs)
