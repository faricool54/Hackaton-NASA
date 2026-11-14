# El reto: "Planet X and SPHEREx" (NASA Space Apps Challenge 2026)

> **Dueño: WS6.** El plan vigente está en [`PLAN.md`](PLAN.md); la evidencia de la revisión, en
> [`REVIEW-2026-11-14.md`](REVIEW-2026-11-14.md). Estados: ✅ verificado 2026-11-14 · 📄 según documentación ·
> ❓ abierto.
>
> Contenido: §1 texto oficial (inglés, textual) · §2 qué pide, en español · §3 reglas y entrega verificadas ·
> §4 trazabilidad requisito → plan · §5 referencias útiles.

---

## 1. Texto oficial (copia textual)

Copiado el **2026-11-14** (sáb, ~11:30 UTC−3) de
https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/ (pestañas *Details* y *Resources*) ✅.
Se respeta la ortografía original, incluido el typo "Astrophy tools" del original.
**Difficulty:** Advanced · **Subjects:** Astrophysics, Planets & Moons, Software.

### Summary

Since 2025, NASA’s SPHEREx mission has been mapping the entire sky every six months in 102 bands of
near-infrared light, returning images of more than a billion objects. Comets, asteroids, stars, brown dwarfs,
and even new planets reveal themselves by shifting position between images, but no one person can sift through
all that data alone. Your challenge is to create a public-facing web tool to display images of the sky from
SPHEREx mission, making it easy for anyone to quickly see how they change over time.

### Background

Asteroids and comets orbit around the Sun. Nearby stars march across the sky as they orbit around the Galaxy.
The Earth orbits the Sun too, causing objects near us to change their apparent positions. Watching for these
motions help us discover new astronomical objects and also help measure the distances to these objects. For
example, the dwarf planet Pluto was discovered when an astronomer compared two images of the sky taken at
different times and recognized that one point of light had shifted between images.

