# Relevamiento técnico SPHEREx (2026-11-14)

> Generado por un relevamiento automático con verificación adversarial: 4 investigadores (datos, APIs, objetos de
> prueba, herramientas) + 1 verificador por tema que re-ejecutó las pruebas. Lo que no se pudo comprobar en vivo
> dice **(sin verificar)**. Los números (filas, tiempos, latencias) son de ese día: re-verificar antes de
> depender de ellos y anotar hallazgos nuevos en [DATA.md](DATA.md).


Relevamiento hecho el **2026-11-14**. Todo lo que no lleva marca se ejecutó en vivo contra los servicios reales (curl, Python o Chrome headless) o se leyó en la documentación oficial de IRSA. Lo que no se pudo comprobar en vivo dice **(sin verificar)**. Donde un verificador refutó o corrigió algo, acá aparece la versión corregida.

---

## 1. Resumen del desafío

**Qué piden:** una herramienta **web pública** donde cualquiera ingresa RA/Dec de un parche de cielo y ve **la serie de imágenes SPHEREx de ese parche como un videíto** (flip-book o blink), para detectar fácilmente lo que se mueve o cambia.

### Obligatorio
1. Una web pública, usable por no especialistas.
2. Entrada: coordenadas RA/Dec.
3. Salida: una secuencia temporal de imágenes SPHEREx del parche, animada.
4. Probarla con:
   - **Barnard's Star**
   - **Epsilon Indi B** (par de enanas marrones que orbita una estrella)
   - **WISE 0855** (RA 08h55m10.831s, Dec −07°14′42.53″)
   - **RW Aurigae** y **R Draconis** (variables)

### Opcional ("Potential considerations")
- Diseño fácil de actualizar cuando salen releases nuevos.
- Uso creativo de las 102 bandas. Por ejemplo, sumar todo lo de cada uno de los 6 detectores para ganar S/N. **"Extra kudos" si genera espectros on-the-fly.**
- Sumar y restar imágenes de épocas distintas.
- FOV elegible por el usuario: más FOV permite seguir objetos más rápidos, a costa de más transferencia.
- Overlays de otros telescopios (Gaia, WISE).
- Consulta por URL (`?ra=..&dec=..`) para poder embeberla.
- Mostrar metadata, como flags de contaminación.
- Usar herramientas públicas: "Astrophy tools" es casi seguro un typo de **Astropy**; también Aladin, del CDS.

### Criterios implícitos (deducidos del enunciado)
- Público general: cero instalación y UX simple.
- "Quickly": latencias de segundos.
- Foco en movimiento (descubrimiento) y en variabilidad.
- Mantenible frente a datos nuevos, reutilizable y embebible.
- Los criterios formales de evaluación de Space Apps no están en el material analizado.

### Lo que hace difícil este desafío (y donde se gana)
- **Los movimientos son chicos.** A 6.15″/px, los objetivos se mueven 0.4–1.7 px/año. Hace falta resampleo subpíxel, zoom, stacks por visita y diferencias.
- **LVF (linear variable filter).** Cada frame ve el objetivo en otra λ, así que un cambio de brillo entre frames mezcla espectro con variabilidad real.
- **Las coordenadas del enunciado y las J2000 están viejas.** WISE 0855 está a ~2.1′ de lo que dice el enunciado y Barnard a ~4.5′ de su J2000. Hay que propagar el movimiento propio.
- **CORS.** SIA, TAP e IBE de IRSA no mandan CORS, así que hace falta al menos un proxy. S3 y HiPS sí lo mandan.
- **Competencia.** Hay 173 repos con "spherex" creados entre el 10 y el 15 de nov de 2026 (266 contando los README).
- **IRSA Firefly ya tiene un checkbox "Auto play"** que pasa por las imágenes cargadas. El diferencial no es "animar", sino un flip-book **alineado (norte arriba), con stretch común, coadd por visita, diferencias, overlay de movimiento propio, filtro por λ local y espectro**.

---

## 2. Datos SPHEREx

### 2.1 Releases y colecciones

| Release | Contenido | Estado | ¿Se busca por SIA/TAP? | Archivos | DOI |
|---|---|---|---|---|---|
| QR1 | Semanales, jul 2025 | Retirado (feb 2026) | no | no | 10.26131/IRSA629 |
| QR2 | QR1 reprocesado + semanales desde oct 2025 (pipeline 6.x) | Reemplazado | **no** | `qr2/` en S3 e IBE hasta feb 2027 | 10.26131/IRSA652 |
| **QR3** | Surveys 3+4, pipeline R7 (`VERSION=7.0.5`), semanales desde sep 2026 | vigente | `spherex_qr3`, `spherex_qr3_deep` | `qr3/` | 10.26131/IRSA662 |
| **DR1** | Surveys 1+2 completos reprocesados con R7, más el **All-Sky Cube** | publicado nov 2026 | `spherex_dr1`, `spherex_dr1_deep`, `spherex_dr1_cube` | `dr1/` | 10.26131/IRSA678 (imágenes), IRSA679 (cubo) |
| DR2 | Años 1+2 | futuro | – | – | – |

- **Buscar siempre DR1 + QR3 juntos.** Juntos forman un set uniforme (los dos con pipeline R7).
- Los datos QR3 observados entre el 16 may y el 19 jul de 2026 salieron junto con DR1 (docs).

**Conteos en vivo** (TAP `GROUP BY obs_collection`; tarda 28–150 s):

| Colección | Filas | t_min (MJD → UTC) | Notas |
|---|---|---|---|
| `spherex_dr1` | 945,725 | 60789.75–61174.49 (2025-04-24 → 2026-05-14) | obs_release_date 2026-09-27 → 10-09 |
| `spherex_dr1_deep` | 233,681 | ídem | deep fields en NEP y SEP |
| `spherex_qr3` | 362,124 | 61174.51–61318.00 (2026-05-14 → **2026-10-05**) | último obs_release_date **2026-10-29** |
| `spherex_qr3_deep` | 86,700 | hasta 61317.97 | |
| `spherex_dr1_cube` | 12,288 (en `ivoa.obscore`) | – | tiles del cubo; **no figura en `spherex.obscore`**; SIA sí lo sirve |
| `spherex_dr1_cal` | 88 | tiempos null | calibración |

- **`spherex_qr2` no está en ObsCore.** Ojo: SIA devuelve un VOTable vacío de 27,474 B, **sin error, para cualquier nombre de colección inexistente**. No hay que hardcodear nombres; conviene descubrirlos así:

```bash
curl "https://irsa.ipac.caltech.edu/TAP/sync?FORMAT=csv&QUERY=SELECT+obs_collection,count(*),min(t_min),max(t_min)+FROM+ivoa.obscore+WHERE+obs_collection+LIKE+'spherex%25'+GROUP+BY+obs_collection"
```

Para imágenes se excluyen `_cal` y `_cube`.

- **Períodos de planificación en S3** (de `?list-type=2`):
  - `dr1/level2/`: 110 períodos (`2025W17_4B` … `2026W20_1A`)
  - `qr3/level2/`: 41 períodos (`2026W20_2A` … `2026W40_2A`)
  - `qr2/level2/`: 129 períodos
  - La raíz del bucket solo tiene `dr1/`, `qr2/`, `qr3/` e `index.html`. **No hay índice de metadata ni parquet**, así que para encontrar frames siempre hace falta SIA o TAP.
- **Desde el 2026-10-29 no salió ningún batch QR3** (16 días al momento del relevamiento). La causa no se conoce; quizás sea una pausa por DR1 (sin verificar).

### 2.2 Instrumento y detectores

| Det | Tipo | λ (µm, SIA em_min–em_max) | R | Pareja dicroica (mismo cielo y mismo instante) |
|---|---|---|---|---|
| D1 | SWIR H2RG 2.6 µm, 62 K | 0.746–1.117 | 39 | D4 |
| D2 | SWIR | 1.103–1.650 | 41 | D5 |
| D3 | SWIR | 1.630–2.435 | 41 | D6 |
| D4 | MWIR 5.3 µm, 45 K | 2.403–3.847 | 35 | D1 |
| D5 | MWIR | 3.811–4.430 | 112 | D2 |
| D6 | MWIR | 4.412–5.010 | 128 | D3 |

**Geometría**
- 2040×2040 px a **6.15″/px** (6.152″ medido con √|det PC|). Cada imagen cubre ~3.49°×3.49°.
- WCS `RA---TAN-SIP` de orden 3, con CRPIX 1020.5. La distorsión llega a ~13 px (~80″) en las esquinas (docs).
- FOV total del instrumento: 2×(3.5°×11.3°).
- Las parejas D1/D4, D2/D5 y D3/D6 comparten `obs_id`. En un punto dado del cielo, cada exposición cae en **una sola** pareja, así que n_imágenes ≈ 2 × n_exposiciones.

