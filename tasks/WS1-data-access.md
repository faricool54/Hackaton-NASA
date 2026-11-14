# WS1 · Acceso a datos SPHEREx

**Objetivo:** dado un punto del cielo, encontrar todas las exposiciones SPHEREx que lo cubren y traer recortes
(cutouts) chicos y cacheados, listos para que WS2 los reproyecte.

**Tus rutas:** `pipeline/errante/data/` · `pipeline/tests/test_data_*.py` · `notebooks/ws1_*` · `docs/DATA.md`
(compartido: agregá hechos verificados) · `pipeline/errante/cli.py` (`search`) en coordinación.

**Entregás:** `irsa.search_frames() -> SearchResult` (lista de `FrameRef`), `cutouts.fetch_cutouts() -> list[Path]`,
`fits_io.read_spherex()` (ya hecho) y `fits_io.wavelength_at()`.

**Leé primero:** `docs/DATA.md` (todo), `pipeline/errante/data/*.py` (docstrings con los detalles), `docs/ARCHITECTURE.md`.

## Estado actual
- ✅ `s3.py`: listado anónimo del bucket, parseo de nombres (`parse_key`), semanas por release.
- ✅ `cache.py`: descarga con caché en disco y reintentos.
- ✅ `fits_io.read_spherex`: lee IMAGE/FLAGS/VARIANCE/ZODI + WCS + MJD-OBS.
- ⛔ `irsa.search_frames`, `cutouts.fetch_cutout(s)`, `fits_io.wavelength_at`: stubs.

## Tareas

- [ ] **WS1-1 (P0) Verificar IRSA desde tu máquina.** Corré a mano la consulta TAP de `irsa.ADQL_FRAMES_AT_POSITION`
  para Barnard's Star (269.4463, 4.7665). Anotá en `docs/DATA.md` §3: tablas/colecciones vigentes (¿cómo se llaman
  en **DR1**?), columnas, cuánto tarda, cuántos frames hay por detector y rango de fechas.
  *Acepta:* sección de DATA.md actualizada con ✅ y fecha.
- [ ] **WS1-2 (P0) `search_frames`.** Implementar con `requests` (TAP sync CSV) o `astroquery`. Filtros por
  detector y MJD. Parsear `uri` → `FrameRef` (obs_id y detector desde el nombre del archivo con `s3.parse_key`,
  release desde la ruta, `s3_key` con `irsa_uri_to_s3_key`). Caché en disco del resultado (clave = query).
  *Acepta:* `errante search --ra 269.4463 --dec 4.7665` imprime un `SearchResult` válido; test `network` pasa;
  test offline con un CSV de ejemplo guardado en `pipeline/tests/fixtures/`.
- [ ] **WS1-3 (P0) `fetch_cutout(s)`.** URL con `cutout_url`, descarga cacheada (`cache.cached_download`),
  `ThreadPoolExecutor(settings.MAX_PARALLEL_DOWNLOADS)`, reintentos, y **reporte de fallas sin abortar todo**.
  *Acepta:* bajar 20 cutouts de 10′ de Barnard en < 2 min; segunda corrida instantánea (caché).
- [ ] **WS1-4 (P0) Primer campo real con WS2.** Junto a WS2, lograr que `errante build barnards-star` llegue
  hasta los PNG (I1 en `docs/ARCHITECTURE.md`). *Acepta:* el blink muestra frames reales en `?dataset=real`.
- [ ] **WS1-5 (P1) `wavelength_at`.** Longitud de onda central y ancho de banda en (ra, dec) desde `WCS-WAVE`,
  funcionando también en cutouts. Rellenar `Frame.wavelength_um`. *Acepta:* test contra un valor conocido.
- [ ] **WS1-6 (P1) Elegir épocas buenas.** Helper que agrupe frames por "visita" (clusters en tiempo) y
  detector, para que WS2 elija conjuntos con buena línea de base (horas, días, 6 meses).
- [ ] **WS1-7 (P2) Fallback S3.** Si IRSA está caído: buscar por semana en S3 + lectura por rangos HTTP del
  header para ver si el campo cae en el archivo (lento, pero independiente de IRSA).
- [ ] **WS1-8 (P2) HiPS DR1.** Investigar `dr1/hips5_cube/` y si IRSA publica un HiPS de imagen usable en
  Aladin Lite (le sirve a WS5).

## Gotchas
- Nombres de colecciones/tablas cambian entre releases (qr2 → qr3 → dr1). No hardcodees sin verificar.
- No uses el header `DATE` (es la fecha del archivo). Usá `MJD-OBS`.
- IRSA limita la concurrencia: nada de 50 hilos. TAP: una consulta a la vez.
- Nada de FITS en git: todo va a `data/cache/`.

## Prompt de arranque (pegalo en tu agente)

> Sos el agente del workstream WS1 (acceso a datos SPHEREx) del repo Errante para NASA Space Apps 2026.
> Leé `AGENTS.md`, `docs/DATA.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACT.md` y `tasks/WS1-data-access.md`.
> Trabajá SOLO en `pipeline/errante/data/`, tests `pipeline/tests/test_data_*.py` y `docs/DATA.md`.
> Empezá por la tarea WS1-1 y WS1-2: verificá la API TAP de IRSA con una consulta real (si no tenés red, decímelo
> y prepará el código + un test con fixture para que yo lo corra), implementá `search_frames` respetando la
> firma y el modelo `FrameRef`, con caché y reintentos. No inventes nombres de tablas ni columnas: verificá.
> Corré `make check` y mostrame el diff antes de commitear.
