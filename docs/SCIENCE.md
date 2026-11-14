# Ciencia mínima para el equipo

Dueño: **WS3**. Lectura obligatoria para WS2, WS3 y WS5; recomendada para todos (sirve para el pitch).
Hechos de datos y servicios: [`DATA.md`](DATA.md). Plan y prioridades: [`PLAN.md`](PLAN.md).

Etiquetas: ✅ verificado 2026-11-14 · 🧮 cálculo nuestro sobre datos ✅ (se indica el método) · 📄 según
documentación o literatura, sin verificar por nosotros · ❓ abierto o INFERIDO.

## 0. Los 5 objetivos oficiales

El enunciado pide probar la herramienta con estos cinco ([`CHALLENGE.md`](CHALLENGE.md)). Tres **se mueven**
(movimiento propio) y dos **cambian de brillo** (variables). **Ninguno se mueve más de ~2 píxeles SPHEREx** en todos
los datos que hay hoy (DR1 + QR3).

### 0.1 Astrometría de referencia

✅ Sesame/SIMBAD en CfA, 2026-11-14 (CDS Estrasburgo está degradado). ICRS, **época de referencia J2000.0**,
`µα*` = µα·cos δ. Está copiada en los comentarios de `pipeline/errante/config/fields.toml` para no depender de
SIMBAD en vivo.

| `id` (fields.toml) | Objetivo | Tipo | J2000 (°) | J2000 (sexagesimal) | µα*, µδ (mas/año) | plx (mas) |
|---|---|---|---|---|---|---|
| `barnards-star` | Barnard's Star | enana roja M4V, el mayor movimiento propio | 269.45207696, +4.69336497 | 17h57m48.498s +04°41′36.11″ | −801.551, +10362.394 | 546.976 |
| `eps-indi-b` | ε Indi B (Ba+Bb) | par de enanas marrones T1V+T6V que orbita ε Ind A | 331.04414659, −56.7828442 | 22h04m10.595s −56°46′58.24″ | +3981.977, −2466.832 | 270.658 (Gaia DR3) |
| `wise-0855` | WISE 0855−0714 | enana marrón Y2 | 133.81890825, −7.247048 | 08h55m16.538s −07°14′49.37″ | −8123.7, +673.2 | 439.0 |
| `rw-aurigae` | RW Aurigae | estrella T Tauri (K1/5e+K5e), variable irregular | 76.95652603, +30.40143817 | 05h07m49.566s +30°24′05.18″ | +7.23, −20.33 (Hipparcos) | 15.42 (Hipparcos); Gaia DR3: A 6.406, B 5.454 |
| `r-draconis` | R Draconis | variable Mira (M4.5–6e), P ≈ 247 d | 248.16761083, +66.75497942 | 16h32m40.227s +66°45′17.93″ | −20.643, +6.149 | 1.2509 |

### 0.2 Qué esperar en los datos SPHEREx

✅ Cobertura: SIA2 sobre `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3` y `spherex_qr3_deep` (detalle por
temporada y detector en [`DATA.md`](DATA.md) §4.2). 🧮 Posición: propagación lineal desde J2000 con el movimiento
propio hasta la **época media** de los frames; es el centro que usa `fields.toml`. 🧮 Desplazamiento: |µ| × (último
frame − primer frame); píxel = 6,15″.

| Objetivo | Época media | 🧮 Posición a la época media (°) | Línea de base | 🧮 Desplazamiento total | Frames | Temporadas | 🧮 Lat. eclíptica |
|---|---|---|---|---|---|---|---|
| Barnard | MJD 61104 (2026.17) | 269.44623, +4.76870 | 1,10 años | 11,5″ = **1,86 px** | 358 | 3 | +28,2° |
| ε Ind B | MJD 61042 (2026.00) | 331.09665, −56.80066 | 1,44 años | 6,7″ = **1,10 px** | 460 | 4 | −41,5° |
| WISE 0855 | MJD 61035 (2025.99) | 133.75980, −7.24219 | 1,02 años | 8,3″ = **1,36 px** | 258 (solo DR1) | 3 | −23,6° |
| RW Aur | MJD 61107 (2026.18) | 76.95659, +30.40129 | 1,04 años | 0,02″ ≈ **0 px** | 335 | 3 | +7,5° |
| R Dra | MJD 61115 (2026.20) | 248.16723, +66.75502 | 1,43 años | 0,03″ ≈ **0 px** | 2493 (1954 deep) | cobertura casi continua | +81,4° |

