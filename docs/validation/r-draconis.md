# Validación: R Draconis

> **Vigencia (2026-11-14).** Se analizó el build de integración (main `9b8ba42` + `ws2/season-compare`, 18:43 UTC). El campo publicado en `main` por #17 (18:54 UTC) tiene **los mismos 40 frames y PNG idénticos bit a bit** (md5), así que este registro vale para el campo publicado. Única diferencia: #17 ya publica `wavelength_um`/`bandwidth_um` en el centro del campo en los 40 frames, así que lo que abajo se dice de «λ nula en `field.json`» quedó resuelto en el producto. Sigue abierto que la *selección* de frames no ordena por λ: las filas SIA no traen λ y la selección de #17 es idéntica.
>
> Los scripts y la caché del análisis quedaron en el scratch local de la sesión de Claude y no se versionan («scratch local» abajo). Las figuras sí están en el repo, en [`figures/r-draconis/`](figures/r-draconis/). Revisión humana pendiente.

**Resultado: `success`, en el alcance que se indica.** R Draconis (Mira, Gaia DR3 1648328016354496384) está saturada (bit `OVERFLOW` en el núcleo) en el **100 %** de los 2488 frames SPHEREx donde cae dentro del detector, sobre un total de 2493 entre dr1, qr3, dr1_deep y qr3_deep (MJD 60790–61310, 520 d). `NONLINEAR` no aparece nunca. Por eso no hay fotometría de núcleo posible. Medí su brillo **relativo** en el ala no saturada de la PSF, comparando solo frames del **mismo detector y con λ dentro de bins de 1–1,5 %**:
- **Análisis original:** anillo de 10–16 px menos 45–60 px.
- **Revisión independiente:** anillo de 12–20 px, fuera de `BLOOM`, menos 40–55 px.

La variabilidad es clara y significativa:
- amplitud pico a pico de 0,5–1,3 mag según el detector;
- p ≤ 0,003 en una prueba de permutación por visitas en los seis detectores, aunque D2 queda en el límite;
- el cociente entre anillos es estable;
- el tamaño del núcleo saturado varía con el ala;
- las estrellas de comparación varían ≤ 0,07 mag.

Además, la serie SPHEREx **sigue a la curva V contemporánea de AAVSO** (818 observaciones, máximos V en MJD 60811,4, 61046,5 y 61304,3). El retraso va de −1 d en D1 a +47 d en D4. El período efectivo de SPHEREx, ~260 d (bootstrap 95 %: 255–265 d), coincide con la duración del último ciclo observado por AAVSO (258 d; el anterior fue de 235 d) y es compatible con Gaia DR3 (247,2 ± 6,0 d). **Límite:** la medición es un análisis offline del FITS. El campo publicado (40 PNG) no la reproduce: `wavelength_um` es nulo y el núcleo saturado está rellenado solo para mostrarlo.

## Registro (plantilla de VALIDATION.md)

- Target / resolved catalog ID: R Draconis = `V* R Dra`.
  - SIMBAD vía Sesame CfA: oid 376084, otype `Mi*`.
  - ✅ Gaia DR3 1648328016354496384: G = 6,37, `phot_variable_flag` = VARIABLE (archivo Gaia de ESA, TAP, 2026-11-14).
  - ✅ Gaia DR3 LPV (`vari_long_period_variable`): frequency 0,0040452 ± 0,0000982 d⁻¹, es decir, **P = 247,2 ± 6,0 d**; amplitud G de 1,38 mag.
  - AAVSO VSX: OID 13673, AUID 000-BBX-660, tipo M, P = 246,12 d, época de máximo JD 2457370, V entre 6,7 y 13,2.
  - Magnitudes (SIMBAD, una sola época): J 3,71, H 3,125, K 2,23 (análisis original, no reconsultadas).
  - ✅ No hay mezcla de fuentes: dentro de 45″ solo hay dos fuentes Gaia de G = 19,2 y 19,4 a 4,1–4,3″. La vecina más cercana con G < 15 está a 92″.
