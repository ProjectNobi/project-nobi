# Project Nobi — API Dockerfile
# Python 3.12 slim with FastAPI + uvicorn

FROM python:3.12-slim AS base

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r nobi && useradd -r -g nobi -m nobi

WORKDIR /app

# Install Python deps (API + core)
COPY api/requirements.txt /app/api-requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/api-requirements.txt && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir gunicorn uvloop httptools

# Copy project source
COPY api/ /app/api/
COPY nobi/ /app/nobi/
COPY setup.py /app/setup.py

# Install project in editable mode
RUN pip install --no-cache-dir -e .

# Data directory
RUN mkdir -p /data && chown nobi:nobi /data
VOLUME /data

USER nobi

EXPOSE 8042

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8042/health || exit 1

# Run with gunicorn + uvicorn workers for production
CMD ["gunicorn", "api.server:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8042", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
