### Server Name: retrieval

### Responsibility:
Retrieves the most relevant top-k document snippets based on query embeddings from the vector store.

### Data Owned:

*   Retrieval logs (query, timestamp, matched docs).
*   Vector store access credentials/config.


### API Endpoints:
-   [GET]  / – Home/status endpoint
-   [GET]  /health – Health check by using the RabbitMQ status
-   [GET] /search – Retrieve top-k relevant snippets for a query embedding.
