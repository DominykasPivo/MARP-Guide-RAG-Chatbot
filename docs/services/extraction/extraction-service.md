### Responsibility:
Extracts raw text from ingested documents and preprocesses it into clean, chunkable text blocks.

### Data Owned:

*   Processing metadata (chunk size, token count).
*   Extracted text chunks (temporary store).

### API Endpoints:
-   [GET] /extract/status/{doc_id} – Get extraction job status.
