# Multi-stage production Dockerfile for VoltAgent
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runner stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Security: non-root user
RUN groupadd -g 10001 voltagent && \
    useradd -u 10000 -g voltagent -s /bin/bash -m voltagent

# Copy installed packages from builder
COPY --from=builder /root/.local /home/voltagent/.local
ENV PATH=/home/voltagent/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000

# Copy source code, frontend UI, data, and scripts
COPY --chown=voltagent:voltagent voltagent /app/voltagent
COPY --chown=voltagent:voltagent frontend /app/frontend
COPY --chown=voltagent:voltagent data /app/data
COPY --chown=voltagent:voltagent scripts /app/scripts

# Pre-create writable index_cache directory for non-root user
RUN mkdir -p /app/data/index_cache && \
    chown -R voltagent:voltagent /app/data

USER voltagent

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request, os; p = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{p}/health')"

CMD ["sh", "-c", "uvicorn voltagent.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]


