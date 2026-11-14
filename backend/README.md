# backend/ — `errante_api` (FastAPI) · WS4

```bash
make api                     # = cd backend && uvicorn errante_api.main:app --reload --port 8000
open http://localhost:8000/docs
```

Datos servidos: `ERRANTE_DATA_DIR` si está definido; si no, `data/products` si existe; si no, `data/demo`.
CORS: `ERRANTE_CORS_ORIGINS` (coma-separado, default `*`; restringir en producción).

Endpoints: ver `docs/CONTRACT.md`. Tests: `pytest -q backend/tests`.
Deploy: TODO(WS4) — cualquier host Python (Render, Railway, Fly.io); instalar `pipeline` y `backend` juntos
(`pip install -e pipeline -e backend`) y arrancar con `uvicorn errante_api.main:app --host 0.0.0.0 --port $PORT`.