**PSF y calidad**
- PSF FWHM 6.9–8.3″ (D1 7.1, D2 6.9, D3 6.9, D4 7.7, D5 8.0, D6 8.3), es decir **1.1–1.35 px: está submuestreada**. El `PSF_FWHM` del header oscila entre 7.45″ y 8.8″.
- RMS astrométrico frente a Gaia: <0.3″ por imagen (docs, dato para D3).
- Inicio de no-linealidad, en AB (docs, Tabla 25, de un modelo pre-lanzamiento): B1 11.50, B2 11.50, B3 11.30, B4 11.71, B5 10.19, B6 9.75.

**Exposición y canales**
- `XPOSURE` = 113.58 s y `TELAPSE` = 118.19 s.
- **17 canales por detector, 102 en total.** Centros de D1 (µm): 0.753 0.771 0.790 0.809 0.828 0.848 0.868 0.889 0.910 0.932 0.955 0.978 1.001 1.025 1.050 1.075 1.102.
- Las tablas completas están en el Explanatory Supplement v2.1, Tablas 29–34. También en la propiedad `data_cube_crval3_arr` del HiPS.

### 2.3 LVF: λ por píxel

**Cómo varía λ en el detector**
- λ cambia a lo largo del **eje Y (filas)**. Las líneas de λ constante se curvan levemente en X (~24 nm de curvatura en D3, alrededor de medio elemento de resolución).
- D3: λ va de 2.419 µm en y=1 a 1.616 µm en y=2040. A media altura (y=1020), λ en X va de 1.983 a 2.007 µm. El gradiente es −0.394 nm/px y **un canal ocupa ~115–120 px**.
- D6: de 5.025 µm en (0,0) a 4.408 µm en (2039,2039).
- Las primeras ~140 filas de D3 son la zona "smile" del dicroico (flag DICHROIC).

**Consecuencia**
- Cada *small slew* mueve el objetivo ~1 canal en y. Exposiciones sucesivas lo ven en λ distintas: en DR1 la estrella de Barnard en D3 recorrió 1.618–2.393 µm en 41 frames.
- **Un flip-book crudo mezcla espectro y variabilidad.**

**Tres formas de sacar λ y Δλ en un píxel**
1. **Astropy** (como en el tutorial):
   ```python
   sw = WCS(hdul['IMAGE'].header, fobj=hdul, key='W'); sw.sip = None
   lam, bw = sw.pixel_to_world(x, y)  # µm
   ```
   Siempre poner `sip=None`. Con SIP activo, una verificación midió errores de 1.8–13 nm (peores en los bordes) y otra vio <0.1 nm en un píxel central.
2. **Portable (JS):** interpolación bilineal de `WCS-WAVE.VALUES[...,0]` (λ) y `[...,1]` (Δλ) sobre la grilla 1-based `X`,`Y`. En Python es `RegularGridInterpolator((Y,X), V[:,:,0])` evaluado en (y+1, x+1). **Coincide exactamente con astropy `sip=None`.** La tabla está en los últimos 5760 B del archivo (`Range: bytes=-5760`).
3. **Calidad científica:** las imágenes `CWAVE`/`CBAND` de 2040×2040 en `dr1/spectral_wcs/cal-swcs-v5-2026-191/{d}/spectral_wcs_D{d}_spx_cal-swcs-v5-2026-191.fits` (33 MB cada una). El nombre real es `cal-swcs`, no `cal-wcs` como dice la doc.

`spectral_channels_*.fits` asigna a cada píxel un canal 0–18. Es geométrico, de planificación; no es λ calibrada (docs).

### 2.4 Formato del archivo L2 (MEF, 58–69 MB)

```
0 PRIMARY   vacío (VERSION='7.0.5')
1 IMAGE     2040x2040 float32 big-endian, MJy/sr, ZODI NO restado
2 FLAGS     CompImageHDU int32, RICE_1, ZTILE 2040x1 (un tile por fila)
3 VARIANCE  float32, MJy²/sr²
4 ZODI      float32, MJy/sr (modelo KEL98_WAVESCL_V1)
5 EPSF      BinTable 33x33 sobremuestreado x5; 451 filas en D3 (11x41 zonas);
            441 (21x21) en D1,2,4,5,6 según docs (sin verificar en vivo); ~3.95 MB
6 WCS-WAVE  BinTable 1 fila: X, Y, VALUES(2,nX,nY); últimos 5760 B del archivo
            grilla: D1 9x9, D2 11x11, D3 9x14, D4 13x20, D5 11x11, D6 9x9
```

**Offsets para range reads**
- Header primario: 2880 B.
- Los datos de IMAGE empiezan en el **byte 25920** en todos los archivos re-verificados (DR1 y QR3). Un reporte vio también 28800 (no reproducido). **Hay que parsear el header y no hardcodear.**
- Cada fila son 8160 B. La fila y (0-based) empieza en `dataStart + y*8160`.
- Ejemplo de un D3 completo (61,948,800 B): FLAGS en 16,689,600, VARIANCE en 24,684,480, ZODI en 41,342,400, EPSF en 57,994,560 y WCS-WAVE en 61,945,920.

**Keywords útiles del header de IMAGE**
- Identidad: `DETECTOR`, `OBSID`, `EXPIDN`.
- Tiempo: `DATE-OBS`, `MJD-OBS`, **`MJD-AVG`**, `MJD-END`.
- Apuntado: `SPS_EPA`. Vale 0 o 180 y alterna por visita (180 en ago 2025, 0 en mar 2026, 180 en ago 2026). **La orientación gira ~180° entre visitas.** Rolls observados: −163.7°, +19.6°, 16.5°.
- Calidad: `L1DQAFLG`/`L2DQAFLG`, `PSF_FWHM`, `OMEGA_MEDIAN` (37.86 arcsec²), `AURORA_CONT`, `SHUTTLE_GLOW_CONT`, `HE_AIRGLOW_CONT`.
- `X_SC`…: posición geocéntrica de la nave (sirve para la paralaje de objetos cercanos).
- `DETCOORD='sky'`: las imágenes MWIR vienen volteadas en X para coincidir con SWIR.

**WCS alternativos**
- `A`: píxeles 0-based. `CRPIX1A`/`CRPIX2A` dan el origen de un cutout dentro de la imagen padre.
- `W`: `WAVE-TAB`, que apunta a WCS-WAVE.

**Nombres de archivo**
- Patrón: `level2_{PlanningPeriod}_{LargeSlew}_{SmallSlew}D{det}_spx_l2b-v{ver}-{YYYY-DDD}.fits`. Ejemplo: `level2_2025W33_2C_0321_1D3_spx_l2b-v27-2026-228.fits`.
- El directorio depende de la versión de procesamiento (`l2b-v27-2026-197`, `l2b_retry-v27-2026-207`…). Las 258 filas de WISE 0855 caen en 12 carpetas distintas.
- **Las URLs no se pueden armar a partir del `obs_id`; hay que sacarlas de SIA o TAP.**
- El `Last-Modified` de S3 es 2026-11-11: los archivos se reescriben.

**Unidades:** MJy/sr. Para pasar a µJy se multiplica por el ángulo sólido del píxel (mapa `solid_angle_pixel_map` o `OMEGA_MEDIAN`).

### 2.5 FLAGS (bitmask)

Los nombres también vienen en el header de FLAGS (`MSKNnnnn`, `MSKMnnnn`, `MSKDnnnn`).

| bit | nombre | significado | % de píxeles (D3 de muestra, cerca del plano galáctico) |
|---|---|---|---|
| 0 | TRANSIENT | salto en el ajuste SUR (rayo cósmico); **no es un transitorio astrofísico** | 0.59 |
| 1 | OVERFLOW | ~½ del pozo lleno | 0.04 |
| 2 | SUR_ERROR | error de procesamiento a bordo | 0.42 |
| 6 | NONFUNC | píxel muerto | 0.29 |
| 7 | DICHROIC | baja transmisión en las esquinas dicroicas de D3/D4 | 2.64 |
| 9 | MISSING_DATA | datos perdidos en la bajada | 0 |
| 10 / 11 | HOT / COLD | por exposición | ~0 / 0.04 |
| 12 | FULLSAMPLE | solo informativo | 0.01 |
| 14 | PHANMISS | sin corrección de phantom | 0 |
| 15 | NONLINEAR | no-linealidad poco confiable | 0 |
| 17 | PERSIST | persistencia | 0.22 |
| 19 | OUTLIER | detector outlier | 0.44 |
| 20 | CROSSTALK | crosstalk | 0 |
| **21** | **SOURCE** | píxel sobre una fuente conocida. **No es malo: nunca enmascararlo** | 94.65 |
| 22 / 23 / 24 | GHOST / GHOST_FPA (no se usa) / GHOST_EXT | ghosts | 0 |
| 25 | STREAK | satélite o basura espacial | 0 |
| 26 | BLOOM | blooming | 0.19 |
| 27 | SNOWBALL | snowball | ~0 |
| 28 | HALO | halo de un transitorio | 1.16 |
| 29 | SATELLITE_HALO | solo en la docs; no aparece en el header | – |

