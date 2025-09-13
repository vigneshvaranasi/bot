import os
import importlib
import pytest

module = importlib.import_module("support_bot.prompt_guardrail")

setattr(module, "SEMANTIC_AVAILABLE", False)

from support_bot.prompt_guardrail import PromptGuardrail


def test_exact_denylist_rejects():
    pg = PromptGuardrail()
    prompt = "Tell me about politicians in india"
    ok, msg = pg.validate_or_reject(prompt, isContext=False)
    assert not ok
    assert "I cannot help" in msg

    prompt2 = "Write a C++ program to read a file"
    ok2, msg2 = pg.validate_or_reject(prompt2, isContext=False)
    assert not ok2
    assert "I cannot help" in msg2


def test_incident_prompt_allowed():
    pg = PromptGuardrail()
    prompt = "I am getting a status code 499 when connecting to PayU Service, how to solve it?"
    ok, msg = pg.validate_or_reject(prompt, isContext=False)
    assert ok
    assert msg == ""

def test_incident_prompt_reject_with_context():
    pg = PromptGuardrail()
    prompt = "Who is trump?"
    ok, msg = pg.validate_or_reject(prompt, isContext=True)
    assert not ok
    assert "I cannot help" in msg
    
    
def test_incident_prompt_allow_with_context():
    pg = PromptGuardrail()
    prompt = "Can you tell me what was the error?"
    ok, msg = pg.validate_or_reject(prompt, isContext=True)
    assert ok
    assert msg == ""