# Base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install build dependencies for compiling chroma-hnswlib
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code into the container
COPY app/ .

# Expose the port that the application listens on
EXPOSE 8000

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]