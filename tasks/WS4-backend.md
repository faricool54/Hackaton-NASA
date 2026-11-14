# WS4 · Backend API, integración y CI

**Objetivo:** API estable sobre los productos, endpoints en vivo robustos (IRSA/JPL lentos o caídos no deben
romper nada), deploy, y ser quien **mantiene `main` verde** e integra el trabajo de todos.

**Tus rutas:** `backend/` · `.github/workflows/` · `Makefile` · deploy (Render/Railway/Fly/…) · coordinación de
`pipeline/errante/products.py` y `build.py`.

**Recibís:** productos en `data/products` / `data/demo` (contrato), funciones de WS1 (`search_frames`) y WS3
(`objects_in_frame`). **Entregás:** `/api/*` documentado (OpenAPI en `/docs`), deploy público del backend (si se usa).

**Leé primero:** `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `backend/errante_api/**`, `docs/WORKFLOW.md`.

## Estado actual
- ✅ `/api/health`, `/api/manifest`, `/api/fields/{id}`, `/candidates`, `/known`, `/data/*` (con tests).
- ⛔ `/api/search`, `/api/known-objects` devuelven 501 hasta que WS1/WS3 implementen.

## Tareas

- [ ] **WS4-1 (P0) Coordinación**: completar `docs/TEAM.md`, proteger `main` (requerir CI verde + 1 review),
  revisar PRs de contrato.
- [ ] **WS4-2 (P0) Endpoints en vivo robustos**: timeouts, caché en memoria (TTL) + disco, errores 502/504 con
  JSON claro, límite de concurrencia hacia IRSA. *Acepta:* tests con funciones mockeadas (lento, error, ok).
- [ ] **WS4-3 (P0) Integración continua de campos reales**: script/target `make build-fields` que construya los
  campos de `fields.toml` y valide (`errante validate --dir data/products`). Ayudar a WS1/WS2 a cerrar I1/I2.
- [ ] **WS4-4 (P1) Deploy** del backend (si el producto lo usa) con `ERRANTE_DATA_DIR` y CORS restringido al
  dominio del frontend. Documentar en `backend/README.md`.
- [ ] **WS4-5 (P1) `/api/fields` on-demand** (P2 si no hay tiempo): construir un campo nuevo para coordenadas
  arbitrarias en background (job id + polling), reutilizando `build.build_field`.
- [ ] **WS4-6 (P1) GitHub Pages / Vercel** para el frontend estático (con WS6): workflow que construye
  `frontend/` con `VITE_BASE` y publica.
- [ ] **WS4-7 (P2) `/api/limits`** cuando WS2 defina el contrato de límites.

## Prompt de arranque

> Sos el agente del workstream WS4 (backend e integración) del repo Errante para NASA Space Apps 2026. Leé
> `AGENTS.md`, `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/WORKFLOW.md` y `tasks/WS4-backend.md`.
> Trabajá SOLO en `backend/`, `.github/` y `Makefile`. Empezá por WS4-2: hacé robustos `/api/search` y
> `/api/known-objects` (timeouts, caché, errores claros) con tests que mockeen las funciones de WS1/WS3. No
> cambies el contrato sin un PR `contract:`. Corré `make check` y mostrame el diff antes de commitear.
