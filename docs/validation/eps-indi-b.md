# Validación: Epsilon Indi B

> **Vigencia (2026-11-14).** Se analizó el build de integración (main `9b8ba42` + `ws2/season-compare`, 18:42 UTC). El campo publicado en `main` por #17 (18:53 UTC) tiene **los mismos 40 frames y PNG idénticos bit a bit** (md5), así que este registro vale para el campo publicado. Única diferencia: #17 ya publica `wavelength_um`/`bandwidth_um` en el centro del campo en los 40 frames, así que lo que abajo se dice de «λ nula en `field.json`» quedó resuelto en el producto. Sigue abierto que la *selección* de frames no ordena por λ: las filas SIA no traen λ y la selección de #17 es idéntica.
>
> Los scripts y la caché del análisis quedaron en el scratch local de la sesión de Claude y no se versionan («scratch local» abajo). Las figuras sí están en el repo, en [`figures/eps-indi-b/`](figures/eps-indi-b/). Revisión humana pendiente.

**Resultado: success.** Se ensayó el movimiento propio sobre el campo `eps-indi-b` con datos reales de SPHEREx (DR1 + QR3).
ε Indi B (Ba+Bb, que SPHEREx no resuelve) se detecta como una sola fuente en 37 de los 40 frames publicados y en ~440 de los
458 frames que cubren la posición: 440 en el análisis original, 441 en la revisión independiente. La diferencia es un frame D1
marginal a 0,83 µm. Las no detecciones son frames D1 por debajo de ~0,83 µm, donde una enana T es muy débil, y 2 frames con
el núcleo enmascarado por `SUR_ERROR`. Entre S0 y S3, con el mismo detector, el desplazamiento medido es
**1,031 ± 0,006 px** según el análisis original y **1,026 ± 0,007 px** según la revisión (± ~0,016 px de sistemático), a PA
126,5–126,7 ± 0,4°. Lo esperado es 1,028–1,030 px a PA 125,8–125,9°. El “sin movimiento” queda descartado a más de 50σ aun
sumando el sistemático. El movimiento propio ajustado coincide con el del catálogo dentro de ≤ 1,5σ.

Hay un offset constante de ~0,6″ (0,1 px) entre el fotocentro y el catálogo, de causa INFERIDA, que no afecta el
desplazamiento. No es un descubrimiento: se recupera un movimiento conocido. Problemas de pipeline y de UI (detalle al final):
λ nula en `field.json`, frames D1 sin el objetivo, un frame con salto de fondo, la UI sin marcador del objetivo y
diferencias de WS2 sin escala ajustada en D5/D6.

Convención: **VERIFICADO** = medido en esta sesión (script en scratch); **INFERIDO** = interpretación no comprobada.
(A) = análisis original; (R) = revisión adversarial independiente, con código propio.

- **Target / resolved catalog ID:** ε Indi B = `* eps Ind B` (SIMBAD oid 3387843, tipo `BD*`, espectro T1V+T6V). Resuelto con
  Sesame de CfA el 2026-11-14; (R) repitió la consulta y obtuvo los mismos valores. Gaia DR3 6412596012146801152 (G = 18,03,
  RUWE 4,30; VizieR CfA `I/355/gaiadr3`). Sesame no encuentra `eps Ind Ba` ni `eps Ind Bb` (VERIFICADO): en SPHEREx el par es
  una sola fuente. La estrella brillante es ε Ind A = `* eps Ind` = HD 209100 (K5V).
  - Identidad de la fuente medida (VERIFICADO por R):
    - Gaia DR3, en un cono de 11′: la fuente más cercana a la posición 2025–2026 es la propia ε Ind B en su época 2016 (a 47″).
      No hay otra fuente Gaia (hasta G ≈ 20,4) a menos de 47″.
    - 2MASS (`II/246`): ninguna fuente a menos de 54″.
    - AllWISE (`II/328`): la fuente más cercana está a 11,5–11,9″ de la trayectoria, con W1 = 16,8, contra W1 = 10,72 de
      ε Ind B (6,1 mag más débil, ~0,4 % del flujo; desplazaría el centroide ≤ 0,007 px).
