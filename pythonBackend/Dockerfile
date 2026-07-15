# syntax=docker/dockerfile:1
#
# Production image for the HikeBuilder FastAPI backend.
# Build from the pythonBackend/ directory:
#   docker build -t hikebuilder-api .
#   docker run -p 8000:8000 --env-file .env hikebuilder-api
#
# On AWS, inject config as real env vars (Secrets Manager / SSM) instead of an
# .env file — DBConnection/main read the environment directly (see .env keys in
# CLAUDE.md / SECURITY_NOTES.md). NOTE: runs a single uvicorn worker on purpose —
# main.py starts an in-process APScheduler job that would otherwise run once per
# worker. Scale out with more tasks/instances only after moving that job out, or
# accept the (idempotent) duplication.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# curl is only for the container HEALTHCHECK. psycopg[binary] bundles libpq, so
# no system Postgres client libs are needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application code (see .dockerignore — .env, caches, ingestion tiles excluded).
COPY . .

# Drop root.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Liveness against the dependency-free /health endpoint (see main.py).
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# No --reload in production.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
