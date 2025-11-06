# Event Catalogue

## Overview
This Overview is for the **LZSCC.311 MARP Guide RAG Chatbot** we're building at the **LZSCC.311 Module**. it's supposed to help students find accurate answers about University rules and everything has to run as microservices with **Event-Driven Architecture (EDA).**  
each big step in the RAG pipeline triggers an event | like when a PDF is found, or when chunks get indexed and other services can react without being directly called. that way everything's decoupled, scalable, and easier to debug. we're also encouraged to use **correlation_id** across all events so we can trace a user query or document all the way through the system.  
overall flow:  
 ingestion -> extraction -> indexing -> retrieval -> chat  

## Event Specifications

### `DocumentDiscovered`
**Description:** Triggered when a new MARP PDF is found for ingestion.  
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
    "title": "string",
    "pageCount": "integer",
    "sourceUrl": "string",
    "filePath": "string",
    "discoveredAt": "string"
  }
}
```

**Example Payload:**
```json
{
  "eventType": "DocumentDiscovered",
  "eventId": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2025-11-04T10:00:00Z",
  "correlationId": "corr_abc123",
  "source": "ingestion-service",
  "version": "1.0",
  "payload": {
    "documentId": "marp_2025_v1",
    "title": "Manual of Academic Regulations and Procedures 2025",
    "pageCount": 124,
    "sourceUrl": "https://www.lancaster.ac.uk/.../marp-2025.pdf",
    "filePath": "/data/marp-2025.pdf",
    "discoveredAt": "2025-11-04T09:59:30Z"
  }
}
```
**Flow:**
1. **Ingestion Service** monitors configured directories or URLs for new MARP documents
2. When a new PDF is detected, the service validates the file and extracts basic metadata
3. The service publishes a `DocumentDiscovered` event to the event broker (RabbitMQ)
4. **Extraction Service** listens for this event and begins processing

**Publishers:** Ingestion Service - responsible for scanning and detecting new documents in the system

**Consumers:** Extraction Service - picks up the event to begin text extraction and processing

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
    "extractedAt": "string",
    "metadata": {
      "title": "string",
      "pageCount": "integer",
      "sourceUrl": "string"
    }
  }
}
```

**Example Payload:**
```json
{
  "eventType": "DocumentExtracted",
  "eventId": "123e4567-e89b-12d3-a456-426614174001",
  "timestamp": "2025-11-04T10:05:00Z",
  "correlationId": "corr_abc123",
  "source": "extraction-service",
  "version": "1.0",
  "payload": {
    "documentId": "marp_2025_v1",
    "textContent": "This document outlines the academic regulations...",
    "extractedAt": "2025-11-04T10:04:50Z",
    "metadata": {
      "title": "Manual of Academic Regulations and Procedures 2025",
      "pageCount": 124,
      "sourceUrl": "https://www.lancaster.ac.uk/.../marp-2025.pdf"
    }
  }
}
```

**Detailed Explanation:**

**Flow:**
1. **Extraction Service** receives `DocumentDiscovered` event with file location
2. Service uses PDF parsing libraries to extract full text content from the document
3. Metadata such as title, pageCount, and sourceUrl is collected under `payload.metadata`
4. Once extraction completes, publishes `DocumentExtracted` with `textContent`, `extractedAt`, and `metadata`
5. **Indexing Service** receives the event and begins chunking and embedding process

**Publishers:** Extraction Service - handles all PDF parsing and text extraction logic

