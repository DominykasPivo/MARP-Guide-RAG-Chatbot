### Service Name: extraction

### Responsibility:
Extracts raw text from PDFs and cleans it for indexing service

### Data Owned:
*   Extracted document metadata (title, page_count, source_url - if available from the PDF)

### API Endpoints:
-   [GET]  / – Home/status endpoint
-   [GET]  /health – Health check by using the RabbitMQ status
-   [POST] /extract - Extract text from a given document (REQUIRES document file_path IN JSON Format)
