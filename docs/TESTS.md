# Tests

## Support Bot Crew Tests

### 1. Prompt Guardrail

Testing the two cases:

1. Irrelevant Prompt
2. Relevant Prompt

```bash
uv run pytest -v tests/test_prompt_guardrail.py
```

### 2. Embeddings

```bash
uv run pytest --capture=no tests/test_embeddings.py
```

### 3. Gemini Embeddings

```bash
uv run pytest --capture=no tests/test_gemini_api.py
```
