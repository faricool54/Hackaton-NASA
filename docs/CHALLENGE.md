# El reto: "Planet X and SPHEREx" (Space Apps 2026)

Página oficial: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=details

Nivel: **Advanced** · Skills: Astrophysics, Planets & Moons, Software.

> Texto oficial copiado de la página del reto el 2026-11-14 (última publicación de la página: 2026-11-13).
> Si la página cambia, actualizar acá.

## Texto oficial

Since 2025, NASA’s SPHEREx mission has been mapping the entire sky every six months in 102 bands of near-infrared light, returning images of more than a billion objects. Comets, asteroids, stars, brown dwarfs, and even new planets reveal themselves by shifting position between images, but no one person can sift through all that data alone. Your challenge is to create a public-facing web tool to display images of the sky from SPHEREx mission, making it easy for anyone to quickly see how they change over time.

### Background
Asteroids and comets orbit around the Sun. Nearby stars march across the sky as they orbit around the Galaxy. The Earth orbits the Sun too, causing objects near us to change their apparent positions. Watching for these motions help us discover new astronomical objects and also help measure the distances to these objects. For example, the dwarf planet Pluto was discovered when an astronomer compared two images of the sky taken at different times and recognized that one point of light had shifted between images.
More recently, astronomers have mounted massive searches for nearby objects using this process with help from the public. Hundreds of thousands of volunteers have used this technique to discover asteroids, comets, stars and brown dwarfs—balls of gas too massive to be considered planets yet without enough mass to burn like stars. In fact, most of the known comets and brown dwarfs were discovered by volunteers in this manner through projects like [backyardworlds.org](http://backyardworlds.org/).
Since May 2025, NASA’s new SPHEREx mission has been returning unique data that could yield new discoveries. SPHEREx is mapping the whole sky once every six months in 102 bands of near-infrared light, making it uniquely sensitive to objects that are rich in hydrogen, water, carbon dioxide, carbon monoxide, and many other molecules. There will be too much data for any one person or even computer code to completely comprehend. There will be images of more than a billion objects - including brown dwarfs, quasars, comets, asteroids, stars, supernovae and galaxies - which often overlap or vary in brightness. We need your creative new tools to make the most of this treasure trove and help as many people as possible pitch in to make discoveries.

### Objectives
Your challenge is to create a public-facing web tool to display images of the sky from the SPHEREx mission, making it easy for anyone to quickly see how they change over time. Users will enter the coordinates of a patch of sky (Right Ascension and declination). Your tool will display a series of images of that patch like a little video, making it easy to spot moving objects.
Test your tool on Barnard’s Star, Epsilon Indi B (a pair of brown dwarfs orbiting a star), WISE 0855 (a fast-moving brown dwarf Right Ascension 08h55m10.831s, declination -7d14m42.53s), and variable stars RW Aurigae and R Draconis.

### Potential Considerations
You may (but are not required to) consider the following:
- New SPHEREx data is arriving fast! Make sure to design a tool that’s easy to update with the latest data releases.
- Think creatively about how to display those 102 infrared bands so users can take advantage of them to make new discoveries! For example, it may make sense to separately add together all the data taken by each of the six detector arrays to improve the signal-to-noise in the images you display. Extra kudos if your tool can generate spectra on the fly.
- It may help users discover moving objects if they have the options to add together or subtract images taken at different times.
- Let users choose the field of view! Larger fields of view can make it possible to track faster-moving sources, at the cost of longer data transfer times.
- Users could benefit from having the option to overlay astronomical data from other telescopes, such as the Gaia mission or the WISE mission.
- If you make it possible to query your tool by including coordinates in the URL, users will be able to easily embed it in other websites and projects.
- It can be useful to display metadata, like contamination flags.
- Consider looking for publicly available tools that may help in handling astronomical data, like the Astrophy tools, and in displaying astronomical data, like the Aladin tool developed by the Strasbourg Astronomical Data Center (CDS).
For data and resources related to this challenge, refer to the Resources tab at the top of the page. More resources may be added before the hackathon begins.

### Resources tab

NASA does not endorse any non-U.S. Government entity and is not responsible for information contained on non-U.S. Government websites. For non-U.S. Government websites, participants must comply with any data use parameters of that specific website.

### NASA Data & Resources
[NASA/IPAC Infrared Science Archive](https://irsa.ipac.caltech.edu/Missions/spherex.html): SPHEREx resources
[SPHEREx Tutorial Notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/): Example Jupyter notebooks for how to access the SPHEREx data via Python.
[WiseView](http://byw.tools/wiseview): A similar tool made for viewing data from an earlier NASA mission called WISE. It’s been used by the public to make hundreds of discoveries. Feel free to use it as a model or as inspiration!
[Gaia Mission Data](https://archive.stsci.edu/missions-and-data/gaia): Be sure to use the latest data release (Data Release 3).

### Space Agency Partner Resources
CSA (Canadian Space Agency)
[NEOSSat: Observing Asteroids, Space Debris and Exoplanets](https://www.asc-csa.gc.ca/eng/satellites/neossat/): Learn about NEOSSat, the world's first space telescope dedicated to detecting and tracking asteroids, comets, satellites, and space debris. This CSA resource highlights how Canada is helping protect our understanding of near-Earth space by contributing to international efforts to identify and monitor objects that could pose risks to Earth or spacecraft.
[Canadian Astronomy Data Centre (CADC)](https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/): The CADC provides access to a vast collection of astronomical observations from Canadian and international telescopes and space missions. Through this resource, participants can explore real scientific data used by astronomers to study stars, galaxies, exoplanets, asteroids, and other celestial objects.
[NEOSSat Data Tutorial](https://github.com/asc-csa/NEOSSAT_Tutorial): This tutorial demonstrates how to use Python to visualize data from Canada's NEOSSat mission. Follow step-by-step instructions to access spacecraft observations, create visualizations, and explore data collected by Canada's space telescope.
[NEOSSat Dataset](https://data.asc-csa.gc.ca/dataset/neossat): This dataset contains observations collected by NEOSSat, Canada's Near-Earth Object Surveillance Satellite. The data supports the detection and tracking of asteroids, comets, satellites, and space debris. Explore real observations from Canada's space telescope and learn how objects are monitored in near-Earth space.

### Lo obligatorio, en una línea

Web pública: el usuario ingresa **RA/Dec** → se muestra la **serie de imágenes SPHEREx** de ese parche "como un
videíto" para ver qué se mueve. Probarla con **Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis**.
Todo lo demás (bandas/espectros, sumar/restar épocas, FOV, overlays Gaia/WISE, coordenadas en la URL, flags,
Aladin/Astropy) es opcional y suma puntos.

> ⚠️ **Consecuencia para el plan:** la búsqueda por coordenadas arbitrarias es el **núcleo obligatorio**, no un
> extra. Hoy figura como WS5-7 (P1) + `/api/search` (WS1+WS4, 501). Conviene subirla a **P0** y que el flujo
> "RA/Dec → frames SPHEREx → flip-book" funcione aunque sea sin detección automática.

## Nuestra interpretación (propuesta de producto)

1. **Explorar**: elegir un pedazo de cielo (de una lista curada o por coordenadas) y ver las observaciones de
   SPHEREx de ese lugar ordenadas en el tiempo.
2. **Comparar ("blink")**: alternar entre épocas como los astrónomos que descubrieron Plutón; slider temporal,
   selector de detector/longitud de onda, capa de diferencia.
3. **Detectar**: un pipeline marca automáticamente lo que se movió, lo cruza con catálogos de objetos conocidos
   (JPL, SkyBoT) y muestra un **reporte de evidencia** por candidato (posiciones, velocidad, distancia
   aproximada, espectro 0.75–5 µm).
4. **Entender**: explicar por qué un Planeta X se movería tan lento, qué tan débil sería y **qué puede y qué no
   puede ver SPHEREx** (límites medidos con objetos simulados inyectados).
5. **Honestidad**: nunca afirmar un descubrimiento. "Sin match en catálogos" ≠ "objeto nuevo".

6. **Explorar en 3D** (WS7): cada objeto/sistema que seguimos tiene un **modelo 3D** construido con parámetros de
   catálogo (radio, temperatura → color, órbitas keplerianas, variabilidad): animación de su evolución y entrada a
   cada planeta/estrella con su ficha. Siempre etiquetado como **modelo, no imagen**. Ver
   [VISION_3D.md](VISION_3D.md).

Lo que nos diferencia: (a) imágenes **reales** de SPHEREx, no ilustraciones; (b) el **espectro** de cada objeto
(superpoder de SPHEREx: 102 colores); (c) límites de detección **medidos**; (d) UX para público general; (e) del punto que se mueve en la imagen al **sistema en 3D** que lo explica.

## Criterios de evaluación (verificar en la web oficial)

Space Apps suele evaluar: **Impacto/Influencia, Creatividad, Validez, Relevancia y Presentación**. Verificar la
lista y el formato de entrega vigentes (link al proyecto, demo/video, descripción, uso de IA) — tarea de WS6.

## Referencias útiles

- SPHEREx en IRSA: https://irsa.ipac.caltech.edu/Missions/spherex.html
- Documentación de acceso a datos: https://caltech-ipac.github.io/spherex-archive-documentation/
- Tutoriales IRSA (Python): https://caltech-ipac.github.io/irsa-tutorials/ (ver "SPHEREx")
- Bucket público AWS: `s3://nasa-irsa-spherex/` (ver `docs/DATA.md`)
- Misión: https://science.nasa.gov/mission/spherex/ · https://spherex.caltech.edu/
- Planeta Nueve: Batygin & Brown (2016, AJ 151, 22); Brown & Batygin (2021, AJ 162, 219)
- JPL SBIdent: https://ssd-api.jpl.nasa.gov/doc/sb_ident.html · Horizons: https://ssd-api.jpl.nasa.gov/doc/horizons.html
- IMCCE SkyBoT: https://ssp.imcce.fr/webservices/skybot/
