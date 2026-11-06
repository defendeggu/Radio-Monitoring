# syntax=docker/dockerfile:1
# RadioMoni API image (Python 3.13, Debian 13 "trixie")
#
#   docker build -t radiomoni-api .                       # runtime image
#   docker build --target test -t radiomoni-api-test .     # image with tests + dev tools
#   docker build --build-arg WITH_USRP=1 .                 # + UHD/GNU Radio for the USRP N200 (~1 GB)
#   docker build --build-arg WITH_CUDA=1 .                 # + CUDA libraries for Whisper on a GPU
#   docker build --build-arg WITH_SDRPLAY=1 .              # + SDRplay API (proprietary, downloaded from
#                                                          #   sdrplay.com; you accept its licence), SoapySDR

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

# --------------------------------------------------------------------------- SDRplay (optional)
# SDRplay RSP support (WITH_SDRPLAY=1): the SDRplay API is proprietary and may not be
# redistributed, so it is downloaded from sdrplay.com during your own build (checksum pinned)
# and never part of the repository. By building with WITH_SDRPLAY=1 you accept its licence
# (/opt/sdrplay_api/sdrplay_license.txt in the image). The installer's script is not run:
# the archive is unpacked and library, headers and service are copied. On top: SoapySDRPlay3
# (MIT) and sdrplay_rx (tools/sdrplay_rx.c). Without WITH_SDRPLAY the stage is empty.
FROM ${PYTHON_IMAGE} AS sdrplay-build
ARG WITH_SDRPLAY=0
ARG SDRPLAY_API_VERSION=3.15.2
ARG SDRPLAY_API_SHA256=3a97ca764263bbe76fb0f2220e6408942357e8864c19e1408a6d6987af382fe3
ARG SOAPY_SDRPLAY3_VERSION=soapy-sdrplay3-0.5.3
COPY tools/sdrplay_rx.c /src/sdrplay_rx.c
RUN mkdir -p /out  && if [ "$WITH_SDRPLAY" = "1" ]; then       apt-get update       && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates curl pkg-config            libsoapysdr-dev       && curl -fsSL -o /tmp/api.run "https://www.sdrplay.com/software/SDRplay_RSP_API-Linux-${SDRPLAY_API_VERSION}.run"       && echo "${SDRPLAY_API_SHA256}  /tmp/api.run" | sha256sum -c -       && lines=$(head -c 20000 /tmp/api.run | grep -a -o -m1 'head -n [0-9]*' | awk '{print $3}')       && offset=$(head -n "$lines" /tmp/api.run | wc -c)       && mkdir -p /tmp/api && tail -c +$((offset + 1)) /tmp/api.run | tar -xzf - -C /tmp/api       && arch=$(dpkg --print-architecture) && lib=$(basename /tmp/api/${arch}/libsdrplay_api.so.*)       && install -D -m 0644 /tmp/api/${arch}/${lib} /out/usr/local/lib/${lib}       && ln -s ${lib} /out/usr/local/lib/libsdrplay_api.so.3 && ln -s libsdrplay_api.so.3 /out/usr/local/lib/libsdrplay_api.so       && install -D -m 0755 /tmp/api/${arch}/sdrplay_apiService /out/opt/sdrplay_api/sdrplay_apiService       && install -D -m 0644 /tmp/api/sdrplay_license.txt /out/opt/sdrplay_api/sdrplay_license.txt       && mkdir -p /out/usr/local/include && cp /tmp/api/inc/*.h /out/usr/local/include/       && cp -a /out/usr/local/. /usr/local/ && ldconfig       && git clone --depth 1 --branch "${SOAPY_SDRPLAY3_VERSION}" https://github.com/pothosware/SoapySDRPlay3.git /src/soapy       && cmake -S /src/soapy -B /src/soapy/build -DCMAKE_BUILD_TYPE=Release       && cmake --build /src/soapy/build -j"$(nproc)"       && DESTDIR=/out cmake --install /src/soapy/build       && mkdir -p /out/usr/local/bin && gcc -O2 -Wall -Wextra -o /out/usr/local/bin/sdrplay_rx /src/sdrplay_rx.c $(pkg-config --cflags --libs SoapySDR);     fi

# --------------------------------------------------------------------------- runtime
FROM ${PYTHON_IMAGE} AS runtime
ARG WITH_USRP=0
ARG WITH_SDRPLAY=0

# SDR drivers and decoders:
#   hackrf, rtl-sdr, airspyhf  - SDR command line tools
#   direwolf, multimon-ng      - APRS / POCSAG
#   rtl-433, rtl-ais           - ISM sensors / AIS (RTL-SDR); readsb (ADS-B, RTL-SDR or HackRF) is built above
#   tini                       - PID 1, reaps decoder subprocesses
#   SoapySDR (WITH_SDRPLAY=1)  - SDRplay RSP through SoapySDRPlay3 and sdrplay_rx
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates libusb-1.0-0 tini \
      hackrf rtl-sdr airspyhf \
      direwolf multimon-ng \
      rtl-433 rtl-ais libncurses6 libzstd1 zlib1g \
 && if [ "$WITH_USRP" = "1" ]; then apt-get install -y --no-install-recommends uhd-host gnuradio; fi \
 && if [ "$WITH_SDRPLAY" = "1" ]; then apt-get install -y --no-install-recommends libsoapysdr0.8 soapysdr-tools libudev1; fi \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=readsb-build /src/readsb/readsb /usr/local/bin/readsb
COPY --from=sdrplay-build /out/ /
RUN ldconfig
COPY config/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

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

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
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
