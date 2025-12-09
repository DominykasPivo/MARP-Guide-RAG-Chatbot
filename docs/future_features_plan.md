# **Future Feature Implementation Plan (Tiers 1 & 2\)**

This document provides the detailed design and implementation plan for the next two major feature tiers, focusing on security, user experience, and the core LLM orchestration functionality.

## **Tier 1: User Authentication and Data Isolation**

Authentication is critical for ensuring secure, personalized experiences and isolating user-specific RAG knowledge bases.

### **1.1 Goal**

Implement secure user registration, login, token management, and a robust authorization layer that isolates each user's data across the PostgreSQL and ChromaDB databases.

### **1.2 Technical Foundation**

This implementation will adhere to the existing architecture:

* All backend logic will be built using **Python/Flask**.  
* Communication between the API Gateway and the AuthService will utilize **Synchronous REST**.  
* **PostgreSQL** will remain the authoritative source for user metadata.

### **1.3 Design Overview**

* **AuthService:** Handles user creation, password hashing, JWT generation, and token validation.  
* **API Gateway:** Acts as the authorization barrier, validating the JWT for all protected routes and forwarding the extracted user\_id to downstream services.  
* **Data Partitioning:** All data queries (chat history, document ingestion, vector retrieval) must be scoped by the authenticated user\_id.

### **1.4 Implementation Plan**

| Step | Service | Description |
| :---- | :---- | :---- |
| **1\. User DB Schema** | AuthService | Update the PostgreSQL schema to include necessary tables: users (id, email, password\_hash, created\_at) and potentially sessions or tokens. |
| **2\. Auth Logic** | AuthService | Implement endpoints for /register and /login. Use **Bcrypt** for secure password hashing. On successful login, generate a signed **JWT** containing the user\_id and an expiration time. |
| **3\. Gateway Authorization** | API Gateway | Implement a middleware or interceptor. For protected routes (e.g., /chat/\*, /document/\*), it must: 1\) Extract the JWT from the Authorization header. 2\) Call the **AuthService** internally to validate the token. 3\) If valid, extract the user\_id and inject it into the request header (e.g., X-User-ID) before forwarding to the target service. |
| **4\. Scoped Retrieval** | RetrievalService | Modify the service to retrieve documents from **ChromaDB** using the X-User-ID header value to filter the correct vector collection (as specified in the architecture, collections should be named based on user ID). |
| **5\. Scoped Ingestion** | IngestionService/IndexingService | Ensure that when a document is indexed, both the PostgreSQL metadata and the **ChromaDB collection name** are explicitly scoped using the user\_id received from the Gateway. |
| **6\. Frontend Integration** | React Frontend | Implement the UI for login/registration and store the received JWT securely (e.g., in HttpOnly cookies or secure local storage). Include the JWT in all API calls. |

## **Tier 2: Multi-Model Comparison (Orchestrator Core)**

This tier implements the core value proposition of providing comparative, grounded answers from different external LLMs simultaneously.

### **2.1 Goal**

Fully activate the **Orchestrator Service** to execute calls to multiple LLM providers (Model A and Model B), collect the generated responses, and return them in a structured format for side-by-side comparison in the UI.

### **2.2 Technical Foundation**

This implementation will adhere to the existing architecture:

* The Orchestrator will be a **Python/Flask** microservice.  
* Communication will use **Synchronous REST** for calls from the ChatService and back.  
* **The Orchestrator will execute blocking API calls sequentially** to external LLMs, maintaining the synchronous nature of the overall RAG flow.

### **2.3 Design Overview**

* **Orchestrator Service:** Dedicated responsibility for querying external LLMs.  
* **Execution Model:** The Orchestrator will make separate, **blocking API calls** to each external LLM provider one after the other, ensuring that a consolidated, structured response containing all answers is collected before returning to the ChatService.  
* **Response Structuring:** Standardize the output from disparate LLM APIs into a single, predictable JSON format.

### **2.4 Implementation Plan**

| Step | Service | Description |
| :---- | :---- | :---- |
| **1\. Orchestrator Configuration** | Orchestrator | Define environment variables for all required LLM API keys (e.g., OPENAI\_API\_KEY, ANTHROPIC\_API\_KEY). |
| **2\. API Clients** | Orchestrator | Implement robust, fault-tolerant client wrappers for the APIs of **Model A** (e.g., OpenAI) and **Model B** (e.g., Anthropic/Claude). |
| **3\. Execution** | Orchestrator | The primary endpoint (POST /orchestrate/rag-query) must execute **sequential blocking API calls** to send the RAG-contextualized prompt to Model A and then Model B. |
| **4\. Response Normalization** | Orchestrator | Create a standard internal response object (e.g., {"model\_name": "...", "answer": "...", "tokens\_used": "..."}) and map the raw API responses from Model A and Model B into this standardized format. |
| **5\. ChatService Integration** | ChatService | Update the ChatService to expect and handle the new **array of responses** from the Orchestrator, rather than a single text string. |
| **6\. Frontend Display** | React Frontend | Update the UI to parse the array of responses and display them in a **side-by-side comparative layout**, along with any associated attribution metadata. |
| **7\. Tier 1 Dependency** | ALL | **Critical:** Ensure the RAG context passed from the ChatService to the Orchestrator correctly includes document chunks retrieved via the now **authenticated and scoped RetrievalService** (Tier 1 prerequisite). |