Cómo leer esto:

- Por año: Barnard ~1,7 px, WISE 0855 ~1,3 px, ε Ind B ~0,8 px. La PSF tiene FWHM ≈ 7,5″ ≈ 1,2 px (D1): el
  desplazamiento total es del orden de un ancho de PSF. **A escala nativa no se ve nada**: hacen falta zoom
  pixelado, retícula, posición predicha en cada época y resta de temporadas (aparece un dipolo +/−).
- Paralaje: amplitud = plx ≤ 0,55″ (≤ 0,09 px). Despreciable frente al movimiento propio.
- La propagación lineal ignora la aceleración de perspectiva (~0,4″ en 26 años para Barnard): despreciable.
- Una sola exposición de RW Aur o R Dra "parpadea" en brillo aunque la estrella no cambie: ver §3.2.

### 0.3 Notas por objetivo

- **Barnard's Star.** Muy brillante en el infrarrojo (K = 4,5): ❓ puede saturar (bits `OVERFLOW`/`NONLINEAR`).
  Es la prueba de cordura principal y el plan B del video. Gaia DR3 4472832130942575872 (época 2016.0) coincide con
  SIMBAD propagado ✅. El centro anterior de `fields.toml` (2025.5) estaba a 1,0″ de la propagación con Gaia.
- **ε Indi B.** SIMBAD no tiene entradas separadas para Ba y Bb ✅: **SPHEREx no separa el par** con píxeles de
  6,15″ (verá una sola fuente; conviene decirlo en la UI). **ε Ind A**, brillante, está a **~402″ (~6,7′) al oeste**
  ✅: entra en un FOV ≥ ~14′ y es un buen ejemplo de flags de contaminación (GHOST/HALO/BLOOM, ❓ INFERIDO).
  Cobertura despareja: D1/D4 tienen 3 frames en la 1.ª temporada y 0 en la última ✅. Gaia DR3 6412596012146801152,
  G = 18,03; J = 11,9, H = 11,3, K = 11,2 ✅.
- **WISE 0855−0714.** La coordenada del enunciado (08h55m10.831s −7°14′42.53″ = 133.79513, −7.24515) es de época
  **~2010** (🧮 retro-propagación: 2010,45 por RA, 2010,16 por Dec). A la época media de los datos el objeto está
  **~126″ (~20 px) al oeste** de esa coordenada (🧮; entra en un FOV ≥ ~8′ centrado en la del enunciado). Está a
  ~2,3 pc (plx 439 mas). Es extremadamente rojo: J = 25,0 y H = 23,8 (SIMBAD), W1 = 16,23 y W2 = 13,70 (AllWISE,
  Vega) ✅ → **probablemente solo visible en coadds de D5/D6 — INFERIDO, hay que medirlo** antes de elegirlo para el
  video. No tiene frames en QR3 ✅. CatWISE (`catwise_2020` en IRSA TAP) lo lista con pmRA ≈ −7,9 a −8,0″/año ✅.
- **RW Aurigae.** T Tauri (SIMBAD: `TT*`, sin período) ✅: **no se mueve, cambia de brillo** de forma irregular.
  J = 8,4, K = 7,0. La paralaje de Hipparcos (15,42 ± 3,69 mas) no coincide con Gaia DR3 (A: 6,406 mas ≈ 156 pc;
  B: 5,454 mas): usar Gaia. Latitud eclíptica +7,5°: pueden cruzar asteroides (SkyBoT, P1). Con 3 temporadas hay 3
  puntos de comparación por detector.
- **R Draconis.** Mira con período ≈ 247 d (Gaia DR3: 247,2 d; otras fuentes de SIMBAD: 247,0 y 246,0 d) ✅. A
  8,6° del polo eclíptico norte, tiene 2493 frames (1954 de las colecciones deep) y cobertura casi continua entre MJD
  60916 y 61310 ✅. 🧮 La línea de base (520 d) cubre ~2,1 ciclos: **el mejor caso para una curva de luz**. D2/D5
  tienen solo ~89 frames contra ~580 de los otros detectores. ❓ Puede saturar.

## 1. ¿Por qué se mueven las cosas en el cielo?

Las estrellas están tan lejos que, en meses, casi no se mueven, salvo las muy cercanas (*movimiento propio*: Barnard
10,4″/año, §0). Los objetos del Sistema Solar se mueven por dos razones:

