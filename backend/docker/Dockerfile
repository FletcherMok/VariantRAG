FROM python:3.13.7-slim
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
RUN useradd --create-home app && mkdir -p /app/backend/data && chown -R app /app/backend
COPY backend /app/backend
COPY tests/fixtures /app/tests/fixtures
ENV PYTHONPATH=/app/backend
USER app
CMD ["python", "-m", "uvicorn", "variantrag.api:app", "--host", "0.0.0.0", "--port", "8000"]
