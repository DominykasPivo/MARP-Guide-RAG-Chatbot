#Base image // Using older one because hnswlib has issues with Python 3.12
FROM python:3.12-slim

#Set working directory
WORKDIR /app

#Copy dependency files
COPY requirements.txt . 

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt


# One of the dependencies requires build tools to compile docker  // # Install curl for healthchecks
RUN apt-get update && apt-get install -y build-essential g++ cmake curl && rm -rf /var/lib/apt/lists/*

# Copy the source code into the container.
COPY app/ .

# Expose the port that the application listens on.
EXPOSE 8000

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application.
CMD ["python", "app.py"]