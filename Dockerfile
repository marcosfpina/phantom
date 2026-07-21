# Stage 1: Build
FROM python:3.13-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir build && \
    python -m build --wheel

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /app

# Install system deps + build tools (numpy builds from source on py3.13)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy wheel from builder and install dependencies
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Strip build tools to keep image lean
RUN apt-get remove -y build-essential python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r phantom && useradd -r -g phantom phantom
USER phantom

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "phantom.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
