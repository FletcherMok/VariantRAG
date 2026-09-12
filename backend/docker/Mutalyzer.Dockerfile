FROM python:3.13.7-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git cmake && rm -rf /var/lib/apt/lists/*
COPY requirements-mutalyzer.lock /tmp/requirements.lock
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r /tmp/requirements.lock
FROM python:3.13.7-slim
WORKDIR /app
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-cache-dir /wheels/* && useradd --uid 10001 --create-home app && mkdir /cache && chown app /cache
COPY scripts/patch_mutalyzer_metadata.py /app/patch_mutalyzer_metadata.py
RUN python /app/patch_mutalyzer_metadata.py
COPY backend/variantrag /app/variantrag
RUN printf "MUTALYZER_CACHE_DIR = '/cache'\n" > /app/mutalyzer-settings.py
ENV MUTALYZER_SETTINGS=/app/mutalyzer-settings.py PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4)"
COPY LICENSE THIRD_PARTY.md /app/
USER app
CMD ["uvicorn", "variantrag.normalizer_api:app", "--host", "0.0.0.0", "--port", "5000", "--limit-concurrency", "2", "--no-proxy-headers"]