**Máscaras posibles**
- **"Malo" sugerido para el visor:** bits 0,2,6,7,9,10,11,14,15,17,20,25,26,27,28,29, que da `1041419973` (`0x3E12CEC5`). OUTLIER y GHOST conviene mostrarlos como overlay.
- La herramienta Spectrophotometry de IRSA ignora los bits 2,6,9,10,11,15,17,26,27,28,29, que da `1006800452`.
- El notebook Source Discovery usa una regla más simple: píxel bueno si FLAGS ∈ {0, 2, 2097152}.

**Lectura:** en el archivo completo, FLAGS está **comprimido con RICE_1**. En el navegador haría falta un decoder RICE (no implementado ni probado). Astropy lo decodifica sin problema, también con `.section` sobre fsspec. En los cutouts de IBE viene sin comprimir.

### 2.6 Cadencia

- **Cada punto del cielo se observa cada ~6 meses**, alternando PA 0° y PA 180°.
  - Surveys 1+2: meses 0–12.5.
  - Surveys 3+4: meses 12.5–25, corridos 6′ (medio canal) para tener muestreo Nyquist espectral.
- **Dentro de una visita** (dura 1–3 semanas) hay ~17–24 exposiciones por detector:
  - Vienen en grupos de 2–4 *small slews* separados **129 s**.
  - Los grupos están separados por horas o días.
  - Un "target group" son 17 apuntados, cada uno a un canal del anterior.
- **Agrupar en visitas con un gap de ~10 días** (dejarlo configurable). Con 30 días, en WISE 0855 se fusionan las visitas de nov y dic 2025.
- **Ingesta:**
  - Datos calibrados en IRSA dentro de los 60 días desde la observación (docs).
  - QR3 sale semanalmente.
  - SIA va ~1 día atrás de TAP y S3 (docs).
- **Deep fields (NEP y cerca del SEP):** cobertura casi continua. En NEP con r=0.01°, `spherex_dr1_deep` devuelve 20,901 filas en 23 s.

### 2.7 Otros productos

**All-Sky Cube (solo DR1, coadd estático, ZODI restado)**
- 12,288 tiles HEALPix de orden 5 (NESTED), cada uno de 512×512×102 a 12.9″/px en proyección HPX.
- Extensiones: IMAGE, NHITS, FLAGS, SPECTRAL_CHANNELS, WCS-WAVE.
- **Cada tile pesa 320,909,760 B.**
- Hay copias **con CORS y Range** en:
  - `https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube/Norder5/Dir{(ipix//10000)*10000}/Npix{ipix}_cube.fits`
  - `https://nasa-irsa-spherex.s3.amazonaws.com/dr1/hips5_cube/hips_20261026/Norder5/Dir0/Npix100_cube.fits` (patrón análogo)
  - La copia en `ibe/data/spherex/dr1/hips5_cube/...` **no** tiene CORS.

**HiPS cube (PNG, para visualización)**
- `https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube`
- Propiedades: order 5, tiles de 512 px, depth 102, `hips_cube_firstframe=1`, stretch asinh 0–40 MJy/sr, ACAO `*`, publicado 2026-11-01.
- Índice de frame = 17·(banda−1) + (canal−1).
- Nombres de tile:
  - Frame 0 es `NpixN.png` o `Allsky.png`, **sin sufijo**.
  - Frames 1–101 son `NpixN_k.png`.
  - **Los frames 50 y 51 (dicroicos) no existen (404).** `_0` y `_102` también dan 404.
- **No tiene eje temporal; sirve solo como capa de contexto.**

**Catálogos**
- SPLICES (lista de fuentes de hielo): tabla TAP `spherex.splices`, 9,925,660 filas y 151 columnas.
- **Todavía no hay un catálogo de fuentes propio de SPHEREx.**

**Otros**
- **Cometa 3I/ATLAS** (ago y dic 2025):
  - Página: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html
  - VOTable: `obscore_3I_Atlas.vot` (259 filas, con `comet_ra`/`comet_dec`).
  - **Todas las filas son de `spherex_qr2`.** Hay que remapear a DR1 por `obs_id` vía SIA/TAP. Ejemplo: `2025W31_2A_0156_1` D3 pasa a ser `dr1/level2/2025W31_2A/l2b-v27-2026-225/3/level2_2025W31_2A_0156_1D3_spx_l2b-v27-2026-225.fits`.
  - Sirve como set de prueba para objetos en movimiento.
- **Productos de calibración** (S3 `dr1/`): abs_gain_matrix, dark, epsf, sip, solid_angle_pixel_map, spectral_channels, spectral_wcs, zodi_scaling_v2, entre otros.
- **Respuesta espectral de laboratorio:** https://irsa.ipac.caltech.edu/data/SPHEREx/docs/spectral_files_20260812/SPHERExSpectralFiles_202607.tar

---

## 3. Acceso a los datos

### 3.1 Endpoints y CORS

Probado con un header `Origin` y en Chrome headless.

| Servicio | URL | CORS | Notas |
|---|---|---|---|
| **SIA v2** | `https://irsa.ipac.caltech.edu/SIA?COLLECTION=..&POS=CIRCLE+RA+DEC+R` | **NO** | Ver detalle abajo |
| **TAP** | `https://irsa.ipac.caltech.edu/TAP/sync` | **NO** | Ver detalle abajo |
| **IBE archivo** | `https://irsa.ipac.caltech.edu/ibe/data/spherex/{dr1\|qr3}/level2/...fits` | **NO** (OPTIONS da 405) | Acepta Range (206). ~1.4–1.85 MB/s |
| **IBE cutout** | URL del archivo + `?center=RA,DEC&size=X[arcsec\|arcmin\|deg\|pix][&gzip=true]` | **NO** | Ver detalle abajo |
| **IBE listado de directorios** | `https://irsa.ipac.caltech.edu/ibe/data/spherex/...` | – | **Da 404 en todo**, aunque la doc apunta ahí. Usar el listado de S3 |
| **S3 (AWS Open Data)** | `https://nasa-irsa-spherex.s3.amazonaws.com/{key}`; también `.s3.us-east-1.amazonaws.com/` y path-style `s3.us-east-1.amazonaws.com/nasa-irsa-spherex/` | **SÍ**, `ACAO: *` | Ver detalle abajo |
| **HiPS** | `https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube/` | **SÍ** | Preflight 204, Allow-Headers Range, max-age 86400 |
| **MOST** | `https://irsa.ipac.caltech.edu/cgi-bin/MOST/nph-most` (POST multipart, `catalog=spherex`) | sin verificar | Vesta (NAIF 20000004): 144 imágenes en 3.3 s |
| **Gaia DR3, CatWISE, WISE** | IRSA TAP: `gaia_dr3_source`, `catwise_2020`, `allsky_4band_p3as_psd`, `neowiser_p1bs_psd`, `unwise_2019`, `unwise.unwise_neo3_images` | **NO** | Gaia 12.7–23 s; CatWISE 13–24 s; NEOWISE single-exposure 76 s |

- **SIA:**
  - Tarda 1–2.5 s en campos anchos. En deep o polares es mucho más (NEP: 23 s y 20.9k filas).
  - Acepta `COLLECTION` repetido, `BAND=lo+hi` (en metros) y `TIME=mjd1+mjd2`, más `MAXREC` (con OVERFLOW) y `RESPONSEFORMAT`.
  - **El CSV viene malformado:** el JSON de `cloud_access`, que es la columna 49 de 51, va sin comillas, así que cada fila da 53 campos. Usar VOTable, o quedarse con los primeros 48 campos.
  - Las respuestas no vienen gzippeadas.
  - **Sin `COLLECTION` busca en todo IRSA: 46 s y 33 MB. No hacerlo nunca.**
- **TAP:**
  - Tablas: `spherex.obscore`, `.plane`, `.artifact`, `.observation`, `.provenance_input`, `.splices`.
  - Tiene los datos más frescos (sin el lag de SIA).
  - Una consulta por posición tarda 4.5–19 s.
  - `a.uri` es relativa: la key de S3 es `uri` menos `ibe/data/spherex/`.
- **IBE cutout:**
  - **Devuelve los 7 HDUs, incluida la EPSF entera: mínimo 3.95–4.05 MB aunque pidas 6×6 px.**
  - Viene alineado al detector, no norte-arriba.
  - Tarda 1.9–7.8 s.
  - **Hoy dio `503 Server busy` (Retry-After: 5) en el 36% de las requests** (5 de 8 con concurrencia 8).
- **S3:**
  - Allow-Methods GET/HEAD y **Allow-Headers range**. Preflight 200 con max-age 3000.
  - Range y suffix-range (`bytes=-5760`) responden 206.
  - El listado `?list-type=2&prefix=..&delimiter=/` también manda CORS.
  - **Es ~15× más rápido que IBE:** 20.8 MB/s contra 1.4 MB/s para los mismos 16.6 MB. Los bytes son idénticos.
  - No pide credenciales y no cobra egress.
  - Solo expone `ETag`: **JS no puede leer `Content-Range`**. `Content-Length` se lee con HEAD, o el tamaño se saca de NAXIS.
  - Sirve solo HTTP/1.1 (~6 conexiones por host). Usar dos hosts duplica eso.

### 3.2 ¿Hace falta backend?

