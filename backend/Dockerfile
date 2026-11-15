FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
COPY data/demo /app/data/demo
COPY data/products /app/data/products
ENV VITE_DATA_MODE=api VITE_DATASET=real VITE_API_BASE=/ VITE_BASE=/
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ERRANTE_DEMO_DIR=/app/data/demo ERRANTE_PRODUCTS_DIR=/app/data/products \
    ERRANTE_CACHE_DIR=/app/runtime/cache ERRANTE_DATA_DIR=/app/runtime/products \
    ERRANTE_SEED_DIR=/app/data/products ERRANTE_SEARCH_SNAPSHOTS=/app/data/index/search \
    ERRANTE_WEB_DIR=/app/web ERRANTE_ENABLE_JOBS=1 ERRANTE_SEARCH_DEADLINE_S=25 PORT=8000
WORKDIR /app
COPY pipeline/pyproject.toml /app/pipeline/pyproject.toml
COPY pipeline/errante /app/pipeline/errante
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/errante_api /app/backend/errante_api
RUN pip install --no-cache-dir -e 'pipeline[science]' -e backend
COPY data/demo /app/data/demo
COPY data/products /app/data/products
COPY data/index /app/data/index
COPY --from=web /app/frontend/dist /app/web
RUN mkdir -p /app/runtime/products /app/runtime/cache && chown -R 10001:10001 /app/runtime
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health',timeout=3)"
CMD ["python", "-m", "errante_api.serve"]
