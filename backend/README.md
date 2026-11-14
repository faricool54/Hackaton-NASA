# backend/ — `errante_api` (FastAPI) · WS4

```bash
make api                     # = cd backend && uvicorn errante_api.main:app --reload --port 8000
open http://localhost:8000/docs
```

Datos servidos: `ERRANTE_DATA_DIR` si está definido; si no, `data/products` si existe; si no, `data/demo`.
CORS: `ERRANTE_CORS_ORIGINS` (coma-separado, default `*`; restringir en producción).

Endpoints: ver `docs/CONTRACT.md`. Tests: `pytest -q backend/tests`.
El backend actual sirve productos y expone búsqueda pendiente; **no construye aún secuencias por coordenadas**.
Para R03, WS4-5 implementará solicitudes RA/Dec/FOV y jobs con caché/progreso, conectados al build básico.
El servicio público de construcción forma parte de P0; JPL, espectros y operaciones son etapas posteriores.
Rutas/estados nuevos se definirán en WS4-10; no confundir propuestas con endpoints disponibles.
Deploy: TODO(WS4) — cualquier host Python (Render, Railway, Fly.io); instalar `pipeline` y `backend` juntos
(`pip install -e pipeline -e backend`) y arrancar con `uvicorn errante_api.main:app --host 0.0.0.0 --port $PORT`.