1. **Su propio movimiento orbital** (un objeto a r UA va a ≈ 29,8/√r km/s).
2. **El movimiento de la Tierra/SPHEREx** (29,8 km/s), que produce un desplazamiento aparente (paralaje)
   inversamente proporcional a la distancia.

### SPHEREx mira a ~90° del Sol (📄; ❓ verificar con `SPS_ELON` y la fecha de cada frame)

SPHEREx observa en círculos perpendiculares a la dirección del Sol (como WISE). En la eclíptica a 90° del Sol, la
Tierra se mueve **a lo largo de la línea de visión**, así que el paralaje *dentro de una visita* casi desaparece y
los objetos lejanos se ven **casi quietos durante horas**. Entre pasadas separadas ~6 meses, en cambio, la Tierra
está del otro lado de su órbita → **desplazamientos enormes** por paralaje.

Órdenes de magnitud (🧮 órbitas circulares coplanares; píxel SPHEREx = 6,15″; K = 147,8″/h):

| r [UA] | ejemplo | en oposición ["/h] | a ~90° del Sol ["/h] | a ~90° [px/día] | entre pasadas (6 meses), solo paralaje | ídem con el movimiento orbital |
|---|---|---|---|---|---|---|
| 2,7 | cinturón principal | 34 | ~33 | ~130 | otro lugar del cielo | otro lugar del cielo |
| 5,2 | troyanos de Júpiter | 20 | ~12,5 | ~49 | otro lugar del cielo | otro lugar del cielo |
| 30 | Neptuno / Plutinos | 4,2 | 0,90 | 3,5 | ~2240 px | ~1600 px |
| 45 | Makemake / KBO clásico | 2,9 | 0,49 | 1,9 | ~1490 px | ~1140 px |
| 100 | disco disperso | 1,3 | 0,15 | 0,58 | ~670 px | ~565 px |
| 500 | tipo Planeta Nueve | 0,28 | 0,013 | 0,05 | ~134 px | ~125 px |
| 800 | Planeta Nueve lejano | 0,18 | 0,0065 | 0,025 | ~84 px | ~79 px |

Fórmulas:
- Oposición: `≈ K·(1 − 1/√r)/(r − 1)` (implementada en `errante.science.motion`).
- A 90° del Sol: `≈ K·r^(−3/2)`. La fórmula anterior de este documento, `K/(√r·√(r² − 1))`, es una aproximación que
  solo difiere a r chico (35,9 contra 33,3″/h a 2,7 UA; 12,7 contra 12,5″/h a 5,2 UA).
- Entre pasadas: solo paralaje `≈ 2 UA/r` rad. El movimiento orbital (prógrado) va en el mismo eje y resta:
  `≈ (2 − π/√r)/r` rad. La corrección es de ~40 % a 30 UA y de ~8 % a 500 UA.

Consecuencias (alineadas con [`PLAN.md`](PLAN.md)):
- **Asteroides**: se mueven mucho **dentro de una temporada** (horas–días). Es el caso del modo "exposiciones
  individuales" (P2: un campo eclíptico con un asteroide conocido, identificado con SkyBoT/SBIdent). La detección y
  el linking automáticos quedan en DROP.
- **TNOs**: ~0,6–3,5 px/día a 90° (30–100 UA) → hacen falta exposiciones del mismo campo separadas por ≥ 1 día.
  No es objetivo del reto.
- **Un Planeta Nueve**: casi quieto dentro de una visita y saltando ~100 px entre pasadas. Buscarlo requiere
  *shift-and-stack* sobre órbitas hipotéticas: DROP (§2).
- **Distancia "por velocidad en oposición"** (`motion.py`): aplicada a la geometría de ~90° **sobreestima ×3** (✅
  3,04″/h da 42 UA con la fórmula de oposición y 13 UA a 90°). DROP en el plan; si queda algo en la UI, ocultarlo.

## 2. Planeta X: motivación narrativa, no entregable

- El título del reto es la **motivación**. El entregable es el visor "RA/Dec → video" probado con los 5 objetivos
  (§0). Región del Planeta Nueve, shift-and-stack, inyección-recuperación y página de límites: **DROP**.
- Números citables (✅ abstract de arXiv 2108.09868; Brown & Batygin 2021, AJ 162, 219): masa 6,2 (+2,2/−1,3)
  masas terrestres, semieje a = 380 (+140/−80) UA, inclinación 16 ± 5°, perihelio q = 300 (+85/−60) UA.
  🧮 Con las medianas, afelio Q = 2a − q ≈ 460 UA.
