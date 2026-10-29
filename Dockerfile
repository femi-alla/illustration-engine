# syntax=docker/dockerfile:1.7
# Multi-stage build: dependencies are built once, the runtime image is slim and non-root.

FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install . \
    # The runtime never installs anything, so drop the installers (and their vendored
    # libraries, which image scanners otherwise flag) from the virtualenv.
    && /opt/venv/bin/pip uninstall -y pip setuptools wheel

FROM python:3.12-slim AS runtime
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown
LABEL org.opencontainers.image.title="illustration-engine" \
      org.opencontainers.image.description="Educational life insurance illustration engine" \
      org.opencontainers.image.source="https://github.com/femi-alla/illustration-engine" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="MIT"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GIT_SHA=${GIT_SHA} \
    BUILD_TIME=${BUILD_TIME} \
    PORT=8080

RUN groupadd --system app && useradd --system --gid app --uid 10001 --home /app app \
    && python -m pip uninstall -y pip setuptools
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else 1)"

CMD ["sh", "-c", "uvicorn illustration_engine.api:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
