# Multi-stage build for optimized image size
# Stage 1: Builder - Install build dependencies and compile Python packages
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    cmake \
    libusb-1.0-0-dev \
    libhackrf-dev \
    librtlsdr-dev \
    libairspyhf-dev \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip to fix CVE-2025-8869
RUN pip install --upgrade pip==25.3

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime - Minimal image with only runtime dependencies
FROM python:3.11-slim

# Install only runtime dependencies (no -dev packages, no build tools)
# Updated: Added Airspy HF+ support (libairspyhf1, airspyhf)
RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    libhackrf0 \
    hackrf \
    rtl-sdr \
    librtlsdr0 \
    libairspyhf1 \
    airspyhf \
    direwolf \
    multimon-ng \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY logging_config.py .
COPY sdr_hardware.py .
COPY transcription_service.py .
COPY aprs_decoder_service.py .
COPY pocsag_decoder_service.py .
COPY streaming_decoder_service.py .
COPY api_service.py .
COPY elasticsearch_service.py .
COPY repeater_activity_analyzer.py .
COPY scan_session_manager.py .
COPY session_store.py .
COPY maidenhead_grid.py .
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
