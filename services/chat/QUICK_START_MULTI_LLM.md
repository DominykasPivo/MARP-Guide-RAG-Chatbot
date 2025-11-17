# Quick Start: Multi-LLM Parallel Comparison

## Configuration

Add to your `docker-compose.yml` or `.env`:

```yaml
services:
  chat:
    environment:
      - OPENROUTER_API_KEY=your_api_key_here
      - LLM_MODELS=anthropic/claude-3.5-sonnet,openai/gpt-4o,google/gemini-pro-1.5
```

## Access the UI

1. Start services:
   ```bash
   docker-compose up -d
   ```

2. Open browser:
   ```
   http://localhost:8000/
   ```

3. Enter your question and see side-by-side LLM comparisons!

## Key Features

✅ **Parallel Processing** - All LLMs query simultaneously  
✅ **Side-by-Side UI** - Beautiful comparison interface  
✅ **Performance Metrics** - See generation time per model  
✅ **Separate Citations** - Each model shows its sources  
✅ **Error Resilient** - One model failure doesn't affect others  

## API Response Format

```json
{
  "query": "Your question here",
  "responses": [
    {
      "model": "anthropic/claude-3.5-sonnet",
      "answer": "Answer text...",
      "citations": [{...}],
      "generation_time": 2.34
    },
    {
      "model": "openai/gpt-4o",
      "answer": "Answer text...",
      "citations": [{...}],
      "generation_time": 1.89
    }
  ]
}
```

## Files Modified

1. ✅ `services/chat/app/models.py` - New response structure
2. ✅ `services/chat/app/llm_rag_helpers.py` - Parallel generation logic
3. ✅ `services/chat/app/app.py` - Updated endpoint
4. ✅ `services/chat/app/static/index.html` - NEW comparison UI

## Test It

```bash
# Via API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is MARP?"}'

# Or just open http://localhost:8000/ in your browser!
```

See `MULTI_LLM_GUIDE.md` for detailed documentation.
