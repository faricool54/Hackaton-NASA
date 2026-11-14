# WS1 · Datos SPHEREx: búsqueda y píxeles

**Objetivo:** dado un RA/Dec y un FOV, encontrar **todas** las exposiciones SPHEREx que cubren ese parche (en los
releases vigentes, sin fijar versiones a mano) y entregar los píxeles del recorte rápido y cacheados, para que WS2
arme la "serie de imágenes como un pequeño video" que pide el enunciado.

**Tus rutas:** `pipeline/errante/data/**` · `pipeline/errante/settings.py` · `pipeline/tests/test_data_*.py` ·
`docs/DATA.md` (dueño; los demás te pasan hechos o agregan en la sección "Notas de otros WS" al final) ·
subcomando `search` de `pipeline/errante/cli.py`.

**Recibís:** posiciones de los 5 objetivos (WS3: centros ya propagados en `pipeline/errante/config/fields.toml`) ·
contrato `FrameRef` / `SearchResult` (la 0.1.0 alcanza).

**Entregás** (firmas propuestas; si cambian, avisá a WS2 y WS4 antes de mergear):

```python
# data/irsa.py
search_frames(ra, dec, radius_deg=0.01, detectors=None, mjd_min=None, mjd_max=None,
              collections=None) -> SearchResult    # SIA2 VOTable + TAP de respaldo, dedupe, mjd = mitad, s3_key
frame_id(ref: FrameRef) -> str                     # f"{ref.obs_id}D{ref.detector}"  (nunca el hash de caché)
# data/epochs.py (nuevo)
group_visits(refs, gap_hours=6.0) -> list[list[FrameRef]]
group_seasons(refs, gap_days=20.0, min_frames=20) -> list[Season]   # Season(index, mjd_start, mjd_end, refs)
# data/s3range.py (nuevo)
read_patch(ref, ra, dec, fov_arcmin, planes=("IMAGE", "VARIANCE", "ZODI")) -> Path   # mini-MEF en data/cache/
# data/cutouts.py
fetch_cutouts(refs, ra, dec, size_arcmin) -> tuple[list[tuple[FrameRef, Path]], list[tuple[FrameRef, str]]]
# data/fits_io.py
read_spherex(path) -> SpherexImage                 # mjd = MJD-AVG (hoy lee MJD-OBS, que es el INICIO)
wavelength_at(path, ra, dec) -> tuple[float, float] | None   # P1
```

`read_patch` escribe un MEF chico con el **mismo layout que un cutout de IRSA** (HDUs `IMAGE`/`VARIANCE`/`ZODI`,
header de IMAGE con `CRPIX` corrido): así `read_spherex` lee igual los dos caminos y WS2 no se entera de cuál se usó.

**Leé primero:** [`AGENTS.md`](../AGENTS.md) · [`docs/PLAN.md`](../docs/PLAN.md) §2–§4 ·
[`docs/CONTRACT.md`](../docs/CONTRACT.md) · [`docs/COLLABORATION.md`](../docs/COLLABORATION.md) ·
[`docs/DATA.md`](../docs/DATA.md) (reescrito hoy con la evidencia de la revisión: §0 primero, después §1–§4) ·
[`docs/REVIEW-2026-11-14.md`](../docs/REVIEW-2026-11-14.md) (evidencia) · `pipeline/errante/data/*.py`.

## Estado actual (verificado 2026-11-14)