- **Astrometry source URL / reference epoch / propagation:**
  `https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?eps%20Ind%20B` (refPos `2020yCat.1350....0G`, Gaia EDR3).
  - Datos de catálogo: ICRS, época J2000.0, RA 331.04414659, Dec −56.7828442; µα* = 3981,977 ± 0,602 y µδ = −2466,832 ± 0,626
    mas/año; paralaje 270,658 ± 0,690 mas.
  - (A) propaga de forma lineal desde J2000.0 (MJD 51544,5) hasta el `MJD-AVG` de cada frame y suma la paralaje anual en forma
    cerrada, con la posición baricéntrica de la Tierra. (R) usa la propagación rigurosa (`apply_space_motion`) y resta el vector
    baricéntrico de la Tierra.
  - Las dos coinciden a ≤ 0,04″ por temporada. La paralaje desplaza ≤ 0,26″ (≤ 0,04 px).
  - Control: propagada a 2016.0, la posición de Sesame coincide con Gaia DR3 a ≤ 0,04″: (+0,009, +0,015)″ en (A) y
    (+0,019, +0,030)″ en (R).
  - Posición predicha a la época media de cada temporada (movimiento propio + paralaje; columna de A):

    | Temporada | MJD medio | RA, Dec predichos (°) |
    |---|---|---|
    | S0 | 60804,92 | 331.095480, −56.800190 |
    | S1 | 60959,27 | 331.096108, −56.800555 |
    | S2 | 61155,18 | 331.097407, −56.800835 |
    | S3 | 61310,83 | 331.098075, −56.801221 |

  - Centro de `fields.toml` (331.09665, −56.80066) contra la posición solo con movimiento propio a MJD 61043,27: ≤ 0,07″
    (A: (−0,037, +0,016)″; R: (−0,062, −0,024)″; la diferencia viene del método de propagación).
- **Query RA, Dec / FOV / query date:**
  - Búsqueda: SIA2 de IRSA en (331.09665, −56.80066) con radio 1″, colecciones `spherex_dr1` + `spherex_qr3`. Respuesta cacheada
    por el build (`search_df6b83b76121bc3c02278d196ac26239.json`, creada el 2026-11-14 a las 18:42:20 UTC, sin overflow ni
    duplicados).
  - (R) repitió SIA en vivo el 2026-11-14 a las 19:24 UTC, en el centro de DATA.md (331.0964, −56.8006): 458 frames, el
    mismo conjunto.
  - Píxeles: patches S3 por Range de 13,5′ (los 40 frames del build) y de 6′ (los 458; 458 archivos, 59,7 MB en disco).
  - Grilla publicada: 88×88 px de 6,15″ (9,02′), TAN con norte arriba.
- **SPHEREx releases / observation IDs / MJDs / detectors / wavelengths:** 458 frames = 338 dr1 + 120 qr3, en 238 exposiciones,
  sin duplicados entre releases y con 19 versiones de pipeline. Por detector: D1 46 · D2 93 · D3 96 · D4 46 · D5 84 · D6 93.
  MJD 60789,856–61315,479. Los 40 frames del build, agrupados por temporada × detector (sin el sufijo `D`, con la λ en el
  objetivo en µm, VERIFICADA por A y R con `WCS-WAVE`):

  | Temporada | D1 | D2 | D3 | D4 | D5 | D6 |
  |---|---|---|---|---|---|---|
  | S0 | 2025W17_4B_0077_3 (0,756); 2025W17_4B_0468_1 (1,066) | 2025W18_2B_0489_2 (1,613); …_0489_3 (1,651) | 2025W19_1B_0344_4 (1,724); 2025W21_1B_0227_1 (1,764) | 2025W17_4B_0468_1 (3,642) | 2025W18_2B_0489_2 (4,390); …_0489_3 (4,424) | 2025W19_1B_0344_4 (4,495); 2025W21_1B_0227_1 (4,528) |
  | S1 | 2025W42_2A_0059_1 (0,767); 2025W43_1A_0019_1 (0,776) | 2025W43_2A_0023_1 (1,470); …_0023_2 (1,505) | 2025W41_1A_0052_1 (2,189); 2025W44_2B_0494_1 (1,740) | 2025W43_1A_0019_1 (2,532) | 2025W43_2A_0023_1 (4,248); …_0023_2 (4,285) | 2025W41_1A_0052_1 (4,847); 2025W44_2B_0494_1 (4,508) |
  | S2 | 2026W18_1A_0032_1 (0,870) | 2026W17_2A_0355_4 (1,400); 2026W17_2A_0403_1 (1,541) | 2026W18_1A_0529_1 (2,169); 2026W18_2A_0174_2 (1,644) | 2026W18_1A_0032_1 (2,883) | 2026W17_2A_0355_3 (4,139); …_0355_4 (4,175) | 2026W18_1A_0529_1 (4,833); 2026W18_2A_0174_2 (4,428) |
  | S3 (qr3) | — | 2026W40_1A_0518_1 (1,579); 2026W40_1A_0569_1 (1,120) | 2026W39_2A_0169_1 (1,886); …_0169_2 (1,929) | — | 2026W40_1A_0518_1 (4,359); 2026W40_1A_0569_1 (3,846) | 2026W39_2A_0169_1 (4,623); …_0169_2 (4,657) |

  En `field.json`, `wavelength_um` y `bandwidth_um` son null en los 40 frames.
