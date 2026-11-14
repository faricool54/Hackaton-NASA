# WS4 · Backend, deploy y coordinación de `main`

> Prioridades y alcance: manda [`docs/PLAN.md`](../docs/PLAN.md). Leyenda: ✅ verificado 2026-11-14 ·
> 📄 según documentación · ❓ abierto.

## Objetivo

Que **"RA/Dec → video" ande en una URL pública**. Como IRSA no envía CORS ✅, el backend FastAPI pasa a ser
**proxy + procesador con caché**: `GET /api/view` arma un `Field` efímero llamando a `build_patch` (WS2) con los
datos de WS1, y la segunda vez responde al instante. Además: deploy público de backend y frontend, CI igual a
`python scripts/dev.py check`, y `main` siempre verde.

## Tus rutas

| WS | Rutas (dueño) |
|---|---|
| **WS4** Backend+deploy+coordinación | `backend/**`, `.github/**`, `Makefile`, `scripts/**`, config de deploy; coordina `main` (mergea `contract:`/`chore:`, revierte si se rompe; los PR de carpeta propia los mergea su autor) |
| **Coordinación** (quien coordine, sugerido WS4) | `AGENTS.md`, `CLAUDE.md`, `README.md` (resto), `docs/PLAN.md`, `docs/KICKOFF.md`, `docs/TEAM.md`, `docs/WORKFLOW.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACT.md`, `docs/REVIEW-*.md`, `tasks/README.md` |
| **CONTRATO** (solo vía PR `contract:`) | `pipeline/errante/models.py`, `pipeline/errante/products.py`, `shared/schema/**`, `frontend/src/api/types.ts`, `data/demo/**` (se regenera con `python scripts/dev.py demo`), `pipeline/tests/test_contract.py` |

El contrato no es tuyo: lo revisás (con WS2 y WS5) en el PR de WS3. Tabla completa:
[`tasks/README.md`](README.md). Marcá casillas solo en este archivo.

## Recibís / Entregás

| Recibís | De | Mientras no está |
|---|---|---|
| `search_frames` (SIA2 VOTable + TAP fallback, colecciones `ERRANTE_COLLECTIONS`) y `read_patch` (Range en S3) | WS1 | `monkeypatch` en tests |
| `build_patch(ra, dec, fov, …)` en `pipeline/errante/build.py` → `Field` + PNGs | WS2 | modo fake con `data/demo` (WS4-4) |
| Lógica de fotometría (P1) y `objects_in_frame` | WS3 | 501 limpio + tests con mock |
| Contrato 0.3.0 (`Field.query`, `Frame.kind`, `Release` como `str`, …) | PR `contract:` de WS3 | responder 0.1.0 |
| Golden fields de los 5 objetivos en `data/products/` | WS2 (`cli.py build`) + WS3 | `data/demo` |

**Entregás:** `GET /api/view` (P0) y `GET /api/photometry` (P1) documentados en `/docs` (OpenAPI) y en
`docs/CONTRACT.md`; URLs públicas de backend y frontend (dom 12:00); CI = `python scripts/dev.py check`;
`main` protegida y verde.

## Leé primero

[`AGENTS.md`](../AGENTS.md) · [`docs/PLAN.md`](../docs/PLAN.md) §2 (arquitectura), §3 (contrato), §4–§5 ·
[`docs/CONTRACT.md`](../docs/CONTRACT.md) (API y errores de 0.3.0) ·
[`docs/REVIEW-2026-11-14.md`](../docs/REVIEW-2026-11-14.md) §4 Backend, CI y entorno ·
`backend/errante_api/**` · `backend/tests/test_api.py` · `scripts/dev.py` · `scripts/owners.py` ·
`.github/workflows/ci.yml` · [`docs/COLLABORATION.md`](../docs/COLLABORATION.md) ·
[`docs/WORKFLOW.md`](../docs/WORKFLOW.md).

## Estado actual

