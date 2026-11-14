FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ERRANTE_DEMO_DIR=/app/data/demo ERRANTE_PRODUCTS_DIR=/app/data/products \
    ERRANTE_CACHE_DIR=/app/data/cache PORT=8000
WORKDIR /app
COPY pipeline/pyproject.toml /app/pipeline/pyproject.toml
COPY pipeline/errante /app/pipeline/errante
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/errante_api /app/backend/errante_api
RUN pip install --no-cache-dir -e 'pipeline[science]' -e backend
COPY data/demo /app/data/demo
RUN mkdir -p /app/data/products /app/data/cache && chown -R 10001:10001 /app/data
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health',timeout=3)"
CMD ["python", "-m", "errante_api.serve"]
