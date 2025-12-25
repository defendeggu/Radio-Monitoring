FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    libhackrf-dev \
    hackrf \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY radio_capture.py .
COPY transcription_service.py .
COPY api_service.py .
COPY .env.example .env

# Create recordings directory
RUN mkdir -p recordings

# Expose API port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the API service
CMD ["python", "api_service.py"]
