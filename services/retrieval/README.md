# MARP Retrieval Service

The Retrieval Service is a high-performance vector search microservice that powers the Retrieval-Augmented Generation (RAG) capabilities of the MARP Chatbot system. It performs semantic search over indexed MARP document chunks using advanced vector embeddings and the Qdrant vector database.

---

## Overview

The Retrieval Service is a critical component in the MARP RAG pipeline, responsible for finding the most relevant document chunks for user queries. It uses sentence transformers to encode queries into vector embeddings and performs similarity search against a pre-indexed collection of MARP document chunks stored in Qdrant.

### Key Features

- **High-Performance Vector Search:** Sub-100ms query response times using optimized sentence transformers.
- **Event-Driven Architecture:** Consumes `QueryReceived` and `ChunksIndexed` events and publishes `RetrievalCompleted` events.
- **RESTful API:** Provides endpoints for direct and event-driven query handling.
- **Scalable Architecture:** Horizontal scaling with external vector database (Qdrant).
- **Comprehensive Monitoring:** Health checks, debug endpoints, and event-based metrics.
- **Production Ready:** Dockerized deployment, robust error handling, and retry mechanisms.

---

## Architecture

### Core Components

- **FastAPI Server:** Handles HTTP requests and responses.
- **Retriever Class:** Encodes queries and performs vector search using Qdrant.
- **Event Consumer:** RabbitMQ integration for consuming query and indexing events.
- **Vector Store Client:** Qdrant client for high-performance similarity search.
- **Metrics Publisher:** Publishes retrieval metrics for observability.

### Data Flow

```
User Query → Chat Service → Retrieval Service API/Event → Vector Search → Ranked Results → Chat Service → AI Response
```

1. User submits a query to the Chat Service.
2. Chat Service calls the Retrieval Service API or publishes a `QueryReceived` event.
3. Retrieval Service encodes the query using a sentence transformer.
4. Vector similarity search is performed against the Qdrant collection.
5. Top-k most relevant chunks are returned with metadata and scores.
6. Retrieval metrics are published via `RetrievalCompleted` events.

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

### 4. **`GET /debug/vector-store`**
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

## Event Integration

### Consumed Events

- **`QueryReceived`:** Tracks user queries for observability.
- **`ChunksIndexed`:** Invalidates cache when new document chunks are indexed.

### Published Events

- **`RetrievalCompleted`:** Publishes metrics and query statistics for monitoring.

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
| `RETRIEVAL_TOP_K`     | `5`                             | Default number of top results to return      |

---

### Testing

1. **Run Unit Tests:**
   ```bash
   pytest tests/unit/
   ```

2. **Run Integration Tests:**
   ```bash
   pytest tests/integration/
   ```

3. **Test API Endpoints:**
   ```bash
   curl -X POST "http://localhost:8000/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "academic regulations", "top_k": 3}'
   ```

---

## Monitoring and Observability

### Health Checks

- HTTP health endpoint at `/health`
- Container health checks via Docker

### Metrics and Logging

- Structured JSON logging with correlation IDs
- Event publishing for query metrics and performance data
- Debug endpoints for development and troubleshooting

---

## Error Handling

### Robust Error Management

- Graceful degradation when Qdrant is unavailable.
- Retry logic for transient network failures.
- Comprehensive error logging with correlation IDs.
- Fallback responses for degraded service states.

### Common Error Scenarios

- **Qdrant Connection Failure:** Service continues with cached responses if available.
- **Event Publishing Failures:** Non-blocking with retry mechanisms.
- **Invalid Query Parameters:** Clear error messages with validation details.

---
