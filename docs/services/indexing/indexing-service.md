### Responsibility:
Embeds extracted text into vector representations and stores them in a vector database.

### Data Owned:

*   Vector properties.
*   Mapping between document IDs and embedding IDs

### API Endpoints:
-   [GET] /index/status/{doc_id} - Check if a document is indexed
-   [POST] /index/reindex/{doc_id} - Trigger re-indexing for a document
