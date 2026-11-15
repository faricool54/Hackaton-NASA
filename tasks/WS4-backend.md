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
- ✅ `/api/search` conectado a WS1. `/api/known-objects` sigue dependiendo de WS3.
- ✅ Frontera de archivos robusta: deadline, cupos que sobreviven al timeout, caché TTL memoria/disco,
  errores JSON y validación de entradas/rutas. Tests offline; sin cambios de contrato 0.2.0.
- ✅ Runner `python scripts/dev.py build-fields`, staging/validación/rollback, contenedor y workflow Pages
  preparados. ✅ Los cinco campos se reconstruyeron con WS1/WS2 reales; URL pública y hosting siguen pendientes.
- ✅ Motor y POST/GET de jobs implementados; correcciones de CORS, destino, publicación, admisión y recuperación
  con regresiones. Contrato 0.3.0 (#32), backend (#33) y conexión WS5 en PRs dependientes separados.

## Tareas

- [ ] **WS4-1 (P0) Coordinación**: completar `docs/TEAM.md`, proteger `main` (requerir CI verde + 1 review),
  revisar PRs de contrato.
- [x] **WS4-2 (P0) Endpoints en vivo robustos**: timeouts, caché en memoria (TTL) + disco, errores 502/504 con
  JSON claro, límite de concurrencia hacia IRSA. *Acepta:* tests con funciones mockeadas (lento, error, ok).
- [x] **WS4-3 (P0) Integración continua de campos reales**: script/target `make build-fields` que construya los
  cinco blancos de `fields.toml` y valide (`errante validate --dir data/products`). Build básico sin análisis;
  selección temporal útil y actualización por release (C01). No marcar un campo sin datos como éxito.
  Runner implementado con timeout duro por campo, verificación de PNGs/épocas/procedencia y rollback.
  Aceptación real verificada el 14/11: cinco campos, 40 imágenes cada uno, `synthetic=False`,
  `errante validate` correcto (revisión previa: 139,9 s). No equivale a validación científica R05.
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
  Contenedor y arranque productivo preparados; falta proveedor/URL y prueba pública; contrato y recorrido local ya implementados.
- [x] **WS4-5 (P0, R03/C04/C06) Campos por coordenadas arbitrarias.** Diseñar contrato de solicitud
  RA/Dec/FOV/filtros, job ID y polling; reutilizar `build.build_field` básico. Validar rangos, FOV/píxeles/frames,
  concurrencia y tiempos. Caché por todos los parámetros y releases/versiones. Estados: en curso, listo,
  sin cobertura y fallo; errores parciales explícitos. *Acepta:* entrada no precargada abre una secuencia real.
  POST `/api/jobs` y GET `/api/jobs/{id}` consumen contrato 0.3.0 (#32). Frontend conectado en PR
  dependiente: formulario, mapa, nombre, polling y PNG reales; tres jobs de 40 frames probados en navegador.
  Aceptación local; la URL pública sigue en WS4-4/6.
- [ ] **WS4-6 (P0, R01) GitHub Pages / Vercel** para el frontend estático (con WS6): workflow que construye
  `frontend/` con `VITE_BASE` y publica.
  Para S03, probar app/demo/materiales finales sin login, permisos ni registro; videos/documentos se alojan
  externamente. El PDF no autoriza sustituir una demo de proyecto por una URL inaccesible o solo documentación.
  Workflow opt-in `pages.yml` implementado; habilitar Pages/variables y comprobar acceso anónimo aún pendiente.
- [ ] **WS4-7 (P2) `/api/limits`** cuando WS2 defina el contrato de límites.
- [x] **WS4-8 (P1, C02) Espectros bajo demanda.** `POST /api/spectra` independiente de candidatos:
  cubo DR1 estático MJy/sr o fotometría L2 mJy por exposición. Calidad/fuentes/fechas, errores, límites,
  hijo supervisado y caché. La integración usa WS1 cube/point y WS2 photometry; no afirma validación R05.
- [x] **WS4-9 (P1, C03) Operaciones de imágenes.** `POST /api/fields/{id}/comparisons` conecta selección
  con medias ponderadas por temporada y diferencias escaladas WS2, por detector. PNG atómicos,
  entradas/método/épocas/λ/cobertura y recursos acotados. No se implementa suma cruda arbitraria.
- [x] **WS4-10 (P0 para jobs; P1 para extras) Contratos aditivos.** Con WS1/2/3/5 definir solicitud y estados
  de jobs; luego calidad/flags, coadds/diferencias y espectros en cualquier posición. Jobs formalizados en 0.3.0;
  espectros/comparaciones en 0.4.0 (`contract/science-api`, PR #53; depende de #39). Mantener `models.py`,
  schema y tipos TS sincronizados, versionar, y no documentar rutas propuestas como endpoints disponibles.
  S08 requiere metadata de atribución para código/datos generados con SI: el inventario actual está en
  `docs/submission/ai-usage.json`; coordinar procedencia de futuros productos sin confundir simulación numérica con imagen IA.

## Estado técnico actualizado (14/11/2026)

- WS1: búsqueda/recortes/λ implementados; WS2: reproyección y épocas por temporada × detector implementadas.
- WS4: CORS POST, productos servidos en el destino del motor, locks entre procesos y manifest atómico.
- Jobs: admisión transaccional, resultados verificados, recuperación por huellas y logs/almacenamiento acotados.
- Errores públicos sanitizados; los tests de backend no dependen de IRSA/JPL.
- Espectros/comparaciones implementados con contrato, límites y procedencia; frontend en PR dependiente.
  Hosting público pendiente de destino; fichas/3D físico y validación R05 tienen sus propios responsables.

## Prompt de arranque

> Sos el agente del workstream WS4 (backend e integración) del repo Errante para NASA Space Apps 2026. Leé
> `AGENTS.md`, `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/WORKFLOW.md` y `tasks/WS4-backend.md`.
> Trabajá SOLO en `backend/`, `.github/` y `Makefile`. Leé `docs/REQUIREMENTS.md`. Empezá por WS4-2 y
> WS4-5: conectar RA/Dec → job → campo visible, con timeouts, caché y errores claros. El cruce JPL es opcional. No
> cambies el contrato sin un PR `contract:`. Corré `python scripts/dev.py check` y mostrame el diff antes de commitear.

Integración con main actualizado: #17 aporta cinco campos reales (40 frames cada uno); #19 aporta
comparaciones de temporadas con `compare.json` provisional. Se conservaron ambos. La comparación web
ahora se adapta a un contrato compartido antes de exponerla. Tener la función por sí sola no cerraba WS4-9.

## Verificación de caché y ciencia (15/11/2026)

Cache `display-mask-v4` + huella de código/dependencias: nuevos cambios WS2 invalidan jobs previos.
Regresiones de flags SOURCE/HOT, huecos del cubo, fotometría firmada/saturación, PNG corrupto, singleflight,
cancelación local, errores sanitizados y terminación real del hijo por disco/deadline.
Recorrido real en navegador: Barnard D2 produjo tres medias y tres diferencias sin fallos de entrada;
fechas, λ, escala y ruido visibles. Es aceptación técnica C02/C03, no validación científica de una señal.