- ✅ Brown, Holman & Batygin 2024 (AJ 167, 146; arXiv 2401.17977), búsqueda con Pan-STARRS1: excluye el 78 % del
  espacio de parámetros de 2021; lo que queda está mayormente en **V > 21**.
- ❓ "V ≈ 20–23" (versión anterior de este documento) **no aparece en el abstract: verificar** antes de usarlo en la
  UI o el pitch. La fila de 800 UA de la tabla de §1 queda fuera del rango ~1σ (INFERIDO); úsenla solo como ilustración.
- `science/planet_x.py` dice "~400–800 AU, V ~ 21–25": inconsistente con lo de arriba. Unificar si se toca (P2).
- No medimos la profundidad de SPHEREx para objetos así y no lo vamos a hacer (DROP): **no prometer nada**.

## 3. Espectros y variabilidad con un filtro lineal variable

### 3.1 Lo que SPHEREx sí hace genial: espectros

Cada detector tiene un filtro lineal variable (LVF): cada punto del detector ve una longitud de onda distinta. Hay
6 detectores × 17 canales = **102 bandas** de 0,75 a 5 µm ✅. Un objeto observado varias veces junta un **espectro
0,75–5 µm** gratis:
- **asteroides**: luz solar reflejada; banda de hidratación ~3 µm en algunos tipos.
- **enanas marrones frías**: muy rojas, absorción de metano ~3,3 µm, brillantes en 4–5 µm (WISE 0855: J = 25 pero
  W2 = 13,7).
- **estrellas**: caen hacia longitudes de onda largas.

Espectro al vuelo (kudos extra del reto): por cada exposición, λ en la posición del objetivo (tabla `WCS-WAVE`,
[`DATA.md`](DATA.md) §2.4) + fotometría de apertura sobre `IMAGE − ZODI` → un punto (λ, flujo). Con las ~17–25
exposiciones por detector y temporada sale un espectro por temporada. Unidades: `IMAGE` está en MJy/sr; con
`OMEGA_MEDIAN` ≈ 37,9 arcsec², 1 MJy/sr en un píxel ≈ 0,89 mJy (constante de `science/spectra.py`, ✅ recalculada).
Ojo: `em_min/em_max` de la búsqueda son el rango del detector entero, no la λ en el objetivo.

### 3.2 Variabilidad con un filtro lineal variable

**Por qué el brillo de exposiciones sueltas no sirve.** En cada exposición el objetivo cae en otro lugar del
detector y se mide en **otra λ**. Como el espectro de una estrella no es plano (y la PSF cambia con λ), su brillo
cambia de exposición a exposición **aunque la estrella sea constante**. Un video de exposiciones individuales
"parpadea" y no permite distinguir variabilidad de color. Además, el PNG no es una medida: el stretch actual satura
las fuentes brillantes (✅ un cambio ×2 de la estrella central da el mismo pico 255).

**Método** (❓ INFERIDO, a validar con datos; los hechos que lo sostienen son ✅):

1. **Coadds por temporada × detector** (frame por defecto del video). En cada temporada cada detector junta
   ~17–25 exposiciones del objetivo (Barnard, RW Aur ✅), del orden de sus 17 canales. Cada coadd promedia
   aproximadamente el mismo rango de λ, así que **los coadds de temporadas distintas son comparables**: lo que cambia
   entre ellos es movimiento o brillo real. Peso 1/`VARIANCE`, `IMAGE − ZODI`, y el **mismo stretch por detector en
   todas las temporadas** ("modo fijo"). Cuidado con la cobertura despareja (ε Ind B en D1/D4, la 1.ª temporada de
   WISE 0855): mostrar `n_inputs` y el rango de λ de cada coadd (campos propuestos en el contrato 0.3.0).
2. **Espectro por temporada.** Puntos (λ, flujo) coloreados por temporada. Una estrella constante superpone sus
   espectros; una variable los desplaza (o les cambia la forma). Las **estrellas de comparación** del mismo campo
   tienen que superponerse: son el control de calibración.
3. **Curva de luz corregida por λ.** Para cada exposición, `flujo / espectro medio del objetivo interpolado en esa λ`,
   graficado contra MJD por detector y normalizado con estrellas de comparación (mismo campo, brillo parecido, no
   variables). R Dra: cobertura densa, ~2 ciclos → curva de luz real. RW Aur: 3 temporadas → 3 puntos por detector
   (variabilidad irregular, sin período).
