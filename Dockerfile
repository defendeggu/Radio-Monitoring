# syntax=docker/dockerfile:1
# RadioMoni API image (Python 3.13, Debian 13 "trixie")
#
#   docker build -t radiomoni-api .                       # runtime image
#   docker build --target test -t radiomoni-api-test .     # image with tests + dev tools
#   docker build --build-arg WITH_USRP=1 .                 # + UHD/GNU Radio for the USRP N200 (~1 GB)
#   docker build --build-arg WITH_CUDA=1 .                 # + CUDA libraries for Whisper on a GPU

ARG PYTHON_IMAGE=python:3.13-slim-trixie

# --------------------------------------------------------------------------- builder
FROM ${PYTHON_IMAGE} AS builder
ARG WITH_CUDA=0
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt \
 && if [ "$WITH_CUDA" = "1" ]; then pip install nvidia-cublas-cu12 'nvidia-cudnn-cu12==9.*'; fi

# --------------------------------------------------------------------------- readsb
# Debian's readsb package is built without RTL-SDR support, so build it from source
# with RTL-SDR and HackRF support.
FROM ${PYTHON_IMAGE} AS readsb-build
ARG READSB_VERSION=v3.16.17
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential git ca-certificates pkg-config \
      librtlsdr-dev libhackrf-dev libncurses-dev zlib1g-dev libzstd-dev \
 && git clone --depth 1 --branch "${READSB_VERSION}" https://github.com/wiedehopf/readsb.git /src/readsb \
 && make -C /src/readsb -j"$(nproc)" RTLSDR=yes HACKRF=yes \
 && /src/readsb/readsb --help | grep -q rtlsdr \
 && /src/readsb/readsb --help | grep -q hackrf-vgagain

# --------------------------------------------------------------------------- runtime
FROM ${PYTHON_IMAGE} AS runtime
ARG WITH_USRP=0

# SDR drivers and decoders:
#   hackrf, rtl-sdr, airspyhf  - SDR command line tools
#   direwolf, multimon-ng      - APRS / POCSAG
#   rtl-433, rtl-ais           - ISM sensors / AIS (RTL-SDR); readsb (ADS-B, RTL-SDR or HackRF) is built above
#   tini                       - PID 1, reaps decoder subprocesses
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates libusb-1.0-0 tini \
      hackrf rtl-sdr airspyhf \
      direwolf multimon-ng \
      rtl-433 rtl-ais libncurses6 libzstd1 zlib1g \
 && if [ "$WITH_USRP" = "1" ]; then apt-get install -y --no-install-recommends uhd-host gnuradio; fi \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=readsb-build /src/readsb/readsb /usr/local/bin/readsb

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/models \
    LD_LIBRARY_PATH=/opt/venv/lib/python3.13/site-packages/nvidia/cublas/lib:/opt/venv/lib/python3.13/site-packages/nvidia/cudnn/lib \
    AUDIO_OUTPUT_DIR=/app/recordings

WORKDIR /app

# Application code (no .env, no secrets — configuration comes from the environment)
COPY radiomoni/ radiomoni/
COPY config/gunicorn_config.py config/direwolf.conf ./
COPY scripts/elasticsearch/ scripts/elasticsearch/
COPY scripts/repeaters_ch.csv scripts/

RUN groupadd -r -g 1000 radiouser \
 && useradd -r -u 1000 -g radiouser -G plugdev,dialout -d /app radiouser \
 && mkdir -p /app/recordings /app/captures /app/models /app/data \
 && chown -R radiouser:radiouser /app/recordings /app/captures /app/models /app/data

USER radiouser
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=5).status == 200 else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "--config", "gunicorn_config.py", "radiomoni.api_service:app"]

# --------------------------------------------------------------------------- test
FROM runtime AS test
USER root
COPY requirements.txt requirements-dev.txt /tmp/
RUN pip install -r /tmp/requirements-dev.txt
COPY tests/ tests/
COPY scripts/*.py scripts/
COPY pyproject.toml requirements.txt requirements-dev.txt ./
RUN chown -R radiouser:radiouser /app
USER radiouser
ENV SKIP_REDIS_CHECK=1 ALLOW_INSECURE=true
CMD ["pytest", "-q"]
