# WS1 · Acceso a datos SPHEREx

**Objetivo:** dado un punto del cielo, encontrar todas las exposiciones SPHEREx que lo cubren y traer recortes
(cutouts) chicos y cacheados, listos para que WS2 los reproyecte.

**Cobertura:** R02/R03/R05, C01/C02/C04/C07/C08 (`docs/REQUIREMENTS.md`).
El camino crítico termina en imágenes visibles; catálogos y detección no son dependencias.

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

- [ ] **WS1-1 (P0, R02/C08) Verificar consultas IRSA desde tu máquina.** Las páginas y notebooks ya son
  accesibles (DATA.md §7); eso no verifica consultas ni descargas. Corré la consulta TAP de `irsa.ADQL_FRAMES_AT_POSITION`
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
  hasta los PNG (I1 en `docs/ARCHITECTURE.md`). *Acepta:* el blink muestra frames reales en `?dataset=real`
  sin `--analyze`; luego repetir cobertura y descargas para los cinco blancos de `docs/VALIDATION.md`,
  con reporte de épocas y fallas.
- [ ] **WS1-5 (P0 para R05; P1 para C02) `wavelength_at`.** Longitud de onda central y ancho de banda en (ra, dec) desde `WCS-WAVE`,
  funcionando también en cutouts. Rellenar `Frame.wavelength_um`. *Acepta:* test contra un valor conocido.
- [ ] **WS1-6 (P0, R02/R05) Elegir épocas buenas.** Agrupar por visita y detector/λ compatible; seleccionar
  línea de base útil para movimiento propio y variables. No truncar siempre a los primeros `max_frames`.
  Eliminar reprocesados duplicados; registrar cobertura insuficiente y selección temporal en la evidencia.
- [ ] **WS1-7 (P2) Fallback S3.** Si IRSA está caído: buscar por semana en S3 + lectura por rangos HTTP del
  header para ver si el campo cae en el archivo (lento, pero independiente de IRSA).
- [ ] **WS1-8 (P2) HiPS DR1.** Investigar `dr1/hips5_cube/` y si IRSA publica un HiPS de imagen usable en
  Aladin Lite (le sirve a WS5).
- [ ] **WS1-9 (P1, C01) Actualización de releases.** Descubrir/configurar colecciones, registrar release y
  versión de procesamiento, refrescar consultas y separar claves de caché por versión. La documentación
  consultada ya enumera `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep` (DATA.md §3);
  verificar respuesta real antes de usarlas. *Acepta:* incorporar nuevas épocas sin cambiar la UI ni duplicar OBSID.

**C04/C07:** `fetch_cutouts` debe recibir el FOV validado por WS4, preservar WCS, flags, VARIANCE y ZODI,
y devolver una asociación inequívoca frame→resultado. Saltar descargas no puede desalinear `refs` y `paths`;
coordinar el cambio con `build.py` y registrar cada falla, sin inventar un producto completo.

## Gotchas
- Nombres de colecciones/tablas cambian entre releases (qr2 → qr3 → dr1). No hardcodees sin verificar.
- No uses el header `DATE` (es la fecha del archivo). Usá `MJD-OBS`.
- IRSA limita la concurrencia: nada de 50 hilos. TAP: una consulta a la vez.
- Nada de FITS en git: todo va a `data/cache/`.

## Hechos verificados (2026-11-14) — leelos antes de implementar

Detalle y fuentes en [`docs/DATA.md`](../docs/DATA.md) §3.0.
- **Búsqueda:** SIA2 en **VOTable** (1–4 s; el CSV viene roto) sobre `spherex_dr1` + `spherex_qr3` (`*_deep`
  opcionales con `TIME`/`MAXREC`); TAP como fallback (8–19 s; la ADQL actual funciona). QR2 ya no está indexado.
  Deduplicar por `(obs_id, detector)` y usar la key S3 que trae `cloud_access`: las versiones de pipeline cambian
  por semana y detector, no armes rutas a mano.
- **Tiempo:** `MJD-OBS` es el **inicio** de la exposición; usar `MJD-AVG` (o `(t_min + t_max)/2` en la búsqueda).
- **Píxeles:** un cutout de IRSA pesa **~4 MB** mínimo (tabla EPSF entera) y tarda 4–15 s; sin solape da **422**.
  Lo rápido es leer por **Range en S3** solo las filas del recorte (`IMAGE` float32 sin comprimir, ~0,4 MB en ~1 s
  a 5′). IRSA **no** tiene CORS; S3 sí.
- **WCS-WAVE:** la grilla depende del detector (D3 9×14, D4 13×20…): leer `TDIM`.
- **`build.py`** corta en `max_frames=40` sobre resultados ordenados por tiempo → todo cae en la 1.ª temporada y
  Barnard no se mueve. Elegir frames por temporada × detector. `frame_id` hoy sale del nombre del archivo de caché
  (un hash): derivarlo de `obs_id` + detector.

## Prompt de arranque (pegalo en tu agente)

> Sos el agente del workstream WS1 (acceso a datos SPHEREx) del repo Errante para NASA Space Apps 2026.
> Leé `AGENTS.md`, `docs/DATA.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACT.md` y `tasks/WS1-data-access.md`.
> Trabajá SOLO en `pipeline/errante/data/`, tests `pipeline/tests/test_data_*.py` y `docs/DATA.md`.
> Empezá por la tarea WS1-1 y WS1-2: verificá la API TAP de IRSA con una consulta real (si no tenés red, decímelo
> y prepará el código + un test con fixture para que yo lo corra), implementá `search_frames` respetando la
> firma y el modelo `FrameRef`, con caché y reintentos. No inventes nombres de tablas ni columnas: verificá.
> Corré `python scripts/dev.py check` y mostrame el diff antes de commitear.
