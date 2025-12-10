# Testing Guide: Multi-LLM Parallel Comparison

## Prerequisites

1. **Docker & Docker Compose** installed
2. **OpenRouter API Key** (get from https://openrouter.ai/)
3. **Services running** (chat, retrieval, qdrant, etc.)

## Step 1: Configure Environment

Edit `docker-compose.yml` or create `.env`:

```yaml
# In docker-compose.yml under chat service
environment:
  - OPENROUTER_API_KEY=your_actual_key_here
  - LLM_MODELS=anthropic/claude-3.5-sonnet,openai/gpt-4o,google/gemini-pro-1.5
```

Or create `.env` file:
```bash
OPENROUTER_API_KEY=your_actual_key_here
LLM_MODELS=anthropic/claude-3.5-sonnet,openai/gpt-4o,google/gemini-pro-1.5
```

## Step 2: Start Services

```bash
# Start all services
docker-compose up -d

# Or rebuild chat service if needed
docker-compose up -d --build chat

# Check logs
docker-compose logs -f chat
```

## Step 3: Test Health Endpoint

```bash
curl http://localhost:8005/health
```

Expected output:
```json
{"status": "healthy"}
```

## Step 4: Test API Endpoint

### Basic Test
```bash
curl -X POST http://localhost:8005/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is MARP?"}'
```

### Expected Response Structure
```json
{
  "query": "What is MARP?",
  "responses": [
    {
      "model": "anthropic/claude-3.5-sonnet",
      "answer": "...",
      "citations": [...],
      "generation_time": 2.34
    },
    {
      "model": "openai/gpt-4o",
      "answer": "...",
      "citations": [...],
      "generation_time": 1.89
    },
    {
      "model": "google/gemini-pro-1.5",
      "answer": "...",
      "citations": [...],
      "generation_time": 2.15
    }
  ]
}
```

### With Pretty Print (jq)
```bash
curl -X POST http://localhost:8005/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is MARP?"}' | jq
```

## Step 5: Test Web UI

1. Open browser: http://localhost:8005/

2. You should see the beautiful comparison UI

3. Enter a question: "What is the minimum GPA required for MARP?"

4. Click "Search"

5. Observe:
   - ✅ All models respond in parallel
   - ✅ Responses appear in grid layout
   - ✅ Each shows generation time
   - ✅ Citations display correctly

## Step 6: Test Different Scenarios

### Test 1: Single Model (Backward Compatibility)
```bash
# Modify docker-compose.yml
LLM_MODELS=anthropic/claude-3.5-sonnet

# Restart
docker-compose restart chat

# Test - should return 1 response
curl -X POST http://localhost:8005/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query"}'
```

### Test 2: Two Models
```bash
LLM_MODELS=openai/gpt-4o,google/gemini-pro-1.5

docker-compose restart chat
# Test via UI or curl
```

### Test 3: Many Models (if you have high rate limits)
```bash
LLM_MODELS=anthropic/claude-3.5-sonnet,openai/gpt-4o,openai/gpt-4-turbo,google/gemini-pro-1.5,meta-llama/llama-3-70b

docker-compose restart chat
# Test via UI or curl
```

### Test 4: Free Models (Lower Cost Testing)
```bash
LLM_MODELS=google/gemma-3-4b-it:free,meta-llama/llama-3-8b-instruct:free,microsoft/phi-3-mini-128k-instruct:free

docker-compose restart chat
# Test via UI or curl
```

## Step 7: Performance Testing

### Measure Response Time
```bash
time curl -X POST http://localhost:8005/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is MARP?"}'
```

### Compare Sequential vs Parallel

**Parallel (Current):**
- Time = slowest model
- Example: ~2-3 seconds for 3 models

**Sequential (Theoretical):**
- Time = sum of all models
- Example: ~6-9 seconds for 3 models

## Step 8: Error Testing

### Test Invalid API Key
```bash
# Set invalid key in docker-compose.yml
OPENROUTER_API_KEY=invalid_key

docker-compose restart chat

# Test - should return error messages
curl -X POST http://localhost:8005/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Test"}'
```

### Test Invalid Model Name
```bash
LLM_MODELS=invalid/model-name,openai/gpt-4o

docker-compose restart chat

# Test - one model fails, other succeeds
curl -X POST http://localhost:8005/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Test"}'
```

### Test No Chunks Retrieved
```bash
# Query something not in your documents
curl -X POST http://localhost:8005/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is quantum physics?"}'
```

Expected: "I couldn't find any relevant information..."

## Step 9: Load Testing (Optional)

### Simple Load Test with curl
```bash
# Run 10 concurrent requests
for i in {1..10}; do
  curl -X POST http://localhost:8005/chat \
    -H "Content-Type: application/json" \
    -d '{"query": "Test query '$i'"}' &
done
wait
```

### Using Apache Bench
```bash
# 100 requests, 10 concurrent
ab -n 100 -c 10 -p post.json -T application/json http://localhost:8005/chat

# post.json contains:
{"query": "What is MARP?"}
```

## Step 10: Verify Logs

```bash
# Check chat service logs
docker-compose logs -f chat

# Look for:
# ✅ "Generating answers from 3 models in parallel"
# ✅ "Model <name> completed in X.XXs"
# ✅ "Generated 3 responses from different models"
```

## Common Issues & Solutions

### Issue 1: "Import httpx could not be resolved"
**Solution:** This is just a linting warning. The Docker container has the dependency.

### Issue 2: "Module 'models' has no attribute 'LLMResponse'"
**Solution:** Restart the service to reload the new models:
```bash
docker-compose restart chat
```

### Issue 3: UI not loading
**Solution:** Check static files exist:
```bash
ls services/chat/app/static/index.html
```

### Issue 4: Slow responses
**Possible causes:**
- API rate limits
- Network latency
- Large context (too many chunks)

**Solutions:**
- Use fewer models
- Reduce chunk count in retrieval
- Check OpenRouter status

### Issue 5: API errors
**Check:**
1. API key is valid
2. Model names are correct (use OpenRouter model IDs)
3. Account has credits
4. Rate limits not exceeded

## Success Criteria

✅ Health endpoint returns 200
✅ UI loads at localhost:8005
✅ Chat endpoint returns multiple responses
✅ Each response has model, answer, citations, generation_time
✅ Total time ≈ slowest model (not sum of all)
✅ Citations display correctly
✅ Generation times are reasonable (1-5s per model)
✅ Logs show parallel execution
✅ Error handling works (one model fails, others succeed)

## Next Steps After Testing

1. **Customize Models:** Choose models that work best for your use case
2. **Optimize Prompts:** Tune RAG_PROMPT_TEMPLATE for better answers
3. **Add Features:** Voting, ranking, model selection in UI
4. **Monitor Costs:** Track API usage per model
5. **User Feedback:** Let users rate which model gave best answer

## Need Help?

Check documentation:
- `MULTI_LLM_GUIDE.md` - Detailed guide
- `QUICK_START_MULTI_LLM.md` - Quick reference
- `API_BEFORE_AFTER.md` - API changes
- `ARCHITECTURE_DIAGRAM.md` - System design

Or check logs:
```bash
docker-compose logs chat
docker-compose logs retrieval
```