| Pieza | Estado |
|---|---|
| `s3.py` | ✅ listado anónimo, `parse_key`, `list_weeks`; `parse_key` + `irsa_uri_to_s3_key` aciertan con los 358 URIs reales de Barnard (incluye `l2b_retry-*`). ⚠ `list_prefix` corta en 1000 claves sin paginar; `parse_key` toma el release del primer segmento (con un URI de IRSA da `ibe`). |
| `cache.py` | ✅ descarga con caché atómica. ⚠ no reintenta `ChunkedEncodingError`, deja `.part` huérfanos, no valida `SIMPLE`, el 422 sale como `HTTPError` genérico. |
| `fits_io.read_spherex` | ✅ abre HDUs por nombre (tolera QR2 y cutouts). ⚠ usa `MJD-OBS` = inicio de la exposición. |
| `irsa.search_frames` | ⛔ stub. ✅ la ADQL de `ADQL_FRAMES_AT_POSITION` funciona: Barnard → 358 frames (dr1 239 + qr3 119) en 11,4 s. |
| `cutouts.fetch_cutout(s)` | ⛔ stub. ✅ `cutout_url` arma URLs válidas (`size=5arcmin` → 49×49 px). ⚠ la firma `-> list[Path]` choca con `zip(strict=True)` de `build.py`. |
| `fits_io.wavelength_at` | ⛔ stub. |
| `settings.py` | ✅ TAP, SIA, IBE y S3 responden 200. Faltan colecciones configurables y paralelismo S3. |
| `docs/DATA.md` | ✅ reescrito el 2026-11-14 (coordinación) con los hechos verificados de la revisión; ya corrige MJD, 422, WCS-WAVE y colecciones y tiene "Notas de otros WS". Quedan ❓ que se cierran implementando (WS1-1). |

## Tareas (ordenadas por prioridad)

- [ ] **WS1-1 (P0, ≤ 30 min y después continuo) Apropiarte de `docs/DATA.md`.** Ya lo reescribió coordinación
  con la evidencia de hoy; todos los agentes lo leen como fuente de verdad. Leelo entero, corregí lo que tu
  implementación contradiga y cerrá los ❓ a medida que los verifiques: receta por Range de punta a punta (§3.4),
  `INTERSECTS` en TAP (§3.3), `BAND` en SIA (§3.2), FLAGS por Range, throughput desde el deploy. Revisá también la
  sección "Notas de otros WS" y subí lo que corresponda.
  *Acepta:* un PR `ws1: docs/DATA.md ...` por cada ❓ que se resuelva, con fecha y cómo se verificó; al cerrar
  WS1-4, §3.4 deja de decir "nadie probó astropy por Range de punta a punta".
- [ ] **WS1-2 (P0) `search_frames` con SIA2 en VOTable + TAP de respaldo.**
  - SIA2 (`settings.IRSA_SIA?COLLECTION=<c>&POS=circle <ra> <dec> <r>`, sin `RESPONSEFORMAT` → VOTable) por cada
    colección de `ERRANTE_COLLECTIONS` (default `spherex_dr1,spherex_qr3`; `*_deep` solo a pedido, con
    `TIME`/`MAXREC`). Parsear con `astropy.io.votable` (core: el CI no necesita pyvo).
  - Por fila: `obs_id`; detector desde `energy_bandpassname` (`SPHEREx-D6`) o la key (`parse_key`);
    `s3_key` = `cloud_access` → `aws.key`;
    `irsa_uri` = `ibe/data/spherex/<key>`; `mjd = (t_min + t_max) / 2`; `wavelength_um` = centro de
    `em_min..em_max` (es la banda del detector, **no** la λ en el objetivo).
  - Dedupe por `(obs_id, detector)` con prioridad dr1 > qr3; detectores y MJD filtrados del lado cliente si hace
    falta; ordenar por mjd.
  - Si SIA falla (timeout/5xx) → TAP con la ADQL corregida (`IN` de detectores, `time_bounds_upper`, filtros de
    MJD; `obs_id` y release salen del `uri`, no de `plane.obsid`/`plane.datarelease`).
  - Caché en disco por (ra, dec redondeados, radio, colecciones, filtros) con TTL ~1 día; reintentos con backoff;
    nunca consultas TAP en paralelo. `frame_id(ref)`. `cli.py search` con `--fov`, `--collection` y `--out <json>`.
  *Acepta:* `errante search --ra 269.4463 --dec 4.7665` imprime un `SearchResult` válido con ≥ 350 frames,
  releases {dr1, qr3}, los 6 detectores y `s3_key` en todos, en < 10 s (segunda vez < 1 s); test offline con un
  VOTable real recortado en `pipeline/tests/fixtures/ws1/`; test con SIA caído (mock) que cae a TAP;
  `test_irsa_finds_frames_for_barnards_star` pasa sin `xfail` con `ERRANTE_NETWORK_TESTS=1`.
