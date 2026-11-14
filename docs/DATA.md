# Datos SPHEREx: hechos verificados

Dueño: **WS1**. Los demás no editan arriba: agregan al final, en [Notas de otros WS](#notas-de-otros-ws), o le
pasan el hecho a WS1. Cada hecho dice **cómo** y **cuándo** se verificó. Si algo de acá está mal, corregilo en un
PR (`ws1: docs/DATA.md ...`).

Etiquetas: ✅ verificado en vivo (fecha y cómo) · 🧮 cálculo nuestro sobre datos ✅ (reproducible, se indica el
método) · 📄 según documentación, no verificado por nosotros · ❓ abierto o INFERIDO (ver §6).

Casi todo lo ✅ sale de la revisión del 2026-11-14 (curl/HTTP Range anónimos contra IRSA y S3, ~14:00 UTC,
reconfirmado a las 11:27 hora local). Plan y prioridades: [`PLAN.md`](PLAN.md).

## 0. Lo que tenés que saber antes de tocar código

1. **Buscar**: SIA2 en **VOTable** sobre `spherex_dr1` + `spherex_qr3` (`*_deep` opcional). TAP como respaldo.
   El CSV de SIA está roto (§3.2). Las colecciones van en config, nunca hardcodeadas.
2. **Leer píxeles**: por **HTTP Range en S3** (~0,4 MB / ~1 s por frame a 5′). El cutout de IRSA pesa ~4 MB fijos
   y tarda 4–15 s: es el fallback (§3.4, §3.5).
3. **IRSA no envía CORS; S3 sí** → hace falta backend para buscar (§3.1).
4. **Tiempo**: `MJD-OBS` es el **inicio** de la exposición. Usá `MJD-AVG` (§2.2).
5. **Nunca armes rutas a mano**: la versión de pipeline cambia por semana y por detector. Usá la key/URI que
   devuelve la búsqueda (§1.2).
6. **WCS-WAVE depende del detector** (9×9 … 13×20): leé `TDIM`, no supongas la forma (§2.4).
7. **FLAGS**: `SOURCE` (bit 21) no es "malo"; `OUTLIER`/`TRANSIENT` pueden caer justo sobre un objeto que se
   mueve (§2.3).
8. **QR2 ya no está indexado** en IRSA (sigue en S3): serie temporal = DR1 + QR3 (§1.1).
9. **CDS Estrasburgo está degradado** desde el 2026-11-09: Aladin desde jsdelivr y todo lo demás desde espejos (§5).

## 1. Bucket público en S3 y releases

### 1.1 Releases y vigencia ✅ (2026-11-14, listado S3 anónimo + SIA/TAP de IRSA)

- Bucket `nasa-irsa-spherex` (us-east-1), **anónimo por HTTPS**, sin cuenta AWS:
  `https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/?list-type=2&delimiter=/&prefix=<prefijo>`
  (AWS CLI: `aws s3 ls --no-sign-request s3://nasa-irsa-spherex/`). Prefijos de primer nivel: `dr1/`, `qr2/`, `qr3/`.
- El listado devuelve **como máximo 1000 claves por página** (`IsTruncated=true` + continuation token): el
  directorio de un detector en una semana tiene más de 1000 archivos. Hay que paginar.

| Release | Semanas en `level2/` | ¿Indexado en IRSA (SIA/TAP)? | Colecciones | Vigencia |
|---|---|---|---|---|
| `dr1/` | 110: `2025W17_4B` → `2026W20_1A` | ✅ sí | `spherex_dr1`, `spherex_dr1_deep`; además `spherex_dr1_cube` (cubo all-sky, 📄 doc de IRSA) | Data Release 1, publicado en IRSA en nov-2026 (📄 página de IRSA) |
| `qr3/` | 41: `2026W20_2A` → `2026W40_2A` | ✅ sí | `spherex_qr3`, `spherex_qr3_deep` | Quick Release 3, lo más reciente (desde sep-2026, 📄) |
| `qr2/` | 129: `2025W17_4B` → `2026W29_2A` | ❌ **no** (SIA da 0 filas en Barnard y NEP; obscore no lo lista) | — | Descargable "through February 2027" pero "no longer searchable" (📄 doc de IRSA). HEAD a un archivo QR2 en IBE: 200 ✅ |

- Solapamiento de semanas ✅: dr1∩qr2 = 110 (las 110 semanas de DR1 también están en QR2), qr2∩qr3 = 19,
  **dr1∩qr3 = 0**.
  → **Serie temporal = `dr1` + `qr3` (+ `*_deep`)**; QR2 está superado. Si algo lee S3 directo, excluir `qr2/` o
  deduplicar por `(obs_id, detector)` con prioridad dr1 > qr3 > qr2. En Barnard hay 0 OBSIDs repetidos entre dr1 y qr3.
- La colección `spherex` (sin sufijo) devuelve 0 filas ✅.
- Conteos por colección ✅ (TAP `SELECT obs_collection, COUNT(*) FROM spherex.obscore GROUP BY ...`, tardó 153 s:
  no usar en vivo):

| Colección | Frames (exposición × detector) |
|---|---|
| `spherex_dr1` | 945.725 |
| `spherex_dr1_deep` | 233.681 |
| `spherex_qr3` | 362.124 |
| `spherex_qr3_deep` | 86.700 |
| `spherex_dr1_cal` | 88 |

- 📄 IRSA ingesta datos nuevos **semanalmente**; aparecen primero en los directorios y en TAP, y en SIA con ~1 día
  de retraso (doc de IRSA, no medido).
- **Releases nuevos** (consideración del reto): las colecciones son configuración (`ERRANTE_COLLECTIONS`, ver
  [`PLAN.md`](PLAN.md) §2) y conviene un test de red que avise si aparece un prefijo nuevo en la raíz del bucket
  (p. ej. `qr4/`, `dr2/`).

### 1.2 Layout y nombres ✅ (2026-11-14, listado S3 + URIs reales de TAP/SIA)

- `<release>/level2/<semana>/<version-pipeline>/<detector>/<archivo>.fits`, ej.
  `dr1/level2/2025W19_2B/l2b-v27-2026-198/1/level2_2025W19_2B_0007_1D1_spx_l2b-v27-2026-198.fits`.
- Nombre: `level2_<OBSID>D<detector>_spx_<version>.fits` (parseado en `errante.data.s3.parse_key`; funciona con
  los 358 URIs reales de Barnard, incluido `l2b_retry`). Sufijos de semana vistos: 1A, 1B, 1C, 2A, 2B, 2C, 2D, 4B.
- **La versión de pipeline varía por semana y por detector**: vistas hoy `l2b-v27-2026-197`, `-198`, `-228` …
  `-243` (solo los frames de Barnard, DR1 + QR3, ya van de -228 a -243) y `-268` (QR3). **No construyas rutas**:
  usá `cloud_access.aws.key` (SIA) o `artifact.uri` (TAP).
- Además del directorio normal, algunas semanas tienen `l2b_retry-v27-.../` con **OBSIDs distintos** (solapamiento
  0): hay que incluirlos. La búsqueda de IRSA ya los devuelve.
- `irsa_uri` ↔ `s3_key`: es solo quitar `ibe/data/spherex/` ✅ (HEAD 200 con el mismo `Content-Length` en S3 y en
  `https://irsa.ipac.caltech.edu/ibe/data/spherex/<key>`).
- Tamaño por archivo: DR1 **60,7–67 MB** (ej. 61.188.480 y 65.885.760 B), QR3 ~65 MB (64.941.120 B), QR2 71,6 MB
  (FLAGS sin comprimir). Para un parche chico **no bajes archivos completos** (§3.4).
- Calibraciones por release (prefijos hermanos de `level2/`): dr1 21 (incluye `epsf/`, `hips5_cube/`,
  `aurora_template/`, `spectral_wcs/`, `sip/`, …), qr3 20, qr2 13 (`average_psf/`, sin `epsf/`).
- **S3 no permite buscar por posición** → para saber qué archivos cubren un punto, usá IRSA (§3).

## 2. Estructura de un archivo Level 2

✅ 2026-11-14: headers leídos por HTTP Range de archivos DR1 (`2025W19_2B_0007_1D1`), QR3 (`2026W40_2A_0001_1D1`,
`2026W34_1A_0363_1D2`) y QR2, y de cutouts reales de IRSA.

### 2.1 HDUs

| HDU | EXTNAME | Contenido |
|---|---|---|
| 0 | PRIMARY | sin datos (`VERSION`, ej. `'7.0.5'`) |
| 1 | `IMAGE` | 2040×2040 float32 (`BITPIX=-32`), **sin comprimir**, **MJy/sr**, luz zodiacal **NO** restada |
| 2 | `FLAGS` | 2040×2040 int32, máscara de bits. Archivo completo DR1/QR3: BINTABLE comprimido `RICE_1` con tiles de 1 fila (`ZTILE1=2040`, `ZTILE2=1`). En **QR2 y en cutouts**: IMAGE int32 sin comprimir. astropy lo abre como imagen en ambos casos |
| 3 | `VARIANCE` | 2040×2040 float32, (MJy/sr)² |
| 4 | `ZODI` | 2040×2040 float32, modelo zodiacal (restalo vos: `IMAGE - ZODI`) |
| 5 | `EPSF` | PSF efectiva: BINTABLE de 441 filas × 8752 B (~3,86 MB; ePSF 33×33, `CWAVE`, `CBAND`). En QR2 se llama `PSF` (IMAGE 101×101) |
| 6 | `WCS-WAVE` | tabla de longitud de onda por píxel; **la grilla depende del detector** (§2.4) |

`read_spherex` abre los HDUs por nombre (no por índice): tolera QR2 y cutouts.

### 2.2 Header de `IMAGE`: claves útiles

- **Tiempo** ✅: `MJD-OBS` = `MJD-BEG` = **inicio** de la exposición; `MJD-AVG` = **punto medio**; `MJD-END` = fin.
  `XPOSURE` = 113,58 s (sesgo de ~57 s si usás `MJD-OBS`). Ej.: MJD-OBS 60803.522714201, MJD-AVG 60803.523380391.
  **Usar `MJD-AVG`** (fallback: `MJD-OBS + XPOSURE/2/86400`); desde la búsqueda, `(t_min + t_max)/2`.
  En TAP `time_bounds_lower/upper` = MJD-BEG/MJD-END, y SIA `t_min/t_max` son los mismos valores. `DATE-OBS` =
  `DATE-BEG`. `DATE` = **fecha de creación del archivo** (ej. 2026-07-17 en un frame de 2025-05-08): no usar.
- Identidad: `DETECTOR` (1–3 SWIR, 4–6 MWIR), `OBSID`, `BUNIT` (`'MJy / sr'`).
- **WCS espacial**: `RA---TAN-SIP`/`DEC--TAN-SIP` con `A/B/AP/BP_ORDER=3` (SIP inverso incluido) → astropy
  `WCS(header)`. La orientación **no es norte-arriba** y cambia por exposición (rotación ≈ −18,9° en un archivo,
  ~175° en un cutout): siempre reproyectar. Hay un WCS alterno `A` (LINEAR) y uno `W` (WAVE-TAB, §2.4).
- `PSF_FWHM` (ej. 7,53″ en D1 DR1; el mismo frame en QR2 dice 5,25″; 9,04″ en un cutout D6), `OMEGA_MEDIAN`
  (HIERARCH, ≈ 37,87 arcsec² → píxel ≈ 6,15″), `PXSRCMSK` (% de píxeles con flag `SOURCE`, ej. 68,44).
- Geometría: posición de la nave `X_SC/Y_SC/Z_SC` [km, `XYZ_SC_SYSTEM='GEOCENTER'`], velocidades `VX_SC…`,
  `SPS_ELON/SPS_ELAT` (eclípticas del apuntado).
- **Contaminación y calidad** (consideración del reto: mostrarlas como metadata). Están también en los cutouts:

| Clave | Valores vistos | Nota |
|---|---|---|
| `HE_AIRGLOW_CONT` (HIERARCH) | `F` | contaminación por airglow de He |
| `AURORA_CONT` | `F`; **`T`** en QR3 `2026W40_2A_0001_1D1` | |
| `SHUTTLE_GLOW_CONT` | `F` | |
| `L2DQAFLG` | `'Pass'` | QA del nivel 2 (también existe `L1DQAFLG`) |
| `SATSTRKS`, `NBLMSRCS`, `SPS_FLAGS` (`'all_sky'`), `DETCOORD` (`'sky'`), conteos `N_*` | — | presentes; significado exacto ❓ (ver Explanatory Supplement) |

### 2.3 Bits de FLAGS ✅ (tarjetas `MSKNnnnn` de un header DR1 real; coinciden con `errante.imaging.flags`)

| bit | nombre | bit | nombre | bit | nombre |
|---|---|---|---|---|---|
| 0 | TRANSIENT | 11 | COLD | 22 | GHOST |
| 1 | OVERFLOW | 12 | FULLSAMPLE | 23 | GHOST_FPA |
| 2 | SUR_ERROR | 14 | PHANMISS | 24 | GHOST_EXT |
| 6 | NONFUNC | 15 | NONLINEAR | 25 | STREAK |
| 7 | DICHROIC | 17 | PERSIST | 26 | BLOOM |
| 9 | MISSING_DATA | 19 | OUTLIER | 28 | HALO |
| 10 | HOT | 20 | CROSSTALK | | |
| | | 21 | **SOURCE** | | |

- Descripciones del header (`MSKD`): GHOST = fuente brillante dentro de la exposición, GHOST_FPA = fuente
  brillante en otro detector, GHOST_EXT = fuente brillante fuera del campo.
- ⚠️ **"Cualquier bit ≠ 0 = malo" está MAL**: `SOURCE` marca todas las estrellas (68 % de los píxeles en el archivo
  inspeccionado). ⚠️ `OUTLIER`/`TRANSIENT` pueden dispararse **justo sobre un objeto en movimiento**: no los
  enmascares a ciegas. Implementado en `errante.imaging.flags` (`DEFAULT_BAD`, `MAYBE_MOVER`, `bits_from_header`).
- Para el visor: mostrar los flags como **metadata/capa** (fracción por tipo, flags en el píxel del objetivo); no
  poner NaN sobre el objetivo. Saturación posible en objetivos brillantes (`OVERFLOW`, `NONLINEAR`): ❓ sin medir.

### 2.4 Longitud de onda: `WCS-WAVE` ✅

Cada exposición mide **una λ distinta en cada punto del detector** (filtro lineal variable, LVF). La λ en una
posición sale de la tabla `WCS-WAVE`, cuya grilla **depende del detector** (misma versión `-230`, `TDIM3` leído por
Range en S3; D1 confirmado también en DR1, QR2 y QR3, y D5 en DR1 y QR3):

| Detector | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|
| `TDIM3` | `(2,9,9)` | `(2,11,11)` | `(2,9,14)` | `(2,13,20)` | `(2,11,11)` | `(2,9,9)` |

- **Leé la forma desde `TDIM`**; no la supongas cuadrada (D3 y D4 no lo son).
- 📄 Receta del tutorial de IRSA: `spectral_wcs = WCS(header, fobj=hdul, key="W"); spectral_wcs.sip = None`.
- ✅ En los cutouts `CRPIX1W/CRPIX2W` vienen actualizados: la tabla sigue siendo usable.
- ⚠️ `em_min/em_max` de SIA (y `energy_bounds_*` de TAP) son el rango **del detector entero** (ej. D6
  4,4115–5,0096 µm), **no** la λ en tu objetivo.

## 3. Acceso: buscar en IRSA y leer píxeles

Fuentes 📄: [SPHEREx Data Access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/),
[tutorial intro](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/),
[tutorial cutouts](https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/),
[parámetros de cutout IBE](https://irsa.ipac.caltech.edu/ibe/cutouts.html),
[SIA2 de IRSA](https://irsa.ipac.caltech.edu/ibe/sia.html),
[Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf).
GUI: [SPHEREx Data Explorer](https://irsa.ipac.caltech.edu/applications/spherex).

### 3.1 CORS ✅ (2026-11-14, `curl -H 'Origin: https://example.org'`, GET y preflight OPTIONS)

| Servicio | CORS | Detalle |
|---|---|---|
| IRSA TAP (`/TAP/sync`), SIA (`/SIA`), IBE `.fits` (también con Range → 206), cutouts, DataLink | ❌ **NO** | 200 sin `Access-Control-Allow-Origin` |
| S3 `nasa-irsa-spherex` (listado, GET con Range, preflight) | ✅ **SÍ** | `ACAO: *`, métodos `HEAD, GET`, `Allow-Headers: range`; expone solo `ETag` y `x-amz-meta-custom-header` (`Content-Range` no es legible desde JS; `Content-Length` sí) |
| HiPS de IRSA (cubo SPHEREx, espejos 2MASS/AllWISE/DSS2) | ✅ SÍ | `ACAO: *` (§5.1) |
| VizieR CfA, Sesame CfA, SkyBoT | ✅ SÍ | §5.3, §5.4 |
| ESA Gaia TAP, IRSA TAP de catálogos (`catwise_2020`, `allwise_p3as_psd`) | ❌ NO | solo desde el backend |

→ **El navegador no puede buscar frames en IRSA**: la búsqueda va por el backend. S3 sí se puede leer desde el
navegador, pero en JS habría que reimplementar WCS con SIP, RICE y reproyección: no en las ~36 h que quedan.

### 3.2 SIA2 (búsqueda principal) ✅

- `https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1&POS=circle+269.4463+4.7665+0.01` (radio en grados).
  Una consulta por colección.
- **Pedí VOTable (el formato por defecto)** y parseá con `astropy.io.votable`/pyvo. **El CSV está roto**: la columna
  `cloud_access` lleva JSON con comas sin comillas → 51 columnas en el encabezado y 53 por fila (verificado con
  `csv.reader`). Las columnas 1–48 quedan bien, pero no te fíes.
- Tiempos: **1–4 s** por colección (0,9–4,5 s; colecciones vacías ~1 s). Barnard: `spherex_dr1` 239–240 filas en
  1,8–3,1 s; `spherex_qr3` 119–124 en 1,5 s. NEP `spherex_dr1_deep`: ~20.800 filas, 19 MB, ~40 s.
- Parámetros que **funcionan**: `MAXREC=500` (4,0 s); `TIME=61000 61030` (rango MJD; 1.558 filas en 6,4 s).
  `BAND`: ❓ no probado.
- `POS=circle` es **intersección** con el footprint (240/124 filas en Barnard contra 239/119 de TAP con
  `CONTAINS(punto)`): puede traer frames que cubren solo parte del parche.
- Columnas útiles:

| Columna | Ejemplo / nota |
|---|---|
| `obs_id` | `2025W33_2C_0321_1` (sin detector) |
| `energy_bandpassname` | `SPHEREx-D6` → detector. Deduplicar por `(obs_id, detector)` |
| `obs_publisher_did` | `ivo://irsa.ipac/spherex_dr1?2025W33_2C_0321_1/D6` |
| `access_url` | URL **directa** al `.fits` en IBE (base para el cutout, §3.5) |
| `cloud_access` | JSON `{"aws": {"bucket_name": "nasa-irsa-spherex", "key": "dr1/level2/...fits", "region": "us-east-1"}}` → **key de S3** |
| `s_region` | `POLYGON ICRS ...` (footprint del detector) |
| `t_min`, `t_max` | MJD-BEG / MJD-END → `mjd = (t_min + t_max)/2` |
| `em_min`, `em_max`, `em_res_power` | rango del detector en metros (no la λ en el objetivo) |
| `obs_collection`, `t_exptime` (113,5826), `s_pixel_scale` (6,150), `s_fov` (3,485°) | |

### 3.3 TAP (respaldo) ✅

- Endpoint `https://irsa.ipac.caltech.edu/TAP/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=...` (el CSV de TAP
  sale bien: columnas explícitas). **8–19 s por consulta** (Barnard con la consulta del repo: 358 filas en 11,35 s;
  filtrando D2: 61 filas en 8,2 s; obscore + `CONTAINS`: 14 s; WISE 0855 en obscore: 12–19 s).
- Tablas (`TAP_SCHEMA.tables`, 0,6 s): **`spherex.obscore`, `spherex.observation`, `spherex.plane`,
  `spherex.artifact`, `spherex.provenance_input`**.
  - `spherex.plane`: `planeid`, `obsid` (**UUID de CAOM**, no el OBSID de SPHEREx), `poly`,
    `time_bounds_lower/upper` (MJD-BEG/END), `energy_bandpassname` (`'SPHEREx-D1'…'SPHEREx-D6'`),
    `energy_bounds_lower/upper` [m], `datarelease` (**una fecha**, ej. `'2026-10-04 05:45:39'`, no `'dr1'`),
    `metrics_maglimit` (vacía: la profundidad por frame no sale de la metadata).
  - `spherex.artifact`: `uri` (relativo: `ibe/data/spherex/<release>/level2/...`; anteponer
    `https://irsa.ipac.caltech.edu/`), `planeid`, `contentlength`, `producttype`.
  - `spherex.obscore`: `obs_collection`, `energy_bandpassname`, `t_min`, `s_region`; su `access_url` es un
    **DataLink** (`https://irsa.ipac.caltech.edu/datalink/links/spherex?ID=ivo://irsa.ipac/spherex_dr1?2025W33_2C_0321_1/D6`),
    no el FITS directo.
- La consulta del repo (`errante.data.irsa.ADQL_FRAMES_AT_POSITION`: `plane JOIN artifact` +
  `CONTAINS(POINT('ICRS', ra, dec), p.poly)`) **funciona**. `obs_id` y release hay que sacarlos del `uri`.
- ⚠️ **Trampa**: hacer `JOIN` de `spherex.obscore` con `spherex.plane` + `CONTAINS` falla con
  `function st_covers(character varying, geography) does not exist`. Usá `plane`+`artifact`, u `obscore` solo.
- Para un FOV elegible conviene `INTERSECTS` con `CIRCLE` en vez de `CONTAINS(POINT)` (❓ no medido).
- El DataLink devuelve el `access_url`, el servicio `ibe-cutout` y `cloud_access` con bucket/key/región.

### 3.4 Leer píxeles por HTTP Range en S3 (camino principal) ✅

Medido el 2026-11-14 desde una máquina local del equipo (una muestra; no desde US-East):

| Lectura | Bytes | Tiempo |
|---|---|---|
| headers (20 bloques) | 57.600 B | 0,65 s |
| 49 filas de IMAGE (≈ 5′) | 399.840 B | 1,00 s (DR1) / 1,38 s (QR3) |
| 147 filas (≈ 15′) | 1.199.520 B | 1,42 s |
| 587 filas (≈ 1°) | 4.789.920 B | 2,05 s |
| Range de 4 MB, mismo archivo | 4 MB | S3 2,12 s (1,88 MB/s) contra IBE 14,6 s (0,27 MB/s) |

TTFB ~0,5 s. Offsets (no los hardcodees: calculalos de los headers):

- PRIMARY + header de IMAGE = **28.800 B** en los tres archivos medidos → los datos de IMAGE empiezan en el byte
  28.800. Fila = 2040 × 4 B = **8.160 B**, float32 **big-endian** (`>f4`); aplicar `BSCALE/BZERO` si existieran.
- IMAGE ocupa 2040·2040·4 = 16.646.400 B (múltiplo exacto de 2880) → el header de FLAGS empieza en
  **16.675.200** (leído así en el DR1 `2025W19_2B_0007_1D1`).
- **FLAGS** es BINTABLE `RICE_1` con tiles de 1 fila y heap (`PCOUNT` 7.287.942 B en el archivo medido): leer
  filas sueltas exige leer los descriptores de esas filas y después sus bytes en el heap, y descomprimir RICE.
  ❓ No implementado ni verificado (P1 en el plan).
- Los offsets de **VARIANCE** y **ZODI** dependen del tamaño comprimido de FLAGS: leé el header de FLAGS y sumá
  `NAXIS1·NAXIS2 + PCOUNT` redondeado a múltiplos de 2880. Las dos son float32 sin comprimir, como IMAGE.
- Receta recomendada: `requests` con `Range` + `astropy.io.fits.Header.fromstring` (headers) + `WCS(header)` para
  pasar las esquinas del parche a filas del detector (la imagen está rotada: leé el bounding box en filas y
  recortá columnas). Paralelismo ≤ 16 conexiones a S3.
- ⚠️ La receta `fits.open(url_https, use_fsspec=True, fsspec_kwargs={'anon': True})` es **dudosa**: `anon` es un
  parámetro de s3fs (`s3://`), no de https, y el `.venv` no tiene fsspec, s3fs ni aiohttp (✅ listando
  `site-packages`). Que falle es INFERIDO. ❓ Nadie probó todavía astropy leyendo un FITS remoto por Range de
  punta a punta.

### 3.5 Cutouts de IRSA/IBE (fallback) ✅

- `<access_url>?center=<ra>,<dec>&size=<s>` (`size` en grados por defecto; `size=5arcmin` válido). Ejemplo 📄 de
  IRSA: `.../qr3/level2/2026W21_2A/l2b-v27-2026-268/1/level2_2026W21_2A_0001_2D1_spx_l2b-v27-2026-268.fits?center=337.8783221,-5.1891588&size=0.1`.
- **Pesa ≥ ~4 MB aunque pidas un recorte chiquito**: viaja la tabla `EPSF` entera (441 × 8752 B = 3.862.080 B) y
  no se gzipea (📄 "SPHEREx cutouts will not be gzipped"):

| `size` | IMAGE | Bytes | Tiempo |
|---|---|---|---|
| 0,05° (3′) | 29×29 | 3.962.880 | 11,4–13,7 s |
| 5′ | 49×49 | 3.985.920–3.988.800 | 3,8–15,3 s |
| 10′ | 98×98 | 4.101.120 | 4,4–11,3 s |
| 15′ | 147×146 | 4.288.320 | 10,7 s |
| 1° | 587×473 | 8.389.440 | 9,3 s |

  TTFB 1,7–2,3 s; ~0,27–0,4 MB/s. Para Barnard (358 frames) serían ~1,4 GB: inviable en vivo.
- Devuelve el mismo MEF (7 HDUs) recortado, en **orientación nativa** (TAN-SIP, `CRPIX` desplazado, `PC` rotado)
  y a veces **no cuadrado** → reproyectar. FLAGS viene como IMAGE int32 sin comprimir. Conserva `MJD-AVG`,
  `L2DQAFLG` y los `*_CONT`.
- Errores:
  - **Sin superposición → HTTP 422** `Input position contains invalid values (NaNs or infs).` (0,75 s), **no 500**.
    Mapearlo a "sin solape", no a error de red.
  - **HEAD sobre la URL del cutout → 405**: no hagas HEAD.
  - **503 `Server busy, retry later`** con `retry-after: 5`: transitorio; reintentar con backoff (el 3.er intento dio 200).
- Validar que la respuesta empiece con `SIMPLE` antes de cachearla.

### 3.6 Límites y concurrencia

- IRSA: ≤ 6 hilos para cutouts (`ERRANTE_MAX_PARALLEL`), reintentos con backoff, no paralelizar consultas TAP.
  📄 El tutorial de cutouts usa 7–12 workers y cita "about 5 minutes for 700 images" en serie.
- S3: ≤ 16 conexiones. ❓ Throughput desde un host de deploy en US-East: sin medir (se espera mejor que desde acá).
- Cachear en disco: búsquedas por `(ra, dec redondeados, colecciones)` y lecturas por `(key, filas)`.
- ❓ Límites de tasa formales de IRSA y tamaño máximo de cutout: sin documentar/medir.

## 4. Instrumento, survey y cobertura

### 4.1 Instrumento y survey

- 📄 6 detectores H2RG 2040×2040, campo ~3,5°×3,5° (✅ `s_fov` 3,485°), píxel **6,15″** (✅ `s_pixel_scale`,
  `OMEGA_MEDIAN`). Pares simultáneos por dicroico (D1,D4), (D2,D5), (D3,D6): ✅ tienen tiempos idénticos en TAP.
- 📄 Bandas aproximadas: D1 0,75–1,11 µm, D2 1,11–1,64, D3 1,64–2,42 (R≈41), D4 2,42–3,82 (R≈35), D5 3,82–4,42
  (R≈110), D6 4,42–5,00 (R≈130). ✅ 102 canales = 6 detectores × 17 (índice `17·(banda−1) + (canal−1)` en el cubo
  HiPS; los canales 50 y 51, dicroicos, vienen vacíos). ✅ D6 en SIA: 4,4115–5,0096 µm, `em_res_power` 127,8.
- ✅ Exposición de 113,58 s. Dentro de una visita, los apuntados están separados ~2,1 min (mediana, Barnard).
- 📄 Cielo completo cada ~6 meses; **campos profundos** en los polos eclípticos (NEP ≈ RA 270°, Dec +66,56°; SEP ≈
  RA 90°, Dec −66,56°) con muchísimas más épocas. ✅ Primeros datos: MJD 60789,75 (2025-04-24, `t_min` del cubo
  HiPS); primera semana en S3: `2025W17_4B`.
- Glosario de tiempo (propuesta del contrato 0.3.0, [`PLAN.md`](PLAN.md) §3): **exposición** (1 archivo, 1
  detector) · **visita** (exposiciones separadas < 6 h) · **temporada/pasada** (bloques separados > 20 días).

### 4.2 Cobertura de los 5 objetivos oficiales ✅

✅ SIA2 (CSV, columnas 1–48) sobre `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`, y TAP
obscore con `CONTAINS`, 2026-11-14. Coinciden salvo Eps Ind B (460 en SIA contra 458 en TAP: intersección contra
punto). 🧮 Temporadas: agrupando `(t_min+t_max)/2` con hueco > 30 d. Centros, movimiento esperado y método:
[`SCIENCE.md`](SCIENCE.md) §0; configuración en `pipeline/errante/config/fields.toml`.

| Objetivo (centro de la consulta TAP) | Frames: dr1 / qr3 / deep | 🧮 Visitas (> 6 h) | 🧮 Temporadas: MJD (n) | Fechas |
|---|---|---|---|---|
| Barnard (269.4463, 4.7665) | **358**: 239 / 119 / 0 | 48 | 60903–60949 (118) · 61110–61165 (121) · 61269–61306 (119) | 2025-08-15 → 2026-09-22 |
| Eps Ind B (331.0964, −56.8006) | **460**: 340 / 120 / 0 | 74 | 60790–60836 (120) · 60947–60992 (147) · 61149–61164 (73) · 61305–61315 (120) | 2025-04-24 → 2026-10-02 |
| WISE 0855 (133.7600, −7.2422) | **258**: 258 / **0** / 0 | 37 | 60801–60802 (30) · 60980–61022 (128) · 61151–61174 (100) | 2025-05-05 → 2026-05-14 |
| RW Aur (76.9565, 30.4014) | **335**: 226 / 109 / 0 | 48 | 60919–60938 (112) · 61092–61111 (114) · 61285–61300 (109) | 2025-09-01 → 2026-09-16 |
| R Dra (248.1676, 66.7550) | **2493**: 413 / 126 / 1225 + 729 | 249 | 60790–60879 (240) · 60916–61310 casi continuo (2253) | 2025-04-24 → 2026-09-27 |

Detalles ✅/🧮 que importan para los coadds por (temporada × detector):

- Barnard: 17–25 frames por detector y temporada. RW Aur: 18–19, muy parejo.
- Eps Ind B: **D1/D4 casi vacíos** en la 1.ª temporada (3 frames) y **sin frames** en la última.
- WISE 0855: **sin datos QR3**; la 1.ª temporada tiene solo 3–8 frames por detector.
- R Dra: D2/D5 tienen ~89 frames contra ~575–585 de D1/D3/D4/D6.
- El umbral importa: con hueco > 20 d (el del glosario), Barnard da 3 bloques principales + 3 chicos de cola (10,
  8 y 2 frames, a 20–25 d) y WISE 0855 parte su 2.ª temporada (110 + 18). Con > 30 d salen las temporadas de la
  tabla. ❓ Decidirlo en el PR de contrato (WS3).

### 4.3 Campos profundos ✅

- NEP (270,0, 66,5607): **29.402 frames** en SIA = dr1 439 + dr1_deep 20.848 + qr3 232 + qr3_deep ~7.890; MJD
  60790–61318; ~4.300–5.200 por detector. `spherex_dr1_deep` solo: 19,2 MB de respuesta en ~40 s;
  `spherex_qr3_deep`: 7,26 MB en 19,9 s.
- R Dra (a 8,6° del NEP) tiene 1954 frames en las colecciones `*_deep`.
- SEP: ❓ no medido.
- → Nunca en vivo sin filtros: `*_deep` opcional, `TIME`/`MAXREC`, bineado temporal y tope de frames. El fallback
  "recorrer semanas de S3 leyendo headers" no escala (~8.600 frames por semana en DR1, 🧮 promedio): DROP.

## 5. Servicios auxiliares y espejos

### 5.1 HiPS de SPHEREx ✅

- **Cubo all-sky DR1 de IRSA** (`ivo://IPAC/P/SPHEREx/DR1/cube`, listado en `https://irsa.ipac.caltech.edu/data/hips/list`):
  `https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube`. Tiles PNG de 512, orden 5 (~12,9″/px,
  `hips_pixel_scale` 0,0035786°), **102 slices** (`hips_cube_depth`; λ en `data_cube_crval3_arr`, 0,753–4,988 µm),
  `t_min/t_max` 60789,75–61174,49, release 2026-11-01, `ACAO: *`. Es una **co-suma estática** (contexto y selector
  de bandas), no una serie temporal. Créditos en `properties`: `obs_copyright = NASA/SPHEREx`,
  `hips_copyright = Caltech/IPAC`. ❓ Que Aladin Lite renderice este cubo: sin probar.
- En S3: `dr1/hips5_cube/hips_20261026/Norder5/Dir*/Npix*_cube.fits`: cubos FITS 512×512×102 de ~320 MB por tile
  (`RA---HPX`, `WAVE-TAB`). No sirven para un visor.
- HiPS `CDS/P/SPHEREx/QR2/D1..D6` y `/color`: registrados en el MocServer de CDS pero sus tiles en alasky dan
  **404** (además son QR2). No usar.

### 5.2 Incidente de CDS Estrasburgo ✅ (aviso "Last updated November 09, 2026 ... cybersecurity incident")

Verificado 2026-11-14 (14:03–14:21 UTC y 11:27 hora local):

| Caído | Funciona (usar esto) |
|---|---|
| `alasky.cds.unistra.fr` (HiPS por defecto de Aladin) → 404; `alaskybis` → timeout | HiPS de IRSA: `https://irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color`, `.../CDS/AllWISE/RGB-W4-W2-W1`, `.../CDS/DSS2/color`; ESA: `https://skies.esac.esa.int/2MASSColor`, `/AllWISEColor` (todos `ACAO: *`) |
| `aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js` → 404 | **`https://cdn.jsdelivr.net/npm/aladin-lite@3.8.2/dist/aladin.js`** (200, 2.390.678 B). npm `latest` es `3.9.2-beta`: no usar |
| `vizier.cds.unistra.fr`, `simbad.cds.unistra.fr` → 404; `vizier.unistra.fr` sin respuesta; `tapvizier`, `axel` → timeout | VizieR CfA `https://vizier.cfa.harvard.edu`, SIMBAD CfA `https://simbad.cfa.harvard.edu`, Sesame CfA (§5.3) |
| — | Siguen OK: MocServer y la portada de AladinLite |

- ⚠️ `aladin.js` 3.8.2 trae hardcodeados `vizier.unistra.fr` (en `catalogFromVizieR`) y alasky/alaskybis (surveys
  por defecto): pasar siempre URLs de espejos explícitas (`A.imageHiPS`, `A.catalogFromURL`). 3.8.2 incluye
  `catalogFromURL`, `imageHiPS`, `catalogFromSkyBot`, `cubeDepth` y `setSliceNumber`.
- ❓ Fecha de vuelta de CDS: desconocida. No depender de CDS en la demo.

### 5.3 Catálogos para overlays y resolución de nombres ✅

| Servicio | Uso | Estado |
|---|---|---|
| VizieR CfA `https://vizier.cfa.harvard.edu/viz-bin/votable?-source=I/355/gaiadr3&-c=...&-c.rs=...` | Gaia DR3 (época de referencia **2016.0**) desde el navegador | ✅ 1,5 s, `ACAO: *` |
| VizieR CfA `II/328` | AllWISE | ✅ |
| VizieR CfA `II/365` | CatWISE2020 | ⚠️ devuelve solo el esquema, 0 filas |
| IRSA TAP `catwise_2020`, `allwise_p3as_psd` | CatWISE/AllWISE desde el backend | ✅ 4,2 s, sin CORS. WISE 0855 en AllWISE: W1 16,231, W2 13,704 |
| ESA Gaia TAP `https://gea.esac.esa.int/tap-server/tap/sync` (`gaiadr3.gaia_source`) | Gaia desde el backend | ✅ 5,3 s, **sin CORS** |
| Sesame CfA `https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?<nombre>` | nombre → coordenadas **+ movimiento propio** | ✅ `ACAO: *`. La Sesame de CDS redirigía (302) al espejo `vizier.idia.ac.za`, también con `ACAO: *` |
| Gaia en MAST (recurso que cita el reto) | — | ❓ CORS sin probar |

### 5.4 Efemérides del Sistema Solar

| Servicio | URL | Estado |
|---|---|---|
| IMCCE SkyBoT | `https://ssp.imcce.fr/webservices/skybot/api/conesearch.php` | ✅ 200 con 2 asteroides en un cono de prueba; `ACAO: *` |
| JPL SB Identification | `https://ssd-api.jpl.nasa.gov/sb_ident.api` | ✅ 200 (soporta observador = nave, 📄) |
| JPL Horizons | `https://ssd.jpl.nasa.gov/api/horizons.api` | 📄 |
| AAVSO VSX | — | ❌ responde con un challenge de Cloudflare: no usar |

### 5.5 Herramientas de IRSA 📄

Spectrophotometry Tool, Mosaic Tool ("does not have an API"), Cutout Tool, Source Discovery Tool y MOST (Moving
Object Search Tool) son GUI. Tutoriales útiles: intro, cutouts (TAP + cutouts en paralelo), psf, source discovery,
mosaic y hipscube (todos en `https://caltech-ipac.github.io/irsa-tutorials/`).

## 6. Abierto ❓

Lo que **nadie verificó** todavía (si lo verificás, movelo arriba con ✅ y fecha):

- Lectura de punta a punta de un FITS remoto por Range con astropy (`Header.fromstring` + offsets) y la
  decodificación RICE de filas sueltas de FLAGS desde el heap.
- Que **WISE 0855 se vea en los coadds de D5/D6** (INFERIDO por magnitudes; medirlo antes de elegirlo como
  protagonista del video; plan B: Barnard).
- Si Barnard, R Dra o eps Ind A **saturan** (bits `OVERFLOW`/`NONLINEAR`) y cuánta área marcan GHOST/HALO.
- Que Aladin Lite 3.8.2 renderice el cubo HiPS SPHEREx de IRSA.
- Throughput desde el host de deploy (US-East) y qué plataforma admite astropy con disco persistente.
- El retraso de ~1 día de SIA respecto de TAP (sale de la doc de IRSA).
- Si IRSA respeta `BAND` en SIA2; límites de tasa y tamaño máximo de cutout.
- Significado exacto de `SATSTRKS`, `NBLMSRCS`, `SPS_FLAGS` y los `N_*` (Explanatory Supplement).
- Umbral de temporada (20 d contra 30 d, §4.2).
- Cobertura del SEP.
- CORS de Gaia en MAST; fecha de vuelta de CDS.
- Política de cita/redistribución para publicar PNGs derivados (poner créditos de datos siempre, solo en texto).

## Notas de otros WS

<!-- Append-only. Formato: - AAAA-MM-DD · WSx · hecho · estado (✅ cómo / 📄 fuente / ❓) -->
