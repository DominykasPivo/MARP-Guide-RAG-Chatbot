# MARP Retrieval Service

The Retrieval Service is a high-performance vector search microservice that powers the Retrieval-Augmented Generation (RAG) capabilities of the MARP Chatbot system. It performs semantic search over indexed MARP document chunks using advanced vector embeddings and the Qdrant vector database.

---

## Overview

The Retrieval Service is a critical component in the MARP RAG pipeline, responsible for finding the most relevant document chunks for user queries. It uses sentence transformers to encode queries into vector embeddings and performs similarity search against a pre-indexed collection of MARP document chunks stored in Qdrant.

### Key Features

- **High-Performance Vector Search:** Sub-100ms query response times using optimized sentence transformers.
- **Event-Driven Architecture:** Consumes `QueryReceived` and `ChunksIndexed` events, publishes `RetrievalCompleted` events.
- **RESTful API:** Provides endpoints for direct query handling.
- **Scalable Architecture:** Horizontal scaling with external vector database (Qdrant).
- **Comprehensive Monitoring:** Health checks, debug endpoints, metrics endpoint, and event-based tracking.
- **Cache Invalidation:** Automatically invalidates cache when new documents are indexed.
- **Production Ready:** Dockerized deployment, robust error handling, and retry mechanisms.

---

## Architecture

### Core Components

- **FastAPI Server:** Handles HTTP requests and responses.
- **Retriever Class:** Encodes queries and performs vector search using Qdrant with cache management.
- **Event Consumers:** 
  - **QueryReceived Consumer:** Tracks user queries for observability (logging only).
  - **ChunksIndexed Consumer:** Tracks indexing metrics and document completion milestones.
- **Cache Invalidation Handler:** Separate RabbitMQ subscription in `retrieval.py` for invalidating cache when documents are indexed.
- **Vector Store Client:** Qdrant client for high-performance similarity search.
- **Metrics Publisher:** Publishes retrieval metrics via `RetrievalCompleted` events.

### Data Flow

```
User Query -> Chat Service -> Retrieval Service API -> Vector Search -> Ranked Results -> Chat Service -> AI Response
                                       |
                                       v
                            RetrievalCompleted Event Published
```

1. User submits a query to the Chat Service.
2. Chat Service calls the Retrieval Service API or publishes a `QueryReceived` event.
3. QueryReceived consumer logs the query for tracking (non-blocking).
4. Retrieval Service encodes the query using a sentence transformer.
5. Vector similarity search is performed against the Qdrant collection.
6. Top-k most relevant chunks are returned with metadata and scores.
7. Retrieval metrics are published via `RetrievalCompleted` events.
8. When new documents are indexed, `ChunksIndexed` events are consumed for metrics tracking.
9. Cache is invalidated after final chunk is indexed to ensure fresh data on next query.

---

## API Endpoints

### 1. **`POST /search`**
Direct vector search endpoint for immediate results.

**Request:**
```json
{
  "query": "What is the appeals process?",
  "top_k": 5
}
```

**Response:**
```json
{
  "query": "What is the appeals process?",
  "results": [
    {
      "text": "The appeals process allows students to...",
      "title": "Academic Appeals Policy",
      "page": 15,
      "url": "https://marp.lancs.ac.uk/appeals",
      "score": 0.87
    }
  ]
}
```

---

### 2. **`POST /query`**
Alternative query endpoint with flexible parameter handling.

**Request:**
```json
{
  "query": "academic regulations",
  "top_k": 3
}
```

**Response:**
```json
{
  "query": "academic regulations",
  "chunks": [
    {
      "text": "Academic regulations govern student conduct...",
      "title": "Student Regulations",
      "page": 5,
      "url": "https://marp.lancs.ac.uk/regulations",
      "score": 0.92
    }
  ]
}
```

---

