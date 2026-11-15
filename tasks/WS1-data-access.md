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
- ✅ `fits_io.read_spherex`: lee IMAGE/FLAGS/VARIANCE/ZODI + WCS; con #23, tiempo de mitad de exposición.
- 🔄 En PR (2026-11-14, faricool54 + Claude): #21 `irsa.search_frames` + `epochs.py`, #22 `s3range.py` +
  `cutouts.fetch_cutouts` (S3 primero, IBE de respaldo, `None` por frame fallido), #23 `fits_io.wavelength_at`.
  Juntos con el #16 de WS2, `errante build barnards-star` ya produce un campo real (40 frames, 22 s).

## Tareas

- [x] **WS1-1 (P0, R02/C08) Verificar consultas IRSA desde tu máquina.** ✅ DATA.md §3.0–§3.1. Las páginas y notebooks ya son
  accesibles (DATA.md §7); eso no verifica consultas ni descargas. Corré la consulta TAP de `irsa.ADQL_FRAMES_AT_POSITION`
  para Barnard's Star (269.4463, 4.7665). Anotá en `docs/DATA.md` §3: tablas/colecciones vigentes (¿cómo se llaman
  en **DR1**?), columnas, cuánto tarda, cuántos frames hay por detector y rango de fechas.
  *Acepta:* sección de DATA.md actualizada con ✅ y fecha.
- [x] **WS1-2 (P0) `search_frames`.** ✅ #21 (falta probar en vivo el fallback TAP). Implementar con `requests` (TAP sync CSV) o `astroquery`. Filtros por
  detector y MJD. Parsear `uri` → `FrameRef` (obs_id y detector desde el nombre del archivo con `s3.parse_key`,
  release desde la ruta, `s3_key` con `irsa_uri_to_s3_key`). Caché en disco del resultado (clave = query).
  *Acepta:* `errante search --ra 269.4463 --dec 4.7665` imprime un `SearchResult` válido; test `network` pasa;
  test offline con un CSV de ejemplo guardado en `pipeline/tests/fixtures/`.
- [x] **WS1-3 (P0) `fetch_cutout(s)`.** ✅ #22 (20 cutouts de 10′ en ~10 s por S3). URL con `cutout_url`, descarga cacheada (`cache.cached_download`),
  `ThreadPoolExecutor(settings.MAX_PARALLEL_DOWNLOADS)`, reintentos, y **reporte de fallas sin abortar todo**.
  *Acepta:* bajar 20 cutouts de 10′ de Barnard en < 2 min; segunda corrida instantánea (caché).
- [x] **WS1-4 (P0) Primer campo real con WS2.** ✅ Los cinco campos reales están publicados (WS2 #17). Cuatro
  están validados en `docs/validation/` (#36); falta el registro de Barnard. Junto a WS2, lograr que `errante build barnards-star` llegue
  hasta los PNG (I1 en `docs/ARCHITECTURE.md`). *Acepta:* el blink muestra frames reales en `?dataset=real`
  sin `--analyze`; luego repetir cobertura y descargas para los cinco blancos de `docs/VALIDATION.md`,
  con reporte de épocas y fallas.
- [x] **WS1-5 (P0 para R05; P1 para C02) `wavelength_at`.** ✅ #23 (falta que `build.py`, de WS2, llene
  `Frame.wavelength_um` con `img.wavelength_at`). Longitud de onda central y ancho de banda en (ra, dec) desde `WCS-WAVE`,
  funcionando también en cutouts. Rellenar `Frame.wavelength_um`. *Acepta:* test contra un valor conocido.
- [ ] **WS1-6 (P0, R02/R05) Elegir épocas buenas.** 🔄 Deduplicación en #21 y `epochs.select_per_season`;
  la selección del build la hace WS2 en #16. Agrupar por visita y detector/λ compatible; seleccionar
  línea de base útil para movimiento propio y variables. No truncar siempre a los primeros `max_frames`.
  Eliminar reprocesados duplicados; registrar cobertura insuficiente y selección temporal en la evidencia.
- [ ] **WS1-7 (P2) Fallback S3.** 🔄 Los píxeles ya salen de S3 (#22). Snapshots de búsqueda de los cinco blancos (#43):
  la demo sobrevive a una caída de IRSA. Falta buscar sin IRSA en un punto arbitrario (HpxFinder solo indexa tiles del cubo). Si IRSA está caído: buscar por semana en S3 + lectura por rangos HTTP del
  header para ver si el campo cae en el archivo (lento, pero independiente de IRSA).
- [x] **WS1-8 (P2) HiPS DR1.** ✅ Aladin Lite dibuja el cubo DR1 de IRSA (`docs/VISION.md`), y `cube_spectrum`
  da el espectro de cualquier posición desde los tiles en S3 (#42).
- [ ] **WS1-9 (P1, C01) Actualización de releases.** Descubrir/configurar colecciones, registrar release y
  versión de procesamiento, refrescar consultas y separar claves de caché por versión. La documentación
  consultada ya enumera `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep` (DATA.md §3);
  verificar respuesta real antes de usarlas. *Acepta:* incorporar nuevas épocas sin cambiar la UI ni duplicar OBSID.

**Visión (14/11, [`docs/VISION.md`](../docs/VISION.md)):**

- [x] **WS1-10 (P0/P1) Todas las exposiciones de un punto.** ✅ PR en curso. `errante.data.point.point_series` + `errante point`:
  stamps de cada exposición en (ra, dec) con λ y tiempo, materia prima del video, el espectro y la curva de luz del panel.
  Revisión aplicada (λ nunca cacheada faltante, ETag de layouts, `--deadline`) y `to_spherex_image` para la fotometría de WS2 (box ≥ 15).
- [x] **WS1-11 (P1) Espectro rápido de cualquier punto.** ✅ #42 (`cube_spectrum`, `errante cube-spectrum`).
- [x] **WS1-12 (P0) La demo sobrevive a una caída de IRSA.** ✅ #43 (snapshots de los cinco blancos y fallback
  antes del timeout de la API). Sin fallback, un punto arbitrario sigue dependiendo de IRSA (timeout del backend: WS4).
- [x] **WS1-13 (P0/P1) Notas de deploy y fixtures de espectro.** ✅ PR `ws1/deploy-spectra-facts`
  ([`DATA.md`](../docs/DATA.md) §3.3). Los snapshots no entran en la imagen actual (simulado; `TODO(WS4)`:
  `COPY data/index` o `ERRANTE_SEARCH_SNAPSHOTS`). También: variables que acotan búsqueda, cubo y serie por debajo de
  los 30 s de la API, y 12 espectros reales del cubo como fixtures para WS4/WS5 (cinco blancos + cielo vacío, apertura 0 y 2).
  Incluye la propuesta de campos para un PR `contract:` y los hechos de Barnard de #46 (saturación, frame `0431_2D6`, `GJ 699`).

**C04/C07:** `fetch_cutouts` debe recibir el FOV validado por WS4, preservar WCS, flags, VARIANCE y ZODI,
y devolver una asociación inequívoca frame→resultado. Saltar descargas no puede desalinear `refs` y `paths`;
coordinar el cambio con `build.py` y registrar cada falla, sin inventar un producto completo.

## Gotchas
- Nombres de colecciones/tablas cambian entre releases (qr2 → qr3 → dr1). No hardcodees sin verificar.
- No uses el header `DATE` (es la fecha del archivo). Usá `MJD-AVG`/`DATE-AVG` (mitad de la exposición).
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