**Anda** (leído en el código): `create_app(Settings)` inyectable; `/api/health`, `/api/manifest`,
`/api/fields/{id}` (+ `/candidates`, `/known`) con `response_model`; `/data/*` con `StaticFiles` (Starlette 1.10
tiene guarda contra traversal ✅); tests de productos. CI verde (run 43601667320 ✅).

**Falta:** `/api/view` y `/api/photometry` no existen. `/api/search` y `/api/known-objects` devuelven 501
(stubs de WS1/WS3).

**Problemas (con línea):**
- `routes/live.py:26-29,42-45` solo traduce `NotImplementedError`: un timeout o un 5xx de IRSA termina en 500
  sin JSON. No hay timeout propio, caché ni semáforo. `HTTP_TIMEOUT_S` = 120 s por defecto
  (`pipeline/errante/settings.py:34`).
- `field_id` llega sin validar a `ProductStore.field_dir` (`routes/products.py:33-51`,
  `pipeline/errante/products.py:39-40`). En Windows `..\..\x` escapa del `data_dir` (✅ con pathlib); que uvicorn
  entregue `%5C` decodificado como `\` es ❓.
- `settings.py:24`: `ERRANTE_CORS_ORIGINS` se parte sin `strip()` (default `*`). `main.py:52`: `/api/health`
  expone la ruta absoluta del `data_dir`. `main.py:58-59`: `/data` solo se monta si el directorio existe al arrancar.
- `tests/test_api.py:37-39` acepta 200 de `/api/search`: cuando WS1 implemente, CI va a consultar IRSA
  (TAP tarda 8–19 s ✅).
- `ci.yml` (copia local, sin commitear): ya tiene `push` solo a `main`, `pull_request`, `workflow_dispatch`,
  `permissions: contents: read`, `concurrency` y un job `owners` informativo. Falta: no corre en Windows, no corre
  `dev.py check` (no lintea `scripts/` ni corre la guardia), y usa `checkout@v4`, `setup-python@v5`,
  `setup-node@v4`, que dieron el aviso "Node.js 20 is deprecated" ✅.

**Repo y entorno ✅:** no existe `main` (default = `claude/affectionate-gauss-rsem1g`), sin protección, merge
commits permitidos, sin auto-delete de ramas, solo labels por defecto (la plantilla de issue usa `task`, que no
existe), 5 colaboradores. `make` no está instalado en Windows. En la copia local, sin commitear:
`scripts/dev.py` (con `API_PORT` y `--reload-dir ../pipeline/errante` en `api`, y la tarea `owners`),
`scripts/owners.py` (guardia de ownership), `.gitattributes`, el `Makefile` como wrapper de `dev.py`, el
`ci.yml` nuevo y [`docs/COLLABORATION.md`](../docs/COLLABORATION.md).

**Hechos externos ✅:** IRSA (TAP, SIA, cutouts) no manda `Access-Control-*`; S3 `nasa-irsa-spherex`
(us-east-1) sí, con `Range`. SIA 1–4 s; S3 por Range ≈ 0,4 MB / ≈ 1 s por frame a 5′; cutout IBE ≈ 4 MB / 4–15 s.

## Tareas

- [ ] **WS4-1 (P0) `main` y reglas del repo** — antes de que se abran ramas (si ya lo hizo quien coordina,
  verificá y tildá).
  - ✅ `main` creada, default, squash-only, auto-delete de ramas y **protegida** (PR + checks `python`/`frontend`,
    historia lineal, sin force-push). Cuándo hace falta un OK: [`docs/COLLABORATION.md`](../docs/COLLABORATION.md) §2.
  - ✅ Ya en `main` (PR `chore:` de preparación): `scripts/dev.py`, `scripts/owners.py` (alineado con la tabla
    de `AGENTS.md`, incluye `data/products/` → WS2 y el bloque WS7), `.gitattributes`, `Makefile` wrapper,
    `ci.yml` con `concurrency`/`permissions`/job `owners`, `.claude/settings.json` compartido, protección de `main`
    (PR + checks `python`/`frontend`, historia lineal, solo squash, borrar rama al mergear).
  - Mantener `scripts/owners.py` y la tabla de `AGENTS.md` siempre iguales (si cambia una, cambia la otra).
  - Labels `ws1`…`ws6`, `contract`, `task` (la reserva de tareas es por issue asignado, ver `tasks/README.md`).
  - Si coordinás: `docs/TEAM.md` en el kickoff, revisión de PRs `contract:` y `chore:`, destrabar merges (reglas
    en [`docs/COLLABORATION.md`](../docs/COLLABORATION.md) §2), sync de 10 min cada ~4 h, cambios de alcance
    anotados en `docs/PLAN.md`.
  - *Acepta:* `main` es la default y tiene todo lo anterior; un push directo a `main` es rechazado (o, si la
    protección no está disponible, se avisa en el chat y se anota en COLLABORATION); `make check` y
    `py scripts/dev.py check` corren lo mismo.

- [ ] **WS4-2 (P0) Tests sin red.** Mockear con `monkeypatch.setattr("errante.data.irsa.search_frames", fake)` y
  `errante.science.known_objects.objects_in_frame` (funciona porque `live.py` importa dentro de la función ✅).
  Escenarios: ok → 200, lento → 504, error upstream → 502, `NotImplementedError` → 501. Borrar el test de
  `test_api.py:37-39`. Todo lo que use red: `@pytest.mark.network`.
  *Acepta:* `python scripts/dev.py test-py` pasa sin conexión a internet.

- [ ] **WS4-3 (P0) Endurecer la API antes de exponerla.**
  - `field_id: str = Path(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")` en `routes/products.py` (mismo slug que
    `SkyField.id`, `models.py:191`). Defensa en profundidad en `ProductStore.field_dir` → PR `contract:` aparte.
  - Handlers según la tabla de errores de [`docs/CONTRACT.md`](../docs/CONTRACT.md): el 422 de validación de
    FastAPI pasa a `400 {detail}` (así `422` queda solo para "ningún frame cubre la posición"), y `Exception` →
    `500 {detail}` que salga con cabeceras CORS (❓ inferido: hoy los 500 de Starlette salen por fuera de
    `CORSMiddleware` y el navegador los ve como error de CORS).
  - CORS: `[o.strip() for o in env.split(",") if o.strip()]`; en producción, orígenes explícitos (sin `*`).
  - `/api/health` sin ruta absoluta. `/data` montado siempre (crear el directorio si falta). `det` en 1..6.
  - *Acepta:* tests con `..`, `..%5C..%5Cx` y `%2E%2E` → 400/404 (verificá que el pedido llegue al handler: el
    cliente HTTP podría normalizar `..` ❓); un `Origin` permitido recibe `access-control-allow-origin` y uno no
    permitido no; una excepción forzada → 500 JSON; `/api/health` no contiene rutas del disco.

