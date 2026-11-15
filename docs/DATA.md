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
(`2025W36_1A_0095_1D1`, `2026W38_1A_0565_1D6`). TODO(WS2): no está en `FLAG_BITS` ni en `DEFAULT_BAD`.

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
| Registro WCS típico | Contra Gaia DR3, offset por frame con mediana ≤ 0,04 px y máximo ~0,2 px (ε Ind B, WISE 0855, RW Aur, R Dra). La estabilidad entre temporadas es ≤ 0,15″. |
| `PSF_FWHM` del header | Es más ancho que el núcleo: la mejor gaussiana mide 0,70–0,86 × header, según el método. Los patches S3 de WS1 no traen el HDU `EPSF`, porque `s3range` lee solo PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI y WCS-WAVE. |
| Saturación | R Dra: `OVERFLOW` en el núcleo en 2488 de 2488 frames. RW Aur: en 304 de 335 (todo D2–D6). `NONLINEAR` no aparece nunca en ninguno de los dos. Los píxeles `OVERFLOW` son **finitos**, no NaN. |
| WISE 0855 | Se ve solo en D5/D6: SNR ~3,5 por exposición y 21–25 sumando por detector. En D1–D4 no se detecta. |
| Cubo HiPS DR1 en S3 | Los tiles FITS (512×512×102) se leen por Range. El `obs_description` de IRSA lo presenta como producto **de visualización**: sirve para el panel, no para fotometría fina. `cube_spectrum` está en #42. |
| Snapshots de búsqueda | Los JSON de `data/index/search/` coinciden exactamente con SIA en vivo para los cinco blancos (centro y círculo descentrado), según #43. |
| TAP | No respondió en toda la sesión del 14/11: el fallback TAP sigue sin probarse en vivo (§6). |

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
| Sesame / VizieR (CfA) ✅ | https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?NOMBRE | resolver nombres con pm; Gaia DR3 `I/355/gaiadr3` (con CORS) |

## 6. Abierto ❓

- ✅ Resuelto: colecciones y tablas reales, `irsa_uri` ↔ key S3 (§3.0).
- Tamaño máximo de cutout y límites de tasa (S3: 16 lecturas en paralelo anduvieron bien; IRSA: ≤ 6–8).
- ❓ Fallback TAP de la búsqueda (JOIN `observation` + `INTERSECTS`) sin probar en vivo: TAP estuvo caído el 14/11.
- Política de cita/redistribución para publicar PNGs derivados (incluir créditos siempre).
- HiPS: ✅ IRSA publica el cubo SPHEREx DR1 (102 canales, orden 5, con CORS); los HiPS QR2 de CDS dan 404 por el
  incidente. ✅ Aladin Lite 3.8.2 lo renderiza (gotchas en [`VISION.md`](VISION.md)).
- ✅ WISE 0855 visible en D5/D6 y ✅ saturación de R Dra y RW Aur (§3.2). ❓ Saturación de Barnard; ❓ throughput a S3
  desde el host de deploy.

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

## Notas de otros WS

### WS7 — hallazgos verificados para el 3D (14/11/2026)

Hallazgos que usa el 3D de WS7 (rama `ws7/procedural-3d`), cada uno con su fuente citada en el código
(`frontend/src/three/ephemerides.ts`, `skyTrack.ts`, `spherexBands.ts`, `spherexCoverage.ts` y
`pipeline/errante/systems/catalog.py`). Se buscaron y leyeron con asistencia de Claude Code el 14/11. Ninguno es una
medición nuestra sobre píxeles SPHEREx, por eso no llevan ✅. Marcas: 📄 leído en la fuente (paper, tabla o consulta
al archivo) · ❓ no releído en esta sesión, o interpretación nuestra pendiente de revisión.