- **Useful epochs / time baseline / coverage and quality flags:**
  - Épocas: 4 temporadas (bloques separados por > 30 d) y 74 visitas (huecos > 6 h). Línea de base: 1,439 años del primer al
    último frame, 1,385 años entre las medias de S0 y S3.
  - D1/D4 tienen 3 y 4 frames en S0 y ninguno en S3 (VERIFICADO).
  - Selección del build: `plan_frames` + `_round_robin` sobre la búsqueda cacheada reproduce exactamente los 40 ids de
    `field.json` (VERIFICADO por R). Son 2 frames por (temporada, detector), salvo S0D4, S1D4, S2D1 y S2D4, que tienen 1. No
    hubo descargas fallidas.
  - Tiempos: el `mjd` de `field.json` es igual al `MJD-AVG` del header (diferencia de 0,000 s), y SIA difiere en ≤ 0,026 s.
  - Flags en el núcleo 3×3 de los 40 frames: `SOURCE` 40, `HALO` 6, `TRANSIENT` 3, `NONFUNC` 1. No hay `OVERFLOW` ni
    `NONLINEAR`: el objetivo no satura. En los 458 frames, `NONLINEAR` no aparece nunca en el núcleo. `OVERFLOW` aparece en 2
    frames (2025W23_2B_0258_1D5 y 2026W39_1A_0276_2D6), en un píxel vecino que es NaN; el píxel central no está marcado.
  - `GHOST`/`GHOST_FPA`/`GHOST_EXT`: 0 píxeles en los 498 patches.
  - `HALO`: 5,0 % de los píxeles en promedio en los 40 patches de 13,5′, con un máximo de 26,9 %; en los de 6′ el máximo es
    31,2 %.
  - `BLOOM`: 0,58 % en los de 13,5′, siempre a ≤ 9,6 px de ε Ind A, y 0 en los de 6′.
  - NaN: ≤ 0,22 % por patch de 13,5′ (ninguno en el núcleo) y ≤ 0,38 % en los de 6′.
  - `TRANSIENT` aparece a ≤ 1 px del objetivo en 20/458 frames (4,4 %), la misma tasa que en discos al azar (4,2–4,5 %).
- **Alignment check / photometry or astrometry method / uncertainties:**
  - Método (A): ajuste Levenberg-Marquardt de una gaussiana circular integrada por píxel más una constante, en un stamp de
    7×7 px de `IMAGE − ZODI`, con peso 1/`VARIANCE` y los píxeles `DEFAULT_BAD` enmascarados; el centro se pasa a RA/Dec con la
    WCS TAN-SIP. Detección: SNR del ajuste ≥ 5, SNR de apertura ≥ 5, centro a ≤ 1,5 px de lo predicho.
  - Revisión independiente (R), con código propio (`review/r2_measure.py`, `r3_motion.py`):
    - re-midió los 40 patches de 13,5′ y los 458 de 6′;
    - ajuste de gaussiana elíptica supermuestreada 5×5 más una constante, en un stamp de 9×9, más un centroide con ventana
      gaussiana (tipo XWIN) como segundo método;
    - punto cero propio con estrellas Gaia DR3 (G ≤ 18, aisladas, SNR ≥ 10, a > 90″ de ε Ind A);
    - predicción con propagación rigurosa y paralaje;
    - comprobó que el resultado no depende del punto de partida del ajuste: al partir de una posición fija, 435/441 frames dan
      el mismo centroide, y S0 y S3 cambian ≤ 0,001″.
  - Punto cero del WCS por temporada, con estrellas de los patches de 6′ (cada valor ± 0,02–0,03″):

    | Temporada | (A) | (R) |
    |---|---|---|
    | S0 | (+0,027, +0,100)″ | (−0,003, +0,057)″ |
    | S1 | (−0,055, +0,025)″ | (−0,098, −0,078)″ |
    | S2 | (+0,025, +0,062)″ | (−0,013, +0,086)″ |
    | S3 | (−0,076, +0,014)″ | (−0,100, −0,066)″ |

    El punto cero depende del método de centroide en ~0,1″. El WCS es estable a ≤ ~0,15″ (≤ 0,025 px) entre temporadas, con
    una alternancia en Dec entre S0/S2 y S1/S3.
  - Punto cero por frame en los patches de 13,5′: (A) 25 frames con ≥ 5 estrellas, dispersión (0,118, 0,109)″; (R) 35 frames,
    dispersión (0,141, 0,130)″ y máximo 0,40″.
  - Dispersión por frame del objetivo respecto del modelo lineal: (0,20–0,27)″ ≈ 0,04 px.
  - Errores de las medias por temporada: dispersión interna / √n, combinada con el error del punto cero. Entre detectores se
    tomó el mayor entre el error formal y la dispersión.
  - Sistemático estimado: ~0,1″ por componente (~0,016 px). Sale de la diferencia entre variantes y de la dependencia del punto
    cero con el método.