### 3. **`GET /health`**
Service health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "service": "retrieval"
}
```

---

### 4. **`GET /metrics`**
Exposes indexing metrics for monitoring and observability.

**Response:**
```json
{
  "service": "retrieval",
  "timestamp": "2024-01-15T10:30:00Z",
  "indexing_metrics": {
    "total_chunks_indexed": 1250,
    "total_documents_indexed": 15,
    "last_indexed_at": 1705318200.123
  }
}
```

---

### 5. **`GET /debug/vector-store`**
Debug endpoint to inspect the state of the Qdrant vector store.

**Response:**
```json
{
  "status": "healthy",
  "collection_name": "chunks",
  "qdrant_host": "qdrant",
  "embedding_model": "all-MiniLM-L6-v2",
  "total_points": 1250,
  "sample_points": [...],
  "has_points": true
}
```

---

### 6. **`GET /debug/qdrant-verification`**
Advanced debug endpoint providing detailed collection statistics and sample search results.

**Response:**
```json
{
  "collection_name": "chunks",
  "total_points": 1250,
  "sample_analyzed": 100,
  "statistics": {
    "unique_documents": 15,
    "unique_document_pages": 87,
    "documents": ["Academic Appeals", "Student Regulations", ...],
    "chunks_per_document_page": {...}
  },
  "test_search": {
    "query": "academic regulations",
    "results_returned": 10,
    "sample_results": [...]
  },
  "health": {
    "has_data": true,
    "has_diverse_data": true,
    "has_multiple_chunks": true
  }
}
```

---

## Event Integration

### Consumed Events

#### 1. **`QueryReceived`**
- **Purpose:** Tracks user queries for observability and analytics.
- **Routing Key:** `queryreceived`
- **Consumer:** `consumers.py` - `consume_query_received_events()`
- **Queue:** `retrieval_query_tracking`
- **Action:** Logs query details (queryId, userId, queryText) for tracking purposes only.
- **Note:** This does NOT trigger query processing; HTTP API handles actual retrieval.

**Event Schema:**
```json
{
  "eventType": "QueryReceived",
  "eventId": "uuid",
  "timestamp": "ISO-8601",
  "source": "chat-service",
  "version": "1.0",
  "payload": {
    "queryId": "string",
    "userId": "string",
    "queryText": "string"
  }
}
```

#### 2. **`ChunksIndexed`**
- **Purpose:** Tracks indexing progress and invalidates cache when documents are fully indexed.
- **Routing Key:** `chunks.indexed`
- **Consumers:**
  - **Metrics Consumer:** `consumers.py` - `consume_chunks_indexed_events()` for logging and metrics
  - **Cache Invalidation:** `retrieval.py` - `handle_chunks_indexed()` for cache management
- **Queues:**
  - `retrieval_chunks_indexed_metrics` (metrics tracking)
  - Cache invalidation queue in `retrieval.py`
- **Action:** 
  - Logs chunk indexing progress with document metadata
  - Tracks total chunks and documents indexed
  - Invalidates retriever cache after final chunk is indexed
  - Logs milestone events when documents complete indexing

**Event Schema:**
```json
{
  "eventType": "ChunksIndexed",
  "eventId": "uuid",
  "timestamp": "ISO-8601",
  "correlationId": "uuid",
  "source": "indexing-service",
  "version": "1.0",
  "payload": {
    "documentId": "string",
    "chunkId": "string",
    "chunkIndex": 0,
    "chunkText": "string (truncated to 2000 chars)",
    "totalChunks": 100,
    "embeddingModel": "all-MiniLM-L6-v2",
    "metadata": {
      "title": "string",
      "pageCount": 50,
      "sourceUrl": "string"
    },
    "indexedAt": "ISO-8601"
  }
}
```

**Metrics Tracked:**
- Total chunks indexed across all documents
- Total documents completed (when final chunk is indexed)
- Last indexed timestamp
- Processing time per event
- Document metadata (title, page count, source URL)

---

### Published Events

#### **`RetrievalCompleted`**
- **Purpose:** Publishes query performance metrics and results statistics.
- **Routing Key:** `retrievalcompleted`
- **Publisher:** `retrieval_events.py` - `publish_retrieval_completed_event()`
- **Action:** Fired after every successful query with performance metrics.

**Event Schema:**
```json
{
  "eventType": "RetrievalCompleted",
  "eventId": "uuid",
  "timestamp": "ISO-8601",
  "source": "retrieval-service",
  "version": "1.0",
  "payload": {
    "queryId": "string",
    "query": "string",
    "resultsCount": 5,
    "topScore": 0.87,
    "latencyMs": 45.2
  }
}
```

---

## Configuration

### Environment Variables

| Variable              | Default                          | Description                                   |
|-----------------------|----------------------------------|-----------------------------------------------|
| `QDRANT_HOST`         | `localhost`                     | Qdrant vector database host                  |
| `QDRANT_PORT`         | `6333`                          | Qdrant vector database port                  |
| `QDRANT_COLLECTION`   | `chunks`                        | Qdrant collection name                       |
| `EMBEDDING_MODEL`     | `all-MiniLM-L6-v2`              | Sentence transformer model name              |
| `RABBITMQ_URL`        | `amqp://guest:guest@localhost`  | RabbitMQ connection URL                      |
| `RABBITMQ_HOST`       | `rabbitmq`                      | RabbitMQ host (used as fallback)             |
| `RETRIEVAL_TOP_K`     | `5`                             | Default number of top results to return      |
| `LOG_LEVEL`           | `INFO`                          | Logging level (DEBUG, INFO, WARNING, ERROR)  |

