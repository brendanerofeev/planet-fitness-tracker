FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py ./
COPY templates/ ./templates/

# Create data directory for database
RUN mkdir -p /app/data

# Environment variables with defaults
ENV PF_EMAIL=""
ENV PF_PASSWORD=""
ENV FLASK_HOST="0.0.0.0"
ENV FLASK_PORT="5000"
ENV LOG_INTERVAL="15"

# Expose Flask port
EXPOSE 5000

# Use the Python entrypoint script
COPY docker-entrypoint.py /app/docker-entrypoint.py

ENTRYPOINT ["python", "/app/docker-entrypoint.py"]