- Astrometry source URL / reference epoch / propagation:
  - Fuente: Sesame CfA (https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxpF/SNV?R%20Dra).
  - J2000.0: 248.16761083 +66.75497942; pmRA* −20,643 y pmDE +6,149 mas/año; plx 1,2509 mas.
  - ✅ Coincide con Gaia DR3 (época 2016.0: 248.16737837 +66.75500675, archivo de ESA) a unos 3 mas.
  - Propagación lineal hasta el `MJD-AVG` de cada frame (en la revisión, desde la época 2016.0 de Gaia). Paralaje ignorada (≤ 1,25 mas).
  - 🧮 Posición predicha por temporada de campo amplio: MJD 60845,9 → 248.16724083 +66.75502292; 61006,1 → 248.16723446 +66.75502367; 61198,9 → 248.16722679 +66.75502457.
  - 🧮 MJD medio de todos los datos, 61114,6 → 248.16723014 +66.75502417. Está a unos 15 mas del centro de `fields.toml` (248.16723, 66.75502).
  - Movimiento total en 520 d: 30,7 mas = 0,005 px. Es despreciable.
- Query RA, Dec / FOV / query date:
  - Búsqueda puntual en 248.16723, +66.75502.
  - Campo amplio (`spherex_dr1` + `spherex_qr3`): SIA2 del build en caché (2026-11-14 18:42:44 UTC; `data/cache/queries/search_72a24d6dfc48e6b380a2d6717d868582.json`).
  - Campos profundos: SIA2 en vivo hacia las 18:47 UTC.
  - ✅ Revisión: SIA2 en vivo propio de las 4 colecciones (r = 1″, VOTable, MAXREC 20000), el 2026-11-14 hacia las 19:25 UTC, 2,9–8,1 s por colección, sin overflow.
  - FOV: patches por Range de S3 de 13,5′ (132×132 px a 6,15″), los mismos del build. Grilla del producto: 0,15° (88×88 px).
- SPHEREx releases / observation IDs / MJDs / detectors / wavelengths:
  - ✅ **2493 frames**: dr1 413, qr3 126, dr1_deep 1225, qr3_deep 729. Sin duplicados entre colecciones; los 2493 están en la caché.
  - Por detector: D1 584, D2 89, D3 574, D4 584, D5 89, D6 573. Los campos profundos solo tienen D1/D3/D4/D6.
  - Campo amplio: 539 frames, 87 visitas (más de 6 h). Temporadas con huecos de más de 30 d:
    - MJD 60812,0–60878,6: 153 frames.
    - MJD 60965,6–61053,4: 212 frames.
    - MJD 61152,3–61237,9: 174 frames.
  - Campos profundos:
    - dr1_deep: 60789,9–60803,4 (87; D3/D6), 60916,4–60987,6 (260; D1/D4) y 61079,5–61166,5 (878; D3/D6).
    - qr3_deep: 61232,0–61310,3 (729; D1/D4).
  - ✅ λ en R Dra (WCS-WAVE con `key="W"` y `sip=None`, igual que `fits_io.wavelength_at` a 1e-15 µm):
    - D1: 0,735–1,122 µm, Δλ 0,024.
    - D2: 1,093–1,659 µm, Δλ 0,032.
    - D3: 1,619–2,422 µm, Δλ 0,047.
    - D4: 2,404–3,838 µm, Δλ 0,091.
    - D5: 3,811–4,430 µm, Δλ 0,037.
    - D6: 4,407–5,012 µm, Δλ 0,036.
  - **40 frames del build**, por temporada del build:
    - 0: `2025W23_1C_0021_{1D3,1D6,2D3}`, `2025W25_2A_0633_{2D2,2D5,3D2,3D5}`, `2025W27_2A_0243_{1D1,1D4}`, `2025W27_2A_0331_1D1`, `2025W27_2A_0557_1D4`
    - 1: `2025W29_2A_0351_{1D1,1D4}`, `2025W29_2A_0805_{1D1,1D4}`
    - 2: `2025W45_1A_0067_{1D1,1D4,2D1,2D4}`, `2025W49_1A_0280_{1D2,1D5,2D2,2D5}`
    - 3: `2026W01_2A_0426_{2D3,3D3,3D6}`
    - 4: `2026W20_2A_0294_{4D3,4D6}`, `2026W25_2A_0573_{2D2,2D5,3D2,3D5}`
    - 5: `2026W26_1A_0047_{1D2,1D5,2D2,2D5}`, `2026W28_2A_0376_{2D1,2D4,3D1,3D4}`
    - Son 26 dr1 y 14 qr3, 22 obs_id y 14 visitas. Ninguno es deep.