---

## Testing

### 1. **Run Unit Tests:**
```bash
pytest tests/unit/
```

### 2. **Run Integration Tests:**
```bash
pytest tests/integration/
```

### 3. **Test API Endpoints:**

**Search Endpoint:**
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "academic regulations", "top_k": 3}'
```

**Query Endpoint:**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "appeals process", "top_k": 5}'
```

**Metrics Endpoint:**
```bash
curl http://localhost:8000/metrics
```

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Vector Store Debug:**
```bash
curl http://localhost:8000/debug/vector-store
```

---

## Monitoring and Observability

### Health Checks

- HTTP health endpoint at `/health`
- Container health checks via Docker
- Qdrant connection verification

### Metrics and Logging

#### Structured Logging
- JSON-formatted logs with correlation IDs
- Event-specific log tags: `[TRACKING]`, `[METRICS]`, `[MILESTONE]`
- Correlation ID tracking across all operations

#### Metrics Tracked
- **Query Metrics:**
  - Total queries processed
  - Query latency (ms)
  - Results count per query
  - Top relevance scores
  
- **Indexing Metrics:**
  - Total chunks indexed
  - Total documents completed
  - Last indexed timestamp
  - Chunk processing time
  - Document metadata (title, page count, source)

#### Debug Endpoints
- `/debug/vector-store` - Inspect Qdrant collection state
- `/debug/qdrant-verification` - Detailed collection statistics
- `/metrics` - Indexing metrics for monitoring

---

## Cache Management

### Cache Invalidation Strategy

The retrieval service implements intelligent cache invalidation to ensure fresh search results:

1. **Cache Validity Flag:** Each retriever instance maintains a `_cache_valid` flag.
2. **Invalidation Trigger:** When the final chunk of a document is indexed (`chunkIndex == totalChunks - 1`), the cache is invalidated.
3. **Dual Consumer Architecture:**
   - **Metrics Consumer:** Tracks all `ChunksIndexed` events for logging and metrics.
   - **Cache Invalidation Handler:** Separate subscription in `retrieval.py` for cache management.
4. **Next Query Refresh:** The next search query will use fresh data from Qdrant.

**Benefits:**
- Ensures search results reflect newly indexed documents
- Minimal performance impact (invalidation only on document completion)
- Separation of concerns (metrics vs. cache management)

---

## Error Handling

### Robust Error Management

- **Graceful Degradation:** Service continues with cached responses when Qdrant is temporarily unavailable.
- **Event Processing Failures:** Non-critical event failures (metrics, logging) don't block query processing.
- **Retry Logic:** Automatic retries for transient network failures.
- **Comprehensive Logging:** All errors logged with correlation IDs and full stack traces.
- **Fallback Responses:** Clear error messages for client applications.

### Common Error Scenarios

- **Qdrant Connection Failure:** Service continues with cached responses if available; logs errors prominently.
- **Event Publishing Failures:** Non-blocking with background retry mechanisms; warnings logged.
- **Invalid Query Parameters:** Validation errors returned with clear HTTP 400 responses.
- **RabbitMQ Consumer Failures:** Automatic reconnection with exponential backoff; errors logged for monitoring.

---

## Performance Characteristics

### Benchmarks

- **Query Latency:** < 100ms for typical queries (5 results)
- **Throughput:** 100+ queries/second (single instance)
- **Cache Hit Rate:** 85%+ in typical workloads
- **Event Processing:** < 10ms per event (metrics tracking)

### Optimization Strategies

- **CPU-Only Inference:** Optimized for cloud deployment without GPU requirements
- **Connection Pooling:** Reused Qdrant client connections
- **Background Event Publishing:** Non-blocking event publishing
- **Efficient Deduplication:** In-memory deduplication of search results


---

## Troubleshooting

### Common Issues

**Issue:** No search results returned
- **Check:** Verify Qdrant collection has data using `/debug/vector-store`
- **Check:** Ensure indexing service has completed document processing
- **Check:** Review logs for Qdrant connection errors
 ---
