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

# Copy source code and scripts
COPY --chown=voltagent:voltagent voltagent /app/voltagent
COPY --chown=voltagent:voltagent scripts /app/scripts
COPY --chown=voltagent:voltagent data/manifest.json /app/data/manifest.json

USER voltagent

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "voltagent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