- Useful epochs / time baseline / coverage and quality flags:
  - Hay 249 visitas en 520 d, unos 2,1 ciclos.
  - Fotometría de la revisión, en el anillo de 12–20 px:
    - Quedan fuera 5 frames donde R Dra cae fuera del array (entre 0,0 y 6,3 px más allá del borde) y los frames cuyo anillo no está completo en el patch.
    - Se descartan los frames en bins de λ que abarcan menos de 30 d.
    - Quedan D1 569, D2 52, D3 559, D4 566, D5 79 y D6 559 frames.
  - Flags en el núcleo (r ≤ 2 px) de los 40 frames del build: `OVERFLOW`, `SUR_ERROR`, `SOURCE` y `BLOOM` en 40/40; `TRANSIENT` en 20; `NONFUNC` en 3; `DICHROIC` en 1; `HOT` en 1.
  - Radio máximo de `BLOOM`: D1 2,7–8,3, D2 4,1–7,3, D3 5,6–8,5, D4 4,7–9,8, D5 6,0–7,5 y D6 5,3–5,9 px.
  - ✅ **Saturados: 2488 de 2488.** Píxeles `OVERFLOW` con r ≤ 5 px: mínimo 1, mediana 21, máximo 61. Píxeles `NONLINEAR`: 0.
- Alignment check / photometry or astrometry method / uncertainties:
  - **Alineación**, remedida por la revisión en **todos** los frames:
    - Centroide gaussiano de 6 estrellas Gaia DR3 (G 12,5–14,0, RUWE < 1,4) frente a sus posiciones propagadas: 8890 medidas en 2481 frames.
    - Offset mediano (−0,019, +0,004) px. Desviación robusta (0,060, 0,068) px. Rms de la mediana por frame (0,058, 0,058) px, es decir, unos 0,36″.
    - Sin deriva entre bloques (≤ 0,03 px).
    - El análisis original obtuvo valores compatibles con 40 frames: (0,065, 0,077) y (0,049, 0,052) px.
  - **Posición de R Dra**, centro geométrico del núcleo OVERFLOW frente a la predicción (2486 frames):
    - Mediana (−0,007, +0,104) px.
    - |r| medio 0,25 px, percentil 95 0,57 px, máximo 1,90 px. En los 40 frames del build el máximo es 0,59 px.
  - **Fotometría:**
    - Ala de la PSF en `IMAGE − ZODI` (MJy/sr), restando un anillo lejano.
    - Revisión: media recortada al 20 % en 12–20 px, con máscara `DEFAULT_BAD` + `BLOOM` + `NONLINEAR` + `TRANSIENT` + `OUTLIER`, menos la mediana de 40–55 px. Análisis original: mediana con sigma-clip en 10–16 px menos 45–60 px.
    - Modelo por detector: m = constante por bin de λ + señal temporal. La señal es una sinusoide con P libre o fijo en 247 d, o bien la curva V de AAVSO escalada por k con un retraso, o bien bloques libres de 15 o 30 d.
    - Mínimos cuadrados ponderados con un piso sistemático tal que χ²/dof = 1. El piso en mag es 0,28 / 0,37 / 0,38 / 0,14 / 0,09 / 0,08 (D1…D6).
  - **Incertidumbres:**
    - Bootstrap por visitas para el período.
    - Permutación de las épocas de visita (300 réplicas) para la significancia.
    - Las incertidumbres de período, fase y retraso son estadísticas: no incluyen el error de modelo.
  - **Revisión independiente:** con código propio, sin reutilizar los scripts originales, se remidieron:
    - la cobertura (SIA2 en vivo);
    - la identidad y la astrometría (archivo Gaia de ESA);
    - la saturación y los flags;
    - la λ;
    - la alineación en todos los frames;
    - la fotometría con otro anillo, otra máscara y otros bins;
    - el período, la permutación y la curva AAVSO contemporánea;
    - los controles;
    - los 40 frames y los PNG del build;
    - `compare`, reejecutado sobre una copia.
