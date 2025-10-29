# Ingestion Service

## Directory Structure
```
services/ingestion/
├── app/
│   ├── data/           # Storage for uploaded files
│   ├── utils/          # Utility functions
│   ├── main.py         # Main application entry point
│   ├── config.py       # Configuration settings
│   └── requirements.txt # Python dependencies
├── Dockerfile          # Container configuration
└── .dockerignore      # Files to exclude from build
```

## Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

2. Install dependencies:
```bash
cd app
pip install -r requirements.txt
```

3. Run the development server:
```bash
python main.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| PORT | Service port number | 8000 |
| LOG_LEVEL | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| MAX_UPLOAD_SIZE | Maximum file upload size | 5MB |

## API Endpoints

- GET `/health` - Health check endpoint
- GET `/ingestion/status/{id}` - Get ingestion status
- POST `/ingestion/upload` - Upload document

## Docker

This service is part of the larger RAG system. To run it along with other services, use the docker-compose file in the root directory:

```bash
# From the root directory
docker-compose up -d
```

For development purposes, you can also build and run this service individually:

```bash
# From the services/ingestion directory
docker build -t rag-ingestion-service .
docker run -d -p 8000:8000 --name rag-ingestion rag-ingestion-service
```
