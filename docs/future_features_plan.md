# **Additional Features Design**

This document provides the detailed design and implementation plan for the chosen Tier 1 and Tier 2 features, along with how they were implemented in the MARP Chatbot system.

## **Tier 1: User Authentication & Session Management**

### **1.1 Feature Overview**

This feature ensures secure user authentication, session handling, and user-specific chat isolation. It allows users to log in, log out, and ensures that their chat history and interactions are isolated from other users.

### **1.2 Design Overview**

* **AuthService:** Handles user registration, login, password hashing, JWT generation, and token validation.
* **API Gateway:** Acts as the authorization barrier, validating JWTs for all protected routes and forwarding the authenticated user ID to downstream services.
* **Session Management:** Ensures that each user’s session is securely managed and isolated.
* **Data Isolation:** All user-specific data (e.g., chat history, document ingestion) is scoped by the authenticated user ID.

### **1.3 Implementation Plan**

| Step | Service | Description |
| :---- | :---- | :---- |
| **1. User DB Schema** | AuthService | Updated the PostgreSQL schema to include tables for users (id, password_hash, created_at) and sessions. |
| **2. Auth Logic** | AuthService | Implemented endpoints for /register and /login. Used **Bcrypt** for secure password hashing. JWTs are generated on successful login. |
| **3. Gateway Authorization** | API Gateway | Middleware validates JWTs for protected routes, extracts the user ID, and injects it into the request headers. |
| **4. Scoped Retrieval** | RetrievalService | Modified to retrieve user-specific data using the user ID from the request headers. |
| **5. Frontend Integration** | Static Frontend | Added login/logout functionality and stored JWTs securely in HttpOnly cookies. Included JWTs in all API calls. |

### **1.4 Implementation Details**

* **Backend:** FastAPI was used to implement the AuthService and API Gateway. JWTs were chosen for stateless authentication, ensuring scalability.
* **Frontend:** The static frontend was updated to include login and logout functionality. User sessions are managed using secure cookies.
* **Data Isolation:** PostgreSQL and ChromaDB queries were updated to scope all data operations by the authenticated user ID.

---

## **Tier 2: Multi-Model Comparison**

### **2.1 Feature Overview**

This feature enables the MARP Chatbot to generate answers in parallel using multiple LLMs and display the results side-by-side in the UI. This allows users to compare responses from different models and choose the most relevant one.

### **2.2 Design Overview**

* **Orchestrator Service:** Responsible for querying multiple LLMs in parallel and consolidating the results.
* **Execution Model:** The Orchestrator sends the same query to multiple LLMs simultaneously and collects their responses.
* **Response Structuring:** Standardizes the output from different LLMs into a unified JSON format.
* **Frontend Display:** The static frontend displays the responses side-by-side, allowing users to compare answers.

### **2.3 Implementation Plan**

| Step | Service | Description |
| :---- | :---- | :---- |
| **1. Orchestrator Configuration** | Orchestrator | Configured environment variables for LLM API keys and endpoints. |
| **2. Parallel API Calls** | Orchestrator | Implemented parallel API calls to multiple LLMs using asyncio. |
| **3. Response Normalization** | Orchestrator | Standardized the responses into a unified JSON format with fields like model_name, answer, and tokens_used. |
| **4. ChatService Integration** | ChatService | Updated to handle and forward the array of responses from the Orchestrator. |
| **5. Frontend Display** | Static Frontend | Updated the UI to display responses side-by-side with metadata like model name and generation time. |

### **2.4 Implementation Details**

* **Backend:** The Orchestrator Service was implemented using FastAPI. It uses asyncio to send parallel requests to multiple LLM APIs and consolidates the responses.
* **Frontend:** The static frontend was updated to display the responses in a side-by-side layout. Each response includes the model name, answer, and metadata like generation time.
* **Performance Optimization:** The Orchestrator was optimized to handle timeouts and retries for LLM API calls, ensuring reliability.

---

## **Summary**

The Tier 1 and Tier 2 features were successfully implemented, enhancing the MARP Chatbot’s functionality and user experience. User authentication and session management ensure secure and personalized interactions, while multi-model comparison provides users with diverse perspectives and improves decision-making. These features align with the project’s goals of scalability, security, and user-centric design.