**Consumers:** Indexing Service - receives extracted text to split into chunks and generate embedding
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
    "embeddingVector": [0.1, -0.2, 0.3],
    "indexedAt": "string"
  }
}
```

**Example Payload:**
```json
{
  "eventType": "ChunksIndexed",
  "eventId": "123e4567-e89b-12d3-a456-426614174002",
  "timestamp": "2025-11-04T10:10:00Z",
  "correlationId": "corr_abc123",
  "source": "indexing-service",
  "version": "1.0",
  "payload": {
    "documentId": "marp_2025_v1",
    "chunkId": "chunk_42",
    "chunkIndex": 42,
    "chunkText": "Students must....",
    "totalChunks": 210,
    "embeddingVector": [0.23, -0.45, 0.67],
    "indexedAt": "2025-11-04T10:09:55Z"
  }
}
```

**Detailed Explanation:**

**Flow:**
1. **Indexing Service** receives `DocumentExtracted` event with full text
2. Service splits text into overlapping chunks
3. Each chunk is processed through an embedding model 
4. For EACH chunk, a separate `ChunksIndexed` event is published
5. **Retrieval Service** stores each chunk and its embedding vector in a vector database (Pinecone, Weaviate, etc.)

**Publishers:** Indexing Service - manages text chunking strategy and embedding generation

**Consumers:** Retrieval Service - stores chunks with embeddings in vector database for semantic search

---

### `QueryReceived`
**Description:** Raised when a user submits a question to the chatbot.  
**Produced by:** Chat Service  
**Consumed by:** Retrieval Service  

**Schema:**
```json
{
  "eventType": "QueryReceived",
  "eventId": "string",
  "timestamp": "string",
  "correlationId": "string",
  "source": "chat-service",
  "version": "1.0",
  "payload": {
    "queryId": "string",
    "userId": "string",
    "queryText": "string"
  }
}
```

**Example Payload:**
```json
{
  "eventType": "QueryReceived",
  "eventId": "123e4567-e89b-12d3-a456-426614174003",
  "timestamp": "2025-11-04T11:00:00Z",
  "correlationId": "corr_def456",
  "source": "chat-service",
  "version": "1.0",
  "payload": {
    "queryId": "q_789",
    "userId": "user_anon_123",
    "queryText": ".......?"
  }
}
```

---

### `ChunksRetrieved`
**Description:** Generated when the retrieval system fetches the most relevant chunks for a query.  
**Produced by:** Retrieval Service  
**Consumed by:** Chat Service  

**Schema:**
```json
{
  "eventType": "ChunksRetrieved",
  "eventId": "string",
  "timestamp": "string",
  "correlationId": "string",
  "source": "retrieval-service",
  "version": "1.0",
  "payload": {
    "queryId": "string",
    "retrievedChunks": [
      {
        "chunkId": "string",
        "documentId": "string",
        "relevanceScore": "number"
      }
    ],
    "retrievalModel": "string"
  }
}
```

**Example Payload:**
```json
{
  "eventType": "ChunksRetrieved",
  "source": "retrieval-service",
  "payload": {
    "queryId": "string",
    "retrievedChunks": [
      {
        "chunkId": "string",
        "documentId": "string",
        "text": "string",              // ← ADD THIS
        "title": "string",            // ← ADD THIS
        "page": "number",             // ← ADD THIS
        "url": "string",              // ← ADD THIS
        "relevanceScore": "number"
      }
    ],
    "retrievalModel": "string"
  }
}
```

---

### `AnswerGenerated`
**Description:** Produced when the chatbot generates an answer from retrieved chunks using the LLM.  
**Produced by:** Chat Service  
**Consumed by:** API Gateway 

**Schema:**
```json
{
  "eventType": "AnswerGenerated",
  "eventId": "string",
  "timestamp": "string",
  "correlationId": "string",
  "source": "chat-service",
  "version": "1.0",
  "payload": {
    "queryId": "string",
    "answerText": "string",
    "citations": [
      {
        "documentId": "string",
        "chunkId": "string",
        "sourcePage": "integer"
      }
    ],
    "confidence": "number",
    "generatedAt": "string"
  }
}
```

**Example Payload:**
```json
{
  "eventType": "AnswerGenerated",
  "eventId": "123e4567-e89b-12d3-a456-426614174005",
  "timestamp": "2025-11-04T11:00:10Z",
  "correlationId": "corr_def456",
  "source": "chat-service",
  "version": "1.0",
  "payload": {
    "queryId": "q_789",
    "answerText": ".....",
    "citations": [
      {
        "documentId": "marp_2025_v1",
        "chunkId": "chunk_42",
        "sourcePage": 34
      }
    ],
    "confidence": 0.95,
    "generatedAt": "2025-11-04T11:00:09Z"
  }
}
```
