# syntax=docker/dockerfile:1

# Base image pinned by digest (python:3.13-slim, pulled 2026-10-25) and every dependency pinned by hash in
# requirements.lock: a rebuild installs exactly what was reviewed, or fails. Update both on purpose only.
FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOME=/tmp \
    HME_DATA_DIR=/data
RUN useradd --system --uid 10001 --user-group --home-dir /nonexistent --shell /usr/sbin/nologin hme \
 && install -d -o hme -g hme -m 700 /data

# Wheels only (no setup.py runs at build time), hash-checked
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.lock \
 && rm /tmp/requirements.lock

# The app itself is copied, not pip-installed, so no build backend is fetched unpinned
COPY src/hme_bitwarden /app/hme_bitwarden

USER hme
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('HME_PORT', '8000')}/healthz\", timeout=4)"]
ENTRYPOINT ["python", "-m", "hme_bitwarden"]
