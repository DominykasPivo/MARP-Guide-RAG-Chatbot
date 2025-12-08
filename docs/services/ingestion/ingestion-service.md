### Server Name: ingestion

### Responsibility:
Discovers, downloads, and registers academic regulation documents from Lancaster University's MARP website.

### Data Owned:
*   PDF document storage
*   Document metadata (document_id, source_url, indexedAt, hash, correlation_id)
*   Document discovery cache (JSON File)

### API Endpoints:
-   [GET]  / – Home/status endpoint
-   [GET]  /health – Health check by using the RabbitMQ status
-   [POST] /discovery/start – Triggers the discovery of new/updated/deleted PDFs 
-   [GET]  /documents - lists all the documents in the discovery cache (JSON file)
-   [GET]  /documents/<document_id> - downloads a specific document by giving its document_id 