- Expected behavior / observed behavior:
  - **Esperado:**
    - Mira con P ≈ 246–247 d (VSX 246,12 d; ✅ Gaia DR3 247,2 ± 6,0 d).
    - V entre 6,7 y 13,2.
    - En el infrarrojo cercano, una amplitud menor que en V (❓ expectativa, no verificada con catálogo).
    - Movimiento ≈ 0 px.
  - **Observado:**
    - Variación periódica en los seis detectores, en fase con la V de AAVSO contemporánea.
    - Ala de la PSF, amplitud pico a pico con P = 247 d (revisión): D1 1,19±0,04, D2 0,96±0,34, D3 1,29±0,08, D4 0,51±0,03, D5 0,62±0,03, D6 0,80±0,01 mag.
    - El análisis original obtuvo 1,22 / 0,78 / 1,30 / 0,53 / 0,60 / 0,78. La dispersión por método es ≤ 0,15 mag, salvo en D2 (0,56–0,96).
    - Retraso respecto de la V de AAVSO: D1 −1 d, D2 +24, D3 +21, D4 +47, D5 +33, D6 +15 d.
    - Período efectivo: 260 d.
    - Movimiento: núcleo centrado en la predicción, consistente con ≈ 0.
- Result: **success**.
  - Variabilidad periódica de una Mira detectada con flujos FITS de SPHEREx a λ compatible.
  - La sostienen tres cosas: permutaciones (p ≤ 0,003), controles y consistencia entre anillos, y la coincidencia de fase con la curva AAVSO contemporánea.
  - Alcance:
    - Es fotometría relativa del ala de la PSF: el núcleo está saturado en todos los frames.
    - Es análisis offline: no está en el producto ni en la UI.
    - El blink publicado (40 PNG con λ distinta) **no** demuestra la variabilidad.
- Limitations and failed downloads:
  - **Descargas fallidas: 0.** Los 2493 patches están en la caché (verificado). Las duraciones de descarga (304 s y 496 s) son del análisis original y no se remidieron.
  - Hay 3 patches del build recortados por el borde del detector:
    - `2025W27_2A_0331_1D1` (75×132, R Dra a 9,5 px del borde);
    - `2025W45_1A_0067_1D1` (75×132, 9,1 px);
    - `2025W45_1A_0067_1D4` (87×131, 21,4 px).
  - El método supone que la fracción de ala depende solo de λ y del detector. Lo apoya que el cociente entre los anillos de 8–12 y 12–20 px varíe ≤ 0,07 mag (0,12±0,05 en D2). La posición en el plano focal no está modelada (❓ INFERIDO menor).
  - El control con el ala de la estrella de G = 8,1 **no es un nulo limpio**:
    - Da 0,03–0,21 mag en el anillo de 4–8 px y hasta 0,55 mag en el de 8–12 px.
    - Su ala vale 0,005–0,13 MJy/sr, entre 20 y 200 veces menos que la de R Dra, y recibe luz del halo de R Dra (correlación +0,28 en D4).
    - Acota la variabilidad espuria del método en ~0,1–0,2 mag para alas débiles.
  - D3 tiene el piso residual más grande (0,38 mag). Su curva de 30 d llega a +1,7 mag con solo 4 frames: la amplitud de D3 es la menos confiable.
  - D2 y D5 solo tienen 89 frames, sin campos profundos. D2 es marginal: Δχ² 23 contra un máximo nulo de 19.
  - El periodograma de SPHEREx solo tiene un alias fuerte en 144 d (Δχ² 4308, frente a 5717 en 260 d). La fase la confirma AAVSO.
  - La efeméride VSX extrapolada se desvía −4, −15 y −3 d de los máximos V observados. Para validar la fase conviene usar la curva AAVSO contemporánea, no la efeméride.
  - Los máximos AAVSO salen de parábolas de ±40 d sobre estimaciones visuales y V. Su error formal es de 0,5–0,8 d, y el real es mayor (❓ INFERIDO: unos pocos días).
  - GCVS y 2MASS no pudieron consultarse: VizieR CfA seguía caído a las 19:23 UTC.