- **Expected behavior / observed behavior:**
  - Esperado: una fuente única (Ba+Bb), sin saturar (J = 11,9, K = 11,2), que se desplaza ~1,1 px (6,7″) del primer al último
    frame hacia el SE (movimiento propio a PA 121,8°; con paralaje, entre las medias de S0 y S3, 1,03 px a PA ≈ 126°).
  - Observado (VERIFICADO por A y R): la fuente aparece en todos los detectores y temporadas, salvo en D1 por debajo de
    ~0,83 µm.
  - El desplazamiento S0→S3 coincide con el esperado en magnitud (cociente 1,002 en A y 0,996 en R) y en dirección
    (diferencia de PA 0,7–0,8 ± 0,4°). Todos los pares de temporadas coinciden con lo esperado dentro de ≤ 0,19″ (A) y ≤ 0,12″
    (R) por componente.
  - En los apilados por temporada de R (`rev_fig1`), el máximo sigue la trayectoria del catálogo, y la diferencia S3 − S0 es un
    dipolo azul al NO y rojo al SE centrado en las posiciones del catálogo.
- **Result:** success. El movimiento propio de ε Indi B se detecta en las imágenes SPHEREx con la magnitud y la dirección
  esperadas: 1,026–1,031 px medidos contra 1,028–1,030 px esperados, con ~0,007 px de error estadístico y ~0,016 px de
  sistemático. Frente a “sin movimiento”, son 158–174σ estadísticos y > 50σ con el sistemático incluido. Lo confirman dos
  análisis independientes. No es un descubrimiento: se recupera un movimiento conocido.
- **Limitations and failed downloads:**
  - Descargas: 0 fallidas (40/40 del build y 458/458 de 6′). El tiempo de bajada (267,8 s) viene del log de A y no se volvió a
    medir.
  - No detecciones en D1 por debajo de ~0,83 µm: 15 (R) o 16 (A) frames, según el criterio. Entre 0,81 y 0,85 µm la SNR de
    apertura es 4–9; desde 0,85 µm, ≥ 13. INFERIDO: espectro de enana T.
  - 2 frames con el núcleo enmascarado por `SUR_ERROR`:
    - 2025W45_2A_0315_1D2: el objetivo se ve (SNR de apertura 74), pero el centroide no se puede medir;
    - 2026W39_2A_0659_1D6: a 4,975 µm.
  - En 6 frames de S1/S2 (5 D1 con SNR baja y 1 D4), el ajuste depende del stamp; no afectan S0→S3.
  - Offset constante centroide − catálogo de ≈ (+0,2, −0,6)″, mayor en D6: (+0,37, −0,73)″. No aparece en las estrellas de
    campo. INFERIDO, sin verificar: el fotocentro infrarrojo de Ba+Bb difiere del fotocentro de Gaia, o el movimiento orbital del
    par desde 2016 no está en la propagación lineal (Gaia RUWE 4,3).
  - Residuo en Dec que alterna entre S0/S2 y S1/S3 (~0,05–0,15″, ≈ 0,01–0,025 px), con el patch girado ~180°: ε Ind A cae en
    x ≈ 123–127 px en S0/S2 y en x ≈ 4–10 px en S1/S3. INFERIDO: un sistemático de centroide o WCS que depende de la
    orientación.
  - El movimiento propio medido es instantáneo (2025–2026); no se modeló la órbita Ba–Bb.
  - Los 40 frames publicados usan 1–2 frames por (temporada, detector) y no tienen λ en `field.json`.
