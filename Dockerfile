# --- Stage 1: build the React SPA ---
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.12-slim
WORKDIR /app

# Install the package + dependencies (from pyproject).
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Migrations live next to the app; db.py falls back to <cwd>/migrations.
COPY migrations/ ./migrations/
# Built SPA from stage 1.
COPY --from=frontend /fe/dist ./static

ENV APP_ENV=production \
    DB_PATH=/data/plantpal.db \
    IMAGE_DIR=/data/images \
    STATIC_DIR=/app/static \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

# Single worker: SQLite + the APScheduler digest job must run in one process.
CMD ["uvicorn", "plantpal.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