**Sí, como mínimo un proxy chico para SIA y TAP** (y para Gaia por TAP). El navegador **no puede** consultar SIA ni TAP ni bajar cutouts de IBE; se verificó con un fetch real en Chrome: "blocked by CORS policy". **Los píxeles sí pueden ir directo de S3 al navegador** con Range reads. Hay un prototipo JS funcionando (ver 3.3).

Aun así, conviene un backend "de verdad" en Python, por estas razones:
- Reproyección SIP → TAN con resampleo bilineal.
- Decodificación de los FLAGS RICE.
- Coadds y diferencias por visita.
- Cache de las consultas de Gaia, que son lentas.
- Espectro on-the-fly.
- Listas precomputadas para la demo.

### 3.3 Ejemplos que funcionaron

**SIA (VOTable), DR1+QR3, en la posición 2026 de WISE 0855:** 258 filas en ~1.4–1.7 s, 567 KB.
```bash
curl -s "https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1&COLLECTION=spherex_qr3&POS=CIRCLE+133.7598387+-7.2421674+0.000278&RESPONSEFORMAT=VOTABLE"
# con filtros: &BAND=4.7e-6+5.1e-6 (D6 solo; BAND matchea cualquier solapamiento con el rango
# del DETECTOR, no la λ en el objetivo) &TIME=60900+60920 (MJD) &MAXREC=2000
```

Columnas útiles:
- `obs_id`, `energy_bandpassname` (`SPHEREx-D1`…`D6`; el detector es el último carácter).
- `t_min`, `t_max` (MJD), `t_exptime`.
- `em_min`, `em_max` (en metros; son del detector entero).
- `access_url`, `access_estsize` (kB), `cloud_access` (JSON con bucket y key).
- `s_region` (POLYGON), `s_fov`, `s_pixel_scale`, `obs_collection`, `obs_release_date`, `obs_publisher_did`.

**Python:**
```python
from astroquery.ipac.irsa import Irsa
res = Irsa.query_sia(pos=(SkyCoord(ra, dec, unit='deg'), 1*u.arcsec),
                     collection=['spherex_dr1', 'spherex_qr3'])      # 258 filas, 2.0 s
# o: pyvo.dal.SIA2Service('https://irsa.ipac.caltech.edu/SIA').search(pos=(ra,dec,r_deg), collection=[...])
```

**TAP** (datos más frescos, con colección; 363 filas en 16 s en Barnard):
```bash
curl --data-urlencode "QUERY=SELECT a.uri, p.time_bounds_lower, p.energy_bandpassname, o.collection FROM spherex.artifact a JOIN spherex.plane p ON a.planeid=p.planeid JOIN spherex.observation o ON p.obsid=o.obsid WHERE 1=CONTAINS(POINT('ICRS',269.4462952,4.7681531),p.poly) ORDER BY p.time_bounds_lower" \
     -d "LANG=ADQL&FORMAT=csv" https://irsa.ipac.caltech.edu/TAP/sync
```

**De access_url a S3** (vale para las 258 filas de 258):
```
key = access_url.removeprefix("https://irsa.ipac.caltech.edu/ibe/data/spherex/")   # == cloud_access.aws.key
url = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/" + key
```

**Range read de S3 desde el navegador** (206 con ACAO `*`):
```bash
curl -r 0-25919 -H "Origin: https://x" "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/dr1/level2/2025W19_1B/l2b-v27-2026-197/3/level2_2025W19_1B_0116_1D3_spx_l2b-v27-2026-197.fits"
```

**Python: estampilla de 60×60 + flags + zodi + λ, leyendo solo los bytes necesarios.** Tarda ~2 s; con `block_size` de 1 MiB, 0.71 s.
```python
from astropy.io import fits; from astropy.wcs import WCS; from astropy.coordinates import SkyCoord
key = "dr1/level2/2025W33_2C/l2b-v27-2026-228/3/level2_2025W33_2C_0321_1D3_spx_l2b-v27-2026-228.fits"
coord = SkyCoord(269.44635, 4.76712, unit="deg")   # Barnard PROPAGADO a 2025.62 (no usar J2000)
with fits.open("https://nasa-irsa-spherex.s3.amazonaws.com/" + key, use_fsspec=True,
               fsspec_kwargs={"block_size": 2**20}) as h:
    w = WCS(h["IMAGE"].header); x, y = (int(round(float(v))) for v in w.world_to_pixel(coord))
    sl = (slice(y-30, y+30), slice(x-30, x+30))
    img, flg, zod = h["IMAGE"].section[sl], h["FLAGS"].section[sl], h["ZODI"].section[sl]  # FLAGS: astropy decodifica RICE
    sw = WCS(h["IMAGE"].header, fobj=h, key="W"); sw.sip = None
    lam, bw = sw.pixel_to_world_values(x, y)   # µm
```

**JS en el navegador, sin dependencias** (prototipo `07_browser_range_cutout.mjs`). Su TAN-SIP coincide con astropy `all_world2pix` hasta 2.4e-7 px.
```js
const s3 = accessUrl.replace("https://irsa.ipac.caltech.edu/ibe/data/spherex/",
                             "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/");
const hb = new Uint8Array(await (await fetch(s3,{headers:{Range:"bytes=0-40319"}})).arrayBuffer());
// parsear cards de 80 chars -> dataStart, CRVAL/CRPIX/PC/A_/B_/AP_/BP_; world->pix con AP/BP + 2 pasos de Newton
const rb = await fetch(s3,{headers:{Range:`bytes=${dataStart+y0*8160}-${dataStart+(y1+1)*8160-1}`}});
const dv = new DataView(await rb.arrayBuffer());
const v = dv.getFloat32(((y-y0)*2040 + x)*4, false);          // big-endian
// λ local: fetch(s3,{headers:{Range:"bytes=-5760"}}) -> HDU WCS-WAVE
```
Resultado: 45 frames D6 de 5′ en **4.5 s**, 25.9 MB, 571 KB por frame, con 6 requests en paralelo.

**IBE cutout** (solo como fallback del lado servidor; implementar reintentos con backoff):
```bash
curl -o cut.fits "https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/2025W33_2C/l2b-v27-2026-228/3/level2_2025W33_2C_0321_1D3_spx_l2b-v27-2026-228.fits?center=269.44635,4.76712&size=0.1"
```
El centro está corregido (sin verificar). El ejemplo original, centrado en la J2000 de Barnard, **no contenía a la estrella**: quedaba a 42.7 px, contra ~29 px de semiancho del cutout.

**MOST** (objetos del Sistema Solar):
```bash
curl -F catalog=spherex -F input_type=naifid_input -F obj_naifid=20000004 -F obj_type=Asteroid \
     -F obs_begin=2026-01-01 -F obs_end=2026-10-15 -F output_mode=Brief https://irsa.ipac.caltech.edu/cgi-bin/MOST/nph-most
```
Por nombre falla si el nombre es ambiguo.

**Gaia DR3 por IRSA TAP** (~13–30 s, sin CORS, así que va por backend y con cache):
```bash
curl --data-urlencode "QUERY=SELECT source_id,ra,dec,pmra,pmdec,parallax,phot_g_mean_mag,ref_epoch FROM gaia_dr3_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',269.4521,4.6934,0.1)) AND phot_g_mean_mag<10" \
     -d "LANG=ADQL&FORMAT=csv" https://irsa.ipac.caltech.edu/TAP/sync
```
En `catwise_2020` el movimiento propio viene en arcsec/año y la época está en `meanobsmjd`.

**Listado de S3** (reemplaza al listado de IBE, que da 404):
```
https://nasa-irsa-spherex.s3.amazonaws.com/?list-type=2&prefix=dr1/level2/&delimiter=/
```

### 3.4 Costos por frame

| Método | Bytes | Tiempo |
|---|---|---|
| S3 Range, estampilla de 3′ | ~0.30 MB (36 filas × 8160 B + header de ~26 KB) | <1 s |
| S3 Range, 5′ / 10′ / 30′ | ~0.57 / 1.1 / 3.4 MB | – |
| IBE cutout (cualquier tamaño chico) | ≥3.95–4.05 MB | 1.9–7.8 s; 36% de 503 |
| Archivo completo | 58–69 MB | 18 s desde S3, 36–53 s desde IRSA |
| Python, 258 frames de todas las bandas a 5′ | 163 MB | 9.6 s (6 threads) |

Las filas a leer son ≈ n·(|cos θ| + |sin θ|) para una caja de n px con roll θ; en el peor caso (45°) es 1.41× n.

### 3.5 Detalles que muerden

- Cachear la metadata, pero **re-consultar SIA/TAP en cada búsqueda nueva** para que aparezcan las semanas QR3 nuevas. Las listas precomputadas se vencen: regenerarlas el día de la demo.
- `s_region` a veces incluye imágenes donde el objetivo cae hasta ~7 px **afuera** del detector. Hay que chequear el píxel antes de cortar.
- Las colecciones deep (cerca de los polos eclípticos) van **apagadas por defecto**, o con `MAXREC`.
- En el navegador se puede lanzar el preflight de Range aunque la request esté safelisted (sin verificar si hace falta); S3 lo acepta igual.

