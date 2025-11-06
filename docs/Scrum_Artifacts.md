# **Product Backlog: Chat AI Application** 

This backlog contains all known features, user stories, and technical debt required to complete the project, prioritized from highest to lowest.

| ID | Feature / User Story | Dependencies | Notes |
| :---- | :---- | :---- | :---- |
| **PBL-01** | **Core RAG Chat Flow** | Docker Setup | Implement ChatService \-\> RetrievalService \-\> Orchestrator (Single LLM) \-\> Frontend flow. |
| **PBL-02** | **Docker Compose Setup** | N/A | Fully functional docker-compose.yml and services for local development. |
| **PBL-03** | **Synchronous API Gateway** | PBL-02 | Set up API Gateway with REST endpoints for /chat and /document/upload. |
|  **PBL-04** |  **Document Ingestion Pipeline (Synchronous)** |  PBL-02 |  Ingestion \-\> Extraction \-\> Indexing (Blocking REST chain, as per current architecture). |
| **PBL-05** | **Frontend (React) Base UI** | PBL-03 | Basic chat input, conversation history display, and document upload UI. |
| **PBL-06** | **User Chat History Storage** | PBL-06 | Scoped storage/retrieval of user chat sessions in PostgreSQL. |
| **PBL-07** | **Error Handling & Logging** | PBL-01, PBL-04 | Standardized error response format across all microservices. |
| **PBL-8** | **Comprehensive Unit Tests** | All Services | Target 80% coverage for core business logic. |

# **Sprint 1 Log: Core Infrastructure and RAG Foundation**

* **Sprint Goal:** Functional core system with basic RAG capability, microservices architecture, event-driven design, and comprehensive documentation.  
* **Duration:** 5 Weeks  
* **Team Capacity:** 3

| Item ID | Description | Backlog Item | Status | Notes |
| :---- | :---- | :---- | :---- | :---- |
| **S1-01** | Define and test docker-compose.yml for all 9 services (incl. DBs/Broker). | PBL-02 | DONE | Confirmed services can communicate internally via network. |
| **S1-02** | Implement API Gateway (Flask) with basic /health endpoint and routing structure. | PBL-03 | DONE | Routing established for /chat. |
| **S1-03** | Implement RetrievalService to connect to ChromaDB and perform simple vector query. | PBL-01 | DONE | Need to finalize ChromaDB connection string within container environment. |
| **S1-04** | Implement Orchestrator (Flask) with placeholder endpoint for single LLM call. | PBL-01 | In Progress | Successful connection to external LLM API (e.g., Gemini). |
| **S1-05** | Implement ChatService to orchestrate RAG: Query \-\> Retrieval \-\> Orchestrator \-\> Response. | PBL-01 | DONE | Dependent on S1-03 and S1-04 completion. |
| **S1-06** | Develop basic React frontend UI for chat input and display. | PBL-05 | DONE | Focusing on layout and API connectivity. |
| **S1-07** | Integrate API Gateway with React frontend. | PBL-03, PBL-05 | DONE | Successful HTTP communication confirmed. |
| **S1-08** | Initial setup and schema creation for PostgreSQL (Users table placeholder). | PBL-08 | DONE |  |

# **Team Retrospective: Sprint 1 (Core RAG Foundation)**

## **1\. What Went Well?**

* **Docker Setup:** Getting the full stack running with docker-compose up on the first try was a huge win. The time spent defining the service network was worth it.  
* **Microservice Isolation:** The Flask service separation is clean. Each service (e.g., Orchestrator) knows its job and doesn't interfere with others.  
* **API Client Wrappers:** Creating simple, dedicated wrappers for the external LLM API in the Orchestrator (S1-04) saved time and made the code immediately testable.

## **2\. What Could Be Improved?**

* **Dependency Tracking:** We underestimated the time needed for the RetrievalService (S1-03) because it relied on the correct ChromaDB volume setup from the Docker work (S1-01). **Action:** Clearly document inter-service setup dependencies in the backlog item notes.  
* **Sequential Testing:** We waited too long to test the end-to-end ChatService flow (S1-05). **Action:** Next sprint, prioritize setting up mock services for early integration testing (e.g., a mock AuthService).  
* **PostgreSQL:** We completed the basic DB setup (S1-08) but didn't link it to a service. **Action:** Integrate the PostgreSQL connection into a service early in Sprint 2 to validate connectivity before starting the Auth feature (PBL-06)
