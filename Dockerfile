FROM python:3.13-slim-bookworm
ARG VERSION=0.3.2-alpha.1
ARG REVISION=unknown
LABEL org.opencontainers.image.title="Downrange" \
      org.opencontainers.image.description="Self-hosted launch visibility research and push alerts" \
      org.opencontainers.image.source="https://github.com/spikked27/downrange" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data PUID=99 PGID=100 TZ=America/New_York HOME=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends gosu ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts/entrypoint.sh /usr/local/bin/downrange-entrypoint
RUN chmod 755 /usr/local/bin/downrange-entrypoint && mkdir /data
EXPOSE 8097
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8097/healthz',timeout=3)" || exit 1
ENTRYPOINT ["/usr/local/bin/downrange-entrypoint"]
CMD ["uvicorn","app.server:app","--host","0.0.0.0","--port","8097","--workers","1","--no-access-log","--no-proxy-headers"]