---

## 4. Objetos de prueba

### 4.1 Astrometría y movimiento esperado

Datos de Gaia DR3 vía IRSA TAP. Píxel SPHEREx = 6.15″.

| Objeto | Catálogo (época) | **Posición para buscar, 2026.0** (deg) | μα*, μδ (mas/año) | ϖ (mas) | Movimiento (px/año) | Desplazamiento sobre la línea de base disponible | Distancia de las coords de catálogo o del enunciado |
|---|---|---|---|---|---|---|---|
| **Barnard** | Gaia DR3 4472832130942575872: 269.4485025, +4.7394201 (J2016.0) | **269.4462952, +4.7681531** | −801.55, +10362.39 | 546.98 | **1.69** (10.39″/año, hacia el norte) | 2025-08 → 2026-08: ~10″ ≈ 1.65 px. 2025-05 → 2026-11: 15.7″ ≈ 2.56 px. Paralaje ±0.55″ | **279″ (45 px) al sur desde J2000** (269.4521, +4.6934) |
| **ε Indi B (Ba+Bb sin resolver)** | Gaia DR3 6412596012146801152: 331.0764526, −56.7938121 (J2016.0); RUWE 4.3 (binaria) | **331.0965591, −56.8006419** | +3981.98, −2466.83 | 270.66 | **0.76** (4.68″/año) | 2025.36 → 2026.74: 6.3″ ≈ **1.03 px** | 126″ (~20 px) desde J2000 (331.0438, −56.7827) |
| **WISE 0855−0714** | No está en Gaia. Ajuste propio WISE + NEOWISE-R: μ ≈ (−8095, +696), ϖ ≈ 430–475. Kirkpatrick+2021: (−8123.7, +673.2), ϖ 439.0 (fuente secundaria, sin verificar) | **133.7598387, −7.2421674** | ≈ −8100, +690 | ~440 | **≈1.32** (8.1″/año, hacia el oeste) | 2025.34 → 2026.33: ~8″ ≈ 1.3 px. Corrimiento geocéntrico a 6 meses: 3.25–3.5″. Paralaje ±0.44″ | Las coords del enunciado (133.7951292, −7.2451472) son de **WISE All-Sky, época 2010.34**: **126.5″ (20.6 px) en 2026.0, 133″ hoy** |
| **RW Aur A (+B a 1.5″)** | Gaia DR3 156430822114424576: 76.9560812, +30.4012046 | 76.9560889, +30.4011286 | +2.64, −27.40 | 6.41 | 0.004 (estática) | despreciable | 0.7″ |
| **R Dra** | Gaia DR3 1648328016354496384: 248.1673784, +66.7550067; flag VARIABLE | 248.1672335, +66.7550235 | −20.64, +6.15 | 1.25 | 0.004 (estática) | despreciable | 0.6″ |

**Posiciones en épocas SPHEREx**
- Barnard: 2025.6 → 269.44636, +4.76705; 2026.2 → 269.44622, +4.76878; 2026.7 → 269.44611, +4.77022.
- ε Indi B: 2025.6 → 331.09585, −56.80039; 2026.7 → 331.09807, −56.80114.
- WISE 0855: 2026-11-14 → 133.757926, −7.241980.
- Las posiciones 2026.0 de la tabla son geocéntricas. Las baricéntricas difieren en 0.2–0.27″, lo que es irrelevante a 6.15″/px.

**Método:** `SkyCoord.apply_space_motion` (incluye RV) más la posición de la Tierra, y propagación al `MJD-AVG` de cada frame.

### 4.2 Cobertura SIA encontrada

En las posiciones de 2026, con r=1″. Pasadas agrupadas con un gap de 30 días.

| Objeto | Imágenes (por colección) | Por detector D1…D6 | Exposiciones / días distintos | Pasadas: fechas (n imágenes; n con λ 3.9–5 µm) | Tile del cubo |
|---|---|---|---|---|---|
| Barnard | **358** (dr1 239, qr3 119) | 60/61/59/59/61/58 | 181 / 39 | 2025-08-15..10-01 (118; 32) · 2026-03-11..05-05 (121; 40) · 2026-08-16..09-22 (119; 38) | Npix7945 |
| ε Indi B | **458** (dr1 338, qr3 120) | 46/93/96/46/84/93 | 238 / 60 | 2025-04-24..06-10 (118; 50) · 2025-09-28..11-12 (146; 39) · 2026-04-18..05-04 (74; 16) · 2026-09-22..10-02 (120; 55; solo D2/3/5/6) | Npix11391 |
| WISE 0855 | **258** (dr1 258, **qr3 0 por ahora**) | 36/48/45/36/48/45 | 129 / 27 | 2025-05-05..06 (30; 11) · 2025-10-31..12-13 (128; 43); con gap de 10 días se separa en 10-31..11-14 (110) y 12-11..13 (18) · 2026-04-21..05-14 (100; 34) | Npix10226 |
| RW Aur | **335** (dr1 226, qr3 109) | 56/55/56/56/56/56 | 168 / 35 | 2025-09-01..20 (112) · 2026-02-20..03-12 (114) · 2026-09-02..16 (109) | Npix277 |
| R Dra (dentro del NEP Deep) | **2493** (dr1 413, **dr1_deep 1225**, qr3 126, **qr3_deep 729**) | 584/89/574/584/89/573 | 1258 / 222 | **Cada mes** de 2025-04 a 2026-09 (gap máximo 37.8 d). Por mes: 58, 41, 91, 50, 14, 188, 84, 82, 84, 20, 112, 500, 253, 84, 56, 119, 432, 225 | Npix2928 |

- Con las coordenadas J2000 los conteos cambian un poco (Barnard 363 = 240+123; ε Indi B 465 = 345+120) porque los frames miden 3.5°. **La cobertura casi no depende de la época; el FOV del recorte sí.**
- La próxima pasada de WISE 0855 (Survey 3/4, ~nov–dic 2026) todavía no está en QR3 (estimación, sin verificar).

### 4.3 FOV recomendado y particularidades

| Objeto | FOV centrado en la posición propagada | FOV centrado en coords de catálogo o enunciado | Particularidades para la herramienta |
|---|---|---|---|
| Barnard | **3′** (29 px) | **≥10–12′** | Saturada: núcleo NaN (1–5 px) en D1–D4, raro en D5, nunca en D6. Fotometría estable en B5/B6 (6.99–7.39 AB, ±0.01–0.04 mag entre pasadas). Se ve el movimiento al norte a ojo |
| ε Indi B | **2–3′** | **6′** | **El mejor test de movimiento**: sin saturar y con S/N de pico 310–420 por imagen. Mantener FOV <13′ para no meter a ε Indi A, que está saturada y a 402.6″ (65.5 px) al oeste |
| WISE 0855 | **2–3′** | **≥6′** | **Solo visible con λ ≥ 3.9 µm (D5/D6)**, filtrando por λ local. S/N por imagen **≈5**; con stack mediano ≈19–23. **En D1–D3 el blob en esa posición es una estrella estática de Gaia** (ver abajo). Hacen falta overlay de catálogo y stack por pasada |
| RW Aur | 3′ (5′ para tener estrellas de comparación) | igual (estática) | 2–3 mag por encima del inicio de no-linealidad en B4–B6, pero sin núcleos NaN. **Variabilidad fuerte en D5/D6** |
| R Dra | 5′ | igual | Núcleo NaN en todas las imágenes: **dibujar NaN como saturado, no como agujero.** Halo enorme. Cadencia mensual, sirve para curva de luz |

**Estrella que contamina a WISE 0855:** Gaia DR3 5756956644387831296 (CatWISE J085501.95−071428.2) en 133.7581825, −7.2411559. G 16.31, W1 15.04, W2 15.20 Vega, μ ≈ 0 (estática).

| Fecha | Separación entre WISE 0855 y la estrella |
|---|---|
| 2025-05 | 11.3″ |
| 2025-11 | 8.0″ |
| 2026-05 | 4.1″ |
| Ago–sep 2026 (mínimo) | **≈3″** (~0.5 px) |
| 2027-05 | 6.0″ |

### 4.4 Validaciones hechas sobre píxeles reales

Range reads de 25 filas desde S3, ajuste gaussiano, conversión TAN-SIP y comparación con lo predicho.

**ε Indi B: el movimiento medido coincide con el predicho**

| Intervalo | Predicho | Medido (reporte) | Medido (verificador independiente) |
|---|---|---|---|
| → 2025-10 | 1.80″ | 1.80″ | 1.77″ |
| → 2026-04 | 4.45″ | 4.36″ | 4.57″ |
| → 2026-09 | 6.31″ | 6.27″ | 6.39″ |

Hay un offset constante de (+0.2″, −0.55″) respecto del fotocentro Gaia propagado. La causa no se conoce: puede ser la órbita Ba/Bb o una diferencia de fotocentro entre IR y banda G.

