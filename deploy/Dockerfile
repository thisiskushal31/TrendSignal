# TrendSignal — Web API (upload UI + POST /analyze)
# Build from repo root: docker build -f deploy/Dockerfile .
# Step 1: install deps (cached until app/requirements.txt changes)
# Step 2: copy only app (smaller layer, faster rebuilds)
FROM python:3.13-slim

WORKDIR /app

# -----------------------------------------------------------------------------
# Step 1: Install dependencies only (layer cached when code changes)
# -----------------------------------------------------------------------------
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Step 2: Copy app package and static files
# -----------------------------------------------------------------------------
COPY app/ ./app/

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8001"]
