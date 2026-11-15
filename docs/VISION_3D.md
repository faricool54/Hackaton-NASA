# Visión 3D: de un punto que se mueve a un sistema que se puede explorar

> Workstream **WS7**. Estado: **esqueleto funcional** — `#/systems` y `#/system/<id>[/<cuerpo>]` ya andan con
> modelos 3D de los 5 objetivos de prueba del reto + un sistema sintético. Tareas en
> [tasks/WS7-3d-systems.md](../tasks/WS7-3d-systems.md).
> En la rama `ws7/procedural-3d` (14/11, todavía sin PR a `main`): cada propiedad visual sale de física y
> catálogo con su tier, el color SPHEREx IR es el modo por defecto, existe el modo **Dataset time** sobre las
> fechas reales de SPHEREx y el panel "Where SPHEREx should see it". Detalle en
> [Derivaciones, niveles (tiers) y mapeos de visualización](#derivaciones-niveles-tiers-y-mapeos-de-visualización)
> y [Tiempo del dataset SPHEREx](#tiempo-del-dataset-spherex-2025-04--2026-11).

**Extensión P2**, posterior al recorrido obligatorio RA/Dec → imágenes reales → animación y ensayos.
Las guías de entrega y evaluación exigen evidencia, honestidad y atribución: `REQUIREMENTS.md`,
`SUBMISSION_GUIDE.md` y `JUDGING_GUIDE.md`. La galería ya existe, pero no valida R02/R05 ni aporta por sí
misma integración real de datos NASA para Relevance. El código llegó en la contribución WS7; los parámetros
se contrastaron con catálogos y papers en WS7-2 (2026-11-14, con asistencia de IA); falta la revisión humana del equipo.

## La idea

SPHEREx muestra los objetos como **puntitos** que se mueven o cambian de brillo entre imágenes. Eso es lo que
pide el reto y es la base (blink / flip-book). Nuestra capa extra: **cada objeto que seguimos se puede abrir en
3D** para entender qué es y cómo evoluciona.

1. **Ver el objeto en 3D.** Estrella, enana marrón, planeta, asteroide: un modelo cuyo tamaño, color y aspecto
   salen de sus datos (radio, temperatura efectiva → color de cuerpo negro, tipo de cuerpo, bandas de nubes,
   cráteres…). Cuando exista un modelo de forma real (p. ej. asteroides con forma por radar/curvas de luz), se
   usa ese.
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
  papers citados; quedan "unverified" solo las estimaciones que ninguna fuente publica (radio de R Dra y de RW Aur A).
- Lo que no sabemos no se dibuja como si lo supiéramos: cada órbita declara `Orbit.quality`. `assumed` (no
  ajustada: un círculo a la separación proyectada o a una distancia estimada) se dibuja **en amarillo** y la ficha
  dice "assumed, not fitted"; `hypothetical` (p. ej. Planeta Nueve) en violeta. Las fases sin época son
  arbitrarias: en *Free-running* el visor muestra tiempo transcurrido, no una fecha "predicha"; en *Dataset time*
  esos cuerpos se atenúan, llevan "(phase unknown)" y un anillo en lugar de una posición (ver
  [Tiempo del dataset](#tiempo-del-dataset-spherex-2025-04--2026-11)).
- Superficies: **esferas lisas** con color de cuerpo negro y oscurecimiento al borde, como pide
  [`VISION.md`](VISION.md) ("lo que no se midió no se dibuja"). Los rasgos típicos de clase solo aparecen con el
  toggle "show class-typical features (illustrative)", **apagado por defecto** y marcado ILLUSTRATIVE. Eso incluye
  las celdas de convección de R Dra: resolubles según el modelo, pero no observadas en esta estrella.
- Lo sintético sigue llevando el badge **SYNTHETIC DATA** (`provenance.synthetic`).
- Simplificaciones explícitas: jerarquías sin baricentros (Epsilon Indi), variabilidad sinusoidal en
  *Free-running* (solo R Dra tiene una curva asimétrica de efeméride, en *Dataset time*), radios estimados de
  planetas no transitantes. Cada una figura en `provenance.notes` o en la etiqueta del dato.

## Qué representan los presets (verificados en WS7-2, 2026-11-14)

Cada valor se comprobó en la fuente y quedó en `catalog.py` con la cita exacta; `systems/sources.py` reproduce
las consultas y los tests `network` de `test_systems.py` las vuelven a correr. Posiciones y movimientos en la
época de la fuente (Gaia DR3 = J2016.0), no en J2000.

| Objetivo | Qué se modela | Fuentes usadas | Correcciones respecto de los valores tipeados |
|---|---|---|---|
| **Barnard's Star** | M4V + 4 planetas (P 2.34–6.74 d, masa mínima 0.19–0.34 M⊕; órbitas circulares; fases desde el t0 de Basant+2025, Tabla 3) + rotación 145 ± 15 d | Exoplanet Archive (González Hernández+2024, Basant+2025), Gaia DR3 4472832130942575872, Toledo-Padrón+2019 | RV −110.47 km/s (Gaia DR3); centro y época → J2016.0; t0 leído como conjunción inferior (pendiente de revisión del equipo) |
| **Epsilon Indi** | K5V + Ab (6.5 M♃, a 15.8 AU, e 0.25) + Ba/Bb (T1/T6, P 11.02 a, e 0.54) | Exoplanet Archive (Sanghi+2026), Matthews+2024, Chen+2022, Scholz+2003, Gaia DR3 | Ab: el ajuste vigente (Sanghi+2026) reemplaza a Matthews+2024 (28 AU, e 0.4); masa de A 0.80; Teff 4700 K |
| **WISE 0855−0714** | enana marrón aislada, ~285 K, ~Y4 | Kirkpatrick+2021 (paralaje/movimiento), Luhman+2024 (JWST) | movimiento propio −8123.7/+673.2 mas/a; las coordenadas del enunciado son WISE All-Sky **época 2010.34**, no J2014 |
| **R Draconis** | Mira, P 245.6 d, V 6.7–13.2 (*Free-running*: seno ilustrativo; *Dataset time*: fase V predicha por la efeméride VSX) | GCVS 5.1, AAVSO VSX, Gaia DR3, Bailer-Jones+2021, van Belle+2002, McDonald+2012, Feast 2009 | Teff como rango 2000–3300 K (cambia con la fase); se agregó movimiento (~790 pc); masa class-typical ~1 M☉ (Feast 2009, sin verificar), solo para el tamaño de las celdas |
| **RW Aurigae** | A (CTTS, 1.24 M☉) + disco de polvo de 19 AU + B (K6.5, 1.0 M☉) en la órbita ajustada | Kurtovic+2024 (ALMA), Dodin+2020, Testi+2022, VSX, Gaia DR3 | B tiene órbita publicada (a ~258 AU, e 0.79, P ~2800 a, muy incierta); **SIMBAD tiene invertidos los Gaia DR3 de A y B** |
| Asteroides / TNOs del pipeline | órbita heliocéntrica real (elementos osculantes) + forma si existe | JPL SBDB, NASA 3D Resources, DAMIT | pendiente (WS7-3) |
| Planeta Nueve (P2, opcional) | órbita **hipotética** con `Orbit.quality = "hypothetical"` | Brown & Batygin 2021 (AJ 162, 219), a verificar | pendiente (WS7-7) |

Para WS3 (blancos): RW Aur A = Gaia DR3 156430817820015232 y B = 156430822114424576 (al revés que SIMBAD; ángulo
de posición WDS y Kurtovic+2024). Las coordenadas del enunciado para WISE 0855 son de 2010.34: hay que propagar
~8.2″/año. Detalle de cada consulta: `pipeline/errante/systems/catalog.py`.

Lo que **no** sale de SPHEREx: las órbitas y parámetros físicos vienen de catálogos. SPHEREx aporta *dónde está y
cómo se mueve en el cielo*, su **espectro 0.75–5 µm** y su variabilidad; la vista 3D lo pone en contexto.
En la versión actual esos productos SPHEREx reales aún no se generaron. Las fuentes de la tabla son
destinos de verificación, no constancia de una consulta ya realizada ni evidencia de parámetros correctos.

## Cómo está armado

```
pipeline/errante/systems/       (WS7)
  catalog.py   sistemas curados (verificados en WS7-2, con fuente por dato) + sistema sintético del demo
  sources.py   NASA Exoplanet Archive, SIMBAD (CfA) y Gaia DR3 por TAP (urllib); stubs: JPL SBDB, modelos de forma
  build.py     valida jerarquía (padres existen, sin ciclos) y escribe <root>/systems/<id>.json
       │  errante demo  → data/demo/systems/*.json      errante systems --real-only → data/products/systems/*.json
       │  (--real-only: solo sistemas no sintéticos; se niega si <out>/systems ya tiene uno sintético)
       ▼
contrato: SystemModel (models.py, schema 0.2.1) · Manifest.systems · GET /api/systems/{id}
       ▼
frontend/src/three/             (WS7, three.js en un chunk aparte, carga diferida; casi todo con *.test.ts al lado)
  orbits.ts          Kepler (posición en el tiempo, elipse), orden padre→hijo, variabilidad sinusoidal
  astro.ts           núcleo físico: cuerpo negro, CIE 1931, L, log g, H_p, granulación, Teq, AB SPHEREx;
                     cada resultado es { value, tier, method, citation, flags }
  cie1931.ts         funciones de igualación CIE 1931 2° (5 nm)
  spherexBands.ts    bandas D1–D6, píxel 6.15″, onset de no linealidad (RECON §2.2)
  colorModes.ts      modos de color (SPHEREx IR por defecto, visible, D1–D6 en gris), glow, leyendas
  appearance.ts      color base, gate de superficies (toggle class-typical), distancias comprimidas, radios
  sceneLayout.ts     radios sin solapes, cámara, reloj, pulsación ±10 %, reglas de spin
  starMaterial.ts    shaders: limb darkening, celdas de convección, contorno (rim)
  ephemerides.ts     Dataset time: t0/P de Barnard b–e, efeméride VSX de R Dra, por qué otras fases no se conocen
  spherexCoverage.ts ventanas de pasadas SPHEREx de los 5 blancos, agrupación de frames, línea "Real epoch"
  skyTrack.ts        trayectoria predicha en el cielo (movimiento espacial + paralaje)
  appearanceNotes.ts filas "How this body is drawn" / "At SPHEREx scale" de la ficha (carga diferida)
  DatasetTimeline.tsx, SkyTrackPanel.tsx   línea de tiempo y panel del cielo (React + SVG, carga diferida)
  viewerKit.ts       lo que el visor carga bajo demanda (leyendas, cobertura, efemérides)
  datasetGate.ts, viewerLink.ts, kindLabels.ts   piezas chicas sin astro/three (van en el chunk principal)
  SystemScene.ts     escena three.js: cuerpos, órbitas, arcos/anillos de fase, flecha "toward Earth", cámara
frontend/src/components/SystemViewer.tsx   controles (play, velocidad, reloj, modo de color, toggle, órbitas, etiquetas)
frontend/src/components/BodyPanel.tsx      ficha del cuerpo (datos + fuente + verified + cómo se dibuja)
frontend/src/pages/SystemsPage.tsx         #/systems
frontend/src/pages/SystemPage.tsx          #/system/<id>[/<cuerpo>] (+ panel "Where SPHEREx should see it")
```

Modelo de datos (resumen; la fuente de verdad es `pipeline/errante/models.py`):

- `SystemModel`: `id`, `name`, `center` (RA/Dec), `motion` (`SpaceMotion`: distancia, paralaje, movimiento propio,
  velocidad radial), `field_id` (campo SPHEREx), `bodies[]`, `representation_note`, `provenance`.
- `Body`: `id`, `kind` (star, brown_dwarf, planet, asteroid, tno, disk…), `radius_km`, `mass_kg`, `teff_k`,
  `spectral_type`, `orbit` (`Orbit`: padre, a, P, e, i, Ω, ω, M₀, época, `quality`, `note`; `null` = cuerpo raíz), `variability`,
  `appearance` (`star | brown_dwarf | rocky | icy | gas_giant | disk | mesh`, `mesh_url`), `facts[]`, `candidate_id`.

## Derivaciones, niveles (tiers) y mapeos de visualización

Estado a 14/11/2026 en la rama `ws7/procedural-3d`. La fuente de verdad es el código (`frontend/src/three/`): la
ficha de cada cuerpo ("How this body is drawn" y "At SPHEREx scale", `appearanceNotes.ts`) muestra para ese cuerpo
el valor, el método, la cita y el tier de cada propiedad, leídos de los mismos módulos que usa la escena. Esta
sección es el resumen para el equipo; no se agregaron campos al contrato (0.2.1): lo que falta en `SystemModel`
vive en tablas WS7 del frontend, con fuente y tests.

**Tiers** (`astro.ts`, de más fuerte a más débil):

| Tier | Significa |
|---|---|
| `measured` | el valor dibujado coincide con un `Fact` verificado, reconocido por su etiqueta, que no dice "estimate/model/illustrative", dentro de su error citado más media unidad del último dígito (sin error: 1 %; 5 % solo si el valor lleva `~`) |
| `derived` | calculado solo desde entradas medidas con una relación exacta (L = 4πR²σT⁴, log g) |
| `model` | interviene un modelo o aproximación (cuerpo negro, μ = 1.3, atmósfera gris, albedo supuesto, órbita circular) o una entrada es un modelo |
| `range-pick` | un número elegido dentro de un rango publicado para **este** objeto (Teff 3000 K de R Dra dentro de ~2000–3300 K) |
| `class-typical` | típico de la clase de objeto, no medido en este objeto |
| `theory` | expectativa teórica (bloqueo de marea) |
| `illustrative` | ninguna fuente verificada respalda el valor |
| `display` | un mapeo de pantalla, nunca fotometría |

Un valor calculado toma la entrada más débil y nunca es más fuerte que el piso de su método (`derivedTier`). Los
tiers de arcos, anillos y fases en *Dataset time* no existen en el código: ahí se indica "predicción" o "arbitraria".

**Cuerpos** (escena 3D):

| Propiedad | Entrada | Método / fórmula | Cita (como en el código) | Tier | Qué NO se modela |
|---|---|---|---|---|---|
| Color · SPHEREx IR (`ir`, modo por defecto) | `teff_k` del catálogo | Por canal, brillo superficial medio en frecuencia ⟨I_ν⟩ = Σ∫B_λ dλ / ΣΔν de un cuerpo negro: azul = D1+D2 (0.746–1.65 µm), verde = D3+D4 (1.63–3.847), rojo = D5+D6 (3.811–5.01). Bordes = `em_min–em_max` de IRSA SIA. Los tres canales comparten un factor (conserva el color). Estiramiento logarítmico fijo de 10 mag por debajo del cuerpo × canal más brillante del sistema. Chip "FALSE COLOUR · BLACKBODY MODEL · SPHEREx 0.75–5 µm bands" | Planck (Rybicki & Lightman 1979); Lupton et al. 2004, PASP 116, 133; bandas: `docs/RECON_SPHEREX.md` §2.2 | `model` (o el de Teff si es más débil: R Dra `range-pick`); el nivel en pantalla es `display` | Bajo 2500 K solo tono cualitativo, sin números y con contorno punteado (Burrows, Sudarsky & Lunine 2003). Exceso IR de disco y acreción: RW Aur es 1.3–3.8 mag más brillante en D5/D6 que su fotosfera (RECON §4.4). Bandas H₂O/CO y polvo de la Mira (Höfner & Olofsson 2018). Emisión y luz reflejada de planetas y discos: se dibujan como contorno. Saturación y no linealidad. No es la imagen SPHEREx |
| Color · D1…D6 (gris) | `teff_k` | El mismo ⟨I_ν⟩ de un solo detector, en gris, estirado 10 mag por debajo del cuerpo más brillante del sistema en ese detector | ídem IR | `model` / `display` | ídem IR |
| Color · Visible | `teff_k` | Cuerpo negro sumado sobre las funciones CIE 1931 2° (360–830 nm, cada 5 nm) → XYZ → sRGB lineal D65, negativos recortados, normalizado al canal mayor. Brillo = clamp(1 + log10(Y(T)/Y(5772 K))/8, 0.05, 1) | CIE 018:2019 / ISO/CIE 11664-1:2019; IEC 61966-2-1:1999 | color `model`; brillo `display` | Enanas marrones: no se calcula, se dibujan neutras (Burrows, Marley & Sharp 2000). Planetas: gris neutro 18 % iluminado por la estrella (albedo y color desconocidos). Discos: neutros y translúcidos. Mira: bandas de TiO (Reid & Goldston 2002). El sistema sintético conserva su paleta a mano y el ajuste de Tanner Helland (`illustrative`) |
| Contorno (rim) | tipo de cuerpo y modo | Línea de 2 px en pantalla (`fwidth`) más caída de Fresnel; punteada (24 trazos) mientras el nivel IR es solo cualitativo | regla de display WS7 | `display` | No es luz emitida: solo ayuda a encontrar cuerpos oscuros |
| Tamaño en pantalla y distancias | `radius_km`, elementos orbitales | Radio visible = clamp(0.12 · R_km^0.18, 0.12, 2.2) unidades; `capRadii` impide que un cuerpo toque a su padre o a un hermano. Distancias comprimidas (lineales hasta el menor periastro = 3 unidades, +10 unidades por década) o en proporción real (toda la cadena en ~30 unidades) | convención de display WS7 (`appearance.ts`, `sceneLayout.ts`) | `display`; la ficha muestra el factor de exageración y el tier del radio | El tamaño real. R Dra (~250 R☉) es un valor ilustrativo; RW Aur A no tiene radio verificado. El radio desde el flujo SPHEREx y la distancia Gaia (`VISION.md`) todavía no existe (WS7-8, depende de WS3) |
| Limb darkening y enrojecimiento del borde | `teff_k` | Atmósfera gris de Eddington, T⁴(τ) = ¾Teff⁴(τ + ⅔), con Eddington–Barbier I(μ) ≈ B(T(τ = μ)); tabla de 16 valores de μ por canal. Visible: a través de las funciones CIE. IR: monocromático en el centro geométrico de cada canal (1.11 / 2.50 / 4.37 µm). D1–D6: en el centro del detector | Mihalas 1978, Stellar Atmospheres; Gray 2005 | `model`, con el tier de Teff incluido (R Dra `range-pick`) | Atmósferas moleculares reales (enanas M, Miras) y diámetros de Mira que cambian con λ. Bajo 2500 K no se calcula (disco plano) |
| Celdas de convección (granulación) | `teff_k`, `mass_kg`, `radius_km` | Celdas a lo ancho = 2R / (10 H_p), con H_p = kTeff / (μ m_H g), μ = 1.3, g = GM/R². Se dibujan solo si son menos de 64. Renovación τ = x / (5 km/s) en tiempo de modelo. Ruido celular sembrado con el id del cuerpo | Trampedach et al. 2013; Freytag et al. 2017; Schwarzschild 1975 (celdas gigantes); H_p: Gray 2005 | tamaño `model`, con el tier de sus entradas; contraste ±15 % `illustrative` | Hoy solo R Dra resulta resoluble (≈8 celdas), con la masa class-typical ~1 M☉ (Feast 2009, sin verificar) y el radio ilustrativo. La ubicación de cada celda es ruido, no una observación. **Solo con el toggle class-typical (apagado por defecto): no observadas en R Dra** (clase: celdas gigantes vistas en π¹ Gru, Paladini et al. 2018) |
| Glow | L = 4πR²σT⁴ × fracción de cuerpo negro en la banda del modo (visible 380–780 nm; IR 0.746–5.01 µm; o el detector) | Tamaño del sprite = radio visible × (2 + 3n), con n = 1 + log10(L/L_max)/4 acotado a [0, 1]. Opacidad = nivel de display. En modo visible la curva V lo modula: opacidad × f^0.25, tamaño × f^0.3 (f = flujo / flujo medio) | convención de display WS7 (`colorModes.ts`) | `display` | Ninguna curva de luz IR: en los modos SPHEREx el glow es fijo. No es un halo físico |
| Pulsación (radio y brillo) · R Dra | `variability` (P, 6.5 mag en V); en *Dataset time*, la efeméride VSX | Radio 1 ± 0.10 (≈20 % pico a pico del diámetro del continuo). *Free-running*: radio 1 − 0.1·sin(2π(MJD − 51544.5)/P) y f = 10^(−0.4·(A/2)·sin(…)), con P = 245.6 d (GCVS) y fase arbitraria (cero en J2000). *Dataset time*: forma asimétrica s(φ) de medios cosenos que sube en el 45 % del ciclo (mínimo en φ = 0.55); radio 1 + 0.1·s y f = 10^(0.2·A·s) | Ireland et al. 2004, MNRAS 350, 365; Woodruff et al. 2004, A&A 421, 703; GCVS 5.1 (Samus et al. 2017); AAVSO VSX | amplitud `class-typical`; fase arbitraria (*Free-running*) o predicción V de catálogo (*Dataset time*) | Tamaño en fase con la luz solo por display (no se modela su relación de fase). Amplitud IR (menor) y retraso de los máximos IR. Cambios ciclo a ciclo. La Teff queda fija en 3000 K aunque cambia con la fase. No es una curva de luz SPHEREx. Las variables irregulares (RW Aur A/B) no se animan |
| Rotación (spin) | `rotation_period_hours` con su `Fact`, o la regla de marea | Ángulo = 2π · 24 · (MJD − 51544.5) / P_h (fase rotacional desconocida, cero en J2000), eje dibujado vertical; se congela si avanzaría más de 90° por cuadro (aliasing). Marea: un planeta con P_orb < 10 d alrededor de una enana M muestra siempre la misma cara | Toledo-Padrón et al. 2019, MNRAS 488, 5145 (Barnard, 145 ± 15 d); Barnes 2017, Celest. Mech. Dyn. Astron. 129, 509 | Barnard `measured`; Barnard b–e `theory` | Orientación del eje y fase rotacional. No giran: ε Ind A (períodos publicados de ~18, 22 y 36 d, discordantes), RW Aur A (solo un candidato de ~5.6 d), WISE 0855 (período no determinado), ε Ind Ba/Bb (no medidos) |
| Superficie | — | Esfera lisa por defecto. Toggle "show class-typical features (illustrative)", **apagado por defecto**, con chip "CLASS-TYPICAL FEATURES · ILLUSTRATIVE". Dibuja solo la lista S5: bandas nubosas irregulares en enanas marrones L9–T3.5 (ε Ind Ba, T1) y bandas zonales en gigantes gaseosos (ε Ind Ab), ±15 % alrededor del brillo medio (elección de dibujo) | Radigan et al. 2014, ApJ 793, 75; Metchev et al. 2015, ApJ 799, 154; Apai et al. 2017, Science 357, 683; Vasavada & Showman 2005; Showman & Kaspi 2013 | `illustrative` | Ningún mapa de superficie medido. Sin patrón en ε Ind Bb (T6), WISE 0855 (Y) ni Barnard b–e: no se revisó una fuente de clase para ellos. En los modos IR los planetas son contorno, así que sus bandas solo se ven en visible. El sistema sintético conserva sus texturas procedurales |
| Iluminación | colores del modo activo | Las estrellas no se iluminan (shader propio) y llevan una luz puntual de su tono, con intensidad normalizada (sin 1/r²). Planetas: gris 18 % iluminado en visible, contorno en los modos SPHEREx. Enanas marrones: autoluminosas, sin iluminar | convención de display WS7 | `display` | Albedo, fases de iluminación reales, luz reflejada entre cuerpos |
| Órbitas (geometría) | `Orbit`: a, P, e, i, Ω, ω, M₀, `epoch_mjd`, `quality` | Kepler de dos cuerpos (Newton–Raphson), rotación 3-1-3, jerarquía padre → hijo sin baricentros. Color según `quality`: ajustada (azul grisáceo), `assumed` (amarillo), `hypothetical` (violeta) | fuentes por dato en `catalog.py` | el de los `Fact` de a y e; una órbita `assumed` da `illustrative` y el flag `assumed-orbit` | Baricentros y perturbaciones. La inclinación real de los planetas por velocidad radial (se dibujan en el plano de referencia, i = 0). El sentido de giro en el cielo (se dibuja antihorario visto desde arriba) |

**Tiempo y posiciones** (detalle en la sección siguiente):

| Propiedad | Entrada | Método / fórmula | Cita (como en el código) | Tier | Qué NO se modela |
|---|---|---|---|---|---|
| Fase orbital en *Dataset time* · Barnard b–e | t0 y P con 1σ (tabla `ORBIT_EPHEMERIDES` y `Orbit.epoch_mjd`) | `epoch_mjd` = t0 − 2400000.5; M = 270° en t0. Arco de 64 puntos sobre ±2σ de anomalía media, con σφ = √(σt0² + N²σP²)/P y N = (t − t0)/P; si σφ > 0.5 ciclo, anillo | Basant et al. 2025, ApJL 982, L1, Tabla 3 (arXiv:2503.08095); propagación lineal (Taylor 1997; Zellem et al. 2020, PASP 132, 054401); cuantiles normales de Acklam 2003 | predicción; t0 y P son `Fact` verificados por su valor, la convención (conjunción) es una lectura nuestra | La covarianza t0–P (no publicada). La inclinación y el sentido de giro |
| Fase orbital en *Dataset time* · sin época | `Orbit.epoch_mjd = null` | Cuerpo atenuado (× 0.35), sufijo "(phase unknown)", anillo de 64 puntos uniformes en anomalía media | `UNKNOWN_PHASE_REASONS` (Sanghi et al. 2026; Chen et al. 2022; Kurtovic et al. 2024) | arbitraria | Cualquier posición en una fecha real |
| Fase de pulsación en *Dataset time* · R Dra | efeméride VSX (tabla `MIRA_EPHEMERIDES`) | φ = frac((t − E0)/P), 0 = máximo; banda de 1σ = 6.6 d | AAVSO VSX R Dra (oid 13673, revisión 4, 2024-01-18); O−C de T. Karlsson, "Maxima of Mira stars" (var.saaf.se) | predicción V de catálogo | Término de Eddington–Plakidis, curva IR, curva de luz SPHEREx |
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
- Banda de tiempo (1σ) de cada máximo predicho = RMS del O−C de los máximos observados 2015–2024 respecto de VSX =
  √(4.7² + 4.6²) ≈ **6.6 d** (media −4.7 d, desvío 4.6 d; lista de T. Karlsson). Las fechas no se corren por la
  media: la banda la incluye. Sin un término de Eddington–Plakidis con fuente, la banda **subestima** la
  incertidumbre (el período además deriva en décadas).
- Máximos predichos dentro del dataset: 2025-05-20, 2026-01-21 y 2026-09-24 (± 6.6 d). Fase 0.90 el 2025-04-24 y
  0.04 el 2026-10-05: ~2.1 ciclos en el dataset. Una estimación propia del máximo de 2026-01 con datos de la base
  AAVSO (no publicada y no usada en el código) cae ~14 d antes de la fecha VSX, ~2σ con esta banda.
- Leyenda: "V-band prediction from a catalogue ephemeris; IR amplitude is smaller and IR maxima lag the visual ones;
  not a SPHEREx light curve". El glow sigue la curva solo en modo visible.
- Una sola regla de variabilidad (`variabilityPhase`) para la línea de tiempo, "On this date", la línea de estado y
  la escena: `irregular` (RW Aur A y B: "irregular: cannot be predicted - look at the frames", nunca una curva),
  `predicted` (periódica con efeméride WS7: hoy solo R Dra) y `unknown` (el resto, congelado en el brillo medio con
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
  velocidad radial: el centro del sistema es A, pero el campo y la cobertura son de B. WISE 0855 usa Kirkpatrick et al.
  2021 (época MJD 57633.39), sin velocidad radial; el ajuste propio de RECON §4.1 da un lugar a 0.31″ (0.05 px) el
  2026-11-14.
- En *Dataset time* el panel marca además el lugar predicho en la fecha del 3D (`SystemViewerContext`).
- No se modela: el bamboleo del fotocentro Ba–Bb (< 1.02″ = 0.17 px), el `MJD-AVG` de cada frame (los frames de una
  pasada se reparten sobre el "drift" mostrado, hasta 0.3 px en Barnard), la fase de píxel y orientación por frame, ni
  la saturación (Barnard en D1–D4, R Dra en todas). La estrella de campo estática junto a WISE 0855 (Gaia DR3
  5756956644387831296) sí se muestra.

### Diferencias con `VISION.md` que siguen abiertas

`VISION.md` pide que cada valor del 3D salga de una medición y que lo no medido no se dibuje. Hoy se cumple para
superficies (esferas lisas; toggle class-typical apagado y marcado ILLUSTRATIVE), spin y fases. No se cumple todavía:

1. el color sale de la Teff de catálogo, no del ajuste del espectro SPHEREx (WS7-8, depende de WS3);
2. el radio es de catálogo, no de la luminosidad SPHEREx + distancia Gaia;
3. la pulsación es una curva V de catálogo, no la curva de luz SPHEREx;
4. (resuelto) las celdas de convección de R Dra quedaron detrás del toggle class-typical, apagado por defecto: la vista
   por defecto es una esfera lisa, como pide `VISION.md`.

## Próximos pasos (ver tareas)

WS7-1 integrar con el flujo principal · WS7-2 verificar valores contra catálogos · WS7-3 órbitas reales de
asteroides desde SBDB para los candidatos `known` · WS7-4 pulido visual (limb darkening, nubes, anillos, brillo
de la Mira) · WS7-5 vista "moverse por el espacio" (paralaje + movimiento propio: por qué Barnard se mueve tanto)
· WS7-6 modelos de forma reales · WS7-7 Planeta Nueve hipotético · WS7-9 tiempo del dataset SPHEREx
(implementado en la rama; faltan la aceptación de M5 por el equipo y la revisión visual).
