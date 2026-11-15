# Validación: RW Aurigae

> **Actualización 2026-11-15 (después de #41).** WS2 reconstruyó los campos publicados en #41 (build del 2026-11-15, 04:05–04:06 UTC), con selección nueva, chequeo de registro por frame y descarte de frames malos, y #48 cambió el render de los núcleos brillantes. **El campo publicado hoy ya no es el que se analizó:** comparte 26 de sus 40 frames con el build de #17. Las mediciones hechas sobre **todas** las exposiciones (los 335 frames) no dependen de esa selección y siguen valiendo. Lo que este registro dice de «los 40 frames publicados» (listas de ids, λ, problemas de los PNG) describe el build de #17 y no se volvió a verificar sobre el nuevo, salvo lo que se indica abajo. Re-verificado en el build nuevo: el frame con la WCS corrida 1,29 px (`2026W38_1A_0162_3D6`) ya se descarta («misregistered frame: field stars 1.34 px off»). El render de núcleos saturados cambió con #48 y no se re-midió.
>
> **Vigencia (2026-11-14).** Se analizó el build de integración (main `9b8ba42` + `ws2/season-compare`, 18:41 UTC). El campo publicado en `main` por #17 (18:54 UTC) tiene **los mismos 40 frames y PNG idénticos bit a bit** (md5), así que este registro vale para el campo publicado. Única diferencia: #17 ya publica `wavelength_um`/`bandwidth_um` en el centro del campo en los 40 frames, así que lo que abajo se dice de «λ nula en `field.json`» quedó resuelto en el producto. Sigue abierto que la *selección* de frames no ordena por λ: las filas SIA no traen λ y la selección de #17 es idéntica.
>
> Los scripts y la caché del análisis quedaron en el scratch local de la sesión de Claude y no se versionan («scratch local» abajo). Las figuras sí están en el repo, en [`figures/rw-aurigae/`](figures/rw-aurigae/). Revisión humana pendiente.

**Resultado: `success` para la variabilidad, medida en los FITS y solo en D1 (0,74–0,88 µm).** Se compararon frames sin flags
del mismo detector a longitud de onda compatible (|Δλ|/λ < 1 %). RW Aur (A+B sin resolver) **se abrillanta ~1 mag a
0,75–0,77 µm entre el 2025-09-02 (MJD 60920,03) y el 2026-09-08 (MJD 61291,28)**: −1,005 y −1,031 mag; −0,99 y −0,97
mag con corrección de punto cero. También se abrillanta 0,38–0,57 mag entre 2025-09 y 2026-03 y 0,40–0,46 mag entre
2026-03 y 2026-09. Los errores estadísticos son ≤ 0,006 mag. Las estrellas de comparación Gaia del mismo campo, medidas
en sus propios pares a λ emparejada, dan una σ robusta de 0,046–0,049 mag y |Δm| ≤ 0,27 mag.
Una revisión adversarial independiente re-midió con código propio la cobertura, la astrometría, la fotometría, los
pares, las comparaciones y el render. Reproduce todos los Δm del objetivo con diferencias ≤ 0,003 mag.
Las imágenes publicadas no muestran el cambio. La estrella está saturada (`OVERFLOW` en la apertura) en 304 de 335 frames, y ningún frame de D2–D6
queda limpio: los 17 frames sin flags en el objetivo son todos de D1 (17 de 56). En los 40 PNG la estrella vale 255.
**La "estrella ausente" en D1 no es un error de datos, de WCS ni de reproyección.** En D1 RW Aur está en el centro como una
mancha blanca compacta de 4–7 px, igual que otras 8–13 estrellas del campo, porque el stretch las satura a todas. En D1 no es
más brillante que el resto del campo: vale 0,4–1,2× la fuente más brillante. En D4–D6, en cambio, domina la imagen. Además, la
UI no marca el objetivo. Los dueños son WS2 (render) y WS5 (UI).
La revisión encontró dos problemas nuevos:
- `repair_for_display` borra parte del núcleo de la estrella en 4 frames de D3, D4 y D6 publicados.
- Un frame del archivo (2026W38_1A_0162_3D6) tiene su WCS corrida 1,29 px.

## Registro (plantilla de VALIDATION.md)

- **Target / resolved catalog ID:**
  - SIMBAD `V* RW Aur` (oid 756681), tipo `TT*`, espectro K1/5e+K5e, resuelto con Sesame de CfA el 2026-11-14
    (`sesame_rw_aur.xml`; re-consultado por la revisión, `review/dl/sesame.xml`).
  - Gaia DR3 tiene dos fuentes separadas 1,49″ (época 2016,0; 1,52″ en 2025–26):
    - 156430822114424576: G = 12,18, plx 6,406 ± 0,044 mas, RUWE 1,50.
    - 156430817820015232: G = 13,04, plx 5,454 ± 0,332 mas, RUWE 16,4.
  - SPHEREx no resuelve el par (píxel 6,15″, FWHM 7,5–9,0″).
  - **No verificado:** qué fuente es A y cuál es B. Sesame CfA no resuelve `RW Aur A` ni `RW Aur B` y CDS está caído.
  - Una tercera fuente Gaia (G = 18,8, a ~6″) se desprecia.
  - 2MASS 05074953+3024050 (J = 8,38, K = 7,02) coincide con la posición.
  - VSX (`B/vsx` en VizieR CfA, re-consultado el 2026-11-14): tipo `CTTS/ROT+CTTS`, V 9,2–13,6, P = 2,64 d.
- **Astrometry source URL / reference epoch / propagation:**
  - SIMBAD vía `https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?RW%20Aur`.
    J2000: 76.95652603, +30.40143817 (ref. 2007A&A...474..653V). µα* = +7,23 ± 2,23 y µδ = −20,33 ± 3,81 mas/año;
    plx 15,42 ± 3,69 mas (Hipparcos).
  - Propagación lineal desde J2000 a la época de cada frame. La paralaje es despreciable.
  - Posición predicha en la MJD media de cada temporada (la revisión la recalculó y coincide):

    | Temporada | MJD media | RA, Dec predichos | Distancia al centro de `fields.toml` |
    |---|---|---|---|
    | S0 | 60928,19 | 76.956586, +30.401293 | 0,017″ |
    | S1 | 61102,26 | 76.956587, +30.401290 | 0,010″ |
    | S2 | 61294,63 | 76.956588, +30.401287 | 0,011″ |

  - Movimiento total en la línea de base: 0,022″ = 0,004 px.
  - Control con Gaia: fotocentro DR3 A+B ponderado por flujo G y propagado con el pm de cada fuente (`I/355/gaiadr3`
    en VizieR CfA). Cae en 76.956237, +30.401168 (S0): 1,18″ = 0,19 px del centro (ΔRA* −1,10″, ΔDec −0,44″).
- **Query RA, Dec / FOV / query date:**
  - Consulta: 76.95659, +30.40129 (centro de `fields.toml`). Búsqueda puntual SIA2 (radio 0 → círculo de 1″) en
    `spherex_dr1` y `spherex_qr3`.
  - Caché `search_bcc8eefac21a441a463d22c2dd672cf7.json`, creada el 2026-11-14 18:41:16 UTC: servicio `sia`, sin overflow
    ni respaldo vencido. No se hicieron consultas nuevas a IRSA SIA/TAP.
  - Producto: grilla 88×88 px de 6,15″ (0,15°), con cutouts de 13,5′.
  - Fotometría: patches S3 de 8′ (78×78 px) de los 335 frames; los 335 están en caché.
    - La revisión comparó un patch (2026W38_1A_0162_3D6) con el cutout IBE del mismo frame. IMAGE, FLAGS y WCS son
      bit a bit idénticos.
- **SPHEREx releases / observation IDs / MJDs / detectors / wavelengths:**
  - 335 frames, sin duplicados entre releases y con 15 versiones de pipeline:
    - dr1: 226 (D1–D6: 38/37/38/38/37/38).
    - qr3: 109 (D1–D6: 18/18/18/18/19/18).
  - Temporadas (corte > 30 d):

    | Temporada | MJD | Fechas | Frames | Release |
    |---|---|---|---|---|
    | S0 | 60919,42–60938,23 | 2025-09-01→09-20 | 112 | todo dr1 |
    | S1 | 61091,72–61111,00 | 2026-02-20→03-12 | 114 | todo dr1 |
    | S2 | 61285,10–61299,90 | 2026-09-02→09-16 | 109 | todo qr3 |

  - Cada detector tiene 18–19 frames por temporada. Hay 48 visitas (> 6 h): 18/15/15.
  - El build usó 40 frames, con 0 fallos y 0 frames saltados. Por temporada (D1–D6):
    - S0: 3/3/2/2/2/2.
    - S1: 3/2/2/2/2/2.
    - S2: 3/2/2/2/2/2.
  - Frames usados, con λ en el objetivo según `SpherexImage.wavelength_at` (la revisión la recalculó y coincide):

    | Detector | Frames usados: temporada y λ (µm) |
    |---|---|
    | D1 | 2025W36_1A_0446_1/2/3 S0 0,782/0,801/0,820 · 2026W10_2B_0591_3/4 S1 0,741/0,758 · 2026W10_2B_0626_1 S1 1,036 · 2026W37_1A_0234_2/3/4 S2 0,754/0,771/0,789 |
    | D2 | 2025W37_1A_0366_1/2/3 S0 1,185/1,214/1,243 · 2026W10_1A_0602_1/2 S1 1,533/1,570 · 2026W37_2A_0516_1/2 S2 1,148/1,175 |
    | D3 | 2025W38_1A_0538_1/2 S0 1,621/1,659 · 2026W09_2A_0224_2/3 S1 1,639/1,677 · 2026W38_1A_0162_4 S2 1,760 · 2026W38_1A_0213_1 S2 2,385 |
    | D4 | 2025W36_1A_0446_1/2 S0 2,556/2,624 · 2026W10_2B_0591_3/4 S1 2,419/2,465 · 2026W37_1A_0234_2/3 S2 2,452/2,514 |
    | D5 | 2025W37_1A_0366_1/2 S0 3,927/3,961 · 2026W10_1A_0602_1/2 S1 4,312/4,349 · 2026W37_2A_0516_1/2 S2 3,881/3,914 |
    | D6 | 2025W38_1A_0538_1/2 S0 4,409/4,441 · 2026W09_2A_0224_2/3 S1 4,425/4,456 · 2026W38_1A_0162_4 S2 4,524 · 2026W38_1A_0213_1 S2 4,981 |

  - `field.json` publica `wavelength_um = null` en los 40 frames.
  - En 2025W38_1A_0538_1D3 el objetivo cae a ~4 filas del borde del detector: el patch de 13,5′ queda en 69×132 px.
- **Useful epochs / time baseline / coverage and quality flags:**
  - Línea de base: 380,5 d. Las 3 temporadas cubren los 6 detectores.
  - Calidad en el objetivo con apertura r = 3 px. La revisión obtuvo los mismos conteos con su propio código:

    | Clase | Frames | Criterio |
    |---|---|---|
    | `sat` | 304 | `OVERFLOW` en la apertura; ningún frame tiene `NONLINEAR` |
    | `bad` | 10 | `SUR_ERROR`, `NONFUNC`, `PERSIST` u otros sin `OVERFLOW` |
    | `edge` | 4 | La apertura o el anillo caen fuera del detector |
    | `clean` | 17 | Todos en D1 |

  - Frames limpios por detector: D1 17/56, D2 0/55, D3 0/56, D4 0/56, D5 0/56, D6 0/56.
  - Frames limpios de D1 por temporada: S0 11, S1 4, S2 2.
  - En D1 el `OVERFLOW` aparece desde un pico de 85,6 MJy/sr (mediana 125,4). El máximo sin flag es 90,6 MJy/sr.
  - En los 40 patches del build, los píxeles `OVERFLOW` son finitos, no NaN. Solo 2025W36_1A_0446_1D4 tiene un NaN en el
    núcleo 5×5.
  - `L2DQAFLG = Pass` en los 335 frames.
- **Alignment check / photometry or astrometry method / uncertainties:**
  - **WCS nativo frente a Gaia DR3:**
    - Análisis original: ajuste PSF de estrellas aisladas con RUWE < 1,4, G < 15,5 y sin `OVERFLOW`. Dio 1945 medidas en
      327 frames, mediana (−0,001, +0,006) px y σ robusta (0,077, 0,058) px.
    - Revisión: centroide gaussiano ventaneado propio (`review/scripts/r5_astrometry.py`). Dio 2195 medidas en 334 frames,
      con mediana (−0,005, +0,009) px. Confirma que no hay sesgo.
    - **Corrección:** el "máximo 0,197 px por frame" no vale para los 335 frames. En 2026W38_1A_0162_3D6 las 4 estrellas
      están desplazadas −1,21 a −1,36 px en x, aunque el header dice `FINAST = 0` (solución "good"). Las exposiciones
      vecinas están a < 0,1 px. Ese frame no está en el build.
    - La σ por estrella de la revisión (0,14 px) es mayor, porque su centroide es más simple. No re-mide la precisión del
      original.
  - **Grilla publicada:**
    - La revisión verificó que los 40 PNG salen idénticos (diferencia máxima 0) del FITS cacheado con `reproject_to_grid`,
      `to_uint8` y el stretch publicado.
    - El pico del objetivo cae en el píxel (43–44, 43–44) en los 40 frames; la posición predicha es (43,68, 43,57).
    - Las cifras de astrometría en la grilla del análisis original (808 medidas, σ robusta ~0,1 px) **no fueron
      re-medidas** por la revisión.
  - **Fotometría:**
    - Apertura circular r = 3 px con fracción de píxel, sobre `IMAGE − ZODI`.
    - Fondo: mediana con sigma-clip en un anillo de 6–10 px, sin píxeles NaN ni con flags malos.
    - Conversión a mJy:
      - análisis original: ángulo sólido local del píxel desde la WCS SIP (37,44–38,42 arcsec²);
      - revisión: `OMEGA_MEDIAN`. Sus flujos salen ~1,1 % más bajos; la diferencia se cancela en los cocientes.
    - Error: `VARIANCE` en la apertura más el término del fondo.
    - Robustez a la apertura en D1 limpio: r2/r3 = 0,976–0,986 y r4/r3 = 1,002–1,009. La revisión lo confirma.
  - **Variabilidad:** pares del mismo detector, de temporadas distintas, con |Δλ|/λ < 1 % y frames limpios. Controles:
    - pares equivalentes de estrellas de comparación, cada una a su propia λ;
    - el ensamble de comparación medido en los mismos dos frames;
    - un punto cero por frame: mediana de los residuos de `ln F = poly2(λ)` por estrella de comparación.
  - **Piso sistemático empírico (comparaciones de D1):**

    | Análisis | Estrellas | Pares | σ robusta (mag) | 95 % dentro de (mag) | Máximo (mag) | σ del punto cero por frame (mag) |
    |---|---|---|---|---|---|---|
    | Original | 6 | 206 | 0,049 | 0,116 | – | 0,018 |
    | Revisión | 7 (6 en común) | 246 | 0,046 | 0,113 | 0,27 | 0,015 |

  - **Pendiente espectral:** el objetivo cambia 2,2–4,4 /µm en ln F entre exposiciones consecutivas. Con |Δλ| ≤ 7 nm eso
    aporta ≤ 0,03 mag a los pares. La excepción es 0446_3→0446_4 (ver limitaciones).
  - **Revisión independiente:** re-midió todo con código propio, sin reutilizar los scripts del análisis original:
    - la cobertura y los frames del build;
    - la astrometría con Sesame y Gaia re-consultados;
    - las clases de saturación;
    - la fotometría del objetivo y de las comparaciones;
    - los pares;
    - la reproducción de los PNG y el ranking de picos;
    - el efecto de `repair_for_display`;
    - `compare` corrido sobre una copia.

    Scripts en `scratch local: rw-aurigae/review/scripts/` (`r1`–`r10`, `rlib.py`).
- **Expected behavior / observed behavior:**
  - **Esperado:** variable irregular T Tauri (VSX: V 9,2–13,6); movimiento ≈ 0 px (0,022″ en 380 d).
  - **Observado, posición:**
    - El pico está en el centro del grid en 40 de 40 frames.
    - El centroide de los 27 frames sin `OVERFLOW` cae más cerca del fotocentro Gaia A+B que de la posición
      SIMBAD/Hipparcos. Las cifras dependen del método:

      | Método | Frente al fotocentro Gaia | Frente a SIMBAD/Hipparcos |
      |---|---|---|
      | Original: ajuste PSF | (+0,08″, +0,07″) | (−1,01″, −0,39″) |
      | Revisión: centroide ventaneado (σ por frame 0,87″) | (+0,35″, −0,12″) | (−0,74″, −0,57″) |

  - **Observado, brillo (D1, entre épocas concretas):**

    | Pares | Fechas | λ (µm) | Δm (mag) | Con punto cero (mag) |
    |---|---|---|---|---|
    | S0→S2 | 2025-09-02 → 2026-09-08 | 0,747–0,771 | −1,005 y −1,031 | −0,99 y −0,97 |
    | S0→S1 | 2025-09-02 → 2026-03-08/10 | 0,741–0,782 | −0,525, −0,566 y −0,375 | – |
    | S0→S1 | 2025-09-03 → 2026-03-04 | 0,879 | −0,096 ± 0,004 | – |
    | S1→S2 | 2026-03 → 2026-09 | – | −0,398 y −0,461 | – |

  - **Inferido, no verificado:** dentro de S0 la estrella también parece cambiar entre visitas, del 2025-09-01 al 09-03.
    El espectro de S0 no es una curva suave (`fig_review_spectrum.png`). Por eso los Δm valen para esas épocas, no como
    "brillo medio de la temporada".
  - **Retirado:** el desplazamiento del centroide de S2 respecto de S0 (+0,57″, +0,42″) no se reproduce. La revisión
    mide (−0,20″, +0,46″) con σ por frame 0,87″, así que se quita.
- **Result:** `success`.
  - Hay 8 pares emparejados con frames limpios de D1 y calibración controlada por estrellas de comparación.
  - El cambio mínimo significativo (0,375 mag) vale:
    - 7,7–8,2 veces la σ robusta de las comparaciones;
    - 3,3 veces su percentil 95;
    - 1,4 veces su máximo (0,27 mag).
  - No se afirma la causa física.
  - El recorrido público (paso 6) sigue pendiente: los PNG no muestran el cambio y no hay URL pública.
- **Limitations and failed downloads:**
  - 0 descargas fallidas: 0 de 40 en el build; 335 de 335 patches de 8′ presentes en caché.
  - Solo D1 es medible: ningún frame de D2–D6 queda limpio (`OVERFLOW`, otros flags o borde). Hay 17 frames limpios, todos D1, que dan 8 pares emparejados.
  - La variabilidad dentro de una temporada mezcla tiempo y color.
  - **Salto sin explicación de +0,38 mag** entre exposiciones consecutivas separadas 2,15 min:
    - 2025W36_1A_0446_3D1: 0,8196 µm, 105,6 mJy (revisión).
    - 2025W36_1A_0446_4D1: 0,8391 µm, 74,2 mJy (revisión).
    - Las 6 comparaciones en esos frames cambian entre −0,115 y +0,064 mag.
    - No se usa en el resultado.
  - **Indicio no válido**, con frames `OVERFLOW` incluidos: la mediana S0→S2 es D1 −0,45, D2 −0,38, D3 −0,11,
    D4 +0,28, D5 +0,74 y D6 +0,75 mag (revisión; el original da valores similares). Con saturación el recorte crece cuanto
    más brilla la estrella, así que el signo en D4–D6 podría ser un artefacto.
  - No se verificó la identificación A/B en Gaia.
  - La visualización pública no muestra el cambio: PNG en 255 y sin marcador del objetivo.
- **Product field ID / public URL / screenshot or animation:**
  - Field ID: `rw-aurigae` (`data/products/fields/rw-aurigae/`). URL pública: pendiente del deploy (WS4).
  - Recorrido revisado solo en la vista local `/?dataset=real#/field/rw-aurigae` (paso 6 de VALIDATION.md pendiente en la URL pública).
    La revisión comprobó en el DOM que se cargan 40 imágenes, que `svg.blink-overlay` existe con 0 elementos (no hay
    marcador del objetivo) y que el caption mostraba solo la banda nominal del detector.
  - Figuras (gráficos generados con código a partir de los FITS reales de SPHEREx):
    - [fig_pairs_D1.png](figures/rw-aurigae/fig_pairs_D1.png): Δm de RW Aur en pares D1 a λ emparejada, contra las estrellas de comparación
    - [fig_spectrum_D1.png](figures/rw-aurigae/fig_spectrum_D1.png): Espectro D1 por temporada
    - [fig_cutouts_seasons.png](figures/rw-aurigae/fig_cutouts_seasons.png): Cutouts por temporada
    - [fig_render_d1_vs_d6.png](figures/rw-aurigae/fig_render_d1_vs_d6.png): Render D1 frente a D6 (por qué la estrella no destaca en D1)
    - [fig_png_zoom_center.png](figures/rw-aurigae/fig_png_zoom_center.png): Zoom al centro de los PNG publicados
    - `fig_png_contact_sheet.png` (no incluida en el repo por tamaño): Hoja de contacto de los 40 PNG publicados
    - [fig_ws2_compare_coadds.png](figures/rw-aurigae/fig_ws2_compare_coadds.png): Coadds de `errante compare` (huecos en los núcleos saturados)
    - [fig_review_zoom_d1_d6.png](figures/rw-aurigae/fig_review_zoom_d1_d6.png): Revisión: PNG publicado frente a patch crudo, D1 y D6, con `OVERFLOW` en rojo
    - [fig_review_render.png](figures/rw-aurigae/fig_review_render.png): Revisión: PNG frente a escala log, D1–D6 × 3 temporadas
    - [fig_review_spectrum.png](figures/rw-aurigae/fig_review_spectrum.png): Revisión: espectro de D1 por temporada
    - [fig_review_pairs.png](figures/rw-aurigae/fig_review_pairs.png): Revisión: Δm de los pares frente a las comparaciones
    - [fig_review_compare.png](figures/rw-aurigae/fig_review_compare.png): Revisión: coadds y diferencias de `compare`

- **Reviewer / date:** Claude (WS1) con revisión adversarial independiente / 2026-11-14; revisión humana pendiente.

## Detalle de la medición

**Método.**
- **Análisis original:** scripts `s1`–`s9` en `.../val/rw-aurigae/scripts/`.
- **Revisión independiente:** `.../val/rw-aurigae/review/scripts/`, con logs `logs_r*.txt`:

  | Script | Qué hace |
  |---|---|
  | `r1_coverage.py` | Cobertura y posición |
  | `r2_render.py` | Reproducción de los PNG y prominencia del objetivo |
  | `r3_phot.py` | Fotometría de 335 frames |
  | `r4_variability.py` | Pares, punto cero y comparaciones |
  | `r5_astrometry.py` | WCS frente a Gaia y centroide del objetivo |
  | `r6_figs.py`, `r7_zoom.py` | Figuras |
  | `r8_repair.py` | Efecto de `repair_for_display` |
  | `r9_checks.py` | `L2DQAFLG`, aperturas, `thumb.png`, overlays |
  | `r10_compare.py` | `compare` corrido sobre una copia |

- **Catálogos:** Gaia DR3 (`review/dl/gaia8.tsv`, G < 17 a menos de 8′, y `gaia_near.tsv`), 2MASS (`tmass8.tsv`) y VSX
  (`vsx.tsv`), todos de `vizier.cfa.harvard.edu`.

**Flujos limpios de D1 a ~0,75 µm (mJy, r = 3 px).** Columna "original": Ω local de la WCS. Columna "revisión":
`OMEGA_MEDIAN`.

| Temporada | Frame | MJD | λ (µm) | Flujo original | Flujo revisión |
|---|---|---|---|---|---|
| S0 | 2025W36_1A_0233_2D1 | 60920,031 | 0,7469 | 73,4 ± 0,3 | 72,5 ± 0,3 |
| S0 | 2025W36_1A_0233_3D1 | 60920,032 | 0,7645 | 76,2 ± 0,3 | 75,4 ± 0,3 |
| S0 | 2025W36_1A_0446_1D1 | 60920,978 | 0,7821 | 91,2 ± 0,4 | 90,3 ± 0,3 |
| S1 | 2026W10_2B_0591_3D1 | 61107,676 | 0,7409 | 119,0 ± 0,4 | 117,9 ± 0,4 |
| S1 | 2026W10_2B_0591_4D1 | 61107,678 | 0,7583 | 128,4 ± 0,4 | 127,3 ± 0,4 |
| S1 | 2026W11_1A_0285_1D1 | 61109,440 | 0,7757 | 128,9 ± 0,4 | 127,8 ± 0,4 (`HALO` en la apertura, sin `OVERFLOW`) |
| S2 | 2026W37_1A_0234_2D1 | 61291,276 | 0,7537 | 185,2 ± 0,5 | 183,2 ± 0,5 |
| S2 | 2026W37_1A_0234_3D1 | 61291,277 | 0,7712 | 197,0 ± 0,5 | 195,0 ± 0,5 |

**Pares emparejados del objetivo** (|Δλ|/λ < 1 %; Δm = posterior − anterior). Columnas de la revisión:
- "con punto cero": Δm corregido con el punto cero por frame de las comparaciones;
- "ensamble": mediana de las comparaciones medidas en los mismos dos frames.

| Par | λ (µm) | Δm original | Δm revisión | Revisión con punto cero | Revisión, ensamble (n) |
|---|---|---|---|---|---|
| S0→S1 | 0,7469→0,7409 | −0,525 ± 0,006 | −0,528 ± 0,006 | −0,544 | +0,026 (4) |
| S0→S1 | 0,7645→0,7583 | −0,566 ± 0,006 | −0,569 ± 0,006 | −0,513 | −0,050 (5) |
| S0→S1 | 0,7821→0,7757 | −0,375 ± 0,005 | −0,377 ± 0,005 | −0,375 | −0,019 (6) |
| S0→S1 | 0,8790→0,8788 | −0,096 ± 0,004 | −0,099 ± 0,004 | −0,107 | −0,006 (7) |
| S0→S2 | 0,7469→0,7537 | −1,005 ± 0,005 | −1,007 ± 0,005 | −0,990 | −0,020 (3) |
| S0→S2 | 0,7645→0,7712 | −1,031 ± 0,005 | −1,032 ± 0,005 | −0,972 | −0,078 (5) |
| S1→S2 | 0,7583→0,7537 | −0,398 ± 0,004 | −0,395 ± 0,004 | −0,399 | +0,006 (5) |
| S1→S2 | 0,7757→0,7712 | −0,461 ± 0,004 | −0,458 ± 0,004 | −0,458 | +0,016 (5) |

En el par S0→S1 a 0,879 µm, el cambio de −0,1 mag equivale a ~2σ del piso sistemático: no es significativo por sí solo.

**Estrellas de comparación de D1.** Selección de la revisión: Gaia G 12–15,8, RUWE < 1,4, a más de 40″ del objetivo y sin
vecina con G < G+1,5 a menos de 15″. Las cifras son de sus propios pares a λ emparejada.

| Gaia DR3 | G | Pares | Mediana Δm (mag) | σ robusta (mag) | Máximo \|Δm\| (mag) |
|---|---|---|---|---|---|
| 156337329267576576 | 14,87 | 29 | −0,006 | 0,039 | 0,112 |
| 156430027546480512 | 14,78 | 34 | +0,005 | 0,030 | 0,101 |
| 156430856476049024 | 15,26 | 44 | −0,040 | 0,075 | 0,253 |
| 156430886538071552 | 12,80 | 38 | +0,003 | 0,021 | 0,051 |
| 156430955257551360 | 14,85 | 29 | −0,022 | 0,058 | 0,184 |
| 156431131353952640 | 15,32 | 39 | −0,010 | 0,056 | 0,269 |
| 156431234433162496 | 14,65 | 33 | −0,008 | 0,043 | 0,111 |

- Punto cero por temporada (mediana del residuo, revisión): S0 +0,004, S1 +0,002 y S2 +0,005 mag. El análisis original da
  offsets S1−S0 +0,003 y S2−S0 +0,001.
- Comparaciones en los otros detectores (revisión): D2 σ 0,041, D3 0,041, D4 0,066, D5 0,146 y D6 0,371 mag. En D5 y D6
  las comparaciones son débiles. El objetivo está saturado en todos ellos.

**Diagnóstico de la "estrella ausente" en D1.** Medido por la revisión en los 40 frames publicados (`r2_render.py`):
- picos > 10σ con filtro de máximo 5×5;
- "otras manchas blancas" = otras manchas de 255 en el PNG.

| Detector | vmax (MJy/sr) | Pico del objetivo en el grid (MJy/sr) | Pico/vmax (mediana) | Objetivo / fuente más brillante | Rango del objetivo | Mancha blanca del objetivo | Otras manchas blancas |
|---|---|---|---|---|---|---|---|
| D1 | 6,88–6,90 | 25,7–60,3 | 6,3 | 0,43–1,20 | 1–4 | 4–7 px | 8–13 manchas, hasta 13 px |
| D2 | 8,45–8,46 | 52–176 | 12,8 | 0,61–1,95 | 1–4 | 4–9 px | – |
| D3 | 8,43–8,47 | 19,6*–183 | 15,6 | 0,21–3,64 | 1–5 | 5–10 px | – |
| D4 | 5,50–5,59 | 160–299 | 34,5 | 2,86–7,60 | 1 | 10–20 px | – |
| D5 | 5,01–5,02 | 246–610 | 87,6 | 7,9–29,5 | 1 | 16–27 px | – |
| D6 | 4,91–4,94 | 350–457 | 74,9 | 13,6–31,3 | 1 | 21–31 px | – |

\* En 2025W38_1A_0538_1D3 el pico publicado (19,6) sale reducido por `repair_for_display`; sin reparar vale 74,2 MJy/sr.

- El análisis original da otros rangos para el cociente objetivo/fuente más brillante (D1 0,36–1,19; D6 19,4–36,4) porque
  detecta los picos de otra forma. La conclusión es la misma.
- En D1 la fuente más brillante "otra" está a 274–296″ del objetivo, en el borde del grid.
- `PSF_FWHM` es 9,04″ en D6 contra 7,53″ en D1.
- Se descartaron las hipótesis alternativas:
  - **NaN o máscara:** no hay NaN en el núcleo. `OVERFLOW` es finito.
  - **Objetivo descentrado:** el pico está en el píxel central.
  - **WCS o reproyección:** los PNG se reproducen exactos y la WCS de los frames del build está alineada con Gaia.
- La causa es el stretch más el SED. El stretch común por detector (`field_stretches`: percentil 99,5 o 40σ) satura a blanco
  a todas las estrellas brillantes. En D1 RW Aur no domina el campo; en D4–D6 sí, por su exceso infrarrojo (la causa física
  es INFERIDA).

## Problemas encontrados

1. **WS2 (render) + WS5 (UI): el objetivo no se distingue en D1, y no se ve su variabilidad.**
   - El stretch satura el objetivo a 255 en los 40 PNG, con pico/vmax mediano de 6× en D1 a 88× en D5. Un cambio de 1 mag
     queda invisible en el blink.
   - `thumb.png` es un frame de D1 (2026W10_2B_0591_4D1), donde el objetivo no domina.
   - WS2: stretch HDR o log con un vmax que incluya el pico del objetivo, o una capa "escala del objetivo". Elegir la
     miniatura del detector donde el objetivo domina.
   - WS5: dibujar una retícula en la posición del objetivo; hoy `BlinkViewer` solo dibuja candidatos y objetos conocidos,
     ambos vacíos. Mostrar un badge de saturación por frame.
2. **Integración `build.py` (WS1 + WS2 + WS4): `wavelength_um` y `bandwidth_um` son `null` en los 40 frames.**
   - Las filas SIA no traen λ y el build no la calcula con `wavelength_at`.
   - `plan_frames` no puede ordenar por λ, así que el blink mezcla λ dentro de un detector: D1 0,741–1,036 µm y D3
     1,621–2,385 µm.
   - La UI muestra solo la banda nominal.
   - Arreglo propuesto: llenar `Frame.wavelength_um` y `bandwidth_um` con `img.wavelength_at(objetivo)` y leer WCS-WAVE antes
     de seleccionar.
3. **WS2 (`compare`) / WS3: saturación.**
   - 304 de 335 frames tienen `OVERFLOW` en el objetivo.
   - Los coadds de `errante compare` (corrido sobre una copia) tienen 1–11 px transparentes en el núcleo en D2–D6.
   - Las diferencias D5 y D6 S2−S0 muestran un anillo cian (más brillante antes) alrededor del hueco. No es interpretable:
     el núcleo está saturado y la λ no está emparejada (D6 S0 4,41–4,44 contra S2 4,52–4,98 µm).
   - D1 S2−S0 da residuo positivo, coherente con lo medido, pero no está emparejado en λ.
   - La evidencia pública necesita un producto de fotometría desde el FITS, como espectros o curva de luz por temporada
     (WS3). Requiere un PR `contract:` aditivo.
4. **WS2 (`reproject.display_defects`), nuevo: la reparación de display borra parte del núcleo de estrellas reales.**
   - Todo píxel `SUR_ERROR` sin `OVERFLOW` se trata como defecto y se reemplaza por la mediana de sus vecinos.
   - En RW Aur esos píxeles son el núcleo de la estrella. Pico publicado frente a sin reparar:
     - 2025W38_1A_0538_1D3: 19,6 contra 74,2 MJy/sr (26 %);
     - 2025W38_1A_0538_1D6: 55 %;
     - 2026W37_1A_0234_3D4: 52 %;
     - 2026W10_2B_0591_4D4: 66 %.
   - No afecta a D1, así que no explica la anomalía. Sí importa para un stretch HDR o para comparar brillos en PNG.
   - Propuesta: no reparar `SUR_ERROR` dentro de un núcleo con `SOURCE` y vecinos brillantes; limitarlo a píxeles aislados.
5. **WS2 (registro) + WS1 (`DATA.md`), nuevo: un frame del archivo tiene la WCS corrida 1,29 px.**
   - En 2026W38_1A_0162_3D6, 4 estrellas Gaia caen a −1,21/−1,36 px en x, aunque el header dice `FINAST = 0` "good" y
     `ASTRONETSOLVED = True`.
   - El patch S3 es idéntico al cutout IBE: el error es del archivo, no del código de WS1.
   - No está en el build. Si se seleccionara, produciría un falso movimiento de 1,3 px en el blink.
   - Propuesta: validar cada frame contra Gaia (offset medio > 0,3 px → descartar o corregir) y anotarlo en `DATA.md`.
6. **WS2 (`flags.py`) + coordinación (`DATA.md`): falta el bit 27 `SNOWBALL`.**
   - Los headers FLAGS de dr1 y qr3 lo declaran (`MSKN0027 = 'SNOWBALL'`, "Pixel part of a snowball artifact").
   - No está en `FLAG_BITS`, en `DEFAULT_BAD` ni en la tabla de `DATA.md` §2.
7. **WS2 (nota de procedencia).**
   - `field.json` dice que los núcleos saturados se rellenan para mostrarlos.
   - En RW Aur los píxeles `OVERFLOW` son finitos y se muestran tal como vienen; solo se rellenan núcleos NaN.
   - Lo que sí se reemplaza son píxeles `SUR_ERROR`/`NONFUNC` sin `OVERFLOW` (punto 4).
8. **WS3 (`fields.toml`, `SCIENCE.md`).**
   - El centro usa la posición SIMBAD/Hipparcos, a 0,9–1,1″ (≤ 0,18 px) del centroide medido. El fotocentro Gaia DR3 A+B
     coincide a 0,1–0,4″, según el método. Es cosmético.
   - La asignación A/B de Gaia en `SCIENCE.md` no está verificada.
   - "3 puntos por detector" no se cumple: solo D1 es medible sin saturación.
   - El ❓ de saturación de `DATA.md` §6 queda resuelto para este blanco: `OVERFLOW` en 304 de 335 frames, ningún frame de D2–D6 limpio y 17 de 56 limpios en D1. (Corregido el 2026-11-15: la versión anterior decía «todo D2–D6 y 37 de 56 de D1», que suma 316, no 304; la tabla de clases no da el reparto por detector de `sat`.)

## Addendum 2026-11-15 (WS3): curva de luz publicada en la app

- **Qué hay.** El producto precalculado `GET /api/lightcurves/rw-aurigae` (#79), con su panel en la página del campo
  (#83), usa las mismas 56 exposiciones D1 y los métodos de WS3 de este registro.
- **Coincide con este registro:** los 17 frames limpios (10 usados + 7 sin pareja en λ) y los 8 pares emparejados en
  λ, con ≤ 0,003 mag de diferencia (−1,008 y −1,034 mag a 0,75–0,77 µm entre el 2025-09-02 y el 2026-09-08).
- **Límites que el producto no declara** (LC4 de la revisión):
  - A y B (1,5″) caen en el mismo píxel;
  - la saturación crece con el brillo (S0 7/19, S1 14/19, S2 16/18) y saca de la curva casi todo el estado brillante;
  - el `summary` sale de bins de 2 puntos, así que es descriptivo y no una significancia;
  - para los pares, el piso de las comparaciones es 0,033 mag (pares), no 0,018 (por punto).
- **Revisión completa:** `docs/SCIENCE.md` § «Revisión científica de las curvas de luz» (#85). No es una validación
  nueva ni reemplaza este registro.