| Tema | Hallazgo | Cómo se verificó |
|---|---|---|
| Barnard b–e: t0 y P 📄 | Basant et al. 2025 (ApJL 982, L1), Tabla 3, con t0 en BJD − 2450000. b: t0 2460243.38 ± 0.09, P 3.1542 ± 0.0004 d. c: 2460242.92 ± 0.10, 4.1244 ± 0.0006 d. d: 2460243.70 (+0.08/−0.07), 2.3402 ± 0.0003 d. e: 2460245.30 (+0.37/−0.36), 6.7392 ± 0.0028 d (el archivo redondea a 0.003). El paper dice "BJD" sin aclarar TDB | Texto completo de arXiv:2503.08095 (v1, la única versión). Coincide con las filas `ps` con `default_flag = 1` del NASA Exoplanet Archive (TAP, 14/11) |
| Barnard b–e: qué es t0 ❓ | El paper lo llama "time of periastron passage". El código de juliet pasa t0 a RadVel como `tc` (conjunción) y no tiene parámetro de periastro. El archivo guarda el valor en `pl_orbtper` (periastro) y deja `pl_tranmid` vacío, siguiendo al paper, así que no lo confirma. Propagado 33 ciclos, el t0 de b coincide con el Tc de González Hernández et al. 2024 (BJD 2460139.204 ± 0.149) en 0.028 ciclos (0.5σ); leído como periastro quedaría a ~4.7σ con el ω mediano | Código de juliet (`fit.py`, `utils.py`, en master y en el tag v.2.2.6) y de RadVel; González Hernández+2024 (arXiv:2410.00569, §6, ec. 8, Tabla 6); test `test_basant_b_ephemeris_reaches_the_gonzalez_hernandez_2024_conjunction`. **Leerlo como conjunción es una decisión nuestra, pendiente de revisión del equipo** (`docs/VISION_3D.md`, M5) |
| R Dra: efeméride 📄 | AAVSO VSX (oid 13673, revisión 4, 2024-01-18): máximo en HJD 2457370.00, P = 246.12 d, subida 45 %, V 6.7–13.2. VSX no da errores de época ni de período. El GCVS 5.1 da P = 245.6 d, que usa el reloj *Free-running* | Página y API de VSX, y VizieR B/vsx en el espejo de CfA, consultados el 14/11 |
| R Dra: dispersión O−C 📄 | O−C de los máximos observados 2015-12 a 2024-09 (ciclos 0–13) respecto de VSX: media −4.7 d, desvío 4.6 d. WS7 usa como banda de 1σ el RMS respecto de VSX, √(4.7² + 4.6²) ≈ 6.6 d | Lista de T. Karlsson, "Maxima of Mira stars" (var.saaf.se, enlazada desde VSX): compilación secundaria, leída el 14/11. Media, desvío y RMS calculados por nosotros. Ningún término de Eddington–Plakidis tiene fuente |
| R Dra: masa ❓ | Masa class-typical ~1 M☉ (`Fact` con `verified = false`), usada solo para el tamaño de las celdas de convección. Base citada en el código: Feast 2009 (arXiv:0812.0250, §3), donde las Miras ricas en O con log P ~2.3 tienen masa inicial < 1 M☉ y las de carbono con log P ~2.7, ~1.8 M☉. R Dra tiene log P = 2.39 | **Sin verificar**: el paper no se releyó en esta sesión. El ~1 M☉ es una interpolación nuestra, y es una masa inicial: la actual es menor por pérdida de masa |
| Barnard: rotación 📄 | P_rot = 145 ± 15 d (Toledo-Padrón et al. 2019, MNRAS 488, 5145), de periodogramas de índices de actividad (Hα, Ca II H&K, Na I D) y del FWHM de la CCF en 14.5 años, con 15.1 años de fotometría | Resumen y Tabla 1 de arXiv:1812.06712, leídos el 14/11. Coherente con 142 ± 9 d de González Hernández+2024 |
| ε Ind Ab y Bb, RW Aur B: fases 📄 | Ninguna tiene una época utilizable. Sanghi et al. 2026 dan para Ab un periastro JD 2441420.76 (+2675/−3217 d) y P = 25450 (+4387/−3302) d, correlacionados y sin covarianza publicada. Chen et al. 2022 ajustaron un T0 para Bb pero no lo publican (la Tabla 4 da P, a, e, ω, Ω, i). Kurtovic et al. 2024 ponen el periastro de B 295 (+136/−457) años antes de su última época ALMA, sin documentar cómo se proyecta el marco de la órbita en el cielo | Sanghi: valores del NASA Exoplanet Archive, como cita el código (el paper no se leyó). Chen: HTML y PDF de arXiv:2205.08077 v1 (la versión AJ no se revisó). Kurtovic: arXiv:2407.18828, Tabla 3 y §3.3 |
| ε Ind B: astrometría del panel del cielo ❓ | Gaia DR3 6412596012146801152 (fotocentro Ba+Bb, RUWE 4.3) en J2016.0: RA 331.0764526°, Dec −56.7938121°, μ 3981.98 / −2466.83 mas/a, paralaje 270.66 mas, sin velocidad radial | Copiado de `docs/RECON_SPHEREX.md` §4.1; WS7 no lo re-consultó en Gaia |
| WISE 0855: dos predicciones 📄 | Con Kirkpatrick et al. 2021 (época MJD 57633.39) el lugar predicho para el 2026-11-14 queda a 0.31″ (0.05 px) del que da el ajuste propio WISE + NEOWISE de RECON §4.1 (133.757926, −7.241980) | `skyTrack.test.ts` reproduce los dos. Falta que WS3 elija uno para los recortes |
| SPHEREx: píxel y ventanas de pasadas 📄 | WS7 usa un píxel de 6.15″ (`SPHEREX_PIXEL_ARCSEC`) y las ventanas de pasadas de los cinco blancos (`SPHEREX_COVERAGE`) | No se re-midió ni se re-consultó. El píxel viene de RECON §2.2 (6.152″ medido con la raíz del determinante de PC; ver también §2 y §4 de este archivo). Las ventanas vienen de §3.0 ("Cobertura de los 5 objetivos", MJD redondeado al día) y de RECON §4.2 (fechas, detectores e imágenes a 3.9–5 µm). `spherexCoverage.test.ts` comprueba que las dos fuentes coinciden dentro del redondeo |
