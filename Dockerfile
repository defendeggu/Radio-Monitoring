FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    libhackrf-dev \
    hackrf \
    build-essential \
    git \
    direwolf \
    libasound2-dev \
    cmake \
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
COPY aprs_decoder_service.py .
COPY api_service.py .
COPY database_service.py .
COPY migrate_json_to_db.py .
COPY direwolf.conf .
COPY .env.example .env

# Create recordings directory
RUN mkdir -p recordings

# Expose API port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the API service
CMD ["python", "api_service.py"]