- **Product field ID / public URL / screenshot or animation:**
  - Field ID: `r-draconis` (`data/products/fields/r-draconis/`). URL pública: pendiente del deploy (WS4).
  - Recorrido revisado solo en la vista local `/?dataset=real#/field/r-draconis` (paso 6 de VALIDATION.md pendiente en la URL pública).
  - Figuras (gráficos generados con código a partir de los FITS reales de SPHEREx):
    - [fig_lightcurve_all.png](figures/r-draconis/fig_lightcurve_all.png): Curva de luz del ala de la PSF por detector (todas las colecciones, incluidas deep)
    - [fig_periodogram_all.png](figures/r-draconis/fig_periodogram_all.png): Periodograma (todas las colecciones)
    - [fig_lightcurve_wide.png](figures/r-draconis/fig_lightcurve_wide.png): Curva de luz solo con dr1/qr3
    - [fig_periodogram_wide.png](figures/r-draconis/fig_periodogram_wide.png): Periodograma solo con dr1/qr3
    - [fig_cutouts_D1.png](figures/r-draconis/fig_cutouts_D1.png): Cutouts D1
    - [fig_cutouts_D2.png](figures/r-draconis/fig_cutouts_D2.png): Cutouts D2
    - [fig_cutouts_D3.png](figures/r-draconis/fig_cutouts_D3.png): Cutouts D3
    - [fig_cutouts_D6.png](figures/r-draconis/fig_cutouts_D6.png): Cutouts D6
    - [fig_png_build_D2_D6.png](figures/r-draconis/fig_png_build_D2_D6.png): PNG publicados D2–D6 (núcleo saturado)
    - [fig_review_lightcurve.png](figures/r-draconis/fig_review_lightcurve.png): Revisión: curva por detector con la V de AAVSO superpuesta
    - [fig_review_periodogram.png](figures/r-draconis/fig_review_periodogram.png): Revisión: periodograma
    - [fig_review_cutouts.png](figures/r-draconis/fig_review_cutouts.png): Revisión: posición predicha y píxeles OVERFLOW en D1 y D6 a λ fija

- Reviewer / date: Claude (WS1) con revisión adversarial independiente / 2026-11-14; revisión humana pendiente

## Detalle de la medición

### 1. Identidad y astrometría

✅ Sesame CfA y Gaia DR3 (archivo de ESA) coinciden a unos 3 mas.

🧮 La posición de cada frame es la de Gaia más el pm hasta su `MJD-AVG`. El píxel sale de la WCS de astropy, con SIP. La época media de todos los frames es MJD 61114,6; la del build, MJD 61022,9. En las dos, la diferencia con `fields.toml` es menor de 15 mas.

La alineación es de unos 0,06 px por eje en todos los frames. El núcleo saturado está a 0,25 px de media de la posición predicha.

### 2. Cobertura y frames del build

El build es reproducible: `select_frames` sobre la búsqueda en caché devuelve exactamente los 40 ids de `field.json`.

Cómo agrupa el build:
- Usa 6 «temporadas» de ≤ 60 d: 60812,0–60870,7 (133), 60873,4–60878,6 (20), 60965,6–61023,7 (164), 61035,2–61053,4 (48), 61152,3–61212,1 (97) y 61212,6–61237,9 (77).
- La búsqueda en caché tiene `wavelength_um` nulo en 539 de 539 filas.

La λ en R Dra varía mucho dentro de cada detector en los frames del build: D1 0,736–1,113 µm (51 %), D2 1,110–1,420 (28 %), D3 1,722–2,196 (28 %), D4 2,406–3,757 (56 %), D5 3,832–4,196 (10 %), D6 4,492–4,836 (8 %).

| temp. build | frames (release, MJD, λ en R Dra [µm], píxeles OVERFLOW con r≤5) |
|---|---|
| 0 | 2025W23_1C_0021_1D3 (dr1, 60828.13, 2.145, 33); _1D6 (4.816, 11); _2D3 (2.196, 40); 2025W25_2A_0633_2D2 (60848.65, 1.110, 26); _2D5 (3.832, 18); _3D2 (1.135, 23); _3D5 (3.865, 17); 2025W27_2A_0243_1D4 (60860.54, 3.528, 54); _1D1 (1.037, 21); 2025W27_2A_0331_1D1 (60860.95, 1.113, 14); 2025W27_2A_0557_1D4 (60861.96, 3.623, 47) |
| 1 | 2025W29_2A_0351_1D1 (dr1, 60874.87, 0.941, 9); _1D4 (3.157, 52); 2025W29_2A_0805_1D1 (60876.77, 1.096, 32); _1D4 (3.757, 55) |
| 2 | 2025W45_1A_0067_1D1 (dr1, 60982.32, 0.736, 4); _1D4 (2.406, 12); _2D1 (0.754, 4); _2D4 (2.451, 32); 2025W49_1A_0280_1D2 (61011.25, 1.276, 20); _1D5 (4.035, 13); _2D2 (1.307, 21); _2D5 (4.070, 14) |
| 3 | 2026W01_2A_0426_2D3 (dr1, 61043.57, 2.125, 37); _3D6 (4.836, 23); _3D3 (2.174, 38) |
| 4 | 2026W20_2A_0294_4D3 (qr3, 61176.37, 1.722, 20); _4D6 (4.492, 7); 2026W25_2A_0573_2D2 (61212.14, 1.293, 12); _2D5 (4.054, 12); _3D2 (1.324, 16); _3D5 (4.089, 12) |
| 5 | 2026W26_1A_0047_1D5 (qr3, 61213.23, 4.161, 13); _1D2 (1.387, 9); _2D5 (4.196, 10); _2D2 (1.420, 10); 2026W28_2A_0376_2D1 (61232.44, 0.919, 12); _2D4 (3.075, 32); _3D1 (0.941, 11); _3D4 (3.160, 30) |

