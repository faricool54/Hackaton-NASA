# Visión 3D: de un punto que se mueve a un sistema que se puede explorar

> Workstream **WS7**. Estado: **esqueleto funcional** — `#/systems` y `#/system/<id>[/<cuerpo>]` ya andan con
> modelos 3D de los 5 objetivos de prueba del reto + un sistema sintético. Tareas en
> [tasks/WS7-3d-systems.md](../tasks/WS7-3d-systems.md).

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
  arbitrarias: el visor muestra tiempo transcurrido, no una fecha "predicha".
- Lo sintético sigue llevando el badge **SYNTHETIC DATA** (`provenance.synthetic`).
- Simplificaciones explícitas: jerarquías sin baricentros (Epsilon Indi), variabilidad sinusoidal, radios
  estimados de planetas no transitantes. Cada una figura en `provenance.notes` o en la etiqueta del dato.

## Qué representan los presets (verificados en WS7-2, 2026-11-14)

Cada valor se comprobó en la fuente y quedó en `catalog.py` con la cita exacta; `systems/sources.py` reproduce
las consultas y los tests `network` de `test_systems.py` las vuelven a correr. Posiciones y movimientos en la
época de la fuente (Gaia DR3 = J2016.0), no en J2000.

| Objetivo | Qué se modela | Fuentes usadas | Correcciones respecto de los valores tipeados |
|---|---|---|---|
| **Barnard's Star** | M4V + 4 planetas (P 2.34–6.74 d, masa mínima 0.19–0.34 M⊕; órbitas circulares) | Exoplanet Archive (González Hernández+2024, Basant+2025), Gaia DR3 4472832130942575872 | RV −110.47 km/s (Gaia DR3); centro y época → J2016.0 |
| **Epsilon Indi** | K5V + Ab (6.5 M♃, a 15.8 AU, e 0.25) + Ba/Bb (T1/T6, P 11.02 a, e 0.54) | Exoplanet Archive (Sanghi+2026), Matthews+2024, Chen+2022, Scholz+2003, Gaia DR3 | Ab: el ajuste vigente (Sanghi+2026) reemplaza a Matthews+2024 (28 AU, e 0.4); masa de A 0.80; Teff 4700 K |
| **WISE 0855−0714** | enana marrón aislada, ~285 K, ~Y4 | Kirkpatrick+2021 (paralaje/movimiento), Luhman+2024 (JWST) | movimiento propio −8123.7/+673.2 mas/a; las coordenadas del enunciado son WISE All-Sky **época 2010.34**, no J2014 |
| **R Draconis** | Mira, P 245.6 d, V 6.7–13.2 (animación sinusoidal ilustrativa) | GCVS 5.1, AAVSO VSX, Gaia DR3, Bailer-Jones+2021, van Belle+2002, McDonald+2012 | Teff como rango 2000–3300 K (cambia con la fase); se agregó movimiento (~790 pc) |
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
       │  errante demo  → data/demo/systems/*.json      errante systems → data/products/systems/*.json
       ▼
contrato: SystemModel (models.py, schema 0.2.1) · Manifest.systems · GET /api/systems/{id}
       ▼
frontend/src/three/             (WS7, three.js en un chunk aparte, carga diferida)
  orbits.ts       Kepler (posición en el tiempo, elipse), orden padre→hijo, variabilidad   [tests]
  appearance.ts   temperatura → color, distancias comprimidas, radios visibles              [tests]
  SystemScene.ts  escena three.js: cuerpos procedurales, órbitas, etiquetas, clic, cámara que sigue
frontend/src/components/SystemViewer.tsx   controles (play, velocidad, distancias, órbitas, etiquetas)
frontend/src/components/BodyPanel.tsx      ficha del cuerpo (datos + fuente + verified)
frontend/src/pages/SystemsPage.tsx         #/systems
frontend/src/pages/SystemPage.tsx          #/system/<id>[/<cuerpo>]
```

Modelo de datos (resumen; la fuente de verdad es `pipeline/errante/models.py`):

- `SystemModel`: `id`, `name`, `center` (RA/Dec), `motion` (`SpaceMotion`: distancia, paralaje, movimiento propio,
  velocidad radial), `field_id` (campo SPHEREx), `bodies[]`, `representation_note`, `provenance`.
- `Body`: `id`, `kind` (star, brown_dwarf, planet, asteroid, tno, disk…), `radius_km`, `mass_kg`, `teff_k`,
  `spectral_type`, `orbit` (`Orbit`: padre, a, P, e, i, Ω, ω, M₀, época, `quality`, `note`; `null` = cuerpo raíz), `variability`,
  `appearance` (`star | brown_dwarf | rocky | icy | gas_giant | disk | mesh`, `mesh_url`), `facts[]`, `candidate_id`.

## Próximos pasos (ver tareas)

WS7-1 integrar con el flujo principal · WS7-2 verificar valores contra catálogos · WS7-3 órbitas reales de
asteroides desde SBDB para los candidatos `known` · WS7-4 pulido visual (limb darkening, nubes, anillos, brillo
de la Mira) · WS7-5 vista "moverse por el espacio" (paralaje + movimiento propio: por qué Barnard se mueve tanto)
· WS7-6 modelos de forma reales · WS7-7 Planeta Nueve hipotético.
