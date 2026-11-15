# Datos SPHEREx: hechos verificados

> Ver también [RECON_SPHEREX.md](RECON_SPHEREX.md): relevamiento del 2026-11-14 con endpoints probados en vivo
> (SIA/TAP sin CORS → proxy; S3 con CORS y Range → píxeles directo al navegador), colecciones DR1 + QR3 y tiempos medidos.
> Es un insumo a re-verificar: lo que se confirme se pasa a este archivo con fecha y método.

Regla: cada hecho dice **cómo** y **cuándo** se verificó. Si descubrís algo nuevo o algo de acá está mal,
corregilo en un PR (`ws1: docs/DATA.md ...`). Etiquetas: ✅ verificado sobre datos reales · 📄 según documentación
(sin verificar por nosotros) · ❓ abierto.

## 1. Bucket público en AWS S3 ✅ (2026-11-14, listado HTTPS anónimo)

- Bucket `nasa-irsa-spherex` (región us-east-1), acceso **anónimo por HTTPS**, sin cuenta AWS:
  `https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/?list-type=2&delimiter=/&prefix=<prefijo>`
  (con AWS CLI: `aws s3 ls --no-sign-request s3://nasa-irsa-spherex/`).
- Releases (prefijos de primer nivel):

| Release | Semanas de survey (`level2/`) | Notas |
|---|---|---|
| `dr1/` | 110 semanas: `2025W17_4B` → `2026W20_1A` | **Data Release 1** (reprocesado, pipeline `l2b-v27-2026-198`). Incluye `hips5_cube/hips_20261026/` (HiPS espectral, cubos FITS por pixel HEALPix orden 5) |
| `qr3/` | 41 semanas: `2026W20_2A` → `2026W40_2A` | Quick Release 3 (lo más reciente) |
| `qr2/` | 129 semanas: `2025W17_4B` → `2026W29_2A` | Quick Release 2 (anterior) |

- Cada release trae además calibraciones (`epsf/`, `spectral_wcs/`, `spectral_channels/`, `sip/`, `dark/`, …).
- Layout de imágenes: `<release>/level2/<semana>/<version-pipeline>/<detector>/<archivo>.fits`
  ej. `dr1/level2/2025W19_2B/l2b-v27-2026-198/1/level2_2025W19_2B_0007_1D1_spx_l2b-v27-2026-198.fits`
- Nombre: `level2_<OBSID>D<detector>_spx_<version>.fits` (parseado en `errante.data.s3.parse_key`).
- Tamaño: **~61–66 MB por archivo** (DR1, ✅ `Content-Length` 2026-11-14). Para un campo chico **no descargues archivos completos**: usá cutouts
  (§3) o lecturas por rango HTTP (los headers se pueden leer con `Range:` sin bajar todo).
- **S3 no permite buscar por posición en el cielo** → para saber qué archivos cubren un punto, usá IRSA (§3).

## 2. Estructura de un archivo Level 2 ✅ (2026-11-14, headers de un archivo DR1 real vía HTTP Range)

| HDU | EXTNAME | Contenido |
|---|---|---|
| 0 | PRIMARY | sin datos (`VERSION`) |
| 1 | `IMAGE` | 2040×2040 float32, **MJy/sr**, luz zodiacal **NO** restada |
| 2 | `FLAGS` | 2040×2040 int32, máscara de bits (comprimido RICE; astropy lo abre como imagen) |
| 3 | `VARIANCE` | 2040×2040 float32, (MJy/sr)² |
| 4 | `ZODI` | 2040×2040 float32, modelo zodiacal (restalo vos: `IMAGE - ZODI`) |
| 5 | `EPSF` | PSF efectiva (tabla). En QR viejos se llamaba `PSF` |
| 6 | `WCS-WAVE` | tabla de búsqueda de longitud de onda por píxel; la grilla depende del detector (✅ §3.1) |

Header de `IMAGE` (claves útiles): `MJD-OBS` = `MJD-BEG` (✅ **inicio** de la exposición, no el medio), `MJD-AVG`
(✅ **mitad** de la exposición — **usar este**, con `DATE-AVG`; fallback `(MJD-OBS + MJD-END)/2`, después
`MJD-OBS + XPOSURE/2/86400`, ~0,8 s temprano porque `XPOSURE` < `MJD-END − MJD-OBS`), `MJD-END`, `DATE-OBS`,
`DETECTOR` (1–3 SWIR, 4–6 MWIR), `OBSID`, `BUNIT`, `PSF_FWHM` (ej. 7.53″ en D1), WCS `RA---TAN-SIP`
(usar astropy `WCS(header)`, incluye distorsión SIP), `OMEGA_MEDIAN` (ángulo sólido del píxel ≈ 37.9 arcsec²
→ píxel ≈ 6.15″), posición de la nave `X_SC/Y_SC/Z_SC` [km, geocéntrico] y velocidades `VX_SC…`,
`SPS_ELON/SPS_ELAT` (coordenadas eclípticas del apuntado), `PXSRCMSK` (% de píxeles con flag SOURCE),
`DATE` = **fecha de creación del archivo, NO de la observación** (no usar).

### Bits de FLAGS ✅ (leídos de las tarjetas `MSKNnnnn` del header DR1)

| bit | nombre | bit | nombre | bit | nombre |
|---|---|---|---|---|---|
| 0 | TRANSIENT | 11 | COLD | 22 | GHOST |
| 1 | OVERFLOW | 12 | FULLSAMPLE | 23 | GHOST_FPA |
| 2 | SUR_ERROR | 14 | PHANMISS | 24 | GHOST_EXT |
| 6 | NONFUNC | 15 | NONLINEAR | 25 | STREAK |
| 7 | DICHROIC | 17 | PERSIST | 26 | BLOOM |
| 9 | MISSING_DATA | 19 | OUTLIER | 27 | SNOWBALL |
| 10 | HOT | 20 | CROSSTALK | 28 | HALO |
| | | 21 | **SOURCE** | | |

⚠️ **"Cualquier bit ≠ 0 = malo" está MAL**: `SOURCE` (21) marca todas las estrellas (68 % de los píxeles en el
archivo inspeccionado). ⚠️ `OUTLIER`/`TRANSIENT` pueden dispararse **justo sobre un objeto en movimiento**
(no está donde el modelo del cielo estático lo espera): no los enmascares a ciegas para buscar movers.
Implementado en `errante.imaging.flags` (`DEFAULT_BAD`, `MAYBE_MOVER`, `bits_from_header`).
✅ 2026-11-14: el bit 27 `SNOWBALL` ("Pixel part of a snowball artifact") está en los headers FLAGS de dr1 y qr3
(`2025W36_1A_0095_1D1`, `2026W38_1A_0565_1D6`). ✅ WS2 lo agregó a `FLAG_BITS` y `DEFAULT_BAD` en #48.