4. **Cuidados.** Saturación (`OVERFLOW`/`NONLINEAR` en el objetivo, ❓), flags de vecinas brillantes
   (GHOST/HALO/BLOOM), apertura acorde a la PSF de cada frame (`PSF_FWHM` cambia por detector). Los pares D1/D4,
   D2/D5 y D3/D6 se toman a la vez ✅: dan color simultáneo.

En la UI conviene distinguir "exposiciones individuales (el brillo cambia por λ)" de "coadds por temporada
(comparables)".

## 4. Encuadre honesto (para UI, pitch y entrega)

- "Planeta X es nuestra motivación científica, no un resultado prometido."
- Mostramos **datos SPHEREx reales** de los 5 objetivos. Su movimiento es de 1–2 píxeles: se hace visible con zoom,
  posición predicha y resta, **sin exagerarlo**. Los datos sintéticos (`data/demo`) exageran el movimiento propio
  (~120″/año) a propósito y siempre llevan el badge de sintético.
- Estados de un candidato (si la detección llega a existir, P2): `known` (coincide con catálogo), `unconfirmed` (sin
  match: puede ser artefacto, error de medición u objeto no catalogado), `artifact` (rechazado por validación),
  `injected` (simulado).
- Mostrar siempre, por frame o coadd: fecha y Δt real, detector y rango de λ, cuántas exposiciones entran, flags en el
  objetivo. Para candidatos: cuántas detecciones, residuo del ajuste y flags tocados.
- Validar con objetos conocidos: medir el desplazamiento observado contra el predicho (1,86 / 1,36 / 1,10 px en
  Barnard, WISE 0855 y ε Ind B) y la variabilidad de R Dra (tabla "esperado vs medido", tarea WS3-5). Solo se
  publican números medidos.
- Créditos de datos solo en texto; nada de branding NASA (reglas en [`CHALLENGE.md`](CHALLENGE.md)).

Números correctos para los textos (UI y pitch; la redacción final es del equipo):
- La mayoría de las estrellas parecen fijas; las más cercanas se desplazan: Barnard ~10,4″/año (~1,7 px SPHEREx por año).
- Un objeto tipo Planeta Nueve a 500 UA se movería ~0,3″/h en oposición y ~0,013″/h a 90° del Sol (no "unos
  segundos de arco por hora").
- SPHEREx: cielo completo cada ~6 meses (📄), 102 bandas entre 0,75 y 5 µm, píxel de 6,15″.

## 5. Glosario rápido

**Exposición**: 1 archivo, 1 detector (~114 s). **Visita**: exposiciones separadas por menos de 6 h.
**Temporada / pasada**: bloque de visitas separado del siguiente por más de ~20 días; SPHEREx vuelve a cada punto
cada ~6 meses (umbral exacto: ❓ [`DATA.md`](DATA.md) §4.2). **Coadd**: suma ponderada de varias exposiciones
reproyectadas a una grilla común. **LVF**: filtro lineal variable (la λ cambia a lo largo del detector).
**MJD**: fecha juliana modificada (días); usar `MJD-AVG`, el punto medio de la exposición. **RA/Dec**: coordenadas
ecuatoriales (grados). **Movimiento propio (pm)**: desplazamiento angular de una estrella por año (mas/año; µα* =
µα·cos δ). **Paralaje (plx)**: oscilación anual por el movimiento de la Tierra; 1000/plx[mas] = distancia en pc.
**Época de referencia**: fecha a la que corresponde una posición de catálogo (J2000.0, o 2016.0 en Gaia DR3).
**Mira**: gigante roja pulsante de período largo. **T Tauri**: estrella joven, variable irregular. **PA**: ángulo de
posición, desde el norte hacia el este. **UA**: distancia Tierra–Sol. **TNO/KBO**: objeto transneptuniano / del
cinturón de Kuiper. **Blink comparator**: alternar imágenes de distintas fechas para ver qué cambia (así se descubrió
Plutón en 1930). **Dipolo**: en una resta de épocas, par negativo/positivo que deja un objeto que se movió.
**Cutout**: recorte de una imagen. **HiPS**: formato de imágenes de todo el cielo por teselas (lo usa Aladin).
**Shift-and-stack**: sumar imágenes desplazadas según un movimiento supuesto para detectar objetos débiles.
