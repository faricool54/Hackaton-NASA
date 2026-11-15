# Ciencia mínima para el equipo

Lectura obligatoria para WS2 y WS3; recomendada para todos (sirve para el pitch).

> **Actualizado el 2026-11-15 (WS3-7).** El §0 incorpora lo que establecieron los cinco registros de
> [`validation/`](validation/); 🆕 marca lo que cambió respecto de la versión del 14/11. Al final está la
> [revisión científica de textos](#revisión-científica-de-textos-ws3-7-2026-11-15), con cambios listos para pegar
> por cada dueño, y después la [revisión científica del 3D de WS7](#revisión-científica-del-3d-ws7-47---2026-11-15)
> (#47).

**Alcance prioritario:** R05 exige ensayar Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis.
Ver `VALIDATION.md`: movimiento propio y variabilidad se validan sin requerir detección automática.
Las estimaciones de distancia y Planeta X que siguen son contexto/extensiones P2; no definen el MVP.

## 0. Los 5 objetivos oficiales

El enunciado pide probar la herramienta con estos cinco ([`CHALLENGE.md`](CHALLENGE.md)). Tres **se mueven**
(movimiento propio) y dos **cambian de brillo** (variables). **Ninguno se mueve más de ~2 píxeles SPHEREx** en todos
los datos que hay hoy (DR1 + QR3).

🆕 **Los cinco tienen registro de validación con resultado `success`** (§0.0). Son análisis offline de los FITS
reales, cada uno repetido por una revisión adversarial independiente con código propio. La revisión humana y el paso 6
de [`VALIDATION.md`](VALIDATION.md) (recorrido en la URL pública) siguen pendientes. Ninguno es un descubrimiento: se
recuperan movimientos y variabilidad ya catalogados.

### 0.0 Qué establecieron los registros de validación 🆕

Resumen para citar en la UI y en la entrega. Los números salen de los registros enlazados; (A) es el análisis
original y (R) la revisión independiente. «px» = píxel SPHEREx de 6,15″.

| Objetivo | Registro | Identidad de la fuente medida | Qué se midió con SPHEREx | Saturación | Qué **no** se puede afirmar |
|---|---|---|---|---|---|
| Barnard's Star | [barnards-star.md](validation/barnards-star.md) (#46) | Gaia DR3 4472832130942575872 (G = 8,19). Fuente dominante: todas las fuentes Gaia a ≤ 30″ son ≥ 6,8 mag más débiles | 358 exposiciones (dr1 239 + qr3 119), 2025-08-15 → 2026-09-22. S0→S2 (misma orientación, 0,98 años entre medias): **10,24 ± 0,11″ = 1,665 ± 0,018 px a PA 354,1 ± 2,1°** (A) y **10,18 ± 0,09″ = 1,655 ± 0,014 px a PA 355,4 ± 0,6°** (R); esperado 10,24″ = 1,665 px a PA 355,7°. «Sin movimiento» descartado a 93σ (A) y 119σ (R). µ (R): (−858 ± 117, +10311 ± 87) mas/año; catálogo (−803, +10375) | `OVERFLOW` en el núcleo en **357 de 358**; `NONLINEAR` nunca; NaN en 240 (en D5/D6 solo 4 de 119). Astrometría desde el ala de la PSF | La **paralaje** (el giro de 180° de S1 es degenerado con su fase). El brillo del núcleo. En los 40 PNG el movimiento está (la meseta se corre 1,60 px; se esperaban 1,68), pero no se ve a simple vista: disco blanco de ~7 px y sin marcador |
| ε Indi B | [eps-indi-b.md](validation/eps-indi-b.md) (#36) | Gaia DR3 6412596012146801152 (G = 18,03, RUWE 4,30). Ba+Bb = **una sola fuente** | 458 frames en SIA en vivo (dr1 338 + qr3 120; 2026-11-14 19:24 UTC), 2025-04-24 → 2026-10-02, 4 temporadas. Detectada en ~440 de 458; **no en D1 por debajo de ~0,83 µm** (espectro de enana T, INFERIDO). S0→S3 (1,385 años entre medias): **1,031 ± 0,006 px** (A) y **1,026 ± 0,007 px** (R), ± ~0,016 px de sistemático, a PA 126,5–126,7 ± 0,4°; esperado 1,028–1,030 px a PA 125,8–125,9°; > 50σ con el sistemático | No satura | Separar Ba de Bb; la órbita Ba–Bb. Hay un offset constante de ~0,6″ entre fotocentro y catálogo, de causa INFERIDA. ε Ind A (402,6″ al oeste) queda **fuera** de la grilla publicada de 9′: solo se ve su halo en el borde oeste |
| WISE 0855−0714 | [wise-0855.md](validation/wise-0855.md) (#36) | Sin contraparte Gaia DR3. SIMBAD: Y2. **Mezclada** con Gaia DR3 5756956644387831296 (G = 16,3), a 1,85 / 1,32 / 0,70 px en S0/S1/S2 | 258 frames, **solo DR1**, 2025-05-05 → 2026-05-14. **Solo se ve en D5/D6 (3,8–5,0 µm)**: SNR mediana por exposición 3,4–3,8 (≥ 5σ en 22 de 93 frames D5/D6) y **SNR 21–25** sumando por detector; en D1–D4 el flujo es compatible con 0. S0→S2 (360 d): **8,51 ± 0,39″ = 1,38 ± 0,06 px a PA 278,5 ± 2,6°** (A) y **8,41 ± 0,35″ a PA 277,5 ± 2,4°** (R); esperado 8,03″ = 1,31 px a PA 274,6°. Modelo estático rechazado (Δχ² 258–412) | No satura | Que se vea en el blink publicado (12 frames D5/D6, SNR mediana 2,1). µδ sale 1,6–3,1σ por encima del catálogo por la mezcla (INFERIDO). Los flujos absolutos dependen del modelo de PSF (~11 %) |
| RW Aurigae | [rw-aurigae.md](validation/rw-aurigae.md) (#36) | A+B sin resolver (1,49″). 🆕 **A = Gaia DR3 156430817820015232, B = 156430822114424576** (verificado en esta revisión, §0.3) | 335 frames (dr1 226 + qr3 109), 2025-09-01 → 2026-09-16. Variabilidad **solo en D1 (0,74–0,88 µm)**, en pares del mismo detector con \|Δλ\|/λ < 1 % y sin flags: **se abrillanta ~1 mag a 0,75–0,77 µm entre el 2025-09-02 y el 2026-09-08** (−1,005 y −1,031 mag; −0,99 y −0,97 con punto cero). Estrellas de comparación: σ robusta 0,046–0,049 mag, máximo 0,27 | `OVERFLOW` en **304 de 335**; ningún frame D2–D6 limpio (0 de 279). Quedan 17 frames limpios, todos en D1, y 8 pares. El desglose del registro («todo D2–D6 y 37 de 56 en D1») no cierra con 304: ver «Conteo de saturación de RW Aur» en la revisión del 3D | La causa física. Un «brillo medio de temporada» (dentro de S0 también parece cambiar, INFERIDO). Variabilidad en D2–D6. Los 40 PNG no muestran el cambio: la estrella vale 255 en todos. La curva de luz precalculada de la app (#79, #83) reproduce los 8 pares con ≤ 0,003 mag de diferencia |
| R Draconis | [r-draconis.md](validation/r-draconis.md) (#36) | Gaia DR3 1648328016354496384 (G = 6,37, VARIABLE). Sin mezcla: dentro de 45″ solo hay dos fuentes de G ≈ 19 | 2493 frames (dr1 413, qr3 126, dr1_deep 1225, qr3_deep 729), MJD 60790–61310 (520 d). Fotometría **relativa del ala de la PSF**, mismo detector y λ en bins de 1–1,5 %: **0,5–1,3 mag pico a pico** según el detector; permutación p ≤ 0,003 (D2 marginal); sigue la curva V contemporánea de AAVSO con retrasos de −1 a +47 d. **Período efectivo ~260 d** (bootstrap 95 %: 255–265 d), igual al último ciclo AAVSO (258 d; el anterior duró 235 d) y compatible con Gaia DR3 (247,2 ± 6,0 d) | `OVERFLOW` en **2488 de 2488** frames con la estrella en el detector; `NONLINEAR` nunca | Fotometría del núcleo o flujo absoluto. Decir que SPHEREx «midió 247 d». El campo publicado (40 PNG, ninguno deep) no muestra la variabilidad. La curva de luz precalculada de la app (#79, #83) usa solo el sondeo ancho: 539 de 2493 exposiciones (ver «Revisión científica de las curvas de luz») |

Comunes a los cinco: scripts en el scratch local (no versionados), figuras en [`validation/figures/`](validation/figures/),
revisión humana pendiente, paso 6 pendiente. Los registros no usan detección automática.

### 0.1 Astrometría de referencia

✅ Sesame/SIMBAD en CfA, 2026-11-14 (CDS Estrasburgo está degradado). ICRS, **época de referencia J2000.0**,
`µα*` = µα·cos δ. Está copiada en los comentarios de `pipeline/errante/config/fields.toml` para no depender de
SIMBAD en vivo. 🆕 Ojo: el comentario de RW Aur en `fields.toml` (línea 70) tiene A y B invertidos (ver la fila y §0.3).

| `id` (fields.toml) | Objetivo | Tipo | J2000 (°) | J2000 (sexagesimal) | µα*, µδ (mas/año) | plx (mas) |
|---|---|---|---|---|---|---|
| `barnards-star` | Barnard's Star | enana roja M4V, el mayor movimiento propio | 269.45207696, +4.69336497 | 17h57m48.498s +04°41′36.11″ | −801.551, +10362.394 | 546.976 |
| `eps-indi-b` | ε Indi B (Ba+Bb) | par de enanas marrones T1V+T6V que orbita ε Ind A | 331.04414659, −56.7828442 | 22h04m10.595s −56°46′58.24″ | +3981.977, −2466.832 | 270.658 (Gaia DR3) |
| `wise-0855` | WISE 0855−0714 | enana marrón Y2 (SIMBAD); 🆕 WS7 usa ~Y4 citando Kirkpatrick+2021 y Luhman+2024 (no re-verificado aquí) | 133.81890825, −7.247048 | 08h55m16.538s −07°14′49.37″ | −8123.7, +673.2 | 439.0 |
| `rw-aurigae` | RW Aurigae | estrella T Tauri (K1/5e+K5e), variable irregular | 76.95652603, +30.40143817 | 05h07m49.566s +30°24′05.18″ | +7.23, −20.33 (Hipparcos) | 15.42 (Hipparcos); 🆕 Gaia DR3 (corregido): **A 5.454 ± 0.332 (RUWE 16,4, no fiable), B 6.406 ± 0.044** → ~156 pc con la de B |
| `r-draconis` | R Draconis | variable Mira; tipo espectral M4.5–6e (SIMBAD) o M5e–M9eIII (GCVS y VSX); 🆕 P de catálogo 245,6 d (GCVS), 246,12 d (VSX), 247,2 ± 6,0 d (Gaia DR3) | 248.16761083, +66.75497942 | 16h32m40.227s +66°45′17.93″ | −20.643, +6.149 | 1.2509 |

### 0.2 Qué esperar en los datos SPHEREx

✅ Cobertura: SIA2 sobre `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3` y `spherex_qr3_deep` (detalle por
temporada y detector en [`DATA.md`](DATA.md) §3.0). 🧮 Posición: propagación lineal desde J2000 con el movimiento
propio hasta la **época media** de los frames; es el centro que usa `fields.toml`. 🧮 Desplazamiento: |µ| × (último
frame − primer frame); píxel = 6,15″.

| Objetivo | Época media | 🧮 Posición a la época media (°) | Línea de base | 🧮 Desplazamiento total | Frames | Temporadas | 🧮 Lat. eclíptica |
|---|---|---|---|---|---|---|---|
| Barnard | MJD 61104 (2026.17) | 269.44623, +4.76870 | 1,10 años | 11,5″ = **1,86 px** | 358 | 3 | +28,2° |
| ε Ind B | MJD 61042 (2026.00) | 331.09665, −56.80066 | 1,44 años | 6,7″ = **1,10 px** | 460 (🆕 458 en SIA en vivo el 2026-11-14 19:24 UTC; causa sin verificar, [DATA.md](DATA.md) §3.0) | 4 | −41,5° |
| WISE 0855 | MJD 61035 (2025.99) | 133.75980, −7.24219 | 1,02 años | 8,3″ = **1,36 px** | 258 (solo DR1) | 3 | −23,6° |
| RW Aur | MJD 61107 (2026.18) | 76.95659, +30.40129 | 1,04 años | 0,02″ ≈ **0 px** | 335 | 3 | +7,5° |
| R Dra | MJD 61115 (2026.20) | 248.16723, +66.75502 | 1,43 años | 0,03″ ≈ **0 px** | 2493 (1954 deep) | cobertura casi continua | +81,4° |

Cómo leer esto:

- Por año: Barnard ~1,7 px, WISE 0855 ~1,3 px, ε Ind B ~0,8 px. La PSF tiene FWHM ≈ 7,5″ ≈ 1,2 px (D1): el
  desplazamiento total es del orden de un ancho de PSF. **A escala nativa no se ve nada**: hacen falta zoom
  pixelado, retícula, posición predicha en cada época y resta de temporadas (aparece un dipolo +/−).
  🆕 Confirmado en los registros: en los 40 PNG de Barnard la meseta saturada se corre 1,60 px, pero es un disco
  blanco de ~7 px, y ninguno de los cinco campos marca el objetivo (`known.json` vacío). Las diferencias de temporada muestran el dipolo de ε Ind B y de
  WISE 0855 (este último solo con todos los frames D5/D6, no con los 40 del build).
- 🆕 Paralaje: amplitud = plx ≤ 0,55″ (≤ 0,09 px). Es chica frente al movimiento propio, pero **no es despreciable
  para astrometría por debajo de 0,1 px**: en WISE 0855 alterna −0,43 / +0,41 / −0,43″ en E entre temporadas
  (0,14 px pico a pico) y los registros la incluyen. En Barnard (±0,55″ en E) **no se puede medir** con estos datos: el
  detector está girado 180° en S1 justo en la fase opuesta de paralaje, y el sesgo de centroide que depende de la
  orientación es degenerado con ella ([registro](validation/barnards-star.md), problema 5). Se fija en Gaia.
- La propagación lineal ignora la aceleración de perspectiva (~0,4″ en 26 años para Barnard): despreciable. 🆕 En la
  época media de Barnard suma +0,066″ en Dec (< 0,02 px).
- Una sola exposición de RW Aur o R Dra "parpadea" en brillo aunque la estrella no cambie: ver §0.4.

### 0.3 Notas por objetivo

- **Barnard's Star.** Muy brillante en el infrarrojo (K = 4,5). 🆕 ✅ **Satura**: `OVERFLOW` en el núcleo en 357 de
  358 exposiciones (la única limpia es `2025W34_2B_0030_1D6`, 4,58 µm), `NONLINEAR` nunca; NaN en 240, pero píxeles
  `OVERFLOW` finitos en 339 ([registro](validation/barnards-star.md); [DATA.md](DATA.md) §3.2). Es la prueba de cordura
  principal y el plan B del video. Gaia DR3 4472832130942575872 (época 2016.0) coincide con SIMBAD propagado ✅. El
  centro anterior de `fields.toml` (2025.5) estaba a 1,0″ de la propagación con Gaia.
  - 🆕 Movimiento medido entre S0 y S2: 1,655–1,665 px a PA 354–355°, contra 1,665 px a PA 355,7° esperados (§0.0).
    Para estrellas saturadas hay que enmascarar `SUR_ERROR` junto al núcleo y re-centrar; una gaussiana deja un
    residuo hacia el oeste de 0,2–0,3″ que el perfil radial libre no deja.
  - 🆕 **La paralaje no se puede medir con estos datos** (ver §0.2). El movimiento propio se cita desde S0→S2.
  - 🆕 `GJ 699` en Sesame CfA devuelve una posición de época antigua, a 8,6′: resolver por «Barnard's Star» o por el
    `source_id` de Gaia.
- **ε Indi B.** SIMBAD no tiene entradas separadas para Ba y Bb ✅: **SPHEREx no separa el par** con píxeles de
  6,15″ (verá una sola fuente; conviene decirlo en la UI). **ε Ind A**, brillante, está a **~402″ (~6,7′) al oeste**
  ✅: entra en un FOV ≥ ~14′. 🆕 En la grilla publicada de 9′ queda afuera; su halo se ve en el borde oeste de los PNG,
  marcado `HALO`, y el `BLOOM` es suyo. No hay píxeles `GHOST` en los 498 patches revisados (antes figuraba como
  ejemplo de GHOST, INFERIDO: no se confirmó). Cobertura despareja: D1/D4 tienen 3 frames en la 1.ª temporada y 0 en la
  última ✅. Gaia DR3 6412596012146801152, G = 18,03; J = 11,9, H = 11,3, K = 11,2 ✅.
  - 🆕 Medido: 1,026–1,031 px entre S0 y S3, contra 1,028–1,030 px esperados (§0.0). **No se detecta en D1 por debajo
    de ~0,83 µm** (3 de los 5 D1 publicados, incluidos los dos de S1): no es un error de datos.
  - 🆕 Offset constante de ~0,6″ (0,1 px) entre fotocentro y catálogo, mayor en D6; INFERIDO, sin verificar: el
    fotocentro infrarrojo de Ba+Bb no es el de Gaia, o el movimiento orbital del par desde 2016 (RUWE 4,3).
- **WISE 0855−0714.** La coordenada del enunciado (08h55m10.831s −7°14′42.53″ = 133.79513, −7.24515) es de época
  **~2010** (🧮 retro-propagación: 2010,45 por RA, 2010,16 por Dec). A la época media de los datos el objeto está
  **~126″ (~20 px) al oeste** de esa coordenada (🧮; 126,6″ en el [registro](validation/wise-0855.md); entra en un FOV ≥
  ~8′ centrado en la del enunciado). Está a ~2,3 pc (plx 439 mas). Es extremadamente rojo: J = 25,0 y H = 23,8 (SIMBAD),
  W1 = 16,23 y W2 = 13,70 (AllWISE, Vega) ✅. No tiene frames en QR3 ✅. CatWISE (`catwise_2020` en IRSA TAP) lo lista
  con pmRA ≈ −7,9 a −8,0″/año ✅ (el registro lo re-verificó: el objeto aparece partido en varias entradas CatWISE2020).
  - 🆕 ✅ **Visibilidad medida** (antes: «probablemente solo en coadds, INFERIDO»): se ve **solo en D5/D6** (3,8–5,0 µm)
    y **también en exposiciones sueltas**, con SNR mediana 3,4–3,8 por exposición (≥ 5σ en 22 de 93); sumando por
    detector, SNR 21–25. En D1–D4 no hay señal. Flujos: 0,28–0,32 mJy en D5 y 0,49–0,54 mJy en D6 según el modelo de
    PSF.
  - 🆕 **Mezcla** con Gaia DR3 5756956644387831296 (G = 16,3; su W2 es el 29 % del de WISE 0855), a 0,70 px en S2. La
    posición de S2 depende de cómo se modelen la estrella y la PSF.
  - 🆕 Medido: 8,41–8,51″ (1,37–1,38 px) entre S0 y S2, contra 8,03″ esperados (§0.0). En el blink publicado (2 frames
    por temporada y detector, SNR mediana 2,1) **no se ve de forma convincente**: hace falta un coadd o una selección
    por λ en el máximo del espectro (4,25–4,70 µm).
- **RW Aurigae.** T Tauri (SIMBAD: `TT*`, sin período) ✅: **no se mueve, cambia de brillo** de forma irregular.
  J = 8,4, K = 7,0. VSX (`B/vsx`): tipo CTTS/ROT+CTTS, V 9,2–13,6. La paralaje de Hipparcos (15,42 ± 3,69 mas) no
  coincide con Gaia DR3: usar Gaia. Latitud eclíptica +7,5°: pueden cruzar asteroides (SkyBoT, P1).
  - 🆕 ✅ **Identidad A/B en Gaia DR3, corregida** (antes este documento decía A = 6,406 mas y B = 5,454 mas, al revés).
    Verificado en esta revisión (2026-11-15 03:29 UTC): según Gaia DR3 (TAP de ESA), la fuente 156430822114424576
    (G = 12,18, plx 6,406 ± 0,044 mas, RUWE 1,50) está a **1,493″ y PA 254,4°** de 156430817820015232 (G = 13,04, plx
    5,454 ± 0,332 mas, RUWE 16,4). El WDS (VizieR CfA `B/wds`, 05078+3024 JOY 5) da para **A→BC** PA 254° y 1,50″
    (2022), con A más débil (13,0 contra 12,2) por sus oscurecimientos. Por lo tanto **A = 156430817820015232 y B =
    156430822114424576**, como usa WS7 (`systems/catalog.py`, citando a Kurtovic et al. 2024). La distancia sale de la
    paralaje de **B** (~156 pc), porque la de A no es fiable.
  - 🆕 ✅ **Satura** (`OVERFLOW`) en 304 de 335 frames, y ningún frame D2–D6 está limpio (0 de 279). **Solo D1 es
    medible** (17 frames limpios, 8 pares). El desglose «todo D2–D6 y 37 de 56 en D1» del registro no cierra con 304
    (ver «Conteo de saturación de RW Aur» en la revisión del 3D). Ya **no** vale «con 3 temporadas hay 3 puntos de
    comparación por detector».
  - 🆕 Medido en D1: se abrillanta ~1 mag a 0,75–0,77 µm entre el 2025-09-02 y el 2026-09-08 (§0.0). Hay además un
    salto de +0,38 mag sin explicar entre dos exposiciones consecutivas separadas 2,15 min (registro, limitaciones).
  - 🆕 El centroide medido cae más cerca del fotocentro Gaia A+B que de la posición SIMBAD/Hipparcos del centro de
    `fields.toml` (0,9–1,1″ de diferencia, ≤ 0,18 px): cosmético.
- **R Draconis.** Mira; período de catálogo 🆕 ✅ 245,6 d (GCVS, VizieR CfA `B/gcvs`, re-consultado el 2026-11-15 03:33
  UTC; el primer intento de las 03:29 dio «database is not currently reachable»), 246,12 d (VSX, OID 13673), 247,2 ±
  6,0 d (Gaia DR3 LPV, archivo de ESA); otras fuentes de SIMBAD: 247,0 y 246,0 d. A 8,6° del polo eclíptico norte, tiene
  2493 frames (1954 de las colecciones deep) y cobertura casi continua entre MJD 60916 y 61310 ✅. 🧮 La línea de base
  (520 d) cubre ~2,1 ciclos: **el mejor caso para una curva de luz**. D2/D5 tienen solo ~89 frames contra ~580 de los
  otros detectores.
  - 🆕 ✅ **Satura en todos los frames** (`OVERFLOW` en 2488 de 2488). La variabilidad se midió en el ala de la PSF
    (§0.4).
  - 🆕 **Período efectivo medido con SPHEREx: ~260 d** (95 %: 255–265 d), no 247 d. Coincide con el último ciclo de
    AAVSO (258 d; el anterior fue de 235 d): las Miras cambian de ciclo a ciclo. Citar 247 d solo como valor de
    catálogo. Para la fase, usar la curva AAVSO contemporánea, no la efeméride VSX extrapolada (se desvía hasta 15 d).
  - 🆕 La búsqueda por defecto (`spherex_dr1,spherex_qr3`) excluye las colecciones deep, que aportan casi todo el
    muestreo: el campo publicado (40 frames) no tiene ninguno. Lo mismo pasa con la curva de luz precalculada de la app
    (#79): 539 de 2493 exposiciones, que no distinguen 259 d de 247 d (ver «Revisión científica de las curvas de luz»).

### 0.4 Variabilidad con un filtro lineal variable

**Por qué el brillo de exposiciones sueltas no sirve.** En cada exposición el objetivo cae en otro lugar del
detector y se mide en **otra λ**. Como el espectro de una estrella no es plano (y la PSF cambia con λ), su brillo
cambia de exposición a exposición **aunque la estrella sea constante**. Un video de exposiciones individuales
"parpadea" y no permite distinguir variabilidad de color. Además, el PNG no es una medida: el stretch actual satura
las fuentes brillantes (✅ un cambio ×2 de la estrella central da el mismo pico 255).

**Método** (❓ INFERIDO, a validar con datos; los hechos que lo sostienen son ✅; 🆕 los pasos 3 y 4 quedaron
validados en RW Aur y R Dra y el paso 1 no sirvió para estrellas saturadas: ver «Lo que de verdad se validó» al final
de esta sección):

1. **Coadds por temporada × detector** (frame por defecto del video). En cada temporada cada detector junta
   ~17–25 exposiciones del objetivo (Barnard, RW Aur ✅), del orden de sus 17 canales. Cada coadd promedia
   aproximadamente el mismo rango de λ, así que **los coadds de temporadas distintas son comparables**: lo que cambia
   entre ellos es movimiento o brillo real. Peso 1/`VARIANCE`, `IMAGE − ZODI`, y el **mismo stretch por detector en
   todas las temporadas** ("modo fijo"). Cuidado con la cobertura despareja (ε Ind B en D1/D4, la 1.ª temporada de
   WISE 0855): mostrar `n_inputs` y el rango de λ de cada coadd (conviene agregarlos al contrato como campos opcionales).
2. **Espectro por temporada.** Puntos (λ, flujo) coloreados por temporada. Una estrella constante superpone sus
   espectros; una variable los desplaza (o les cambia la forma). Las **estrellas de comparación** del mismo campo
   tienen que superponerse: son el control de calibración.
3. **Curva de luz corregida por λ.** Para cada exposición, `flujo / espectro medio del objetivo interpolado en esa λ`,
   graficado contra MJD por detector y normalizado con estrellas de comparación (mismo campo, brillo parecido, no
   variables). R Dra: cobertura densa, ~2 ciclos → curva de luz real. RW Aur: 3 temporadas → 3 puntos por detector
   (variabilidad irregular, sin período). 🆕 En la práctica solo D1 tiene frames sin saturar (8 pares útiles).
4. **Cuidados.** Saturación (`OVERFLOW` en el objetivo; 🆕 ✅ verificada en Barnard, RW Aur y R Dra, `NONLINEAR` no
   aparece nunca), flags de vecinas brillantes (GHOST/HALO/BLOOM), apertura acorde a la PSF de cada frame (`PSF_FWHM`
   cambia por detector; 🆕 ✅ el del header es más ancho que el núcleo real: la mejor gaussiana mide 0,70–0,86 × header).
   Los pares D1/D4, D2/D5 y D3/D6 se toman a la vez ✅: dan color simultáneo.

🆕 **Lo que de verdad se validó (registros del 14 y 15/11).** El paso 1 (coadds por temporada) **no** se usó para medir
la variabilidad de ninguno de los dos blancos variables, porque están saturados: los coadds de `errante compare` tienen
el núcleo vacío o a 255 y mezclan λ distintas. Lo que funcionó fue:

- **RW Aur** ([registro](validation/rw-aurigae.md)): fotometría de apertura (r = 3 px, fondo en 6–10 px) en
  **exposiciones individuales** de D1 sin flags, comparadas **de a pares** del mismo detector con \|Δλ\|/λ < 1 % y
  temporadas distintas. Control: las estrellas de comparación Gaia del mismo campo, cada una a su propia λ, más un punto
  cero por frame. Es la variante "λ compatible" del paso 3, sin coadds.
- **R Dra** ([registro](validation/r-draconis.md)): flujo **relativo del ala de la PSF** (anillo de 10–20 px fuera de
  `BLOOM`, menos un fondo en 40–60 px). Modelo por detector: una constante por bin de λ (1–1,5 %) más una señal temporal
  (sinusoide, curva V de AAVSO escalada o bloques libres). Significancia por permutación de visitas, con controles y
  la curva AAVSO contemporánea como prueba independiente de fase.
- **WISE 0855** ([registro](validation/wise-0855.md)): los coadds por temporada con **todos** los frames D5/D6 sí
  sirvieron, pero para ver el movimiento (dipolo), no la variabilidad.

En la UI conviene distinguir "exposiciones individuales (el brillo cambia por λ)" de "coadds por temporada
(comparables)". 🆕 Y, para Barnard, RW Aur y R Dra, avisar que **el brillo del PNG no es una medida**: el núcleo está
saturado y el stretch lo lleva a 255.

## 1. ¿Por qué se mueven las cosas en el cielo?

Las estrellas están tan lejos que, en meses, casi no se mueven (salvo las muy cercanas: *movimiento propio*,
p. ej. Barnard 10″/año). Los objetos del Sistema Solar se mueven por dos razones:

1. **Su propio movimiento orbital** (un objeto a r UA va a ≈ 29.8/√r km/s).
2. **El movimiento de la Tierra/SPHEREx** (29.8 km/s), que produce un desplazamiento aparente (paralaje)
   inversamente proporcional a la distancia.

### SPHEREx mira a ~90° del Sol (¡importante!)

SPHEREx observa en círculos perpendiculares a la dirección del Sol (como WISE). En la eclíptica a 90° del Sol,
la Tierra se mueve **a lo largo de la línea de visión**, así que el paralaje *dentro de una visita* casi
desaparece y los objetos lejanos se ven **casi quietos durante horas**. Entre pasadas separadas ~6 meses, en
cambio, la Tierra está del otro lado de su órbita → **desplazamientos enormes** por paralaje.

Órdenes de magnitud (órbitas circulares, aproximación r ≫ 1; píxel SPHEREx = 6.15″):

| r [UA] | ejemplo | en oposición ["/h] | a ~90° del Sol ["/h] | a ~90° [px/día] | entre pasadas a 6 meses |
|---|---|---|---|---|---|
| 2.7 | cinturón principal | 34 | ~decenas | ~100+ | otro lugar del cielo |
| 5.2 | troyanos de Júpiter | 20 | ~10 | ~50 | otro lugar del cielo |
| 30 | Neptuno / Plutinos | 4.2 | 0.9 | 3.5 | ~2200 px |
| 45 | Makemake / KBO clásico | 2.9 | 0.5 | 1.9 | ~1500 px |
| 100 | disco disperso | 1.3 | 0.15 | 0.6 | ~670 px |
| 500 | tipo Planeta Nueve | 0.28 | 0.013 | 0.05 | ~130 px |
| 800 | Planeta Nueve lejano | 0.18 | 0.007 | 0.03 | ~85 px |

Fórmulas: oposición `≈ 147.8″/h · (1 − 1/√r)/(r − 1)` (implementada en `errante.science.motion`);
a 90° `≈ 147.8″/h / (√r · √(r² − 1))`; paralaje entre pasadas `≈ 2 UA / r` rad (geometría real: WS3).

**Consecuencias para el diseño:**
- Asteroides: pueden estudiarse **dentro de una visita** (horas) con linking lineal (WS2, P2).
  Su recuperación depende de cobertura, brillo y calidad; no se promete sin una prueba real.
- TNOs: ~1–4 px/día a 90° → se necesitan observaciones separadas por ≥ 1 día del mismo campo (ver en DATA
  cuántas hay; los **campos profundos** de los polos eclípticos tienen muchas más épocas).
- Un Planeta Nueve: prácticamente **quieto dentro de una visita** y saltando ~100 px entre pasadas. Buscarlo
  requiere *shift-and-stack* a lo largo de órbitas hipotéticas (rango de distancias) entre pasadas — es una
  demo/visualización educativa posible, no un resultado prometido para esta ventana de hackatón.
- La estimación de distancia "por velocidad en oposición" del demo es **solo orden de magnitud**; WS3 debe
  reemplazarla por la geometría real usando la posición de SPHEREx (`X_SC…` en el header) y la fecha.

## 2. ¿Qué tan débil es un Planeta X?

- Predicciones para el Planeta Nueve (Brown & Batygin 2021, AJ 162, 219): semieje ≈ 380 UA (perihelio
  ≈ 300 UA, hoy probablemente cerca del afelio, a varios cientos de UA), ≈ 6 masas terrestres, inclinación
  ≈ 16°, brillo en el visible del orden de **V ≈ 20–23** según distancia y albedo. **Verificar los números en
  el paper antes de citarlos** en la UI o el pitch (tarea de WS3). 🆕 2026-11-15: siguen sin verificar, y ningún
  texto de la UI ni de la entrega los usa (revisado en WS3-7).
- SPHEREx no está optimizado para objetos tan débiles en una sola exposición. **No sabemos** su profundidad
  real para nuestros métodos → la medimos con **inyección-recuperación** (WS2): plantamos objetos falsos en
  imágenes reales y vemos cuáles recuperamos. Esa tabla de límites es parte central del producto.

## 3. Lo que SPHEREx sí hace genial: espectros

Cada exposición mide una longitud de onda distinta en cada punto (filtro lineal variable). Un objeto observado
varias veces junta un **espectro 0.75–5 µm** gratis:
- **asteroides**: luz solar reflejada; banda de hidratación ~3 µm en algunos tipos.
- **enanas marrones frías**: muy rojas, absorción de metano ~3.3 µm, brillantes en 4–5 µm.
- **estrellas**: caen hacia longitudes de onda largas.

Ojo: diferencias de brillo entre exposiciones pueden venir de distinta longitud de onda, variabilidad real
o efectos instrumentales. Comparar brillos a longitud de onda compatible y con errores/calibración controlados;
mismo detector no basta. Para RW Aurigae y R Draconis usar fotometría del FITS, no el brillo de PNGs autoescalados.

### 3.1 Contexto de catálogo de un punto o un nombre (WS3-10, C05)

`errante.science.context.object_context` / `errante object`: quién es el objeto y qué midieron **otros**
catálogos (nada de esto es SPHEREx). Respuestas crudas grabadas en `pipeline/tests/fixtures/ws3/context/`.
Verificado en vivo el 2026-11-15 (✅ consultas reales; los números salen de esas respuestas):

- ✅ Servicios: Sesame en CfA (SIMBAD), TAP del archivo Gaia de ESA (`gaia_source`, `astrophysical_parameters`,
  `external.gaiaedr3_distance`, `vari_long_period_variable`), VizieR CfA (VSX `B/vsx/vsx`, 2MASS `II/246/out`,
  AllWISE `II/328/allwise`, respaldo Gaia `I/355/gaiadr3`), NASA Exoplanet Archive `pscomppars` con caja
  ra/dec (sin `CONTAINS`).
- ✅ Gaia se cruza **después** de propagar cada candidato de 2016.0 a la época SPHEREx (Barnard está a ~100″
  de su posición 2016). En un click, si dentro del radio hay una fuente ≥ 2,5 mag más brillante en G que la más
  cercana, se adopta esa (domina el píxel de 6,15″: a 5,5″ de R Dra, G = 6,4, la más cercana es una G = 19,4).
- ✅ Identificación incierta (varias fuentes parecidas en el radio, o la adoptada a más de medio radio del click)
  ⇒ nada que dependa de la identidad queda `verified`: valores Gaia, SIMBAD alcanzado por el id Gaia, VSX cruzado
  por posición y magnitudes 2MASS/AllWISE (`identity_uncertain`). Por nombre, SIMBAD es el objeto pedido.
- ✅ Extragalácticos: 3C 273 (SIMBAD `BLL`, DSC quasar 0,85, paralaje −0,016 ± 0,021 mas) recibía Teff GSP-Phot
  9880 K y distancia Bailer-Jones 17119 pc "verificadas". Ahora, si SIMBAD lo tipa como galaxia/AGN/QSO (códigos
  de la tabla `otypedef` de SIMBAD, TAP CfA) no se muestran parámetros estelares; con DSC ≥ 0,5 o tipo candidato
  se muestran sin verificar y con advertencia.
- ✅ Distancia: Bailer-Jones solo si S/N de paralaje ≥ 1, y `verified` solo si ≥ 5; por debajo de 1 sería solo el
  prior galáctico (núcleo de M87: −1,47 ± 0,43 mas daba 5941 pc) y no se muestra.
- ✅ ESP-UCD da incertidumbre: ε Ind B `teff_espucd` 1417 ± 98 K (`teff_espucd_uncertainty`).
- ✅ Un servicio que no responde se informa como "could not be reached … not a negative result", nunca como "no
  catalogado". VizieR CfA devuelve a veces un RESOURCE vacío (sin `#Table`) para conos con filas: se reintenta y
  no se cachea; los tests de red reintentan y se saltean si el servicio sigue sin responder.
- ✅ El WAF (Cloudflare) del Exoplanet Archive responde 403 a `where 1=1 and …`; cerca de los polos se usa
  `ra >= 0`. Las posiciones de `pscomppars` son de época Gaia (ε Ind A a 2,4″ de su posición DR3 2016.0): la
  separación a un anfitrión vecino se da en 2016.0 (ε Ind A–B ≈ 404″).
- Límite: el respaldo VizieR (`I/355/gaiadr3`) no se consulta por probabilidades DSC ni trae FLAME/Bailer-Jones/
  LPV; si la ESA no responde, solo protegen el tipo SIMBAD y el S/N de paralaje.

## 4. Encuadre honesto (para UI, pitch y entrega)

- "Planeta X es nuestra motivación científica, no un resultado prometido."
- Estados: `known` (coincide con catálogo), `unconfirmed` (sin match: puede ser artefacto, error de medición u
  objeto no catalogado), `artifact` (rechazado por validación), `injected` (simulado).
- Mostrar siempre: cuántas detecciones, residuo del ajuste, flags tocados, límites medidos.
- Validación obligatoria: los cinco blancos de `VALIDATION.md`, incluidos Epsilon Indi B y las dos variables.
  Asteroides/TNOs son ensayos adicionales. Separar intentos realizados de recuperaciones demostradas;
  citar métodos, épocas, calidad e incertidumbres al informar resultados.
- 🆕 Los cinco blancos son objetos conocidos: recuperar su movimiento o su variabilidad es una **validación**, no un
  descubrimiento. Decir «medido offline en los FITS» cuando el número no sale del producto publicado, y «revisión humana
  pendiente» mientras lo esté.
- 🆕 Para estrellas saturadas (Barnard, RW Aur, R Dra), el brillo del PNG no es una medida.

## 5. Glosario rápido

**MJD**: fecha juliana modificada (días). **RA/Dec**: coordenadas ecuatoriales (grados). **PA**: ángulo de
posición, desde el norte hacia el este. **UA**: distancia Tierra–Sol. **TNO/KBO**: objeto transneptuniano /
del cinturón de Kuiper. **Blink comparator**: alternar imágenes de distintas fechas para ver qué cambia (así se
descubrió Plutón en 1930). **Cutout**: recorte de una imagen. **HiPS**: formato de imágenes de todo el cielo por
teselas (lo usa Aladin). **Shift-and-stack**: sumar imágenes desplazadas según un movimiento supuesto para
detectar objetos débiles.

## Revisión científica de textos (WS3-7, 2026-11-15)

Revisión de todo texto que ve un usuario o un jurado, en `main` `3713d3b`: la UI (`frontend/src`, `frontend/index.html`,
`frontend/public/sky-map.html`), los facts 3D (`pipeline/errante/systems/catalog.py`), las descripciones de los campos
(`fields.toml` → `field.json`), las notas de los productos publicados, `README.md`, `AI_USAGE.md` y `docs/submission/`.
Cada afirmación se contrastó con los registros de [`validation/`](validation/), [`DATA.md`](DATA.md), §0 de este
documento y, cuando hizo falta, con un servicio en vivo (lista al final). WS3 no edita esos archivos: cada dueño aplica
su fila. El texto sugerido está en inglés para la UI y la entrega, y en español para los documentos internos.

**Resumen.** No hay exageraciones: nada dice «discover», «new object» ni «Planet X found». El problema es el opuesto.
Varios textos que leen los jueces siguen diciendo que **no hay datos SPHEREx reales ni ensayos de los cinco
blancos**, cuando hay cinco campos reales y cinco registros `success`. También faltan créditos (Gaia/ESA, AllWISE,
CfA, AAVSO), la declaración de uso de Claude está incompleta, hay un enlace de crédito roto y ningún texto avisa que
Barnard, RW Aur y R Dra están saturados.

Severidad: **bloquea** = corregir antes de enviar (texto falso en materiales de evaluación); **importante** =
corregir antes del freeze si se puede; **menor** = mejora. La tabla tiene 47 filas: 8 bloquean, 24 son importantes y 15
menores.

Todo texto sugerido que cite un número de validación dice «offline»: esos números salen de análisis de los FITS, y el
producto publicado todavía no los muestra (§4). `pipeline/tests/test_science_review_texts.py` comprueba esa regla, los
conteos de arriba y que los facts del bloque **A5** se lean bien con su unidad.

| archivo:línea | texto actual | problema | texto sugerido | severidad | dueño |
|---|---|---|---|---|---|
| `frontend/src/pages/AboutPage.tsx:20-23` | «currently demonstrates temporal playback with numerically simulated data … validation of the five challenge targets are still being developed» | Falso hoy: hay cinco campos reales en `data/products`, mapa SPHEREx DR1, jobs por coordenadas (modo API) y cinco registros `success` (§0.0) | Reemplazar ese párrafo (líneas 19-24) por el bloque **A1** y agregar el bloque **A2** como sección nueva «Validation of the five challenge targets». El párrafo del 3D sigue en la fila siguiente | bloquea | WS6 (texto), WS5 (archivo) |
| `frontend/src/pages/AboutPage.tsx:26-27` | «illustrates the challenge targets with hand-entered, unverified parameters» | Contradice `catalog.py` (WS7-2: cada valor contrastado con su fuente el 14/11, marcado `unverified` si no). Lo que sí falta es que ningún valor sale de SPHEREx | "The optional 3D gallery draws the challenge targets from published catalog and literature values; every value shows its source and whether it was verified. These models are not SPHEREx images, and none of their values is measured by SPHEREx yet." | importante | WS6, WS5 |
| `frontend/src/pages/AboutPage.tsx:41` | «Real SPHEREx products from NASA/JPL-Caltech/IPAC have not yet been integrated into this demonstration.» | Falso hoy. Además faltan los créditos de lo que sí se usa (SPHEREx con el texto que pide IRSA, IRSA, Gaia/ESA, AllWISE, CfA, Aladin, AAVSO, NASA Exoplanet Archive) | Reemplazar el párrafo de «Sources and acknowledgments» por el bloque **A3** | bloquea | WS6, WS5 |
| `frontend/src/pages/AboutPage.tsx:45-48` | «OpenAI Codex assisted with … The imported 3D contribution declares Claude assistance» | Incompleto: Claude Code escribió código de WS1, midió los cinco registros de validación y redactó VISION.md ([`AI_USAGE.md`](../AI_USAGE.md) líneas 22-56). Regla 14 / S08 | "OpenAI Codex and Anthropic Claude Code assisted with source review, documentation, code, tests and the validation measurements of the five targets (each re-measured by an independent AI review). The team defined the product vision. Details and pending human review: AI_USAGE.md in the repository." | importante | WS6, WS5 |
| `frontend/src/pages/HomePage.tsx:56` | «{f.n_candidates} candidates» | En los cinco campos reales muestra «0 candidates», pero la detección no se corrió (lo dice la nota de procedencia). Una lista vacía sin análisis no es un resultado negativo (regla 12) | Si el campo es real y `n_candidates === 0`: "detection not run"; o quitar el contador de las tarjetas reales | importante | WS5 |
| `frontend/index.html:6` | «…with NASA SPHEREx data and find what moves.» | Sugiere detección automática, que es P2 y no se corrió en los campos reales | "Watch the infrared sky change over time with NASA SPHEREx data: motion and brightness changes, date by date." | menor | WS5 |
| `frontend/src/components/SkyExplorer.tsx:114` | «This preset is not a validated detection.» | Desactualizado: los cinco tienen registro `success` | `` `${target.name}: position propagated to MJD ${target.mjd} (Sesame/SIMBAD at CfA, checked 14 Nov 2026). Offline validation on the SPHEREx FITS files: docs/validation/ (human review pending). Bright targets saturate: image brightness is not a measurement.` `` | importante | WS5 |
| `frontend/src/api/showcase.ts:8` | RW Aurigae con `detector: 2` | En RW Aur ningún frame de D2-D6 está limpio (0 de 279); el cambio de ~1 mag solo se midió en D1 (0,74-0,88 µm) | `detector: 1`, y en el aviso del preset: "RW Aurigae: brightness change measured offline in D1 (about 1 mag brighter at 0.75–0.77 µm from Sep 2025 to Sep 2026). The star saturates D2–D6, and the images do not show the change." | importante | WS5 |
| `frontend/src/api/showcase.ts:9` | R Draconis con `detector: 2` | D2 es el detector con menos frames (89, sin deep) y con la variabilidad más débil (Δχ² 23 contra un máximo nulo de 19) | `detector: 1` (D1: 1,19 ± 0,04 mag pico a pico, retraso −1 d respecto de la V de AAVSO), con el aviso de saturación | menor | WS5 |
| `frontend/src/components/ExplorerMap.tsx:54` | `href="https://irsa.ipac.caltech.edu/data/SPHEREx/"` | **Enlace roto**: HTTP 404 (2026-11-15 03:30 UTC). La página de la misión responde 200 | `https://irsa.ipac.caltech.edu/Missions/spherex.html` | importante | WS5 |
| `frontend/src/components/ExplorerMap.tsx:53` | «This map is a static coadd, not a video.» | Correcto en esencia. El `properties` del HiPS lo describe como cubo DR1 «for visualization» con datos de MJD 60789,75-61174,49; conviene decir que no es una medida | "This map is the SPHEREx DR1 all-sky cube made for visualization (data from Apr 2025 to May 2026): not a video, and not a measurement." | menor | WS5 |
| `frontend/src/pages/FieldPage.tsx:104` | leyenda «catalog prediction» | `known.json` está vacío en los cinco campos reales: la leyenda anuncia un marcador que nunca aparece, y el objetivo no se puede ubicar (registros de Barnard, problema 1, y de ε Ind B, problema 4) | Ocultar la entrada si `known.length === 0`. Dibujar la retícula del objetivo (TODO de `BlinkViewer.tsx:237`) con la trayectoria que WS3 agregue a `known.json` | importante | WS5, WS3 |
| `frontend/src/pages/FieldPage.tsx:57` y `frontend/src/components/BlinkViewer.tsx:158-163` | sin aviso de saturación | Barnard (357/358), RW Aur (304/335) y R Dra (2488/2488) saturan; el PNG lleva el núcleo a 255 (§0.0) | Badge o nota por campo: "Saturated: image brightness is not a measurement." Puede venir de la descripción de `fields.toml` (filas de abajo) | importante | WS5, WS3 |
| `frontend/src/components/BlinkViewer.tsx:229` | `{(1000 / intervalMs).toFixed(1)}×` | Muestra cuadros por segundo con «×»: parece un multiplicador de velocidad | `{(1000 / intervalMs).toFixed(1)} fps` | menor | WS5 |
| `frontend/src/components/BlinkViewer.tsx:107` | ``alt={`SPHEREx frame ${f.id}`}`` | En los campos sintéticos llama «SPHEREx» a una simulación | `Synthetic frame …` si `field.provenance.synthetic`; si no, `SPHEREx frame …` | menor | WS5 |
| `frontend/src/components/SpectrumChart.tsx:93` y `:130` | «Observed measurement» / «Observed: …» | En el demo sintético los puntos son simulados | "Measurement" (o "Simulated measurement" si el campo es sintético) | menor | WS5 |
| `frontend/src/components/SpectrumChart.tsx:135` | «Measurements may come from separate exposures.» | Falta lo que importa para RW Aur y R Dra: las exposiciones son de fechas distintas y la variabilidad se mezcla con la forma del espectro (§3) | "Each point is a separate exposure taken on its own date; for variable stars, brightness changes between dates mix with the spectral shape." | menor | WS5 |
| `frontend/src/pages/SystemsPage.tsx:23-26` | «Their parameters were checked against the NASA Exoplanet Archive, SIMBAD, Gaia DR3 and the cited papers» | Correcto (WS7-2; en esta revisión Barnard b-e y ε Ind A b coinciden con el Exoplanet Archive en vivo). Pero la visión pide 3D desde mediciones y todavía no hay ningún valor SPHEREx | Agregar: "No value in these models is measured by SPHEREx yet." Cuando entren los facts del bloque **A5**: "What SPHEREx measured for each target is listed as \"Seen by SPHEREx\"." | menor | WS7 |
| `pipeline/errante/systems/catalog.py:219`, `:419`, `:489` | `field_id=None  # TODO(WS3/WS7): add an … field to config/fields.toml` | Los campos ya existen (`fields.toml:34`, `:80`, `:66`). Sin `field_id` la página 3D no enlaza a las imágenes SPHEREx. Además `data/products/manifest.json` no tiene `systems`, así que el dataset real no muestra el 3D | `field_id="eps-indi-b"`, `"r-draconis"` y `"rw-aurigae"`. Publicar los sistemas también en el dataset real | importante | WS7 (+ WS4) |
| `pipeline/errante/systems/catalog.py:208` | «a Sun-like star, a cold giant planet and a pair of brown dwarfs» | ε Ind A es K5V, 4700 K y 0,80 M☉; el propio cuerpo dice «a bit smaller and cooler than the Sun» | "Challenge test target: an orange dwarf star, a cold giant planet and a pair of brown dwarfs." | menor | WS7 |
| `pipeline/errante/systems/catalog.py:378` | `"Spectral type", "~Y4"` | SIMBAD da Y2 ([registro](validation/wise-0855.md); §0.1 y `fields.toml:53`). Las dos son de literatura: hay que decir de dónde sale cada una | "~Y4 (Kirkpatrick et al. 2021); SIMBAD lists Y2" | menor | WS7 (+ WS3) |
| `pipeline/errante/systems/catalog.py:459-461` | «much smaller in the infrared SPHEREx sees. It is not a measured or SPHEREx light curve.» | Correcto, pero ya hay medida: 0,5-1,3 mag y ~260 d. El período del modelo (245,6 d, GCVS) quedó ✅ verificado en esta revisión | "…much smaller in the infrared: offline measurements on the SPHEREx FITS files give 0.5–1.3 mag peak-to-peak at 0.74–5.0 µm and a ~260-day cycle in 2025–2026 (docs/validation/r-draconis.md). The animation is not that light curve, and the SPHEREx images in this app do not show it." | importante | WS7 |
| `pipeline/errante/systems/catalog.py:339` | «Gaia DR3 measures Ba+Bb as one unresolved source (RUWE 4.3)» | Correcto; falta lo mismo para SPHEREx. 🧮 Con a = 2,4058 UA, e = 0,5404 (Chen et al. 2022) y 3,64 pc: a = 0,66″ (semieje mayor), a(1 − e) = 0,30″ y a(1 + e) = 1,02″; la separación proyectada nunca supera la real | Agregar: "SPHEREx also sees Ba+Bb as one source: they are never more than about 1″ apart (orbit semi-major axis 2.4 AU, 0.66″ at 3.64 pc; eccentricity 0.54), and a SPHEREx pixel is 6.15″." | menor | WS7 |
| `pipeline/errante/systems/catalog.py` (los cinco sistemas) | ningún fact con valores SPHEREx | La visión («El 3D: realista y sin inventar nada») pide valores medidos; ya hay medidas SPHEREx validadas de los cinco | Agregar los facts del bloque **A5** | importante | WS7 |
| `pipeline/errante/config/fields.toml:68` | «Compare season coadds or per-season spectra, not single exposures.» | Contradicho por el registro: satura en D2-D6 y el cambio se midió con **exposiciones individuales** de D1 emparejadas en λ; los coadds tienen el núcleo saturado | "Official test target. Young T Tauri star (A+B unresolved): it does not move, it changes brightness. Saturated in D2–D6; measured offline on unsaturated D1 exposures at matched wavelength, it brightened by about 1 mag (0.75–0.77 µm) from Sep 2025 to Sep 2026. The images here do not show that change." | importante | WS3 |
| `pipeline/errante/config/fields.toml:82` | «Mira variable (period ~247 d) … the best light-curve case.» | No dice que satura en todos los frames ni que el campo publicado no tiene frames deep; SPHEREx midió ~260 d | "Official test target. Mira variable (catalog period 245.6–247.2 d), 8.6° from the north ecliptic pole. Saturated in every exposure: measured offline in the PSF wings on the SPHEREx FITS files, it shows a 0.5–1.3 mag cycle of ~260 d in 2025–2026, in phase with AAVSO. Image brightness here is not a measurement." | importante | WS3 |
| `pipeline/errante/config/fields.toml:52` | «Extremely red (J=25, W2=13.7): look at the longest wavelengths.» | Ya está medido: solo D5/D6 | "…Extremely red (J=25, W2=13.7): SPHEREx sees it only at 3.8–5.0 µm (D5–D6), faint in single exposures. Only DR1 data so far: ~1.4 SPHEREx pixels of motion." | menor | WS3 |
| `pipeline/errante/config/fields.toml:23` | «~1.9 SPHEREx pixels over the DR1+QR3 baseline.» | Correcto (1,86 px solo con movimiento propio), pero falta la saturación y el valor medido | "…~1.9 SPHEREx pixels over the DR1+QR3 baseline (1.66 px measured offline on the FITS files between the Aug 2025 and Aug 2026 seasons). Saturated core: image brightness is not a measurement." | menor | WS3 |
| `pipeline/errante/config/fields.toml:70`, `:59` y `:13` (comentarios) | «RW Aur A plx 6.406 …; RW Aur B plx 5.454»; «Probably only visible in D5/D6 coadds (INFERRED…)»; «NOT completed validation runs» | A y B invertidos (§0.3); la visibilidad ya está medida; los registros existen. No se ven en la UI, pero son la fuente de §0 | "Gaia DR3: RW Aur A = 156430817820015232 (plx 5.454, RUWE 16.4, unreliable); B = 156430822114424576 (plx 6.406)"; "Visible only in D5/D6, also in single exposures (docs/validation/wise-0855.md)"; "Validation records: docs/validation/" | menor | WS3 |
| `data/products/fields/rw-aurigae/field.json:809` (la misma nota en los cinco campos) | «Saturated star cores and detector-defect pixels are filled from their neighbours for display only» | Es la nota de la build del 14/11. El registro de RW Aur (problemas 4 y 7) mostró que los `OVERFLOW` finitos se ven tal cual y que se reemplazaban píxeles `SUR_ERROR` del núcleo. #48 corrigió el código y la nota (`pipeline/errante/build.py:501-511`), pero los productos no se reconstruyeron; además declaran `schema_version` 0.2.1 contra 0.3.0 del código | Reconstruir los cinco campos con `errante build <id>` para publicar la nota nueva | importante | WS2 (+ WS4) |
| `README.md:20-21` | «Scientific validation of all five targets (R05) and a verified public deployment are still pending.» | Desactualizado: hay cinco registros `success` | "All five targets (R05) have validation records with offline measurements on the SPHEREx FITS files (docs/validation/); human review of those records and a verified public deployment are still pending." | importante | coordinación, WS6 |
| `README.md:23-24` y `:55` | «illustrative, unverified models»; «currently unverified parameters» | Igual que la fila de `AboutPage.tsx:26-27` | "The 3D gallery draws the challenge targets from published catalog values (each with its source and verification flag), plus one synthetic system; none of its values is measured by SPHEREx yet." y `# write 3D models from catalog values (source per fact)` | menor | coordinación, WS7 |
| `README.md:116-119` | «Real SPHEREx observations have not yet been integrated into the committed demonstration. Catalog services, WISE/Gaia context … are planned» | Contradice `README.md:11` y `:73` (cinco campos reales). Gaia DR3, AllWISE, Sesame/VizieR en CfA y AAVSO ya se usaron | Reemplazar el párrafo por el bloque **A3** | bloquea | coordinación, WS6 |
| `README.md:121-124` | «OpenAI Codex assisted … The imported 3D contribution declares Claude assistance» | Omite el uso de Claude Code (WS1, validaciones, VISION) | El mismo texto que la fila de `AboutPage.tsx:45-48`, con enlace a AI_USAGE.md | importante | coordinación, WS6 |
| `AI_USAGE.md:66-67` | «The 3D presets remain hand-entered and unverified.» | Contradice el `VERIFIED_NOTE` de `catalog.py` (WS7-2) | "The 3D presets were cross-checked on 2026-11-14 against the cited catalogs and papers (WS7-2, AI-assisted; each fact carries a verified flag). They are not SPHEREx observations or measured orbits, and human review is pending." | importante | coordinación, WS6 |
| `AI_USAGE.md:71-74` | «The committed demonstration fields are numerical simulations…» | Desactualizado: `data/demo` es sintético y `data/products` tiene cinco campos SPHEREx reales | "data/demo holds labelled numerical simulations generated by errante.synthetic. data/products holds five real SPHEREx fields built from IRSA DR1/QR3 Level 2 images." | importante | coordinación, WS6 |
| `docs/submission/PROJECT.md:19-26` | «Users will enter … The current application is a labelled synthetic demonstration; real-data access, public coordinate requests and the five validation runs are still pending.» | Falso hoy, y es el texto que leen los jueces | Bloque **A4** | bloquea | WS6 |
| `docs/submission/PROJECT.md:54-58` | «hand-entered, unverified parameters»; «Pending: archive search/cutouts/reprojection, coordinate-build jobs, public deployment and five real tests.» | La búsqueda en IRSA, los recortes, la reproyección, los jobs (modo API local) y los cinco ensayos están hechos; falta el deploy público | "- Available: SPHEREx DR1 sky map (Aladin Lite + IRSA HiPS) with name and coordinate search; real SPHEREx sequences built from IRSA Level 2 images (live API mode); five prebuilt real challenge fields; synthetic examples labelled as such. - Available extension: a 3D gallery of the five targets from published catalog values (source per value), not yet built from SPHEREx measurements. - Pending: public deployment and human review of the validation records." | bloquea | WS6 |
| `docs/submission/PROJECT.md:67` | «The public service for arbitrary coordinates is not implemented yet.» | Implementado (jobs con `ERRANTE_ENABLE_JOBS`); falta alojarlo | "Arbitrary coordinates are built by background jobs on the API; public hosting is pending." | importante | WS6 |
| `docs/submission/PROJECT.md:71-77` | tabla con «Pending real-data test» en los cinco | Los cinco tienen resultado | Tabla del bloque **A2b** | bloquea | WS6 |
| `docs/submission/PROJECT.md:99-100` | «Real archive/image processing and validation are pending»; «NASA observations are not yet integrated into the committed demo» | Desactualizado | Validity: "Five validation records (offline FITS measurements, independently re-measured); human review and user tests pending." Relevance: "Five real SPHEREx fields (DR1/QR3) and live builds from IRSA; public URL pending." | importante | WS6 |
| `docs/submission/PROJECT.md:117-122` | «Yes. OpenAI Codex assisted … The imported 3D contribution declares Claude assistance…» | La declaración SI del formulario omite Claude Code | Agregar: "Anthropic Claude Code assisted team member faricool54 with data-access code (WS1), the validation measurements and records of the five targets (each re-measured by an independent AI review; human review pending), documentation and the scientific review of this text. The team defined the product vision; Claude checked its feasibility and wrote it down (AI_USAGE.md)." | bloquea | WS6 |
| `docs/submission/PROJECT.md:139-141` | «**No real SPHEREx observations have yet been integrated into the committed demonstration.**» | Falso hoy | Bloque **A6** | bloquea | WS6 |
| `docs/submission/PROJECT.md:153-156` | «no processing of those datasets is claimed»; «Aladin integration and JPL/SkyBoT analysis remain planned» | Gaia DR3 (archivo de ESA) se procesó como referencia astrométrica en los cinco registros; Aladin Lite 3.8.2 está integrado; AllWISE es capa de contexto; AAVSO se usó para la fase de R Dra; 2MASS y CatWISE2020 para identidad | Bloque **A3**, más: "Gaia DR3 (ESA) positions were the astrometric reference in the five validation records. Aladin Lite 3.8.2 displays the IRSA SPHEREx HiPS. JPL/SkyBoT analysis remains planned." | importante | WS6 |
| `docs/submission/PITCH.md:21-22` | «[Describe the implemented workflow…]»; «[State one verified result…]» | Faltan las frases; tienen que ser reales y entrar en ~10 s y ~8 s | 00:10-00:20: "Type a name or click the map, and Errante plays the SPHEREx images of that spot, date by date." 00:20-00:28: "Measured offline in the SPHEREx files, Barnard's Star moves ten arcseconds a year, as Gaia predicts. Known motion, not a discovery." Imagen de ese tramo: una figura del registro (p. ej. `docs/validation/figures/barnards-star/fig2_track.png`), no el blink, donde la estrella saturada es un disco blanco sin marcador. Cronometrar: ~20 palabras | importante | WS6 |
| `docs/submission/JUDGING_REVIEW.md:14-15` y `:21-22` | «acceso/procesamiento real y cinco ensayos pendientes»; «imágenes SPHEREx reales pendientes»; «La galería de seis modelos 3D tiene parámetros sin verificar» | Desactualizado (registros, campos reales, WS7-2) | Validity: «Cinco registros `success` (análisis offline y revisión IA independiente) en docs/validation/; faltan la revisión humana y el paso 6.» Relevance: «Mapa SPHEREx DR1, cinco campos reales y builds en vivo (modo API); falta la URL pública.» 3D: «Los modelos usan valores de catálogo verificados (WS7-2), no mediciones SPHEREx; no cuentan para R05.» | importante | WS6 |
| `docs/submission/CHECKLIST.md:79-83` y `:85` | casillas de R05 sin marcar; «parámetros no verificados» | Los cinco registros existen; faltan la revisión humana y el paso 6 | Marcar cada R05 con la nota «registro hecho (IA, con revisión independiente); revisión humana y paso 6 pendientes». En `:85`: «Modelos 3D identificados como modelos de catálogo (no mediciones SPHEREx); no cuentan como ensayos.» | importante | WS6 |

**Revisado sin cambios** (correcto contra las fuentes): «102 infrared colors» y la descripción de SPHEREx en
`AboutPage.tsx:6-11`; el crédito de la capa AllWISE en `ExplorerMap.tsx:56` (el `properties` del HiPS de ESA dice R =
W4, G = W2, B = W1, creado por CDS, © IPAC/NASA); `sky-map.html` (centro en Barnard a la época media, enlace de Aladin
con 200); «the fastest-moving star in our sky» (Barnard), «the coldest known brown dwarf» (WISE 0855), «every ~8
months» (R Dra); los planetas de Barnard y ε Ind A b contra el NASA Exoplanet Archive; la identidad A/B de RW Aur en
`catalog.py`; los avisos de candidatos `unconfirmed` y la nota de `FieldPage.tsx:98-100`; el placeholder sexagesimal de
`SkyExplorer.tsx:129-131` (269,44623° = 17h57m47,1s; +4,76870° = +04°46′07,3″).

### Textos listos para pegar

**A1. About, «Current project status»** (reemplaza el primer párrafo, `AboutPage.tsx:19-24`):

```text
Errante shows real NASA SPHEREx observations. The sky map is the SPHEREx DR1 all-sky cube served by
NASA/IPAC IRSA. In live mode, clicking a position or searching a name builds a sequence from the SPHEREx
Level 2 images that cover it; five prebuilt fields cover the challenge targets. Each frame shows its date,
detector, wavelength and data release. Separate example fields are numerical simulations, labelled
SYNTHETIC DATA · NOT SPHEREx. Automatic detection and catalog matching are optional and were not run on the
five real fields: an empty candidate list there is not a negative result.
```

**A2. About, sección nueva «Validation of the five challenge targets»** (fuente: §0.0):

```text
We validated the five challenge targets with offline measurements on the SPHEREx FITS files, each
repeated by an independent second analysis (human review pending). All five are known objects, so these
are recoveries of known behaviour, not discoveries.

- Barnard's Star moves 10.2″ (1.66 SPHEREx pixels) between the August 2025 and August 2026 seasons, in the
  direction Gaia DR3 predicts (10.24″). The star saturates the detector, so positions come from the wings
  of its image; its parallax cannot be measured with these data.
- Epsilon Indi B: the brown-dwarf pair Ba+Bb appears as one source and moves 1.03 pixels (6.3″) between May
  2025 and September 2026, as the catalog predicts.
- WISE 0855−0714 is visible only at 3.8–5.0 µm. It is faint in single exposures and clear when they are
  combined, and it moves 8.4–8.5″ in a year (8.0″ expected).
- RW Aurigae brightened by about 1 magnitude at 0.75–0.77 µm between September 2025 and September 2026,
  measured on unsaturated exposures at matched wavelengths. Comparison stars scatter by 0.05 mag.
- R Draconis saturates every exposure. Measured in the wings of its image, it varies by 0.5–1.3 magnitudes
  with a cycle of about 260 days that follows contemporaneous AAVSO observations (catalog: 245.6–247.2 d).

The motions are 1–2 pixels, and saturated stars look white in the viewer, where image brightness is not a
measurement. The viewer does not yet mark the targets or show these measurements. Full records:
docs/validation/ in the project repository.
```

**A2b. Tabla de `PROJECT.md` «Validation and limitations»** (reemplaza `PROJECT.md:71-77`):

```markdown
| Target | Observed result (SPHEREx DR1/QR3, offline FITS analysis; human review pending) |
|---|---|
| Barnard's Star | Proper motion recovered: 10.2″ (1.66 SPHEREx pixels) between the Aug 2025 and Aug 2026 seasons at PA 354–355°, vs 10.24″ at PA 355.7° from Gaia DR3; 358 exposures. Saturated in 357/358: positions from the PSF wings. Parallax not measurable with these data. |
| Epsilon Indi B | Ba+Bb seen as one source in ~440 of 458 frames (not below ~0.83 µm); moved 1.03 pixels between May 2025 and Sep 2026, matching the catalog prediction within its uncertainty. |
| WISE 0855−0714 | Detected only at 3.8–5.0 µm (detectors D5–D6): signal-to-noise ~3–4 per exposure, 21–25 combined; moved 8.4–8.5″ in 360 days vs 8.0″ expected; blended with a G = 16.3 background star. DR1 data only. |
| RW Aurigae | Brightened ~1.0 mag at 0.75–0.77 µm between 2 Sep 2025 and 8 Sep 2026, from unsaturated D1 exposures at matched wavelength (comparison stars: 0.05 mag robust scatter). Saturated in D2–D6. |
| R Draconis | Saturated in all 2,488 exposures. PSF-wing photometry shows a 0.5–1.3 mag cycle of ~260 d (95%: 255–265 d), in phase with contemporaneous AAVSO V data; catalog periods 245.6–247.2 d. |
```

**A3. Créditos** (About «Sources and acknowledgments», `README.md` y `PROJECT.md`). Las frases entre comillas son
literales de la fuente indicada, consultada el 2026-11-15; las demás hay que copiarlas de su fuente antes de enviar.

```text
Sources and acknowledgments
- "This publication makes use of data products from the Spectro-Photometer for the History of the Universe,
  Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion
  Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space
  Administration."
- SPHEREx images, search and the DR1 sky cube: NASA/IPAC Infrared Science Archive (IRSA),
  https://irsa.ipac.caltech.edu/Missions/spherex.html
- "This work has made use of data from the European Space Agency (ESA) mission Gaia
  (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC,
  https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national
  institutions, in particular the institutions participating in the Gaia Multilateral Agreement."
- Map context layer: AllWISE color (W4/W2/W1) from NASA's WISE and NEOWISE (IPAC/NASA), HiPS by CDS, served by
  ESA ESASky. Not SPHEREx data.
- Name resolution and catalogs: Sesame, SIMBAD and VizieR (CDS, Strasbourg), through the CfA mirror. 2MASS
  and CatWISE2020 were used for identity checks.
- Variable-star observations from the AAVSO International Database (R Draconis phase check).
- "This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute of
  Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet
  Exploration Program." (3D gallery)
- Sky viewer: Aladin Lite 3.8.2 (CDS), GPL-3.
```

Pendientes de A3: la frase de reconocimiento de IRSA (las URLs probadas dieron 404), la de AAVSO (el PDF de
https://www.aavso.org/data-usage-guidelines dio 404), y el `obs_ack` completo de WISE/NEOWISE, que está en
https://skies.esac.esa.int/AllWISEColor/properties.

**A4. `PROJECT.md`, «High-Level Project Summary»** (reemplaza `PROJECT.md:19-26`):

```text
Errante is a web explorer for NASA SPHEREx images over time. On a map of the real SPHEREx sky, a user
searches a name or coordinates, or clicks a point, and Errante builds and plays the SPHEREx Level 2 images
of that spot date by date, showing each frame's date, detector, wavelength and data release. We validated
the five challenge targets with offline measurements on the SPHEREx FITS files, each repeated by an
independent second analysis (human review pending): the SPHEREx data recover the known proper motions of
Barnard's Star (1.66 pixels in a year), Epsilon Indi B and WISE 0855−0714, and the brightness changes of
RW Aurigae (about 1 magnitude) and R Draconis (a cycle of about 260 days). These are recoveries of known
behaviour, not discoveries. The viewer does not yet mark the targets, and saturated stars appear white, so
these measurements are not yet visible in the app. Remaining work: showing them in the viewer, public
deployment and human review of the validation records.
```

**A5. Facts SPHEREx para el 3D** (`catalog.py`, con su helper `_vfact`; la fuente es el registro, cuyos valores se
copian tal cual). `BodyPanel.tsx` muestra cada fact como «valor unidad»: si hay unidad, el valor es solo el número.
La fuente dice «offline» porque el producto publicado no muestra estas medidas. Al agregarlos, `VERIFIED_NOTE`
tiene que decir que los facts «seen by SPHEREx» se copiaron de los registros de validación (análisis de IA con
revisión independiente; revisión humana pendiente), no del cruce con catálogos del 14/11.

```python
# barnards_star(), cuerpo "barnards-star"
_vfact("Motion seen by SPHEREx", "10.2″ (1.66 px) between the Aug 2025 and Aug 2026 seasons, PA 354–355°", None,
       "SPHEREx DR1+QR3, 358 exposures, offline FITS analysis; docs/validation/barnards-star.md "
       "(saturated core: wing astrometry)"),
# epsilon_indi(), cuerpo "eps-indi-ba" (o una nota del sistema)
_vfact("Motion seen by SPHEREx (Ba+Bb as one source)", "1.03 px (6.3″) between May 2025 and Sep 2026", None,
       "SPHEREx DR1+QR3, offline FITS analysis; docs/validation/eps-indi-b.md"),
# wise_0855()
_vfact("Seen by SPHEREx", "only at 3.8–5.0 µm: ~0.3 mJy at 3.8–4.4 µm, ~0.5 mJy at 4.4–5.0 µm", None,
       "SPHEREx DR1, 258 frames, offline FITS analysis; docs/validation/wise-0855.md "
       "(fluxes depend on the PSF model, ~11 %)"),
# rw_aurigae(), cuerpo "rw-aur-a" (A+B sin resolver: decirlo en el label)
_vfact("Brightness change seen by SPHEREx (A+B)", "about 1.0 mag brighter at 0.75–0.77 µm, Sep 2025 → Sep 2026",
       None, "SPHEREx DR1+QR3, unsaturated D1 exposures, offline FITS analysis; docs/validation/rw-aurigae.md"),
# r_draconis(): dos facts, para que cada unidad quede junto a su número
_vfact("Cycle seen by SPHEREx", "~260 (95 %: 255–265)", "days",
       "SPHEREx DR1+QR3+deep, offline PSF-wing photometry; docs/validation/r-draconis.md"),
_vfact("Brightness range seen by SPHEREx (0.74–5.0 µm, by detector)", "0.5–1.3", "mag peak-to-peak",
       "SPHEREx DR1+QR3+deep, offline PSF-wing photometry; docs/validation/r-draconis.md"),
```

**A6. `PROJECT.md`, «NASA Data»** (reemplaza `PROJECT.md:139-141`):

```text
Errante's images are NASA SPHEREx data: Level 2 spectral images from the DR1 and QR3 releases (archive:
NASA/IPAC IRSA), found with IRSA's SIA2 search and read from the public nasa-irsa-spherex AWS S3 bucket,
plus the SPHEREx DR1 all-sky cube (HiPS) for the map. The five prebuilt challenge fields use 40 frames each
from 2025–2026. The offline validation analyses used every exposure covering each target (258 to 2,493 per
target). For each target, docs/validation/ gives the exposure counts by release and detector, the date
ranges, the wavelengths, and the observation IDs of the 40 published frames. Gaia DR3 (ESA) positions were
the astrometric reference.
```

### Comprobaciones en vivo de esta revisión (2026-11-15, UTC)

- **03:29, Gaia DR3** (TAP del archivo de ESA, `gaiadr3.gaia_source`): 156430822114424576 → RA 76.95608120, Dec
  +30.40120459, G 12,184, plx 6,406 ± 0,044 mas, µ (+2,641, −27,398) mas/año, RUWE 1,50, RV −20,9 km/s.
  156430817820015232 → RA 76.95654431, Dec +30.40131615, G 13,035, plx 5,454 ± 0,332 mas, µ (+4,906, −24,578) mas/año,
  RUWE 16,42. 🧮 La primera está a 1,493″ y PA 254,4° de la segunda.
- **03:29, WDS** (VizieR CfA `B/wds/wds`, cono de 30″): 05078+3024, JOY 5, componentes A,BC, 1944-2022, 24
  observaciones, PA 254°, separación 1,50″, magnitudes 13,0 y 12,2. Hay además un par GHE 16 BC a 0,1″ (1990). →
  RW Aur **A = 156430817820015232**, **B = 156430822114424576**.
- **03:29 y 03:33, GCVS y VSX** (VizieR CfA `B/gcvs/gcvs_cat` y `B/vsx/vsx`): a las 03:29 VizieR CfA respondió «The
  database is not currently reachable»; a las 03:33 respondió. GCVS: R Dra, tipo M, máx. 6,7, P = 245,6 d,
  M5e-M9eIII. VSX: OID 13673, V 6,7-13,2, P = 246,12 d, M5e-M9eIII.
- **03:31, NASA Exoplanet Archive** (TAP, `pscomppars` con caja `ra/dec BETWEEN`): Barnard b, c, d, e con P = 3,1542 /
  4,1244 / 2,3402 / 6,7392 d, masa mínima 0,299 / 0,335 / 0,263 / 0,193 M⊕ y a = 0,0229 / 0,0274 / 0,0188 / 0,0381 UA;
  Teff 3195 K, 1,827 pc. ε Ind A b: P = 25 450 d, 6,5 MJ, a = 15,76 UA, e = 0,25; estrella de 4700 K a 3,639 pc.
  Coinciden con `catalog.py`.
- **03:29-03:30, páginas de créditos:** la página SPHEREx de IRSA (200) trae el texto de reconocimiento citado en A3;
  `https://irsa.ipac.caltech.edu/data/SPHEREx/` da **404**. La documentación de Gaia DR3 en ESA da el texto citado en
  A3, y la página de reconocimiento del NASA Exoplanet Archive, el suyo.
- **03:30, `properties` de los HiPS:** SPHEREx DR1 en IRSA: «SPHEREx DR1 all-sky data cube», «for visualization», ©
  NASA/SPHEREx, creador SPHEREx Science Data Center, `t_min` 60789,75 y `t_max` 61174,49 (2025-04-24 → 2026-05-14).
  AllWISEColor en ESA: rojo W4, verde W2, azul W1, creador CDS, © IPAC/NASA.

**Sin verificar en esta revisión** (no inventar): la frase de reconocimiento genérica de IRSA y la de AAVSO (URLs
con 404); el tipo espectral ~Y4 de WISE 0855 en Kirkpatrick+2021 y Luhman+2024; los números del Planeta Nueve del §2;
la VR de RW Aur (Gaia DR3 da −20,9 km/s para B y `catalog.py` usa +15 km/s de SIMBAD, Nguyen et al. 2012: no se ve en
la UI). Los registros de validación son análisis de IA con revisión independiente; la revisión humana sigue pendiente.

## Revisión científica del 3D (WS7, #47) - 2026-11-15

Revisión de WS3 del 3D procedural que entró con #47 (`main` `8a3f82f`): `pipeline/errante/systems/catalog.py`,
`frontend/src/three/` (`appearance`, `starMaterial`, `astro`, `colorModes`, `ephemerides`, `skyTrack`, `spherexBands`,
`spherexCoverage`, `datasetGate`, `appearanceNotes`, `sceneLayout`, `SystemScene`), [`VISION_3D.md`](VISION_3D.md),
[`tasks/WS7-3d-systems.md`](../tasks/WS7-3d-systems.md) y las «Notas de otros WS» de [`DATA.md`](DATA.md). Cada valor y
cada afirmación se contrastó con los cinco registros de [`validation/`](validation/), con §0 y §3.1 de este documento,
con [`DATA.md`](DATA.md) §3.0 y §3.2, con el contexto de catálogo de WS3 (`errante.science.context.object_context` y
`physical_parameters`, reproducidos offline desde `pipeline/tests/fixtures/ws3/context/`, grabados el 2026-11-15) y, cuando
hizo falta, con consultas en vivo (lista al final). La regla es la de [`VISION.md`](VISION.md) («El 3D: realista y sin
inventar nada»). WS3 no edita archivos de WS7: cada dueño aplica su fila. El texto sugerido está en inglés para la UI y el
código, y en español para los documentos internos; si cita un número de validación, dice «offline» (§4).

**Resumen.** El 3D cumple lo esencial: nada se presenta como imagen, las superficies son lisas por defecto, los colores
están rotulados y los valores de catálogo que WS3 pudo comprobar coinciden con Gaia DR3, SIMBAD, VSX y el NASA Exoplanet
Archive. Los problemas son de otro tipo:

- una cita de la ficha de RW Aur presenta como **medición SPHEREx** magnitudes D5/D6 de núcleos saturados, que el registro
  de RW Aur invalidó;
- varias notas del panel del cielo repiten afirmaciones de `RECON_SPHEREX.md` que los registros corrigieron (saturación de
  Barnard por detector, S/N de WISE 0855, NaN en R Dra);
- en *Dataset time*, la banda de ±6,6 d de R Dra no cubre el máximo de enero de 2026 que midió el registro (−14,8 d), y el
  radio de R Dra pulsa por defecto aunque ese cambio no está medido en esta estrella;
- para RW Aur el visor manda a «mirar los frames», donde el cambio no se puede ver (la estrella satura en D2–D6).

Severidad, como en la revisión de textos: **bloquea** = corregir antes de enviar; **importante** = antes del freeze si se
puede; **menor** = mejora. La tabla tiene 17 filas: 1 bloquea, 5 importantes y 11 menores.

| archivo:línea | valor o texto | problema | corrección sugerida (lista para pegar) | severidad | dueño |
|---|---|---|---|---|---|
| `frontend/src/three/astro.ts:1150-1151` (`IR_EXCESS_CITE`, en la ficha de RW Aur A, «At SPHEREx scale») | «SPHEREx measured D5 7.92–8.65 and D6 7.63–8.38 AB in 2025-09 to 2026-09 (docs/RECON_SPHEREX.md §4.4) … i.e. 1.3–3.8 mag brighter than the A+B photosphere blackbody» | En RW Aur ningún frame D2–D6 está limpio (0 de 279; 0 de 56 en D5 y en D6) y 304 de 335 tienen `OVERFLOW`. El [registro](validation/rw-aurigae.md) llama a esas magnitudes «indicio no válido»: con saturación el recorte crece con el brillo. Además RECON §4.4 concluía que la estrella se apagó en D5/D6, mientras que lo medido sin saturar (D1) es que se abrillantó ~1 mag. La regla (una T Tauri tiene exceso IR) es correcta; la evidencia citada como «SPHEREx measured» no lo es. 🧮 Con la fotosfera A+B del propio catálogo (4900 K y 1,3 R☉ + 4150 K y 1,5 R☉, a 156,1 pc) y las magnitudes de 2MASS y AllWISE del contexto WS3, el exceso es 1,35 mag en Ks, 1,89 en W1 y 2,80 en W2 | `'evidence for the rule (RW Aur A+B, classical T Tauri stars with disks): 2MASS Ks = 7.020 Vega = 8.87 AB (Cutri et al. 2003, VizieR II/246; K_AB − K_Vega = 1.85, Blanton & Roweis 2007, AJ 133, 734) and AllWISE W1 = 6.246 and W2 = 5.228 Vega = 8.95 and 8.57 AB (Cutri et al. 2013, VizieR II/328; AB − Vega = 2.699 and 3.339, WISE Explanatory Supplement) are 1.4, 1.9 and 2.8 mag brighter than the A+B photosphere blackbody (catalog Teff and radii, 156.1 pc); the epochs differ and the star varies by magnitudes. No SPHEREx D2–D6 exposure of RW Aur is usable: 0 of 279 are clean (OVERFLOW in 304 of 335 exposures overall; offline FITS analysis, docs/validation/rw-aurigae.md), so no SPHEREx flux is quoted here'`. En el comentario de `astro.ts:1177`: «(RW Aur: 1.4–2.8 mag at 2.2–4.6 µm, 2MASS/AllWISE)» | bloquea | WS7 |
| `frontend/src/three/ephemerides.ts:263-280` (`MIRA_EPHEMERIDES`, R Dra), `docs/VISION_3D.md:257-263` y `tasks/WS7-3d-systems.md:105` | Banda de 1σ de ±6,6 d (RMS del O−C 2015–2024) alrededor de las fechas VSX: máximos predichos 2025-05-20, 2026-01-21 y 2026-09-24. VISION_3D: la estimación del máximo de 2026-01 «no publicada y no usada» | El [registro de R Dra](validation/r-draconis.md) (§3, 818 observaciones AAVSO) midió los máximos V de esos mismos ciclos: MJD 60811,4, 61046,5 y 61304,3 (2025-05-16, 2026-01-06 y 2026-09-21). 🧮 O−C respecto de VSX: −3,8, −14,8 y −3,1 d (RMS 9,0 d). El de enero de 2026 queda a 2,2σ de la banda, y la fase que el 3D dibuja ese mes está corrida ~0,06 ciclos. [`VISION.md`](VISION.md) pide la curva medida cuando existe, y esta ya está publicada en el registro (lo que VISION_3D llama «no publicada») | Dentro de la ventana SPHEREx, fechar la fase con los máximos medidos y dejar VSX solo fuera de ella. En la entrada de R Dra: `observedMaximaMjd: [60811.4, 61046.5, 61304.3]`, `observedMaximaSource: 'AAVSO International Database, 818 visual and V observations, JD 2460700–2461360; maxima from ±40 d parabolas (offline WS3 analysis, docs/validation/r-draconis.md)'`; fase lineal entre máximos consecutivos y banda de ±3 d (error formal 0,5–0,8 d; el real, «unos pocos días», es INFERIDO en el registro). Si no da el tiempo: `timingSigmaDays: 9.0` con `timingSource: 'RMS of the O−C of the 2025–2026 AAVSO maxima about VSX: −3.8, −14.8 and −3.1 d (offline WS3 analysis, docs/validation/r-draconis.md)'`. En `tasks/WS7-3d-systems.md:105`, el contraste con los máximos AAVSO ya está hecho (en el registro); queda el término de Eddington–Plakidis | importante | WS7 |
| `frontend/src/three/sceneLayout.ts:25`, `SystemScene.ts:973-975` y `:1000-1008`; leyenda en `colorModes.ts:613-617` | R Dra: radio ±10 % (`PULSATION_RADIUS_AMPLITUDE`), dibujado **por defecto** en los dos relojes y en todos los modos de color, «in phase with the light for display only» | El cambio de tamaño no está medido en R Dra: es `class-typical`, de otras Miras, y su relación de fase con la luz no se conoce. En *Dataset time* se dibuja en una fecha real, así que parece una predicción. [`VISION.md`](VISION.md) dice «lo que no se midió no se dibuja» (pulsación: «si falta, modelo estático»), y es el mismo criterio que WS7 ya aplicó a las celdas de convección. Además, en el modo IR por defecto el radio sigue la fase V, y los máximos SPHEREx llegan entre 1 d antes y 47 d después (registro) | Radio constante salvo con el toggle class-typical: pasar `classTypical` a `pulsationAt` y devolver `radiusScale: 1` cuando está apagado. Leyenda: "R Draconis: radius drawn constant, because its size change is not measured. With class-typical features on: ±10 % (CLASS-TYPICAL Mira diameter change), drawn in phase with the light for display only." | importante | WS7 |
| `frontend/src/three/ephemerides.ts:423` (`IRREGULAR_TEXT`: línea de tiempo y «On this date») | «irregular: cannot be predicted - look at the frames» | En RW Aur los frames no sirven para ver el cambio: ningún frame D2–D6 está limpio (0 de 279; `OVERFLOW` en 304 de 335) y la estrella valía 255 en los 40 PNG del build que revisó el registro (#48 cambió después el render de núcleos brillantes, sin re-medir). El registro solo pudo medir la variación en exposiciones D1 sin saturar, emparejadas en λ. Mandar a «mirar los frames» sugiere que ahí se ve | Genérico: "irregular: cannot be predicted". Para RW Aur, agregar: "Measured offline on unsaturated SPHEREx D1 exposures at matched wavelength, RW Aur (A+B) was about 1 mag brighter at 0.75–0.77 µm in Sep 2026 than in Sep 2025 (docs/validation/rw-aurigae.md). In the same offline analysis no D2–D6 exposure is clean (0 of 279; OVERFLOW in 304 of 335 overall): image brightness here is not a measurement." | importante | WS7 |
| `frontend/src/three/skyTrack.ts:270` (panel «Where SPHEREx should see it», Barnard) | «Saturated in D1–D4 (NaN core of 1–5 px), rarely in D5, never in D6 (RECON 4.3).» | Contradicho por el [registro de Barnard](validation/barnards-star.md) y por DATA.md §3.2: `OVERFLOW` en 357 de 358 exposiciones, en los seis detectores (D5 61 de 61, D6 57 de 58). Lo raro en D5/D6 es el NaN (4 de 119), no la saturación: RECON confundió NaN con saturación | "Saturated (OVERFLOW) in 357 of 358 exposures, in all six detectors; the core is NaN in 240 of them, almost all in D1–D4 (offline FITS analysis, docs/validation/barnards-star.md)." | importante | WS7 |
| `frontend/src/three/skyTrack.ts:300` (WISE 0855) | «Visible only at local wavelengths ≥ 3.9 µm (D5/D6), S/N ≈ 5 per image (RECON 4.3).» | El [registro](validation/wise-0855.md) midió los 258 frames: S/N mediana por exposición 3,4–3,8 (≥ 5 en 22 de 93 frames D5/D6) y 21–25 sumando por detector; se ve en todo D5/D6 (3,8–5,0 µm), con el máximo en 4,25–4,70 µm. «≈ 5» sobreestima lo que se ve en un frame; en los 12 frames D5/D6 del build que revisó el registro la S/N mediana era 2,1 | "Seen only in D5/D6 (3.8–5.0 µm), brightest at 4.25–4.70 µm: median S/N 3.4–3.8 per exposure (5 or more in 22 of 93) and 21–25 per detector with all exposures combined (offline FITS analysis, docs/validation/wise-0855.md)." | importante | WS7 |
| `frontend/src/three/skyTrack.ts:315` (R Dra) | «Saturated core (NaN) in every image (RECON 4.3).» | Satura en todas (2488 de 2488), pero los píxeles `OVERFLOW` son finitos, no NaN ([registro](validation/r-draconis.md); DATA.md §3.2; NaN ≤ 0,28 % por patch) | "Saturated (OVERFLOW) in all 2,488 exposures with the star on the detector; the flagged core pixels are finite, not NaN (offline FITS analysis, docs/validation/r-draconis.md)." | menor | WS7 |
| `frontend/src/three/skyTrack.ts:307` (estrella de campo junto a WISE 0855) | «in D1–D3 the blob at the target position is this star» | El registro no detecta a WISE 0855 en D1–D4 (flujo compatible con 0) y mide la estrella en los cuatro | "in D1–D4 the blob at the target position is this star (docs/validation/wise-0855.md)" | menor | WS7 |
| `frontend/src/three/astro.ts:1216`, `:1226` y `appearanceNotes.ts:156-157` | «check the OVERFLOW/NONLINEAR pixel flags» | Para los cinco blancos ya están revisados en los registros: Barnard 357 de 358, RW Aur 304 de 335 (ningún frame D2–D6 limpio) y R Dra 2488 de 2488 con `OVERFLOW`; `NONLINEAR` nunca; ε Ind B y WISE 0855 no saturan | Para los cinco blancos, el resultado en lugar de «check»: R Dra "saturated (OVERFLOW) in all 2,488 SPHEREx exposures, NONLINEAR never (offline FITS analysis, docs/validation/r-draconis.md)"; RW Aur "OVERFLOW in 304 of 335 SPHEREx exposures, and no clean D2–D6 exposure (0 of 279; offline FITS analysis, docs/validation/rw-aurigae.md)"; Barnard "saturated (OVERFLOW) in 357 of 358 exposures (offline FITS analysis, docs/validation/barnards-star.md)". Para cualquier otro objeto, dejar «check» | menor | WS7 |
| `pipeline/errante/systems/catalog.py:188-190` (nota de órbita de Barnard b–e) | «Drawn circular: the fitted eccentricities are consistent with zero (Basant et al. 2025 favour e < 0.02).» | El NASA Exoplanet Archive (`ps`, `default_flag = 1`, Basant et al. 2025; en vivo, 2026-11-15) da e = 0,04 (+0,05/−0,03) para d, 0,03 (+0,03/−0,02) para b, 0,08 (+0,06/−0,05) para c y 0,04 (+0,03/−0,04) para e. «e < 0.02» no se pudo verificar. 🧮 Dibujar la órbita circular corre la posición hasta 2e rad (3,4° en b, 9,2° en c), un término que el arco de ±2σ no incluye; en c es del orden de su 1σ (11–16°) | "Drawn circular: the fitted eccentricities (d 0.04, b 0.03, c 0.08, e 0.04; Basant et al. 2025 via the NASA Exoplanet Archive) are consistent with zero within 2σ. A circular drawing can misplace the planet along its orbit by up to 2e rad (3–9°); the phase arc does not include that." | menor | WS7 |
| `frontend/src/three/spherexCoverage.ts:134-153` (ε Ind) | `spherex_dr1: 340`; pasadas de 120, 147, 73 y 120 imágenes (460, de DATA.md) | El [registro de ε Ind B](validation/eps-indi-b.md) y la nota de DATA.md §3.0 dan 458 en SIA2 en vivo (338/120; 118, 146, 74 y 120), y la causa del 460 no está verificada. La UI suma las imágenes con el conteo que no se reprodujo | Conteo principal 458 (`spherex_dr1: 338`; 118, 146, 74 y 120), y en la nota: 'DATA.md §3.0 first counted 460 (340/120); live SIA2 on 2026-11-14 19:24 UTC gives 458 at this centre and at the field centre (docs/validation/eps-indi-b.md); the cause of the difference is not verified.' | menor | WS7 |
| `frontend/src/three/spherexCoverage.ts:223` | «R Dra lies in the NEP deep field.» | R Dra está a 8,6° del polo eclíptico norte. Tiene 1954 frames de las colecciones deep, contra ~29 400 en el NEP (DATA.md §3.0): cae en la huella de las colecciones deep, no en el centro del campo profundo | "R Dra is 8.6° from the north ecliptic pole, inside the footprint of the SPHEREx deep collections (1,954 of its 2,493 frames)." | menor | WS7 |
| `frontend/src/three/ephemerides.ts:260-261` (`MIRA_PREDICTION_CAVEAT`) | «IR amplitude is smaller and IR maxima lag the visual ones» | Correcto en lo cualitativo, y el registro ya lo cuantifica: 0,5–1,3 mag pico a pico según el detector (en V, 6,5 mag) y máximos entre 1 d antes (D1) y 47 d después (D4) de los visuales. En D1 no hay retraso | "V-band prediction from a catalogue ephemeris, not a SPHEREx light curve. Measured offline on the SPHEREx FITS files, the infrared cycle is 0.5–1.3 mag peak-to-peak (6.5 mag in V), with maxima from 1 day before (0.74–1.1 µm) to 47 days after (2.4–3.8 µm) the visual ones (docs/validation/r-draconis.md)." | menor | WS7 |
| `frontend/src/three/appearanceNotes.ts:377-380` (RW Aur A, por qué no gira) | «no secure period: a candidate of about 5.5–5.7 d without a formal uncertainty» | AAVSO VSX da P = 2,64 d para RW Aur (tipo CTTS/ROT+CTTS, A+B sin resolver; contexto WS3, 2026-11-15) y la ficha no lo menciona. La decisión no cambia (no hay un período seguro de A), pero falta decir por qué no se usa | Agregar al final: "; AAVSO VSX lists 2.64 d for RW Aur (type CTTS/ROT, A+B unresolved, component not stated): not adopted" | menor | WS7 |
| `frontend/src/three/colorModes.ts:650-652` (`colourModeChip`) | Modo visible sin chip (`return null`) | IR y D1–D6 llevan el chip «BLACKBODY MODEL»; el visible no, aunque también es el color de un cuerpo negro a la Teff de catálogo y no el color real (bandas de TiO en R Dra; enanas M). Lo dice la leyenda, pero no el chip | `if (mode === 'visible') return 'VISIBLE · BLACKBODY COLOUR MODEL';` | menor | WS7 |
| `frontend/src/three/skyTrack.ts:299` (WISE 0855) | «RECON 4.1 predicts 133.757926, −7.241980 … from the team's own WISE + NEOWISE fit …; this track, from Kirkpatrick et al. 2021, is 0.31″ (0.05 px) away» | Correcto. Falta decir que Kirkpatrick et al. 2021 es la solución elegida (decisión de WS3, abajo) | "Adopted solution: Kirkpatrick et al. 2021, also used by fields.toml and docs/validation/wise-0855.md. Cross-check: the team's own unpublished WISE + NEOWISE fit (docs/RECON_SPHEREX.md 4.1, μ ≈ −8095, +696 mas/yr) is 0.31″ (0.05 px) away on 2026-11-14." | menor | WS7 |
| `docs/DATA.md:439-440` (Notas de otros WS, WS7) | ε Ind B: «❓ … WS7 no lo re-consultó en Gaia». WISE 0855: «Falta que WS3 elija uno para los recortes» | Se pueden cerrar. La solución de ε Ind B coincide cifra por cifra con Gaia DR3 en el TAP de ESA (fixture de WS3 del 2026-11-15). WS3 eligió Kirkpatrick et al. 2021 para WISE 0855 | ε Ind B: «📄 Coincide con Gaia DR3 6412596012146801152 en el TAP de ESA (fixture de WS3, `pipeline/tests/fixtures/ws3/context/`, 2026-11-15): RA 331.0764526, Dec −56.7938121, µ 3981.977 / −2466.832 mas/a, plx 270.658 ± 0.690 mas.» WISE 0855: «📄 WS3 eligió Kirkpatrick et al. 2021 ([SCIENCE.md](SCIENCE.md#revisión-científica-del-3d-ws7-47---2026-11-15)): es la solución publicada, con errores, y la que usan `fields.toml`, el registro y el contexto de WS3; el ajuste de RECON §4.1 queda como control.» | menor | WS7 |

### Decisiones de WS3

**WISE 0855: se usa Kirkpatrick et al. 2021** (la predicción que el panel ya dibuja), no el ajuste WISE + NEOWISE de
`RECON_SPHEREX.md` §4.1. Razones:

1. Es una solución publicada y con errores (µ ± 1,3 mas/año, paralaje 439,0 ± 2,4 mas). El ajuste de RECON es nuestro, no
   está publicado y no documenta errores ni método (da una paralaje de «≈ 430–475»).
2. Es la que usa el resto del proyecto. SIMBAD (vía Sesame CfA) da justamente esa solución (referencia
   `2021ApJS..253....7K`); de ahí salen el centro de `fields.toml`, las predicciones del
   [registro](validation/wise-0855.md) y el contexto de WS3. 🧮 El centro de `catalog.py` a MJD 57633,39 es la posición
   J2000 de SIMBAD propagada a esa época, con 0,011″ de diferencia. Con una sola solución, el panel 3D y los recortes no
   difieren en 0,05 px.
3. SPHEREx no distingue entre las dos: 0,31″ = 0,05 px es comparable al error por temporada del registro (0,17–0,36″) y
   menor que el sistemático de la mezcla con Gaia DR3 5756956644387831296 (+0,38 a +1,08″ al norte en S2, según el
   método) y que el error del movimiento propio medido (±0,34″/año). Ese movimiento, (−8,24 ± 0,34, +1,21 ± 0,34)″/año en
   la revisión, es igual de compatible con Kirkpatrick (−8,12, +0,67) y con RECON (≈ −8,10, +0,70).

En los dos casos hay que incluir la paralaje: alterna ±0,43″ en E entre temporadas (§0.2).

**Barnard b–e, t0 de Basant et al. 2025 (M5): WS3 recomienda aceptar la lectura como conjunción inferior**, con la
advertencia visible que ya tiene. La decisión es del equipo; esta es la opinión de WS3 y sus razones:

1. **Argumento físico, independiente del código.** Los t0 tienen errores de ±0,08–0,37 d (2–5 % del período). Según WS7,
   ω queda sin restringir (±120°), y e es compatible con 0 (archivo: 0,03–0,08, a ≤ 1,6σ). El tiempo de periastro de una
   órbita casi circular con ω libre está mal definido: su posterior se extendería sobre buena parte del período. Un tiempo
   de conjunción, en cambio, queda bien fijado por la fase de la curva de velocidad radial. Un t0 tan acotado es una
   conjunción.
2. **Control externo.** 🧮 t0(b) − 33 P = BJD 2460139,291, a +0,087 d (0,028 ciclos, 0,50σ) del Tc de González Hernández
   et al. 2024 (2460139,204 ± 0,149 d), un ajuste independiente con otro instrumento. Si t0 fuera un periastro con ω
   arbitrario, la conjunción caería en cualquier punto del ciclo. La chance de quedar a ≤ 0,087 d del Tc publicado sería de
   ~6 % (0,17 d sobre 3,15 d).
3. **Convención del código.** Según WS7, juliet pasa t0 a RadVel como `tc` (conjunción) y no tiene un parámetro de
   periastro. WS3 no leyó ese código.

En contra: el texto del paper dice «time of periastron passage», y el Exoplanet Archive guarda el valor en `pl_orbtper`,
con `pl_tranmid` vacío (consultado en vivo por WS3). Sigue al paper, así que no confirma ni refuta. Condiciones para
aceptarla:

- mantener «read as the time of inferior conjunction; the paper text says periastron» en la nota de la órbita, la ficha y
  «On this date»;
- sumar el término de excentricidad (fila de `catalog.py:188-190`);
- recordar en la leyenda que la inclinación, la orientación del plano y el sentido de giro no se conocen: la flecha
  «toward Earth» es una convención de dibujo;
- si se puede, consultar a los autores.

Si el equipo no la acepta, se revierte como indica WS7 (`epoch_mjd = null`, tarea WS7-9).

### Lo que está sólido

- **Nada se presenta como imagen.** El badge «3D MODEL · NOT AN IMAGE» está en el visor (`SystemViewer.tsx:279`), en la
  página (`SystemPage.tsx:89`, con `representation_note`) y en la ficha (`BodyPanel.tsx:270`).
- **Superficies.** Esferas lisas por defecto. Las celdas de R Dra y las bandas de ε Ind Ab y Ba aparecen solo con el toggle
  class-typical, que está apagado (`SystemViewer.tsx:112`) y marcado ILLUSTRATIVE. El giro sale solo de un período
  verificado (Barnard 145 ± 15 d; VSX da 130 d para V2500 Oph, compatible) y no se ve sobre una esfera uniforme.
- **Colores.** El modo IR por defecto lleva el chip «FALSE COLOUR · BLACKBODY MODEL» y la leyenda de canales en orden de λ
  (azul = D1+D2, verde = D3+D4, rojo = D5+D6); D1–D6 tienen su propio chip. No hay colores mal rotulados como visibles (solo
  falta el chip del modo visible, fila de `colorModes.ts:650-652`). Por debajo de 2500 K el color es cualitativo y con
  contorno punteado.
- **Valores de catálogo comprobados por WS3.**
  - Barnard: posición, µ, paralaje y VR de Gaia DR3 (fixture); P, masa mínima, a y t0 con sus errores de los cuatro
    planetas (Exoplanet Archive, en vivo).
  - ε Ind A: µ, paralaje 274,8431 ± 0,0956 mas y VR −40,43 km/s (Gaia DR3 vía VizieR CfA, en vivo); K5V (SIMBAD).
  - ε Ind A b: P, a, e, 6,5 MJ, radio calculado 12,7 R⊕ = 1,13 RJ e i = 102° (fixture del Exoplanet Archive).
  - ε Ind B: astrometría del panel del cielo (Gaia DR3, fixture).
  - WISE 0855: centro, µ y paralaje (SIMBAD/Kirkpatrick+2021).
  - R Dra: Gaia DR3; Bailer-Jones 792 (750–832) pc; VSX P = 246,12 d, época HJD 2457370, V 6,7–13,2; Gaia LPV 247,2 ± 6,0
    d; GCVS 245,6 d (§3.1 y revisión de textos).
  - RW Aur: la identidad A/B de `catalog.py` coincide con el WDS (§0.3; SIMBAD tiene los ids de Gaia invertidos); la
    distancia de 156,1 pc sale de la paralaje de B.
  - 🧮 Kepler cierra en todas las órbitas: ε Ind Bb, a³/P² = 0,1147 M☉ = Ba + Bb de Chen et al. 2022; ε Ind Ab, 0,806 M☉;
    RW Aur B, a = q/(1 − e) = 258 UA y P = 2773 años; Barnard b, a = 0,0229 UA.
- **Ventanas de pasadas SPHEREx** (`spherexCoverage.ts`). Coinciden con DATA.md §3.0 y con las temporadas de los registros
  dentro del redondeo de ±0,5 d: Barnard 60902,87–61305,63; ε Ind B 60789,86–61315,48; WISE 0855 60800,70–61174,29; RW Aur
  60919,42–61299,90; R Dra 60789,9–61310,3, con deep. También coinciden los conteos por detector (salvo el 460 de ε Ind), la
  2.ª pasada de WISE 0855 partida en dos visitas y la última de ε Ind B solo con D2, D3, D5 y D6.
- **Fases desconocidas.** ε Ind Ab, Ba y Bb y RW Aur B se dibujan como anillos «phase unknown», con la razón y la fuente.
  RW Aur A y B nunca se animan. Barnard b–e llevan la dispersión de fase de 1σ (11–31°) con la fórmula correcta (🧮 b: 13,0°
  al inicio de DR1 y 18,6° en el último frame QR3).
- **Panel del cielo** (`skyTrack.ts`). El modelo es correcto: movimiento espacial con VR más paralaje; Tierra heliocéntrica,
  con un error ≤ 0,75 % de la paralaje. Para ε Ind usa la astrometría de B, que es lo que mira el campo (A está a ~402″ al
  oeste). La estrella de campo junto a WISE 0855 coincide con Gaia DR3 5756956644387831296 (fixture: 133.7581825,
  −7.2411559).

### Sigue abierto (ya declarado por WS7 o por la revisión de textos)

- Lo que [`VISION_3D.md`](VISION_3D.md) («Diferencias con `VISION.md` que siguen abiertas») ya declara: el color sale de la
  Teff de catálogo y no del espectro SPHEREx; el radio es de catálogo (R Dra 250 R☉ ilustrativo, RW Aur A estimado); la
  pulsación es una curva V y no la curva SPHEREx. Las medidas ya existen offline en los registros, y WS3 publicó las curvas
  de luz de las variables (#59): es el insumo de WS7-8.
- Filas de la revisión de textos sobre `catalog.py` que siguen abiertas tras #47, con su línea nueva: «a Sun-like star»
  (`:264`), «Y4 (approx.)» y «~Y4» frente a Y2 de SIMBAD (`:441` y `:444`), la nota de R Dra sin las medidas SPHEREx
  (`:476-486`), Ba+Bb sin resolver también en SPHEREx (`:405`) y los facts del bloque **A5**. Resuelta: `field_id` de
  `eps-indi-b`, `r-draconis` y `rw-aurigae` (`:275`, `:515` y `:586`). Sigue pendiente publicar los sistemas en el dataset
  real: `data/products/manifest.json` tiene `systems: []` (WS7 + WS4).
- La VR de RW Aur (+15 km/s de SIMBAD, Nguyen et al. 2012) no coincide con la de Gaia DR3 para B (−20,9 ± 4,0 km/s). 🧮 En
  el panel del cielo el efecto es < 0,001″.

**Para WS3 (✅ resuelto el 2026-11-15, V15).** `science/context.py` nombraba el click de RW Aur con el cross-id de SIMBAD,
que llama «RW Aur B» a Gaia DR3 156430817820015232; según el WDS (§0.3) y WS7 es A. Ahora `COMPONENT_NAME_FIXES` corrige el
nombre visible (`display_name` «RW Aur A»; `main_id` conserva el de SIMBAD) y agrega un aviso. El aviso dice que el tipo
espectral y la variabilidad salen de la entrada «RW Aur B» de SIMBAD y que SPHEREx mide el par sin resolver. Test:
`test_rw_aur_click_names_the_component`.

**Conteo de saturación de RW Aur** (✅ resuelto en #66/#67: el registro dice «304 de 335; ningún frame D2–D6 limpio; 17 de 56
limpios en D1», sin el reparto por detector de `sat`. El texto que sigue es el diagnóstico original) (registro: coordinación; `DATA.md` §3.2: WS1; §0 de este documento:
WS3). El [registro](validation/rw-aurigae.md) dice «`OVERFLOW` en 304 de 335 frames: todo D2–D6 y 37 de 56 frames de D1»,
y `DATA.md` §3.2 repite «todo D2–D6». 🧮 No cierra: D2–D6 tienen 55 + 4 × 56 = 279 frames, y 279 + 37 = 316, no 304. La
tabla de clases del propio registro (`sat` 304, `bad` 10 «sin `OVERFLOW`», `edge` 4, `clean` 17, todos en D1) admite dos
lecturas: o 12 frames D2–D6 quedan fuera de `sat` (al menos 8 de ellos son `bad`, sin `OVERFLOW` en la apertura de
r = 3 px), o D1 tiene 25 frames con `OVERFLOW` y no 37 (y los 14 `bad` + `edge` están en D1). Las dos sostienen lo que
usan los textos de esta revisión: ningún frame D2–D6 está limpio (0 de 279), solo D1 es medible y hay `OVERFLOW` en 304
de 335. Falta recontar por detector con `r3_phot.py` (la caché de los 335 patches no está en esta máquina) y corregir el
registro, `DATA.md` §3.2 y §0.

### Comprobaciones hechas para esta revisión (2026-11-15, UTC)

- **Offline:** `object_context` por nombre de los cinco blancos, reproducido desde los fixtures de WS3 (grabados entre las
  03:44 y las 04:22 UTC): Gaia DR3 (posiciones, µ, paralaje, FLAME, Bailer-Jones, LPV), SIMBAD, VSX, 2MASS, AllWISE y el Exoplanet
  Archive.
- **05:14, TAP de Gaia en ESA:** no respondió (HTTP 000). Se usó el espejo de CfA.
- **05:15, VizieR CfA `I/355/gaiadr3`:** ε Ind A = 6412595290592307840: RA 330.8724079, Dec −56.7972547, plx 274.8431 ±
  0.0956 mas, µ (3966.661, −2536.192) mas/año, VR −40.43 ± 0.13 km/s, RUWE 1.148. Coincide con `catalog.py`.
- **05:18, Sesame CfA** (`eps Ind`): K5V, plx 274.8431 mas.
- **05:19, NASA Exoplanet Archive** (`ps`, `default_flag = 1`, Barnard): `pl_orbtper` 2460243.38 / 2460242.92 /
  2460243.70 / 2460245.30 para b / c / d / e, con los errores de `catalog.py`; `pl_tranmid` vacío; e 0.03 / 0.08 / 0.04 /
  0.04.
- 🧮 Los cálculos (exceso IR de RW Aur, O−C de R Dra, t0 de Barnard contra González Hernández+2024, término 2e y
  propagación de WISE 0855) están en un script del scratch local, sin versionar.

**No re-verificado por WS3** (no inventar): la masa class-typical de R Dra (Feast 2009); el ±10 % de diámetro de las Miras
(Ireland+2004, Woodruff+2004); las Teff de R Dra (van Belle+2002, McDonald+2012), de RW Aur A (Testi+2022) y de RW Aur B
(Dodin+2020); los valores de Kurtovic+2024; el radio de ε Ind A (Sanghi+2026); Matthews+2024; Luhman+2024; Hitchcock+2020;
Esplin+2016, Wilson+2025 y Miles+2026; el «e < 0.02» y el ω de Basant+2025; la convención de juliet/RadVel; la lista O−C de
Karlsson; la subida del 45 % de VSX; los desplazamientos AB − Vega de WISE (2,699 y 3,339). Los registros de validación son
análisis de IA con revisión independiente; la revisión humana sigue pendiente.

## Revisión científica de las curvas de luz (#78, #79, #83) - 2026-11-15

rpccp pidió en #78 la revisión de WS3 de los campos científicos y unidades, las magnitudes relativas por bin, los puntos
cero de comparación no aplicados, la significancia del período y la procedencia/completitud. Esta sección responde ese
pedido. Abarca:
- el contrato 0.6.0 (`LightCurve*` en `models.py`);
- el adaptador `backend/errante_api/lightcurve_build.py`;
- los dos productos publicados (`backend/errante_api/curated/lightcurves/{rw-aurigae,r-draconis}.json`);
- el panel `frontend/src/components/LightCurvePanel.tsx`.

**Método.** Cinco revisiones independientes: contrato, adaptador, números, presentación y una reproducción desde los
FITS. Un verificador por revisión intentó refutar cada hallazgo, y al final un crítico buscó lo que faltaba revisar.
Salieron 71 hallazgos. Ninguno quedó refutado del todo, y varios bajaron de severidad. Todos los números de esta sección
se recalcularon desde los JSON publicados, desde los FITS o desde los catálogos. Los scripts están en el scratch local,
sin versionar.

### Veredicto

- **La ciencia de los dos productos se sostiene.**
  - Los dos se reproducen bit a bit desde los FITS reales con los presets exactos. Solo cambian `built_at`, `id`, la
    huella y `schema_version`.
  - La selección de frames está completa según IRSA en vivo.
  - Los números concuerdan con los registros R05 y con los catálogos.
  - **No hay bloqueantes.**
- **Lo que falla es la comunicación.** Los productos traen sus advertencias en `notes`, pero el panel no las muestra.
  Las barras de error son solo estadísticas, y faltan tres avisos:
  - que R Dra usa solo el sondeo ancho;
  - que RW Aur es una binaria sin resolver;
  - que la saturación de RW Aur se come los estados brillantes.

  Son siete puntos importantes (LC1–LC7), que conviene arreglar antes de la demo.
- `ready` y `significant: true` no equivalen a una validación R05, y los productos lo dicen. Los registros de
  `docs/validation/` siguen siendo la evidencia de R05.

### Respuestas a las preguntas de #78

1. **Campos y unidades: correctos.**
   - `rel_mag` = −2,5 log10(flux) − `mean_mag` del bin, y positivo = más débil. Error máximo recalculado: 9e−16.
   - `mean_mag` es la magnitud instrumental media del bin en la unidad del producto: mJy (apertura) o MJy/sr (ala).
     Sin punto cero absoluto.
   - `rel_mag_err` = 1,0857 · `flux_err`/`flux`, solo estadístico. En el ala excluye el ruido de fotones del propio
     ala (no hay plano `VARIANCE`), así que es una cota inferior.
   - El validador apertura → mJy / ala → MJy/sr relativo es correcto. El `Literal` de exclusiones coincide con los
     motivos de WS3, y `types.ts` coincide con los modelos.
   - **Falta:** ninguno de estos campos tiene `description` en el contrato ni en el esquema (LC15).
2. **Magnitudes relativas por bin.**
   - Cada punto se compara con la media geométrica de su detector y su bin de λ (1 %). El 0 % del panel es esa media,
     no un nivel base ni de reposo: se comparan los puntos entre sí, no con el 0.
   - En RW Aur los cinco bins tienen exactamente dos puntos, y cada `rel_mag` vale ± la mitad de la diferencia
     (±0,264, ±0,198, ±0,517, ±0,188, ±0,049). Por eso la mediana es 0 y el `summary` (σ 0,294,
     `scatter_over_control` 16,3) descansa en solo cinco diferencias: es descriptivo, no una significancia.
   - Normalizar por bin no sesga el período ni las amplitudes de R Dra (inyección y recuperación, 200 simulaciones).
     Sí comprime un poco los `rel_mag` mostrados en D1/D2.
3. **Puntos cero no aplicados.**
   - `zero_point_mag` es la mediana de los `rel_mag` de ≥ 2 estrellas de comparación en esa exposición. Se recalculó
     sin diferencias: 55 frames de RW Aur y 490 de R Dra.
   - Signo: positivo = las comparaciones se ven más débiles, así que para corregir se **resta**.
   - **No aplicarlo es correcto.** En R Dra, aplicarlo deja igual la dispersión en D1–D3 y la empeora en D4–D6
     (0,113 → 0,129, 0,081 → 0,097, 0,071 → 0,110), porque en esos detectores las comparaciones son débiles y su
     ruido se suma. En RW Aur cambiaría los pares en ≤ 0,03 mag.
   - **Falta** documentar el signo y el número de estrellas (LC15).
4. **Significancia del período de R Dra: real, pero mal expresada.**
   - 0 de 1000 permutaciones de visitas alcanzan el pico observado (Δχ² 1826 contra un máximo nulo de 975).
   - El `false_alarm` publicado, 0,0099 = 1/101, es solo el **piso** de 100 permutaciones: una cota, no una medida
     (LC8).
   - «Significativo» quiere decir *variabilidad correlacionada en el tiempo*, no *periodicidad*. Sobre el muestreo de
     R Dra, una tendencia lineal de 0,6 mag da el mejor período en el borde de la grilla (800 d) y sale
     «significativa» (LC7).
   - El período de 259,1 d (bootstrap 95 %: 240,2–276,3 d) contiene los valores de catálogo, todos consultados en el
     espejo de VizieR en CfA:
     - GCVS: 245,6 d;
     - VSX: 246,12 d;
     - Gaia DR3: 247,2 ± 6,0 d.
   - A 247 d, Δχ² queda solo ~5 por debajo del pico. **Este producto no distingue 259 d de 247 d.** El «~260 d» de §0.3
     sale del registro, que usa las 2493 exposiciones.
   - Los picos secundarios (104,3, 150,4 y 79,9 d) son alias de la cadencia (ventana espectral con picos en 183 d y
     350 d).
5. **Procedencia y completitud.**
   - La selección está completa: IRSA SIA en vivo (2026-11-15, 14:18–14:20 UTC) devolvió exactamente los mismos frames
     (56 para RW Aur D1 y 539 para R Dra).
   - `stale_search: true` no quiere decir que falten datos. Cuando se armó el producto, IRSA falló (502 y timeouts), y
     respondió el snapshot comprometido del 2026-11-14 19:33/19:34 UTC. El producto no guarda esa fecha (LC9).
   - `partial: true` sale de ese snapshot y, en R Dra, de un `no_overlap` que WS1 no cuenta como pérdida (LC10).
   - **La pérdida real no está declarada:** R Dra usa solo DR1+QR3, que son 539 de 2493 exposiciones (21,6 %) en
     426 d, unos 1,64 ciclos. Quedan afuera las colecciones deep (LC5).
   - La huella `57d42f…` publicada no se reproduce con el código mergeado: HEAD da `bc4a19…` y el árbol de #79,
     `0c372c…` (LC11).

### Lo que está sólido (comprobado)

- **Reproducción**, en el scratch local y con los mismos comandos del README:
  - `python -m errante_api.lightcurve_build --preset rw-aurigae` (27,6 s) y `--preset r-draconis` (105,2 s) generan
    curvas idénticas;
  - en R Dra, 7 floats difieren en ≤ 1,5e−15 relativo;
  - los RNG de bootstrap y permutaciones tienen semilla fija (seed 1).
- **RW Aur coincide con el registro:**
  - 17 frames D1 limpios: 10 usados más 7 `lone_bin`;
  - 8 pares emparejados en λ, iguales al registro con ≤ 0,003 mag de diferencia (−1,008 y −1,034 mag entre
    2025-09-02 y 2026-09-08);
  - ensemble ≤ 0,021 mag.
  - **El abrillantamiento de ~0,4–1,0 mag es robusto:** queda 11–31σ por encima de la dispersión de pares de las
    propias comparaciones (0,033 mag, 180 pares).
  - El par de 0,879 µm (−0,098 mag) no es significativo por sí solo, como dice el registro.
- **Elección de detectores de RW Aur.** Usar solo D1 es correcto (0 frames limpios en D2–D6). No fijar período también
  lo es: hay 10 puntos, y el período de rotación de 2,64 d (VSX) cae fuera de la grilla.
- **Amplitudes de R Dra** (pico a pico del seno, con error de la covarianza): D1 1,21 ± 0,39, D2 1,05 ± 0,28,
  D3 1,28 ± 0,15, D4 0,61 ± 0,06, D5 0,62 ± 0,03 y D6 0,94 ± 0,04 mag.
  - Coinciden con el registro en D1, D2, D3 y D5. D4 y D6 difieren un poco a 247 d (0,63 / 0,91 contra 0,51 / 0,80).
  - Que el ala sature en los 538 frames justifica el método.
- **Estrellas de comparación.**
  - Las 11 son estrellas reales de catálogo: todas tienen contraparte 2MASS y Gaia a ≤ 2,3″, y ninguna figura en VSX
    a 30″.
  - En D5/D6 su dispersión es igual a su error estadístico (cociente 0,5–1,5): ruido de estrellas débiles, no
    estrellas variables.
  - No hay contaminación medible por el halo del blanco (p = 0,81 entre frames con el blanco saturado y sin saturar).
- **Movimiento propio despreciable** (Gaia DR3): 0,025–0,028″ en la línea de base, unos 0,004 px. La nota «fixed sky
  position» es correcta.
- **Pureza de la apertura de RW Aur** (r = 3 px = 18,5″): el resto de las fuentes aporta < 0,1 %. La única mezcla que
  importa es la de A+BC (LC4).
- **Fuentes accesibles:** las 594 URI de `provenance.sources` responden HTTP 200 sin login.
- **Panel:**
  - la conversión a % (100 · (10^(−0,4 `rel_mag`) − 1)) y las barras asimétricas están bien;
  - brillo hacia arriba;
  - nunca mezcla bins ni detectores en un mismo gráfico;
  - el ala se rotula como relativa;
  - «Candidate cycle» aparece solo si es significativo;
  - el caveat del período está a la vista;
  - los conteos coinciden con el JSON;
  - el panel se oculta en datos sintéticos.
- **Tests:** pasan los 55 de curvas de luz, de contrato y de backend.

### Hallazgos importantes (antes de la demo)

| ID | Dueño | Qué | Arreglo propuesto |
|---|---|---|---|
| LC1 | WS5 | El panel no muestra `curve.notes` ni `provenance.notes`. Quedan invisibles «not a new R05 validation», el aviso de filtro lineal variable, «saturated = lower limits» y «zero point not applied». Tampoco muestra la selección (colecciones, rango de fechas, n_found, fecha del build) | Bloque visible «Limits of this product» con las notas, y otro «Data selection» con colecciones, MJD usados, n_found/n_selected y fecha del snapshot |
| LC2 | WS5 (+ WS3) | Las barras son solo estadísticas: en R Dra, mediana 0,001–0,004 mag contra pisos empíricos de 0,09–0,39 mag. Dentro de un mismo bin, puntos separados por < 5 d ya difieren hasta 0,5–0,9 mag (D1/D3) | Decir en el pie que las barras no incluyen sistemáticos, y mostrar el control del detector (y `floor_mag` en el ala) como banda o como número. WS3 puede publicar un piso por detector (LC23) |
| LC3 | WS5 | En modo estático (Pages) el panel no carga: `export_static_science.py` copia los JSON a `lightcurves/`, pero `client.getLightCurve` falla fuera del modo API (`client.ts:135`). **Importante solo si se entrega Pages:** la URL pública de #84 (https://errante.34-148-242-13.sslip.io, con API) sí muestra el panel de R Dra (comprobado el 2026-11-15) | Leer `${staticBase}lightcurves/{id}.json` en modo estático y tratar un 404 como «missing» |
| LC4 | WS4 + WS5 | RW Aur, dos avisos que faltan. (a) Es **A+BC sin resolver**: WDS JOY 5, 1,50″ a PA 254° (2022); par Gaia a 1,493″; las dos componentes caen dentro de la apertura de 18,5″. (b) **La saturación depende del brillo**: satura 7/19 (S0, la temporada débil), 14/19 (S1) y 16/18 (S2), así que los estados brillantes quedan afuera y en S2 solo sobreviven 2 puntos. Además, el panel lista los flujos saturados como «Measured signal» cuando son cotas inferiores | Nota por preset en `PRESETS` (WS4) y texto del panel (WS5): «Uncorrected aperture flux (r = 3 px); RW Aur A+BC unresolved; N saturated exposures (lower limits, mostly in the bright seasons) are excluded». Saturados como «≥ valor» |
| LC5 | WS4 + WS5 | R Dra usa solo el sondeo ancho (539 de 2493 exposiciones, 426 d) y no lo dice. La página muestra arriba «~2,500 frames… the best light-curve case» (field.json) y el panel, «450 of 538» | Nota del preset: «Wide survey only (DR1+QR3): 539 of 2493 exposures; deep collections excluded; data end 2026-07-16». Opcional: reconstruir con las colecciones deep y `max_frames` ≤ 2500, revisando el tope de 8 MiB (LC16) |
| LC6 | WS3 (+ rebuild del campo) | Los textos de `fields.toml` que se ven arriba del panel lo contradicen: RW Aur dice «not single exposures», y R Dra, «period ~247 d… ~2,500 frames». Ya estaban como pendientes en la revisión de textos | Aplicar los textos listos de esa tabla. A R Dra, agregarle que la curva de la app usa solo el sondeo ancho. `field.json` se regenera al publicar los campos |
| LC7 | WS3 + contrato + WS5 | «Significant» se presenta como si confirmara un período, pero solo prueba variabilidad ordenada en el tiempo: una tendencia o un escalón pasan el test en el borde de la grilla. El docstring de `LightCurvePeriod` dice que un período significativo deja de ser candidato, y eso contradice el caveat de WS3. El contrato acepta `period_days` = 5000 con la grilla [20, 800] | WS3: no testear un mejor período en el borde de la grilla o que cubra < 1,5 ciclos, y reescribir el caveat (✅ hecho; ver «Arreglos de WS3 aplicados»). Contrato: `period_range_days[0] ≤ period_days ≤ [1]` y docstring corregido. WS5: «Variability significant; best period 259.1 d», con los alias y los períodos de catálogo |

### Hallazgos menores y observaciones, por dueño

**WS4 (rpccp), `lightcurve_build.py` y documentos:**
- **LC8.** Publicar con `--permutations 999` y `--bootstrap 1000`: 1000 permutaciones tardan ~9 s. Con 100 resamples,
  el límite inferior del bootstrap salta entre 231 y 245 d según la semilla, y una sola excedencia cambiaría el
  veredicto. WS5 debería mostrar «≤ 1/101 (0 of 100 permutations reached the peak)» en lugar de «0.99%».
- **LC9.** Guardar qué respondió la búsqueda (`service`) y la fecha del snapshot en `provenance.notes`; no hace falta
  tocar el contrato. El constructor offline hereda el tope de 20 s del fallback de la API (`irsa.search_budget`), así
  que con el snapshot comprometido casi siempre gana el snapshot. Hay que darle al hijo
  `ERRANTE_SEARCH_DEADLINE_S` = archive deadline y `ERRANTE_SEARCH_FALLBACK_DEADLINE_S`.
- **LC10.** `partial` no debería encenderse por `no_overlap` (`point.py` lo trata como completo). El mapeo de fallas
  rotula todo como `download_failed`, timeouts y FITS truncados incluidos. El test que exige `partial and
  stale_search` en los productos reales va a fallar cuando haya un rebuild fresco.
- **LC11.** La huella y el `id` no se pueden reproducir ni verificar desde el JSON. Registrar el commit y las versiones
  efectivas, o documentar el `id` como opaco. Los productos dicen `schema_version` 0.6.0 y el contrato está en 0.7.0:
  inofensivo, porque los modelos de curva de luz no cambiaron.
- **LC12.** El adaptador reimplementa `variability.light_curve()`. Hoy da lo mismo que la CLI: la verificación lo
  confirmó (`errante lightcurve` con los parámetros del preset da la misma curva). Pero se pierden la nota de timeout,
  el calificador de unidad («no aperture correction»), `box_px`/`planes` y el modo automático del período, y ningún
  test lo ata a la CLI. Llamar a `light_curve()`; si hace falta `max_workers`, WS3 lo agrega como parámetro.
- **LC13.** Documentar por qué RW Aur usa solo D1 y no fija período: satura en todo D2–D6 y tiene 10 puntos.
- **LC14.** Documentación vieja después de #83: `backend/README.md:316-318` dice que no hay panel ni publicación estática;
  WS4-11 sigue listando el panel como pendiente; `ai-usage.json` llama «draft» a #78, y el docstring de la ruta dice
  «validated».

**Contrato (PR `contract:`):**
- **LC15.** Agregar `description` a `rel_mag` (signo), `rel_mag_err` (estadístico; en el ala, cota inferior), `mean_mag`
  (unidad), `zero_point_mag` (definición, signo «restar», número de estrellas), `relative_only`, `unit`, `control`,
  `summary` y `scatter_over_control`. El fixture de `test_contract.py` es científicamente imposible: un bin de un punto
  con `rel_mag` −0,1.
- **LC16.** `matched_pairs` admite 100 000 pares y `max_frames` 2500, pero el tope de publicación es 8 MiB. Los pares
  crecen de forma cuadrática y no son independientes: cada frame aparece en hasta 14.
- **LC17.** `period: bool = False` no puede expresar el modo automático de WS3 (`None`). Hoy no afecta, porque los presets lo
  fijan.
- **LC18.** Validador de `false_alarm`: `n_permutations` = 0 o ≥ 99, y `false_alarm` · (n + 1) entero. Opcional: `n_exceed`.

**WS5 (mateoa007), además de LC1–LC5:**
- **LC19.** Se grafica un solo bin de 1 % por vez: como mucho 10 de los 450 puntos de R Dra y 2 de los 10 de RW Aur. Así no se ve
  el ciclo de 259 d. Agregar una vista por detector con todos los puntos usados (son comparables tras la normalización
  por bin) o plegada en fase.
- **LC20.** Mostrar los `matched_pairs` de RW Aur, que son el método del registro R05. Tres de los 8 pares cruzan bins y no
  aparecen, entre ellos uno de los dos cambios de ~1 mag entre S0 y S2.
- **LC21.** «First to last» sin incertidumbre: en una Mira se lee como tendencia, cuando es una diferencia de fase.
- **LC22.** Explicar que el 0 % es la media del bin, agregar columnas de % y error a la tabla, y agregar tests de la
  conversión y de los tres textos del período.

**WS3 (nosotros):**
- **LC23.** Publicar un piso de incertidumbre por detector que el panel pueda dibujar. En R Dra, los pisos de D1–D3 son
  dispersión de medición por exposición (los residuos no se correlacionan dentro de una visita), no la forma intrínseca
  de la Mira.
- **LC24.** `scatter_over_control` divide la dispersión del ala por la de comparaciones medidas con apertura. Para
  `wing` no significa nada: pasarlo a `null` o documentarlo. En RW Aur cuenta 5 diferencias como 10 puntos.
- **LC25.** `control[det].excluded` siempre sale `{}`, aunque en R Dra se excluyen 1178 de las 3228 mediciones de
  comparación.
- **LC26.** Falta un control a nivel de pares: la dispersión de pares de las comparaciones es 1,4–1,9 veces el control
  por punto, y en RW Aur da 0,033 contra 0,018.
- **LC27.** Los pisos del período se calculan en el mejor período estadístico (239 d), no en el final (259 d).
  Recalculados en el período final, el de R Dra pasa de 259,1 a 261,9 d (Δχ² 0,3 entre los dos, dentro del error), y el
  piso de D6 baja de 0,091 a 0,075.
- **LC28.** Bins de 1 %:
  - en R Dra D1 son anchos: el corrimiento de λ dentro del bin explica ~0,14 de los 0,29 mag de residuo;
  - en D5/D6, un bin de 1 % es más ancho que el canal del filtro lineal variable (hoy sin efecto medible);
  - el ensemble de cada par no se empareja en λ (mediana 0,5–0,9 %).
- **LC29.** `amplitude_mag` sin error (ver arriba) y comentario de `PERIOD_FALSE_ALARM` inexacto: dice «no más del 1 %
  de las permutaciones», pero con 100, una sola excedencia ya da 2/101.
- **LC30.** En esta PR: actualizar §0.0 y §0.3, que decían que no había producto de curva de luz. Pendiente: un
  addendum fechado en los dos registros de `docs/validation/` (archivos de coordinación) que apunte a
  `/api/lightcurves/{id}`, y la fila de curvas de luz en `docs/PARALLEL_PLAN.md`.

### Arreglos de WS3 aplicados (2026-11-15)

Los arreglos están en `pipeline/errante/science/variability.py`, con tests. Los productos publicados en
`backend/errante_api/curated/lightcurves/` (de WS4) **no se regeneraron**: los números de arriba describen esos productos,
y cambian recién cuando WS4 los republique. Se probaron con un rebuild desde los FITS reales en el scratch, con los mismos
presets y los mismos frames.

| ID | Qué se hizo | Efecto en el rebuild real |
|---|---|---|
| LC7 | Si el mejor período cae a un paso de cualquiera de los extremos de la grilla, o cubre menos de 1,5 ciclos, no se testea: `false_alarm` y `significant` quedan `null` y la nota dice por qué. El caveat dice que «significant» es variabilidad correlacionada en el tiempo, no un período confirmado. La FAP se escribe como cuenta: «1/101 (0 of 100 permutations reached the peak…)». | Ni R Dra ni RW Aur caen en la guarda |
| LC23 (parcial) | El piso de pares y los errores de amplitud se publican en `notes`. Para que sean datos estructurados hace falta una PR `contract:` | Notas nuevas |
| LC24 | Con `wing`, `scatter_over_control` es `null` y una nota explica por qué. Pendiente: en RW Aur el `summary` sale de bins de 2 puntos | R Dra: 25,9…3,3 → `null` |
| LC25 | `control[det].excluded` cuenta las exclusiones de las comparaciones | R Dra: 1178 de 3228; RW Aur: 77 de 280 |
| LC26 | Nota con la dispersión de pares de las comparaciones. En `aperture` es el piso de los pares del blanco; en `wing` se aclara que **no** lo es | RW Aur D1: 0,033 mag (180 pares). R Dra D1–D6: 0,030 / 0,038 / 0,044 / 0,049 / 0,134 / 0,169 |
| LC27 | Los pisos se recalculan en el período final hasta que deja de moverse | R Dra: 259,09 → **261,88 d**, error formal 6,2 → 4,95 d, bootstrap 240,2–276,3 → 242,0–274,4 d. Sigue significativo (1/101). Las amplitudes cambian ≤ 0,06 mag |
| LC28 | El ensemble de cada par usa solo comparaciones emparejadas en λ (\|Δλ\|/λ < `max_frac`). El ancho del bin de 1 % quedó solo documentado | RW Aur: cambia el ensemble de 4 de los 8 pares. Los dos pares de ~1 mag no cambian (corregidos −0,987 y −1,027). Un par queda con una sola comparación. R Dra: 37 pares sin ensemble (antes 12) |
| LC29 | Error de cada amplitud pico a pico, desde la covarianza del ajuste, en la nota del período. Corregido el comentario de `PERIOD_FALSE_ALARM`, y la CLI escribe la FAP como cuenta | R Dra: D1 1,15 ± 0,37, D2 1,06 ± 0,28, D3 1,29 ± 0,15, D4 0,64 ± 0,08, D5 0,63 ± 0,03, D6 0,96 ± 0,03 mag |
| LC4 (parte de WS3) | Nota de saturación por temporada cuando la fracción saturada cambia ≥ 0,3 entre temporadas | RW Aur: «S0 7/19, S1 14/19, S2 16/18…» |

- **Por qué 1,5 ciclos y no los 2 que proponía LC7.** Se midió sobre el muestreo real de R Dra (450 puntos en 426 d),
  con ruido igual a sus pisos:
  - las señales fuertes sin período (tendencias, parábolas, desvanecimientos, escalones de 0,5 mag, sinusoides parciales
    de 600 a 3000 d) caen en ≤ 1,22 ciclos, casi siempre en el borde de 800 d;
  - con 2 ciclos solo se descartarían 2 de 30 sinusoides parciales débiles, y quedarían sin testear los períodos de
    catálogo de R Dra (245,6–247,2 d = 1,72 ciclos).

  Ningún umbral hace que «significant» signifique «periódico»: en ese muestreo, escalones débiles de 0,2 mag pasan el test
  a 3–7 ciclos. Para resolverlo de verdad hay que comparar el seno contra un modelo de tendencia por detector, y eso es
  trabajo nuevo.
- **Con el período nuevo**, 247,2 d (Gaia) queda Δχ² ≈ 10,7 por debajo del pico, pero sigue dentro del bootstrap
  (242,0–274,4 d). La conclusión no cambia: este producto, que usa solo el sondeo ancho, no distingue ~260 d de 247 d.
- **Pendiente:**
  - campos estructurados (PR `contract:`);
  - el `summary` de bins de 2 puntos (LC24);
  - el ancho del bin (LC28);
  - que WS4 republique los dos productos y que WS5 muestre las notas (LC1) y `n_ensemble` junto a
    `delta_mag_corrected`.

### Comprobaciones hechas para esta revisión (2026-11-15, UTC)

- **Rebuild de los dos presets** en el scratch, con caché vacío (comandos de arriba). IRSA respondió 502 en SIA
  y TAP, y usó el snapshot.
- **14:18–14:20, IRSA SIA en vivo** (`use_cache=False`, `use_snapshot=False`, deadline de 120 s): RW Aur D1, 56 frames
  con y sin `mjd_max`; R Dra, 539 (dr1 413 + qr3 126, máximo MJD 61237,87). Mismos conjuntos de frames que los
  productos.
- **Listado del bucket S3** (`qr3/level2/`): las semanas más nuevas, 2026W38–W40, se subieron entre el 2026-10-25 y el
  2026-10-30. Para estas posiciones no hay frames posteriores a los publicados.
- **VizieR CfA:**
  - `B/gcvs`: R Dra M, P 245,6 d; RW Aur IT, V 9,2–12,5.
  - `B/vsx`: R Dra 246,12 d; RW Aur CTTS/ROT+CTTS, P 2,64 d.
  - `B/wds`: 05078+3024 JOY 5 A,BC 1,50″, PA 254° (2022), y GHE 16 BC 0,1″.
  - `I/355/gaiadr3`: par de RW Aur a 1,493″ y PA 254,4°; movimientos propios; contrapartes de las comparaciones.
- **Permutaciones** sobre los 450 puntos usados de R Dra: 0 de 1000 alcanzan el pico; semillas 1–5 con 100–400
  permutaciones, 0 excedencias.
- **HEAD** a las 594 URI de `provenance.sources`: todas responden 200.
- **URL pública de #84:** `GET /api/lightcurves` lista los dos productos, y la página de R Dra muestra el panel con «450 of
  538 measurements used» y «Archive selection: partial · cached search», sin las notas (LC1). Arriba sigue el texto de
  `fields.toml` con «period ~247 d… ~2,500 frames» (LC6).

**No verificado:** el ciclo AAVSO contemporáneo de R Dra (se tomó del registro). Por qué la huella publicada no se
reproduce: probablemente se construyó desde la rama previa al squash o con otras dependencias, pero no se puede
confirmar.


## V18 y LC24 restante — implementación WS3 (15/11/2026)

Se parte del trabajo de **faricool54**: #93 (algoritmos LC7/LC23–29), #94/#95 (productos republicados)
y #97 (notas, floors y selección en UI). Las tablas anteriores son revisiones fechadas de las versiones
que citan: no implican que aún falten esos cambios. No se reemplazan sus algoritmos ni sus resultados.

### Temperatura y color desde espectros

`science.continuum.estimate_temperature(points)` ajusta un cuerpo negro **F_nu** (mJy), con escala positiva
libre a 2 µm, grilla logarítmica 300–20000 K y perfil de chi-cuadrado. Es **temperatura de color del continuo**,
no Teff de atmósfera estelar, temperatura de equilibrio, radio, masa ni RGB. La escala no se convierte en tamaño.
La ley y la convención por Hz se cotejaron con [Astropy BlackBody](https://docs.astropy.org/en/stable/modeling/physical_models.html#blackbody);
los tests generan sus referencias independientemente con ese modelo, no con la función del ajuste.

Controles deliberados, no umbrales validados como calibración de SPHEREx:

- Errores positivos/finítos, S/N ≥ 3 y flujos positivos. Nada de convertir negativos o cotas en detecciones.
- ≥ 6 grupos espectrales y alcance en λ ≥ 2×. Agrupación de repeticiones en 2,5 %; piso de modelado supuesto
  del 5 % por grupo, que no se reduce artificialmente al repetir un frame. Incluye dispersión de las repeticiones.
- Con más del 20 % de entradas rechazadas, sin corrección de apertura o calidad insuficiente, no informa temperatura.
- Rechaza chi² reducido > 5, intervalos que alcanzan los límites de búsqueda o amplitud del intervalo > 50 % de T.
- El intervalo de Δchi²=1 es **condicional al modelo y al piso supuesto**; no es incertidumbre astrofísica total.
- `spectra.interpret_spectrum` separa temporadas: jamás entrega una temperatura global de una fuente variable.
  Una temporada agrupa huecos ≤30 días; no prueba simultaneidad ni constancia dentro de ese intervalo.
- Cubos MJy/sr sin sustracción local de fondo/errores no se ajustan como espectro de una estrella. La guía de
  [IRSA para visualización](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/visualization.html) distingue
  el drill de una extracción fotométrica con fondo/PSF. El adaptador devuelve `unsupported_product`.

`color_class` describe la mediana F_nu(4–5 µm) / mediana F_nu(1–2 µm), con ≥3 grupos por ventana:
<0,25 `star-like`; <1 `neutral`; <4 `red`; ≥4 `very-red`; sin cobertura/calidad, `unknown`.
Son categorías de visualización declaradas, **no clases estelares calibradas ni color visible**. La extinción,
los discos, las bandas moleculares, la mezcla y la variabilidad pueden cambiar ese cociente.

La CLI `errante position-spectrum --json` agrega `interpretation` por temporada a su producto científico
interno, y el modo texto explica estados/límites. No cambia `SpectrumResponse`, `Fact`, schema ni versión 0.7.0.
`interpret_measurements` e `interpretation_notes` permiten mostrar el resultado en las notas existentes de
la API; el consumo físico por WS7 exige mantener la procedencia y estas limitaciones, sin copiarlo como Teff.

**Comprobación real de rechazo:** 40 exposiciones nativas de ε Ind B, 35 utilizables, seguimiento con el
movimiento propio J2000 del preset, `max_frames=40`. IRSA SIA/TAP agotó el plazo: se usó el snapshot de búsqueda
2026-11-14 y se descargaron los FITS de S3 (0 fallos de extracción). El muestreo acotado produjo cinco grupos
separados por huecos; no implica cinco temporadas completas del archivo. No se informó temperatura en ninguno:
calidad/cobertura/censura o ajuste malo (chi² reducido ~131 y ~78 en dos de los grupos con cobertura suficiente).
El espectro molecular de Ba+Bb sin resolver no se convierte en una Teff de cuerpo negro. Fixture reproducible
sin red: `pipeline/tests/fixtures/ws3/continuum/eps-indi-b.json`. No es nueva aprobación humana de R05.

### Identidad de RW Aur: trabajo de faricool54, PR #101

Farid publicó #101 mientras se preparaba esta implementación. Se retiraron de esta rama los cambios
propios de identidad y sus tests para evitar duplicarlo: `context.py` permanece igual a main de base.
#101 conserva el nombre crudo de SIMBAD, cambia el nombre visible según WDS y avisa que SPHEREx mide
el sistema sin resolver. Su estado de merge/deploy se verifica por separado; no se presenta como incluido aquí.
[Dodin et al. 2020, p. 2](https://arxiv.org/pdf/2007.12559) identifica B con Gaia DR2 156430822114424576;
[Kurtovic et al. 2024](https://arxiv.org/html/2407.18828v1) da RUWE ~16 para A y ~1,5 para B. Estas fuentes
respaldan la revisión ya escrita en §0.3; no justifican atribuir la fotometría mezclada a un componente.

### LC24: dos puntos no son dos muestras de dispersión independientes

Un bin de dos exposiciones fuerza dos valores opuestos que proceden de **una** diferencia. Se conservan
ambos para la curva y el análisis de pares, pero se excluyen del resumen de dispersión por exposición.
Si no quedan bins con ≥3 exposiciones, `summary.n=0` y `scatter_over_control=null`; una nota lo explica.
No cambia los flujos, magnitudes relativas ni pares medidos. El control de pares publicado por #93 sigue siendo
la referencia para pares en apertura. Los productos ya empaquetados necesitan rebuild WS4 para reflejar el
resumen nuevo; no se presentan como regenerados por este PR. LC23 estructurado y otros cambios de modelo
requieren contrato separado. P2 (SkyBoT/JPL/Planeta X) y la aprobación humana R05 permanecen fuera de este cierre.
