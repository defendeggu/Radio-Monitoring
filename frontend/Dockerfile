# syntax=docker/dockerfile:1
# Build the Svelte UI and serve it with nginx (unprivileged, port 8080)

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# APRS symbol images: the aprs.fi set (github.com/hessu/aprs-symbols), pinned commit and
# checksums. Not in the repository: the symbols come from many sources with different or
# unknown licences, some are brand logos (see the COPYRIGHT.md of that repository).
FROM python:3.13-alpine AS aprs-symbols
ARG APRS_SYMBOLS_COMMIT=f2286a9cd43eb6ba4501250b4c39fff111e3796c
WORKDIR /work
RUN pip install --no-cache-dir pillow==11.3.0 \
 && for n in 0 1 2; do \
      wget -q -O "aprs-symbols-24-$n@2x.png" \
        "https://raw.githubusercontent.com/hessu/aprs-symbols/${APRS_SYMBOLS_COMMIT}/png/aprs-symbols-24-$n@2x.png"; \
    done \
 && printf '%s\n' \
      'b22875a93e0a114b4d4e6da1089349fabfc82cf0ceff78b5f3e2d72ef357847f  aprs-symbols-24-0@2x.png' \
      'cbc5d527fb3d063637a89ad06af5d923f6fcc9e616a8801e2be0aeb502d75d12  aprs-symbols-24-1@2x.png' \
      '97c73ed53e93a35a2be00ce84abf82c7e6fc4772388e1efd3c120c6ce594c4a5  aprs-symbols-24-2@2x.png' \
    | sha256sum -c -
COPY scripts/aprs_symbols.py /work/
RUN python3 aprs_symbols.py /work /out/aprs-symbols

FROM nginx:1.30.7-alpine
# Pull Alpine security fixes that the upstream image does not contain yet
# (the CI Trivy scan fails on fixable HIGH/CRITICAL findings)
RUN apk upgrade --no-cache
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/onair.conf /etc/nginx/conf.d/onair.conf
COPY nginx/aprsstats.conf /etc/nginx/conf.d/aprsstats.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=aprs-symbols /out/aprs-symbols /usr/share/nginx/html/aprs-symbols
USER nginx
EXPOSE 8080 8765 8092
CMD ["nginx", "-g", "daemon off;"]
