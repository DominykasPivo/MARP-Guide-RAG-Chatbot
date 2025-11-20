### Service Name: chat

### Responsibility:
Orchestrates the real-time user interaction pipeline — manages user queries, rewrites, retrieval, and RAG LLM response generation.

### Data Owned:

*   Chat session history.
*   User query logs and response metadata.

### API Endpoints:
-   [POST] /chat – Main chat endpoint: accepts query, calls rewriting → retrieval → LLM → returns answer.
-   [GET]  / – Home/status endpoint