En los PNG del build, la caja central de 16×16 tiene entre 23 y 255 píxeles a 255.

En los 40 patches FITS:
- El pico finito con r ≤ 4 va de 1521 a 8632 MJy/sr (mediana 2863).
- El ruido de fondo (MAD en 40–60 px) es de 0,038 MJy/sr de mediana.
- La fracción de NaN es ≤ 0,28 %.

### 3. Fotometría a λ compatible y período

Por qué el ala: el núcleo está saturado en todos los frames. El ala de 12–20 px vale entre 0,2 y 4,3 MJy/sr (percentiles 5–95 por detector), muy por debajo de la saturación, y queda fuera de `BLOOM` (radio ≤ 9,8 px).

| det | λ [µm] | frames | bins de 1 % | pico a pico, P = 247 [mag] (revisión) | original | piso [mag] | Δχ² en 247 / máximo nulo (bloques) | t_max mod 247 | retraso vs V AAVSO [d] (1σ formal) | k = Δm_ala/ΔV |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 0.74–1.12 | 569 | 41 | 1.19±0.04 | 1.22±0.04 | 0.28 | 1060 / 162 | 60 | −1 (−1…0) | 0.249±0.008 |
| D2 | 1.11–1.63 | 52 | 18 | 0.96±0.34 | 0.78±0.16 | 0.37 | 23 / 19 | 71 | +24 (+18…+44) | 0.189±0.040 |
| D3 | 1.63–2.42 | 559 | 40 | 1.29±0.08 | 1.30±0.08 | 0.38 | 285 / 61 | 77 | +21 (+19…+22) | 0.229±0.015 |
| D4 | 2.41–3.82 | 566 | 47 | 0.51±0.03 | 0.53±0.03 | 0.14 | 307 / 62 | 97 | +47 (+46…+47) | 0.113±0.006 |
| D5 | 3.81–4.42 | 79 | 15 | 0.62±0.03 | 0.60±0.03 | 0.09 | 465 / 286 | 77 | +33 (+31…+33) | 0.122±0.006 |
| D6 | 4.41–5.00 | 559 | 13 | 0.80±0.01 | 0.78±0.01 | 0.08 | 3495 / 402 | 67 | +15 (+15…+15) | 0.158±0.003 |

Robustez:
- **Anillo de 8–12 px:** 1,24 / 0,56 / 1,15 / 0,44 / 0,57 / 0,79 mag.
- **Bins de 1,5 %:** 1,19 / 0,64 / 1,27 / 0,49 / 0,62 / 0,79 mag.
- **Período conjunto:** 260 d en los tres casos. El análisis original da 256, 259 y 261 d con anillos de 6–10, 10–16 y 16–24 px.
- **Cociente entre anillos (8–12)/(12–20):** pico a pico ≤ 0,07 mag (0,12±0,05 en D2).
- **Tamaño del núcleo:** la correlación de rangos entre el número de píxeles OVERFLOW (r ≤ 5) y el brillo del ala, ambos a λ fija, es +0,93, +0,87, +0,93, +0,82, +0,83 y +0,45 en D1…D6.
- **Período:**
  - Sinusoide conjunta: 260 d (bootstrap de 200 remuestreos sobre 240 visitas: 68 % entre 258 y 263, 95 % entre 255 y 265).
  - Dejando fuera un detector: 255–268 d.
  - El análisis original da 259 d (95 % entre 254 y 264). Con armónico, 255 d (análisis original, no remedido).
