### Responsibility:
Retrieves the most relevant top-k document snippets based on query embeddings from the vector store.

### Data Owned:

*   Retrieval logs (query, timestamp, matched docs).
*   Vector store access credentials/config.


### API Endpoints:
-   [POST] /retrieve – Retrieve top-k relevant snippets for a query embedding.
-   [GET] /retrieve/stats – Retrieve retrieval performance and usage metrics.
