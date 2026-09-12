# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/tsconfig.json frontend/next-env.d.ts frontend/next.config.mjs ./
COPY frontend/src ./src
RUN npm run build

FROM python:3.13.7-slim AS runtime
ENV PYTHONPATH=/app/backend \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VARIANTRAG_DATA=/app/backend/data/workbench \
    VARIANTRAG_UI=/app/frontend/out \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --only-binary=:all: -r requirements.lock \
    && useradd --uid 10001 --create-home app \
    && mkdir -p /app/backend/data/workbench \
    && chown -R app:app /app/backend/data
COPY backend/variantrag ./backend/variantrag
COPY --from=frontend /frontend/out ./frontend/out
COPY LICENSE THIRD_PARTY.md /app/
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "variantrag.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
