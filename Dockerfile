# 🏛️ Solana AI Risk Organism — Production Dockerfile
FROM python:3.10-slim

# Prevent Python from writing .pyc files & enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (7860 is default for HuggingFace Spaces)
EXPOSE 7860

# Run with Gunicorn + Eventlet for Socket.io support
# We use -w 1 because Socket.io with in-memory state needs a single worker 
# unless using a message queue like Redis.
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:7860", "app:app"]
