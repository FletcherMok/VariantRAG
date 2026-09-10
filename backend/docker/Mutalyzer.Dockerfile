FROM python:3.13.7-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements-mutalyzer.lock /tmp/requirements.lock
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r /tmp/requirements.lock
FROM python:3.13.7-slim
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels && useradd --create-home app && mkdir /cache && chown app /cache
COPY scripts/patch_mutalyzer_metadata.py /app/patch_mutalyzer_metadata.py
RUN python /app/patch_mutalyzer_metadata.py
COPY backend/variantrag /app/variantrag
RUN printf "MUTALYZER_CACHE_DIR = '/cache'\n" > /app/mutalyzer-settings.py
ENV MUTALYZER_SETTINGS=/app/mutalyzer-settings.py
USER app
CMD ["uvicorn", "variantrag.normalizer_api:app", "--host", "0.0.0.0", "--port", "5000", "--limit-concurrency", "2"]
