# Visión 3D: de un punto que se mueve a un sistema que se puede explorar

> Workstream **WS7**. Estado en `main`: `#/systems` y `#/system/<id>[/<cuerpo>]` andan con modelos 3D de los 5
> objetivos de prueba del reto + un sistema sintético (#1, #8, #9); cada propiedad visual sale de física y catálogo
> con su tier, el color SPHEREx IR es el modo por defecto, existe el modo **Dataset time** sobre las fechas reales de
> SPHEREx y el panel "Where SPHEREx should see it" (#47); los cinco sistemas están publicados en el dataset real
> (#64). Tareas en [tasks/WS7-3d-systems.md](../tasks/WS7-3d-systems.md).
> En la rama `ws7/measured-3d` (15/11, V13 con V4 y V12 de `PARALLEL_PLAN.md`, todavía sin PR): se quitan los
> valores elegidos a mano, lo que ninguna fuente da se dibuja como **desconocido**, se quita el toggle
> class-typical, una capa de mediciones (snapshots congelados del contexto de WS3 + registro `targets.toml`) agrega
> los facts "seen by SPHEREx" y los cruces de catálogo, y cada dato de la ficha muestra su **origen**. Detalle en
> [Capa de mediciones](#capa-de-mediciones-v13-snapshots-y-registro),
> [Derivaciones, niveles (tiers) y mapeos de visualización](#derivaciones-niveles-tiers-y-mapeos-de-visualización)
> y [Diferencias con `VISION.md`](#diferencias-con-visionmd-que-siguen-abiertas).

**Prioridad P1** (el 3D desde mediciones es parte central de la visión en [`VISION.md`](VISION.md); V13/V14 de
`PARALLEL_PLAN.md`), siempre después del recorrido obligatorio RA/Dec → imágenes reales → animación y ensayos.
Las guías de entrega y evaluación exigen evidencia, honestidad y atribución: `REQUIREMENTS.md`,
`SUBMISSION_GUIDE.md` y `JUDGING_GUIDE.md`. La galería no valida R02/R05 ni aporta por sí misma integración real
de datos NASA para Relevance. El código llegó en la contribución WS7; los parámetros se contrastaron con catálogos
y papers en WS7-2 (2026-11-14, con asistencia de IA); falta la revisión humana del equipo. Uso de IA de WS7:
`pipeline/errante/systems/ai-usage.json` y `frontend/src/three/ai-usage.json` (Claude Code; revisión de DankoLiv
en curso, no terminada).

## La idea

SPHEREx muestra los objetos como **puntitos** que se mueven o cambian de brillo entre imágenes. Eso es lo que
pide el reto y es la base (blink / flip-book). Nuestra capa extra: **cada objeto que seguimos se puede abrir en
3D** para entender qué es y cómo evoluciona.

1. **Ver el objeto en 3D.** Estrella, enana marrón, planeta, asteroide: un modelo cuyo tamaño y color salen de sus
   datos (radio, temperatura efectiva → color de cuerpo negro, tipo de cuerpo). Lo que ningún dato da se muestra
   como desconocido (gris, tamaño de marcador fijo), nunca con un valor inventado; no se dibujan bandas, nubes ni
   cráteres que nadie midió. Cuando exista un modelo de forma real (p. ej. asteroides con forma por radar/curvas
   de luz), se usa ese.
2. **Ver el sistema animado.** Si el objeto es parte de un sistema (estrella con planetas, binaria, enana marrón
   compañera, asteroide alrededor del Sol), se arma el sistema con **órbitas keplerianas** de catálogo y se anima
   en el tiempo: velocidad ajustable, pausa, distancias comprimidas o en proporción real.
3. **Entrar a cada cuerpo.** Clic en un planeta/estrella → la cámara vuela hasta él y lo sigue; se abre su
   **ficha** con datos, unidades y fuente de cada valor. Cada cuerpo tiene URL propia
   (`#/system/barnards-star/barnard-b`), así se puede compartir o embeber.
4. **Volver al cielo real.** Desde el sistema se salta al **campo SPHEREx** donde se observa (y viceversa: la
   página de un campo ofrece "Explore these objects in 3D"). Un candidato del pipeline puede enlazarse a su cuerpo
   3D (`Body.candidate_id`).

### Prioridad de diseño

Buena representación y buen diseño: fondo de cielo oscuro, colores físicos (no arbitrarios), etiquetas
clickeables, transiciones suaves de cámara, panel lateral legible y que funcione en celular.

## Honestidad (reglas que no se negocian)

- Es una **representación de modelo, no una imagen**. La UI muestra siempre el badge **"3D MODEL · NOT AN IMAGE"**
  y la nota `representation_note`: tamaños exagerados, distancias opcionalmente comprimidas.
- Cada dato de la ficha es un `Fact` con `source` y `verified`. Si no se verificó contra la fuente, la UI lo marca
  **"unverified"** y el sistema muestra el badge **"UNVERIFIED VALUES"**. Desde WS7-2 (2026-11-14) los valores
  de los cinco blancos están contrastados con NASA Exoplanet Archive, SIMBAD (espejo CfA), Gaia DR3, VizieR y los
  papers citados. Desde V13 (rama `ws7/measured-3d`) el único `Fact` "unverified" de un blanco real es un valor
  derivado por WS7: el radio de RW Aur A, ~1.3 R☉, desde la luminosidad de Herczeg & Hillenbrand 2014 llevada a la
  distancia Gaia (por eso RW Aur sigue con el badge). El radio de R Dra y su masa class-typical ya no existen.
- **Origen de cada dato** (V13, `frontend/src/three/factOrigin.ts`, sin campo nuevo en el contrato): la ficha pone un
  chip en cada `Fact`. **"SPHEREx-measured (offline)"** si `Fact.source` empieza con "SPHEREx" (los facts "seen by SPHEREx" del
  bloque A5 de `SCIENCE.md`, copiados de los registros de validación: análisis offline de los FITS, revisión humana
  guiada el 2026-11-15, sin volver a correr los análisis); **"derived"** si la etiqueta contiene "(derived" (la fuente dice desde qué); **"catalog, not measured
  by SPHEREx"** para el resto con fuente (Gaia DR3, SIMBAD, VSX, NASA Exoplanet Archive, papers); **"no source
  given"** si un fact real no trae fuente (hoy ninguno, y nunca se lo llama catálogo); y **"synthetic demo"** para todo
  fact del sistema sintético (`provenance.synthetic`), diga lo que diga su fuente. No existe todavía
  ningún valor dibujado que salga de SPHEREx: el ajuste de temperatura del espectro (V18) es de WS3 y no está hecho.
- **Lo que ninguna fuente da no se dibuja como si se supiera** (`VISION.md`): una estrella o enana marrón sin
  `teff_k` va en **gris neutro** con "colour unknown (no single temperature adopted)"; un cuerpo sin `radius_km` va con
  un **tamaño fijo de marcador**, sin escalar, y la etiqueta "size unknown · not to scale" (no se usa el contorno
  punteado: ya significa "solo tono cualitativo en IR"). La ficha del cuerpo muestra **la razón propia de ese cuerpo**
  (la lee de la nota "Not measured, so not drawn" con `unknownReasons()`; el texto genérico queda solo de respaldo), y
  las leyendas no describen un cuerpo negro ni un oscurecimiento al borde que ningún cuerpo del sistema recibe (R Dra).
  Cada sistema dice en `provenance.notes` qué quedó sin
  medir y por qué ("Not measured, so not drawn (shown as unknown): …"); esos huecos no se agregan como `Fact`
  "unknown", para no encender el badge UNVERIFIED VALUES.
- Lo que no sabemos no se dibuja como si lo supiéramos: cada órbita declara `Orbit.quality`. `assumed` (no
  ajustada: un círculo a la separación proyectada o a una distancia estimada) se dibuja **en amarillo** y la ficha
  dice "assumed, not fitted"; `hypothetical` (p. ej. Planeta Nueve) en violeta. Las fases sin época son
  arbitrarias: en *Free-running* el visor muestra tiempo transcurrido, no una fecha "predicha"; en *Dataset time*
  esos cuerpos se atenúan, llevan "(phase unknown)" y un anillo en lugar de una posición (ver
  [Tiempo del dataset](#tiempo-del-dataset-spherex-2025-04--2026-11)).
- Superficies: **esferas lisas** con color de cuerpo negro y oscurecimiento al borde, como pide
  [`VISION.md`](VISION.md) ("lo que no se midió no se dibuja"). Desde V13 no hay rasgos típicos de clase en los
  blancos reales: se quitaron el toggle "show class-typical features (illustrative)", sus bandas en ε Ind Ab y Ba y
  las celdas de convección de R Dra (resolubles según el modelo, pero no observadas en esta estrella). Tampoco se
  dibuja el cambio de tamaño de R Dra (±10 % class-typical): su radio es constante.
- Lo sintético sigue llevando el badge **SYNTHETIC DATA** (`provenance.synthetic`) y conserva sus texturas
  procedurales: es una decoración rotulada, no un blanco real.
- Simplificaciones explícitas: jerarquías sin baricentros (Epsilon Indi), variabilidad sinusoidal en
  *Free-running* (solo R Dra tiene una curva asimétrica de efeméride, en *Dataset time*), radios estimados de
  planetas no transitantes. Cada una figura en `provenance.notes` o en la etiqueta del dato.

## Qué representan los modelos (verificados en WS7-2, 2026-11-14; sin valores elegidos a mano desde V13)

Cada valor se comprobó en la fuente y quedó en `catalog.py` con la cita exacta; `systems/sources.py` reproduce
las consultas y los tests `network` de `test_systems.py` las vuelven a correr. Posiciones y movimientos en la
época de la fuente (Gaia DR3 = J2016.0), no en J2000.

**Regla de qué se dibuja (V13).** Se dibuja un valor publicado para **este** objeto, medido o de modelo, rotulado como
tal (p. ej. los radios de Barnard b–e y ε Ind Ab estimados por el archivo desde la masa, o el radio de WISE 0855 de
modelos evolutivos). Un valor que ninguna fuente da no se dibuja: el campo queda en `null` y la UI lo muestra como
desconocido. La excepción declarada es un valor **derivado** por WS7 con un método de `VISION.md` (luminosidad +
distancia por Stefan–Boltzmann), rotulado "(derived …)" y "unverified". Con esa regla se quitaron en V13:

| Cuerpo | Valor quitado | Por qué | Qué queda |
|---|---|---|---|
| R Draconis | Teff 3000 K | elegido dentro del rango publicado; la Teff cambia con la fase | `teff_k = null` (color desconocido); el rango ~2000–3300 K queda como `Fact` (van Belle+2002, McDonald+2012) |
| R Draconis | radio 250 R☉ | valor ilustrativo: los tamaños publicados dependen de la distancia y la fase | `radius_km = null` (tamaño desconocido) |
| R Draconis | masa ~1 M☉ | class-typical para su período (Feast 2009), solo servía para las celdas de convección | `mass_kg = null` (no hay masa dinámica) |
| ε Ind Ba y Bb | radio 0.9 R♃ | ilustrativo, sin radio publicado y sin `Fact` | `radius_km = null` (tamaño desconocido) |
| WISE 0855−0714 | masa 5 M♃ | elegida dentro del rango 3–10 M♃ de modelos evolutivos | `mass_kg = null`; el rango queda como `Fact` (Luhman+2024) |

RW Aur A **conserva** su radio, ahora rotulado "Radius (derived from the catalog luminosity)": Herczeg & Hillenbrand
2014 dan 1.20 R☉ con su luminosidad a 140 pc; a la distancia Gaia DR3 de 156.1 pc la luminosidad escala con d² y, a
la misma temperatura, el radio con d: 1.20 × 156.1 / 140 = 1.34 R☉. Sigue "unverified". Hace falta porque la
fotosfera A+B con ese radio es la base de los números de V4 (exceso IR de 1.4, 1.9 y 2.8 mag). No se cambió ningún
otro valor dibujado (ni la Teff de ε Ind A ni distancias por precisión): los valores de Gaia o SIMBAD que difieren se
agregan como facts de cruce, rotulados "catalog, not measured by SPHEREx" (ver
[Capa de mediciones](#capa-de-mediciones-v13-snapshots-y-registro)).

| Objetivo | Qué se modela | Fuentes usadas | Correcciones respecto de los valores tipeados |
|---|---|---|---|
| **Barnard's Star** | M4V + 4 planetas (P 2.34–6.74 d, masa mínima 0.19–0.34 M⊕; órbitas circulares; fases desde el t0 de Basant+2025, Tabla 3) + rotación 145 ± 15 d | Exoplanet Archive (González Hernández+2024, Basant+2025), Gaia DR3 4472832130942575872, Toledo-Padrón+2019 | RV −110.47 km/s (Gaia DR3); centro y época → J2016.0; t0 leído como conjunción inferior (pendiente de revisión del equipo); nota de órbita circular con las e ajustadas (0.03–0.08) y el error de hasta 2e rad (3–9°) |
| **Epsilon Indi** | K5V + Ab (6.5 M♃, a 15.8 AU, e 0.25) + Ba/Bb (T1/T6, P 11.02 a, e 0.54; **tamaño desconocido**) | Exoplanet Archive (Sanghi+2026), Matthews+2024, Chen+2022, Scholz+2003, Gaia DR3 | Ab: el ajuste vigente (Sanghi+2026) reemplaza a Matthews+2024 (28 AU, e 0.4); masa de A 0.80; Teff 4700 K; A es "an orange dwarf star", no "Sun-like"; Ba+Bb son una sola fuente para Gaia y para SPHEREx (≤ ~1″ contra píxeles de 6.15″) |
| **WISE 0855−0714** | enana marrón aislada, ~285 K, ~Y4 (Kirkpatrick+2021; SIMBAD da Y2); masa sin valor único (rango 3–10 M♃) | Kirkpatrick+2021 (paralaje/movimiento), Luhman+2024 (JWST) | movimiento propio −8123.7/+673.2 mas/a; las coordenadas del enunciado son WISE All-Sky **época 2010.34**, no J2014 |
| **R Draconis** | Mira, P 245.6 d, V 6.7–13.2 (*Free-running*: seno ilustrativo del brillo; *Dataset time*: fase V fechada con los máximos AAVSO medidos dentro de la ventana SPHEREx y con la efeméride VSX fuera de ella); **color y tamaño desconocidos**, radio constante | GCVS 5.1, AAVSO VSX, Gaia DR3, Bailer-Jones+2021, van Belle+2002, McDonald+2012 | Teff como rango 2000–3300 K (cambia con la fase); se agregó movimiento (~790 pc); se quitaron la Teff dibujada, el radio ilustrativo y la masa class-typical (V13) |
| **RW Aurigae** | A (CTTS, 1.24 M☉, radio derivado ~1.3 R☉) + disco de polvo de 19 AU + B (K6.5, 1.0 M☉) en la órbita ajustada | Kurtovic+2024 (ALMA), Dodin+2020, Testi+2022, Herczeg & Hillenbrand 2014, VSX, Gaia DR3 | B tiene órbita publicada (a ~258 AU, e 0.79, P ~2800 a, muy incierta); **SIMBAD tiene invertidos los Gaia DR3 de A y B** (V15, corregido en la ficha de WS3 por #101; el snapshot es anterior) |
| Asteroides / TNOs del pipeline | órbita heliocéntrica real (elementos osculantes) + forma si existe | JPL SBDB, NASA 3D Resources, DAMIT | pendiente (WS7-3) |
| Planeta Nueve (P2, opcional) | órbita **hipotética** con `Orbit.quality = "hypothetical"` | Brown & Batygin 2021 (AJ 162, 219), a verificar | pendiente (WS7-7) |

Para WS3 (blancos): RW Aur A = Gaia DR3 156430817820015232 y B = 156430822114424576 (al revés que SIMBAD; ángulo
de posición WDS y Kurtovic+2024). Las coordenadas del enunciado para WISE 0855 son de 2010.34: hay que propagar
~8.2″/año. Detalle de cada consulta: `pipeline/errante/systems/catalog.py`.

Lo que **no** sale de SPHEREx: las órbitas y los parámetros físicos dibujados vienen de catálogos. SPHEREx aporta
*dónde está y cómo se mueve en el cielo*, su **espectro 0.75–5 µm** y su variabilidad. Los campos reales de los cinco
blancos existen (`data/products`, WS2) y los registros de validación (`docs/validation/`, revisión humana guiada el 2026-11-15, sin volver a correr los análisis)
midieron offline el movimiento, el ciclo y el cambio de brillo: el 3D los muestra en la ficha como facts "seen by
SPHEREx" (bloque A5 de `SCIENCE.md`), sin convertirlos en geometría. La curva de luz SPHEREx precomputada de R Dra y
de RW Aur la muestra el panel de la página del campo (`LightCurvePanel`, WS5, #83, en modo API), no el 3D. Las
fuentes de la tabla son destinos de verificación, no evidencia de parámetros correctos más allá de lo comprobado en
WS7-2.

## Cómo está armado

```
pipeline/errante/systems/       (WS7)
  catalog.py      capa de literatura: sistemas curados (verificados en WS7-2, con fuente por dato; lo que ninguna
                  fuente da queda en None) + sistema sintético del demo
  targets.toml    registro (V13): por sistema y cuerpo, qué snapshot usar, qué parámetros agregar como cruce de
                  catálogo y los facts "seen by SPHEREx" (textos de SCIENCE.md, bloque A5)
  inputs/objects/<slug>.json   snapshots congelados del contexto de objeto de WS3 (facts + parámetros numéricos)
  measured.py     capa de mediciones (V13): lee registro + snapshots, agrega facts y notas "Not measured, so not drawn"
  sources.py      NASA Exoplanet Archive, SIMBAD (CfA) y Gaia DR3 por TAP (urllib), para los tests network;
                  stubs: JPL SBDB, modelos de forma
  build.py        valida jerarquía (padres existen, sin ciclos) y escribe <root>/systems/<id>.json
  ai-usage.json   registro de uso de IA de WS7 (lado pipeline)
       │  errante demo  → data/demo/systems/*.json      errante systems --real-only → data/products/systems/*.json
       │  (--real-only: solo sistemas no sintéticos; se niega si <out>/systems ya tiene uno sintético)
       │  errante systems --explain: cuerpo, parámetro, valor, origen y razón · --record: re-graba snapshots (dev)
       ▼
contrato: SystemModel (models.py; V13 no cambia el contrato, 0.7.0 en main) · Manifest.systems · GET /api/systems/{id}
       ▼
frontend/src/three/             (WS7, three.js en un chunk aparte, carga diferida; casi todo con *.test.ts al lado)
  orbits.ts          Kepler (posición en el tiempo, elipse), orden padre→hijo, variabilidad sinusoidal
  astro.ts           núcleo físico: cuerpo negro, CIE 1931, L, log g, H_p, granulación, Teq, AB SPHEREx;
                     cada resultado es { value, tier, method, citation, flags }
  cie1931.ts         funciones de igualación CIE 1931 2° (5 nm)
  spherexBands.ts    bandas D1–D6, píxel 6.15″, onset de no linealidad (RECON §2.2)
  colorModes.ts      modos de color (SPHEREx IR por defecto, visible, D1–D6 en gris), glow, leyendas
  appearance.ts      color base, gate de superficies (solo el sintético), distancias comprimidas, radios
                     (sin radio: marcador fijo, sin escalar)
  factOrigin.ts      origen de cada Fact (SPHEREx-measured (offline) / derived / catalog) y textos de color y tamaño
                     desconocidos; sin astro ni three (va en el chunk principal)
  sceneLayout.ts     radios sin solapes, cámara, reloj, reglas de spin (radio constante: nada pulsa en tamaño)
  starMaterial.ts    shaders: limb darkening, contorno (rim)
  ephemerides.ts     Dataset time: t0/P de Barnard b–e, efeméride VSX de R Dra, por qué otras fases no se conocen
  spherexCoverage.ts ventanas de pasadas SPHEREx de los 5 blancos, agrupación de frames, línea "Real epoch"
  skyTrack.ts        trayectoria predicha en el cielo (movimiento espacial + paralaje)
  appearanceNotes.ts filas "How this body is drawn" / "At SPHEREx scale" de la ficha (carga diferida)
  DatasetTimeline.tsx, SkyTrackPanel.tsx   línea de tiempo y panel del cielo (React + SVG, carga diferida)
  viewerKit.ts       lo que el visor carga bajo demanda (leyendas, cobertura, efemérides)
  datasetGate.ts, viewerLink.ts, kindLabels.ts   piezas chicas sin astro/three (van en el chunk principal)
  ai-usage.json      registro de uso de IA de WS7 (lado frontend)
  SystemScene.ts     escena three.js: cuerpos, órbitas, arcos/anillos de fase, flecha "toward Earth", cámara
frontend/src/components/SystemViewer.tsx   controles (play, velocidad, reloj, modo de color, órbitas, etiquetas)
frontend/src/components/BodyPanel.tsx      ficha del cuerpo (datos + fuente + verified + chip de origen + cómo se dibuja)
frontend/src/pages/SystemsPage.tsx         #/systems
frontend/src/pages/SystemPage.tsx          #/system/<id>[/<cuerpo>] (+ panel "Where SPHEREx should see it")
```

Modelo de datos (resumen; la fuente de verdad es `pipeline/errante/models.py`):

- `SystemModel`: `id`, `name`, `center` (RA/Dec), `motion` (`SpaceMotion`: distancia, paralaje, movimiento propio,
  velocidad radial), `field_id` (campo SPHEREx), `bodies[]`, `representation_note`, `provenance`.
- `Body`: `id`, `kind` (star, brown_dwarf, planet, asteroid, tno, disk…), `radius_km`, `mass_kg`, `teff_k`,
  `spectral_type`, `orbit` (`Orbit`: padre, a, P, e, i, Ω, ω, M₀, época, `quality`, `note`; `null` = cuerpo raíz), `variability`,
  `appearance` (`star | brown_dwarf | rocky | icy | gas_giant | disk | mesh`, `mesh_url`), `facts[]`, `candidate_id`.

## Capa de mediciones (V13): snapshots y registro

Estado en la rama `ws7/measured-3d` (15/11). Objetivo: que cada valor del 3D diga de dónde sale y que sumar un blanco o
una medición nueva sea cargar datos, no escribir código. Hoy **ningún valor dibujado sale de SPHEREx** (no existe el
ajuste de temperatura del espectro, V18 de WS3); SPHEREx aparece como facts medidos offline, y Gaia DR3 / SIMBAD /
VSX / NASA Exoplanet Archive como valores de catálogo rotulados "catalog, not measured by SPHEREx" (decisión D7 de
`PARALLEL_PLAN.md`, pendiente de confirmar por el equipo).

**Piezas** (todo en `pipeline/errante/systems/`, WS7):

- `catalog.py`: la capa de literatura de cada sistema (valores publicados con su fuente, WS7-2). Lo que ninguna fuente
  da queda en `None`.
- `inputs/objects/<slug>.json`: **snapshots congelados** del contexto de objeto de WS3 (`errante.science.context`) para
  los nombres que cubren los fixtures de WS3: `barnards-star` ("Barnard's Star"), `eps-indi-b` ("eps Ind B"),
  `wise-0855` ("WISE J085510.83-071442.5"), `r-draconis` ("R Dra") y `rw-aurigae` ("RW Aur"). Cada uno guarda la
  consulta, `recorded_utc`, el origen (cómo se grabó, hora de cada servicio, sha256 de cada archivo de caché leído), la
  identidad (SIMBAD, tipo de match, fuente Gaia DR3), la astrometría Gaia, la variabilidad VSX, los planetas
  confirmados, los `Fact` del contrato que arma `physical_parameters` y los parámetros numéricos de
  `derive_parameters` (valor, intervalo, método, fuente, caveats, verified).
- `targets.toml`: el **registro**. `[snapshots]` mapea cada slug a su consulta de WS3; cada `[[system]]` /
  `[[system.body]]` dice qué snapshot describe a ese cuerpo, qué parámetros de WS3 se agregan como facts de cruce
  (`cross_check`, solo valores verificados), los facts medidos por SPHEREx (`spherex_fact`, textos literales del
  bloque A5 de `SCIENCE.md`, con fuente que empieza con "SPHEREx") y, para cada campo dibujado que queda
  desconocido (`teff`, `radius`, `mass`), **por qué** (`unknown`). El build falla si un campo queda desconocido sin
  razón. Un `snapshot` a nivel de sistema (`snapshot_keys`, `snapshot_note`) es para un contexto que no se puede dar a
  un solo cuerpo: ε Ind B es una sola fuente Gaia sin resolver (Ba+Bb), y en RW Aur el contexto describe el par A+B sin
  resolver y SIMBAD tiene invertidos los nombres A/B respecto del WDS (V15, corregido en la ficha de WS3 por #101; el snapshot es anterior). En esos dos casos los
  valores van solo a una nota del sistema, nunca a un componente.
- `measured.py`: la **capa de mediciones** (`apply_registry`). Lee registro y snapshots (solo JSON: sin red y sin
  código de WS3 en build ni en tests) y, al final de `Body.facts` para no cambiar el orden de los existentes, agrega a
  cada cuerpo sus facts "seen by SPHEREx" y los facts de cruce de catálogo: el `Fact` de WS3 tal como se grabó, con el
  sufijo " (via WS3 object context; catalog, not measured by SPHEREx)" en la fuente (p. ej. la Teff GSP-Phot de Gaia
  de Barnard, 3100 K, junto a los 3195 K publicados que se dibujan). En `provenance.notes` agrega la nota del contexto
  de sistema, una nota con los snapshots usados (consulta, horas de los servicios, "replayed offline from the WS3
  fixtures") y "Not measured, so not drawn (shown as unknown): <cuerpo>: <parámetro> (<razón>)", con la razón del
  registro, la de WS3 si la hay y, para temperatura y radio, que todavía no existe la ruta SPHEREx (V18 de WS3,
  WS7-8). No cambia ningún valor dibujado y nunca agrega facts "unknown" ni facts no verificados (encenderían el
  badge UNVERIFIED VALUES); si un `cross_check` no tiene valor verificado en el snapshot, el build falla.
- `measured.system_from_snapshot`: arma un sistema **solo desde un snapshot**, para un blanco sin función en
  `catalog.py` (bloque `new` en `targets.toml`): estrella o enana marrón según el tipo SIMBAD (y solo con un match
  seguro), Teff/radio/masa/distancia solo si WS3 los da verificados, centro y movimiento de Gaia DR3, planetas
  confirmados con órbita solo si se publican P y a (sin e publicada, círculo con nota). Lo que falta queda
  desconocido y explicado. Hoy ningún blanco publicado lo usa; un test lo arma desde un snapshot existente.
- `record.py` + `errante systems --record <slug|all>` (solo desarrollo): re-graba un snapshot. Por defecto reproduce los
  fixtures de WS3 (`pipeline/tests/fixtures/ws3/context/`, respuestas reales grabadas por WS3 el 2026-11-15 entre las
  03:44 y las 04:22 UTC, con el archivo Gaia de ESA arriba) con `object_context(name=…, offline=True)`: sin red y
  reproducible. `--live` consulta los archivos en una caché vacía y se niega a escribir si un servicio dio error o si los
  parámetros de Gaia no vinieron del archivo de ESA (el respaldo de VizieR no trae FLAME, Bailer-Jones ni LPV).
  Un snapshot grabado con `--live` no tiene fixtures: `--record all` sin `--live` lo saltea y nombrarlo sin `--live` da
  error; el test acepta `origin.kind` `ws3-fixtures` o `live` (sin servicios con error y, si es live, Gaia de ESA).
- `errante systems --explain`: tabla de cuerpo, parámetro, valor, origen y razón de cada valor dibujado o desconocido.

**Por qué snapshots congelados y no WS3 en vivo.** Si el build corriera el código de WS3, un cambio de WS3 en sus
consultas o en su formato rompería los tests de WS7 dentro de un PR de WS3, que además no puede regenerar
`data/demo` (contrato) ni `data/products` (WS2). Con JSON congelado, un cambio de WS3 entra solo cuando alguien
re-graba con `--record` y revisa el diff. El costo: los snapshots envejecen; se re-graban a mano.

**Cómo agregar un blanco** (ver también la tarea WS7-10 en `tasks/WS7-3d-systems.md`):

1. Elegir la consulta por nombre que resuelve WS3 (las claves de caché dependen del texto exacto) y agregarla en
   `[snapshots]` de `targets.toml`.
2. Grabar el snapshot: `errante systems --record <slug>` si los fixtures de WS3 la cubren; si no, `--record <slug>
   --live` con el archivo Gaia de ESA respondiendo. Revisar el JSON (identidad, match, caveats) antes de commitear.
3. Agregar el bloque `[[system]]` / `[[system.body]]`: `snapshot`, `cross_check`, los `spherex_fact` que ya existan en
   un registro de validación y la razón de cada campo desconocido.
4. La capa de literatura: una función en `catalog.py` con los valores publicados y su fuente (y agregarla a
   `curated_systems()`), o un sistema armado solo desde el snapshot con `system_from_snapshot` (bloque `new` con
   `name` y, si hay, `description`, `field_id`, `body_id`): solo valores de catálogo verificados, el resto desconocido.
5. Regenerar los JSON: `errante systems --out data/demo` y `errante systems --out data/products --real-only`. Esos
   caminos son de contrato (`data/demo`) y de WS2 (`data/products`): la guardia de ownership los marca y el PR lo
   declara (precedentes #47 y #64).
6. Opcional, del lado frontend: las tablas por blanco (`ephemerides.ts`, `spherexCoverage.ts`, `skyTrack.ts`,
   `datasetGate.ts`). Sin ellas el blanco funciona: sin *Dataset time* de archivo, fases "unknown", sin panel del cielo
   si falta `motion`.

**Cómo agregar una fuente de medición.** Una medición SPHEREx nueva de un registro de validación entra como
`spherex_fact` (fuente que empiece con "SPHEREx": la UI le pone el chip "SPHEREx-measured (offline)"). Un parámetro nuevo de
WS3 entra agregando su clave a `cross_check`. Cuando WS3 publique la temperatura ajustada al espectro SPHEREx (V18),
ese valor tendrá que reemplazar la Teff de catálogo con su fuente SPHEREx; eso todavía no está implementado (WS7-8).

## Derivaciones, niveles (tiers) y mapeos de visualización

Estado en `main` desde #47 (15/11), con los cambios de V13 de la rama `ws7/measured-3d`. La fuente de verdad es el
código (`frontend/src/three/`): la ficha de cada cuerpo ("How this body is drawn" y "At SPHEREx scale",
`appearanceNotes.ts`) muestra para ese cuerpo el valor, el método, la cita y el tier de cada propiedad, leídos de
los mismos módulos que usa la escena. Esta sección es el resumen para el equipo; WS7 no agregó campos al contrato
(0.7.0 en `main`): lo que falta en `SystemModel` vive en tablas WS7 del frontend, con fuente y tests. El tier dice
cuán firme es un valor; el chip de origen (`factOrigin.ts`) dice de dónde sale: un valor `measured` de catálogo
sigue siendo "catalog, not measured by SPHEREx".

**Tiers** (`astro.ts`, de más fuerte a más débil):

| Tier | Significa |
|---|---|
| `measured` | el valor dibujado coincide con un `Fact` verificado, reconocido por su etiqueta, que no dice "estimate/model/illustrative", dentro de su error citado más media unidad del último dígito (sin error: 1 %; 5 % solo si el valor lleva `~`) |
| `derived` | calculado solo desde entradas medidas con una relación exacta (L = 4πR²σT⁴, log g) |
| `model` | interviene un modelo o aproximación (cuerpo negro, μ = 1.3, atmósfera gris, albedo supuesto, órbita circular) o una entrada es un modelo |
| `range-pick` | un número elegido dentro de un rango publicado para **este** objeto (Teff 4150 K de RW Aur B dentro de 4100–4200 K, Dodin+2020; la Teff 3000 K de R Dra dentro de ~2000–3300 K se quitó en V13) |
| `class-typical` | típico de la clase de objeto, no medido en este objeto (V13 quitó los dos que se dibujaban: la masa ~1 M☉ de R Dra y el ±10 % de su radio) |
| `theory` | expectativa teórica (bloqueo de marea) |
| `illustrative` | ninguna fuente verificada respalda el valor |
| `display` | un mapeo de pantalla, nunca fotometría |

Un valor calculado toma la entrada más débil y nunca es más fuerte que el piso de su método (`derivedTier`). Los
tiers de arcos, anillos y fases en *Dataset time* no existen en el código: ahí se indica "predicción" o "arbitraria".

**Cuerpos** (escena 3D):

| Propiedad | Entrada | Método / fórmula | Cita (como en el código) | Tier | Qué NO se modela |
|---|---|---|---|---|---|
| Color · SPHEREx IR (`ir`, modo por defecto) | `teff_k` del catálogo | Por canal, brillo superficial medio en frecuencia ⟨I_ν⟩ = Σ∫B_λ dλ / ΣΔν de un cuerpo negro: azul = D1+D2 (0.746–1.65 µm), verde = D3+D4 (1.63–3.847), rojo = D5+D6 (3.811–5.01). Bordes = `em_min–em_max` de IRSA SIA. Los tres canales comparten un factor (conserva el color). Estiramiento logarítmico fijo de 10 mag por debajo del cuerpo × canal más brillante del sistema. Chip "FALSE COLOUR · BLACKBODY MODEL · SPHEREx 0.75–5 µm bands" | Planck (Rybicki & Lightman 1979); Lupton et al. 2004, PASP 116, 133; bandas: `docs/RECON_SPHEREX.md` §2.2 | `model` (o el de Teff si es más débil: RW Aur B `range-pick`); el nivel en pantalla es `display` | **Sin Teff** (R Dra desde V13): gris neutro en todos los modos, "colour unknown (no single temperature adopted)", nunca una temperatura supuesta; la leyenda lo dice con la razón. Bajo 2500 K solo tono cualitativo, sin números y con contorno punteado (Burrows, Sudarsky & Lunine 2003). Exceso IR de disco y acreción (V4): 2MASS Ks y AllWISE W1/W2 de RW Aur A+B son 1.4, 1.9 y 2.8 mag más brillantes que la fotosfera A+B de cuerpo negro (Teff y radios de catálogo, 156.1 pc; épocas distintas, la estrella varía magnitudes); ninguna exposición SPHEREx D2–D6 de RW Aur sirve (0 de 279 limpias, OVERFLOW en 304 de 335), así que no se cita flujo SPHEREx. Bandas H₂O/CO y polvo de la Mira (Höfner & Olofsson 2018). Emisión y luz reflejada de planetas y discos: se dibujan como contorno. Saturación y no linealidad. No es la imagen SPHEREx |
| Color · D1…D6 (gris) | `teff_k` | El mismo ⟨I_ν⟩ de un solo detector, en gris, estirado 10 mag por debajo del cuerpo más brillante del sistema en ese detector | ídem IR | `model` / `display` | ídem IR |
| Color · Visible | `teff_k` | Cuerpo negro sumado sobre las funciones CIE 1931 2° (360–830 nm, cada 5 nm) → XYZ → sRGB lineal D65, negativos recortados, normalizado al canal mayor. Brillo = clamp(1 + log10(Y(T)/Y(5772 K))/8, 0.05, 1) | CIE 018:2019 / ISO/CIE 11664-1:2019; IEC 61966-2-1:1999 | color `model`; brillo `display` | Sin Teff: gris neutro, "colour unknown". Chip "VISIBLE · BLACKBODY COLOUR MODEL" (A15 de la revisión). Enanas marrones: no se calcula, se dibujan neutras (Burrows, Marley & Sharp 2000). Planetas: gris neutro 18 % iluminado por la estrella (albedo y color desconocidos). Discos: neutros y translúcidos. Mira: bandas de TiO (Reid & Goldston 2002). El sistema sintético conserva su paleta a mano y el ajuste de Tanner Helland (`illustrative`) |
| Contorno (rim) | tipo de cuerpo y modo | Línea de 2 px en pantalla (`fwidth`) más caída de Fresnel; punteada (24 trazos) mientras el nivel IR es solo cualitativo | regla de display WS7 | `display` | No es luz emitida: solo ayuda a encontrar cuerpos oscuros |
| Tamaño en pantalla y distancias | `radius_km`, elementos orbitales | Radio visible = clamp(0.12 · R_km^0.18, 0.12, 2.2) unidades; `capRadii` impide que un cuerpo toque a su padre o a un hermano. Distancias comprimidas (lineales hasta el menor periastro = 3 unidades, +10 unidades por década) o en proporción real (toda la cadena en ~30 unidades) | convención de display WS7 (`appearance.ts`, `sceneLayout.ts`) | `display`; la ficha muestra el factor de exageración y el tier del radio | El tamaño real. **Sin radio** (R Dra, ε Ind Ba y Bb desde V13): marcador fijo de 0.3 unidades (entre el piso de 0.12 y la Tierra, ~0.35), igual para todo tipo de cuerpo y sin escalar, con la etiqueta "size unknown · not to scale"; antes se inventaban 700 000 km para una estrella y 3000 km para lo demás. RW Aur A: radio derivado (luminosidad de catálogo + distancia Gaia), no verificado. El radio desde el flujo SPHEREx y la distancia Gaia (`VISION.md`) todavía no existe (WS7-8, depende de WS3) |
| Limb darkening y enrojecimiento del borde | `teff_k` | Atmósfera gris de Eddington, T⁴(τ) = ¾Teff⁴(τ + ⅔), con Eddington–Barbier I(μ) ≈ B(T(τ = μ)); tabla de 16 valores de μ por canal. Visible: a través de las funciones CIE. IR: monocromático en el centro geométrico de cada canal (1.11 / 2.50 / 4.37 µm). D1–D6: en el centro del detector | Mihalas 1978, Stellar Atmospheres; Gray 2005 | `model`, con el tier de Teff incluido (RW Aur B `range-pick`) | Atmósferas moleculares reales (enanas M, Miras) y diámetros de Mira que cambian con λ. Sin Teff o bajo 2500 K no se calcula (disco plano; la leyenda lo dice) |
| Celdas de convección (granulación) | `teff_k`, `mass_kg`, `radius_km` | Celdas a lo ancho = 2R / (10 H_p), con H_p = kTeff / (μ m_H g), μ = 1.3, g = GM/R²; solo si son menos de 64 | Trampedach et al. 2013; Freytag et al. 2017; Schwarzschild 1975 (celdas gigantes); H_p: Gray 2005 | tamaño `model`; contraste ±15 % `illustrative` | **No se dibujan en ningún blanco real desde V13** (ninguna celda está observada; `VISION.md`: sin manchas inventadas). Antes R Dra resultaba resoluble (≈8 celdas) solo con su radio ilustrativo y su masa class-typical, que se quitaron. El cálculo queda para el sistema sintético, rotulado ILLUSTRATIVE |
| Glow | L = 4πR²σT⁴ × fracción de cuerpo negro en la banda del modo (visible 380–780 nm; IR 0.746–5.01 µm; o el detector) | Tamaño del sprite = radio visible × (2 + 3n), con n = 1 + log10(L/L_max)/4 acotado a [0, 1]. Opacidad = nivel de display. En modo visible la curva V lo modula: opacidad × f^0.25, tamaño × f^0.3 (f = flujo / flujo medio) | convención de display WS7 (`colorModes.ts`) | `display` | Ninguna curva de luz IR: en los modos SPHEREx el glow es fijo. Sin Teff o sin radio (R Dra) L es desconocida: el glow toma el tamaño fijo de display (factor 2) en el tono del cuerpo, gris neutro si el color es desconocido, y en visible sigue la curva V de catálogo. No es un halo físico |
| Pulsación (brillo) · R Dra | `variability` (P, 6.5 mag en V); en *Dataset time*, los máximos AAVSO medidos (ventana SPHEREx) y la efeméride VSX (fuera) | **Radio constante** (V12b, decisión D3 tomada por WS7 a confirmar por el equipo): el cambio de tamaño no está medido en R Dra. Solo el brillo pulsa. *Free-running*: f = 10^(−0.4·(A/2)·sin(2π(MJD − 51544.5)/P)), con P = 245.6 d (GCVS) y fase arbitraria (cero en J2000). *Dataset time*: forma asimétrica s(φ) de medios cosenos que sube en el 45 % del ciclo (mínimo en φ = 0.55); f = 10^(0.2·A·s). Leyenda: "R Draconis: radius drawn constant, because its size change is not measured. Its V-band light curve (catalog, not measured by SPHEREx) drives the glow in the visible mode only …" | GCVS 5.1 (Samus et al. 2017); AAVSO VSX | fase arbitraria (*Free-running*) o predicción V de catálogo (*Dataset time*) | El cambio de tamaño (antes ±10 % class-typical, Ireland+2004 / Woodruff+2004: quitado). La curva SPHEREx: medida offline, 0.5–1.3 mag pico a pico a 0.74–5.0 µm y ciclo de ~260 d en 2025–2026 (facts "seen by SPHEREx"); el 3D no la dibuja y remite al panel "Light curve" de la página del campo (`LightCurvePanel`, WS5, #83). Cambios ciclo a ciclo. Las variables irregulares (RW Aur A/B) no se animan |
| Rotación (spin) | `rotation_period_hours` con su `Fact`, o la regla de marea | Ángulo = 2π · 24 · (MJD − 51544.5) / P_h (fase rotacional desconocida, cero en J2000), eje dibujado vertical; se congela si avanzaría más de 90° por cuadro (aliasing). Marea: un planeta con P_orb < 10 d alrededor de una enana M muestra siempre la misma cara | Toledo-Padrón et al. 2019, MNRAS 488, 5145 (Barnard, 145 ± 15 d); Barnes 2017, Celest. Mech. Dyn. Astron. 129, 509 | Barnard `measured`; Barnard b–e `theory` | Orientación del eje y fase rotacional. No giran: ε Ind A (períodos publicados de ~18, 22 y 36 d, discordantes), RW Aur A (solo un candidato de ~5.6 d; los 2.64 d de AAVSO VSX son de A+B sin resolver y no se adoptan), WISE 0855 (período no determinado), ε Ind Ba/Bb (no medidos) |
| Superficie | — | Esfera lisa con color de cuerpo negro y oscurecimiento al borde en todos los cuerpos reales. **V13 quitó el toggle "show class-typical features (illustrative)"**, su chip y la lista S5 que dibujaba (bandas nubosas en ε Ind Ba y bandas zonales en ε Ind Ab, ±15 %, y las celdas de R Dra) | `VISION.md` (superficie: "sin manchas, nubes ni bandas inventadas") | — | Ningún mapa de superficie medido, ni amplitud de modulación rotacional verificada. El sistema sintético conserva sus texturas procedurales (decoración rotulada SYNTHETIC) |
| Iluminación | colores del modo activo | Las estrellas no se iluminan (shader propio) y llevan una luz puntual de su tono, con intensidad normalizada (sin 1/r²). Planetas: gris 18 % iluminado en visible, contorno en los modos SPHEREx. Enanas marrones: autoluminosas, sin iluminar | convención de display WS7 | `display` | Albedo, fases de iluminación reales, luz reflejada entre cuerpos |
| Órbitas (geometría) | `Orbit`: a, P, e, i, Ω, ω, M₀, `epoch_mjd`, `quality` | Kepler de dos cuerpos (Newton–Raphson), rotación 3-1-3, jerarquía padre → hijo sin baricentros. Color según `quality`: ajustada (azul grisáceo), `assumed` (amarillo), `hypothetical` (violeta) | fuentes por dato en `catalog.py` | el de los `Fact` de a y e; una órbita `assumed` da `illustrative` y el flag `assumed-orbit` | Baricentros y perturbaciones. La inclinación real de los planetas por velocidad radial (se dibujan en el plano de referencia, i = 0). El sentido de giro en el cielo (se dibuja antihorario visto desde arriba) |

**Tiempo y posiciones** (detalle en la sección siguiente):

| Propiedad | Entrada | Método / fórmula | Cita (como en el código) | Tier | Qué NO se modela |
|---|---|---|---|---|---|
| Fase orbital en *Dataset time* · Barnard b–e | t0 y P con 1σ (tabla `ORBIT_EPHEMERIDES` y `Orbit.epoch_mjd`) | `epoch_mjd` = t0 − 2400000.5; M = 270° en t0. Arco de 64 puntos sobre ±2σ de anomalía media, con σφ = √(σt0² + N²σP²)/P y N = (t − t0)/P; si σφ > 0.5 ciclo, anillo | Basant et al. 2025, ApJL 982, L1, Tabla 3 (arXiv:2503.08095); propagación lineal (Taylor 1997; Zellem et al. 2020, PASP 132, 054401); cuantiles normales de Acklam 2003 | predicción; t0 y P son `Fact` verificados por su valor, la convención (conjunción) es una lectura nuestra | La covarianza t0–P (no publicada). La inclinación y el sentido de giro |
| Fase orbital en *Dataset time* · sin época | `Orbit.epoch_mjd = null` | Cuerpo atenuado (× 0.35), sufijo "(phase unknown)", anillo de 64 puntos uniformes en anomalía media | `UNKNOWN_PHASE_REASONS` (Sanghi et al. 2026; Chen et al. 2022; Kurtovic et al. 2024) | arbitraria | Cualquier posición en una fecha real |
| Fase de pulsación en *Dataset time* · R Dra | máximos V medidos (MJD 60811.4, 61046.5, 61304.3) y efeméride VSX (tabla `MIRA_EPHEMERIDES`) | Dentro de la ventana SPHEREx (MJD 60790–61310): φ lineal entre máximos medidos consecutivos (antes del primero y después del último, desde el más cercano con P de VSX), banda de ±3 d. Fuera: φ = frac((t − E0)/P), 0 = máximo, banda de 1σ = 9.0 d (RMS del O−C de esos máximos respecto de VSX) | AAVSO International Database, 818 observaciones visuales y V (parábolas de ±40 d; análisis offline de WS3, `docs/validation/r-draconis.md`); AAVSO VSX R Dra (oid 13673, revisión 4, 2024-01-18) | fase V fechada con máximos medidos (ventana) o predicción V de catálogo (fuera) | Término de Eddington–Plakidis, curva IR, curva de luz SPHEREx. En los bordes de la ventana la fase salta < 0.02 ciclos |
| Trayectoria en el cielo ("Where SPHEREx should see it") | `SystemModel.center` + `motion` (o una constante WS7 para ε Ind B) | Movimiento espacial rectilíneo con velocidad radial + paralaje anual con la Tierra = −Sol (baja precisión); lugar astrométrico ICRS geocéntrico; offsets gnomónicos, norte arriba y este a la izquierda; un punto por pasada | Butkevich & Lindegren 2014, A&A 570, A62; Astronomical Almanac, Section C; Meeus 1998, cap. 25; validación contra `docs/RECON_SPHEREX.md` §4.1 | posiciones `derived`, paralaje `model`, lugar `derived`, grilla de píxeles `display` | Ver la sección siguiente |

## Tiempo del dataset SPHEREx (2025-04 → 2026-11)

El visor tiene **dos relojes** (selector junto a Play). Ninguno muestra datos SPHEREx en 3D: el 3D sigue siendo un
modelo de catálogo; el reloj solo decide en qué fecha se evalúan órbitas y pulsaciones.

- **Free-running** (al abrir): arranca en un instante arbitrario (la hora del navegador) y muestra "Model time"
  como tiempo transcurrido, nunca una fecha. Velocidad = el período más corto del sistema en 8 s, por el slider
  de velocidad (0.25–8×). Las órbitas sin época toman `mean_anomaly_deg` en J2000 (convención de dibujo) y la
  variabilidad periódica es un seno con fase cero en J2000. El texto dice "not a prediction for a real date".
- **Dataset time (SPHEREx 2025-2026)**: disponible para los cinco blancos (ventanas de archivo) y para un sistema
  cuyo campo construido tenga frames con `mjd` (el sintético usa los frames de `demo-ecliptic`). El reloj va del
  inicio de DR1 (MJD 60789.75 = 2025-04-24 18:00 UTC) al fin de la última pasada o al 2026-11-14 (MJD 61358, fecha
  de la consulta), lo que sea posterior. Abre en pausa a mitad de la Pasada 1, se detiene al final y Play vuelve a
  empezar. Velocidad = la de *Free-running*, pero nunca más rápida que la ventana completa en 60 s, por el slider.
  Muestra el chip "DATASET TIME · fecha", la línea "Real epoch: … · Arbitrary phase: …" y la lista "On this date"
  con la fase de cada cuerpo.
- **Línea de tiempo** (`DatasetTimeline.tsx`): las pasadas de archivo aparecen rayadas con "archive coverage -
  frames not built in this dataset"; los frames construidos, como marcas coloreadas por detector. Hay botones
  "Pass N", un marcador "today 2026-11-14 · no later data in this dataset" y una fila por variable: la curva V
  predicha de R Dra con cada máximo y su banda, y RW Aur rayado como irregular.
- **Ventanas de pasadas** (`spherexCoverage.ts`): copiadas de `docs/DATA.md` §3.0 ("Cobertura de los 5 objetivos",
  MJD redondeado al día, ±0.5 d) y de `docs/RECON_SPHEREX.md` §4.2 (fechas, conteos por detector, imágenes a
  3.9–5 µm). Son **ventanas de archivo**: IRSA tiene frames del blanco ahí, pero este dataset no los contiene
  (`data/demo` solo tiene campos sintéticos). La 2.ª pasada de WISE 0855 se parte en dos visitas con el corte de
  10 días (RECON §2.6). En la última pasada de ε Ind B solo hay D2, D3, D5 y D6. Los tiempos de frame son
  `MJD-AVG`, tratados como UTC (la diferencia TT/UTC de ~69 s no importa al día).

### Barnard b–e en su fase publicada (M5)

- t0 y P de Basant et al. 2025, Tabla 3 (en la tabla, t0 = BJD − 2450000). `epoch_mjd` = t0 − 2400000.5 y
  `mean_anomaly_deg` = 270: en t0 el planeta queda en AU (0, −a, 0) = escena +z, sobre la flecha "toward Earth (line
  of sight projected on the orbit plane; inclination unknown)" que se dibuja para órbitas fechadas con
  i = Ω = ω = 0. El sentido de giro en el cielo no se conoce (antihorario visto desde arriba).
- **Lectura de t0 como conjunción inferior: es una decisión de criterio, pendiente de revisión del equipo; el
  equipo no la decidió.** El texto del paper dice "time of periastron passage". A favor de la conjunción:
  - juliet pasa t0 a RadVel como `tc` (tiempo de conjunción) y no tiene parámetro de periastro;
  - las posteriores de t0 (±0.09 d) son estrechas mientras ω queda sin restringir (±120°), lo que no tiene sentido
    para un periastro de una órbita casi circular;
  - propagado 33 ciclos hacia atrás, el t0 de b coincide con el Tc de González Hernández et al. 2024 (BJD
    2460139.204 ± 0.149) en 0.028 ciclos (0.5σ). Leído como periastro quedaría a ~4.7σ con el ω mediano.
    Lo comprueba `test_basant_b_ephemeris_reaches_the_gonzalez_hernandez_2024_conjunction`.
  El NASA Exoplanet Archive guarda el valor en su columna de periastro (`pl_orbtper`), siguiendo el texto del paper,
  así que no lo confirma de forma independiente. El `Fact` "Reference time t0" está verificado solo por el valor; la
  advertencia aparece en la nota de la órbita, en la ficha y en cada línea "On this date". Si el equipo no la acepta,
  hay que volver a `epoch_mjd = null` (fase arbitraria; ver la tarea WS7-9).
- Dispersión de fase a 1σ: σφ = √(σt0² + N²σP²)/P, propagación lineal, sin la covarianza (no publicada). Para un
  error asimétrico se toma el lado mayor, y para e la σP del paper (0.0028 d; el archivo la redondea a 0.003). Del
  inicio de DR1 (2025-04-24) al último frame QR3 (2026-10-05): d 16.4° → 24.5°, b 13.0° → 18.6°,
  c 11.2° → 16.2°, e 23.2° → 31.0°.
- Dibujo: arco de 64 puntos en cuantiles fijos de la normal (Acklam 2003) sobre ±2σ de anomalía media, con opacidad
  según la densidad gaussiana y el color de la leyenda de órbitas, aclarado. Si σφ > 0.5 ciclo, el arco pasa a anillo.

### Anillos de fase desconocida (S2)

Toda órbita sin `epoch_mjd` se dibuja en *Dataset time* atenuada (× 0.35), con "(phase unknown)" y un anillo de
64 puntos uniformes en anomalía media (densidad en el tiempo: más denso cerca del apoastro). En una órbita ajustada,
el anillo muestra dónde podría estar el cuerpo. En una `assumed` o `hypothetical` no se conoce ni la órbita ni la fase:
el anillo es solo el círculo supuesto. Por qué cada fase queda sin fecha (`UNKNOWN_PHASE_REASONS`):

- ε Ind Ab: Sanghi et al. 2026 dan un periastro JD 2441420.76 (+2675/−3217 d) y P = 25450 (+4387/−3302) d,
  fuertemente correlacionados y sin covarianza publicada, así que no se propaga.
- ε Ind Bb: Chen et al. 2022 ajustaron un tiempo de periastro pero no lo publican (la Tabla 4 da P, a, e, ω, Ω, i).
  Un T0 derivado por nosotros de su Tabla 3 no se usa: no es un valor publicado.
- ε Ind Ba: órbita `assumed` alrededor de A.
- RW Aur B: periastro 295 (+136/−457) años antes de la última época ALMA (~1590–2180 d.C.), y el paper no documenta
  cómo se proyecta el marco de la órbita en el cielo (Kurtovic et al. 2024, Tabla 3 y §3.3).

### R Dra en su fase V predicha (S3)

- Efeméride AAVSO VSX (oid 13673, revisión 4, 2024-01-18): máximo en HJD 2457370.00, P = 246.12 d, subida 45 %.
  φ = frac((t − E0)/P), con 0 = máximo. VSX no publica errores. *Free-running* sigue con el seno a P = 245.6 d
  (GCVS); *Dataset time* usa época y período de VSX juntos, sin mezclarlos con el GCVS.
- **V12a (variante completa, hecha):** dentro de la ventana SPHEREx de R Dra (MJD 60790–61310, 2025-04-24 →
  2026-09-27) la fase se fecha con los máximos V medidos en el registro (MJD 60811.4, 61046.5 y 61304.3 = 2025-05-16,
  2026-01-06 y 2026-09-21): fase lineal entre máximos consecutivos (ciclos de 235 y 258 d) y banda de ±3 d (error
  formal 0.5–0.8 d; el real, "unos pocos días", es INFERIDO en el registro). Antes del primer máximo y después del
  último (21 d y 6 d dentro de la ventana) la fase corre desde el máximo medido más cercano con el P de VSX. Los mínimos
  dibujados (φ = 0.55) caen en MJD 60940.7 y 61188.3, dentro de los medidos (60939–60947 y 61185–61196). Fuera de la
  ventana sigue la efeméride VSX con la banda de abajo; en los bordes la fase salta < 0.02 ciclos (test).
- Banda de tiempo (1σ) de cada máximo predicho fuera de la ventana (V12a, variante corta): RMS del O−C de los máximos V
  2025–2026 medidos en el registro de R Dra (818 observaciones AAVSO; MJD 60811.4, 61046.5 y 61304.3) respecto de
  VSX: −3.8, −14.8 y −3.1 d → **9.0 d**. Antes era 6.6 d (máximos 2015–2024 de la lista de T. Karlsson: media −4.7 d,
  desvío 4.6 d), que dejaba el máximo de enero de 2026 a 2.2σ. Las fechas no se corren por la media: la banda la
  incluye. Sin un término de Eddington–Plakidis con fuente, la banda **subestima** la incertidumbre (el período además
  deriva en décadas).
- Máximos dibujados dentro del dataset: los medidos, 2025-05-16, 2026-01-06 y 2026-09-21 (± 3 d); las fechas VSX de
  esos ciclos (2025-05-20, 2026-01-21 y 2026-09-24) ya no se dibujan. Fase 0.91 el 2025-04-24 (VSX: 0.90) y 0.04 el
  2026-10-05 (fuera de la ventana, VSX): ~2.1 ciclos en el dataset.
- Leyenda (A13 de la revisión): "V-band prediction from a catalogue ephemeris, not a SPHEREx light curve. Measured
  offline on the SPHEREx FITS files, the infrared cycle is 0.5–1.3 mag peak-to-peak (6.5 mag in V), with maxima from
  1 day before (0.74–1.1 µm) to 47 days after (2.4–3.8 µm) the visual ones (docs/validation/r-draconis.md)". El glow
  sigue la curva solo en modo visible; el radio no cambia.
- Una sola regla de variabilidad (`variabilityPhase`) para la línea de tiempo, "On this date", la línea de estado y
  la escena: `irregular` (RW Aur A y B: "irregular: cannot be predicted", nunca una curva; V12c: para RW Aur se agrega
  lo medido offline, ~1 mag más brillante a 0.75–0.77 µm en sep 2026 que en sep 2025 en exposiciones D1 sin saturar,
  y que ninguna exposición D2–D6 está limpia, así que el brillo de la imagen no es una medición), `predicted`
  (periódica con efeméride WS7: hoy solo R Dra) y `unknown` (el resto, congelado en el brillo medio con
  "pulsation/variability phase unknown").

### Trayectoria predicha en el cielo (S4)

Panel "Where SPHEREx should see it" debajo de las tarjetas de `#/system/<id>` (carga diferida), con el badge
"PREDICTION · NOT A MEASUREMENT" y el texto "Predicted position from catalog astrometry - not a measurement".

- Movimiento espacial rectilíneo desde la época de catálogo, con velocidad radial cuando se conoce (Butkevich &
  Lindegren 2014). Paralaje con la posición de la Tierra = −Sol del Astronomical Almanac de baja precisión (~0.01° en
  longitud): +0.00569° de aberración anual, −0.01397°/año al equinoccio J2000 (Meeus 1998, cap. 25) y oblicuidad
  J2000 (84381.448″). Es heliocéntrica, no baricéntrica: el Sol está a ≤ 0.0074 AU del baricentro en 2025–2026, es
  decir ≤ 0.75 % de la paralaje (4 mas en Barnard). La órbita de SPHEREx (~5×10⁻⁵ AU) se ignora.
- Salida: lugar astrométrico ICRS geocéntrico (sin aberración ni deflexión de la luz), el que sirve para cruzar
  catálogos y centrar recortes. Offsets gnomónicos en arcsec, norte arriba y este a la izquierda. Un punto por
  pasada, a mitad de la ventana, o por visita cuando el corte de 10 días la parte. La grilla son píxeles de 6.15″
  alineados para display: cada frame real tiene su propia fase de píxel y orientación.
- Validación (`skyTrack.test.ts`): reproduce los vectores geocéntricos 2026.0 de RECON §4.1 (astropy) a < 0.01″ y
  los baricéntricos a 5 decimales; la Tierra coincide con ERFA `epv00` a 0.0003 AU y 0.012°; Barnard se mueve
  15.7″ = 2.56 px del 2025-05-01 al 2026-11-14.
- Fuentes: Barnard, R Dra y RW Aur salen de `SystemModel` (Gaia DR3 y velocidades radiales de catálogo). ε Ind usa la
  solución Gaia DR3 de **B** (6412596012146801152, fotocentro Ba+Bb) como constante WS7 copiada de RECON §4.1, sin
  velocidad radial: el centro del sistema es A, pero el campo y la cobertura son de B (la solución coincide con Gaia DR3
  en el TAP de ESA, fixture de WS3 del 2026-11-15, según la revisión de WS3). WISE 0855 usa Kirkpatrick et al. 2021
  (época MJD 57633.39), sin velocidad radial: es la solución adoptada (decisión de WS3 en `SCIENCE.md`, también la de
  `fields.toml` y del registro); el ajuste propio, no publicado, de RECON §4.1 queda como control a 0.31″ (0.05 px) el
  2026-11-14.
- En *Dataset time* el panel marca además el lugar predicho en la fecha del 3D (`SystemViewerContext`).
- Notas por blanco con los resultados de los registros de validación (V12d/e y menores de la revisión; análisis
  offline de los FITS): Barnard saturada (OVERFLOW) en 357 de 358 exposiciones, en los seis detectores, con núcleo NaN
  en 240 (casi todas D1–D4); WISE 0855 se ve solo en D5/D6 (3.8–5.0 µm), S/N mediana 3.4–3.8 por exposición y 21–25
  por detector sumando todo; en D1–D4 la mancha en su posición es la estrella de campo; R Dra saturada (OVERFLOW) en
  las 2,488 exposiciones con píxeles finitos, no NaN.
- No se modela: el bamboleo del fotocentro Ba–Bb (< 1.02″ = 0.17 px), el `MJD-AVG` de cada frame (los frames de una
  pasada se reparten sobre el "drift" mostrado, hasta 0.3 px en Barnard), la fase de píxel y orientación por frame, ni
  la saturación (solo se informa en las notas). La estrella de campo estática junto a WISE 0855 (Gaia DR3
  5756956644387831296) sí se muestra.

### Diferencias con `VISION.md` que siguen abiertas

`VISION.md` pide que cada valor del 3D salga de una medición y que lo no medido no se dibuje, o se muestre como
"unknown". Estado con V13 (rama `ws7/measured-3d`), propiedad por propiedad de la tabla de `VISION.md`:

| Propiedad | Estado | Qué falta |
|---|---|---|
| Temperatura → color | **parcial.** Teff publicada (NASA Exoplanet Archive / papers, `catalog.py`), rotulada "catalog, not measured by SPHEREx"; sin Teff publicada → gris y "colour unknown" (R Dra) | El ajuste del espectro SPHEREx (V18, WS3; `color_class` sigue sin implementar) y usarlo en el 3D (WS7-8). Solo ε Ind B (mezcla Ba+Bb) y WISE 0855 (D5/D6) tienen espectros SPHEREx sin saturar; Barnard, R Dra y RW Aur saturan |
| Radio / tamaño | **parcial.** Radios publicados (medidos o de modelo, rotulados) o derivados con Stefan–Boltzmann desde una luminosidad de catálogo y la distancia Gaia (RW Aur A, "derived", unverified); sin radio → marcador fijo "size unknown · not to scale" (R Dra, ε Ind Ba/Bb) | La luminosidad desde el flujo SPHEREx integrado (no implementada en WS3) |
| Pulsación | **parcial.** Modelo de brillo V de catálogo (seno GCVS / efeméride VSX) con radio constante; la curva SPHEREx medida está como facts "seen by SPHEREx" y en el panel "Light curve" de la página del campo (WS5, #83) | Dibujar la curva SPHEREx a λ compatible (revisión de WS3 del producto pendiente, `backend/README.md`); hasta entonces `VISION.md` admite "modelo estático" |
| Movimiento en el cielo | **parcial.** Predicción desde astrometría de catálogo ("PREDICTION · NOT A MEASUREMENT"), más los facts "Motion seen by SPHEREx" de Barnard y ε Ind B | Mostrar las posiciones SPHEREx por temporada |
| Rasgos del espectro | **cumple** (no se dibujan como geometría; la ficha dice qué no se modela) | Listar en la ficha los rasgos medidos en el espectro SPHEREx |
| Planetas y compañeras | **cumple** (solo confirmados en catálogo, con fuente) | — |
| Superficie | **cumple.** Esferas lisas, sin toggle class-typical (quitado en V13); el sintético conserva sus texturas rotuladas | — |
| Punto no catalogado | **no cumple:** no hay 3D para un click arbitrario | V14 (trabajo futuro, D7): armar un sistema desde el contexto de objeto de WS3 sin inventar nada |

Antes de V13 también faltaba: valores elegidos a mano (Teff 3000 K, radio 250 R☉ y masa ~1 M☉ de R Dra; radio 0.9 R♃
de ε Ind Ba/Bb; masa 5 M♃ de WISE 0855), el toggle con bandas y celdas inventadas, el ±10 % de radio de R Dra y los
tamaños por defecto de 700 000 / 3000 km para cuerpos sin radio. Todo eso se quitó.

## Próximos pasos (ver tareas)

WS7-1 integrar con el flujo principal · WS7-2 verificar valores contra catálogos (hecho) · WS7-3 órbitas reales de
asteroides desde SBDB para los candidatos `known` · WS7-4 pulido visual (anillos, cámara, leyenda de escala) · WS7-5
vista "moverse por el espacio" (paralaje + movimiento propio: por qué Barnard se mueve tanto) · WS7-6 modelos de forma
reales · WS7-7 Planeta Nueve hipotético · WS7-8 color desde el espectro SPHEREx (depende de V18 de WS3) · WS7-9 tiempo
del dataset SPHEREx (mergeado en #47; faltan la aceptación de M5 por el equipo y la revisión visual) · WS7-10 capa de
mediciones (V13, rama `ws7/measured-3d`) · V14 3D para un click arbitrario (trabajo futuro). P2 congelado hasta después
del envío según la propuesta D10 de `PARALLEL_PLAN.md`.
