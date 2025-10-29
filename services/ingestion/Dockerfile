#Base image

FROM python:3.9-slim

#Set working directory
WORKDIR /app


#Copy dependency files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Copy the source code into the container.
COPY app/app.py .

# Expose the port that the application listens on.
EXPOSE 8000

# Run the application.
CMD ["python", "app.py"]