- [ ] **WS1-3 (P0) `group_seasons` / `group_visits`** (`data/epochs.py`). Glosario de PLAN §3: visita = exposiciones
  separadas < 6 h; temporada = bloques separados > 20 días (el umbral final lo fija el PR de contrato de WS3:
  dejalo como parámetro). Calcular las temporadas con **todos** los detectores juntos (la temporada 0 de D1 es la
  misma que la de D6); fusionar colas chicas (< `min_frames`) con la temporada más cercana; `max_season_days`
  opcional para campos con cobertura casi continua (R Dra, polos).
  *Acepta:* con el fixture de Barnard (358 frames de TAP): 48 visitas; con hueco > 20 d salen 3 bloques grandes
  (108/113/117) + 3 colas de 10, 8 y 2 frames, y tras fusionar quedan 3 temporadas de 118/121/119; WISE 0855 da
  30/128/100 (con 20 d su 2.ª temporada se parte en 110 + 18). Es decir, coincide con la tabla de `DATA.md` §4.2.
- [ ] **WS1-4 (P0) `read_patch` por Range en S3** (`data/s3range.py`, solo `requests` + astropy).
  1. `hdu_layout(key)`: leer bytes 0–57599 y recorrer headers con `fits.Header.fromstring` (bloques de 2880 B
     hasta `END`; datos = |BITPIX|/8 · NAXIS1 · NAXIS2 (+ `PCOUNT` en BINTABLE), rellenado a 2880) → offsets de
     IMAGE, FLAGS, VARIANCE, ZODI y WCS-WAVE. Cachear layout + header IMAGE en `data/cache/` (JSON).
  2. Con el WCS del header IMAGE (SIP incluido) calcular la caja de píxeles del FOV + margen; sin solape →
     `NoOverlap`.
  3. Por plano, **un** Range de filas contiguas (fila = 2040 × 4 B = 8160 B, float32 big-endian) y recortar
     columnas.
  4. Escribir el mini-MEF en `data/cache/patches/` con `CRPIX1/2`, `CRPIX1A/2A`, `CRPIX1W/2W` y `NAXIS1/2`
     corregidos.
  5. `ThreadPoolExecutor` con ≤ 16 conexiones a S3 (setting nuevo, p. ej. `ERRANTE_S3_PARALLEL`); reintentos en
     5xx/timeouts.
  *Acepta:* test offline que sirve un FITS sintético local con el mismo layout (monkeypatch del lector de rangos)
  y compara bit a bit contra `fits.open(...)[plano].data[y0:y1, x0:x1]`, con el WCS del parche a < 0,01 px del
  original; test `network` con un frame de Barnard a 5′: ≤ 1,5 MB bajados, < 5 s, segunda llamada sin requests.
- [ ] **WS1-5 (P0) `fetch_cutouts`: S3 primero, cutout de IRSA (IBE) de respaldo.** Devuelve
  `(ok: [(ref, path)], failed: [(ref, motivo)])` sin abortar. IBE: `cutout_url` sobre `irsa_uri`, ≤ 6 hilos
  (`MAX_PARALLEL_DOWNLOADS`), reintento en 503 respetando `retry-after`, 422 → `no_overlap` sin reintentar, nunca
  `HEAD`, validar que el cuerpo empiece con `SIMPLE`. Avisale a WS2 el cambio de firma (hoy `build.py` usa
  `zip(strict=True)`).
  *Acepta:* 20 frames de Barnard a 5′ en < 60 s por S3 y segunda corrida instantánea; forzando IBE (mock o flag)
  un frame llega por cutout; un frame sin solape aparece en `failed` como `no_overlap`.
