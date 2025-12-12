# Chat Service

The Chat Service is a core component of the **MARP Guide RAG Chatbot**. It handles user queries, interacts with the retrieval service to fetch relevant document chunks, and generates answers using multiple LLMs.

---

## Features

- **Query Handling:** Accepts user queries via the `/chat` endpoint.
- **Chunk Retrieval:** Fetches relevant document chunks from the retrieval service.
- **LLM Integration:** Generates answers using multiple LLMs in parallel.
- **Event Tracking:** Publishes `QueryReceived` events for observability.
- **Asynchronous Processing:** Uses async HTTP calls and background threads for non-blocking operations.
- **Health Monitoring:** Provides a `/health` endpoint for service status checks.

---

## Architecture

1. **User Query:** A user submits a query via the `/chat` endpoint.
2. **Event Publishing:** The service publishes a `QueryReceived` event for tracking.
3. **Chunk Retrieval:** Relevant document chunks are fetched from the retrieval service.
4. **Answer Generation:** Multiple LLMs process the query and chunks in parallel to generate answers.
5. **Response:** The service returns the generated answers along with citations.

---

## Prerequisites

- **Python Version:** 3.9 or higher
- **RabbitMQ:** For event-driven communication.
- **Retrieval Service:** Must be running and accessible.
- **Environment Variables:** Ensure the following are set:
  - `RABBITMQ_URL`: RabbitMQ connection string (e.g., `amqp://guest:guest@localhost:5672/`).
  - `RETRIEVAL_SERVICE_URL`: URL of the retrieval service (e.g., `http://retrieval:8000`).
  - `OPENROUTER_API_KEY`: API key for LLM integration.
  - `LLM_MODELS`: Comma-separated list of LLM models (e.g., `model1,model2`).

---

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/saeedkabak/MARP-Guide-RAG-Chatbot.git
   cd MARP-Guide-RAG-Chatbot/services/chat
   ```

2. **Install Dependencies:**
   Use `pip` to install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up RabbitMQ:**
   Ensure RabbitMQ is running and accessible. Update the `RABBITMQ_URL` environment variable if necessary.

4. **Configure Environment Variables:**
   Create a `.env` file or export the required variables:
   ```bash
   export RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
   export RETRIEVAL_SERVICE_URL="http://retrieval:8000"
   export OPENROUTER_API_KEY="your-api-key"
   export LLM_MODELS="model1,model2"
   ```

---

### Endpoints

#### 1. **`GET /health`**
- **Description:** Health check endpoint.
- **Response:**
  ```json
  {
    "status": "healthy"
  }
  ```

#### 2. **`GET /models`**
- **Description:** Returns the list of available LLM models.
- **Response:**
  ```json
  {
    "models": ["model1", "model2"]
  }
  ```

#### 3. **`POST /chat`**
- **Description:** Main endpoint for submitting user queries.
- **Request Body:**
  ```json
  {
    "query": "What are the university regulations?",
    "selected_models": ["model1", "model2"]
  }
  ```
- **Response:**
  ```json
  {
    "query": "What are the university regulations?",
    "responses": [
      {
        "model": "model1",
        "answer": "The university regulations are...",
        "citations": [
          {
            "title": "General Regulations",
            "page": 12,
            "url": "https://example.com/regulations.pdf",
            "score": 0.95
          }
        ],
        "generation_time": 2.5
      }
    ]
  }
  ```

---

## Event-Driven Features

### Published Events

#### `QueryReceived`
- **Description:** Tracks user queries for observability.
- **Published By:** `/chat` endpoint.
- **Schema:**
  ```json
  {
    "eventType": "QueryReceived",
    "eventId": "string",
    "timestamp": "string",
    "source": "chat-service",
    "version": "1.0",
    "payload": {
      "queryId": "string",
      "userId": "string",
      "queryText": "string"
    }
  }
  ```

---
### Common Issues

1. **RabbitMQ Connection Error:**
   - Ensure RabbitMQ is running and the `RABBITMQ_URL` is correct.

2. **Retrieval Service Unreachable:**
   - Verify the `RETRIEVAL_SERVICE_URL` and ensure the retrieval service is running.

3. **LLM API Key Missing:**
   - Set the `OPENROUTER_API_KEY` environment variable.