**Otros resultados**
- **Barnard:** se midieron 6.12″ y 10.07″ contra 5.69″ y 10.23″ predichos.
- **WISE 0855:** se recupera el movimiento con ruido. La afirmación del "sesgo por blend 6.0″ vs 8.0″" **no se reprodujo**; el verificador midió 7.55″ contra 7.99″.
- **RW Aur se desvaneció ~0.75 mag** en B5/B6 entre sep 2025 y sep 2026:
  - D5: 7.92 → 8.07 → 8.65 AB.
  - D6: 7.63 → ~8.0 → 8.38.
  - D1 se **abrillantó** 0.45 mag.
  - Las estrellas de referencia varían 0.01–0.10 mag, así que el cambio es real.
  - En la literatura, RW Aur tiene oscurecimientos aperiódicos de hasta ~5 mag en V (Dodin+2018, Koutoulaki+2019; leído vía búsqueda, sin verificar en la fuente primaria).
- **R Dra:** es una Mira de P ≈ 245–246 d con V 6.7–13.2 (sin verificar; GCVS y AAVSO no estaban accesibles).
  - En SPHEREx solo el **tamaño del núcleo saturado en D3** sigue el brillo (21–24 → 8–14 px NaN).
  - **Lo de "B4 39 px vs 8 px" fue refutado:** comparaba D4 con D5. **Regla: nunca comparar fotometría ni tamaño de núcleo entre detectores; agrupar por detector y por λ local.**
- **Lecciones generales:**
  - Usar **stack mediano**. El stack promedio queda dominado por rayos cósmicos y snowballs, que parecen "movers" falsos.
  - Resamplear con interpolación subpíxel (bilineal o Lanczos). Nearest-neighbour mete ±0.5 px de jitter, que es comparable al movimiento que se busca. Para mostrar en pantalla sí va nearest-neighbour (×8–16, `image-rendering: pixelated`).

---

## 5. Inspiración y herramientas

### 5.1 WiseView (el modelo a seguir)

- Repo: https://github.com/backyardworlds/wiseview. Es de dominio público (Unlicense, en el README), con último commit 2021-09-01 y citable como ASCL 1806.004. Hay un clon local (ver Fuentes).
- **Arquitectura:**
  - El servidor (Flask, y en v3 un Lambda `png-animation`) hace el stretch y devuelve **PNGs pre-renderizados + JSON** con `mjds`, `epochs`, `min/max` y un WCS mínimo (`CRPIX`, `CRVAL`, `NAXIS`).
  - El cliente (jQuery, `flash3.js` de 1355 líneas) blinkea en un `<canvas>` y dibuja los overlays en otro canvas.
  - Cada cambio de slider implica un round-trip.
- **Stretch:**
  - `AsinhStretch(a)`, con un slider de linealidad de 0 a 1.
  - Clip `fixed`, `percent` o `adapt` (Scharr).
  - Filtro de mediana para hot pixels.
  - Invertido por defecto.
- **Controles:**
  - RA/Dec (decimal o sexagesimal), tamaño en arcsec (default 60), banda W1/W2/W1+W2 (color: R=W2, B=W1).
  - Blink de 20–1000 ms (default 500), zoom de 0.5 a 20 (default 9), trim min/max.
  - "Sliding window" en años: el default depende del camino (0, 0.75 o 0.5).
  - Checkboxes: separar por dirección de scan (paralaje), "skip middle epochs" (pre/post), borde punteado en la época 0.
  - **Diferencias** (ventana A − resto B) y **shift-and-add** por pmra/pmdec.
  - Objetos sintéticos para probar detectabilidad.
  - Leyenda de épocas `+ - .`.
  - Click para recentrar. Links a Legacy Survey, SIMBAD y VizieR. Cutout de Pan-STARRS.
- **Estado en el hash de la URL:** `ra, dec, size, band, speed, minbright, maxbright, window, diff_window, linear, zoom, border, gaia, invert, diff, outer_epochs, shift, pmra, pmdec…`. Conviene usar los mismos nombres.
- **Overlay de Gaia (copiar la lógica):**
  - La posición en cada frame es la de Gaia más (MJD del frame − MJD de referencia) × μ. WiseView usa MJD 57204 (2015.5, eDR3); para DR3 hay que usar `ref_epoch` = 2016.0.
  - Radio = max(0.1, ϖ/50) px.
  - Verde si |μα|+|μδ| ≥ 100 mas/año, rojo si no.
  - Una línea desde la primera época hasta la última.

### 5.2 Backyard Worlds, unWISE y unTimely

Datos tomados de búsqueda y memoria (sin verificar):
- Backyard Worlds arrancó en febrero de 2017 (Zooniverse). Los voluntarios miran flip-books de coadds unWISE W1/W2.
- Lo que buscan son **"movers"** (saltan entre frames) y **"dipolos"** (par claro/oscuro en la diferencia). Los artefactos más comunes son ghosts, latents y spikes; en SPHEREx ya vienen codificados en FLAGS.
- Sucesor: "Cool Neighbors" (2023).
- **unWISE time-resolved:** un coadd por pasada de ~6 meses (docs IRSA). unTimely (Meisner+2023, DOI 10.26131/IRSA580) hizo fotometría por época.
- **Lección para SPHEREx: coadd dentro de cada visita y blink entre visitas.**

### 5.3 Herramientas de IRSA para SPHEREx