- **Periodograma conjunto (Δχ²):** 5717 en 260 d, 5635 en 247, 4308 en 144 (alias), 1647 en 183, 1367 en 365, 3539 en 500 y 4578 en 800 d.
- **AAVSO contemporáneo** (VSX `api.delim`, JD 2460700–2461360, consultado el 2026-11-14; 818 observaciones Vis./V; no se guardan los nombres de los observadores):
  - Máximos V en MJD 60811,4 (V ≈ 7,4), 61046,5 (≈ 7,0) y 61304,3 (≈ 7,5).
  - Mínimos (medianas de 10 d) cerca de 60939–60947 (V ≈ 12,2) y 61185–61196 (≈ 12,6–12,7).
  - Ciclos de 235 y 258 d. VSX predice 60815,2, 61061,3 y 61307,4.
- ❓ INFERIDO: que el máximo infrarrojo llegue más tarde que el de V es compatible con el comportamiento conocido de las Miras, pero no lo verifiqué contra la literatura. Además, el retraso no crece de forma monótona con λ (D6 < D5 < D4).

Δmag corregido por λ en bloques de 30 d (revisión: bloques libres + bins de λ de 1 %, respecto de la media del detector; negativo = más brillante; error estadístico con piso; entre paréntesis, frames):

| bloque MJD | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|
| 60780–60810 |  |  | −0.16±0.06 (41) |  |  | −0.19±0.01 (43) |
| 60810–60840 | −0.32±0.15 (4) | −0.22±0.11 (11) | −0.03±0.08 (22) | −0.65±0.07 (4) | −0.37±0.03 (12) | −0.31±0.02 (20) |
| 60840–60870 | +0.04±0.15 (4) | −0.45±0.14 (9) |  | −0.43±0.07 (4) | −0.27±0.03 (12) |  |
| 60870–60900 | −0.16±0.08 (12) |  |  | −0.52±0.04 (13) |  |  |
| 60900–60930 | +0.47±0.03 (63) |  |  | +0.03±0.02 (62) |  |  |
| 60930–60960 | +0.70±0.04 (45) |  |  | +0.07±0.02 (44) |  |  |
| 60960–60990 | +0.49±0.04 (52) |  |  | −0.01±0.02 (54) |  |  |
| 60990–61020 | +0.09±0.11 (7) | +0.21±0.07 (19) |  | −0.43±0.07 (4) | +0.09±0.02 (22) |  |
| 61020–61050 |  | +0.09±0.12 (10) | +0.03±0.09 (20) |  | +0.02±0.02 (14) | −0.04±0.02 (20) |
| 61050–61080 |  |  | −0.09±0.19 (4) |  |  | −0.19±0.03 (5) |
| 61080–61110 |  |  | −0.28±0.03 (126) |  |  | −0.14±0.01 (124) |
| 61110–61140 |  |  | −0.03±0.02 (237) |  |  | −0.02±0.00 (235) |
| 61140–61170 |  |  | +0.24±0.04 (80) |  |  | +0.27±0.01 (81) |
| 61170–61200 |  |  | +0.89±0.08 (25) |  |  | +0.46±0.01 (27) |
| 61200–61230 | +0.53±0.11 (7) | +0.52±0.29 (3) | +1.71±0.20 (4) | +0.04±0.06 (7) | +0.29±0.02 (19) | +0.55±0.04 (4) |
| 61230–61260 | +0.13±0.03 (84) |  |  | +0.12±0.02 (83) |  |  |
| 61260–61290 | −0.34±0.02 (224) |  |  | +0.05±0.01 (224) |  |  |
| 61290–61320 | −0.34±0.03 (67) |  |  | −0.18±0.02 (67) |  |  |

Controles, con el mismo modelo, P = 247 y λ propia de cada estrella (las estrellas están a una mediana de 0,62 % y un máximo de 1,34 % de la λ de R Dra):

| control | pico a pico [mag] | comentario |
|---|---|---|
| Apertura r ≤ 3 px, 6 estrellas Gaia (G 12,5–14,0), series de más de 400 frames | ≤ 0,067±0,029 | Δχ² ≤ 25 |
| Apertura, series cortas o ruidosas (G 13,61 en D6; G 13,97 con ≤ 44 frames) | hasta 0,25±0,15 y 0,66±0,47 | no significativas, Δχ² ≤ 8 |
| Ala de la estrella de G = 8,1, 4–8 px | 0,03–0,21 (D6 0,212±0,026; D4 0,101±0,010) | significativa en D4 y D6 |
| Ala de la estrella de G = 8,1, 8–12 px | hasta 0,55±0,04 (D4) | ala de 0,005–0,13 MJy/sr, contaminada por el halo de R Dra |

