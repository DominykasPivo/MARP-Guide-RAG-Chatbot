# Environment Configuration Guide

## Overview
All services now use environment variables from `.env` file for configuration, making it easy to customize behavior without changing code.

**⚠️ Security Note:** The default configuration uses guest credentials for development. For production, see [SECURITY.md](./SECURITY.md) to secure RabbitMQ, Qdrant, and other services.

## Quick Start

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Add your OpenRouter API key:**
   Edit `.env` and set:
   ```
   OPENROUTER_API_KEY=your_key_here
   ```

3. **Run the services:**
   ```bash
   docker-compose up
   ```

## Environment Variables by Category

### RabbitMQ Configuration
- `RABBITMQ_HOST` - RabbitMQ hostname (default: `rabbitmq`)
- `RABBITMQ_URL` - Full RabbitMQ connection URL
- `RABBITMQ_AMQP_PORT` - AMQP protocol port (default: `5672`)
- `RABBITMQ_MANAGEMENT_PORT` - Management UI port (default: `15672`)
- `RABBITMQ_MAX_RETRIES` - Max connection retry attempts (default: `5`)
- `RABBITMQ_INITIAL_RETRY_DELAY` - Initial retry delay in seconds (default: `1`)
- `RABBITMQ_MAX_RETRY_DELAY` - Max retry delay in seconds (default: `30`)
- `RABBITMQ_CONNECTION_TIMEOUT` - Connection timeout in seconds (default: `30`)

### Qdrant Vector Database
- `QDRANT_HOST` - Qdrant hostname (default: `qdrant`)
- `QDRANT_PORT` - Qdrant HTTP port (default: `6333`)
- `QDRANT_COLLECTION` - Collection name (default: `chunks`)
- `QDRANT_VECTOR_SIZE` - Vector dimensions - must match embedding model (default: `384` for all-MiniLM-L6-v2)

### Embedding & Chunking
- `EMBEDDING_MODEL` - Model for embeddings (default: `all-MiniLM-L6-v2`)
  - `all-MiniLM-L6-v2`: 384 dimensions, fast
  - `all-mpnet-base-v2`: 768 dimensions, more accurate
- `CHUNK_MAX_TOKENS` - Max tokens per chunk (default: `400`)
- `TIKTOKEN_ENCODING` - Token encoding method (default: `cl100k_base`)

### LLM Configuration
- `OPENROUTER_API_KEY` - **Required** - Your OpenRouter API key
- `OPENROUTER_API_URL` - OpenRouter API endpoint
- `LLM_MODEL` - Single model (legacy)
- `LLM_MODELS` - Comma-separated list of models for parallel generation
- `LLM_MAX_TOKENS` - Max tokens in LLM response (default: `2000`)
- `LLM_TEMPERATURE` - Creativity level 0.0-1.0 (default: `0.7`)
- `LLM_TIMEOUT` - LLM API timeout in seconds (default: `60`)

### Retrieval Configuration
- `RETRIEVAL_SERVICE_URL` - Retrieval service URL (default: `http://retrieval:8000`)
- `RETRIEVAL_TOP_K` - Number of chunks to retrieve (default: `5`)
- `RETRIEVAL_MIN_SCORE` - Minimum relevance score (default: `0.0`)

### Service Ports
- `INGESTION_PORT` - External port for ingestion (default: `8001`)
- `EXTRACTION_PORT` - External port for extraction (default: `8002`)
- `INDEXING_PORT` - External port for indexing (default: `8003`)
- `RETRIEVAL_PORT` - External port for retrieval (default: `8004`)
- `CHAT_PORT` - External port for chat (default: `8005`)

### Timeouts & Performance
- `DISCOVERY_TIMEOUT` - Document discovery timeout (default: `10` seconds)
- `DOWNLOAD_TIMEOUT` - Document download timeout (default: `60` seconds)
- `API_TIMEOUT` - General API request timeout (default: `30` seconds)

### Logging
- `LOG_LEVEL` - Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)

### Data Storage
- `DATA_DIR` - Directory for document storage (default: `/data`)
- `EVENT_VERSION` - Event system version (default: `1.0`)

## Service-Specific Usage

### Chat Service
Uses: LLM config, RabbitMQ, retrieval URL, API timeouts, logging

### Retrieval Service
Uses: Qdrant config, embedding model, RabbitMQ, retrieval settings, logging

### Indexing Service
Uses: Qdrant config, embedding model, chunking config, RabbitMQ, logging

### Ingestion Service
Uses: RabbitMQ, data directory, timeouts, logging

### Extraction Service
Uses: RabbitMQ, logging

## Important Notes

### Embedding Model & Vector Size
**CRITICAL:** `QDRANT_VECTOR_SIZE` must match your `EMBEDDING_MODEL`:
- `all-MiniLM-L6-v2` → `QDRANT_VECTOR_SIZE=384`
- `all-mpnet-base-v2` → `QDRANT_VECTOR_SIZE=768`

Mismatched sizes will cause indexing/retrieval errors!

### Free LLM Models
Available free models on OpenRouter:
- `google/gemma-2-9b-it:free`
- `meta-llama/llama-3.2-3b-instruct:free`
- `microsoft/phi-3-mini-128k-instruct:free`
- `mistralai/mistral-7b-instruct:free`
- `openai/gpt-oss-20b:free`

### Development vs Production
- **Development:** Use defaults in `.env.example`
- **Production:** Increase timeouts, adjust retry settings, set appropriate log levels

## Troubleshooting

### Services fail to start
- Check `RABBITMQ_HOST` and `QDRANT_HOST` match your docker-compose service names
- Verify ports aren't already in use

### LLM errors
- Ensure `OPENROUTER_API_KEY` is set
- Check `LLM_TIMEOUT` if requests are timing out
- Verify model names in `LLM_MODELS` are correct

### Vector search issues
- Confirm `QDRANT_VECTOR_SIZE` matches `EMBEDDING_MODEL`
- Check `RETRIEVAL_TOP_K` isn't too large
- Verify Qdrant collection exists and has data

### Slow performance
- Increase `*_TIMEOUT` values
- Reduce `CHUNK_MAX_TOKENS` for faster processing
- Increase `RETRIEVAL_TOP_K` for better context
