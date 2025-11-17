# API Response Comparison: Before vs After

## Before (Single LLM)

### Request
```bash
POST /chat
{
  "query": "What is the minimum GPA required?"
}
```

### Response
```json
{
  "answer": "Based on the MARP regulations...",
  "citations": [
    {
      "title": "General Regulations",
      "page": 15,
      "url": "https://example.com/doc.pdf"
    }
  ]
}
```

---

## After (Multiple LLMs in Parallel)

### Request (Same)
```bash
POST /chat
{
  "query": "What is the minimum GPA required?"
}
```

### Response (Enhanced)
```json
{
  "query": "What is the minimum GPA required?",
  "responses": [
    {
      "model": "anthropic/claude-3.5-sonnet",
      "answer": "According to the MARP General Regulations, students must maintain a minimum weighted average of 40% to be eligible for awards. This requirement is clearly stated in Section 4.2 of the regulations.",
      "citations": [
        {
          "title": "General Regulations",
          "page": 15,
          "url": "https://example.com/doc.pdf"
        }
      ],
      "generation_time": 2.34
    },
    {
      "model": "openai/gpt-4o",
      "answer": "The MARP guidelines specify that a minimum 40% weighted average is required for award eligibility. Students falling below this threshold may face academic consequences.",
      "citations": [
        {
          "title": "General Regulations",
          "page": 15,
          "url": "https://example.com/doc.pdf"
        }
      ],
      "generation_time": 1.89
    },
    {
      "model": "google/gemini-pro-1.5",
      "answer": "Based on the provided context, the minimum GPA requirement for MARP is 40% weighted average. This is a fundamental requirement outlined in the academic regulations.",
      "citations": [
        {
          "title": "General Regulations",
          "page": 15,
          "url": "https://example.com/doc.pdf"
        }
      ],
      "generation_time": 2.15
    }
  ]
}
```

---

## Key Differences

| Aspect | Before | After |
|--------|--------|-------|
| **Structure** | Single answer object | Array of responses |
| **Models** | 1 model | Multiple models (configurable) |
| **Comparison** | Not possible | Side-by-side comparison |
| **Performance** | Single API call time | Parallel execution (fastest of all) |
| **Metadata** | None | Model name + generation time |
| **Redundancy** | Single point of failure | Resilient (one fails, others work) |

---

## Benefits for Users

1. **Compare Quality**: See how different models interpret the same query
2. **Verify Consistency**: Check if all models agree on the answer
3. **Performance Metrics**: Know which model is fastest
4. **Better Trust**: Multiple sources increase confidence
5. **Model Selection**: Users can prefer responses from specific models

---

## Migration Notes

### Backward Compatibility
If you need the old format, set `LLM_MODELS` to a single model:
```yaml
LLM_MODELS=anthropic/claude-3.5-sonnet
```

The response will still use the new format but with only one model in the array.

### Frontend Updates
If you have existing frontend code consuming the `/chat` endpoint:

**Old Code:**
```javascript
const response = await fetch('/chat', {...});
const data = await response.json();
console.log(data.answer);  // Direct access
console.log(data.citations);
```

**New Code:**
```javascript
const response = await fetch('/chat', {...});
const data = await response.json();
console.log(data.query);  // Original query
data.responses.forEach(r => {
  console.log(r.model);  // Model name
  console.log(r.answer);  // Answer
  console.log(r.citations);  // Citations
  console.log(r.generation_time);  // Performance
});
```

Or to get the first model's response (similar to old behavior):
```javascript
const firstResponse = data.responses[0];
console.log(firstResponse.answer);
console.log(firstResponse.citations);
```