- **Product field ID / public URL / screenshot or animation:**
  - Field ID: `eps-indi-b` (`data/products/fields/eps-indi-b/`). URL pública: pendiente del deploy (WS4).
  - Recorrido revisado solo en la vista local `/?dataset=real#/field/eps-indi-b` (paso 6 de VALIDATION.md pendiente en la URL pública).
  - Figuras (gráficos generados con código a partir de los FITS reales de SPHEREx):
    - [rev_fig1_season_stacks.png](figures/eps-indi-b/rev_fig1_season_stacks.png): Revisión: apilados por temporada con las posiciones de catálogo y el dipolo S3 − S0
    - [rev_fig2_residuals.png](figures/eps-indi-b/rev_fig2_residuals.png): Revisión: residuos por frame y trayectoria
    - [rev_fig3_flux_lambda.png](figures/eps-indi-b/rev_fig3_flux_lambda.png): Revisión: flujo frente a λ (forma de enana T)
    - [rev_fig4_published_pngs.png](figures/eps-indi-b/rev_fig4_published_pngs.png): Revisión: PNG publicados con el píxel predicho
    - [rev_fig5_ws2_compare.png](figures/eps-indi-b/rev_fig5_ws2_compare.png): Revisión: diferencias de `errante compare` (WS2)
    - [fig1_season_stamps_all.png](figures/eps-indi-b/fig1_season_stamps_all.png): Análisis original: stamps por temporada
    - [fig2_centroids_all.png](figures/eps-indi-b/fig2_centroids_all.png): Análisis original: centroides por frame
    - [fig3_ws2_differences.png](figures/eps-indi-b/fig3_ws2_differences.png): Análisis original: diferencias de WS2
    - [fig4_flags_epsA.png](figures/eps-indi-b/fig4_flags_epsA.png): Análisis original: flags y halo de ε Ind A
    - [fig5_flux_vs_wavelength_all.png](figures/eps-indi-b/fig5_flux_vs_wavelength_all.png): Análisis original: flujo frente a λ
    - [fig6_built_pngs_D1_D2_D3.png](figures/eps-indi-b/fig6_built_pngs_D1_D2_D3.png): Análisis original: PNG publicados D1–D3 (frames D1 sin objetivo, salto de fondo)
    - [fig7_ui_localhost_eps-indi-b.jpg](figures/eps-indi-b/fig7_ui_localhost_eps-indi-b.jpg): Análisis original: captura de la UI local

- **Reviewer / date:** Claude (WS1) con revisión adversarial independiente / 2026-11-14; revisión humana pendiente

## Detalle de la medición

### Método

1. **Astrometría:**
   - (A) `s1_astrometry_coverage.py`: Sesame CfA, control contra Gaia DR3 y propagación lineal más paralaje.
   - (R) `review/r2_measure.py`: Sesame repetido, propagación rigurosa con astropy y paralaje por vector baricéntrico.
   - Identidad (R): conos en Gaia DR3, 2MASS y AllWISE en VizieR CfA (`review/cat/`).
2. **Cobertura:**
   - (A) `s1` y (R) `review/r1_coverage.py`: `irsa.search_frames_report` desde la caché y temporadas por huecos > 30 d.
   - (R) `review/r8_selection.py`: repite `plan_frames` + `_round_robin`.
   - (R) `review/r9_count.py`: SIA en vivo en el centro de DATA.md.
3. **Medición por frame:**
   - (A) `measure.py` y `s2_frames.py`.
   - (R) `review/r2_measure.py`, con ajuste propio y estrellas Gaia propias, en los 40 patches de 13,5′ y en los 458 de 6′.
4. **Análisis temporal:**
   - (A) `s3_motion.py` y `s3b_differential.py`.
   - (R) `review/r3_motion.py`: medias por temporada, pares con el mismo detector, variantes (punto cero por temporada, por frame
     o ninguno; dos centroides) y ajuste de movimiento propio con offset por detector y jackknife por temporada.
