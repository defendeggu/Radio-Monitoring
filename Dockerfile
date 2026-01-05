FROM python:3.11-slim

# Install system dependencies (HackRF + RTL-SDR)
RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    libhackrf-dev \
    hackrf \
    rtl-sdr \
    librtlsdr-dev \
    build-essential \
    git \
    direwolf \
    multimon-ng \
    libasound2-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Upgrade pip to fix CVE-2025-8869
RUN pip install --upgrade pip==25.3

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY sdr_hardware.py .
COPY transcription_service.py .
COPY aprs_decoder_service.py .
COPY pocsag_decoder_service.py .
COPY streaming_decoder_service.py .
COPY api_service.py .
COPY elasticsearch_service.py .
COPY repeater_activity_analyzer.py .
COPY scan_session_manager.py .
COPY gunicorn_config.py .
COPY direwolf.conf .
COPY .env.example .env
COPY scripts/ scripts/
COPY blueprints/ blueprints/

# Create recordings directory
RUN mkdir -p recordings captures

# Create non-root user for security
# Note: We need access to USB devices, so user must be in plugdev/dialout groups
RUN groupadd -r radiouser && \
    useradd -r -g radiouser -G plugdev,dialout -u 1000 radiouser && \
    chown -R radiouser:radiouser /app && \
    chown -R radiouser:radiouser /app/recordings /app/captures

# Switch to non-root user
USER radiouser

# Expose API port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the API service with Gunicorn (production WSGI server)
CMD ["gunicorn", "--config", "gunicorn_config.py", "api_service:app"]
