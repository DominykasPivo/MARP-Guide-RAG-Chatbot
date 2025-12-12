### Server Name: indexing

### Responsibility:
Embeds extracted text into vector representations and stores them in a vector database.

### Data Owned:
*   Vector embeddings.
*   Chunk metadata (documentId, fileType, correlationId, title, pageCount, sourceUrl)
*   Mapping between document IDs and embedding IDs (ChromaDB maintains the relationship between both)
*   Indexing status (which documents are indexed and how many chunks each has)

### API Endpoints:
-   [GET]  /       – Home/status endpoint
-   [GET]  /health – Health check by using the RabbitMQ status
-   [POST] /index  - Index a document (requires a DocumentExtracted event payload)
    DocumentExtracted Args:
        > payload{extractedAt, metadata{title, sourceUrl, fileType, pageCount}, textContent, documentId}, version,
        > source, correlationId, timestamp, eventId, eventType
-   [GET]  /debug/queue – Debug: show RabbitMQ event queue status
-   [GET]  /debug/chunks – Return all chunks stored in the ChromaDB collection for inspection.
