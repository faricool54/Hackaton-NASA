# El reto: "Planet X and SPHEREx" (Space Apps 2026)

Página oficial: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=details

> ⚠️ **Pegá acá el texto oficial completo** (Summary, Objectives, Potential Considerations, Data & Resources).
> El esqueleto se generó desde un entorno que **no podía abrir** spaceappschallenge.org, así que lo de abajo
> se reconstruyó de resúmenes públicos del reto. Cuando lo peguen, revisen que la interpretación siga valiendo
> y avisen si cambia algo de las tareas.

```
<!-- TEXTO OFICIAL DEL RETO — pegar aquí -->
```

## Lo que sabemos del reto (fuentes secundarias)

- Construir una **herramienta web pública** que muestre **imágenes del cielo en infrarrojo cercano de SPHEREx**
  y permita ver **cómo cambia el cielo con el tiempo**, para **descubrir objetos celestes que cambian de posición**.
- Nivel: **avanzado**. Datos: imágenes de **NASA SPHEREx** (archivo IRSA).
- Motivación: el hipotético **Planeta X / Planeta Nueve** — un planeta lejano que se movería muy lentamente
  contra las estrellas de fondo.

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

Lo que nos diferencia: (a) imágenes **reales** de SPHEREx, no ilustraciones; (b) el **espectro** de cada objeto
(superpoder de SPHEREx: 102 colores); (c) límites de detección **medidos**; (d) UX para público general.

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
