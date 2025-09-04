# Support Bot - UV Workflow Guide

This guide shows you how to use the support bot with the modern UV package manager and clean command structure.

## Quick Start

All commands now use the clean `uv run <command>` format instead of cumbersome `.venv/bin/uv` commands.

### Available Commands

#### Main Bot Commands
```bash
# Run the support bot (main interface)
uv run support-bot

# Training mode (if applicable)
uv run support-bot-train

# Replay previous sessions
uv run support-bot-replay

# Test the bot
uv run support-bot-test
```

#### Database Management
```bash
# Populate Qdrant with incident data using Sentence Transformers
uv run populate-qdrant

# Populate with Gemini embeddings (higher quality, requires API key)
uv run populate-qdrant --gemini

# Recreate the collection completely
uv run populate-qdrant --gemini --recreate

# Use custom collection name
uv run populate-qdrant --collection custom_data

# Clean up collections
uv run cleanup-qdrant --collections incident_data

# Clean all collections (with preview)
uv run cleanup-qdrant --all --dry-run

# Actually clean all collections
uv run cleanup-qdrant --all
```

#### Testing and Development
```bash
# Test embedding implementations
uv run test-embeddings

# Test Gemini API connectivity
uv run test-gemini-api
```

## Environment Setup

1. **Install UV** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup the project**:
   ```bash
   git clone <repository>
   cd bot
   uv sync  # Install all dependencies
   ```

3. **Environment Configuration**:
   Create a `.env` file:
   ```env
   # Qdrant Configuration
   QDRANT_URL=https://your-cluster-url.qdrant.io:6333
   QDRANT_API_KEY=your-api-key-here

   # Gemini Configuration (optional, for better embeddings)
   GOOGLE_API_KEY=your-gemini-api-key-here
   # OR
   GEMINI_API_KEY=your-gemini-api-key-here
   ```

## Usage Examples

### Basic Usage
```bash
# Start the support bot
uv run support-bot
# Then enter your query when prompted, e.g., "payment timeout issues"
```

### Database Setup (First Time)
```bash
# Option 1: Use Sentence Transformers (faster, local)
uv run populate-qdrant

# Option 2: Use Gemini embeddings (better quality, requires API key)
uv run populate-qdrant --gemini --recreate
```

### Testing Your Setup
```bash
# Test API connectivity
uv run test-gemini-api

# Test and compare embedding models
uv run test-embeddings

# Clean up test data
uv run cleanup-qdrant --dry-run  # Preview what will be deleted
uv run cleanup-qdrant --all      # Actually clean up
```

## Project Structure

The project now follows proper Python packaging standards:

```
bot/
├── pyproject.toml              # Central configuration with dependencies
├── src/support_bot/            # Main package
│   ├── main.py                 # Bot entry point
│   ├── agents.py               # CrewAI agents
│   ├── crew.py                 # Main crew coordination
│   ├── tasks.py                # Task definitions
│   ├── scripts/                # Utility scripts (new package)
│   │   ├── populate_qdrant.py  # Database population
│   │   ├── cleanup_qdrant.py   # Database cleanup
│   │   ├── test_embeddings.py  # Embedding tests
│   │   └── test_gemini_api.py  # API tests
│   ├── tools/                  # Custom tools
│   └── utils/                  # Utilities
└── data/                       # Incident data
```

## Key Improvements

1. **Clean Commands**: No more `.venv/bin/uv` - just `uv run command`
2. **Proper Package Structure**: Scripts are now proper Python packages
3. **Comprehensive Dependencies**: All dependencies managed in `pyproject.toml`
4. **Enhanced Scripts**: Better argument parsing, help messages, and error handling
5. **Fallback Support**: Gemini → Sentence Transformers → Simple Hash embeddings

## Embedding Models

The bot supports multiple embedding models with automatic fallback:

1. **Gemini Embeddings** (3072 dimensions)
   - Highest quality semantic search
   - Requires Google API key
   - Best for production

2. **Sentence Transformers** (384 dimensions)
   - Fast, local processing
   - Good quality, no API required
   - Great for development

3. **Simple Hash** (configurable dimensions)
   - Deterministic fallback
   - Used when other models fail
   - Testing purposes only

## Troubleshooting

### Common Issues

1. **"Missing google-generativeai package"**
   ```bash
   uv sync  # Reinstall dependencies
   ```

2. **"API connection failed"**
   - Check your API key in `.env`
   - Verify API quotas at Google Cloud Console
   - Test with: `uv run test-gemini-api`

3. **"Qdrant connection failed"**
   - Check `QDRANT_URL` and `QDRANT_API_KEY` in `.env`
   - Verify cluster is running

4. **Virtual environment warnings**
   - These are harmless warnings about environment detection
   - The commands still work correctly

### Getting Help

Each command has built-in help:
```bash
uv run populate-qdrant --help
uv run cleanup-qdrant --help
uv run test-embeddings --help
uv run test-gemini-api --help
```

## Performance Tips

1. **For Development**: Use Sentence Transformers
   ```bash
   uv run populate-qdrant  # No --gemini flag
   ```

2. **For Production**: Use Gemini embeddings
   ```bash
   uv run populate-qdrant --gemini
   ```

3. **For Testing**: Use dry-run modes
   ```bash
   uv run cleanup-qdrant --all --dry-run
   ```

## Next Steps

1. Run `uv run test-gemini-api` to verify your setup
2. Populate your database with `uv run populate-qdrant --gemini`
3. Start analyzing incidents with `uv run support-bot`
4. Monitor performance with `uv run test-embeddings`

The bot will now provide comprehensive incident analysis based on historical data from your Qdrant vector database!
