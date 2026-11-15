# Validación: Barnard's Star

> **Vigencia (2026-11-15).** Se analizó el campo publicado en `main` (`4af29e3`; `field.json` construido por #17 el 2026-11-14 a las 18:53:08 UTC, 40 frames) y las **358** exposiciones SPHEREx que cubren la posición:
> - el análisis original (A) las leyó de S3 el 2026-11-14 desde las 23:44 UTC;
> - la revisión adversarial independiente (R), con código propio, las volvió a leer el 2026-11-15 desde las 00:24 UTC.
>
> Las dos búsquedas fueron SIA2 en vivo. No se usó el snapshot versionado, que da el mismo conjunto.
>
> Los scripts y la caché de A y de R quedaron en el scratch local de la sesión de Claude y no se versionan («scratch local» abajo; los de R están en `review/`). scipy 1.18.1 y matplotlib 3.11.2 se instalaron en ese scratch, fuera del venv del repo, y A y R usan esas mismas bibliotecas. Las figuras van en [`figures/barnards-star/`](figures/barnards-star/). Revisión humana pendiente.

**Resultado: success.** Se ensayó el movimiento propio de Barnard's Star (Gaia DR3 4472832130942575872) con las 358 exposiciones SPHEREx que cubren la posición: DR1 + QR3, 3 temporadas, del 2025-08-15 al 2026-09-22. La estrella **satura** (VERIFICADO por A y R, con los mismos conteos):
- `OVERFLOW` en el núcleo en 357 de 358 exposiciones (1–11 px a ≤ 3 px);
- `NONLINEAR` nunca;
- un anillo de `SUR_ERROR` + `TRANSIENT` + `BLOOM` alrededor del núcleo.

La astrometría sale del ala de la PSF, con dos métodos independientes:
- (A) una gaussiana integrada por píxel, con `OVERFLOW`, NaN y `SUR_ERROR` enmascarados y la caja re-centrada en la solución;
- (R) un perfil radial libre, sin modelo de PSF salvo la simetría circular, con la zona saturada dilatada 1 px y `SUR_ERROR` enmascarados.

El WCS de cada exposición se refirió a estrellas Gaia DR3 de campo, con selecciones propias en A y en R. Es estable a 0,014–0,017 px, salvo un frame corrido 0,27–0,28 px.

Entre S0 y S2, con la misma orientación del detector y casi la misma fase de paralaje:
- (A): **10,238 ± 0,061 (est.) ± 0,110 (total)″ = 1,665 ± 0,018 px a PA 354,1 ± 2,1°**;
- (R): **10,179 ± 0,081 (est.) ± 0,086 (total)″ = 1,655 ± 0,014 px a PA 355,4 ± 0,6°**;
- esperado con movimiento propio + paralaje: **10,237″ = 1,665 px a PA 355,7°**.

«Sin movimiento» queda descartado a 93σ (A) y a 119σ (R), con el sistemático incluido. El movimiento propio desde S0→S2 es:
- (A): (−1099 ± 380, +10350 ± 106) mas/año;
- (R): (−858 ± 117, +10311 ± 87) mas/año;
- catálogo: (−803, +10375) mas/año.

**Corrección de la revisión.** A encontró un residuo hacia el oeste de −0,29 a −1,01″ en E en todas sus variantes. Ese residuo depende del estimador:
- R lo reproduce con su propia gaussiana: −0,23″ con `SUR_ERROR` enmascarado y −0,71″ si se conserva;
- con el perfil radial libre queda en −0,01 a −0,09″.

No hace falta invocar una diferencia entre DR1 y QR3. La causa más probable es el desajuste del modelo gaussiano en el ala de un núcleo saturado (INFERIDO).

S1 tiene el detector girado 180°, y ese giro coincide con la fase de paralaje:
- según el estimador, S1 queda corrida entre −0,66 y +1,35″ en E respecto de la media de S0 y S2 (hasta 0,22 px);
- es un sesgo del centroide en coordenadas del detector, degenerado con la paralaje;
- la paralaje no se puede medir aquí.

No es un descubrimiento: se recupera un movimiento conocido. En los 40 PNG publicados el movimiento está: el centroide de la meseta saturada se mueve 1,60 px contra 1,68 px esperados (A y R). Pero Barnard es un disco blanco de ~7 px y la UI no marca la posición, así que a simple vista cuesta verlo.

Convención: **VERIFICADO** = medido en esta sesión (script en scratch); **INFERIDO** = interpretación no comprobada; 🧮 = cálculo. (A) = análisis original; (R) = revisión adversarial independiente, con código propio.

- **Target / resolved catalog ID:** Barnard's Star = `NAME Barnard's star` (SIMBAD oid 2669393, tipo `BY*`, M4V).
  - Resuelta con Sesame de CfA por A (2026-11-14 23:42:59 UTC) y por R (2026-11-15 00:21:58 UTC), con los mismos valores.
  - Gaia DR3 4472832130942575872 (archivo Gaia de ESA): G = 8,194, BP = 9,792, RP = 6,958, RUWE 1,085.
  - J = 5,24 y K = 4,52 vienen del encargo y no se reconsultaron.
  - ⚠️ Sesame con el nombre `GJ 699` responde solo con VizieR local: 17:57:51.47 +04:33:03.2, a 514,8″ (8,6′) de la posición J2000 de Barnard, una posición de época antigua (VERIFICADO por R). Conviene resolver con «Barnard's Star» o con el `source_id` de Gaia.
  - Identidad de la fuente medida (VERIFICADO por A y R; R corrige el detalle de Gaia):
    - es la fuente dominante en todas las exposiciones, con el núcleo saturado;
    - se mueve 10,2″ entre S0 y S2 como predice Gaia (no es una estrella de fondo), y a ≤ 5 px no hay píxeles `GHOST*`, `STREAK` ni `SNOWBALL`;
    - Gaia DR3 (cono de R de 0,25°, todas las magnitudes, 15 408 fuentes): la fuente más cercana a la trayectoria tiene G = 20,90. Está a 2,0″ en S0, 5,2″ en S1 y 10,0″ en S2: es 12,7 mag más débil.
      - A ≤ 30″, la más brillante tiene G = 16,70 en S0/S1, y G = 14,98 en S2 (a 28,4″). Todas son ≥ 6,8 mag más débiles en G.
      - A informó «la más cercana, G = 16,7 a 17,8″» porque su cono llegaba solo a G < 19,5;
    - 2MASS (VizieR CfA `II/246`, cono de 60″ alrededor del centro del campo; A a las 23:54:52 UTC y R a las 00:34:56 UTC): la fuente más cercana está a 21,3″ (J = 16,03) y la más brillante a 31,1″ (J = 13,16), ≥ 7,9 mag más débiles en J. Barnard no está en ese cono: 🧮 en la época de 2MASS (~2000) estaba ~4,5′ al sur.
- **Astrometry source URL / reference epoch / propagation:** `https://gea.esac.esa.int/tap-server/tap/sync`, ADQL sobre `gaiadr3.gaia_source` con `source_id = 4472832130942575872` (A a las 2026-11-14 23:42:56 UTC; R a las 2026-11-15 00:21:47 UTC, con los mismos valores).
  - Gaia DR3, época 2016.0: RA 269.4485025254, Dec +4.7394200511; µα* = −801,551 ± 0,032 y µδ = +10362,394 ± 0,036 mas/año; paralaje 546,976 ± 0,040 mas; RV −110,47 ± 0,13 km/s.
  - Control con Sesame CfA (`https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?Barnard%27s%20Star`, refPos `2020yCat.1350....0G`): J2000 269.45207696 +4.69336497, el mismo movimiento propio y paralaje 546,9759 mas.
    - Propagada linealmente a 2016.0 coincide con Gaia DR3 a 0,000″ (A y R): es Gaia retropropagada sin RV.
    - Con propagación rigurosa y la RV de Sesame (−110,11 km/s), se separa (−0,014, +0,164)″ (R; A: 0,16″ en Dec). Es la aceleración de perspectiva.
  - Los valores aproximados del encargo (−798,6 y +10328,1 mas/año; 548,3 mas) no coinciden con DR3 y no se usaron.
  - Propagación a `MJD-AVG`:
    - (A): `SkyCoord.apply_space_motion` (astropy 8.0.2) con distancia 1/paralaje y RV, menos el vector baricéntrico de la Tierra (`get_body_barycentric`);
    - (R): implementación propia de las fórmulas rigurosas de Gaia, con la Tierra de ERFA `epv00`;
    - las dos coinciden a < 0,0001″ en los 358 frames (VERIFICADO por R);
    - la aceleración de perspectiva suma +0,066″ en Dec a la época media;
    - la órbita baja de SPHEREx no se modeló: 🧮 ~700 km cambian la paralaje en ~3e-6″;
    - es la posición astrométrica, sin aberración: la aberración es común a las estrellas de campo y la absorbe el punto cero de cada exposición.
  - Paralaje: semiamplitud de 0,548″ en E y 0,259″ en N (≤ 0,089 px). Por temporada: S0 (−0,504, +0,108)″, S1 (+0,546, −0,001)″ y S2 (−0,477, +0,135)″ (A y R).
  - Posición predicha a la época media de cada temporada (pm + paralaje; A y R coinciden en las 6 cifras):

    | Temporada | MJD medio | RA, Dec predichos (°) |
    |---|---|---|
    | S0 | 60916,19 | 269.446203, +4.767268 |
    | S1 | 61119,45 | 269.446371, +4.768841 |
    | S2 | 61274,63 | 269.445991, +4.770103 |

  - Centro de `fields.toml` (269.44623, +4.76870), comparado a MJD 61104 (la época media de los 358 frames es 61104,04):
    - contra la posición rigurosa solo con pm: (+0,006, −0,070)″. Es la aceleración de perspectiva que omite la propagación lineal de SCIENCE.md §0.2;
    - contra pm + paralaje: (−0,518, −0,001)″;
    - las dos diferencias son menores que 0,1 px (A y R).
- **Query RA, Dec / FOV / query date:**
  - Búsqueda: SIA2 de IRSA en vivo con `errante.data.irsa.search_frames_report`, sin caché ni snapshot, en (269.44623, +4.76870), con radio 1″ y colecciones `spherex_dr1` + `spherex_qr3`.
    - A la corrió el 2026-11-14 a las 23:44:30 UTC; R el 2026-11-15 a las 00:22:44 y otra vez a las 00:24:29 UTC.
    - Resultado: 358 frames, servicio `sia`, sin overflow ni duplicados.
    - Repetida en las posiciones predichas del primer y del último frame (269.446228, +4.767177 y 269.445952, +4.770312; A y R): el mismo conjunto.
    - El snapshot versionado `data/index/search/barnards-star.json` reproduce exactamente ese conjunto (`load_snapshot().replay`; A y R).
  - Píxeles:
    - (A): stamps de 25 px (2,56′) de `point.point_series` en el centro del campo, 358/358 en 17,8 s (3,2 s de SIA + 14,6 s de S3, 2848 requests); patches S3 de 10′ (16 hilos), 358/358 en 59,2 s;
    - (R): `point_series`, 358/358 en 20,3 s (6,0 s de búsqueda + 14,1 s de S3, 1790 requests; los tiempos dependen del entorno); 2 stamps salen recortados (19×25 y 21×25). Patches S3 propios de 12′, 358/358 en 68,2 s (16 hilos, 134 MB).
  - Estrellas de referencia:
    - (A): cono Gaia DR3 de 0,2° con G < 19,5 (4627 fuentes; 23:43:01 UTC);
    - (R): cono de 0,25° con todas las magnitudes (15 408 fuentes; 2026-11-15 00:21:49 UTC).
  - Grilla publicada: 88×88 px de 6,15″ (9,02′), TAN con norte arriba.
- **SPHEREx releases / observation IDs / MJDs / detectors / wavelengths:** 358 frames = 239 dr1 + 119 qr3, en 181 exposiciones (`obs_id`), con 17 versiones del pipeline y sin duplicados entre releases (A y R).
  - Por detector: D1 60 · D2 61 · D3 59 · D4 59 · D5 61 · D6 58. MJD 60902,865–61305,629.
  - λ en la posición predicha (`WCS-WAVE`): D1 0,741–1,107 · D2 1,088–1,661 · D3 1,625–2,411 · D4 2,419–3,800 · D5 3,804–4,430 · D6 4,412–5,002 µm.
  - Los 40 frames del build por temporada × detector, sin el sufijo `D`. La λ va en µm en la posición predicha; R reprodujo los 40 ids y sus λ a 0,001 µm:

  | Temporada | D1 | D2 | D3 | D4 | D5 | D6 |
  |---|---|---|---|---|---|---|
  | S0 | 2025W35_2A_0611_4 (0,993); 2025W36_1A_0024_1 (1,017); 2025W36_2B_0123_1 (0,904) | 2025W35_1A_0146_2 (1,553); …_0146_3 (1,591); …_0146_4 (1,629) | 2025W34_2B_0030_3 (1,917); …_0030_4 (1,961) | 2025W36_1A_0024_1 (3,449); 2025W36_2B_0123_1 (3,014) | 2025W35_1A_0146_3 (4,370); …_0146_4 (4,407) | 2025W34_2B_0030_3 (4,647); …_0030_4 (4,681) |
  | S1 | 2026W11_1A_0511_1 (0,804); …_0511_2 (0,823); …_0511_3 (0,843) | 2026W12_1A_0311_3 (1,379); …_0311_4 (1,412) | 2026W13_1A_0549_1 (1,779); 2026W15_2A_0137_1 (1,793) | 2026W11_1A_0511_1 (2,637); …_0511_2 (2,708) | 2026W12_1A_0311_3 (4,151); …_0311_4 (4,187) | 2026W13_1A_0549_1 (4,540); 2026W15_2A_0137_1 (4,551) |
  | S2 (qr3) | 2026W35_2A_0412_1 (0,936); …_0412_2 (0,958); …_0412_3 (0,982) | 2026W35_1A_0092_1 (1,614); 2026W35_2A_0126_1 (1,653) | 2026W34_1A_0308_3 (1,938); …_0308_4 (1,983) | 2026W35_2A_0412_1 (3,140); …_0412_2 (3,226) | 2026W35_1A_0092_1 (4,393); 2026W35_2A_0126_1 (4,430) | 2026W34_1A_0308_3 (4,664); …_0308_4 (4,698) |

  - El `wavelength_um` de `field.json` está calculado en el centro del campo. Es igual al de `WCS-WAVE` y al de `point_series` (diferencia 0,0000 nm). En la posición predicha de Barnard, λ cambia ≤ 0,73 nm (mediana 0,22 nm) en los 358 frames (A y R).
- **Useful epochs / time baseline / coverage and quality flags:**
  - Épocas:
    - 3 temporadas, con huecos de 160,8 y 103,5 d;
    - 48 visitas (huecos > 6 h): 18 en S0, 14 en S1 y 16 en S2;
    - S0 y S1 son dr1; S2 es qr3;
    - línea de base: 402,76 d (1,103 años) del primer al último frame; 358,44 d (0,981 años) entre las medias de S0 y S2.
  - Orientación (VERIFICADO por A y R con el jacobiano del WCS):
    - S0 y S2 tienen la misma: la x del detector apunta casi al E (dE/dx = +6,14″/px);
    - S1 está girada 180° (dE/dx = −6,15″/px);
    - el giro coincide con el cambio de signo de la paralaje.
  - Saturación a ≤ 3 px de la posición predicha (VERIFICADO por A y R, con los mismos conteos; tabla por detector abajo):
    - `OVERFLOW` en 357/358 exposiciones. La única sin `OVERFLOW` es 2025W34_2B_0030_1D6 (4,58 µm);
    - `NONLINEAR` no aparece nunca;
    - NaN en 240 exposiciones, siempre junto con `OVERFLOW`; en D5/D6 solo hay NaN en 4 de 119;
    - píxeles `OVERFLOW` con valor finito en 339 exposiciones;
    - D1 a la λ más corta satura menos: media de 2,3 px `OVERFLOW` a < 0,80 µm, contra 5,0 a ≥ 1,00 µm. Ningún frame D1 queda libre de `OVERFLOW`.
  - Flags alrededor del núcleo:
    - anillo de `SUR_ERROR` + `TRANSIENT` + `BLOOM`: de los ~28 píxeles a ≤ 3 px, mediana de 25–26 `SUR_ERROR` en D1–D4, 12 en D5 y 4 en D6;
    - en el 3×3 central: `SOURCE` 358, `OVERFLOW` 357, `TRANSIENT` 353, `BLOOM` 353, `SUR_ERROR` 351, `NONFUNC` 17, `PERSIST` 11, `HOT` 7 y `HALO` 1 (este último solo en R);
    - a ≤ 5 px: `NONFUNC` en 95 frames, `PERSIST` en 42, `HALO` en 35, `COLD` en 11 (solo en R) y `HOT` en 7, todos enmascarados. No hay `GHOST*`, `SNOWBALL` ni `STREAK`.
  - Bordes: la distancia mínima al borde del detector es 6,1 px (2026W12_2A_0371_1D5).
  - Tiempos: el `mjd` de `field.json` es igual al `MJD-AVG` del header (0,000 s); SIA difiere en ≤ 0,027 s.
  - Build: los 40 frames están en la búsqueda en vivo, repartidos 14/13/13 por temporada y 2–3 por (temporada, detector). Los 40 están saturados (`OVERFLOW` de 1 a 11 px). No hubo descargas fallidas.
- **Alignment check / photometry or astrometry method / uncertainties:**
  - WCS de cada exposición contra estrellas Gaia DR3 de campo, propagadas al `MJD-AVG`, con selección y ajuste propios en cada análisis:

    | | (A) `s5_fieldstars.py`, `s5b_zp.py` | (R) `review/r5_measure.py`, `r6_census.py` |
    |---|---|---|
    | Selección | 288 estrellas: 5/6 parámetros, G 8–17, RUWE < 1,4, índice de contaminación < 0,03, a > 60″ de Barnard | 388 estrellas en el cono, 56 medidas: 5/6 parámetros, G 9–17, RUWE < 1,4, `ipd_frac_multi_peak` ≤ 2, no duplicadas, sin vecinas con G < G★+3 a ≤ 12″ ni con G < G★+0,5 a ≤ 24″, a > 75″ de Barnard |
    | Propagación | movimiento propio | movimiento propio + paralaje |
    | Ajuste | gaussiana circular integrada por píxel, 7×7 px | gaussiana circular integrada por píxel (código propio), 7×7, re-centrada, con núcleo de r ≤ 2 px limpio y SNR > 20; control con perfil radial |
    | Frames con punto cero | 356/358, mediana 33 estrellas | 355/358, mediana 31 estrellas |
    | Dispersión robusta del punto cero | (0,094, 0,102)″ = (0,015, 0,017) px | (0,086, 0,103)″ = (0,014, 0,017) px |
    | \|Punto cero\| mediano | 0,020 px | 0,019 px |
    | Frames > 0,05 / > 0,1 px | 21 / 2 | 20 / 1 |
    | Residuo por estrella | σ robusta (0,18, 0,26)″ | dispersión mediana por frame (0,15, 0,19)″ |
    | Medias por temporada | S0 (−0,062, −0,024)″; S1 (+0,074, +0,042)″; S2 (−0,071, −0,042)″ | S0 (−0,040 ± 0,007, −0,015 ± 0,011)″; S1 (+0,068 ± 0,008, +0,049 ± 0,013)″; S2 (−0,049 ± 0,009, −0,035 ± 0,017)″ |

    - Frames sin punto cero: en A, 2026W13_1A_0129_1 y _2 (D3, cerca del borde); en R, esos dos más 2026W12_2A_0520_1D3.
    - Como en ε Ind B, el WCS alterna ~0,1″ (0,02 px) en E entre orientaciones.
    - **2026W34_1A_0431_2D6** está corrido (+0,66, −1,50)″ = 0,27 px en A y (+0,68, −1,60)″ = 0,283 px en R. Tiene `MATCH_NSTARS` 1255, contra 2292 y 2357 en sus vecinas D6 _1 y _3, que están a 0,011 y 0,039 px (R). `FINAST` = 0. El D3 de la misma exposición está a 0,038 px.
    - 2026W35_1A_0249_4D4 está corrido 0,10 px en A y 0,083 px en R (0,115 px con centroides de perfil radial).
    - Ninguno de los dos frames está en el build.
  - Astrometría de Barnard, sobre `IMAGE − ZODI`:
    - (A) `s4_barnard.py`, siete variantes re-centradas hasta estabilizarse, con peso 1/`VARIANCE`:
      - **gcS (principal):** gaussiana circular integrada por píxel más una constante, en 9×9 px. Enmascara `OVERFLOW`, NaN, `SUR_ERROR` y los demás defectos, y usa ~50 de los 81 px;
      - gcd: la zona saturada dilatada 1 px en lugar de `SUR_ERROR`;
      - gc, ge y mof: sacan solo `OVERFLOW`/NaN (circular, elíptica y Moffat);
      - naive: referencia sesgada a propósito;
      - satc: centro de la zona saturada.
      - El ajuste parte del centro de la zona saturada. Desde el centro fijo del campo o desde la predicción, gcS da el mismo centro (< 0,001 px) en 348–349 de 358 frames.
      - χ²_ν mediano de 87 a 204 según el detector: domina el desajuste del modelo.
    - (R) `review/r5_measure.py`, con un método distinto:
      - **rp (principal, elegido antes de ver resultados):** perfil radial libre. Para cada centro de prueba, el perfil es una función lineal a tramos de r (nodos cada 0,5 px, con regularización de suavidad) que se resuelve por mínimos cuadrados lineales; el centro minimiza χ² (Nelder-Mead, acotado a ≤ 2 px del punto de partida). No supone forma de PSF salvo la simetría circular. Peso 1/(`VARIANCE` + (0,05·I)²), con un ahusamiento radial suave entre 4 y 6 px. Máscara: `OVERFLOW`/`NONLINEAR`/NaN dilatados 1 px (3×3), `SUR_ERROR` y los demás defectos;
      - variantes: rpU (sin dilatar), rpB (enmascara además `BLOOM` y `TRANSIENT`) y rpE (perfil elíptico: cualquier PSF con simetría de reflexión central);
      - para reproducir afirmaciones de A: gaussiana propia integrada por píxel en 9×9, con `SUR_ERROR` enmascarado o conservado, y con la caja re-centrada o fija en el centro del campo; satc;
      - rp da el mismo centro (< 0,001 px) partiendo del centro de la zona saturada o de la predicción en 352/358 frames, con un máximo de 0,011 px.
    - El centro se pasa a RA/Dec con la WCS TAN-SIP de cada frame y se le resta el punto cero de esa exposición.
  - Por qué hay que enmascarar `SUR_ERROR` (VERIFICADO por A y R):
    - las gaussianas que conservan los píxeles `SUR_ERROR` vecinos de la saturación tienen más dispersión por frame. En D1: A gc (0,98, 0,65)″ contra gcS (0,46, 0,29)″; R (0,97, 0,63)″ contra (0,47, 0,25)″;
    - muestran outliers de hasta ~0,5 px (R: 3,16″ = 0,51 px) y giran la dirección de S0→S2 ~4°;
    - dispersión robusta por frame de rp (R): (0,36, 0,25)″ en D1, (0,47, 0,24) en D2, (0,28, 0,68) en D3, (0,47, 0,20) en D4, (0,21, 0,17) en D5 y (0,21, 0,22) en D6. Es menor o igual que la de la gaussiana con `SUR_ERROR` enmascarado en D1–D4: (0,47, 0,25), (0,60, 0,29), (0,45, 0,72) y (0,86, 0,52).
  - Errores:
    - (A): estadístico = el mayor entre el error estándar (media con recorte a 4σ) y un bootstrap por visitas; sistemático = la mitad del rango de gcS, gcd, gc, ge y mof;
    - (R): mediana por temporada con bootstrap por visitas (4000 remuestreos dentro de cada temporada); sistemático = la mitad del rango de rp, rpU, rpB y rpE, cada una con el punto cero gaussiano o el de perfil radial. Para S0→S2 vale (0,040, 0,027)″. La diferencia entre estimadores (A gcS contra R rp: (−0,24, +0,04)″ en S0→S2) va en la tabla de variantes y no está incluida en ese sistemático.
  - Lección de método (A, reproducido en signo por R): con la caja fija en el centro del campo y sin re-centrar, S0→S2 sale más largo.
    - (A): +0,17″ (10,412″ contra 10,238″);
    - (R), gaussiana propia con `SUR_ERROR` enmascarado: +0,08″ (10,337″ contra 10,254″);
    - la caja queda ~0,84 px al sur del objetivo en S0 y ~0,82 px al norte en S2 (🧮).
- **Expected behavior / observed behavior:**
  - Esperado: una fuente única, muy brillante (K = 4,5) y probablemente saturada (SCIENCE.md §0.3), que se mueve casi hacia el norte.
    - Del primer al último frame (402,76 d): 11,33″ = 1,842 px a PA 355,0° con la paralaje. Solo con movimiento propio son 11,475″ = 1,866 px: el 1,86 px de SCIENCE.md.
    - Entre las medias de S0 y S2 (misma orientación, casi la misma fase de paralaje): (−0,761, +10,209)″ = 10,237″ = **1,665 px a PA 355,7°**.
    - La paralaje (±0,55″ en E) corre S1 hacia el este respecto de S0 y S2.
  - Observado (VERIFICADO por A y R): la estrella está saturada en 357/358 exposiciones y su núcleo sigue la trayectoria del catálogo en los seis detectores (`rev_fig1`, `rev_fig2`, `fig1`, `fig2`).
  - S0→S2:
    - (A) gcS: (−1,052 ± 0,095, +10,183 ± 0,060)″ = 10,238 ± 0,061 ± 0,110″ = 1,665 ± 0,018 px a PA 354,1 ± 0,5 ± 2,1°; medido − esperado (−0,29, −0,03)″;
    - (R) rp: (−0,815 ± 0,108, +10,146 ± 0,081)″ = 10,179 ± 0,081 ± 0,086″ = 1,655 ± 0,014 px a PA 355,4 ± 0,6 ± 0,6°; medido − esperado (−0,06, −0,06)″ = (−0,5σ, −0,7σ). El cociente con lo esperado es 0,994;
    - variantes de perfil radial (R): 10,127–10,185″ (1,647–1,656 px), PA 355,2–355,6°;
    - variantes de A: 10,174–10,244″ (1,654–1,666 px), PA 350,0–354,1°.
    - El residuo en E depende del estimador (`rev_fig5`):
      - va de −0,01 a −0,09″ con el perfil radial;
      - −0,23″ con la gaussiana de R con `SUR_ERROR` enmascarado; −0,29 y −0,32″ con gcS y gcd de A;
      - −0,71″ (R) y −1,01″ (A) si se conserva `SUR_ERROR`;
      - −1,16″ con satc.
  - Posiciones absolutas por temporada:
    - quedan a ≤ 0,57″ (≤ 0,094 px) del catálogo con gcS (A) y a ≤ 0,74″ (≤ 0,121 px) con rp (R);
    - S1 − media(S0, S2) en E vale +0,63″ con gcS, +1,22″ con rp y entre −0,66 y +1,35″ según la variante (≤ 0,22 px). Es un sesgo del centroide del núcleo saturado en coordenadas del detector (hacia −x en las tres temporadas; `fig5` de A), que cambia de signo en el cielo al girar el detector.
  - En los 40 PNG publicados (`rev_fig4`, `fig4`; A y R):
    - el centroide de la meseta blanca se mueve (+0,21, −1,60) px de S0 a S2, contra (+0,13, −1,68) px predichos;
    - Barnard es un disco de 12–76 px a 255 (mediana 41; ~7 px de diámetro) y la UI no dibuja la posición.
  - Solo con los 40 frames del build (R, rp): S0→S2 = 10,385 ± 0,18″ = 1,689 px a PA 355,9°, contra 10,347″ = 1,682 px esperados.
- **Result:** success.
  - El movimiento propio de Barnard's Star se detecta en las imágenes SPHEREx con la magnitud y la dirección esperadas. Entre S0 y S2 se miden 1,665 ± 0,018 px (A) y 1,655 ± 0,014 px (R), contra 1,665 px esperados, a PA 354,1 ± 2,1° (A) y 355,4 ± 0,6° (R), contra 355,7°.
  - «Sin movimiento» queda descartado a 93σ (A) y a 119σ (R) con el sistemático incluido.
  - Lo confirman dos análisis independientes, con estimadores distintos.
  - El sistemático de la posición absoluta por temporada (~0,1 px) depende del estimador y es propio de la saturación. En S0→S2 se cancela casi del todo.
  - No es un descubrimiento: se recupera un movimiento conocido.
- **Limitations and failed downloads:**
  - Descargas: 0 fallidas (A: 358/358 stamps y 358/358 patches de 10′; R: 358/358 stamps y 358/358 patches de 12′).
  - Saturación: el núcleo no se puede usar y la astrometría sale del ala de la PSF.
    - La posición absoluta por temporada depende del estimador en hasta ~0,1–0,2 px. S0→S2, con la misma orientación, depende mucho menos: 1,647–1,666 px entre todas las variantes resistentes de A y R.
    - El residuo en E de S2 − S0 que A atribuía a DR1/QR3 no aparece con el perfil radial libre. Causa INFERIDA del residuo de las gaussianas: desajuste del modelo en el ala saturada, que cambia con las fases subpíxel y las λ muestreadas.
    - No hay otra estrella saturada en los patches para calibrar el método. La más brillante del cono después de Barnard tiene G = 8,52 y está a 590″, fuera de los patches.
  - PSF:
    - modelo gaussiano o de Moffat (A) o perfil radial libre (R), sin la EPSF: los patches de S3 no traen ese HDU (DATA.md §3.2);
    - los errores salen de la dispersión empírica, no del ajuste.
  - Paralaje: no se puede medir de forma independiente.
    - El giro de 180° de S1 coincide con su fase de paralaje, y el sesgo que depende de la orientación (−0,66 a +1,35″ según el estimador, contra ~1,03″ de paralaje) es degenerado con ella.
    - La paralaje queda fija en el valor de Gaia.
  - Movimiento propio:
    - con gaussianas, µα* sale sesgado hacia el oeste: −1099 ± 380 mas/año en S0→S2, y entre −1057 y −1426 en los ajustes de tres temporadas de A (no reproducidos por R);
    - con el perfil radial (R): −858 ± 117 mas/año, a −0,5σ del catálogo.
  - D1 a λ < 0,85 µm, la que menos satura (1–4 px de `OVERFLOW`; n = 9 en S0 y 6 en S2): el residuo S2 − S0 vale (−0,04, −0,21)″ en A y (+0,22, −0,24)″ en R.
  - Paso 6 de VALIDATION.md pendiente: en esta sesión no se levantaron servidores ni se revisó la UI. Tampoco se corrió `errante compare` para este campo.
- **Product field ID / public URL / screenshot or animation:**
  - barnards-star (data/products/fields/barnards-star/). URL pública: pendiente del deploy (WS4).
  - Figuras (gráficos generados con código a partir de los FITS reales de SPHEREx y de los PNG publicados):
    - [rev_fig1_stamps.png](figures/barnards-star/rev_fig1_stamps.png): Revisión: una exposición por detector y temporada. Remuestreo al vecino más cercano con norte arriba, sobre un marco de cielo fijo; posiciones predichas de S0, S1 y S2, ajuste rp y píxeles `OVERFLOW`/NaN.
    - [rev_fig2_track.png](figures/barnards-star/rev_fig2_track.png): Revisión: trayectoria medida (358 exposiciones) contra Gaia DR3 (pm y pm + paralaje), y residuos frente al tiempo con perfil radial y gaussiana.
    - [rev_fig3_wcs.png](figures/barnards-star/rev_fig3_wcs.png): Revisión: punto cero del WCS por exposición con estrellas Gaia propias, incluido el frame de 0,28 px.
    - [rev_fig4_pngs.png](figures/barnards-star/rev_fig4_pngs.png): Revisión: media de los PNG publicados por temporada, con el píxel predicho y la meseta saturada de S0 y S2.
    - [rev_fig5_methods.png](figures/barnards-star/rev_fig5_methods.png): Revisión: residuo de S0→S2 por estimador (R y A). El residuo hacia el oeste solo aparece con las gaussianas y satc.
    - [fig1_stamps.png](figures/barnards-star/fig1_stamps.png): Análisis original: una exposición por detector y temporada, con la predicción, el ajuste gcS, `OVERFLOW` y `SUR_ERROR`.
    - [fig2_track.png](figures/barnards-star/fig2_track.png): Análisis original: trayectoria, residuos frente al tiempo y S0→S2 por método y por detector.
    - [fig3_wcs.png](figures/barnards-star/fig3_wcs.png): Análisis original: punto cero del WCS por exposición.
    - [fig4_published_pngs.png](figures/barnards-star/fig4_published_pngs.png): Análisis original: los 40 PNG publicados con la posición predicha y el centroide de la meseta.
    - [fig5_methods.png](figures/barnards-star/fig5_methods.png): Análisis original: máscaras de cada método y residuos frente a la fase subpíxel.
- **Reviewer / date:** Claude (WS1) con revisión adversarial independiente / 2026-11-15; revisión humana pendiente

## Detalle de la medición

### Método

1. **Astrometría:**
   - (A) `s1_catalog.py`, `s10_astrometry.py` y `common.py`: Gaia DR3 por TAP de ESA, Sesame CfA, cono Gaia de 0,2° y propagación con astropy.
   - (R) `review/r1_catalog.py` y `review/r3_astrometry.py` (con `rcommon.py`): TAP y Sesame repetidos, propagación rigurosa propia con ERFA y control contra astropy.
   - Identidad: (A) 2MASS con `curl`; (R) `review/r10_identity.py`, con Gaia de todas las magnitudes y 2MASS.
2. **Cobertura:**
   - (A) `s2_coverage.py`.
   - (R) `review/r2_coverage.py`: SIA2 en vivo en tres posiciones, snapshot, temporadas, visitas y build.
3. **Píxeles:**
   - (A) `s3a_point.py` (stamps de 25 px) y `s3b_patches.py` (patches de 10′).
   - (R) `review/r4_fetch.py` (patches de 12′) y `review/r11_lambda.py` (`point_series`, λ).
4. **Medición por frame:**
   - (A) `s4_barnard.py` (con `meas.py`), `s4b_summary.py`, `s5_fieldstars.py` y `s5b_zp.py`.
   - (R) `review/r5_measure.py`: perfil radial, gaussianas propias, satc y estrellas de campo propias. `review/r6_census.py`: saturación, flags, orientación y punto cero.
5. **Análisis temporal:**
   - (A) `s6_motion.py`, `s6b_methods.py`, `s7_pmfit.py`, `s8_final.py` y `s11_tables.py`.
   - (R) `review/r7_motion.py`: medianas por temporada con bootstrap por visitas, pares, variantes, por detector, movimiento propio y solo build. `review/r8_scatter.py`: dispersión por detector y subconjunto D1 de λ corta. `review/r13_final.py`: números finales.
6. **Producto publicado:** (A) `s9_png.py`; (R) `review/r9_png.py`, que comprueba además la convención de PNG con y hacia abajo.
7. **Figuras:**
   - (A) `f1_stamps.py` a `f5_methods.py`, `s6c_phase.py` y `dbg_detpos.py`.
   - (R) `review/r12_figures.py`.

### Cobertura por temporada (búsqueda: 358 frames; A y R)

| Temporada | MJD (fechas) | n | dr1/qr3 | Visitas | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|---|---|---|---|
| S0 | 60902,87–60949,27 (2025-08-15 → 2025-10-01) | 118 | 118/0 | 18 | 24 | 18 | 18 | 23 | 18 | 17 |
| S1 | 61110,09–61165,08 (2026-03-11 → 2026-05-05) | 121 | 121/0 | 14 | 18 | 18 | 24 | 18 | 19 | 24 |
| S2 | 61268,63–61305,63 (2026-08-16 → 2026-09-22) | 119 | 0/119 | 16 | 18 | 25 | 17 | 18 | 24 | 17 |

Coincide con DATA.md §3.0 (118/121/119).

### Saturación por detector (a ≤ 3 px de la posición predicha; A y R, con valores idénticos)

| Detector | n | Con `OVERFLOW` | px `OVERFLOW`: mediana [mín–máx] | Con NaN | Con `OVERFLOW` finito | px `SUR_ERROR` (mediana) | λ (µm) |
|---|---|---|---|---|---|---|---|
| D1 | 60 | 60 | 3 [1–6] | 57 | 57 | 25 | 0,741–1,107 |
| D2 | 61 | 61 | 5 [4–8] | 61 | 55 | 26 | 1,088–1,661 |
| D3 | 59 | 59 | 5 [1–8] | 59 | 52 | 26 | 1,625–2,411 |
| D4 | 59 | 59 | 6 [4–7] | 59 | 57 | 26 | 2,419–3,800 |
| D5 | 61 | 61 | 3 [1–11] | 3 | 61 | 12 | 3,804–4,430 |
| D6 | 58 | 57 | 3 [0–7] | 1 | 57 | 4 | 4,412–5,002 |
| Total | 358 | 357 | 5 [0–11] | 240 | 339 | 24 | |

El valor finito máximo a ≤ 3 px es de 385–3244 MJy/sr (`IMAGE − ZODI`).

### Posición por temporada

Medido − catálogo (pm + paralaje), en ″ y en (E, N), con el punto cero de cada exposición aplicado:
- (A): media robusta ± el mayor entre el error estándar y el bootstrap por visitas; en S1 usa 119 frames;
- (R): mediana ± bootstrap por visitas; usa 118 frames en S0, 118 en S1 y 119 en S2.

| Temporada | MJD medio | (A) gcS | (A) gc (`SUR_ERROR` conservado) | (R) rp (principal) | (R) gaussiana, `SUR_ERROR` enmascarado | (R) gaussiana, `SUR_ERROR` conservado |
|---|---|---|---|---|---|---|
| S0 | 60916,19 | (+0,05 ± 0,09, +0,02 ± 0,04) | (+0,76 ± 0,18, −0,18 ± 0,06) | (−0,45 ± 0,10, +0,03 ± 0,06) | (−0,06 ± 0,10, −0,01 ± 0,03) | (+0,45 ± 0,33, −0,15 ± 0,06) |
| S1 | 61119,39 | (+0,53 ± 0,08, +0,21 ± 0,03) | (+0,10 ± 0,05, +0,27 ± 0,04) | (+0,74 ± 0,03, +0,08 ± 0,06) | (+0,52 ± 0,08, +0,15 ± 0,04) | (+0,16 ± 0,08, +0,28 ± 0,03) |
| S2 | 61274,63 | (−0,24 ± 0,04, −0,00 ± 0,04) | (−0,26 ± 0,04, −0,37 ± 0,05) | (−0,51 ± 0,05, −0,03 ± 0,05) | (−0,30 ± 0,05, −0,02 ± 0,05) | (−0,27 ± 0,06, −0,33 ± 0,08) |

- S1 − media(S0, S2):
  - (A): (+0,63, +0,20)″ con gcS, (+0,96, +0,18)″ con gcd y (−0,15, +0,54)″ con gc;
  - (R): (+1,22, +0,08)″ con rp y (+0,93…+1,35, −0,05…+0,19)″ con las variantes de perfil radial; (+0,70, +0,16)″ con la gaussiana enmascarada, (+0,07, +0,52)″ con la conservada y (−0,66, +0,61)″ con satc.
- Sin el punto cero por exposición, S0→S2 da 10,209″ (1,660 px) a PA 353,9° con gcS (A) y 10,161″ (1,652 px) a PA 355,1° con rp (R).

### Desplazamiento entre temporadas

Medido = esperado entre las MJD medias + cambio del residuo. En |d| y PA, el primer ± es estadístico y el segundo es total (estadístico más el sistemático de las variantes de cada análisis).

| Par | Análisis | Medido (ΔE, ΔN) ″ | \|d\| ″ / px | PA | Esperado: ″ / px, PA | Medido − esperado (ΔE, ΔN) ″ | Rango de variantes |
|---|---|---|---|---|---|---|---|
| S0→S1 | (A) gcS | (+1,086, +5,849) | 5,949 ± 0,057 ± 0,208 / 0,967 ± 0,034 | 10,5 ± 1,2 ± 7,1° | 5,695 / 0,926, 6,1° | (+0,48, +0,19) | 5,949–6,135″; PA 359,4–13,6° |
| S0→S1 | (R) rp | (+1,801, +5,708) | 5,986 ± 0,091 ± 0,131 / 0,973 ± 0,021 | 17,5 ± 1,0 ± 1,9° | 5,695 / 0,926, 6,1° | (+1,20, +0,05) | 5,781–5,986″; PA 14,8–18,1° |
| S1→S2 | (A) gcS | (−2,138, +4,334) | 4,833 ± 0,061 ± 0,278 / 0,786 ± 0,045 | 333,7 ± 1,0 ± 4,4° | 4,746 / 0,772, 343,3° | (−0,77, −0,21) | 4,245–5,014″; PA 330,3–336,3° |
| S1→S2 | (R) rp | (−2,616, +4,437) | 5,151 ± 0,075 ± 0,122 / 0,838 ± 0,020 | 329,5 ± 0,7 ± 1,7° | 4,746 / 0,772, 343,3° | (−1,25, −0,11) | 5,038–5,201″; PA 329,4–332,5° |
| **S0→S2** | **(A) gcS** | **(−1,052, +10,183)** | **10,238 ± 0,061 ± 0,110 / 1,665 ± 0,018** | **354,1 ± 0,5 ± 2,1°** | 10,237 / 1,665, 355,7° | (−0,29, −0,03) | 10,174–10,244″; PA 350,0–354,1° |
| **S0→S2** | **(R) rp** | **(−0,815, +10,146)** | **10,179 ± 0,081 ± 0,086 / 1,655 ± 0,014** | **355,4 ± 0,6 ± 0,6°** | 10,237 / 1,665, 355,7° | (−0,06, −0,06) | 10,127–10,185″; PA 355,2–355,6° |

- S0→S1 y S1→S2 mezclan el giro de 180° con el cambio de paralaje: su apartamiento (hasta 1,25″ = 0,20 px en R) es el sistemático que depende de la orientación, no un desacuerdo con el catálogo.
- S0→S2 por variante (″; error estadístico):

  | Variante | (ΔE, ΔN) | \|d\| ″ / px | PA |
  |---|---|---|---|
  | (A) gcS | (−1,052 ± 0,095, +10,183 ± 0,060) | 10,238 / 1,665 | 354,1° |
  | (A) gcd | (−1,078 ± 0,107, +10,187 ± 0,062) | 10,244 / 1,666 | 354,0° |
  | (A) gc | (−1,774 ± 0,180, +10,018 ± 0,082) | 10,174 / 1,654 | 350,0° |
  | (A) ge | (−1,768 ± 0,181, +10,022 ± 0,079) | 10,177 / 1,655 | 350,0° |
  | (A) mof | (−1,731 ± 0,187, +10,033 ± 0,079) | 10,181 / 1,655 | 350,2° |
  | (A) naive | (−1,761 ± 0,186, +9,975 ± 0,073) | 10,130 / 1,647 | 350,0° |
  | (A) satc | (−1,789 ± 0,247, +10,083 ± 0,159) | 10,240 / 1,665 | 349,9° |
  | (R) rp | (−0,815 ± 0,108, +10,146 ± 0,081) | 10,179 / 1,655 | 355,4° |
  | (R) rp, punto cero de perfil radial | (−0,829 ± 0,100, +10,094 ± 0,055) | 10,128 / 1,647 | 355,3° |
  | (R) rpU | (−0,853 ± 0,092, +10,149 ± 0,068) | 10,185 / 1,656 | 355,2° |
  | (R) rpB | (−0,801 ± 0,076, +10,123 ± 0,080) | 10,155 / 1,651 | 355,5° |
  | (R) rpE | (−0,792 ± 0,103, +10,122 ± 0,077) | 10,153 / 1,651 | 355,5° |
  | (R) gaussiana, `SUR_ERROR` enmascarado | (−0,994 ± 0,107, +10,206 ± 0,060) | 10,254 / 1,667 | 354,4° |
  | (R) gaussiana, `SUR_ERROR` conservado | (−1,476 ± 0,340, +10,030 ± 0,097) | 10,138 / 1,648 | 351,6° |
  | (R) gaussiana, caja fija | (−1,012 ± 0,102, +10,287 ± 0,077) | 10,337 / 1,681 | 354,4° |
  | (R) satc | (−1,916 ± 0,364, +10,001 ± 0,158) | 10,183 / 1,656 | 349,2° |
  | Esperado | (−0,761, +10,209) | 10,237 / 1,665 | 355,7° |

- S0→S2 por detector (″; error estadístico):

  | Detector | n (S0, S2) | (A) gcS: (ΔE, ΔN); \|d\|, PA | (R) rp: (ΔE, ΔN); \|d\|, PA | Esperado ″, PA |
  |---|---|---|---|---|
  | D1 | 24, 18 | (−0,857 ± 0,155, +9,991 ± 0,091); 10,028, 355,1° | (−0,692 ± 0,166, +9,896 ± 0,122); 9,920, 356,0° | 10,137, 355,8° |
  | D2 | 18, 25 | (−0,824 ± 0,226, +10,169 ± 0,155); 10,202, 355,4° | (−0,661 ± 0,230, +10,136 ± 0,098); 10,158, 356,3° | 10,303, 355,7° |
  | D3 | 18, 17 | (−0,847 ± 0,156, +10,521 ± 0,224); 10,556, 355,4° | (−0,960 ± 0,106, +10,443 ± 0,269); 10,487, 354,7° | 10,332, 355,7° |
  | D4 | 23, 18 | (−1,392 ± 0,342, +9,924 ± 0,197); 10,021, 352,0° | (−0,950 ± 0,308, +10,095 ± 0,123); 10,140, 354,6° | 10,131, 355,8° |
  | D5 | 18, 24 | (−1,428 ± 0,159, +10,334 ± 0,083); 10,432, 352,1° | (−0,929 ± 0,270, +10,259 ± 0,100); 10,301, 354,8° | 10,307, 355,7° |
  | D6 | 17, 17 | (−1,155 ± 0,098, +10,382 ± 0,057); 10,447, 353,7° | (−0,888 ± 0,129, +10,423 ± 0,088); 10,461, 355,1° | 10,328, 355,7° |

  D1 sale corto en los dos análisis, 0,11–0,22″ (≤ 1,8σ). En R, el residuo en E por detector va de −0,20 a +0,10″, sin signo común.
- Solo con los 40 frames del build (R, rp): (−0,741 ± 0,315, +10,358 ± 0,183)″ = 10,385″ = 1,689 px a PA 355,9°, contra 10,347″ = 1,682 px a PA 355,6°.

### Movimiento propio ajustado

En S0→S2 se resta la paralaje del catálogo, (+0,027, +0,027)″ en 0,9813 años; el error es el total. En los ajustes de tres temporadas de A, el error es el mayor entre el formal y el jackknife por detector.

| Ajuste | µα* (mas/año) | µδ (mas/año) | \|µ\| | PA |
|---|---|---|---|---|
| (A) S0→S2, gcS | −1099 ± 380 | +10350 ± 106 | 10408 | 353,9° |
| (R) S0→S2, rp | −858 ± 117 | +10311 ± 87 | 10347 | 355,2° |
| (A) 3 temporadas, gcS, con offset por detector y sesgo en coordenadas de detector | −1141 ± 86 | +10367 ± 44 | 10430 | 353,7° |
| (A) Ídem, gcd | −1057 ± 101 | +10358 ± 72 | 10412 | 354,2° |
| (A) Ídem, gc | −1316 ± 275 | +10297 ± 129 | 10381 | 352,7° |
| (A) Ídem, ge | −1426 ± 342 | +10282 ± 85 | 10380 | 352,1° |
| (A) Ídem, mof | −1268 ± 806 | +10271 ± 115 | 10349 | 353,0° |
| Catálogo: instantáneo a MJD 61104 (riguroso); en el intervalo S0→S2, (−802,6, +10375,4) | −802,6 | +10375,4 | 10406 | 355,6° |

- (R) se aparta del catálogo en (−56, −64) mas/año, es decir −0,5σ y −0,7σ.
- R no repitió los ajustes de tres temporadas: con un término libre de orientación, S1 solo fija ese término y el ajuste se reduce a S0→S2.
- El sesgo de µα* hacia el oeste de A sale de los estimadores gaussianos (ver la tabla de variantes).

### Blink publicado (40 PNG; A y R)

- Posición predicha en la grilla (convención PNG, y hacia abajo) y centroide medido de la meseta a 255, por temporada:

  | Temporada | y predicha | y de la meseta | Centroide pesado (13×13): A / R |
  |---|---|---|---|
  | S0 | 44,35 | 44,35 | 44,12 / 44,11 |
  | S1 | 43,42 | 43,43 | 43,19 / 43,17 |
  | S2 | 42,67 | 42,75 | 42,80 / 42,82 |

  De S0 a S2, la meseta se corre (+0,21, −1,60) px, contra (+0,13, −1,68) px predichos. R comprobó la convención: la meseta queda a 0,19 px (mediana) de la y predicha con la inversión de PNG, y a 1,48 px sin ella.
- La meseta a 255 ocupa 12–76 px en una ventana de 13×13 (mediana 41, ~7 px de diámetro equivalente).
- El estiramiento llega a un vmax de 3,89–9,95 MJy/sr según el detector, mientras que Barnard alcanza 385–3244 MJy/sr.
- El núcleo saturado se rellena con sus vecinos solo para mostrarlo (nota de `provenance`).

## Problemas encontrados

1. **El blink publicado no deja ver el movimiento a simple vista** (VERIFICADO por A y R).
   - Barnard es un disco blanco de ~7 px: la meseta a 255 ocupa 12–76 px, con mediana 41.
   - El corrimiento S0→S2 (1,6 px) equivale a ~¼ del disco.
   - `known.json` y `candidates.json` están vacíos, y `BlinkViewer` solo dibuja marcadores desde esos archivos. La retícula sigue como `TODO(WS5)` en `frontend/src/components/BlinkViewer.tsx:237`.
   - El dato sí está: la meseta sigue la predicción a ≤ 0,1 px (`rev_fig4`, `fig4`).
   - Dueños:
     - WS2: render; por ejemplo, un recuadro o un estiramiento propio para el blanco brillante;
     - WS5: overlay con la posición predicha por época;
     - WS3: trayectoria de los blancos oficiales en `known.json`.
2. **Astrometría de estrellas saturadas** (VERIFICADO por A y R; R amplía el diagnóstico).
   - Enmascarar solo `OVERFLOW` no alcanza: los píxeles `SUR_ERROR` vecinos del núcleo duplican la dispersión por frame, dejan outliers de ~0,5 px y giran la dirección de S0→S2 unos 4°.
   - Una caja fija, sin re-centrar, alarga S0→S2 entre +0,08″ (R) y +0,17″ (A).
   - Aun con `SUR_ERROR` enmascarado, una gaussiana deja en S0→S2 un residuo de −0,23″ (R) o −0,29″ (A) en E que el perfil radial libre no deja (−0,01 a −0,09″).
   - La posición absoluta del núcleo saturado tiene un sesgo de ~0,1 px en coordenadas del detector, que depende del estimador.
   - El flujo del núcleo no sirve: hay `OVERFLOW` en 357/358 exposiciones.
   - Dueño: WS2 (`imaging.photometry`, `detect`), que debería enmascarar `SUR_ERROR` junto a la saturación, re-centrar y preferir un perfil empírico (o la EPSF) a una gaussiana para estrellas saturadas.
3. **El docstring de `errante.data.point` no describe bien la saturación de Barnard** (VERIFICADO por A y R).
   - `PointSample` dice «Saturated cores are NaN with OVERFLOW (bit 1) set» (`pipeline/errante/data/point.py:940`).
   - En Barnard hay NaN en el núcleo en 240/358 exposiciones, pero 339/358 tienen píxeles `OVERFLOW` finitos, y en D5/D6 solo 4 de 119 tienen NaN.
   - DATA.md §3.2 dice que los `OVERFLOW` son finitos (R Dra, RW Aur); en Barnard aparecen los dos casos.
   - DATA.md §6 todavía lista «❓ Saturación de Barnard», y SCIENCE.md §0.3 dice «❓ puede saturar». Las dos se pueden cerrar con la tabla de este registro.
   - Dueño: WS1, con el coordinador para SCIENCE.md.
4. **Hay un frame con el WCS corrido 0,27–0,28 px** (VERIFICADO por A y R).
   - 2026W34_1A_0431_2D6: (+0,66, −1,50)″ en A y (+0,68, −1,60)″ en R. Tiene `MATCH_NSTARS` 1255, contra 2292–2357 en sus vecinas D6 (a 0,011 y 0,039 px), y `FINAST` = 0.
   - No está en el build, pero otra selección podría tomarlo.
   - Es el mismo tipo de defecto que 2026W38_1A_0162_3D6 de DATA.md §3.2. Hace falta un control de registro por frame.
   - Dueños: WS2 (QA) y WS1 (DATA.md).
5. **No hay que afirmar una paralaje medida con SPHEREx para este blanco** (VERIFICADO por A y R).
   - El giro de 180° de S1 coincide con su fase de paralaje.
   - El sesgo de orientación, de −0,66 a +1,35″ según el estimador (hasta 0,22 px), es degenerado con la paralaje, que es de ~1,03″.
   - El movimiento propio se cita desde S0→S2.
   - Dueños: WS3 (textos científicos) y WS6 (pitch).
6. **Sesame resuelve `GJ 699` a una posición de época antigua, a 8,6′** (VERIFICADO por R).
   - Responde solo VizieR local, con 17:57:51.47 +04:33:03.2.
   - Hay que resolver por «Barnard's Star» o por el `source_id` de Gaia DR3; las notas de `fields.toml` y SCIENCE.md ya usan la posición correcta.
   - Dueño: WS3.

Sin problema (VERIFICADO por A y R):

- No hay fuentes de catálogo que contaminen la trayectoria: en Gaia DR3 todas son ≥ 6,8 mag más débiles a ≤ 30″, y 2MASS tampoco tiene ninguna brillante cerca.
- Tiempos: el `mjd` de `field.json` es igual a `MJD-AVG`; SIA difiere en ≤ 0,027 s.
- λ: `field.json` coincide con `WCS-WAVE` y con `point_series` en el centro del campo; en la posición de Barnard, λ cambia ≤ 0,73 nm.
- La búsqueda SIA2 en vivo coincide con el snapshot versionado (358 frames, el mismo conjunto), y los 40 frames del build están en ella.
- No hay `GHOST*`, `SNOWBALL` ni `STREAK` a ≤ 5 px de Barnard.
- El WCS es estable entre temporadas a ≤ 0,12″ (0,02 px), sin contar el frame corrido.
- La propagación con astropy (A) y la implementación propia con ERFA (R) coinciden a < 0,0001″.
