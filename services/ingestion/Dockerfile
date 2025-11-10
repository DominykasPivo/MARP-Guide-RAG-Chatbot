#Base image
FROM python:3.12-slim

#Set working directory
WORKDIR /app

#Copy dependency files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy the source code into the container.
COPY app/ .

# Create data directory for document storage
RUN mkdir -p data

# Expose the port that the application listens on.
EXPOSE 8000

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]