- [ ] **WS1-6 (P0, chica) `read_spherex` con `MJD-AVG`** (fallback `MJD-OBS + XPOSURE/2/86400`) y, de paso, copiar
  a `extra` las claves de calidad del header (`L2DQAFLG`, `HE_AIRGLOW_CONT`, `AURORA_CONT`, `SHUTTLE_GLOW_CONT`,
  `PSF_FWHM`) para que WS2 las pueda mostrar.
  *Acepta:* test con un header real guardado como texto: `mjd == MJD-AVG`; sin `MJD-AVG` usa el fallback.
- [ ] **WS1-7 (P0) Índice SIA de los 5 objetivos en el repo** (plan B: S3 no depende de IRSA). Guardar
  `data/index/<id>.json` (`SearchResult`, dr1 + qr3, sin `*_deep`) con `errante search ... --out`, y que
  `search_frames` lo use si IRSA no responde y la posición cae a < 1′ de un índice (con aviso en el log).
  `data/index/` y `pipeline/tests/fixtures/ws1/` son tuyas según `scripts/owners.py`. Conteos esperados
  (SIA ✅): Barnard dr1 239 / qr3 119 · WISE 0855 258 / 0 · Eps Ind B 340 / 120 · RW Aur 226 / 109 ·
  R Dra 413 / 126 (+ `_deep` 1225 / 729, excluidos).
  *Acepta:* 5 archivos que validan como `SearchResult`, < 1 MB en total, conteos ±5 %; con IRSA caído (mock)
  `search_frames(269.4463, 4.7665)` devuelve el índice de Barnard.
- [ ] **WS1-8 (P1) `wavelength_at`** leyendo la tabla WCS-WAVE con su `TDIM` (la grilla depende del detector:
  D1 9×9, D2 11×11, D3 **9×14**, D4 13×20, D5 11×11, D6 9×9; no supongas que es cuadrada). Tiene que andar en el
  archivo completo (HDU WCS-WAVE por Range vía `hdu_layout`; copiarla también al mini-MEF) y en cutouts de IRSA
  (`CRPIX1W/2W` ya vienen corridos ✅). Receta del tutorial de IRSA (📄): `WCS(header, fobj=hdul, key="W")` con
  `sip = None`.
  *Acepta:* test con las WCS-WAVE reales de D1 y D3 guardadas como fixture de texto/JSON: la λ cae dentro de
  `em_min..em_max` del frame, y archivo completo vs cutout del mismo frame coinciden ± 0,01 µm.
- [ ] **WS1-9 (P1) FLAGS por Range (spike, máx. 1 h 30).** FLAGS es BINTABLE `RICE_1` con tiles de una fila
  (`ZTILE1 = 2040`, `ZTILE2 = 1`): leer los descriptores de las filas del parche y su porción del heap, y
  descomprimir sin dependencias nuevas (❓ cómo, con astropy). Si no sale en el tiempo: `flags=None` y WS2 lo
  informa; el cutout de IRSA trae FLAGS sin comprimir pero cuesta ~4 MB por frame.
  *Acepta:* para un frame, los FLAGS del parche coinciden con los del cutout de IRSA del mismo frame en la zona
  común.
- [ ] **WS1-10 (P2) "Fácil de actualizar con releases nuevos".** `s3.list_prefix` paginado (`IsTruncated` /
  `NextContinuationToken`); `parse_key` que acepte URIs de IRSA y URLs (release con la regex
  `(dr\d+|qr\d+)/level2/`); test `network` que falle si aparece un prefijo nuevo en la raíz del bucket (p. ej.
  `qr4/`, `dr2/`) para sumarlo a `ERRANTE_COLLECTIONS`.
  *Acepta:* test offline con un XML de listado truncado; `parse_key("ibe/data/spherex/dr1/...")` da release `dr1`.
- [ ] **WS1-11 (P2) Robustez de `cache.cached_download`:** capturar `requests.RequestException`, borrar el `.part`
  si falla, `.part` único por hilo, validar `SIMPLE`, no dormir después del último intento.
  *Acepta:* tests con respuestas simuladas (corte a mitad, página de error con 200).