## 3. Buscar y recortar con IRSA (✅ verificado en vivo el 2026-11-14: ver §3.0)

Fuentes: [SPHEREx Data Access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/),
[tutorial intro](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/),
[tutorial cutouts](https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/),
[parámetros de cutout IBE](https://irsa.ipac.caltech.edu/ibe/cutouts.html).

### 3.0 Verificado en vivo (2026-11-14) ✅

Consultas reales con `curl`/Python el 2026-11-14. Estos hechos **corrigen** lo que diga el resto de esta sección.

| Tema | Hecho verificado |
|---|---|
| CORS | IRSA (TAP, SIA, archivos IBE, cutouts, datalink) **no** envía `Access-Control-Allow-Origin` → el navegador no puede consultarlo: hace falta backend/proxy. El bucket S3 **sí** (ACAO `*`, `Range` permitido) y el HiPS SPHEREx de IRSA también. |
| Colecciones | `spherex_dr1` (945 725 frames), `spherex_dr1_deep` (233 681), `spherex_qr3` (362 124), `spherex_qr3_deep` (86 700). **QR2 ya no está indexado** (sigue en S3). Una colección inexistente devuelve un VOTable vacío **sin error**: no hardcodear nombres sin probarlos. |
| SIA2 | 1–4 s por consulta (2,6–9,3 s el 14/11 por la tarde). Pedir **VOTable**: el CSV viene **roto** (la columna `cloud_access` lleva JSON sin comillas). Trae `access_url`, `cloud_access.aws.key` (key S3), `s_region`, `t_min`/`t_max`, `em_min`/`em_max`. `MAXREC` y `TIME` funcionan. |
| TAP | 8–19 s. Tablas: `spherex.obscore`, `observation`, `plane`, `artifact`, `provenance_input`. La ADQL de `errante.data.irsa` (plane JOIN artifact + `CONTAINS`) **funciona**. JOIN obscore+plane falla (`st_covers`). |
| Cutouts IBE | Devuelven los 7 HDUs con la tabla **EPSF entera**: **~4 MB mínimo** aunque pidas 5′, 4–15 s cada uno. Sin solape → **HTTP 422** (no 500). 503 transitorios: reintentar. |
| Lectura por Range en S3 | `IMAGE` es float32 **sin comprimir**: se leen solo las filas del recorte (5′ ≈ 0,4 MB en ~1 s; header por Range + `astropy.io.fits.Header.fromstring`). `FLAGS` está comprimido RICE_1 con tiles de 1 fila (hay que leer el heap). Usar `requests` con `Range`; la receta con fsspec no está probada. |
| Rutas | La versión del pipeline (`l2b-v27-2026-NNN`) **cambia por semana y detector**: nunca construir rutas a mano, usar la key/URI que devuelve la búsqueda. `irsa_uri` → key S3 = quitar `ibe/data/spherex/` ✅. |
| WCS-WAVE | La grilla depende del **detector**: D1 9×9, D2 11×11, D3 9×14, D4 13×20, D5 11×11, D6 9×9 → leer `TDIM` del archivo, no suponerla cuadrada. |
| Contaminación | Headers con `HE_AIRGLOW_CONT`, `AURORA_CONT`, `SHUTTLE_GLOW_CONT`, `L2DQAFLG` (también en cutouts). |
| CDS Estrasburgo | Degradado desde el 2026-11-09 (incidente de seguridad): SIMBAD, VizieR, HiPS de alasky y la URL "latest" de Aladin dan 404. Usar espejos: Sesame/VizieR de **CfA** (`vizier.cfa.harvard.edu`, con CORS), HiPS de **IRSA** (`irsa.ipac.caltech.edu/data/hips/CDS/...`) o **ESA** (`skies.esac.esa.int`), Aladin Lite **3.8.2 desde jsdelivr**. |

**Cobertura de los 5 objetivos** (SIA2 + TAP; temporadas = bloques separados > 30 días):

| Objetivo (centro de la consulta TAP) | Frames: dr1 / qr3 / deep | 🧮 Visitas (> 6 h) | 🧮 Temporadas: MJD (n) | Fechas |
|---|---|---|---|---|
| Barnard (269.4463, 4.7665) | **358**: 239 / 119 / 0 | 48 | 60903–60949 (118) · 61110–61165 (121) · 61269–61306 (119) | 2025-08-15 → 2026-09-22 |
| Eps Ind B (331.0964, −56.8006) | **460**: 340 / 120 / 0 (⚠️ ver nota) | 74 | 60790–60836 (120) · 60947–60992 (147) · 61149–61164 (73) · 61305–61315 (120) | 2025-04-24 → 2026-10-02 |
| WISE 0855 (133.7600, −7.2422) | **258**: 258 / **0** / 0 | 37 | 60801–60802 (30) · 60980–61022 (128) · 61151–61174 (100) | 2025-05-05 → 2026-05-14 |
| RW Aur (76.9565, 30.4014) | **335**: 226 / 109 / 0 | 48 | 60919–60938 (112) · 61092–61111 (114) · 61285–61300 (109) | 2025-09-01 → 2026-09-16 |
| R Dra (248.1676, 66.7550) | **2493**: 413 / 126 / 1225 + 729 | 249 | 60790–60879 (240) · 60916–61310 casi continuo (2253) | 2025-04-24 → 2026-09-27 |

Centros propagados, movimiento esperado (1–2 px en total) y método para variables: [`SCIENCE.md`](SCIENCE.md) §0.
Campos profundos: el NEP tiene ~29 400 frames (dr1 + deep + qr3 + qr3_deep): nunca en vivo.

⚠️ Eps Ind B: SIA2 en vivo el 2026-11-14 a las 19:24 UTC, en este mismo centro y en el del campo, da **458**
(338 / 120; temporadas 118 / 146 / 74 / 120). La causa de la diferencia con 460 no está verificada (¿suma
SIA+TAP? ¿cambio del índice de IRSA?). Anotar servicio, centro y hora de cada conteo.

### 3.1 Verificado al implementar WS1 (2026-11-14) ✅

Medido en vivo por los agentes de WS1 (PRs #21 búsqueda, #22 píxeles, #23 longitud de onda) y por una revisión
independiente de cada rama. Corrige o amplía §3.0.

**Búsqueda (SIA2/TAP)**

| Tema | Hecho verificado |
|---|---|
| VOTable de SIA2 | Los `FIELD` tienen `ID="col_N"`: con astropy hay que usar `to_table(use_names_over_ids=True)` (si no, `access_url` no aparece como nombre). Antes del `RESOURCE type="results"` viene un `RESOURCE type="meta"` sin tabla. |
| Filas | `obs_id` **sin** sufijo de detector (`2026W33_2A_0594_4`); `energy_bandpassname` = `SPHEREx-D<n>`; todo `science`, `image`, nivel de calibración 2; exposiciones de ~115 s. `em_min`/`em_max` están en **metros**. `(t_min + t_max)/2` = `MJD-AVG` del header con error < 0,03 s. |
| Detectores por exposición | Un punto del cielo cae en un solo par dicroico por exposición (D1/D4, D2/D5 o D3/D6) → como mucho 2 filas por `obs_id` en una posición. |
| Colecciones deep | Usan el layout normal de S3: `spherex_dr1_deep` → `dr1/level2/...`, `spherex_qr3_deep` → `qr3/level2/...`. Solo la colección distingue wide de deep. |
| Versiones de pipeline | Barnard: **17** versiones distintas (`l2b-v27-2026-228` … `-268`), una con otra forma: `l2b_retry-v27-2026-230`. Otra razón para no armar rutas a mano. |
| Truncado | SIA marca `QUERY_STATUS=OVERFLOW` al llegar a `MAXREC` (probado con R Dra deep, `MAXREC=200`). TAP sync también respeta `MAXREC`, pero su CSV **no** trae estado: hay que comparar el conteo con `MAXREC`. |
| Esquema TAP | Existen `spherex.plane.time_bounds_upper`, `spherex.observation.collection` y `obsid` (vía `TAP_SCHEMA`). ❓ La consulta de fallback con JOIN a `observation` + `INTERSECTS(CIRCLE)` no pudo correrse en vivo (ver caída). |
| Caída de IRSA (14/11) | Desde ~13:40 ART: SIA respondía ~50 % de 502 rápidos (después ~1 de cada 12); TAP sync/async no respondió en ~2 h (502 o cuelgues de 120–180 s en toda consulta espacial; `TAP_SCHEMA` sí en ~1 s; un job async quedó `QUEUED` > 520 s). **IBE y S3 siguieron funcionando.** Por eso la búsqueda tiene caché con respaldo vencido y los píxeles salen de S3. |

**Píxeles (S3 por Range y cutouts IBE)**

| Tema | Hecho verificado |
|---|---|
| Caja de un cutout IBE | `n = round(size / escala)` píxeles por eje (puede no ser cuadrada: 97×98 a 10′), primer píxel `ceil(xc − n/2)` en base 0, recortada al detector. IBE recibe el centro como texto `%.7f`: para reproducir la caja exacta en un empate hay que redondear ra/dec a 7 decimales. Verificado en 5 cutouts reales + casos de borde. |
| WCS de un cutout IBE | Desplaza `CRPIXn`, `CRPIXnA` **y** `CRPIXnW` juntos; no escribe `LTV1/LTV2`. La WCS alternativa `A` es `LINEAR` = píxel 0-based del detector completo. FLAGS vuelve como `ImageHDU` int32 **sin comprimir**. WCS-WAVE se copia byte a byte. |
| Layout del archivo | El inicio de los datos de `IMAGE` **varía**: byte 28800 en archivos D1/D2, 25920 en D3–D6 → nunca fijar offsets. Ejemplo D3: FLAGS con heap `PCOUNT`=7 966 999 y `TFORM1 1PB(5166)`; EPSF 3 947 152 B (451 filas); WCS-WAVE es el último HDU (2880 + 2880 B). |
| Patch S3 = cutout IBE | Leyendo solo las filas del recorte (más los descriptores y el heap de FLAGS) y desplazando las `CRPIXn<key>`, el resultado es **bit a bit idéntico** al cutout IBE (IMAGE, FLAGS, VARIANCE, ZODI y headers). Verificado en Barnard (D1/D5/D6, 5′ y 10′), WISE 0855 (D1–D6), R Dra (incluido un recorte contra el borde) y un archivo qr2. |
| Costos por frame | Patch S3: 5′ ≈ 1,4 MB y 0,4–0,7 s con el directorio de HDUs cacheado (1,5 MB, 11 requests y ~3,5 s en frío); 10′ ≈ 2,8 MB y 0,5–2 s; en disco 120 KB (5′) / 235 KB (10′). Se leen filas completas de 2040 px (8160 B por fila y plano); S3 no acepta multi-range. Cutout IBE: 4,0–4,2 MB y 5–11 s. |
| Lote | 20 frames de Barnard a 10′: S3 ≈ 10 s contra IBE ≈ 29 s (6 hilos); 4,6 MB contra 82 MB en disco; segunda corrida 0,01 s. |
| Clientes HTTP | Un cuerpo cortado a mitad de la transferencia llega en `requests` como `ChunkedEncodingError`, que **no** es `ConnectionError`: reintentarlo explícitamente. En Windows, `os.replace` concurrente sobre el mismo destino da `PermissionError [WinError 5]`: candado por key o tolerarlo. |

**Longitud de onda (WCS-WAVE) y tiempo**

| Tema | Hecho verificado |
|---|---|
| Layout de WCS-WAVE | Una fila con columnas `X` (nX), `Y` (nY) y `VALUES` con `TDIM3=(2,nX,nY)` → numpy `(nY, nX, 2)` = (λ, Δλ). Los nodos son píxeles **1-based del detector completo**. Claves `W` del header: `CTYPEnW='WAVE-TAB'`, `CRPIXnW=CRVALnW=1` en archivos completos, `PS1_0W='WCS-WAVE'`, `PV1_3W=1` (λ), `PV2_3W=2` (Δλ). Grillas confirmadas: D1 9×9, D2 11×11, D3 9×14, D4 13×20, D5 11×11, D6 9×9. |
| SIP | astropy pega la distorsión SIP celeste a **todas** las WCS alternativas (`W` y `A`). Si no se quita (`sip=None`), λ se corre 8 nm en Barnard y hasta 14,7 nm en el D3, y la `A` también queda mal. |
| Rango de las tablas | Las tablas pasan 10–25 nm los bordes de banda nominales: D1 0,7349–1,1263 · D2 1,0859–1,6677 · D3 1,6163–2,4391 · D4 2,3980–3,8629 · D5 3,7984–4,4426 · D6 4,4018–5,0246 µm. Gradiente a lo largo de y: 0,19 / 0,28 / 0,39 / 0,70 / 0,31 / 0,30 nm por píxel (D1…D6). |
| λ en Barnard (2026.2) | D1 0,750 · D2 1,379 · D3 2,308 · D4 2,782 · D5 4,151 · D6 4,894 µm (un frame por detector); 18 frames en total coinciden con el método del tutorial (< 2e-15 µm) y el archivo completo da el mismo λ que su cutout. |
| Tiempo | `MJD-AVG − MJD-OBS` = 57,56 s en todos los headers vistos; `MJD-AVG` = `(MJD-OBS + MJD-END)/2`; `XPOSURE` = 113,58 s < `MJD-END − MJD-OBS` (115,1 s) < `TELAPSE` (118,19 s). `errante` publica `Frame.mjd` = `MJD-AVG` y `Frame.date_obs` = `DATE-AVG` (mismo instante). |

**Integración (2026-11-14):** `errante build barnards-star` con los tres PRs de WS1 + el #16 de WS2 dio 40 frames
reales (6 detectores, 3 temporadas: 14/13/13) en **22 s**, todos desde S3 (0 fallbacks a IBE, 18 MB de caché), y
`errante validate` OK.

- **TAP** (ADQL, sync, CSV): `https://irsa.ipac.caltech.edu/TAP/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=...`
  Tablas documentadas: `spherex.plane` (`planeid`, `time_bounds_lower` [MJD], `poly`, `energy_bandpassname` =
  `'SPHEREx-D1'…'SPHEREx-D6'`) y `spherex.artifact` (`uri`, `planeid`). Consulta tipo en
  `errante.data.irsa.ADQL_FRAMES_AT_POSITION` (`CONTAINS(POINT('ICRS', ra, dec), p.poly)`).
  `uri` es relativo (`ibe/data/spherex/<release>/level2/...`): anteponer `https://irsa.ipac.caltech.edu/`.
- **SIA2**: `https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr3&POS=circle+<ra>+<dec>+<radio>`;
  colecciones vigentes ✅ `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep` (QR2 ya no
  indexado). Pedir `RESPONSEFORMAT=VOTABLE` (el CSV viene roto, §3.0).
- **Cutout server-side**: `<url-del-fits>?center=<ra>,<dec>&size=<s>` (grados por defecto; `size=5arcmin` válido).
  Devuelve el mismo MEF recortado (no gzip), en **orientación nativa** (no norte-arriba → reproyectar), puede ser
  **no cuadrado** con NaN en bordes; sin superposición → **HTTP 422** ✅; pesa **~4 MB** como mínimo (EPSF, §3.0).
- **Python**: `astroquery.ipac.irsa.Irsa.query_tap(...)`, `pyvo`. GUI: https://irsa.ipac.caltech.edu/applications/spherex
- Rendimiento reportado por otros: TAP 3–20 s por consulta; cutout 1–15 s; IRSA limita la concurrencia
  (usar ≤ 6–8 hilos, reintentos con backoff, no paralelizar consultas TAP).
- Variación de longitud de onda: cada exposición mide **una longitud de onda distinta en cada punto del
  detector** (filtro lineal variable). Calcularla en la posición del objeto con `WCS-WAVE`
  (`WCS(header, fobj=hdul, key="W")` según el tutorial) — ✅ verificado en archivos completos, cutouts IBE y
  patches S3; detalle en §3.1.

**Actualización documental 2026-11-14:** se leyeron los [notebooks SPHEREx](https://caltech-ipac.github.io/irsa-tutorials/spherex/)
y la [introducción](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/). Enumeran `spherex_dr1`,
`spherex_dr1_deep`, `spherex_qr3` y `spherex_qr3_deep`; recomiendan DR1/QR3 sobre QR2. Esta comprobación
es **📄 documentación**, no una consulta SIA ejecutada ni una descarga validada por nosotros.
La guía muestra WCS espectral `key="W"` con `sip = None`: ✅ comprobado sobre nuestros cutouts (§3.1).

### 3.2 Verificado en la validación y en los tracks de la visión (2026-11-14) ✅

Medido por los agentes de WS1 sobre FITS reales, con una revisión independiente que volvió a medir con código
propio. Evidencia en [`validation/`](validation/) (#36) y en las PRs #42 (cubo) y #43 (snapshots).

| Tema | Hallazgo |
|---|---|
| Colecciones deep | R Dra: 1954 de sus 2493 frames son `*_deep`, y aportan casi todo el muestreo temporal. La búsqueda por defecto (`spherex_dr1,spherex_qr3`) los excluye: ofrecer deep como opción para variables del NEP. |
| Huella frente a array | 5 frames de la búsqueda de R Dra contienen la posición en su huella, pero el píxel cae 0–6 px fuera del array. El pipeline lo maneja sin fallar; solo infla los conteos de cobertura. |
| WCS defectuosa en el archivo | `2026W38_1A_0162_3D6`: 4 estrellas Gaia corridas −1,21 a −1,36 px en x (~7,9″), aunque el header dice `FINAST=0` ("good") y `ASTRONETSOLVED=True`. Las exposiciones vecinas están a < 0,1 px. El patch S3 es idéntico al cutout IBE: el error viene del archivo. Hace falta un control de registro por frame. |
| WCS corrida en Barnard | `2026W34_1A_0431_2D6`: corrida (+0,66, −1,50)″ = 0,27 px (análisis A) y (+0,68, −1,60)″ = 0,283 px (revisión R) contra estrellas Gaia DR3 de campo, con `FINAST=0` y `MATCH_NSTARS` 1255, contra 2292 y 2357 en sus vecinas D6 `_1` y `_3`, que están a 0,011 y 0,039 px. El D3 de la misma exposición está a 0,038 px. Fuente: [`validation/barnards-star.md`](validation/barnards-star.md) (#46). Un `MATCH_NSTARS` mucho menor que el de las vecinas podría servir de alarma (INFERIDO, sin probar). |
| Registro WCS típico | Contra Gaia DR3, offset por frame con mediana ≤ 0,04 px y máximo ~0,2 px (ε Ind B, WISE 0855, RW Aur, R Dra). La estabilidad entre temporadas es ≤ 0,15″. Barnard: estable a 0,014–0,017 px salvo el frame de 0,28 px (#46). |
| `PSF_FWHM` del header | Es más ancho que el núcleo: la mejor gaussiana mide 0,70–0,86 × header, según el método. Los patches S3 de WS1 no traen el HDU `EPSF`, porque `s3range` lee solo PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI y WCS-WAVE. |
| Saturación | R Dra: `OVERFLOW` en el núcleo en 2488 de 2488 frames. RW Aur: en 304 de 335 (todo D2–D6). `NONLINEAR` no aparece nunca en ninguno de los dos. Los píxeles `OVERFLOW` son **finitos**, no NaN. |
| Saturación de Barnard | ✅ Satura (#46, [`validation/barnards-star.md`](validation/barnards-star.md), mismos conteos en el análisis y en la revisión independiente). A ≤ 3 px de la posición predicha: `OVERFLOW` en el núcleo en **357 de 358** exposiciones (la única sin `OVERFLOW` es `2025W34_2B_0030_1D6`, 4,58 µm); `NONLINEAR` **nunca**; NaN en el núcleo en 240 (siempre junto con `OVERFLOW`; en D5/D6 solo 4 de 119), pero píxeles `OVERFLOW` **finitos** en 339. D1 a λ < 0,80 µm satura menos (media 2,3 px `OVERFLOW` contra 5,0 a ≥ 1,00 µm). En el cubo DR1 el núcleo queda vacío en 90 de 100 planos (§3.3). |
| WISE 0855 | Se ve solo en D5/D6: SNR ~3,5 por exposición y 21–25 sumando por detector. En D1–D4 no se detecta. |
| Cubo HiPS DR1 en S3 | Los tiles FITS (512×512×102) se leen por Range. El `obs_description` de IRSA lo presenta como producto **de visualización**: sirve para el panel, no para fotometría fina. `cube_spectrum` está en #42. |
| Snapshots de búsqueda | Los JSON de `data/index/search/` coinciden exactamente con SIA en vivo para los cinco blancos (centro y círculo descentrado), según #43. |
| TAP | No respondió en toda la sesión del 14/11: el fallback TAP sigue sin probarse en vivo (§6). |

### 3.3 Para el deploy (WS4) ✅ (2026-11-14, código en `849a2d0`, simulación y mediciones en vivo)

Verificado por WS1 (Claude) la noche del 14/11 (≈ 02 UTC del 15/11) desde una laptop en Buenos Aires, leyendo
`backend/Dockerfile`, `backend/errante_api/{settings,live_service}.py`, `backend/errante_api/jobs/supervisor.py` y
`pipeline/errante/data/*.py`. De código de WS1 solo cambia el texto de una nota de `cube_spectrum` (e); lo que toca
`backend/` queda como `TODO(WS4)`. b), c), d) y e) se revisaron el 15/11 ≈ 02:45 UTC con reproducciones (abajo).

**a) Los snapshots de búsqueda no entran en la imagen.**

- `irsa.DEFAULT_SNAPSHOT_DIR = settings.REPO_ROOT / "data" / "index" / "search"`, y `REPO_ROOT` es la carpeta dos
  niveles arriba de `errante/settings.py`. En el contenedor (`pip install -e 'pipeline[science]'` en `/app`) eso
  da `/app/data/index/search`, pero `backend/Dockerfile` solo hace `COPY data/demo`. Si IRSA se cae, la búsqueda
  **no** cae a los snapshots de #43: el único rastro es un `WARNING` por proceso (`Search snapshot directory ...
  does not exist: the IRSA-outage fallback is off`) y la API responde el mismo 502/504 que sin snapshots.
- Simulación: copia de `pipeline/errante` + `pyproject.toml` en una carpeta sin `data/`, caché vacía, SIA y TAP
  apuntando a un puerto cerrado (`127.0.0.1:9`, `ConnectionError`), `ERRANTE_SEARCH_ATTEMPTS=1` y
  `irsa.search_frames_report(269.44623, 4.76870)` (Barnard):

  | Caso | Resultado |
  |---|---|
  | Sin `data/index` ni variable (= imagen actual) | `SearchError` con `is_outage=True` a los 4,1 s |
  | `ERRANTE_SEARCH_SNAPSHOTS=<repo>/data/index/search` | responde `service='snapshot'`, `stale=True`, 358 frames y el warning con la fecha del snapshot (4,1 s) |
  | `data/index` copiado junto a `pipeline/` (= `COPY data/index /app/data/index`) | igual que el anterior |

- `backend/Dockerfile.dockerignore` no excluye `data/index`, así que el `COPY` funciona (5 JSON, 492 KB).
- `ERRANTE_SEARCH_SNAPSHOTS` se lee **al importar** `errante.data.irsa` (`irsa.SNAPSHOT_DIR`): definila en el entorno
  del proceso. `0`/`off` apaga el respaldo sin warning.
- **TODO(WS4):** agregar `COPY data/index /app/data/index` junto a `COPY data/demo` (o copiarlos a otra ruta y definir
  `ERRANTE_SEARCH_SNAPSHOTS`). WS1 no edita el Dockerfile.

**b) Presupuestos de tiempo frente a `ERRANTE_API_TIMEOUT_S` (30 s).**

`live_service.call` espera 30 s con `asyncio.wait_for` y contesta 504, pero el trabajo **sigue corriendo** en su
hilo y retiene uno de los `ERRANTE_API_MAX_CONCURRENT` (2) cupos hasta terminar. Con un solo cupo retenido la
siguiente consulta usa el otro y contesta normal; **si los 2 cupos quedan retenidos**, las demás reciben 503
("Archive capacity is busy") hasta que alguno termine. Reproducido con `LiveService(Settings(live_timeout_s=0,5,
live_max_concurrent=2))` y una función que duerme 3 s: lenta → 504, rápida → 200, lenta → 504, rápida → **503**.
Cada presupuesto de WS1 tiene que quedar por debajo de 30 s para contestar a tiempo **y** para liberar el cupo. Todas
estas variables se leen al importar (cambiarlas = reiniciar el proceso).

| Variable | Default (código) | Qué acota | Recomendado en el contenedor |
|---|---|---|---|
| `ERRANTE_SEARCH_DEADLINE_S` | 60 (`settings.py`) | Búsqueda completa: SIA (≤ la mitad) + TAP | **25**. Hoy una búsqueda sin respaldo puede retener un cupo hasta 60 s: 30 s más allá del 504. SIA tardó 3,7–4,0 s (abajo). |
| `ERRANTE_SEARCH_FALLBACK_DEADLINE_S` | 20 | Tiempo para IRSA cuando una caché vencida o un snapshot pueden contestar | 20 (dejar). Solo sirve si los snapshots están en la imagen (a). |
| `ERRANTE_SIA_TIMEOUT_S` / `ERRANTE_TAP_TIMEOUT_S` / `ERRANTE_SEARCH_ATTEMPTS` | 30 / 60 / 4 | Cada intento | Dejar: el deadline los recorta. |
| `ERRANTE_CUBE_DEADLINE_S` | 20 **por fuente** (`cube.py`) | `cube_spectrum`: S3 y, si falla, la copia de IRSA → peor caso 40 s | **12** (2 × 12 = 24 s). Medido: 0,7–2,6 s. |
| `ERRANTE_CUBE_TIMEOUT_S` | 10 (conexión: mín(5, valor)) | Cada Range del cubo (4 B–64 KB) | Dejar. |
| `ERRANTE_CUBE_PARALLEL` | 32 | Requests en vuelo por fuente, en todo el proceso | Dejar. |
| `point_series(deadline_s=...)` | sin límite. **No hay variable**: es un parámetro (CLI `errante point --deadline`) | Lecturas de la serie. La búsqueda interna **no** queda acotada por `deadline_s` (solo por `ERRANTE_SEARCH_*`), pero su tiempo se descuenta de él | Si WS4 la expone en vivo: pasar `deadline_s` ≤ 25 y usar `ERRANTE_SEARCH_DEADLINE_S` ≤ 15. Los frames que no llegan quedan como `TimeoutError` y esa serie no se cachea. |
| `ERRANTE_POINT_MAX_PARALLEL` | 48 (tope 64) | Requests S3 en vuelo por serie | Dejar (medido en laptop). ❓ CPU del host de deploy. |
| `ERRANTE_HTTP_TIMEOUT_S` | 120 | Timeout (conexión y lectura) de cada request de `s3range` (que usa `point`) y de `cache`; también de los requests que siguen en segundo plano tras el deadline de una serie | Considerar 30 en la API (❓ no medido; los jobs de build bajan archivos más grandes). |

Mediciones en vivo (2026-11-15 ~02:14 UTC, laptop en Buenos Aires → S3 us-east-1; el host de deploy, más cerca de
S3, debería andar más rápido, ❓ sin medir):

- `search_frames_report` puntual sin caché ni snapshot: Barnard 3,7 s (SIA, 358 frames), R Dra 4,0 s (SIA, 539).
- `cube_spectrum` con los parámetros por defecto (sin NHITS ni FLAGS), ε Ind B, caché vacía: tile en frío **2,6 s**
  (106 requests, 38 KB); apertura 2 en el mismo proceso 0,7 s (102 requests, 838 KB); proceso nuevo con los headers
  en disco 2,4 s (abrir conexiones) y después 0,7–0,8 s; resultado cacheado 0,00 s. Con NHITS + FLAGS (302
  requests, las fixtures de d): 1,8–4,0 s.
- `point_series` (medido en #45, no repetido): Barnard 358 frames, 3,4 s de SIA + 15,1 s de lecturas en frío y 7,9 s
  con los layouts cacheados; R Dra 539 frames, 4,3 + 23,3 s → en frío **no entra** en 25 s (resultado parcial).

**c) Otras suposiciones de WS1 sobre rutas y disco (leyendo `pipeline/errante/data/*.py`).**

- Todo lo que WS1 escribe va bajo `settings.CACHE_DIR` (`ERRANTE_CACHE_DIR=/app/data/cache` en el Dockerfile, creado
  y con dueño 10001); el backend agrega `api/` y `jobs/`. Hay dos tipos de escritura:
  - **Obligatorias (el archivo en disco es el resultado):** los píxeles de cada frame de un build.
    `s3range.fetch_patch` escribe `s3patch/<ra>_<dec>_<tamaño>am/<release>/<frame>.fits` y, si S3 falla, el respaldo
    IBE (`cutouts.fetch_cutout` → `cache.cached_download`) escribe `<hh>/<hash>.fits`. Las dos propagan el `OSError`:
    con la caché sin permiso de escritura o sin espacio, cada frame termina como `DOWNLOAD_FAILED` en `build.py` y el
    build se queda sin imágenes. Son además lo que más ocupa: 358 patches S3 de 12′ de Barnard = 134 MB
    ([`validation/barnards-star.md`](validation/barnards-star.md)).
  - **Best-effort (solo caché):** `queries/` (búsquedas), `cube/dir` (~40 KB por tile) y `cube/spectra` (~7 KB por
    espectro), `s3range/dir`, `point/layout`, `point/wave` y `point/series`. Un `OSError` no rompe la consulta, solo
    se pierde la caché.
  - Reproducido (15/11 ≈ 02:45 UTC) con `ERRANTE_CACHE_DIR` debajo de un archivo común: `cache.cached_download` →
    `FileExistsError [WinError 183]`; la escritura de un patch (`s3range._atomic_write` sin `best_effort`) → el mismo
    error; la del directorio de `s3range` (`best_effort=True`) → `False` sin excepción. En vivo, la búsqueda de
    Barnard contestó igual (SIA, 358 frames; `irsa._cache_write` solo registra `Could not write search cache ...`),
    pero `cutouts.fetch_cutouts` de 2 frames devolvió `[None, None]` (`S3: FileExistsError ...; IBE: FileExistsError
    ...`).
- **Cada job de build usa su propia caché.** `backend/errante_api/jobs/supervisor.py` (`_launch_child`) lanza el
  proceso hijo con `ERRANTE_CACHE_DIR=<jobs_dir>/staging/<intento>/cache` (`jobs_dir` = `ERRANTE_JOBS_DIR`, por
  defecto `CACHE_DIR/jobs`). Un job no reutiliza los patches de la API ni de otros jobs; `_cleanup` borra esa
  `cache/` cuando el intento terminó y el job ya no está `running` ni `publishing` (y todo el staging a las 24 h). El
  disco tiene que alcanzar para los patches de los jobs simultáneos: no montar `CACHE_DIR` ni `jobs_dir` como solo
  lectura ni con un tope chico.
- **No hay desalojo ni tope de tamaño** en la caché de la API: crece con cada punto o tile distinto. En un disco
  efímero se borra con cada redeploy (correcto, solo más lento la primera vez).
- La única ruta del repo que WS1 usa en ejecución es `data/index/search` (a). En producción solo se lee;
  `errante snapshot-search` la escribe, pero es una herramienta de desarrollo.
- `fields.toml` viaja dentro del paquete (`errante/config/`, leído por `build.py`), así que `COPY pipeline/errante`
  alcanza.
- Salida a red: HTTPS a `nasa-irsa-spherex.s3.us-east-1.amazonaws.com` (píxeles y cubo) y a `irsa.ipac.caltech.edu`
  (SIA/TAP y respaldo del cubo). Sin claves. `s3range` respeta `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` si el host usa
  un almacén de certificados propio.

**d) Espectros reales como fixtures para WS4/WS5.** `pipeline/tests/fixtures/ws1/cube_spectra/<id>_ap{0,2}.json`:
`CubeSpectrum.to_dict()` en JSON estricto (NaN → `null`), 7,6–8,7 KB cada una, cargadas por
`pipeline/tests/test_data_cube_spectra_fixtures.py`. Llamadas en vivo desde S3 con `with_nhits` y `with_flags`: el
2026-11-15 ~02:10 UTC en el centro de `fields.toml` de los cinco blancos y en un cielo vacío, y ~02:40 UTC en un
hueco de cobertura cerca del centro galáctico. El cielo vacío es (200,0, +40,1): sin fuentes Gaia DR3 a < 45″ y la
AllWISE más cercana a 19″ (W1 = 17,2), según VizieR CfA. El hueco es (268,09113, −28,71602), a ~1,5° de Sgr A\*.

| Punto | Tile, píxel (x, y) | Planos válidos (ap 0 / ap 2) | Núcleo vacío (NaN, NHITS = 0) | Válidos con `OVERFLOW` |
|---|---|---|---|---|
| Barnard | 7945 (98, 103) | **10**: solo D5/D6, ≥ 4,29 µm (igual) | 90 | 2 |
| ε Ind B | 11391 (98, 408) | 100 (igual) | 0 | 0 |
| WISE 0855 | 10226 (212, 238) | 100 (igual) | 0 | 0 |
| RW Aur | 277 (400, 252) | 85 (igual) | 15 (D4, 2,51–3,77 µm) | 50 |
| R Dra | 2928 (20, 425) | **0** | 100 | 0 |
| Cielo vacío | 2708 (178, 220) | 100 (igual) | 0 | 0 |
| Hueco (centro galáctico) | 7207 (75, 107) | 68 / 66 (planos 7 y 29: < 50 % de la apertura con datos) | **32** (D1–D3, 0,91–2,35 µm) | 5 |

- Los planos 50 y 51 (dicroicos) están siempre en blanco. La apertura de 2 px no rescata un núcleo vacío.
- **Núcleo vacío no es lo mismo que saturado.** En las tres estrellas saturadas, la región NaN que contiene el núcleo
  mide 1–28 px (Barnard 2 y 6, RW Aur 1 y 3, R Dra 3 y 28, en dos planos perdidos de cada una, leídos completos). En el
  hueco mide 33 014 px (plano 8) y 11 312 px (plano 34), con caja de hasta ~46′ × 67′ que llega al borde del tile: es
  falta de cobertura del coadd, no una estrella.
- En el FLAGS del cubo, los planos perdidos de las **estrellas saturadas** llevan `SUR_ERROR` + `BLOOM` (los 90, 15 y
  100) y **nunca** `OVERFLOW`, aunque en las exposiciones L2 esos mismos núcleos tienen `OVERFLOW` (§3.2). Los del
  **hueco** llevan `CROSSTALK` (32 de 32) y `PERSIST` (28), **nunca** `SUR_ERROR`, y `BLOOM` en uno (plano 30). En el
  cubo, `OVERFLOW` marca en cambio planos **válidos** (finitos, probablemente subestimados; también 5 en el hueco).
  `SOURCE` está prendido en los 100 planos del cielo vacío: el FLAGS del cubo acumula los bits de las entradas, y
  `SOURCE` no sirve para decir "acá hay una estrella".

**e) Propuesta para un futuro PR `contract:` (espectro de un punto).** No se tocó `models.py`. Un modelo nuevo y
opcional (p. ej. `PointSpectrum`), con campos que salen directo de `CubeSpectrum.to_dict()`:

| Campo | Tipo | Origen / regla |
|---|---|---|
| `ra`, `dec` | float, grados ICRS | posición pedida |
| `pixel_center` | `{ra, dec}` | centro del píxel del cubo usado (píxel de 12,88″: hasta ~9″ de la posición pedida) |
| `wavelength_um`, `bandwidth_um` | 102 floats | tabla WCS-WAVE del cubo, fija: 0,753–4,988 µm |
| `flux` | 102 × `float \| null` | brillo superficial del píxel o media de la apertura en **MJy/sr**; `null` donde `valid` es falso |
| `valid` | 102 bool | núcleo con datos, plano no en blanco y, con apertura, ≥ 50 % de sus píxeles con datos |
| `unit` | `"MJy/sr"` | `BUNIT` del cubo |
| `aperture_px`, `n_pixels` | int | radio pedido (0–10) y píxeles de la apertura (1, o 13 con radio 2) |
| `n_used` (opcional) | 102 int | píxeles con datos por plano. Flujo integrado [Jy] = `flux * n_used * pixel_sr * 1e6`, sin restar fondo |
| `pixel_sr`, `pixel_scale_arcsec` | float | 3,901e-9 sr y 12,8831″ |
| `blank_planes` | int[] | `[50, 51]` |
| `mjd_range` | `[float, float]` | MJD de las entradas del coadd: **no hay eje temporal** |
| `source`, `release` | str | `s3` o `irsa`; `dr1/hips5_cube/hips_20261026` |
| `notes` | str[] | la primera es siempre la nota de IRSA "for visualization" (`cube.NOTE_VISUALIZATION`): la UI tiene que mostrarla |
| `n_core_missing` | int | planos fuera de `blank_planes` con `core_valid` falso (núcleo NaN, NHITS = 0). Sale de la llamada por defecto, sin FLAGS. **Significa "núcleo saturado o sin cobertura"**, no "saturado": Barnard 90, RW Aur 15, R Dra 100 y también el hueco del centro galáctico, 32 (d). `cube_spectrum` agrega una nota cuando es > 0 y nombra las dos causas |
| `saturated` | `bool \| null` | **regla (INFERIDA de 3 estrellas saturadas + 1 hueco + 3 puntos limpios):** algún plano de los que cuenta `n_core_missing` con `SUR_ERROR` **y** `BLOOM` en el FLAGS del cubo. Necesita `with_flags`; sin FLAGS es `null` (desconocido), nunca `false`. Medido: verdadero en Barnard, RW Aur y R Dra (todos sus planos perdidos tienen los dos bits); falso en ε Ind B, WISE 0855, el cielo vacío **y el hueco** (sin `SUR_ERROR`). "`SUR_ERROR` **o** `BLOOM`" no sirve: el plano 30 del hueco tiene `BLOOM` |
| `n_core_saturated` (opcional) | int | solo con `with_flags`: cuántos planos cumplen la regla de `saturated`; `n_core_missing − n_core_saturated` = planos perdidos por cobertura |
| `overflow_planes` (opcional) | int[] | solo con `with_flags`: planos válidos con `OVERFLOW` en el FLAGS del cubo (RW Aur 50, Barnard 2, hueco 5). No indica saturación por sí solo |

`tile`, `pixel`, `nhits`, `flags` y `timings` quedan fuera del contrato (sirven para depurar). Las reglas de
`n_core_missing` y `saturated` están implementadas en el test (`saturation_hint`), con el hueco como regresión, para
que el PR de contrato las copie. Una regla sin FLAGS (`saturated` = algún núcleo vacío) marcaría el hueco como
estrella saturada: no usarla.

## 4. Instrumento y survey 📄

- 6 detectores H2RG 2040×2040 activos, píxel **6.15″**, campo ~3.5°×3.5° por detector; pares simultáneos
  (D1,D4), (D2,D5), (D3,D6) vía dicroico.
- Bandas aproximadas: D1 0.75–1.11 µm, D2 1.11–1.64, D3 1.64–2.42 (R≈41), D4 2.42–3.82 (R≈35),
  D5 3.82–4.42 (R≈110), D6 4.42–5.00 (R≈130) → 102 canales espectrales en total.
- Cielo completo cada ~6 meses (4 mapas en 2 años); **campos profundos** cerca de los polos eclípticos
  (NEP ≈ RA 270°, Dec +66.56°; SEP ≈ RA 90°, Dec −66.56°) con muchísimas más épocas.
- Survey científico desde ~mayo 2025 (primera semana en S3: `2025W17`).

## 5. Servicios auxiliares 📄

| Servicio | URL | Uso |
|---|---|---|
| JPL SBIdent | https://ssd-api.jpl.nasa.gov/sb_ident.api | objetos conocidos en un campo/época (soporta observador = nave) |
| JPL Horizons | https://ssd.jpl.nasa.gov/api/horizons.api | efemérides de un objeto |
| IMCCE SkyBoT | https://ssp.imcce.fr/webservices/skybot/api/conesearch.php | cone search por época (JSON, CORS) |
| SIMBAD | https://simbad.cds.unistra.fr/ | estrellas/enanas marrones con movimiento propio (⚠ CDS degradado: usar Sesame de CfA) |
| Sesame / VizieR (CfA) ✅ | https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?NOMBRE | resolver nombres con pm; Gaia DR3 `I/355/gaiadr3` (con CORS). ⚠️ `GJ 699` responde solo con VizieR local: 17:57:51.47 +04:33:03.2, a 514,8″ (**8,6′**) de la posición J2000 de Barnard (una posición de época antigua). Resolver con «Barnard's Star» o con el `source_id` Gaia DR3 4472832130942575872 ([`validation/barnards-star.md`](validation/barnards-star.md), #46) |

## 6. Abierto ❓

- ✅ Resuelto: colecciones y tablas reales, `irsa_uri` ↔ key S3 (§3.0).
- Tamaño máximo de cutout y límites de tasa (S3: 16 lecturas en paralelo anduvieron bien; IRSA: ≤ 6–8).
- ❓ Fallback TAP de la búsqueda (JOIN `observation` + `INTERSECTS`) sin probar en vivo: TAP estuvo caído el 14/11.
- Política de cita/redistribución para publicar PNGs derivados (incluir créditos siempre).
- HiPS: ✅ IRSA publica el cubo SPHEREx DR1 (102 canales, orden 5, con CORS); los HiPS QR2 de CDS dan 404 por el
  incidente. ✅ Aladin Lite 3.8.2 lo renderiza (gotchas en [`VISION.md`](VISION.md)).
- ✅ WISE 0855 visible en D5/D6 y ✅ saturación de R Dra, RW Aur y **Barnard** (§3.2; Barnard cerrado con #46).
  ❓ Throughput a S3 y tiempos de `cube_spectrum`/`point_series` desde el host de deploy (§3.3 solo midió desde
  Buenos Aires).
- ❓ Snapshots de búsqueda en la imagen de deploy: hoy no entran (§3.3 a, `TODO(WS4)`).

## 7. Comprobación de los enlaces del enunciado (2026-11-14)

Se comprobó acceso a las ocho URLs de recursos aportadas en `ENUNCIADO.md`. Se distinguen lectura de
documentación, respuesta HTTP y funcionamiento de un servicio científico. No se desactivó TLS para reintentar.

| Recurso / URL | Método y resultado | Qué queda pendiente |
|---|---|---|
| [IRSA SPHEREx](https://irsa.ipac.caltech.edu/Missions/spherex.html) | Página leída con navegador de investigación | Consultas y descargas de nuestro pipeline |
| [Notebooks SPHEREx](https://caltech-ipac.github.io/irsa-tutorials/spherex/) | Índice, introducción y cutouts accesibles y leídos | Ejecutarlos con datos seleccionados para los cinco blancos |
| [WiseView](http://byw.tools/wiseview) | Navegador: timeout; HTTP directo desde esta máquina: **200**, HTML leído con controles de RA/Dec, FOV y blink | Ejecución interactiva/servidor de imágenes no probados |
| [Gaia en MAST](https://archive.stsci.edu/missions-and-data/gaia) | Página leída con navegador de investigación | Consulta de catálogo y overlay DR3 |
| [CSA NEOSSat](https://www.asc-csa.gc.ca/eng/satellites/neossat/) | Página de misión leída con navegador de investigación | Comparación opcional y condiciones aplicables |
| [CADC](https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/) | Página leída con navegador de investigación | Acceso programático a datasets y condiciones |
| [Tutorial NEOSSat](https://github.com/asc-csa/NEOSSAT_Tutorial) | Repositorio y descripción accesibles con navegador de investigación | Ejecutar notebooks y revisar licencia antes de reutilizar |
| [Dataset NEOSSat](https://data.asc-csa.gc.ca/dataset/neossat) | Navegador: timeout; Python: certificado no validable; `Invoke-WebRequest` con confianza TLS de Windows: **200**, página recibida | Descarga y procesamiento del dataset no probados |

**Enlace adicional ya presente en el repo:** la [página de Space Apps](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=details)
no abrió con el navegador de investigación. Python y el cliente HTTP de Windows fallaron al establecer TLS.
Esto describe el acceso desde este entorno, no demuestra que la página esté caída para todo el mundo.
El texto de CHALLENGE.md se tomó del archivo del usuario y no se cotejó con esa página.

**Herramientas complementarias:** [Astropy](https://www.astropy.org/) y [Aladin Lite](https://aladin.cds.unistra.fr/AladinLite/)
accesibles con navegador de investigación; su integración y pruebas específicas tienen tareas C08.
Astropy ya se usa en FITS/WCS; Aladin sigue siendo un enlace externo en el frontend.

Antes de la publicación, aplicar las condiciones de reconocimiento de IRSA y de cada fuente realmente usada.
La página IRSA enlaza herramientas de fotometría, mosaicos y cutouts: evaluar reutilización antes de duplicarlas,
sin asumir que sus endpoints o condiciones ya están integrados.
