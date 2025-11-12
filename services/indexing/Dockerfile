
# Base image
FROM python:3.12-slim

#Set working directory
WORKDIR /app


# Copy dependency files
COPY requirements.txt .


# Install dependencies (includes qdrant-client)
RUN pip install --no-cache-dir -r requirements.txt



# Install build tools and curl for healthchecks
RUN apt-get update && apt-get install -y build-essential g++ cmake curl && rm -rf /var/lib/apt/lists/*


# Copy the source code into the container.
COPY app/ .


# Expose the port that the application listens on.
EXPOSE 8000


# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1


# Run the application.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]