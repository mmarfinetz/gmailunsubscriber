# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first for better caching
COPY gmail-unsubscriber-backend/requirements.txt ./requirements.txt

# Install Python dependencies
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Set working directory to backend
WORKDIR /app/gmail-unsubscriber-backend

# Set environment variables
ENV PYTHONPATH=/app/gmail-unsubscriber-backend
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE $PORT

# Run the application
CMD ["python", "-m", "gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "--workers", "2", "--timeout", "120", "--preload"]