import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from support_bot.moderation import redact_sensitive_fields, safe_send_to_llm

class DummyLLM:
    def __call__(self, prompt, **kwargs):
        return prompt

def test_redact_sensitive_fields():
    test_prompt = """
    User email: alice@example.com
    SSN: 123-45-6789
    Address: 123 Main St
    Some other info: keep this
    """
    expected = """
    User email: ***
    SSN: ***
    Address: ***
    Some other info: keep this
    """
    redacted = redact_sensitive_fields(test_prompt, fields=['email', 'ssn', 'address'], anonymize_with='***')
    # Normalize whitespace for comparison
    assert '\n'.join([l.strip() for l in redacted.strip().splitlines()]) == \
           '\n'.join([l.strip() for l in expected.strip().splitlines()])
    print("redact_sensitive_fields PASSED")

def test_safe_send_to_llm():
    test_prompt = "email: alice@example.com, ssn: 123-45-6789, keep: ok"
    dummy_llm = DummyLLM()
    # Should anonymize by default with 'xxxx'
    result = safe_send_to_llm(test_prompt, dummy_llm, enable_safe_send=True, fields_to_redact=['email', 'ssn'], anonymize_with='xxxx')
    assert 'alice@example.com' not in result and '123-45-6789' not in result
    assert 'xxxx' in result
    print("safe_send_to_llm (enabled) PASSED")
    # Should not anonymize if disabled
    result2 = safe_send_to_llm(test_prompt, dummy_llm, enable_safe_send=False, fields_to_redact=['email', 'ssn'], anonymize_with='xxxx')
    assert 'alice@example.com' in result2 and '123-45-6789' in result2
    print("safe_send_to_llm (disabled) PASSED")

if __name__ == "__main__":
    test_redact_sensitive_fields()
    test_safe_send_to_llm()
    print("All tests passed.")
