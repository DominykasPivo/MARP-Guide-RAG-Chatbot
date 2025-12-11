#Base image
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies in one layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies with aggressive cleanup
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip && \
    find /usr/local/lib/python3.12 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.12 -type f -name "*.pyc" -delete && \
    find /usr/local/lib/python3.12 -type f -name "*.pyo" -delete

# Copy service files
COPY app/ .

# Expose port for health checks
EXPOSE 8000

# Run the service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