## DROP (no hacer)

- **Buscar escaneando semanas en S3** (el viejo "fallback S3"): solo dr1 tiene 945.725 frames en 110 semanas; lo
  reemplaza el índice de WS1-7.
- **`fsspec` / `s3fs` / `use_fsspec=True`:** no están en `.venv` y `anon` es un parámetro de s3fs, no de https;
  `requests` + `Range` + `Header.fromstring` alcanza.
- **CSV de SIA:** está roto (`cloud_access` lleva JSON sin comillas: 51 columnas en el encabezado, 53 por fila).
- **Incluir `qr2`:** IRSA ya no lo indexa y sus semanas duplican las 110 de DR1.
- **`*_deep` por defecto:** en el NEP son 29.402 frames y decenas de MB por consulta.
- **Armar rutas S3 a mano o fijar versiones de pipeline:** usá siempre la key que devuelve la búsqueda.
- **Investigar HiPS** (vieja WS1-8): resuelto, el cubo DR1 de IRSA anda con CORS y es de WS5; los HiPS QR2 de CDS
  dan 404.

## Gotchas (✅ verificado 2026-11-14 · 📄 según documentación · ❓ abierto)

- ✅ **IRSA no envía CORS** (TAP, SIA, IBE, cutouts); S3 sí (`Access-Control-Allow-Origin: *`, permite `Range`;
  `Content-Range` no está expuesto). Todo lo de IRSA pasa por el backend.
- ✅ `MJD-OBS` = `MJD-BEG` = **inicio**; `MJD-AVG` = mitad (+57,6 s; `XPOSURE` = 113,58 s). En TAP,
  `time_bounds_lower/upper` = `MJD-BEG/MJD-END`. `DATE` es la fecha de creación del archivo: no usar.
- ✅ Cutout de IRSA: sin solape → **422** "Input position contains invalid values (NaNs or infs)."; `HEAD` → **405**;
  bajo carga → **503** "Server busy, retry later" con `retry-after: 5`.
- ✅ Cutout ≈ **4 MB** de 5′ a 15′ (8,4 MB a 1°) en 4–15 s: la tabla EPSF (441 filas × 8752 B ≈ 3,86 MB) viaja
  entera siempre. 📄 los cutouts SPHEREx no se comprimen con gzip.
- ✅ S3 por Range: header 57,6 KB en 0,65 s; 49 filas (399.840 B) en 1,0–1,4 s; 147 filas en 1,42 s; 587 filas en
  2,05 s. Throughput de una muestra: S3 1,88 MB/s contra IRSA 0,27 MB/s.
- ✅ Layout del MEF: PRIMARY · IMAGE (2040×2040, `BITPIX = -32` sin comprimir; en un QR3 los datos empiezan en el
  byte 28.800) · FLAGS (BINTABLE `RICE_1`, `ZTILE` 2040×1; en QR2 y en los cutouts es IMAGE int32 sin comprimir) ·
  VARIANCE · ZODI · EPSF (`PSF` en QR2) · WCS-WAVE. No fijes offsets: recorré los headers.
- ✅ WCS-WAVE depende del **detector** (`TDIM3`): D1 (2,9,9), D2 (2,11,11), D3 (2,9,14), D4 (2,13,20), D5
  (2,11,11), D6 (2,9,9).
- ✅ Versiones de pipeline variables por semana **y** detector (solo en Barnard, de -228 a -243).
- ✅ Colecciones (conteo en obscore): `spherex_dr1` 945.725, `spherex_dr1_deep` 233.681, `spherex_qr3` 362.124,
  `spherex_qr3_deep` 86.700, `spherex_dr1_cal` 88. QR2: 0 filas en SIA/TAP; 📄 se puede descargar hasta
  febrero de 2027, pero no buscar.
- ✅ S3: dr1 110 semanas (2025W17_4B → 2026W20_1A), qr3 41 (2026W20_2A → 2026W40_2A), qr2 129 (superado). DR1 +
  QR3 = cobertura continua, 0 OBSID repetidos en Barnard. Los directorios `l2b_retry-*` traen OBSIDs que no están
  en el normal: no los filtres.