- [ ] **WS4-4 (P0) `GET /api/view`** — el corazón del producto (hito I1, sáb 20:00).
  - Params según [`docs/CONTRACT.md`](../docs/CONTRACT.md) (`GET /api/view`): `ra` [0, 360), `dec` [−90, 90],
    `fov_arcmin` (default y tope se fijan en el PR de contrato; el costo crece con las filas leídas: 5′ ≈ 0,4 MB y
    1° ≈ 4,8 MB por exposición ✅; WISE 0855 está ~2,1′ al oeste de la coordenada del enunciado ✅), `det` (un
    entero 1–6 por pedido en P0), `group=season|exposure` (default `season`), `collections` (P1).
  - Llama a `build_patch` (WS2) importándolo **dentro** de la función, como `live.py`, para poder mockearlo.
  - Id determinista `v-<ra>-<dec>-<fov>-d<det>-<group>` que cumpla `^[a-z0-9][a-z0-9-]*$` (sin `.` ni `+`; la
    codificación exacta se fija en el PR de contrato 0.3.0).
  - Caché en disco: `data/cache/views/fields/<id>/` (root = `ERRANTE_CACHE_DIR/views`, layout de `ProductStore`);
    clave = (ra, dec redondeados, fov, det, group, colecciones). Un hit no llama a `build_patch`. Las vistas
    nunca entran al `manifest`.
  - Concurrencia: lock por clave (dos pedidos iguales esperan el mismo build) + semáforo global de builds (y por
    lo tanto de consultas a IRSA) con espera acotada; si no entra en el presupuesto de tiempo → 504 (o proponer
    `503` + `Retry-After` en el PR de contrato). Los límites internos (≤ 16 conexiones S3, ≤ 6 hilos IBE) son de WS1.
  - Tiempo: presupuesto total configurable (p. ej. `ERRANTE_VIEW_TIMEOUT_S`), menor que el corte de la plataforma
    (❓ al elegir host). Si se pasa → 504, pero el build sigue en segundo plano y queda en caché.
  - Errores (tabla de CONTRACT): parámetros inválidos o fuera de tope → `400 {detail, hint}`; ningún frame cubre
    la posición → `422 {detail}`; `requests.HTTPError`/`ConnectionError` → `502 {detail, upstream}`;
    `requests.Timeout`/`TimeoutError` → `504 {detail, upstream}`; `NotImplementedError` → 501.
  - PNGs: hoy `/data` solo monta los productos. Servir `data/cache/views` donde los busca el cliente en modo api
    (`/data/fields/<id>/<rel>`, `frontend/src/api/client.ts:71-74`) o en otra ruta acordada con WS5 (p. ej.
    `/views/fields/<id>/<rel>`), con la misma validación de slug y traversal. Se decide en el PR de contrato.
  - Hasta que WS2 tenga `build_patch`: modo fake detrás de una variable de entorno que devuelve un campo de
    `data/demo` con `provenance.synthetic = true` (el badge se ve). Nunca activo en el deploy.
  - *Acepta:* tests con `build_patch` mockeado (ok, sin frames → 422, timeout → 504, upstream → 502, hit sin
    llamar a `build_patch`, dos pedidos simultáneos = un solo build); con WS1+WS2 reales, `/api/view` de Barnard
    (`ra=269.44623&dec=4.76870`, centro de `fields.toml`, 1 detector, `group=season`) se ve en el frontend.

