## **Detailed Architecture and Communication Patterns**

**The final, complete architecture diagram is maintained externally in Draw.io.**

**Please paste the public link or image markdown for your Draw.io diagram immediately below this line:**

[https://drive.google.com/file/d/1GVf\_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing](https://drive.google.com/file/d/1GVf_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing)


**This document details the microservice boundaries and communication flows for the Chat AI Application, utilizing Synchronous HTTP Communication (FastAPI) for the RAG query path and an Asynchronous Event-Driven Architecture (EDA) for the non-blocking document ingestion pipeline.**


### **1\. Synchronous Flow: User Chat Request (RAG)**

**This flow represents the real-time request path taken when a user submits a query. It is a synchronous process designed to deliver a consolidated answer derived from multiple LLMs and the vector knowledge base (Qdrant). All core services are implemented using FastAPI to handle the blocking HTTP communication pattern.**

| Step | Initiator | Target | Communication Type | Payload/Action |
| :---- | :---- | :---- | :---- | :---- |
| **1\.** | Frontend | API Gateway | **(HTTP/S)** | POST /chat/query (User query, Chat ID, User Auth Token) |
| **2\.** | API Gateway | ChatService | **(HTTP)** | **Internal Proxy:** Forwards the query and user context. |
| **3\.** | ChatService | QueryRewriter | **(HTTP)** | (Tier 2 Feature) Sends the user query for potential expansion/rewriting. |
| **4\.** | ChatService | RetrievalService | **(HTTP)** | Sends the (potentially rewritten) query. |
| **5\.** | RetrievalService | Vector DB (Qdrant) | **R/W** | **Read:** Queries vectors to retrieve top-k relevant document chunks. |
| **6\.** | RetrievalService | ChatService | **(HTTP)** | Returns the retrieved document chunks and citation metadata. |
| **7\.** | ChatService | Orchestrator | **(HTTP)** | Sends the full RAG context (Original Query, Chat History, Retrieved Chunks). |
| **8\.** | Orchestrator | External LLMs (A & B) | **External API** | Sends the final prompt to multiple models (e.g., GPT-4, Claude 3\) concurrently. |
| **9\.** | Orchestrator | ChatService | **(HTTP)** | Returns a collection of generated answers and source attributions. |
| **10\.** | ChatService | API Gateway | **(HTTP)** | Returns the final structured response (multi-model answers). |
| **11\.** | API Gateway | Frontend (FastAPI) | **(HTTP/S)** | Returns the response to the user. |

### **2\. Asynchronous Flow: Document Ingestion Process (Event-Driven Architecture)**

**This workflow is non-blocking and uses the Event Broker (RabbitMQ) to decouple services. The user receives an immediate confirmation, while the computationally intensive tasks of extraction, embedding, and indexing run asynchronously in the background.**

| Step | Initiator | Target | Communication Type | Payload/Action |
| :---- | :---- | :---- | :---- | :---- |
| **1\.** | External Source/Frontend | API Gateway | **(HTTP/S)** | POST /document/upload (Uploads new MARP PDF). |
| **2\.** | API Gateway | Ingestion Service | **(HTTP)** | **Internal Proxy:** Forwards the document/initiation request. |
| **3\.** | Ingestion Service | Extraction Service | **(HTTP)** | **Blocking Call:** Sends the document/path for synchronous text and metadata extraction. |
| **4\.** | Extraction Service | Indexing Service | **(HTTP)** | **Blocking Call:** Sends extracted data and requests synchronous vector embedding/persistence. |
| **5\.** | Indexing Service | Vector DB (Qdrant) | **Write** | **Writes Embeddings:** Chunks text, generates vector embeddings, and persists them. |
| **6\.** | Indexing Service | User DB (PostgreSQL) | **Write** | **Writes Metadata:** Records document status, title, and ingestion completion metadata. |
| **7\.** | Indexing Service | Extraction Service | **(HTTP)** | Returns success confirmation. |
| **8\.** | Extraction Service | Ingestion Service | **(HTTP)** | Returns success confirmation. |
| **9\.** | Ingestion Service | API Gateway | **(HTTP)** | Returns final success confirmation (Document Indexed). |
| **10\.** | API Gateway | External Source/Frontend | **(HTTP/S)** | Returns final response to the user. |

### **Network Communication Summary**

* **API Gateway (Port 8000): Only public-facing service. Uses HTTP/S Request for external communication.  
* **Internal Microservices (FastAPI): Communicate via HTTP for the synchronous RAG path.
* **Data Pipeline Services: Communicate asynchronously using the Event Broker (RabbitMQ) for the document ingestion path.
* **Databases:** Qdrant is used as the high-performance Vector Database (accessed by Retrieval and Indexing services).
* Qdrant is used as the high-performance Vector Database (accessed by Retrieval and Indexing services).
* PostgreSQL is used as the User Database for user data, chat history, and document metadata (accessed by Auth and Indexing services).
* External LLMs: Accessed via the Orchestrator service's external API calls.

