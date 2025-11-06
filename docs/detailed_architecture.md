## **Detailed Architecture and Communication Patterns**

**The final, complete architecture diagram is maintained externally in Draw.io.**

**Please paste the public link or image markdown for your Draw.io diagram immediately below this line:**

[https://drive.google.com/file/d/1GVf\_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing](https://drive.google.com/file/d/1GVf_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing)


This document details the microservice boundaries and communication flows for the Chat AI Application (V2), utilizing **Synchronous REST** for all communication paths (Chat and Document Ingestion).


### **1\. Synchronous Flow: User Chat Request (RAG)**

This flow represents the **real-time request path** taken when a user submits a query via the front-end. It is a synchronous, blocking process designed to deliver a consolidated answer derived from multiple LLMs and the vector knowledge base. The process begins with the **API Gateway** routing the request to the **ChatService**, which acts as the central coordinator. The ChatService first uses the **RetrievalService** to fetch contextual data from **ChromaDB**. It then sends the compiled prompt to the **Orchestrator**, which fans out the request to external LLMs and collects the multi-model responses before returning the final result to the user.

| Step | Initiator | Target | Communication Type | Payload/Action |
| :---- | :---- | :---- | :---- | :---- |
| **1\.** | Frontend (React) | API Gateway | **REST (HTTP/S)** | POST /chat/query (User query, Chat ID, User Auth Token) |
| **2\.** | API Gateway | ChatService | **REST (HTTP)** | **Internal Proxy:** Forwards the query and user context. |
| **3\.** | ChatService | QueryRewriter | **REST (HTTP)** | (Tier 2 Feature) Sends the user query for potential expansion/rewriting. |
| **4\.** | ChatService | RetrievalService | **REST (HTTP)** | Sends the (potentially rewritten) query. |
| **5\.** | RetrievalService | Vector DB (ChromaDB) | **R/W** | **Read:** Queries vectors to retrieve top-k relevant document chunks. |
| **6\.** | RetrievalService | ChatService | **REST (HTTP)** | Returns the retrieved document chunks and citation metadata. |
| **7\.** | ChatService | Orchestrator | **REST (HTTP)** | Sends the full RAG context (Original Query, Chat History, Retrieved Chunks). |
| **8\.** | Orchestrator | External LLMs (A & B) | **External API** | Sends the final prompt to multiple models (e.g., GPT-4, Claude 3\) concurrently. |
| **9\.** | Orchestrator | ChatService | **REST (HTTP)** | Returns a collection of generated answers and source attributions. |
| **10\.** | ChatService | API Gateway | **REST (HTTP)** | Returns the final structured response (multi-model answers). |
| **11\.** | API Gateway | Frontend (React) | **REST (HTTP/S)** | Returns the response to the user. |

### **2\. Synchronous Flow: Document Ingestion Process**

This workflow is a single, **blocking chain of REST calls** responsible for reliably processing a new MARP PDF and integrating its content into the knowledge base. Because the entire process (Extraction, Embedding, and Database writes) is synchronous, the user must wait until step 10 to receive confirmation. The process is initiated by the **Ingestion Service**, which immediately makes a blocking call to the **Extraction Service**. This service, in turn, blocks while communicating with the **Indexing Service** to perform the heavy lifting of generating vector embeddings and writing both vectors (to ChromaDB) and metadata (to PostgreSQL). The service calls cascade back up the chain upon completion. **RabbitMQ is not used in this operational flow.**

| Step | Initiator | Target | Communication Type | Payload/Action |
| :---- | :---- | :---- | :---- | :---- |
| **1\.** | External Source/Frontend | API Gateway | **REST (HTTP/S)** | POST /document/upload (Uploads new MARP PDF). |
| **2\.** | API Gateway | Ingestion Service | **REST (HTTP)** | **Internal Proxy:** Forwards the document/initiation request. |
| **3\.** | Ingestion Service | Extraction Service | **REST (HTTP)** | **Blocking Call:** Sends the document/path for synchronous text and metadata extraction. |
| **4\.** | Extraction Service | Indexing Service | **REST (HTTP)** | **Blocking Call:** Sends extracted data and requests synchronous vector embedding/persistence. |
| **5\.** | Indexing Service | Vector DB (ChromaDB) | **Write** | **Writes Embeddings:** Chunks text, generates vector embeddings, and persists them. |
| **6\.** | Indexing Service | User DB (PostgreSQL) | **Write** | **Writes Metadata:** Records document status, title, and ingestion completion metadata. |
| **7\.** | Indexing Service | Extraction Service | **REST (HTTP)** | Returns success confirmation. |
| **8\.** | Extraction Service | Ingestion Service | **REST (HTTP)** | Returns success confirmation. |
| **9\.** | Ingestion Service | API Gateway | **REST (HTTP)** | Returns final success confirmation (Document Indexed). |
| **10\.** | API Gateway | External Source/Frontend | **REST (HTTP/S)** | Returns final response to the user. |

### **Network Communication Summary**

* **API Gateway (Port 8000):** Only public-facing service. Uses **REST (HTTP/S)** for external communication.  
* **Internal Microservices:** Communicate exclusively via **REST (HTTP)** for both chat and document processing.  
* **Databases:** Accessed directly by the services responsible for managing their data.
