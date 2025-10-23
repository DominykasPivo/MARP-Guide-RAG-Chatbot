### Responsibility:
Enhances and reformulates user queries using multiple LLMs to improve retrieval accuracy.

### Data Owned:
*   Query rewrite history.
*   Model usage statistics.

### API Endpoints:
-   [GET] /rewrite/models – List available LLM models used for rewriting.
-   [POST] /rewrite – Accepts raw query and returns rewritten/enhanced queries.
