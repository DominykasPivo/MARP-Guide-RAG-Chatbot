#Base image
FROM python:3.12-slim

#Set working directory
WORKDIR /app

# Install curl for healthchecks first
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#Copy dependency files
COPY requirements.txt .

# Install dependencies with aggressive cleanup
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip && \
    find /usr/local/lib/python3.12 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.12 -type f -name "*.pyc" -delete && \
    find /usr/local/lib/python3.12 -type f -name "*.pyo" -delete

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