- [ ] **WS4-5 (P0) Deploy público** (hito dom 12:00). Desplegá el esqueleto ya el sábado para descubrir
  problemas temprano y redesplegá seguido.
  - Backend: host Python en US-East (el bucket está en us-east-1 ✅): Render, Railway o Fly. Necesita disco
    persistente para `ERRANTE_CACHE_DIR`, Python 3.12 (igual que CI), `pipeline` + `backend` instalados en modo
    editable (ver Gotchas) + lo que pida `build_patch`, y arranque con
    `uvicorn errante_api.main:app --host 0.0.0.0 --port $PORT`. ❓ qué plataforma da astropy + disco + requests
    largos en plan gratis; ❓ si el plan "duerme" la instancia (si duerme: WS4-9 antes de grabar y de juzgar).
  - Variables: `ERRANTE_DATA_DIR` (golden fields), `ERRANTE_CACHE_DIR` (disco), `ERRANTE_CORS_ORIGINS` (origen
    exacto del frontend), `ERRANTE_COLLECTIONS` (WS1).
  - Frontend estático: GitHub Pages (`VITE_BASE=/<repo>/`), Vercel o Netlify (base `/`). Build con
    `VITE_API_BASE=<url del backend>` y `VITE_DATASET=real` cuando existan los golden fields. ❓ Pages con el repo
    privado (depende del plan de GitHub; si WS6 hace público el repo, no aplica).
  - Workflow en `.github/` o integración Git de la plataforma. Documentar en `backend/README.md` (comandos
    neutros: sin `open`, que es solo macOS; `python scripts/dev.py api` en vez de `make api`).
  - *Acepta:* en incógnito, en desktop y en el celular: la URL del frontend abre, un golden field se ve sin
    backend, `/api/view` de un objetivo responde desde la URL pública y `/api/health` no expone rutas.