- **Data Explorer** (https://irsa.ipac.caltech.edu/applications/spherex, Firefly):
  - Búsqueda por posición, tiempo y λ sobre el HiPS más el MOC.
  - Vista en tiles, composición RGB, "drill" por planos del cubo.
  - **Tiene "Auto play" para pasar por las imágenes cargadas.** No reproyecta a una grilla común, no aplica stretch compartido, no coaddea ni diferencia, y no anima por planos del cubo.
- **Spectrophotometry Tool:** fotometría forzada con Tractor.
  - Tarda minutos a horas: horas ≈ 0.000463·N_imágenes + 0.013, con un mínimo de ~5 min.
  - Máximo 20 fuentes por lista y 2 jobs a la vez.
  - **Un espectro rápido calculado por nuestra herramienta en segundos es un diferencial real.**
- **Otras:** Mosaic Tool (solo GUI, sin API), Cutout Tool, MOST, Source Discovery Tool (paquete Python en los tutoriales) y la página del cometa 3I/ATLAS.

### 5.4 Aladin Lite v3 (CDS)

**Versión y paquete**
- `aladin-lite@3.8.2` es la última estable (2026-03-06). El tag `latest` apunta a 3.9.2-beta.
- Un solo ESM de 2.3 MB con la WASM embebida. **Requiere WebGL2.**
- Licencia GPL-3: hay que mantener el logo y el link.
- El `require` apunta a `aladin.umd.cjs`, que **no existe** en el tarball: usar ESM (`import A from 'aladin-lite'` con Vite).
- CDN: `https://aladin.cds.unistra.fr/AladinLite/api/v3/3.8.2/aladin.js` (sin verificar desde el sandbox; el CDS no era alcanzable).

**API confirmada en el bundle**
- `A.init`, `A.aladin`, `gotoRaDec`, `gotoObject` (Sesame), `setFoV`, `pix2world`/`world2pix`, `getShareURL`.
- Eventos: `on('positionChanged'|'click'|...)`.
- Capas: `A.HiPS`, `setBaseImageLayer`, `setOverlayImageLayer`, `setOpacity`, `setColormap`, `setCuts`.
- Catálogos y gráficos: `A.catalogHiPS`, `A.catalogFromVizieR`, `A.catalogFromURL`, `A.graphicOverlay`, `A.vector`, `A.circle`, `A.polyline`.

**⚠ Planos del cubo SPHEREx**
- **`setSliceNumber(n)` y el slider de cubo que trae Aladin muestran planos equivocados.** Por ejemplo, `setSliceNumber(90)` pide el tile `_1` (0.771 µm).
- Usar esto (verificado para k = 1, 20, 50, 90 y 101):
  ```js
  const c=299792458, fmin=c/5.009e-6, fmax=c/7.43e-7;
  layer.setFrequency({value: fmin + (k+0.5)/102*(fmax-fmin)});   // muestra el frame k
  // λ física del frame k = data_cube_crval3_arr[k] (k=90 -> 4.600 µm)
  ```
- El frame 0 no se puede mostrar: Aladin pide `_0` e IRSA lo sirve sin sufijo.
- Hay que ocultar el slider nativo.
- En swiftshader el render salió en blanco, así que esto no está verificado visualmente.

**⚠ `A.image()` con FITS crudo de SPHEREx**
- Abre la primera extensión de imagen, pero **el header TAN-SIP la ubica muy mal**: RA 163.75, Dec +79.70 en vez de 133.79, −7.25.
- Sacando las keys `A_*`/`B_*`/`AP_*`/`BP_*` y el sufijo `-SIP` queda bien. Una grilla TAN norte-arriba reproyectada cae exacta.
- **Hay que reproyectar a TAN, o al menos quitar SIP, antes de pasarle nada a Aladin.**
- Evitar `displayJPG`/`displayPNG`: mandan la URL a un servicio externo del CDS (`fits2HiPS`).

**Catálogos**
- Gaia DR3 por HiPS: `https://axel.cds.unistra.fr/HiPSCatService/I/355/gaiadr3`.
- VizieR: `I/355/gaiadr3`, `II/328/allwise`, `II/365/catwise`, `II/246/out`. Los IDs y el CORS de VizieR y del CDS están sin verificar.
- HiPS por defecto útiles: `CDS/P/allWISE/color`, `CDS/P/2MASS/color`, PanSTARRS DR1.

**Uso recomendado:** como **panel de contexto sincronizado** (HiPS SPHEREx, AllWISE y catálogos). El blink va en un canvas propio, como hace WiseView.

### 5.5 Librerías

| Librería | Versión | Uso / veredicto |
|---|---|---|
| **astropy** | 8.0.2 | WCS SIP, MEF, `visualization` (ZScale, Percentile, AsinhStretch, `make_lupton_rgb`), `apply_space_motion` |
| **reproject** | 0.21.0 | `reproject_interp` a TAN norte-arriba |
| astroquery / pyvo | – | `Irsa.query_sia`, `SIA2Service`, TAP |
| fsspec (+ aiohttp) | – | `fits.open(url, use_fsspec=True)` + `.section` (Range reads); `block_size` de ~1 MiB |
| photutils, sep | – | fotometría por apertura y fondo |
| numpy, Pillow, imageio | imageio 2.38.1 | PNG y GIF |
| spxquery | 0.4.1 | curvas de luz SPHEREx (github.com/WenkeRen/spxquery) |
| firefly-client | 3.4.0 | Firefly desde Python |
| fitsjs | 0.6.6 | viejo (2022); solo HDU primaria |
| jsfitsio | 3.1.0 | mantenida; sin reproyección SIP |
| fitsjs-ng | 1.0.2 | nueva (FITS/XISF) |
| JS9 | 3.9.0 | demasiado para 48 h (dicen que tiene blink, sin verificar) |
| OpenSeadragon | 6.1.1 | no es astronómica; no hace falta |
| Plotly / Chart.js | – | espectro y curva de luz |

### 5.6 Notebooks tutoriales de IRSA

Están en https://caltech-ipac.github.io/irsa-tutorials/spherex/ y en raw.githubusercontent `Caltech-IPAC/irsa-tutorials/main/tutorials/spherex/`.

1. `spherex_intro.md`: SIA con astroquery, recorrido del MEF, WCS espacial, λ con `key='W'` y `sip=None`, nombres de flags.
2. `spherex_cutouts.md`: TAP con URLs de cutout, descarga en paralelo (10 workers) y empaquetado en un MEF.
3. `spherex_psf.md`: zonas EPSF y mapeo de cutout a imagen padre (`x_orig = 1 + x_cut − CRPIX1A`).
4. `spherex_source_discovery_tool_demo.md`: lectura directa de S3, conversión MJy/sr → µJy, `sep`, reproyección D2→D4 e imagen diferencia. **El patrón se puede reutilizar para diferencias entre épocas.**
5. `spherex_mosaic.md`: cubo del Mosaic Tool (M101) y mapa de PAH 3.3 µm.
6. `spherex_hipscube.md`: HiPS cube en Firefly y descarga de un tile FITS por `ipix` (`hpgeom.angle_to_pixel(2**5, ra, dec, nest=True, lonlat=True)`).

### 5.7 Técnicas de visualización a implementar

- **Fondo:** restar ZODI (HDU) o una mediana local con sigma-clipping por frame. El zodiacal cambia mucho entre visitas y entre detectores.
- **Normalización única para todos los frames** (ZScale o percentil 0.5–99.5 + asinh). El autoscale por frame hace "respirar" el fondo.
- **Agrupar:**
  - Por visita (gap de ~10 días) × detector, con stack mediano o con media pesada por varianza (VARIANCE).
  - Opción "mismo canal o λ entre años" (Survey 1 vs 3, Survey 2 vs 4) para la variabilidad.
- **Diferencias:** última − primera, visita − resto (A−B estilo WiseView) y running diff. Escala divergente centrada en 0 (los dipolos delatan movimiento).
- **Shift-and-add** con un μ ingresado por el usuario.
- **Crosshair** en la posición predicha y overlay de Gaia/CatWISE propagado al MJD de cada frame, con vectores de μ.
- **Filtro por λ local** (no por `BAND`). Etiquetar cada frame con su λ en el objetivo.
- **Falso color:** detectores en RGB, por ejemplo D1/D3/D6. Las enanas marrones deberían verse rojas, brillantes ~4.5 µm y con absorción de CH₄ (sin verificar como regla general; es consistente con que WISE 0855 solo se detecta en D5/D6).
- **Espectro on-the-fly (extra kudos):**
  - De los mismos frames ya bajados: flujo por apertura en el píxel propagado menos el fondo, más λ y Δλ de WCS-WAVE.
  - Salen ~100–460 muestras (λ, flujo, mjd, det, flags) de 0.75 a 5 µm en segundos.
  - Mostrar flujo vs λ coloreado por visita, y una curva de luz en un bin estrecho de λ.
- **Overlay de FLAGS por grupos** (artefactos y malos), más el % flageado en el objetivo para cada frame.
- **Badge "saturado"** donde haya NaN.

---

## 6. Arquitecturas candidatas para 48 h

| | **A. FastAPI + canvas + Aladin** | **B. Streamlit monolítico** | **C. Estático + proxy mínimo + S3 directo desde el navegador** |
|---|---|---|---|
| Búsqueda | Backend: SIA (VOTable) / TAP | Python directo | Proxy (Cloudflare Worker o Vercel) solo para `/SIA` |
| Píxeles | Backend: S3 Range → `reproject_interp` a TAN → coadd/diff → **mini-cubo float32** (30 frames × 61² × 4 B ≈ 446 KB) | Python, y sale un GIF | El navegador hace Range a S3, parsea el header y aplica TAN-SIP en JS (prototipo validado a 2.4e-7 px) |
| Stretch, blink, diff | En el cliente sobre TypedArrays: los sliders responden al instante | Re-ejecuta el script entero; la animación es un GIF | En el cliente |
| Flags RICE | astropy, sin esfuerzo | astropy | **Falta un decoder RICE en JS** (no implementado) |
| Gaia / overlays | TAP con cache en el backend | TAP | Proxy, o catálogos del CDS en Aladin (sin verificar) |
| Espectro | Fácil (astropy) | Fácil | Hay que reimplementarlo en JS |
| Hosting | Front estático + backend Python (lo más incierto) | Streamlit Community Cloud (límites sin verificar) | Solo front estático + Worker: lo más barato y escalable |
| Pros | Astrometría correcta, rápido, UX pulida, URL embebible, reutiliza los notebooks | MVP en 4–8 h, un solo lenguaje | Escala gratis y casi sin servidor; la vía de píxeles ya está probada en JS |
| Contras | Dos codebases y un backend que hostear | Poco interactivo, mal para embeber, menos "herramienta pública" | Reimplementar SIP, resampleo bilineal, RICE y coadds en JS; más riesgo en 48 h |

**Recomendación**
- **A como camino principal**, con un **núcleo Python reutilizable** (`spherex_core.py`: SIA → S3 Range → TAN → coadd → cubo/PNG), que es lo que validaron los prototipos.
- **B** solo si el equipo es muy Python y quiere una red de seguridad en las primeras ~12 h, importando el mismo núcleo.
- **C** como plan alternativo **si el hosting del backend se complica** (el prototipo JS existe), o como optimización posterior.
- En cualquier caso:
  - **Fallback precomputado** de los 5 objetivos (frames y cubos en JSON/bin), regenerado el día de la demo.
  - **IBE cutouts fuera del camino de la demo** (por los 503).

**API sugerida para A** (es una propuesta de diseño, no está implementada):
```
GET /api/frames?ra&dec&fov&dets=5,6&group=visit|frame&coadd=median|ivar&pm=auto|<pmra>,<pmdec>&lam_min&lam_max&deep=0
 -> { wcs:{TAN norte-arriba}, shape:[nf,ny,nx], cube:"/api/cube/<hash>.f32",
      frames:[{mjd_min,mjd_max,n,dets,lam_at_target,flag_frac,collection,obs_ids}],
      target_track:[{mjd,ra,dec}], gaia:[{ra,dec,pmra,pmdec,plx,g}] }
GET /api/spectrum?ra&dec&pm=auto -> [{lam,bw,flux,err,mjd,det,flags}]
GET /api/gif?...                 -> para compartir
```
- Cache LRU o en disco por (obs_id, ra, dec, size).
- ThreadPool de 6–16 workers para S3.
- Colecciones en config, o descubiertas por TAP.
- Estado de la UI en la URL (`?ra=&dec=&fov=&det=&mode=&speed=&zoom=&stretch=`, con nombres compatibles con WiseView).

**Hosting** (todo sin verificar)
- Front: GitHub Pages, Cloudflare Pages o Vercel.
- Backend: Render free. Según búsqueda, duerme a los ~15 min con cold starts de 30–60 s. Hay que confirmar también si HF Spaces, Fly o Railway siguen siendo gratis para cuentas nuevas.
- Plan C de demo: uvicorn en una laptop expuesto con Cloudflare Tunnel.
- El host del backend tiene que poder llegar a irsa.ipac.caltech.edu y a S3.

**Plan orientativo de 48 h**

| Horas | Tarea |
|---|---|
| 0–4 | Núcleo Python: SIA → filtro → Range de S3 → TAN bilineal → stack mediano por visita → PNG. Validar con **ε Indi B** |
| 4–12 | FastAPI `/api/frames` (mini-cubo), cache y precomputado de los 5 objetivos |
| 8–20 | Canvas: blink, velocidad, zoom pixelated, stretch común, invertir, modos de diferencia, estado en la URL |
| 20–30 | Propagación de μ (Gaia TAP con cache) + crosshair y vectores; filtro por λ local; selector de detector y RGB |
| 30–38 | Espectro y curva de luz (Plotly), overlay de FLAGS, panel Aladin sincronizado |
| 38–44 | Deploy, pruebas con los 5 objetivos, regenerar listas |
| 44–48 | Demo, video, README |

---

## 7. Riesgos y preguntas abiertas

**Riesgos técnicos**
1. **La señal es muy chica:** 0.4–1.7 px/año con una PSF submuestreada (~1.2 px). Sin propagación de μ, resampleo subpíxel, stacks y diferencias, "no se ve nada".
2. **Coordenadas viejas.** Con J2000 o con las coords del enunciado, Barnard y WISE 0855 quedan fuera de una caja de 3–4′. Hay que propagar o usar un FOV grande por defecto (≥6′, y ≥12′ para Barnard).
3. **El LVF engaña:** cambios de brillo por λ y, para WISE 0855, una estrella estática en D1–D3. Filtrar por λ local y avisar en la UI.
4. **Orientación:** roll distinto por frame y ~180° entre visitas. Siempre reproyectar a norte-arriba.
5. **IBE inestable:** 36% de 503. No depender de los cutouts.
6. **Campos deep:** R Dra tiene 2493 frames (~1.4 GB a 5′ si se baja todo). Por defecto, stacks por visita y detector, carga perezosa y colecciones deep apagadas.
7. **Datos que cambian:** los archivos se reescriben (Last-Modified 2026-11-11), los directorios dependen de la versión y QR3 sale semanalmente. No cachear la cobertura por mucho tiempo.
8. **TAP lento** (Gaia 13–30 s, CatWISE hasta 24 s): cachear y precomputar para los objetivos.
9. **Aladin:** `setSliceNumber` roto, SIP mal ubicado, frame 0 inaccesible, render no verificado visualmente.
10. **Hosting gratuito incierto** (sin verificar). Tener un plan con laptop + túnel.
11. **Throughput de S3** medido desde un contenedor en la nube. Desde la red del equipo, fuera de EE.UU., no se midió (sin verificar).
12. **Competencia fuerte** (173+ repos). Diferenciarse con alineado, coadd, diferencias, μ, λ local y espectro.

**Preguntas abiertas**
- ¿Por qué no hay batches QR3 desde el 2026-10-29? Re-chequear `MAX(obs_release_date)` durante el hackatón.
- ¿Cuándo entra la pasada S3/S4 de WISE 0855 a QR3? Hoy hay 0 filas.
- ¿El cutout de IBE acepta algún parámetro para omitir la EPSF? No está documentado.
- ¿Los listados de IBE (404) son temporales?
- ¿Decodificar RICE en JS (para C) o traer FLAGS desde el backend?
- ¿Qué proxy usar (Worker, Vercel o FastAPI) y conviene recortar o comprimir las respuestas de SIA (567 KB para WISE 0855, 5.2 MB para R Dra)?
- ¿Cuál es el origen del offset (+0.2″, −0.55″) de ε Indi B: órbita, fotocentro IR o sistemática?
- ¿Cuál es la fase actual de la Mira R Dra? (P y amplitud sin verificar en GCVS/AAVSO.)
- ¿Qué astrometría usar para WISE 0855? Kirkpatrick+2021 viene de fuente secundaria; el ajuste propio coincide dentro de ~2σ.
- ¿Conviene usar los bits OVERFLOW/NONLINEAR para dibujar los núcleos saturados en vez de NaN?
- ¿Se mantienen estables la config CORS de S3 y los offsets de header en futuros releases? Seguir parseando, no hardcodear.
- ¿Funciona en la práctica el HiPS deep-field del CDS (`alasky.cds.unistra.fr/SPHEREx/D1–D3`)? (Sin verificar.)

---

## 8. Fuentes

**Desafío**
- https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=details

**IRSA / SPHEREx: documentación**
- https://irsa.ipac.caltech.edu/Missions/spherex.html
- https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html
- https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html
- https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-releases
- https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-access
- https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html
- https://irsa.ipac.caltech.edu/ibe/cutouts.html
- https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html
- https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/visualization.html
- https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/searching.html
- https://irsa.ipac.caltech.edu/cloud_access/
- Explanatory Supplement v2.1 (2026-11-10): copia local en `recon/expsupp.txt`

**IRSA / SPHEREx: servicios y datos**
- https://irsa.ipac.caltech.edu/applications/spherex
- https://irsa.ipac.caltech.edu/SIA (+ `/SIA/capabilities`)
- https://irsa.ipac.caltech.edu/TAP/sync
- https://irsa.ipac.caltech.edu/cgi-bin/MOST/nph-most
- https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/index.html
- https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube/properties
- https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html
- https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/obscore_3I_Atlas.vot
- https://irsa.ipac.caltech.edu/data/SPHEREx/docs/spectral_files_20260812/SPHERExSpectralFiles_202607.tar
- https://irsa.ipac.caltech.edu/data/demos/notebooks/spherex/M101_irsa.fits

**Tutoriales**
- https://caltech-ipac.github.io/irsa-tutorials/spherex/
- https://raw.githubusercontent.com/Caltech-IPAC/irsa-tutorials/main/tutorials/spherex/spherex_intro.md (también `spherex_cutouts.md`, `spherex_psf.md`, `spherex_source_discovery_tool_demo.md`, `spherex_mosaic.md`, `spherex_hipscube.md`)

**Inspiración y herramientas**
- http://byw.tools/wiseview y https://github.com/backyardworlds/wiseview
- https://www.zooniverse.org/projects/marckuchner/backyard-worlds-planet-9/about
- https://en.wikipedia.org/wiki/Backyard_Worlds
- https://blog.backyardworlds.org/2017/09/13/wiseview/ (no accesible desde el sandbox)
- https://irsa.ipac.caltech.edu/data/WISE/unWISE/overview.html
- https://www.ipac.caltech.edu/doi/10.26131/IRSA580
- https://arxiv.org/abs/2209.14327
- https://github.com/cds-astro/aladin-lite, https://cds-astro.github.io/aladin-lite, npm `aladin-lite@3.8.2`
- https://github.com/WenkeRen/spxquery (PyPI `spxquery`)
- https://archive.stsci.edu/missions-and-data/gaia (recurso Gaia del desafío; acá se usó IRSA TAP `gaia_dr3_source`)

**Ciencia de los objetivos**
- https://arxiv.org/pdf/1605.06655 (Luhman & Esplin 2016)
- https://en.wikipedia.org/wiki/WISE_0855%E2%88%920714 (valores de Kirkpatrick+2021; fuente secundaria)
- https://arxiv.org/html/2505.12105v2
- https://arxiv.org/abs/1811.00449 (Dodin+2018)
- https://arxiv.org/pdf/1610.08303
- https://air.unimi.it/retrieve/handle/2434/866602/1865361/Koutolaki2019.pdf
- https://britastro.org/vss/obj-dra.html
- https://en.wikipedia.org/wiki/Mira_variable

**Hosting** (terceros, sin verificar)
- https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026
- https://flaviocopes.com/hosting-free-tiers/
- https://snapdeploy.dev/state-of-free-hosting

**Artefactos locales del relevamiento**

Todo está bajo `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/`:
- Prototipo de acceso: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/access/` (`07_browser_range_cutout.mjs` es el prototipo JS de Range+WCS; `03_range_cutout.py`, `05_targets.py`, salidas en `out/`)
- Prototipo de flip-book en Python: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/scripts/flipbook_proto.py` (GIF en `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/out/w0855/flipbook.gif`)
- Astrometría y cobertura de objetivos: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/targets/` (`positions_2026.json`, `propagation.json`, `09_measure_motion.py`, `motion_*.png`)
- Clon de WiseView: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/clones/wiseview/`
- Bundle de Aladin y tests en navegador: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/npm_aladin/package/dist/aladin.js`, `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/verify_fe/`
- Fuentes de los notebooks: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/nb/`
- Explanatory Supplement en texto: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/expsupp.txt`
- Venv con astropy, reproject y fsspec: `/tmp/claude-0/-home-user-Hackaton-NASA/26d3ce61-5800-5d8e-8c79-9d3765b423ef/scratchpad/recon/venv`
