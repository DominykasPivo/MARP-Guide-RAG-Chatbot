# Multi-LLM Parallel Answer Generation - Implementation Guide

## Overview

The chat service now supports **parallel answer generation from multiple LLMs** with a **side-by-side UI comparison**. This allows users to compare responses from different models (e.g., Claude, GPT-4, Gemini) simultaneously.

## What Changed

### 1. **Models (`models.py`)**
- Added `LLMResponse` class to represent individual model responses
- Modified `ChatResponse` to return multiple responses instead of a single answer
- Each response includes: model name, answer, citations, and generation time

### 2. **LLM Helpers (`llm_rag_helpers.py`)**
- Added `generate_answers_parallel()` function that calls multiple LLMs concurrently
- Uses `asyncio.gather()` for parallel execution
- Tracks generation time for each model
- Handles errors gracefully per model

### 3. **Main App (`app.py`)**
- Added `LLM_MODELS` environment variable (comma-separated list of models)
- Modified `/chat` endpoint to return multiple responses
- Added static file serving for the UI
- Added root `/` endpoint to serve the comparison interface

### 4. **UI (`static/index.html`)**
- Beautiful, responsive interface for side-by-side comparison
- Shows all model responses in a grid layout
- Displays generation time for each model
- Shows citations per model
- Gradient design with smooth animations

## Configuration

### Environment Variables

Add/modify in your `.env` or `docker-compose.yml`:

```bash
# Comma-separated list of LLM models to use
LLM_MODELS=anthropic/claude-3.5-sonnet,openai/gpt-4o,google/gemini-pro-1.5

# Your OpenRouter API key (required)
OPENROUTER_API_KEY=your_api_key_here
```

### Default Models

If `LLM_MODELS` is not set, defaults to:
- `anthropic/claude-3.5-sonnet`
- `openai/gpt-4o`
- `google/gemini-pro-1.5`

You can customize this to use any models supported by OpenRouter.

## Usage

### Option 1: Web UI (Recommended)

1. Start the chat service:
   ```bash
   docker-compose up chat
   ```

2. Open your browser to: `http://localhost:8000/`

3. Enter your question and click "Search"

4. View side-by-side responses from all configured models

### Option 2: API Endpoint

**Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the minimum GPA required for MARP?"}'
```

**Response:**
```json
{
  "query": "What is the minimum GPA required for MARP?",
  "responses": [
    {
      "model": "anthropic/claude-3.5-sonnet",
      "answer": "Based on the MARP regulations...",
      "citations": [
        {
          "title": "General Regulations",
          "page": 15,
          "url": "https://..."
        }
      ],
      "generation_time": 2.34
    },
    {
      "model": "openai/gpt-4o",
      "answer": "According to the documents...",
      "citations": [...],
      "generation_time": 1.89
    },
    {
      "model": "google/gemini-pro-1.5",
      "answer": "The MARP guide states...",
      "citations": [...],
      "generation_time": 2.15
    }
  ]
}
```

## Benefits

### 1. **Model Comparison**
- Compare different LLM responses side-by-side
- Evaluate which model provides better answers
- Understand model strengths and weaknesses

### 2. **Parallel Execution**
- All models are queried simultaneously (not sequentially)
- Total time ≈ slowest model (not sum of all models)
- Efficient use of async/await

### 3. **Performance Tracking**
- Each response shows generation time
- Identify faster models
- Monitor API performance

### 4. **Error Handling**
- If one model fails, others still return results
- Graceful degradation
- Clear error messages per model

## Architecture

```
User Query
    ↓
Chat Service (/chat endpoint)
    ↓
Retrieval Service (get relevant chunks)
    ↓
Parallel LLM Calls (asyncio.gather)
    ├─→ Model 1 (Claude)
    ├─→ Model 2 (GPT-4)
    └─→ Model 3 (Gemini)
    ↓
Combine Responses
    ↓
Return to User (JSON or UI)
```

## Customization

### Add More Models

Edit your environment variable:
```bash
LLM_MODELS=anthropic/claude-3.5-sonnet,openai/gpt-4o,openai/gpt-4-turbo,google/gemini-pro-1.5,meta-llama/llama-3-70b
```

### Use Only One Model

Set to a single model to revert to original behavior:
```bash
LLM_MODELS=anthropic/claude-3.5-sonnet
```

### Modify UI Styling

Edit `services/chat/app/static/index.html`:
- Change colors in the `<style>` section
- Modify grid layout (currently auto-fit with min 400px)
- Add additional features (export, copy, compare metrics)

## Performance Considerations

1. **API Costs**: Running multiple models increases API costs proportionally
2. **Rate Limits**: Ensure your OpenRouter account can handle parallel requests
3. **Timeout**: Default timeout is 60s per model (configurable in `llm_rag_helpers.py`)
4. **Memory**: Each model response is held in memory - consider for large responses

## Troubleshooting

### Models Not Responding
- Check `OPENROUTER_API_KEY` is set correctly
- Verify model names are correct (use OpenRouter model IDs)
- Check logs for API errors

### UI Not Loading
- Ensure `static/index.html` exists
- Check file permissions
- Verify FastAPI is serving static files

### Slow Response Times
- Reduce number of models
- Check network latency to OpenRouter
- Consider caching results for common queries

## Future Enhancements

Potential improvements:
- Model voting/ranking system
- Response quality scoring
- A/B testing framework
- Model selection in UI
- Response caching
- Streaming responses
- Cost tracking per model
- Custom model configurations per query

## Testing

Test with a simple query:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello, how are you?"}'
```

Expected: Multiple responses from configured models with different generation times.
