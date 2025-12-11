# Citation Accuracy Testing Guide

## Overview

This guide explains how to verify that the MARP RAG system meets the **≥90% citation accuracy** requirement.

## What is Citation Accuracy?

Citation accuracy measures how often the system retrieves the **correct source documents and page numbers** for a given query.

**Formula:**
```
Accuracy = (Number of Correct Citations / Total Expected Citations) × 100%
```

**MARP Requirement:** ≥90% accuracy

## Testing Approaches

### 1. Integration Testing (Recommended)

**File:** `tests/integration/test_citation_accuracy.py`

This approach tests the entire RAG pipeline with real queries against a ground truth dataset.

**Steps:**

1. **Create Ground Truth Dataset**
   - Select 20-50 representative MARP questions
   - Manually verify the correct source documents and pages
   - Store in `tests/fixtures/citation_ground_truth.json`

   Example:
   ```json
   [
     {
       "query": "What is the MARP compliance process?",
       "expected_citations": [
         {"source": "MARP_Guide_v2.pdf", "page": 15},
         {"source": "MARP_Guide_v2.pdf", "page": 16}
       ]
     }
   ]
   ```

2. **Run Integration Test**
   ```bash
   pytest tests/integration/test_citation_accuracy.py -v
   ```

3. **Review Results**
   - Test will show accuracy percentage
   - Fails if accuracy < 90%
   - Shows precision and recall metrics

### 2. Manual Verification

For quick validation:

1. **Select Test Queries**
   - Choose 10-20 diverse MARP questions
   - Cover different topics (appeals, compliance, documentation, etc.)

2. **Manually Verify**
   - Send each query to the chat endpoint
   - Check if returned citations match actual source locations
   - Record correct vs. incorrect citations

3. **Calculate Accuracy**
   ```
   Accuracy = (Correct Citations / Total Citations) × 100%
   ```

### 3. User Feedback Analysis

Track real-world accuracy:

1. **Add Citation Feedback**
   - Add "Was this citation helpful?" buttons in the UI
   - Track positive/negative feedback per citation

2. **Analyze Periodically**
   - Calculate: `Accuracy = Positive Feedback / Total Feedback × 100%`
   - Target: ≥90% positive feedback

## Metrics Explained

### Accuracy
- **Definition:** Percentage of correct citations retrieved
- **Target:** ≥90%
- **When to use:** Overall system quality measure

### Precision
- **Definition:** Of all retrieved citations, how many are relevant?
- **Formula:** `Relevant Retrieved / Total Retrieved`
- **Target:** ≥80%
- **When to use:** Measure if system retrieves too many irrelevant citations

### Recall
- **Definition:** Of all relevant citations, how many were retrieved?
- **Formula:** `Relevant Retrieved / Total Relevant`
- **Target:** ≥80%
- **When to use:** Measure if system misses important citations

## Citation Matching Rules

A citation is considered **correct** if:

1. **Source Match:** Document name matches (fuzzy match allowed)
   - Example: "MARP_Guide.pdf" matches "MARP Guide v2.pdf"

2. **Page Match:** Page number within ±1 tolerance
   - Example: Expected page 15 → retrieved page 14, 15, or 16 = correct

## Running Tests

### Full Integration Test
```bash
# Start services first
docker-compose up -d

# Run citation accuracy tests
pytest tests/integration/test_citation_accuracy.py -v -s

# With coverage
pytest tests/integration/test_citation_accuracy.py --cov=services --cov-report=term-missing
```

### Quick Unit Test
```bash
# Run unit tests (mocked, doesn't verify real accuracy)
pytest tests/unit/test_chat_service.py::TestMARPChatQuality::test_citation_accuracy_above_90_percent -v
```

## Improving Citation Accuracy

If accuracy falls below 90%:

1. **Improve Embeddings**
   - Use domain-specific embedding models
   - Fine-tune on MARP documents

2. **Optimize Chunking**
   - Adjust chunk size/overlap
   - Use semantic chunking

3. **Refine Retrieval**
   - Tune similarity threshold
   - Increase top_k for reranking
   - Add hybrid search (keyword + semantic)

4. **Enhance Metadata**
   - Extract better document structure
   - Include section headings in chunks
   - Add document type classification

## Continuous Monitoring

Set up automated monitoring:

1. **Weekly Accuracy Tests**
   - Run integration tests on CI/CD
   - Alert if accuracy drops below 90%

2. **Production Monitoring**
   - Log all queries and retrieved citations
   - Sample and manually verify monthly
   - Track accuracy trends over time

## Example Ground Truth Creation

```python
# Script to help create ground truth data
import json

ground_truth = []

questions = [
    "What is the MARP process?",
    "How do I submit an appeal?",
    # ... add more questions
]

for q in questions:
    print(f"\nQuestion: {q}")
    # 1. Send query to your RAG system
    # 2. Review retrieved citations
    # 3. Manually verify correct citations from actual documents
    # 4. Record ground truth

    citations = input("Enter correct citations (source:page,source:page): ")
    # Parse and add to ground_truth

with open('tests/fixtures/citation_ground_truth.json', 'w') as f:
    json.dump(ground_truth, f, indent=2)
```

## Summary

- **Unit tests** (current): Verify code logic, not real accuracy
- **Integration tests** (recommended): Verify real accuracy with ground truth
- **Manual verification**: Quick validation for small datasets
- **User feedback**: Continuous monitoring in production

**Next Steps:**
1. Create ground truth dataset with 20+ MARP questions
2. Run integration tests
3. Achieve ≥90% accuracy target
4. Set up continuous monitoring
