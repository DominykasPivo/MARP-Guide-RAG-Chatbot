![CI](https://github.com/DominykasPivo/MARP-Guide-RAG-Chatbot/actions/workflows/ci.yml/badge.svg)

# MARP-Guide-RAG-Chatbot
LZSCC.311  - Year 3 Group Project

RAG Chatbot with Microservices and Event-Driven Architecture

# **Goal of Project | Chat AI Application**

Building a chat application that answers questions about Lancaster University’s Manual of Academic Regulations and Procedures (MARP). The answers must be derived from the processed MARP PDF documents and must be properly cited
(with title, page number, and link), and presented in an understandable manner.


## **1\. Key Features**

* **User Authentication:** Secure login and registration so every user has their own private chat history.  
* **Document Ingestion Pipeline:** An event-driven workflow for reliably processing new documents (MARP PDFs) and updating the knowledge base.  
* **Vector-Powered Memory (RAG):** The app uses a special **Qdrant** vector database to "remember" past conversations and provide **Retrieval-Augmented Generation (RAG)** answers.  
* **Multi-Model Comparison:** Get answers from different LLMs (like GPT-4, Claude 3, etc.) for the *same question*, shown side-by-side so you can compare them.

## **2\. Technology Stack**

This project is built using a modern, professional stack:

| Component | Technology | Purpose |
| :---- | :---- | :---- |
| **Frontend (UI)** | **FastAPI** | Serves the HTML for the UI. Used to be (React) |
| **Backend (APIs)** | **Python (FastAPI)** | High-performance, modern framework for all microservices. Used to be (Flask) |
| **Event Broker** | **RabbitMQ** | Manages asynchronous background tasks (Document Pipeline). |
| **Vector Database** | **Qdrant** | High-performance, scalable vector store for RAG. replaced ChromaDB |
| **User Database** | **PostgreSQL** | Standard SQL database for securely storing user accounts and metadata. |


## **3\. Full Architecture Diagram (Provided by [Draw.io](http://Draw.io))**

## **The final, complete architecture diagram is maintained externally in Draw.io.**

**Please paste the public link or image markdown for your Draw.io diagram immediately below this line:**

[https://drive.google.com/file/d/1GVf\_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing](https://drive.google.com/file/d/1GVf_S1b8M28ZETZ2Z4B94uoLGt74oon3/view?usp=sharing)

## **4\. How It Works: Key Scenario**

#### **Document Ingestion Pipeline (Synchronous)**

* ### This workflow is a single, blocking chain of REST calls responsible for reliably processing a new MARP PDF and integrating its content into the knowledge base. The user must wait for the entire process—including extraction, chunking, vector embedding, and database writes—to complete before receiving a final confirmation.

* ### Flow Summary: The Ingestion Service initiates a blocking call to the Extraction Service. The Extraction Service performs text extraction and then initiates a blocking call to the Indexing Service. The Indexing Service performs the computationally heavy work (embedding generation and vector writes to Qdrant) before the successful response cascades back up through the chain to the user.



## **5\. Deployment & Ports**

The **API Gateway** remains the single public entry point; all other services are internal.

| Service | Host Port | Notes |
| :---- | :---- | :---- |
| APIGateway | 8000 | **Public:** This is the entry point for users/UI access. |
| Auth | 8006 | **Internal:** Handles user authentication and authorization (Login/Registration). |
| Ingestion | 8001 | **Internal:** Listens for external documents. |
| Extraction | 8002 | **Internal:** Consumes events from RabbitMQ. |
| Indexing | 8003 | **Internal:** Consumes events to generate embeddings and write to Qdrant. |
| Chat | 8004 | **Internal:** Manages conversation state and orchestrates RAG flow. |
| Retrieval | 8005 | **Internal:** Queries the VectorDB(Qdrant) for relevant document chunks.. |




# **Chat AI Application Setup and Run Instructions**

This guide provides the necessary steps to set up and run the entire microservices architecture using Docker Compose.

**Prerequisites:**

1. **Docker:** Ensure Docker and Docker Compose (or Docker Desktop) are installed and running on your system.  
2. **Codebase:** The source code for each service must be cloned and organized into directories matching the service names (e.g., apigateway/, authservice/, ingestionservice/, etc.).

## **1\. Project Structure Verification**

Before proceeding, verify that your project directory structure looks like this:

/chatbot  
|-- docker-compose.yml   \<-- The file generated above  
|-- README.md  
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
|-- .env (Optional, for custom configuration)

## 

## **2\. Launching the System**

Execute the following command in the root directory where your docker-compose.yml file is located:

#Step 1 Building

docker-compose build ingestion extraction indexing --no-cache

#Step 2 Running

docker-compose up ingestion extraction indexing -d






| Command | Purpose |
| :---- | :---- |
| up | Starts all services defined in the configuration. |
| \--build | Forces Docker to rebuild the images for the application services (e.g., apigateway, authservice) based on their Dockerfiles. **Crucial for initial setup or after code changes.** |
| \-d | Runs the containers in **detached** mode (in the background). |

## **4\. System Verification (Health Check)**

After running the up command, the system should be fully operational. You can verify the status and access the infrastructure components:

| Component | Status Check Command | Access URL (Local) | Notes |
| :---- | :---- | :---- | :---- |
| **All Containers** | docker-compose ps | N/A | All containers should be in the Up state. |
| **API Gateway** | Check logs: docker-compose logs api\_gateway | http://localhost:8000 | This is the entry point for the React Frontend. |
| **RabbitMQ UI** | N/A | http://localhost:15672 | Log in with the credentials defined in .env (default: guest/guest). |

## **5\. Stopping and Cleanup**

To stop all running services and keep the data volumes (for faster restarts):

docker-compose stop

To stop all services and remove the containers, networks, and persistent data volumes:

docker-compose down \-v

**Note:** The \-v flag removes the postgres\_data and chromadb\_data volumes. **All database and vector data will be permanently deleted.** Only use this command if you want a clean restart.




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









