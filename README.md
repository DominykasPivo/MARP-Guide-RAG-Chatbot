# MARP-Guide-RAG-Chatbot
LZSCC.311  - Year 3 Group Project

RAG Chatbot with Microservices and Event-Driven Architecture

# **Goal of Project | Chat AI Application**

Building a chat application that answers questions about Lancaster University’s Manual of Academic Regulations and Procedures (MARP). The answers must be derived from the processed MARP PDF documents and must be properly cited
(with title, page number, and link), and presented in an understandable manner.


## **1\. Key Features**

* **User Authentication:** Secure login and registration so every user has their own private chat history.  
* **Document Ingestion Pipeline:** An event-driven workflow for reliably processing new documents (MARP PDFs) and updating the knowledge base.  
* **Vector-Powered Memory (RAG):** The app uses a special **ChromaDB** vector database to "remember" past conversations and provide **Retrieval-Augmented Generation (RAG)** answers.  
* **Multi-Model Comparison:** Get answers from different LLMs (like GPT-4, Claude 3, etc.) for the *same question*, shown side-by-side so you can compare them.

## **2\. Technology Stack**

This project is built using a modern, professional stack:

| Component | Technology | Purpose |
| :---- | :---- | :---- |
| **Frontend (UI)** | **React** | The fast, modern website you interact with. |
| **Backend (APIs)** | **Python (Flask)** | Powers all the "behind-the-scenes" logic and microservices. |
| **Event Broker** | **RabbitMQ** | Manages asynchronous background tasks (Document Pipeline). |
| **Vector Database** | **ChromaDB** | The AI's "memory," storing document chunks as searchable vectors. |
| **User Database** | **PostgreSQL** | Standard SQL database for securely storing user accounts and metadata. |


## **3\. Full Architecture Diagram (Provided by [Draw.io](http://Draw.io))**

## **The final, complete architecture diagram is maintained externally in Draw.io.**

**Please paste the public link or image markdown for your Draw.io diagram immediately below this line:**