5. **Controles (R):**
   - `review/r4_checks.py`: flags, ε Ind A, tiempos, salto de fondo.
   - `review/r10_flux.py`: espectro y frontera D1.
   - `review/r11_nan.py`: NaN y `BLOOM`.
   - `review/r12_start.py`: dependencia del punto de partida del ajuste.
   - `review/r6_spot.py`: una “fuente” compacta a ~14″ en un apilado sin máscara resultó ser píxeles `SUR_ERROR`/`PERSIST` de un
     solo frame (2026W39_2A_0155_2D6). Está enmascarada en las mediciones; no es una fuente del cielo.
6. **WS2:** `errante compare eps-indi-b --dir <scratch>/products` sobre copias del campo, en A y en R (`review/products`).

### Cobertura por temporada (búsqueda: 458 frames)

| Temporada | MJD (fechas) | n | dr1/qr3 | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|---|---|---|
| S0 | 60789,86–60836,19 (2025-04-24 → 2025-06-10) | 118 | 118/0 | 3 | 32 | 25 | 4 | 30 | 24 |
| S1 | 60946,96–60991,86 (2025-09-28 → 2025-11-12) | 146 | 146/0 | 24 | 30 | 23 | 23 | 24 | 22 |
| S2 | 61148,85–61164,12 (2026-04-18 → 2026-05-04) | 74 | 74/0 | 19 | 7 | 12 | 19 | 6 | 11 |
| S3 | 61305,23–61315,48 (2026-09-22 → 2026-10-02) | 120 | 0/120 | 0 | 24 | 36 | 0 | 24 | 36 |

### Detecciones

- Frames del build: 37/40.
  - SNR de apertura 27–197 y SNR del ajuste 21–92; los valores exactos dependen del método.
  - El centro ajustado queda a ≤ 0,18 px del píxel predicho, incluido el offset constante de ~0,1 px.
  - Las 3 no detecciones son D1 a 0,756, 0,767 y 0,776 µm (SNR de apertura ≈ 0).
- Los 458 frames, por detector (A / R):

  | Detector | D1 | D2 | D3 | D4 | D5 | D6 |
  |---|---|---|---|---|---|---|
  | Detectados / total | 30/46 / 31/46 | 92/93 | 96/96 | 46/46 | 84/84 | 92/93 |

- **Identidad (VERIFICADO; interpretación INFERIDA):** el flujo de apertura frente a λ (`rev_fig3`, 458 frames) tiene forma de
  enana T. Máximos en ~1,06, 1,26–1,30, 1,58, 2,10 y 4,02–4,06 µm; mínimos en ~1,14, 1,38–1,42, 1,86 y 2,5–3,3 µm; flujo nulo
  en D1 por debajo de ~0,83 µm.
- **Repetibilidad:** a igual λ, temporadas distintas dan el mismo flujo. Entre 1,216 y 1,217 µm: 32,3 y 30,2 en S0, 31,7 en S1 y
  31,0 en S3 (MJy/sr·px).

### Posición por temporada

Medido − catálogo (pm + paralaje), en ″, con el punto cero por temporada aplicado; para R, ± error estándar:

| Temporada | n (A/R) | MJD medio | (A) | (R) |
|---|---|---|---|---|
| S0 | 117/117 | 60805,05 | (+0,238, −0,596) | (+0,252 ± 0,017, −0,582 ± 0,019) |
| S1 | 135/135 | 60958,30 | (+0,205, −0,673) | (+0,223 ± 0,021, −0,637 ± 0,026) |
| S2 | 69/70 | 61155,4 | (+0,197, −0,525) | (+0,232 ± 0,031, −0,584 ± 0,028) |
| S3 | 119/119 | 61310,83 | (+0,208, −0,661) | (+0,189 ± 0,035, −0,637 ± 0,026) |

El offset por detector (R) es de (+0,14…+0,26, −0,55…−0,64)″ en D1–D5 y de (+0,37, −0,73)″ en D6, con errores de 0,02–0,06″.

### Desplazamiento entre temporadas

Mismo detector en ambas temporadas, punto cero por temporada y paralaje incluido en lo medido y en lo esperado:

| Par | Detectores | (A) \|d\| (″) | (R) \|d\| (″) / px | (R) PA | Esperado (R) ″ / px, PA | (R) medido − esperado (ΔRA*, ΔDec ″) |
|---|---|---|---|---|---|---|
| S0→S1 | D1–D6 | 1,856 ± 0,041 | 1,827 ± 0,030 / 0,297 ± 0,005 | 138,0 ± 0,9° | 1,801 / 0,293, 136,2° | −0,023, −0,056 |
| S1→S2 | D1–D6 | 2,740 ± 0,035 | 2,790 ± 0,044 / 0,454 ± 0,007 | 110,6 ± 1,3° | 2,768 / 0,450, 111,9° | +0,044, +0,051 |
| S2→S3 | D2,D3,D5,D6 | 1,855 ± 0,090 | 1,759 ± 0,082 / 0,286 ± 0,013 | 138,5 ± 2,5° | 1,866 / 0,303, 136,4° | −0,122, +0,033 |
| S0→S2 | D1–D6 | 4,525 ± 0,069 | 4,567 ± 0,046 / 0,743 ± 0,007 | 121,8 ± 0,7° | 4,507 / 0,733, 121,6° | +0,042, −0,047 |
| S1→S3 | D2,D3,D5,D6 | 4,561 ± 0,036 | 4,558 ± 0,038 / 0,741 ± 0,006 | 122,0 ± 0,5° | 4,582 / 0,745, 121,7° | −0,034, −0,009 |
| **S0→S3** | D2,D3,D5,D6 | **6,338 ± 0,039 (1,031 ± 0,006 px), PA 126,7 ± 0,4°** | **6,307 ± 0,040 / 1,026 ± 0,007** | **126,5 ± 0,4°** | 6,332 / 1,030, 125,8° | −0,062, −0,044 |

- **S0→S3 por detector (R)** (medido / esperado, en ″): D2 6,245 ± 0,064 / 6,296; D3 6,259 ± 0,062 / 6,354;
  D5 6,329 ± 0,131 / 6,299; D6 6,356 ± 0,056 / 6,351.
- **Variantes de S0→S3, todos los frames (R):**
  - sin punto cero (WCS absoluto): 6,303 ± 0,036″ (1,025 px), PA 128,0 ± 0,3°; en A, 6,313 ± 0,036″ (1,026 px);
  - centroide con ventana: 6,309 ± 0,071″ (1,026 px);
  - punto cero por frame: 6,283 ± 0,059″ (1,022 px).
- **Solo los 40 frames del build:**
  - (R), desplazamiento en el cielo con paralaje: 6,348 ± 0,095″ = 1,032 ± 0,016 px, PA 126,4 ± 0,9°, contra 6,367″
    (1,035 px) esperados; con el mismo detector, 6,317 ± 0,084″ contra 6,321″.
  - (A) informó 6,507 ± 0,079″ = 1,058 ± 0,013 px contra 6,527″, pero **con la paralaje del catálogo restada a lo medido**: es
    el desplazamiento por movimiento propio solo, no el desplazamiento en el cielo. Las dos cifras son coherentes.
- **Movimiento propio ajustado** (paralaje del catálogo restada, offset por detector; error = el mayor entre el formal y el
  jackknife por temporada):

  | Ajuste | µα* (mas/año) | µδ (mas/año) |
  |---|---|---|
  | (A), 440 frames | 3954 ± 18 | −2473 ± 71 |
  | (R), 441 frames | 3935 ± 39 | −2482 ± 43 |
  | (R), 40 frames | 3953 ± 71 | −2487 ± 55 |
  | Catálogo | 3982 ± 0,6 | −2467 ± 0,6 |

  Δ(R) = (−47, −15) mas/año, es decir 1,2σ y 0,35σ. |µ| vale 4652 (R) y 4664 (A), contra 4684; PA 122,2° (R) contra 121,8°.

### WS2 (`errante compare`, copia en scratch; reproducido por R)

- `errante compare` produjo 22 coadds (1–2 frames cada uno) y 30 diferencias.
- D2/D3/D5/D6 S3−S0 muestran el dipolo NO→SE esperado (`rev_fig5`).
- Escalas de flujo:
  - ajustadas en D2 y D3 S3−S0 (0,793 y 0,800);
  - sin ajustar en 8 pares (D5 S1−S0, S2−S0, S3−S0, S2−S1; D6 S3−S0, S2−S1, S3−S1, S3−S2), con 2–4 estrellas y s = 1;
  - D4 S2−S0 (s = 1,494) y D4 S1−S0 (s = 1,798) dejan un residuo casi solo negativo, porque la λ del frame D4 cambia (3,64 µm
    frente a 2,88 y 2,53 µm) y el color de la enana T no es el de las estrellas.