More recently, astronomers have mounted massive searches for nearby objects using this process with help from
the public. Hundreds of thousands of volunteers have used this technique to discover asteroids, comets, stars
and brown dwarfs—balls of gas too massive to be considered planets yet without enough mass to burn like stars.
In fact, most of the known comets and brown dwarfs were discovered by volunteers in this manner through
projects like [backyardworlds.org](http://backyardworlds.org/).

Since May 2025, NASA’s new SPHEREx mission has been returning unique data that could yield new discoveries.
SPHEREx is mapping the whole sky once every six months in 102 bands of near-infrared light, making it uniquely
sensitive to objects that are rich in hydrogen, water, carbon dioxide, carbon monoxide, and many other
molecules. There will be too much data for any one person or even computer code to completely comprehend.
There will be images of more than a billion objects - including brown dwarfs, quasars, comets, asteroids,
stars, supernovae and galaxies - which often overlap or vary in brightness. We need your creative new tools to
make the most of this treasure trove and help as many people as possible pitch in to make discoveries.

### Objectives

Your challenge is to create a public-facing web tool to display images of the sky from the SPHEREx mission,
making it easy for anyone to quickly see how they change over time. Users will enter the coordinates of a patch
of sky (Right Ascension and declination). Your tool will display a series of images of that patch like a
little video, making it easy to spot moving objects.

Test your tool on Barnard’s Star, Epsilon Indi B (a pair of brown dwarfs orbiting a star), WISE 0855 (a
fast-moving brown dwarf Right Ascension 08h55m10.831s, declination -7d14m42.53s), and variable stars RW Aurigae
and R Draconis.

### Potential Considerations

You may (but are not required to) consider the following:

- New SPHEREx data is arriving fast! Make sure to design a tool that’s easy to update with the latest data
  releases.
- Think creatively about how to display those 102 infrared bands so users can take advantage of them to make
  new discoveries! For example, it may make sense to separately add together all the data taken by each of the
  six detector arrays to improve the signal-to-noise in the images you display. Extra kudos if your tool can
  generate spectra on the fly.
- It may help users discover moving objects if they have the options to add together or subtract images taken
  at different times.
- Let users choose the field of view! Larger fields of view can make it possible to track faster-moving
  sources, at the cost of longer data transfer times.
- Users could benefit from having the option to overlay astronomical data from other telescopes, such as the
  Gaia mission or the WISE mission.
- If you make it possible to query your tool by including coordinates in the URL, users will be able to easily
  embed it in other websites and projects.
- It can be useful to display metadata, like contamination flags.
- Consider looking for publicly available tools that may help in handling astronomical data, like the Astrophy
  tools, and in displaying astronomical data, like the Aladin tool developed by the Strasbourg Astronomical Data
  Center (CDS).

For data and resources related to this challenge, refer to the Resources tab at the top of the page. More
resources may be added before the hackathon begins.

### Resources (pestaña *Resources*)

*NASA does not endorse any non-U.S. Government entity and is not responsible for information contained on
non-U.S. Government websites. For non-U.S. Government websites, participants must comply with any data use
parameters of that specific website.*

**NASA Data & Resources**

- [NASA/IPAC Infrared Science Archive](https://irsa.ipac.caltech.edu/Missions/spherex.html): SPHEREx resources
- [SPHEREx Tutorial Notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/): Example Jupyter
  notebooks for how to access the SPHEREx data via Python.
- [WiseView](http://byw.tools/wiseview): A similar tool made for viewing data from an earlier NASA mission
  called WISE. It’s been used by the public to make hundreds of discoveries. Feel free to use it as a model or
  as inspiration!
- [Gaia Mission Data](https://archive.stsci.edu/missions-and-data/gaia): Be sure to use the latest data release
  (Data Release 3).

**Space Agency Partner Resources — CSA (Canadian Space Agency)** *(títulos y links textuales; descripciones de
la CSA resumidas en español)*

- [NEOSSat: Observing Asteroids, Space Debris and Exoplanets](https://www.asc-csa.gc.ca/eng/satellites/neossat/)
  — telescopio espacial canadiense dedicado a detectar y seguir asteroides, cometas, satélites y basura espacial.
- [Canadian Astronomy Data Centre (CADC)](https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/) — archivo de
  observaciones de telescopios y misiones canadienses e internacionales.
- [NEOSSat Data Tutorial](https://github.com/asc-csa/NEOSSAT_Tutorial) — tutorial en Python para acceder y
  visualizar datos de NEOSSat.
- [NEOSSat Dataset](https://data.asc-csa.gc.ca/dataset/neossat) — observaciones de NEOSSat (asteroides,
  cometas, satélites, basura espacial).

---

## 2. Qué pide, en español

### Objetivo central

Una **herramienta web pública** donde **el usuario ingresa RA/Dec** de un parche de cielo y ve **la serie de
imágenes SPHEREx de ese parche "como un pequeño video"**, para que sea fácil **ver lo que se mueve** (y cambia).
Está pensada para **personas** (ciencia ciudadana, como Backyard Worlds y WiseView), no para un detector
automático. "Planet X" aparece solo en el título: el texto se apoya en Plutón, Backyard Worlds y las enanas
marrones ✅. En el plan, el Planeta X queda como **motivación narrativa** ([`PLAN.md`](PLAN.md) §1.8).

### Los 5 objetivos de prueba

Todos tienen cobertura SPHEREx (DR1+QR3) ✅. Movimientos propios de Sesame CfA ✅; los desplazamientos en píxeles
son cálculo propio sobre la línea de base real (píxel 6.15″), corregidos por la crítica final ✅.

| Objetivo | Qué es | Frames SPHEREx ✅ | Qué esperar |
|---|---|---|---|
| Barnard's Star | estrella con gran movimiento propio (10.39″/año) | 358 (dr1 239 + qr3 119), ~3 temporadas | **1.86 px** en 1.10 años |
| Epsilon Indi B | par de enanas marrones que orbitan eps Ind A | 458–460 (según TAP/SIA), 4 temporadas | **1.10 px** en 1.44 años. El par **no se resuelve** con píxeles de 6.15″: SPHEREx ve una sola fuente (decirlo en la UI). eps Ind A, muy brillante, está a 402″ (sirve para mostrar flags) |
| WISE 0855 | enana marrón muy fría y rápida (8.15″/año) | 258, **solo DR1** | **1.36 px** en 1.02 años. La coordenada del enunciado es de ~2010: hoy está **~126″ al oeste** → centrar en la posición propagada. Que solo se vea en D5/D6 es INFERIDO ❓ (hace falta un spike medido) |
| RW Aurigae | estrella variable (T Tauri) | 335, 3 temporadas | **no se mueve: cambia de brillo** |
| R Draconis | estrella variable (Mira), a 8.6° del polo norte eclíptico | 2493 (incluye `*_deep`) | **no se mueve: cambia de brillo**; mucha cobertura, la mejor candidata para curva de luz |

**Trampa del filtro variable (LVF):** dentro de una temporada cada exposición mide otra longitud de onda, así que
una estrella constante "parpadea". Por eso el video se arma con **coadds por temporada × detector**
([`PLAN.md`](PLAN.md) §1.4). Que con eso la variabilidad de RW Aur y R Dra se vea bien es INFERIDO ❓: hay que
validarlo con datos.

### Las 8 consideraciones (opcionales: "may, but are not required to")

| # | Consideración | En concreto |
|---|---|---|
| C1 | Fácil de actualizar con nuevos releases | colecciones configurables, sin rutas ni versiones de pipeline hardcodeadas |
| C2 | Mostrar las 102 bandas de forma creativa | sugiere **co-sumar por cada uno de los 6 detectores** (más S/N); *extra kudos* si genera **espectros al vuelo** |
| C3 | Sumar o restar imágenes de distintas épocas | suma de épocas elegidas, resta A − B |
| C4 | Que el usuario elija el campo de visión (FOV) | FOV grande = sigue objetos más rápidos, pero más transferencia |
| C5 | Superponer datos de otros telescopios | Gaia, WISE |
| C6 | Coordenadas en la URL | consultable y **embebible** en otros sitios |
| C7 | Mostrar metadata | por ejemplo, **flags de contaminación** |
| C8 | Usar herramientas públicas | Astropy (datos), Aladin del CDS (visualización) |

**Principio que se mantiene:** nunca afirmar un descubrimiento. "Sin match en catálogos" ≠ "objeto nuevo"
(ver [`SCIENCE.md`](SCIENCE.md)).

---

## 3. Reglas y entrega (verificadas)

Fuentes, todas leídas el **2026-11-14** ✅:
[Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) ·
[Judging & Awards Guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/) ·
[Participant FAQs](https://www.spaceappschallenge.org/resources/participant-faqs/) ·
[Página 2026](https://www.spaceappschallenge.org/2026/).
Todo lo que sigue es ✅ salvo que diga otra cosa.

### 3.1 Fechas y plazos

- **El envío abre el sáb 14/11 a las 9:00 y cierra el dom 15/11 a las 23:59, hora del Local Event.** En el
  Universal Event cuenta la hora local de residencia del Team Owner.
- Se puede **editar y reenviar** cuantas veces se quiera hasta el cierre. Los jueces ven **solo el último envío
  guardado**. Lo guardado o enviado después del cierre no es elegible.
- El juzgamiento y los premios **locales** pueden tener otro horario: lo define el/la **Local Lead**.
  ❓ **Abierto:** zona horaria del Local Event y si hay presentación o juzgamiento local (preguntar en el kickoff).
- Si el Local Event está en UTC−3, al sáb 11:40 quedan ~36 h. Nuestro plan apunta a *Submit for Judging* el
  **dom 20:00** ([`PLAN.md`](PLAN.md) §5).

### 3.2 Equipo y elegibilidad

- Máximo **6 integrantes** (nosotros somos 5). En un Local Event alcanza con 1 persona.
- **Todos** (Team Owner incluido) tienen que estar registrados y **confirmados en el mismo Local Event** (no en
  lista de espera) y figurar en la pestaña *Members* del equipo. **No se pueden agregar integrantes después del
  cierre.**
- El proyecto tiene que responder a uno de los retos oficiales. Una persona puede estar en un solo equipo y
  cada equipo trabaja en un solo reto.

### 3.3 Formulario (pestaña *Project* del equipo)

**Todo el contenido del formulario va en inglés**, y también **"any linked materials"**: si el link al proyecto
es el repo, el README tiene que estar en inglés (o usar como link la URL del sitio). Borrador:
[`submission/PROJECT.md`](submission/PROJECT.md).

| Campo obligatorio | Qué va |
|---|---|
| Project Name | nombre del proyecto |
| High-Level Project Summary | qué desarrollamos, cómo responde al reto, por qué importa |
| Link to Project Demo | video o deck público (ver §3.4) |
| Link to Final Project | sitio, repo u otro hosting **público** |
| Detailed Project Description | qué hace exactamente, cómo funciona, beneficios, qué queremos lograr, herramientas y lenguajes usados |
| Use of Super Intelligence (SI) | si usamos SI y cómo (ver §3.5) |
| NASA Data | qué datos y recursos NASA usamos, con detalle |
| Space Agency Partner Data and Other References | **todos** los datos, recursos y herramientas usados (código, texto e imágenes, aunque sean libres) |

- Para enviar: tildar **"Terms and Conditions"** y **"Confirm All Work is Original"**, y apretar **"Submit for
  Judging"**. Si falta un campo obligatorio, no deja enviar. Si salió bien, aparece un banner de confirmación.
- La página admite imágenes **JPG, PNG o GIF de hasta 10 MB**. No admite videos ni documentos: van como link.
- Guardar seguido con **"Save Progress"**. Usar el **"Lock"** de edición para no pisarse (otra persona puede
  quitarlo, así que hay que coordinar).
- **Links públicos**: sin contraseña, sin pedir permiso y sin registro. Probarlos en una ventana de incógnito.
- Recomendado, no obligatorio: si publicamos un sitio nuevo, pedir la clasificación **FortiGuard Web Filter**
  para que los jueces no lo encuentren bloqueado (el procedimiento está en la guía de entrega).
- Lista de *Space Agency Partners* 2026: incluye a **ESA** (Gaia), a la **CSA** (los recursos del reto) y a la
  *National Space Activities Commission of Argentina*. La guía alienta usar sus datos.

### 3.4 Demo

- **Video de 30 s o menos, o deck de hasta 7 slides** (contando título e intro). Cita de la guía: *"Projects that
  exceed these limits will not be eligible for Global Judging."*
- Se aloja afuera (YouTube, Google Drive, GitHub, etc.) con link público. No se puede subir a la web de Space
  Apps.
- Idioma: inglés. Un **video hablado en otro idioma tiene que tener subtítulos en inglés**. El deck, en inglés.
- Estructura sugerida del video: **[0:00]** quiénes somos y nombre del equipo · **[0:02]** qué reto y por qué ·
  **[0:05]** nombre del proyecto y tagline · **[0:10]** la idea: cómo funciona, imágenes o prototipo,
  experiencia de uso y cómo los datos abiertos de NASA y de las agencias socias lo hacen posible ·
  **[0:20–0:30]** el futuro. Plantilla: [`submission/PITCH.md`](submission/PITCH.md).
- El deck tiene que incluir: nombre del equipo, nombres de los integrantes, el reto elegido, una imagen del
  proyecto, la experiencia de usuario y cómo los datos NASA y de agencias socias lo hacen posible.
- La demo pesa sobre todo en *Presentation*. El grueso de la evaluación sale de la página del proyecto.
- **Personas menores de 18 años:** prohibido incluir imágenes, video, audio o cualquier semejanza suya en la demo
  o en el proyecto.

### 3.5 Super Intelligence (SI) y branding

- "SI" es el término oficial para lo que antes se llamaba IA: lo dispone una orden ejecutiva de EE. UU. del
  29/09/2026 (FAQ). Incluye LLMs, asistentes de chat, generadores de imagen y video, y generadores de código.
- **Está permitido** usarla como herramienta. Pero **no para idear la solución**. Cita de la guía: *"SI should
  not be used to (come up with your idea of how to solve the challenge)."*
- Hay que indicar dónde y cómo se usó:
  - **imágenes y videos** generados con SI: **marca de agua visible**;
  - **audio**, **código y datos**: reconocerlo en **texto descriptivo y metadata**.
- La respuesta del campo SI **no la ven los jueces**, pero sí ven los indicadores dentro del proyecto (marcas de
  agua, textos, metadata).
- **Branding:** el contenido generado no puede usar, contener ni modificar **branding de NASA** (logos, banderas,
  identificadores de misión). Para nosotros: ni logo NASA ni parche de SPHEREx; los créditos van **solo en
  texto**.
- Material con copyright: hace falta permiso. Todo recurso usado se lista en *Other References*.
- **Cómo lo aplicamos:** sección "Use of SI" en el [README](../README.md), trailer `Co-Authored-By:` en los
  commits hechos con agentes, y la idea, el nombre y el tagline escritos por el equipo en el kickoff
  ([`KICKOFF.md`](KICKOFF.md)). Matiz: el núcleo "coordenadas → video" lo dicta el enunciado; el riesgo está en la
  interpretación, el nombre y el plan, que redactó un asistente de IA.

### 3.6 Criterios de evaluación (cada uno de 1 a 5, en todas las fases)

| Criterio | Qué mira | Para nosotros |
|---|---|---|
| **Impact** | cuánto problema resuelve y a cuánta gente inspira o ayuda | que cualquiera pueda mirar datos reales de SPHEREx |
| **Creativity** | originalidad, o una mejora significativa sobre ideas existentes | hay otros equipos con visores (ver §5): diferenciarse |
| **Validity** | base científica, factibilidad, usabilidad | honestidad (1–2 px, LVF, variables), que funcione con datos reales |
| **Relevance** | *"fully and directly addresses the challenge"*; datos NASA como núcleo, no como adorno | RA/Dec → video SPHEREx real, probado en los 5 objetivos |
| **Presentation** | claridad y storytelling; se evalúa con la demo **y** el proyecto completo | video ≤ 30 s y página del proyecto completa |

### 3.7 Fases y premios

- **Fase 1:** los jueces locales eligen a los *Global Nominees* (anuncio **3/12/2026**). Los premios locales son
  opcionales e independientes.
- **Fase 2:** jueces expertos eligen a los *Global Finalists* y las *Honorable Mentions* (anuncio **17/12/2026**).
- **Fase 3:** un comité ejecutivo de NASA y las agencias socias elige a los *Global Winners* (anuncio
  **26/01/2027**).
- **10 premios globales:** Best Use of Science · Best Use of Data · Best Use of Technology · Galactic Impact ·
  Best Mission Concept · Most Inspirational · Best Storytelling · Global Connection · Art & Technology · Local
  Impact.
- Para premio global hay que usar **al menos un dato o recurso NASA** (SPHEREx lo cumple).
- Todo equipo que envía antes del cierre recibe un **certificado de participación** (se descarga desde el
  perfil).

---

## 4. Trazabilidad: requisito → plan → estado hoy

"Dónde" remite a las prioridades de [`PLAN.md`](PLAN.md) §4 (cada WS las baja a su `tasks/WSx-*.md`). "Estado
hoy" describe el esqueleto al sáb 14/11 ~11:40 (detalle y evidencia en
[`REVIEW-2026-11-14.md`](REVIEW-2026-11-14.md)).

### Objetivo central

| ID | Requisito | Dónde se cubre (PLAN §4) | Prio | Estado hoy |
|---|---|---|---|---|
| O1 | Herramienta web **pública** | WS4: deploy público de backend y frontend · WS6: repo público o URL del sitio | P0 | PARCIAL: corre local con datos sintéticos; sin deploy; el repo da 404 sin login ✅ |
| O2 | Imágenes **de SPHEREx** | WS1: `search_frames` (SIA2 VOTable + TAP) y `read_patch` (Range en S3) · WS2: `reproject_to_grid`, coadd, PNG | P0 | AUSENTE con datos reales (stubs); solo hay demo sintético |
| O3 | Ver cómo cambia en el tiempo | WS2: coadd por (temporada × detector) · WS5: modo Blink/Diferencia | P0 | PARCIAL: el `BlinkViewer` (play, slider, velocidad, teclado) anda sobre datos sintéticos; un frame por exposición → parpadeo por λ |
| O4 | **El usuario ingresa RA/Dec** | WS5: caja RA/Dec (decimal, sexagesimal, nombre vía Sesame CfA) + 5 chips + FOV · WS4: `GET /api/view` | P0 | AUSENTE: la home es una lista curada y la caja es un TODO |
| O5 | Serie de imágenes **de ese parche**, "como un pequeño video" | WS4 `/api/view` + `build_patch(ra, dec, fov, …)` de WS1/WS2 (la misma función arma los golden fields) | P0 | AUSENTE para coordenadas arbitrarias |
| O6 | Que sea fácil ver lo que se mueve | WS5: zoom pixelado ×8, retícula, posición predicha, Diferencia · WS3: tabla de movimiento esperado | P0 | AUSENTE (los movimientos son de 1.1–1.9 px) |

### Objetivos de prueba

| ID | Objetivo | Dónde se cubre | Prio | Estado hoy |
|---|---|---|---|---|
| T1 | Barnard's Star | WS3: objetivo en `fields.toml` + golden field · hito **I1** (sáb 20:00) = `/api/view` de Barnard | P0 | PARCIAL: está en `fields.toml` con la posición bien propagada; sin frames reales |
| T2 | Epsilon Indi B | WS3: pm/plx/época guardados en el repo · aclarar en la UI que el par no se resuelve | P0 | PARCIAL: ya está en `fields.toml` (centro propagado; pm/plx en comentarios); sin frames reales |
| T3 | WISE 0855 | WS3: centrar en la posición propagada a la época de los datos · spike D5/D6 antes de usarlo en el video | P0 | PARCIAL: `fields.toml` ya lo centra en la posición propagada (≈126″ al oeste de la del enunciado); visibilidad en D5/D6 ❓ |
| T4 | RW Aurigae (variable) | WS3: método de variabilidad (coadds y espectros por temporada) · WS2: coadds | P0 | PARCIAL: ya está en `fields.toml`; método sin implementar |
| T5 | R Draconis (variable) | igual que T4 · WS4/WS5 P1: `/api/photometry` + curva de luz | P0 / P1 | PARCIAL: ya está en `fields.toml`; método sin implementar |
| T* | Los 5 como atajos + plan B | WS5: 5 chips · WS2/WS3: golden fields precomputados (hito **I2**, dom 08:00) | P0 | AUSENTE: sin chips ni golden fields (los 5 ya están en `fields.toml`) |

### Consideraciones

| ID | Consideración | Dónde se cubre | Prio | Estado hoy |
|---|---|---|---|---|
| C1 | Nuevos releases | WS1: colecciones configurables (`ERRANTE_COLLECTIONS`), usar la key/URI que devuelve la búsqueda · contrato 0.3.0: `Release` como `str` con patrón | P0 | PARCIAL: productos estáticos; hoy hay `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep` ✅ |
| C2a | 102 bandas / coadd por detector | WS2: coadd ponderado 1/VAR por (temporada, detector) · WS1 P1: `wavelength_at` (la grilla WCS-WAVE depende del detector) · WS2 P1 / WS5 P2: falso color D1/D3/D6 | P0 / P1 | AUSENTE (render por exposición) |
| C2b | Espectros al vuelo (*extra kudos*) | WS3/WS4: `/api/photometry` + espectro · WS5: click → espectro | P1 | PARCIAL: existe `SpectrumChart`, sin espectro por posición |
| C3 | Sumar / restar épocas | WS2: `difference(a, b)` (P0) y suma de épocas elegidas (P1) · WS5: modo Diferencia | P0 / P1 | AUSENTE |
| C4 | FOV elegible | WS5: control de FOV · WS4: `fov_arcmin` en `/api/view` | P0 | AUSENTE (`size_deg` fijo por campo) |
| C5 | Overlays Gaia / WISE | WS5: Aladin Lite 3.8.2 (jsdelivr) + HiPS de IRSA + overlay Gaia · WS4: proxy de catálogos si hace falta | P1 | PARCIAL: `SkyMap` es un placeholder que apunta a CDS (degradado) |
| C6 | Coordenadas en la URL / embebible | WS5: `?ra&dec&fov&det&mode&embed=1` · contrato: `Field.query` | P0 | AUSENTE (router por hash `#/field/<id>`) |
| C7 | Metadata / flags de contaminación | WS5: tira de metadata por frame (P0) · WS2: capa y porcentajes de flags (P1) · WS1: FLAGS por Range (P1) · contrato: `flag_fractions`, `flags_at_target` | P0 / P1 | PARCIAL: los flags solo se usan para enmascarar |
| C8 | Astropy + Aladin | WS1/WS2: numpy + astropy · WS5: Aladin Lite | P0 / P1 | PARCIAL |

### Recursos citados por el reto y entrega

| ID | Requisito | Dónde se cubre | Prio | Estado hoy |
|---|---|---|---|---|
| R1 | WiseView como modelo | referencia de UX para WS5 (parámetros en la URL, blink, resta) | — | sin usar todavía (0 menciones en el esqueleto) |
| R2 | Gaia DR3 | WS5 P1: overlay · WS3 P0: pm/plx de los objetivos guardados en el repo | P1 | AUSENTE |
| E1 | Video ≤ 30 s o deck ≤ 7 slides, en inglés | WS6 | P0 | plantilla en `PITCH.md` (2026-11-14); el guion viejo duraba 70–100 s |
| E2 | Use of SI + reconocimiento en texto/metadata, sin branding NASA | WS6 + todos (trailers en los commits) | P0 | plantilla en el README (2026-11-14); el equipo tiene que confirmarla |
| E3 | Links públicos sin login | WS4 (deploy) + coordinación (repo público) | P0 | AUSENTE: sin deploy, repo privado; falta `LICENSE` |
| E4 | ≥ 1 dato o recurso NASA | SPHEREx es el núcleo | P0 | pendiente de datos reales |
| E5 | Formulario completo en inglés | WS6 / coordinación: `PROJECT.md` → formulario | P0 | plantilla con TODOs (2026-11-14) |

---

## 5. Referencias útiles

**SPHEREx e IRSA**

| Recurso | URL | Estado |
|---|---|---|
| SPHEREx en IRSA (recurso oficial del reto) | https://irsa.ipac.caltech.edu/Missions/spherex.html | ✅ 200. La página dice que DR1 está disponible desde noviembre de 2026 |
| Tutoriales SPHEREx de IRSA (intro, cutouts, PSF, source discovery tool, mosaic, HiPS cube) | https://caltech-ipac.github.io/irsa-tutorials/spherex/ | ✅ 200 |
| Documentación del archivo SPHEREx | https://caltech-ipac.github.io/spherex-archive-documentation/ | ✅ 200 (no la revisamos en detalle) |
| Bucket público AWS: acepta CORS y lecturas por `Range` (los servicios de IRSA, TAP/SIA/cutouts, **no** envían CORS) | `s3://nasa-irsa-spherex/` (ver [`DATA.md`](DATA.md)) | ✅ |
| Cubo HiPS SPHEREx DR1 de IRSA (102 cortes, contexto estático) | https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube | ✅ 200 (`properties`) |
| Misión | https://science.nasa.gov/mission/spherex/ · https://spherex.caltech.edu/ | ✅ 200 |

**Modelos citados por el reto**

| Recurso | URL | Estado |
|---|---|---|
| WiseView: visor tipo blink para WISE. Parámetros en el hash (`ra`, `dec`, `size`, `band`, `speed`, `diff`, `zoom`, `gaia`, `shift`+`pmra`/`pmdec`…); por defecto abre en WISE 0855 | http://byw.tools/wiseview | ✅ 200, analizado 2026-11-14 |
| Backyard Worlds (ciencia ciudadana) | http://backyardworlds.org/ | ✅ 200 |

**Catálogos y overlays.** CDS Estrasburgo está degradado por un incidente de ciberseguridad (aviso del
2026-11-09) ✅. Hoy a las 11:39, `alasky…/2MASS/Color/properties` y `aladin.cds…/api/v3/latest/aladin.js` siguen
en 404. Usar estos espejos:

| Recurso | URL | Estado |
|---|---|---|
| Gaia DR3 en MAST (recurso oficial del reto) | https://archive.stsci.edu/missions-and-data/gaia | ✅ 200 |
| Gaia DR3 vía VizieR de CfA (con CORS), catálogo `I/355/gaiadr3` | https://vizier.cfa.harvard.edu/ | ✅ |
| Gaia TAP de ESA (**sin** CORS: solo desde el backend) | https://gea.esac.esa.int/tap-server/tap/sync | ✅ |
| Sesame en CfA: resolver de nombres, devuelve pm (con CORS) | `https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?<nombre>` | ✅ 200 |
| Aladin Lite **3.8.2** desde jsdelivr (no desde CDS) | https://cdn.jsdelivr.net/npm/aladin-lite@3.8.2/dist/aladin.js | ✅ 200 |
| Documentación de Aladin Lite | https://cds-astro.github.io/aladin-lite/ | ✅ 200 · 📄 API |
| HiPS 2MASS / AllWISE en espejos de IRSA y ESA | https://irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color · `…/CDS/AllWISE/RGB-W4-W2-W1` · https://skies.esac.esa.int/2MASSColor | ✅ |
| CatWISE2020 en IRSA TAP (`catwise_2020`, sin CORS) | vía backend | ✅ |
| SkyBoT (IMCCE), asteroides conocidos (overlay P1) | https://ssp.imcce.fr/webservices/skybot/ | ✅ 200 · 📄 API |
| Astropy | https://www.astropy.org/ | ✅ 200 |

**Prior art.** Una búsqueda en GitHub del 2026-11-14 encontró al menos ~15 repos públicos de otros equipos para
este reto (por ejemplo `root3315/muninn`, que confirma por su cuenta la lectura por rangos en S3) ✅. Sirven para
saber contra qué diferenciarse (*Creativity*). **No copiar código.** Si algo se reutiliza, se cita en *Other
References*.

**Narrativa (Planeta X, solo motivación)**

- Batygin & Brown (2016, AJ 151, 22) · Brown & Batygin (2021, AJ 162, 219) 📄. Los números y las citas están en
  [`SCIENCE.md`](SCIENCE.md) (los revisa WS3).
