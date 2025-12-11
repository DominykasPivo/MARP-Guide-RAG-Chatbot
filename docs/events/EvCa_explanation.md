# Event Catalog Explanations

This file provides detailed explanations for each event in the EvCA.json catalog, including what services publish and consume them, their purpose, usage in code, and why they are used.

## DocumentDiscovered Event
- **Published by:** Ingestion Service
- **Consumed by:** Extraction Service
- **Purpose:** Triggers the document processing pipeline when a new MARP PDF is uploaded. Notifies extraction service to begin text extraction.
- **Usage in Code:**
  - Published: services/ingestion/app/events.py via publish_event()
  - Consumed: services/extraction/app/extractor.py via EventConsumer.subscribe()
- **Why Used:** Enables asynchronous decoupling between ingestion and extraction services in the document pipeline, allowing for scalable processing without blocking the user.

## DocumentExtracted Event
- **Published by:** Extraction Service
- **Consumed by:** Indexing Service
- **Purpose:** Notifies that PDF text extraction is complete and provides the extracted content for chunking and embedding.
- **Usage in Code:**
  - Published: services/extraction/app/extractor.py via EventConsumer.publish()
  - Consumed: services/indexing/app/rabbitmq.py via EventConsumer.subscribe()
- **Why Used:** Enables the document pipeline to continue asynchronously to indexing, allowing for scalable processing of large PDFs without requiring the extraction service to wait for indexing completion.

## ChunksIndexed Event
- **Published by:** Indexing Service
- **Consumed by:** Retrieval Service
- **Purpose:** Notifies that document chunks have been embedded and stored in the vector database (Qdrant). Triggers cache invalidation in retrieval service.
- **Usage in Code:**
  - Published: services/indexing/app/rabbitmq.py via publish_chunks_indexed_event()
  - Consumed: services/retrieval/app/retrieval.py via handle_chunks_indexed() for cache invalidation
- **Why Used:** Ensures retrieval service can invalidate its cache when new documents are indexed, maintaining up-to-date search results and preventing stale data from being returned to users.

## QueryReceived Event
- **Published by:** Chat Service
- **Consumed by:** Chat Service, Retrieval Service
- **Purpose:** Tracks user queries for monitoring and analytics. Does NOT trigger retrieval (that happens via HTTP).
- **Usage in Code:**
  - Published: services/chat/app/chat_events.py via publish_query_received_event() in daemon thread
  - Consumed: 
    - services/chat/app/consumers.py (tracking/logging only)
    - services/retrieval/app/consumers.py (tracking/logging only)
- **Why Used:** Provides fire-and-forget event tracking for observability without blocking the main query flow. Actual retrieval happens synchronously via HTTP POST to /query endpoint for reliability.

## RetrievalCompleted Event
- **Published by:** Retrieval Service
- **Consumed by:** Chat Service, Retrieval Service
- **Purpose:** Provides metrics and completion notification for retrieval operations including result count, top score, and latency.
- **Usage in Code:**
  - Published: services/retrieval/app/retrieval_events.py via publish_retrieval_completed_event() in daemon thread
  - Consumed: 
    - services/chat/app/consumers.py (tracking/logging only)
    - services/retrieval/app/consumers.py (tracking/logging only)
- **Why Used:** Enables monitoring, logging, and analytics of retrieval performance without blocking the HTTP response. Runs in background thread to ensure immediate response to chat service while still capturing metrics for observability and debugging.


## Event Architecture Notes

### Synchronous Document Pipeline (Blocking Events)
- **DocumentDiscovered** → **DocumentExtracted** → **ChunksIndexed**
- These events drive the core document processing pipeline and are consumed by the next service in the chain.

### Asynchronous Query Flow (Non-Blocking Events)
- **QueryReceived** and **RetrievalCompleted** are fire-and-forget tracking events
- Actual query processing happens via HTTP POST /query endpoint (chat → retrieval)
- Events run in daemon threads and won't block or crash services if RabbitMQ fails
- Used purely for observability, monitoring, and debugging