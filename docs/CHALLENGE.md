# Enunciado del reto SPHEREx

## Procedencia y alcance

Texto completo aportado por el equipo en `../ENUNCIADO.md`, incorporado el **2026-11-14**.
Se conserva literalmente, incluidos todos los recursos. La URL de Space Apps que ya figuraba en el repo
no pudo consultarse: fallo de TLS desde esta máquina y acceso fallido desde el navegador de investigación.
Por eso no se presenta esta copia como cotejada con la página oficial. Las reglas de entrega se toman
por separado del PDF aportado, no se infieren del enunciado técnico.

URL pendiente de cotejo: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=details

El objetivo principal es un **explorador temporal público de imágenes reales de SPHEREx por RA/Dec**.
La detección automática, las estimaciones de distancia y Planeta X son extensiones del equipo.
Las consideraciones del enunciado son opcionales: todas tienen una tarea asignada, sin convertirlas
artificialmente en condiciones obligatorias de entrega.

- [Matriz de requisitos y consideraciones](REQUIREMENTS.md): cobertura, responsables y aceptación.
- [Validación de los cinco objetos pedidos](VALIDATION.md): protocolo y evidencia pendiente.
- [Arquitectura](ARCHITECTURE.md): flujo principal y análisis opcional.
- [Acceso a recursos](DATA.md#7-comprobación-de-los-enlaces-del-enunciado-2026-11-14): resultados y limitaciones.
- [Guía de entrega](SUBMISSION_GUIDE.md): reglas S01–S10 del [PDF aportado](<references/NASA Space Apps Challenge.pdf>).
- [Evaluación y premios](JUDGING_GUIDE.md): criterios 1–5, elegibilidad y fases del segundo PDF aportado.

## Texto completo del enunciado aportado

Since 2025, NASA’s SPHEREx mission has been mapping the entire sky every six months in 102 bands of near-infrared light, returning images of more than a billion objects. Comets, asteroids, stars, brown dwarfs, and even new planets reveal themselves by shifting position between images, but no one person can sift through all that data alone. Your challenge is to create a public-facing web tool to display images of the sky from SPHEREx mission, making it easy for anyone to quickly see how they change over time.

Background
Asteroids and comets orbit around the Sun. Nearby stars march across the sky as they orbit around the Galaxy. The Earth orbits the Sun too, causing objects near us to change their apparent positions. Watching for these motions help us discover new astronomical objects and also help measure the distances to these objects. For example, the dwarf planet Pluto was discovered when an astronomer compared two images of the sky taken at different times and recognized that one point of light had shifted between images.

More recently, astronomers have mounted massive searches for nearby objects using this process with help from the public. Hundreds of thousands of volunteers have used this technique to discover asteroids, comets, stars and brown dwarfs—balls of gas too massive to be considered planets yet without enough mass to burn like stars. In fact, most of the known comets and brown dwarfs were discovered by volunteers in this manner through projects like backyardworlds.org.

Since May 2025, NASA’s new SPHEREx mission has been returning unique data that could yield new discoveries. SPHEREx is mapping the whole sky once every six months in 102 bands of near-infrared light, making it uniquely sensitive to objects that are rich in hydrogen, water, carbon dioxide, carbon monoxide, and many other molecules. There will be too much data for any one person or even computer code to completely comprehend. There will be images of more than a billion objects - including brown dwarfs, quasars, comets, asteroids, stars, supernovae and galaxies - which often overlap or vary in brightness. We need your creative new tools to make the most of this treasure trove and help as many people as possible pitch in to make discoveries.

Objectives
Your challenge is to create a public-facing web tool to display images of the sky from the SPHEREx mission, making it easy for anyone to quickly see how they change over time. Users will enter the coordinates of a patch of sky (Right Ascension and declination). Your tool will display a series of images of that patch like a little video, making it easy to spot moving objects.

Test your tool on Barnard’s Star, Epsilon Indi B (a pair of brown dwarfs orbiting a star), WISE 0855 (a fast-moving brown dwarf Right Ascension 08h55m10.831s, declination -7d14m42.53s), and variable stars RW Aurigae and R Draconis.

Potential Considerations
You may (but are not required to) consider the following:

New SPHEREx data is arriving fast! Make sure to design a tool that’s easy to update with the latest data releases.
Think creatively about how to display those 102 infrared bands so users can take advantage of them to make new discoveries! For example, it may make sense to separately add together all the data taken by each of the six detector arrays to improve the signal-to-noise in the images you display. Extra kudos if your tool can generate spectra on the fly.
It may help users discover moving objects if they have the options to add together or subtract images taken at different times.
Let users choose the field of view! Larger fields of view can make it possible to track faster-moving sources, at the cost of longer data transfer times.
Users could benefit from having the option to overlay astronomical data from other telescopes, such as the Gaia mission or the WISE mission.
If you make it possible to query your tool by including coordinates in the URL, users will be able to easily embed it in other websites and projects.
It can be useful to display metadata, like contamination flags.
Consider looking for publicly available tools that may help in handling astronomical data, like the Astrophy tools, and in displaying astronomical data, like the Aladin tool developed by the Strasbourg Astronomical Data Center (CDS).
For data and resources related to this challenge, refer to the Resources tab at the top of the page. More resources may be added before the hackathon begins.


## RESOURCES

NASA does not endorse any non-U.S. Government entity and is not responsible for information contained on non-U.S. Government websites. For non-U.S. Government websites, participants must comply with any data use parameters of that specific website.

NASA Data & Resources
NASA/IPAC Infrared Science Archive: SPHEREx resources
https://irsa.ipac.caltech.edu/Missions/spherex.html

SPHEREx Tutorial Notebooks: Example Jupyter notebooks for how to access the SPHEREx data via Python.
https://caltech-ipac.github.io/irsa-tutorials/spherex/

WiseView: A similar tool made for viewing data from an earlier NASA mission called WISE. It’s been used by the public to make hundreds of discoveries. Feel free to use it as a model or as inspiration!
http://byw.tools/wiseview

Gaia Mission Data: Be sure to use the latest data release (Data Release 3).
https://archive.stsci.edu/missions-and-data/gaia

Space Agency Partner Resources
CSA (Canadian Space Agency)

NEOSSat: Observing Asteroids, Space Debris and Exoplanets: Learn about NEOSSat, the world's first space telescope dedicated to detecting and tracking asteroids, comets, satellites, and space debris. This CSA resource highlights how Canada is helping protect our understanding of near-Earth space by contributing to international efforts to identify and monitor objects that could pose risks to Earth or spacecraft.
https://www.asc-csa.gc.ca/eng/satellites/neossat/

Canadian Astronomy Data Centre (CADC): The CADC provides access to a vast collection of astronomical observations from Canadian and international telescopes and space missions. Through this resource, participants can explore real scientific data used by astronomers to study stars, galaxies, exoplanets, asteroids, and other celestial objects.
https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/

NEOSSat Data Tutorial: This tutorial demonstrates how to use Python to visualize data from Canada's NEOSSat mission. Follow step-by-step instructions to access spacecraft observations, create visualizations, and explore data collected by Canada's space telescope.
https://github.com/asc-csa/NEOSSAT_Tutorial

NEOSSat Dataset: This dataset contains observations collected by NEOSSat, Canada's Near-Earth Object Surveillance Satellite. The data supports the detection and tracking of asteroids, comets, satellites, and space debris. Explore real observations from Canada's space telescope and learn how objects are monitored in near-Earth space.
https://data.asc-csa.gc.ca/dataset/neossat

---

## Cómo se traduce al proyecto

**Obligatorio (R01–R05):** web pública; imágenes reales de la misma región en distintas fechas;
entrada por ascensión recta y declinación; reproducción temporal; pruebas con Barnard's Star,
Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis.

**Opcional del enunciado (C01–C08):** actualizar releases; explorar bandas, coadds por detector y espectros;
sumar/restar épocas; elegir FOV; superponer Gaia/WISE; coordenadas en URL e integración embebida;
mostrar metadatos/flags; evaluar herramientas públicas como Astropy y Aladin. El original dice
"Astrophy"; la propuesta técnica usa Astropy, cuyo sitio se consultó, sin alterar el texto original.

**Extensiones propias:** detección automática, cruce de asteroides con JPL/SkyBoT, distancia,
inyección-recuperación y contenido educativo de Planeta X. No bloquean la visualización ni sustituyen
la validación de estrellas con movimiento propio y variables. Ver prioridades en `REQUIREMENTS.md`.
La capa **3D de WS7** también es una extensión P2: sus modelos y parámetros sin verificar no sustituyen
imágenes reales ni validan los cinco blancos. Se conserva en la integración como galería educativa;
la especificación y las limitaciones están en [VISION_3D.md](VISION_3D.md).

**Recursos:** SPHEREx/IRSA y sus notebooks son la base. WiseView es referencia de experiencia de usuario;
Gaia DR3 y WISE aportan contexto opcional. CSA, CADC, el tutorial y el dataset NEOSSat quedan contemplados
como referencias y posible comparación futura, siempre identificados por misión, sin sustituir SPHEREx.
Las reglas de uso y citas se revisan antes de redistribuir datos o publicar la entrega.

## Reglas de entrega documentadas por separado

El texto técnico no fija reglas de envío. El PDF **Project Submission Guide**, fechado 13/11/2026,
sí establece demo obligatoria (video <= 30 s o hasta 7 slides), inglés, enlaces públicos, formulario,
atribución de SI/IA, recursos NASA, elegibilidad y cierre. Ver [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md)
y [CHECKLIST.md](submission/CHECKLIST.md), con fuentes y páginas.

Sede confirmada por el usuario: Universidad de Palermo, Buenos Aires. Cierre según guía:
**15/11/2026 a las 23:59 ART (UTC-3)**; objetivo interno: **21:00 ART**. Horario de evaluación local y
detalles de las guías enlazadas siguen pendientes. La copia íntegra del enunciado se mantiene sin cambios.

La **Judging & Awards Guide** aportada después ya se leyó e incorporó: cinco criterios de 1–5,
integrantes locales 1–6 (Universal 2–6), condiciones de nominación y diez premios. Ver JUDGING_GUIDE.md.
Siguen pendientes términos completos y arreglos de evaluación local; no se asigna elegibilidad ni nota al equipo.