- ✅ SIA: 1–4 s por colección (Barnard dr1 2,2–3,1 s); `MAXREC=500` → 4 s; `TIME=61000 61030` funciona; `BAND` ❓
  no probado. TAP: 8–11 s; obscore + `CONTAINS` 14 s; el JOIN obscore–plane falla (`st_covers`). 📄 SIA va
  ~1 día atrás de TAP.
- ✅ SIA con círculo r = 0,01° (intersección) da 240/124 frames contra 239/119 de TAP por punto (contención).
- ✅ `obs_id` de SIA = `2025W33_2C_0321_1` (sin detector); en TAP `plane.obsid` es un UUID y `plane.datarelease`
  una fecha.
- ✅ `em_min/em_max` es la banda entera del detector (D6: 4,41–5,01 µm); la λ en el objetivo sale de WCS-WAVE (LVF).
- ✅ Archivos de 61–67 MB: nunca bajarlos enteros. `*.fits` está en `.gitignore`: fixtures como texto, JSON o
  VOTable.
- ✅ `.venv`: astropy 8.0.2 y numpy 2.5.4, sin fsspec/s3fs/aiohttp; el CI instala solo `pipeline[dev]`.
- ❓ Throughput desde el host de deploy (US-East) y límites de tasa de IRSA: medirlos cuando WS4 despliegue.

## Dependencias

- **Nadie te bloquea.** Para el índice (WS1-7) usá los `id` y centros de `pipeline/errante/config/fields.toml`
  (`barnards-star`, `eps-indi-b`, `wise-0855`, `rw-aurigae`, `r-draconis`), ya propagados a la época media de los
  datos. Con r = 0,01° y frames de ~3,5° la época casi no cambia el resultado.
- **WS2** programa contra tus firmas: si la implementación tarda, mergeá temprano un PR con las firmas nuevas
  (stubs con `NotImplementedError`) y fixtures.
- **WS4** llama a `search_frames` / `fetch_cutouts` desde `/api/search` y `/api/view` y los mockea en sus tests:
  no cambies firmas sin avisar.
- **Contrato:** `FrameRef`/`SearchResult` 0.1.0 alcanzan (`Release` acepta dr1/qr3); con 0.3.0 `Release` pasa a
  `str` con patrón.
- **Sin red:** fixtures + `@pytest.mark.network` para lo vivo:
  `ERRANTE_NETWORK_TESTS=1 python scripts/dev.py test-py` (PowerShell: `$env:ERRANTE_NETWORK_TESTS=1; py scripts/dev.py test-py`).

## Prompt de arranque (pegalo en Claude Code / Codex)

> Sos el agente de WS1 (datos SPHEREx) del repo del equipo para NASA Space Apps 2026, reto "Planet X and
> SPHEREx". Leé `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACT.md`, `docs/COLLABORATION.md` y
> `tasks/WS1-data-access.md`. Trabajá SOLO en tus rutas: `pipeline/errante/data/`, `pipeline/errante/settings.py`,
> `pipeline/tests/test_data_*.py`, `docs/DATA.md` y el subcomando `search` de `cli.py`. Empezá por WS1-1 (leer
> `docs/DATA.md` entero: es la fuente de verdad y la mantenés vos) y WS1-2 (`search_frames` con SIA2 en VOTable +
> TAP de respaldo).
> No inventes servicios, tablas ni columnas: verificalos con una consulta real; si no tenés red, dejá el código, un
> test offline con fixture y un test `@pytest.mark.network`, y decímelo. Nada de dependencias nuevas sin
> preguntarme. Corré `python scripts/dev.py check` (Windows: `py scripts/dev.py check`; en Mac/Linux `make check`
> también sirve), mostrame el diff antes de commitear y commiteá como `ws1: <verbo + qué>` con el trailer
> `Co-Authored-By:` del agente.
