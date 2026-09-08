# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14-slim-trixie
ARG UV_VERSION=0.11.17
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:${PYTHON_VERSION} AS build
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md MANIFEST.in ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:${PYTHON_VERSION} AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends tini ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 wwwmin \
    && useradd --uid 10001 --gid 10001 --home-dir /home/wwwmin --create-home wwwmin \
    && mkdir -p /data/wwwmin /config/wwwmin \
    && chown -R wwwmin:wwwmin /data
COPY --from=build /app/.venv /app/.venv
COPY docker/entrypoint.py /app/entrypoint.py
ENV PATH=/app/.venv/bin:$PATH \
    XDG_CONFIG_HOME=/config \
    XDG_DATA_HOME=/data \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER wwwmin
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
ENTRYPOINT ["/usr/bin/tini", "--", "python", "/app/entrypoint.py"]