Las amplitudes de R Dra son ≥ 2,5 veces mayores que las de cualquier control del mismo detector. La prueba independiente más fuerte es que la serie sigue la fase de la curva V real.

### 4. Cómo reproducir

Análisis original (en `val/r-draconis/`, con `env.sh`), en este orden:
1. `coverage.py`
2. `search_deep.py`
3. `fetch_all.py wide` y `fetch_all.py deep`
4. `images.py`
5. `lc_measure.py`
6. `analyze_lc.py all a10_16`
7. `robust.py`
8. `harmonic.py`
9. `lamdep.py`
10. `figures.py`

Revisión (en `val/r-draconis/review/`, con el venv del proyecto; solo numpy, astropy y Pillow), en este orden:
1. `sia_counts.py` (SIA2 en vivo)
2. `measure.py` (lee los 2493 patches de la caché)
3. `stats.py`
4. `aavso.py` (sobre `aavso_rdra.txt`)
5. `lc.py w12_20 0.01`, más las variantes `lc.py w8_12 0.01` y `lc.py w12_20 0.015`
6. `diag.py`
7. `extra.py`
8. `period_boot.py`
9. `perm.py`
10. `blocks30.py`
11. `astrom.py`
12. `build_check.py`
13. `build_frames_flags.py`
14. `figs.py`

Además, `errante compare r-draconis --dir review/products` sobre una copia del campo. Los logs (`*.log`) quedan junto a cada script.

## Problemas encontrados

1. **WS1 + WS2 (`build.py`):** `wavelength_um` es null en los 40 frames y en las 539 filas de la búsqueda en caché.
   - Se eligen exposiciones consecutivas: 22 obs_id y 14 visitas.
   - El blink mezcla λ de hasta un 56 % de diferencia dentro de un detector.
   - Arreglo: calcular `wavelength_at` en el target desde el patch antes de ordenar y publicarla.
2. **WS2 (render) + WS5 (UI):** R Dra está saturada en 2488 de 2488 frames.
   - El PNG rellena el núcleo solo para mostrarlo: la caja central de 16×16 tiene entre 23 y 255 píxeles a 255.
   - La UI debe marcar «saturado: el brillo del PNG no es una medida».
   - Evaluar un indicador opcional de saturación por frame (requiere un PR `contract:`).
3. **WS3 + WS5 + contrato:** no existe un producto de curva de luz ni de fotometría FITS.
   - La comparación de brillo de R05 solo vive en el análisis offline.
   - Propuesta: un producto opcional con el método de ala (fuera de `BLOOM`), bins de λ, controles y, como referencia, AAVSO.
4. **WS2 (`compare`, C02/C03):** reejecutado y confirmado.
   - Hay 18 coadds de 1 a 4 frames con λ distintas. `flux_scale` va de 0,4634 a 1,2633, y en D6 no se ajusta (2–3 estrellas).
   - `compare` usa 5 temporadas (S0–S4) y el build 6 (0–5).
   - Advertirlo o desactivarlo en campos de variables.
5. **WS1 (búsqueda por defecto):** se excluyen los campos profundos (1954 de 2493 frames).
   - La curva de luz depende de ellos.
   - Ofrecer deep como opción, con agrupación temporal.
6. **WS2 (+ WS5):** las «temporadas» del build (≤ 60 d) no son temporadas de observación.
   - Son 6 bins contra 3 bloques reales en campo amplio.
   - Cambiar la etiqueta en la UI.
7. **WS1 (menor):** en 5 frames la huella del archivo contiene a R Dra, pero el píxel predicho cae entre 0,0 y 6,3 px fuera del array.
   - Se manejan sin fallar, pero cuentan como cobertura.
8. **WS3 (fuentes externas):** VizieR CfA seguía caído a las 19:23 UTC.
   - El período de Gaia DR3 ya está verificado por el archivo de ESA: 247,2 ± 6,0 d. Conviene citarlo con su error.
   - GCVS sigue sin verificar.
   - Para la fase, usar la curva AAVSO contemporánea y no la efeméride VSX extrapolada, que se desvía hasta 15 d.
