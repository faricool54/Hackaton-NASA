# Visión 3D: de un punto que se mueve a un sistema que se puede explorar

> Workstream **WS7**. Estado: **esqueleto funcional** — `#/systems` y `#/system/<id>[/<cuerpo>]` ya andan con
> modelos 3D de los 5 objetivos de prueba del reto + un sistema sintético. Tareas en
> [tasks/WS7-3d-systems.md](../tasks/WS7-3d-systems.md).

**Extensión P2**, posterior al recorrido obligatorio RA/Dec → imágenes reales → animación y ensayos.
Las guías de entrega y evaluación exigen evidencia, honestidad y atribución: `REQUIREMENTS.md`,
`SUBMISSION_GUIDE.md` y `JUDGING_GUIDE.md`. La galería ya existe, pero no valida R02/R05 ni aporta por sí
misma integración real de datos NASA para Relevance. El código llegó en la contribución WS7; parámetros
de catálogo y procedencia completa siguen pendientes de revisión.

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
  **"unverified"** y el sistema muestra el badge **"UNVERIFIED VALUES"**. Hoy **todos** los valores reales están
  tipeados a mano como punto de partida → WS7-2 los verifica.
- Lo que no sabemos no se dibuja como si lo supiéramos: cada órbita declara `Orbit.quality`. `assumed` (no
  ajustada: un círculo a la separación proyectada o a una distancia estimada) se dibuja **en amarillo** y la ficha
  dice "assumed, not fitted"; `hypothetical` (p. ej. Planeta Nueve) en violeta. Las fases sin época son
  arbitrarias: el visor muestra tiempo transcurrido, no una fecha "predicha".
- Lo sintético sigue llevando el badge **SYNTHETIC DATA** (`provenance.synthetic`).
- Simplificaciones explícitas: jerarquías sin baricentros (Epsilon Indi), variabilidad sinusoidal, radios
  estimados de planetas no transitantes. Cada una figura en `provenance.notes` o en la etiqueta del dato.

## Qué representan los presets actuales (sin validar científicamente)

| Objetivo | Qué se puede modelar | Fuente para verificar (WS7-2) |
|---|---|---|
| **Barnard's Star** | estrella y compañeros planetarios ilustrativos; existencia/parámetros del preset a contrastar | NASA Exoplanet Archive, Gaia DR3 |
| **Epsilon Indi** | estrella, compañero planetario y componentes Ba/Bb con jerarquía simplificada; distinguir B de A | NASA Exoplanet Archive, SIMBAD, literatura |
| **WISE 0855−0714** | cuerpo aislado ilustrativo; temperatura, masa y astrometría sin verificar | SIMBAD, Luhman et al. 2024 (JWST), Kirkpatrick et al. 2021 (paralaje) |
| **R Draconis** | modelo de pulsación, no curva de luz SPHEREx medida | AAVSO VSX / GCVS |
| **RW Aurigae** | binaria joven A+B con disco alrededor de A; atenuaciones irregulares | SIMBAD, literatura |
| Asteroides / TNOs del pipeline | órbita heliocéntrica real (elementos osculantes) + forma si existe | JPL SBDB, NASA 3D Resources, DAMIT |
| Planeta Nueve (P2, opcional) | órbita **hipotética** con `Orbit.quality = "hypothetical"`; parámetros a revisar antes de mostrar | Brown & Batygin 2021 (AJ 162, 219), a verificar |

Lo que **no** sale de SPHEREx: las órbitas y parámetros físicos vienen de catálogos. SPHEREx aporta *dónde está y
cómo se mueve en el cielo*, su **espectro 0.75–5 µm** y su variabilidad; la vista 3D lo pone en contexto.
En la versión actual esos productos SPHEREx reales aún no se generaron. Las fuentes de la tabla son
destinos de verificación, no constancia de una consulta ya realizada ni evidencia de parámetros correctos.

## Cómo está armado

```
pipeline/errante/systems/       (WS7)
  catalog.py   sistemas curados (hoy tipeados a mano, verified=False) + sistema sintético del demo
  sources.py   stubs: NASA Exoplanet Archive (TAP), JPL SBDB, SIMBAD/Gaia, modelos de forma
  build.py     valida jerarquía (padres existen, sin ciclos) y escribe <root>/systems/<id>.json
       │  errante demo  → data/demo/systems/*.json      errante systems → data/products/systems/*.json
       ▼
contrato: SystemModel (models.py, schema 0.3.0) · Manifest.systems · GET /api/systems/{id}
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
