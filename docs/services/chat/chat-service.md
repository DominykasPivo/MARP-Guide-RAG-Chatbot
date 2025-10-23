### Responsibility:
Orchestrates the real-time user interaction pipeline — manages user queries, rewrites, retrieval, and RAG LLM response generation.

### Data Owned:

*   Chat session history.
*   User query logs and response metadata.

### API Endpoints:
-   [POST] /chat – Main chat endpoint: accepts query, calls rewriting → retrieval → LLM → returns answer.
-   [POST] /chat/feedback – Submit user feedback for an answer. (This is needed for the Bot to learn!)
-   [GET] /chat/session/{id} – Retrieve past conversation history.