- El coadd D1_S1 solo tiene frames a 0,767–0,776 µm, sin objetivo: la diferencia D1 S1−S0 es solo “desaparición”.

## Problemas encontrados

1. **`wavelength_um` es null en la búsqueda (458/458) y en `field.json` (40/40).**
   - `build.py` copia `ref.wavelength_um`, aunque `WCS-WAVE` está en cada patch y `wavelength_at` funciona. Por eso el ranking
     por λ de `plan_frames` no actúa.
   - La UI cae a la banda nominal (`BlinkViewer.tsx` usa `DETECTOR_BANDS`).
   - Dueños: WS1 + WS2 (`build.py`, coordinar con WS4); WS5 en la UI.
2. **La selección incluye frames D1 a λ < ~0,83 µm sin el objetivo.**
   - Son 3 de los 5 D1 publicados, entre ellos los dos de S1. El objetivo “desaparece” en el blink D1, y los coadds y
     diferencias D1 de WS2 pierden sentido.
   - Dueño: WS2 (selección), con WS3 (λ útil por objetivo; para enanas T, λ ≥ 0,85 µm en D1).
3. **2025W17_4B_0468_1D1 tiene un salto de fondo.**
   - `IMAGE − ZODI` tiene mediana 2,175 MJy/sr, contra 0,078–0,120 en los otros D1, con un borde diagonal (medianas por fila de
     0,25 a 4,01).
   - El stretch tiene un ancho común por detector y está anclado al fondo de cada frame (vmin 1,538). El 39 % de los píxeles,
     incluida la vecindad del objetivo (fondo local 1,51), sale negro.
   - `HE_AIRGLOW_CONT = True` aparece en los 5 D1 del build, así que la bandera sola no lo distingue.
   - El objetivo sí se detecta (SNR de apertura 44). Causa INFERIDA: airglow o luz parásita.
   - Dueños: WS2 (render y QA del fondo) y WS1 (exponer las claves de contaminación).
4. **La UI no marca el objetivo ni su posición predicha por época.**
   - `known.json` y `candidates.json` están vacíos. `BlinkViewer` solo dibuja desde esos archivos y la retícula es
     `TODO(WS5)`. La leyenda dice “catalog prediction”, pero no se dibuja nada.
   - En la grilla, el objetivo pasa de (43,88; 43,21) px en S0 a (43,04; 43,82) px en S3: 1,07 px entre el primer y el último
     frame. Sin marcador no se puede comprobar (SCIENCE.md §0.2).
   - Dueños: WS3 (trayectoria predicha de los blancos oficiales) y WS5 (overlay).
5. **WS2 compare:**
   - 8 pares sin escala de flujo ajustada en D5/D6, por falta de estrellas;
   - sobrecorrección por color en D4 (s = 1,49 y 1,80);
   - coadds de 1–2 frames;
   - D1_S1 sin objetivo.
   - `compare.json` sigue siendo provisional. Dueño: WS2.
6. **Conteo de DATA.md §3.0 y SCIENCE.md §0.2:** dicen 460 frames (340/120; por temporada 120/147/73/120).
   - SIA en vivo el 2026-11-14 a las 19:24 UTC da 458 (338/120; 118/146/74/120), con el mismo conjunto en el centro de DATA.md
     y en el del campo.
   - Queda **refutada** la explicación de “2 frames dr1 en el borde de un footprint por otro centro de consulta”. La causa no
     está verificada: posible combinación SIA2+TAP o un cambio del índice de IRSA.
   - Conviene anotar servicio, centro y fecha de cada conteo. Dueño: WS1, con el coordinador para SCIENCE.md.

Sin problema (VERIFICADO por A y R):

- ε Ind A (a 402,6″ al oeste) queda dentro de los patches de 13,5′, a 63,5–66,7 px, pero fuera de la grilla publicada de 9′
  (semiancho 270,6″). Su halo se ve en el borde oeste (derecho) de los PNG revisados y está marcado `HALO`; el `BLOOM` es suyo.
- No hay píxeles GHOST.
- Tiempos: el `mjd` de `field.json` es igual a `MJD-AVG`.
- No hay fuentes de catálogo que contaminen la trayectoria del objetivo.