- [ ] **WS4-6 (P1) `GET /api/photometry?ra&dec[&det][&radius_arcsec]`** → `{center, points: SpectrumPoint[]}`
  con `{frame_id, mjd, season, detector, wavelength_um, bandwidth_um, flux_mjy, flux_err_mjy, flags}` (CONTRACT),
  reutilizando los frames que ya leyó `/api/view` (misma caché). La lógica es de WS3; vos la cableás con los
  mismos timeouts, errores y semáforo. *Acepta:* tests con mock; con datos reales, RW Aur o R Dra devuelven puntos
  de varias temporadas.
- [ ] **WS4-7 (P1) CI = `dev.py check` + Windows.** Sobre el `ci.yml` nuevo (que ya tiene `concurrency`,
  `permissions` y el job `owners`): matriz `ubuntu-latest` + `windows-latest` que corra
  `python scripts/dev.py setup` y `python scripts/dev.py check`; acciones en versiones que corran en Node 24
  (verificar la versión exacta de cada una). Si cambian los nombres de los jobs, actualizar los checks requeridos
  de la protección. *Acepta:* un PR muestra ambos OS en verde y un solo run por push.
- [ ] **WS4-8 (P1) Puerto configurable** — ya está en la copia local de `dev.py` (`API_PORT`, `--reload-dir`).
  *Acepta:* en `main`, dos backends en la misma máquina (dos worktrees) en puertos distintos, y un cambio en
  `pipeline/errante/` recarga el backend.
- [ ] **WS4-9 (P1) Precalentar la caché.** Script en `scripts/` (p. ej. `scripts/warm_views.py --base <url>`) que
  pide `/api/view` de los 5 objetivos con los parámetros por defecto. Correrlo después de cada deploy y antes de
  grabar el video y del juzgamiento. *Acepta:* el segundo pedido de cada objetivo sale de caché (log sin
  llamadas a IRSA/S3).
- [ ] **WS4-10 (P1) Proxy de catálogos, solo si WS3/WS5 lo piden.** Gaia DR3 vía VizieR CfA no lo necesita
  (tiene CORS ✅). CatWISE (IRSA TAP `catwise_2020`) y la TAP de ESA Gaia no tienen CORS ✅ → endpoint con caché,
  timeout y semáforo. *Acepta:* test con mock; respuesta < timeout del frontend.
- [ ] **WS4-11 (P2)** `Cache-Control` largo para los PNG de vistas (inmutables por id); tope de tamaño de la
  caché en disco; `CODEOWNERS` con los logins; `.claude/settings.json` compartido (allow/deny; archivo de
  coordinación).
  *Acepta:* el segundo pedido de un PNG de vista responde con `Cache-Control` largo; superar el tope de la caché
  borra lo más viejo (test).
- [ ] **WS4-12 (P2)** Solo si `/api/view` no entra en el corte de la plataforma: `202` + polling del mismo id (o
  frames progresivos).
  *Acepta:* con `build_patch` mockeado lento, el primer pedido devuelve `202` y el polling del mismo id termina en
  `200` con el `Field`.

## DROP

- `/api/limits` (inyección-recuperación: fuera del enunciado).
- Sistema de jobs con progreso para `/api/fields` on-demand (ex WS4-5): lo reemplaza `/api/view` síncrono con
  caché; queda como WS4-12 (P2) solo si hace falta.
- Target `build-fields` en el Makefile: los golden fields se construyen con `errante build <target>` (WS2) y
  `python scripts/dev.py validate` ya valida `data/products` cuando existe ✅.

## Gotchas

- `Release` es `Literal["dr1","qr2","qr3","synthetic"]` en 0.1.0 (`models.py:30`): si `ERRANTE_COLLECTIONS`
  incluye `*_deep` antes de que se mergee 0.3.0 (que lo pasa a `str` con patrón), el `response_model` da 500.
