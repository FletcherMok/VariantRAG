FROM python:3.13.7-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements-mutalyzer.lock /app/requirements-mutalyzer.lock
RUN pip install --no-cache-dir -r /app/requirements-mutalyzer.lock
WORKDIR /app
RUN printf "MUTALYZER_CACHE_DIR = '/cache'\n" > /app/mutalyzer-settings.py
ENV MUTALYZER_SETTINGS=/app/mutalyzer-settings.py
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "mutalyzer_api.endpoints:app"]
