# WS4 · Backend API, integración y CI

**Objetivo:** API estable sobre los productos, endpoints en vivo robustos (IRSA/JPL lentos o caídos no deben
romper nada), deploy, y ser quien **mantiene `main` verde** e integra el trabajo de todos.

**Cobertura:** R01/R02/R03, C01/C02/C03/C04/C06/C07. La construcción por coordenadas es P0;
JPL y análisis automático no son requisitos para abrir un campo.

**Tus rutas:** `backend/` · `.github/workflows/` · `Makefile` · deploy (Render/Railway/Fly/…) · coordinación de
`pipeline/errante/products.py` y `build.py`.

**Recibís:** productos en `data/products` / `data/demo` (contrato), funciones de WS1 (`search_frames`) y WS3
(`objects_in_frame`). **Entregás:** `/api/*` documentado (OpenAPI en `/docs`), deploy público del backend (si se usa).

**Leé primero:** `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `backend/errante_api/**`, `docs/WORKFLOW.md`.

## Estado actual
Implementación y validación de esta etapa: [PR #6](https://github.com/faricool54/Hackaton-NASA/pull/6).

- ✅ `/api/health`, `/api/manifest`, `/api/fields/{id}`, `/candidates`, `/known`, `/data/*` (con tests).
- ⛔ `/api/search`, `/api/known-objects` devuelven 501 hasta que WS1/WS3 implementen.
- ✅ Frontera de archivos robusta: deadline, cupos que sobreviven al timeout, caché TTL memoria/disco,
  errores JSON y validación de entradas/rutas. Tests offline; sin cambios de contrato 0.2.0.
- ✅ Runner `python scripts/dev.py build-fields`, staging/validación/rollback, contenedor y workflow Pages
  preparados. ⛔ Datos reales dependen de WS1/WS2; URL pública y activación de hosting siguen pendientes.
- ⛔ Jobs: propuesta concreta en `backend/README.md`, pendiente de dueño WS3/PR de contrato con WS5.

## Tareas

- [ ] **WS4-1 (P0) Coordinación**: completar `docs/TEAM.md`, proteger `main` (requerir CI verde + 1 review),
  revisar PRs de contrato.
- [x] **WS4-2 (P0) Endpoints en vivo robustos**: timeouts, caché en memoria (TTL) + disco, errores 502/504 con
  JSON claro, límite de concurrencia hacia IRSA. *Acepta:* tests con funciones mockeadas (lento, error, ok).
- [ ] **WS4-3 (P0) Integración continua de campos reales**: script/target `make build-fields` que construya los
  cinco blancos de `fields.toml` y valide (`errante validate --dir data/products`). Build básico sin análisis;
  selección temporal útil y actualización por release (C01). No marcar un campo sin datos como éxito.
  Runner implementado con timeout duro por campo, verificación de PNGs/épocas/procedencia y rollback.
  Aceptación real pendiente de WS1/WS2; no se marca completa por pasar tests con dobles del pipeline.
- [x] **WS4-3a (P0) Separar imágenes y análisis** (2026-11-14): build básico sin detección/cruce,
  `--analyze` optativo, campo conservado ante fallo del análisis y error explícito sin cobertura.
  Regresión offline en `pipeline/tests/test_build.py`; no implica que IRSA/cutouts/reproyección estén implementados.
- [x] **WS4-3b (P0) Integrar documentación y ampliación WS7** (2026-11-14): conservar contrato 0.2.0,
  endpoints/productos 3D y pruebas, junto a enunciado/PDFs/guías. Galería P2 con parámetros sin verificar,
  copia pública corregida y metadatos de asistencia actualizados. Validación local: 39 tests Python,
  9 frontend, schema/lint/build y navegador escritorio/móvil; corregido desbordamiento del canvas en móvil.
- [ ] **WS4-4 (P0, R01/R03) Deploy** del servicio de construcción por coordenadas (o equivalente verificable)
  con `ERRANTE_DATA_DIR`, worker/caché y CORS configurado. La web estática sola no cubre coordenadas arbitrarias.
  Documentar en `backend/README.md` y probar frontend → job → imágenes desde la URL pública.
  Contenedor y arranque productivo preparados; falta proveedor/URL, contrato de jobs y recorrido real.
- [ ] **WS4-5 (P0, R03/C04/C06) Campos por coordenadas arbitrarias.** Diseñar contrato de solicitud
  RA/Dec/FOV/filtros, job ID y polling; reutilizar `build.build_field` básico. Validar rangos, FOV/píxeles/frames,
  concurrencia y tiempos. Caché por todos los parámetros y releases/versiones. Estados: en curso, listo,
  sin cobertura y fallo; errores parciales explícitos. *Acepta:* entrada no precargada abre una secuencia real.
  Las rutas concretas de jobs se definen con WS4-10; todavía no existen.
- [ ] **WS4-6 (P0, R01) GitHub Pages / Vercel** para el frontend estático (con WS6): workflow que construye
  `frontend/` con `VITE_BASE` y publica.
  Para S03, probar app/demo/materiales finales sin login, permisos ni registro; videos/documentos se alojan
  externamente. El PDF no autoriza sustituir una demo de proyecto por una URL inaccesible o solo documentación.
  Workflow opt-in `pages.yml` implementado; habilitar Pages/variables y comprobar acceso anónimo aún pendiente.
- [ ] **WS4-7 (P2) `/api/limits`** cuando WS2 defina el contrato de límites.
- [ ] **WS4-8 (P1, C02) Espectros bajo demanda.** Servicio de extracción por campo + posición elegida,
  independiente de candidatos; integrar WS1-5 y WS3-5 con errores, límites y caché. Contrato/ruta por definir.
- [ ] **WS4-9 (P1, C03) Operaciones de imágenes.** Conectar selección de frames con suma/media/resta de
  WS2; devolver producto y procedencia de entradas, método, fechas, detector/λ y cobertura. Límites de recursos.
- [ ] **WS4-10 (P0 para jobs; P1 para extras) Contratos aditivos.** Con WS1/2/3/5 definir solicitud y estados
  de jobs; luego calidad/flags, coadds/diferencias y espectros en cualquier posición. Mantener `models.py`,
  schema y tipos TS sincronizados, versionar, y no documentar rutas propuestas como endpoints disponibles.
  S08 requiere metadata de atribución para código/datos generados con SI: el inventario actual está en
  `docs/submission/ai-usage.json`; coordinar procedencia de futuros productos sin confundir simulación numérica con imagen IA.

## Hechos verificados (2026-11-14) — leelos antes de implementar

- **IRSA no tiene CORS** (TAP, SIA, cutouts): el backend es obligatorio como proxy para el flujo RA/Dec → video.
  S3 sí tiene CORS. Detalle en [`docs/DATA.md`](../docs/DATA.md) §3.0.
- Tiempos medidos: SIA 1–4 s, TAP 8–19 s, cutout IBE 4–15 s y ~4 MB, lectura por Range en S3 ~1 s por frame a 5′.
  Hace falta caché en disco, timeouts y respuestas 502/504 en JSON (hoy `live.py` solo maneja `NotImplementedError`).
- **Path traversal:** `field_id` llega sin validar a `root / "fields" / field_id` (en Windows `..\..\x` escapa del
  data dir). Validar con el patrón slug de `SkyField.id` antes de exponer el backend.
- El test de `/api/search` va a pegarle a IRSA en CI cuando WS1 implemente `search_frames`: mockearlo con
  `monkeypatch` y dejar lo real en `@pytest.mark.network`.
- `ERRANTE_CORS_ORIGINS` se separa por coma sin `strip()`; `/api/health` expone la ruta absoluta del data dir.

## Prompt de arranque

> Sos el agente del workstream WS4 (backend e integración) del repo Errante para NASA Space Apps 2026. Leé
> `AGENTS.md`, `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/WORKFLOW.md` y `tasks/WS4-backend.md`.
> Trabajá SOLO en `backend/`, `.github/` y `Makefile`. Leé `docs/REQUIREMENTS.md`. Empezá por WS4-2 y
> WS4-5: conectar RA/Dec → job → campo visible, con timeouts, caché y errores claros. El cruce JPL es opcional. No
> cambies el contrato sin un PR `contract:`. Corré `python scripts/dev.py check` y mostrame el diff antes de commitear.
