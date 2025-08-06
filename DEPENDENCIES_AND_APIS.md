# Project Dependencies and External APIs

## Dependencies

The following Python packages are specified in `pyproject.toml`:

### Core AI and ML
- `crewai[tools]` (>=0.152.0,<1.0.0): CrewAI framework and tools
- `google-genai` (>=1.28.0): Google Gemini API client
- `sentence-transformers` (>=2.2.0): Sentence embeddings
- `transformers` (>=4.36.0): Hugging Face Transformers
- `torch` (>=2.0.0): PyTorch

### Vector Database and Data Processing
- `qdrant-client` (>=1.7.0): Qdrant vector database client
- `numpy` (>=1.24.0): Numerical operations

### Utilities and Configuration
- `python-dotenv` (>=1.0.0): Environment variable management
- `pydantic` (>=2.0.0): Data validation
- `requests` (>=2.31.0): HTTP requests

### Optional/Enhanced Functionality
- `colorama` (>=0.4.6): Colored terminal output
- `rich` (>=13.0.0): Rich console output
- `click` (>=8.0.0): CLI improvements

### Development (dev dependencies)
- `pytest`, `pytest-cov`, `pytest-asyncio`, `pytest-mock`: Testing
- `black`, `isort`, `flake8`, `mypy`, `pre-commit`: Code quality/formatting
- `mkdocs`, `mkdocs-material`: Documentation
- `ipython`, `jupyter`: Development utilities

### Performance (optional)
- `uvloop` (>=0.17.0): Fast event loop (non-Windows)
- `orjson` (>=3.9.0): Fast JSON
- `httpx` (>=0.24.0): Async HTTP client

## External APIs

- **Google Gemini API**: Used via the `google-genai` package for AI/LLM capabilities.
- **Qdrant Vector Database**: Accessed via the `qdrant-client` for vector storage and retrieval.

## Notes
- Some dependencies are optional and only installed for development or performance.