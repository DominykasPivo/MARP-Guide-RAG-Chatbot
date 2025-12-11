# Event Catalogue

## Overview
This overview is for the **LZSCC.311 MARP Guide RAG Chatbot** being developed at the **LZSCC.311 Module**. It is designed to help students find accurate answers about university rules and operates as a microservices-based system with an **Event-Driven Architecture (EDA)**. 

Each major step in the RAG pipeline triggers an event (e.g., when a PDF is discovered or chunks are indexed), allowing other services to react without direct calls. This approach ensures decoupling, scalability, and easier debugging. A **correlationId** is used across all events to trace a user query or document throughout the system.

### Overall Flow:
1. Ingestion  2. Extraction  3. Indexing  4. Retrieval  5. Chat

---

## Event Specifications

### `DocumentDiscovered`
**Description:** Triggered when a new MARP PDF is discovered for ingestion.  
**Produced by:** Ingestion Service  
**Consumed by:** Extraction Service  

**Schema:**
```json
{
  "eventType": "DocumentDiscovered",
  "eventId": "string",
  "timestamp": "string",
  "correlationId": "string",
  "source": "ingestion-service",
  "version": "1.0",
  "payload": {
    "documentId": "string",
    "sourceUrl": "string",
    "filePath": "string",
    "discoveredAt": "string"
  }
}
```

**Flow:**
1. **Ingestion Service** monitors directories or URLs for new MARP documents.
2. When a new PDF is detected, the service validates the file and publishes a `DocumentDiscovered` event.
3. **Extraction Service** listens for this event and begins processing.

---

### `DocumentExtracted`
**Description:** Fired after the document text and metadata have been extracted.  
**Produced by:** Extraction Service  
**Consumed by:** Indexing Service  

**Schema:**
```json
{
  "eventType": "DocumentExtracted",
  "eventId": "string",
  "timestamp": "string",
  "correlationId": "string",
  "source": "extraction-service",
  "version": "1.0",
  "payload": {
    "documentId": "string",
    "textContent": "string",
    "fileType": "string",
    "extractedAt": "string",
    "metadata": {
      "title": "string",
      "pageCount": "integer",
      "sourceUrl": "string"
    }
  }
}
```

**Flow:**
1. **Extraction Service** receives `DocumentDiscovered` event with file location.
2. The service extracts text content and metadata from the document.
3. Once extraction completes, it publishes a `DocumentExtracted` event.
4. **Indexing Service** consumes this event to begin chunking and embedding.

---

### `ChunksIndexed`
**Description:** Emitted when text chunks are split and transformed into vector embeddings for indexing and retrieval.  
**Produced by:** Indexing Service  
**Consumed by:** Retrieval Service  

**Schema:**
```json
{
  "eventType": "ChunksIndexed",
  "eventId": "string",
  "timestamp": "string",
  "correlationId": "string",
  "source": "indexing-service",
  "version": "1.0",
  "payload": {
    "documentId": "string",
    "chunkId": "string",
    "chunkIndex": "integer",
    "chunkText": "string",
    "totalChunks": "integer",
    "embeddingModel": "string",
    "metadata": {
      "title": "string",
      "pageCount": "integer",
      "sourceUrl": "string"
    },
    "indexedAt": "string"
  }
}
```

**Flow:**
1. **Indexing Service** receives `DocumentExtracted` event with full text.
2. The service splits the text into chunks and generates embeddings.
3. For each chunk, a `ChunksIndexed` event is published.
4. **Retrieval Service** consumes these events to store chunks in the vector database.

---

### `QueryReceived`
**Description:** Raised when a user submits a question to the chatbot.  
**Produced by:** Chat Service  
**Consumed by:** Chat Service, Retrieval Service  

**Schema:**
```json
{
  "eventType": "QueryReceived",
  "eventId": "string",
  "timestamp": "string",
  "source": "chat-service",
  "version": "1.0",
  "payload": {
    "queryId": "string",
    "userId": "string",
    "queryText": "string"
  }
}
```

**Flow:**
1. **Chat Service** publishes this event for tracking and analytics.
2. **Retrieval Service** may log or monitor the event but does not use it for query processing.

---

### `RetrievalCompleted`
**Description:** Provides metrics and completion notification for retrieval operations, including result count, top score, and latency.  
**Produced by:** Retrieval Service  
**Consumed by:** Chat Service, Retrieval Service  

**Schema:**
```json
{
  "eventType": "RetrievalCompleted",
  "eventId": "string",
  "timestamp": "string",
  "source": "retrieval-service",
  "version": "1.0",
  "payload": {
    "queryId": "string",
    "query": "string",
    "resultsCount": "integer",
    "topScore": "number",
    "latencyMs": "number"
  }
}
```

**Flow:**
1. **Retrieval Service** publishes this event after completing a query.
2. **Chat Service** logs the event for monitoring and analytics.

---

## Event Architecture Notes

### Synchronous Document Pipeline (Blocking Events)
- **DocumentDiscovered** → **DocumentExtracted** → **ChunksIndexed**
- These events drive the core document processing pipeline and are consumed by the next service in the chain.

### Asynchronous Query Flow (Non-Blocking Events)
- **QueryReceived** and **RetrievalCompleted** are fire-and-forget tracking events.
- Actual query processing happens via HTTP POST `/query` endpoint (chat to retrieval).
- Events run in daemon threads and won't block or crash services if RabbitMQ fails.
- Used purely for observability, monitoring, and debugging.
