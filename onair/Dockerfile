# syntax=docker/dockerfile:1
# OnAir (https://on-air.dev) headless server for RadioMoni: onair-server only, controlled by radio-api
# over its remote-control API. OnAir is GPL-3.0 with attribution terms (ADDITIONAL-TERMS.md of OnAir);
# it is not part of this repository: the official release .deb is downloaded at build time,
# pinned by version and checksum.
#
#   Based on OnAir by Kristijonas Adomaitis - https://on-air.dev
#   OnAir contributors: https://github.com/adswill/OnAir/blob/main/CONTRIBUTORS.md

FROM ubuntu:24.04

ARG ONAIR_VERSION=4.6.0
ARG ONAIR_DEB_SHA256=aec8854afc2477562250f95ade13f1d07ceaab113f4d108bf758fc093656ac3f

ENV DEBIAN_FRONTEND=noninteractive \
    ONAIR_NO_UPDATE_CHECK=1 \
    ONAIR_CODEC_DIR=/codecs \
    HOME=/data

RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    curl -fsSL --retry 5 -o /tmp/onair.deb \
      "https://github.com/adswill/OnAir/releases/download/v${ONAIR_VERSION}/onair_${ONAIR_VERSION}_amd64.deb"; \
    echo "${ONAIR_DEB_SHA256}  /tmp/onair.deb" | sha256sum -c -; \
    apt-get install -y --no-install-recommends /tmp/onair.deb soapysdr-module-hackrf; \
    # the desktop GUI and the scanner are not used here
    rm -f /usr/bin/onair /usr/bin/onair-scan /tmp/onair.deb; \
    rm -rf /var/lib/apt/lists/* /usr/share/man/*; \
    useradd --uid 1000 --create-home --home-dir /data --groups plugdev onair 2>/dev/null \
      || useradd --uid 1001 --create-home --home-dir /data --groups plugdev onair; \
    mkdir -p /codecs && chown onair: /data /codecs

COPY --chmod=0755 entrypoint.sh /usr/local/bin/onair-entrypoint

USER onair
WORKDIR /data
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS -o /dev/null http://127.0.0.1:8765/api/v1/status || exit 1
ENTRYPOINT ["/usr/local/bin/onair-entrypoint"]
