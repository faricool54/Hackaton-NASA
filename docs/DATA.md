# Datos SPHEREx: hechos verificados

> Ver también [RECON_SPHEREX.md](RECON_SPHEREX.md): relevamiento del 2026-11-14 con endpoints probados en vivo
> (SIA/TAP sin CORS → proxy; S3 con CORS y Range → píxeles directo al navegador), colecciones DR1 + QR3 y tiempos medidos.

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
- Tamaño: **~66 MB por archivo** (DR1). Para un campo chico **no descargues archivos completos**: usá cutouts
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
| 6 | `WCS-WAVE` | tabla de búsqueda de longitud de onda por píxel: grilla **9×9** en DR1 (11×11 en QR según docs) |

Header de `IMAGE` (claves útiles): `MJD-OBS` (tiempo medio de la exposición — **usar este**), `DATE-OBS`,
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
| 9 | MISSING_DATA | 19 | OUTLIER | 28 | HALO |
| 10 | HOT | 20 | CROSSTALK | | |
| | | 21 | **SOURCE** | | |

⚠️ **"Cualquier bit ≠ 0 = malo" está MAL**: `SOURCE` (21) marca todas las estrellas (68 % de los píxeles en el
archivo inspeccionado). ⚠️ `OUTLIER`/`TRANSIENT` pueden dispararse **justo sobre un objeto en movimiento**
(no está donde el modelo del cielo estático lo espera): no los enmascares a ciegas para buscar movers.
Implementado en `errante.imaging.flags` (`DEFAULT_BAD`, `MAYBE_MOVER`, `bits_from_header`).

## 3. Buscar y recortar con IRSA 📄 (sin verificar: IRSA no era accesible desde el entorno que generó esto)

Fuentes: [SPHEREx Data Access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/),
[tutorial intro](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/),
[tutorial cutouts](https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/),
[parámetros de cutout IBE](https://irsa.ipac.caltech.edu/ibe/cutouts.html).

- **TAP** (ADQL, sync, CSV): `https://irsa.ipac.caltech.edu/TAP/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=...`
  Tablas documentadas: `spherex.plane` (`planeid`, `time_bounds_lower` [MJD], `poly`, `energy_bandpassname` =
  `'SPHEREx-D1'…'SPHEREx-D6'`) y `spherex.artifact` (`uri`, `planeid`). Consulta tipo en
  `errante.data.irsa.ADQL_FRAMES_AT_POSITION` (`CONTAINS(POINT('ICRS', ra, dec), p.poly)`).
  `uri` es relativo (`ibe/data/spherex/<release>/level2/...`): anteponer `https://irsa.ipac.caltech.edu/`.
- **SIA2**: `https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr3&POS=circle+<ra>+<dec>+<radio>`;
  colecciones documentadas `spherex_qr2`, `spherex_qr2_deep`, `spherex_qr3`, `spherex_qr3_deep`.
  ❓ Nombres para DR1 — **verificar** (WS1, primera tarea).
- **Cutout server-side**: `<url-del-fits>?center=<ra>,<dec>&size=<s>` (grados por defecto; `size=5arcmin` válido).
  Devuelve el mismo MEF recortado (no gzip), en **orientación nativa** (no norte-arriba → reproyectar), puede ser
  **no cuadrado** con NaN en bordes; sin superposición → HTTP 500.
- **Python**: `astroquery.ipac.irsa.Irsa.query_tap(...)`, `pyvo`. GUI: https://irsa.ipac.caltech.edu/applications/spherex
- Rendimiento reportado por otros: TAP 3–20 s por consulta; cutout 1–15 s; IRSA limita la concurrencia
  (usar ≤ 6–8 hilos, reintentos con backoff, no paralelizar consultas TAP).
- Variación de longitud de onda: cada exposición mide **una longitud de onda distinta en cada punto del
  detector** (filtro lineal variable). Calcularla en la posición del objeto con `WCS-WAVE`
  (`WCS(header, fobj=hdul, key="W")` según el tutorial) — ❓ verificar en cutouts.

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
| SIMBAD | https://simbad.cds.unistra.fr/ | estrellas/enanas marrones con movimiento propio |

## 6. Abierto ❓

- Nombres de colecciones/tablas de DR1 en IRSA; si `irsa_uri` ↔ `s3_key` es solo quitar `ibe/data/spherex/`.
- Tamaño máximo de cutout y límites de tasa.
- Política de cita/redistribución para publicar PNGs derivados (incluir créditos siempre).
- ¿Hay HiPS de SPHEREx (imagen, no cubo) usable directo en Aladin Lite?