[https://drive.google.com/file/d/1GVf\_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing](https://drive.google.com/file/d/1GVf_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing)

## **4\. How It Works: Key Scenario**

#### **Document Ingestion Pipeline (Synchronous)**

* ### This workflow is a single, blocking chain of REST calls responsible for reliably processing a new MARP PDF and integrating its content into the knowledge base. The user must wait for the entire process—including extraction, chunking, vector embedding, and database writes—to complete before receiving a final confirmation.

* ### Flow Summary: The Ingestion Service initiates a blocking call to the Extraction Service. The Extraction Service performs text extraction and then initiates a blocking call to the Indexing Service. The Indexing Service performs the computationally heavy work (embedding generation and vector writes to ChromaDB) before the successful response cascades back up through the chain to the user.



## **5\. Deployment & Ports**

The **API Gateway** remains the single public entry point; all other services are internal.

| Service | Host Port | Container Port | Notes |
| :---- | :---- | :---- | :---- |
| APIGateway | 8000 | 8000 | **Public:** Frontend (React) talks to this port. |
| Ingestion | 8001 | 8000 | **Internal:** Listens for external documents. |
| Extraction | 8002 | 8000 | **Internal:** Consumes events from RabbitMQ. |
| Indexing | 8003 | 8000 | **Internal:** Consumes events to generate embeddings. |
| Chat | 8004 | 8000 | **Internal:** Manages conversation state and orchestrates RAG flow. |
| Retrieval | 8005 | 8000 | **Internal:** Queries the VectorDB. |



# **Chat AI Application Setup and Run Instructions**

This guide provides the necessary steps to set up and run the entire microservices architecture using Docker Compose.

---

## **Prerequisites**

1. **Docker**: Install Docker (20.10+) and Docker Compose (or Docker Desktop) on your system.
2. **Codebase**: Clone the repository and ensure the project structure matches the expected layout.
3. **Environment Variables**: Copy `.env.example` to `.env` and configure the necessary variables (e.g., API keys, database credentials).

---

## **1. Project Structure Verification**

Ensure your project directory structure looks like this:

```
/chatbot
|-- docker-compose.yml
|-- README.md
|-- .env.example
|-- .env
|-- /apigateway
|   |-- Dockerfile
|-- /auth
|   |-- Dockerfile
|-- /ingestion
|   |-- Dockerfile
|-- /extraction
|   |-- Dockerfile
|-- /indexing
|   |-- Dockerfile
|-- /chat
|   |-- Dockerfile
|-- /retrieval
|   |-- Dockerfile
```

---

## **2. Launching the System**

Run the following commands in the root directory where `docker-compose.yml` is located:

### **Step 1: Build Services**
```bash
docker-compose build --no-cache
```

### **Step 2: Start Services**
```bash
docker-compose up --build -d
```

---

## **3. System Verification (Health Check)**

Verify the status of the system and access the components:

| Component         | Status Check Command               | Access URL (Local)           | Notes                                      |
|-------------------|------------------------------------|------------------------------|--------------------------------------------|
| **All Containers**| `docker-compose ps`               | N/A                          | All containers should be in the Up state. |
| **API Gateway**   | `docker-compose logs apigateway`  | http://localhost:8000        | Entry point for the backend.              |
| **RabbitMQ UI**   | N/A                                | http://localhost:15672       | Default credentials: guest/guest.         |
| **Auth Service**  | N/A                                | http://localhost:8001/health | Check the `/health` endpoint.             |
| **Chat Service**  | N/A                                | http://localhost:8005/health | Check the `/health` endpoint.             |

---

## **4. Stopping and Cleanup**

### **Stop Services**
To stop all running services while keeping data volumes:
```bash
docker-compose stop
```

### **Remove Services and Data**
To stop all services and remove containers, networks, and volumes:
```bash
docker-compose down -v
```

**Warning**: The `-v` flag removes all data volumes, including database and vector data. Backup your data before using this command.

---



## **Document Ingestion Technology Stack Overview**

This stack outlines the dependencies for the two critical microservices responsible for transforming raw PDFs into searchable vector embeddings.

| Service | Technology (Package) | Version | Role in Service |
| :---- | :---- | :---- | :---- |
| **Extraction Service** | **Flask** | 3.0.0 **Latest**  | Microservice Framework: Provides the REST API endpoint and handles the HTTP request/response for synchronous processing. |
|  | **pika** | 1.3.2 **Latest**  | RabbitMQ Client: Used for future-proofing; handles connection to the Event Broker (RabbitMQ). |
|  | **PyPDF2** | 3.0.1 **Latest**  | PDF Utility: Used for basic PDF manipulation and extracting metadata like page count. |
|  | **pdfplumber** | 0.10.3 **Latest**  | PDF Text Extractor: **Primary tool** for robustly extracting text content from PDF files. |
|  | **python-magic** | 0.4.27 **Latest**  | File Type Identification: Used to detect the file type (e.g., confirm it is indeed a PDF) for validation. |
| **Indexing Service** | **Flask** | 3.1.2 **Latest**  | Microservice Framework: Provides the REST API endpoint to receive extracted text and initiates the embedding process. |
|  | **pika** | 1.3.2 **Latest**  | RabbitMQ Client: Used for future-proofing; handles connection to the Event Broker (RabbitMQ). |
|  | **chromadb** | 0.4.24 **Latest**  | Vector Database Client: **Core component** for connecting to ChromaDB, performing vector writes, and managing collections. |
|  | **tiktoken** | 0.5.2  **Latest**  | Tokenizer: Used to accurately count tokens and chunk text documents into segments that fit within the context window limits of the embedding models. |
|  | **sentence-transformers** | 5.1.1 **Latest**  | Embedding Generation: Core library used to load and run pre-trained language models to convert the chunked text segments into dense vector embeddings. This is the critical step for transforming text into a searchable numerical format that the Vector Database (ChromaDB) can store and use for similarity search. |
|  | **pydantic-settings** | 2.11.0 **Latest**  | Configuration Management: Handles the loading and validation of settings (e.g., environment variables, secrets) for the service configuration. |
|  | **tenacity** | 8.2.3 **Latest**  | Retry Pattern: Used to implement robust retries for potentially transient network or service errors when making requests to other microservices (like the Extraction Service). |
| **Ingestion Service** | **Flask** | 3.1.2 **Latest** | Microservice Framework: Provides the REST API endpoint to receive the raw document file upload and handles the initial HTTP request/response. |
|  | **Werkzeug** | 3.1.0  | WSGI Utility: Provides the underlying toolkit for handling WSGI requests, which Flask is built upon, including request, response, and URL routing objects |
|  | **requests** | 2.31.0 **Latest** | HTTP Client: Used to make internal API calls (e.g., to the Extraction Service) after receiving and validating the uploaded file. |
|  | **python-multipart** | 0.0.6 **Latest** | MIME Parser: Used for parsing multipart/form-data encoded requests, which is the standard way to handle file uploads via a REST API endpoint. |
|  | **pika** | 1.3.2 **Latest** | RabbitMQ Client: Used for future-proofing; handles connection to the Event Broker (RabbitMQ) for asynchronous processing or queuing of ingestion tasks. |
|  | **beautifulsoup4** | 4.13.0 **Latest** | HTML/XML Parser: Typically used for web scraping or processing structured data like HTML/XML that may be part of the ingestion flow (though less common for raw PDF ingestion, it's a general-purpose parsing utility). |
|  | **lxml** | 4.9.3  | XML/HTML Processor: A high-performance parser often used in conjunction with beautifulsoup4 or for handling XML/HTML data sources to be ingested. |
|  | **urllib3** | 1.21.1 | HTTP Client Library: Provides low-level HTTP client functionality; often used as a dependency by packages like requests to manage connection pooling and retries. |