- `errante.settings.REPO_ROOT` sale de la ubicación del archivo (`pipeline/errante/settings.py:8`): con una
  instalación **no editable** los defaults de `data/` apuntan a `site-packages`. En el deploy: instalación
  editable o `ERRANTE_DATA_DIR` / `ERRANTE_CACHE_DIR` explícitos.
- Los endpoints `def` corren en el threadpool compartido: sin semáforo, unas pocas vistas de ~1 min frenan
  también `/api/manifest`.
- No reconstruyas rutas de S3 ni versiones de pipeline: varían por semana y detector ✅. Siempre la key/URI que
  devuelve la búsqueda (WS1).
- CDS Estrasburgo está degradado desde el 2026-11-09 ✅ (alasky, VizieR y SIMBAD de Estrasburgo dan 404): nunca
  `*.cds.unistra.fr` desde el backend; espejos de IRSA y CfA.
- `VITE_BASE` en `.env.local` no llega a `vite.config.ts:6` hasta que WS5 use `loadEnv` (📄 doc de Vite): en el
  build de deploy/CI pasala como variable de entorno real.
- Config de deploy en la raíz (`render.yaml`, `fly.toml`, `railway.json`, `Dockerfile`): la guardia
  `scripts/owners.py` ya la asigna a WS4. Si la del frontend tiene que vivir en `frontend/` (p. ej.
  `vercel.json`, `netlify.toml`), la guardia la asigna a WS5: pedísela a WS5 o hacela en un PR `chore:`.
- `.claude/launch.json` (sin trackear): la entrada `api` usa `uv run --project backend`, que probablemente no
  tenga `errante` (❓ inferido). Usá `python scripts/dev.py api`.
- Worktrees: las instalaciones editables apuntan al checkout principal ✅; con el `.venv` compartido testeás el
  código equivocado → `python scripts/dev.py setup` dentro de cada worktree.
- `ruff` no está fijado: si `ruff format --check` da distinto en CI que en local, compará versiones (local 0.17.5 ✅).
- Sin secretos en el repo: ninguna API que usamos pide clave; los tokens de la plataforma de deploy van en sus
  secrets.

## Dependencias

- **No esperás a nadie** para WS4-1, WS4-2, WS4-3 ni para desplegar el esqueleto con `data/demo`.
- `/api/view` sin WS1/WS2: `build_patch` mockeado en tests + modo fake demo para que WS5 integre. Ojo: hoy
  `build.py` no escribe nada hasta que existe la detección (hallazgo N1 de la revisión); `build_patch` lo resuelve
  (WS2 P0).
- Sin contrato 0.3.0: responder `Field` 0.1.0 (sin `query`) y agregarlo al mergear. Revisás ese PR junto con
  WS2 y WS5.
- Con WS5 y WS3, **en el PR de contrato (sáb ~15:00)**: ruta de los PNG de vistas, codificación del id, FOV por
  defecto y tope (los códigos de error y `det` como entero ya están propuestos en `docs/CONTRACT.md`).

## Prompt de arranque

> Sos el agente del workstream WS4 (backend, deploy y coordinación de `main`) del repo de NASA Space Apps 2026,
> reto "Planet X and SPHEREx". Leé `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACT.md` y `tasks/WS4-backend.md`.
> Trabajá SOLO en `backend/`, `.github/`, `Makefile`, `scripts/` y la config de deploy; si hace falta tocar el
> contrato (`models.py`, `products.py`, `types.ts`), proponelo como PR `contract:` aparte. Con WS4-1 hecho,
> empezá por WS4-2 y WS4-3 (tests sin red con `monkeypatch`, validación de `field_id`, handlers 400/500 en JSON,
> CORS) y seguí con WS4-4 (`/api/view` con `build_patch` mockeado). No inventes respuestas de IRSA. Corré `python scripts/dev.py check`
> (Windows: `py scripts/dev.py check`); si tocás el deploy, abrí la URL pública en el navegador, en desktop y en
> el celular. Mostrame el diff y cómo lo probaste antes de commitear, y commiteá como `ws4: verbo + qué` con el
> trailer `Co-Authored-By:` del agente.
