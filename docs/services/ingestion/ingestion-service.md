### Responsibility:
Discovers, downloads, and registers academic regulation documents from Lancaster University's MARP website.

### Data Owned:
*   PDF document storage
*   Document metadata (title, source URL, discovery date, last modified)
*   Document discovery cache

### API Endpoints:
-   [GET] / – Basic health check endpoint
-   [GET] /health – Detailed health check with RabbitMQ status
-   [POST] /discovery/start – Trigger discovery of new/updated MARP documents
