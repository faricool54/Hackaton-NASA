# WS3 · Ciencia: objetos conocidos, distancia, espectros y Planeta X

**Objetivo:** que cada candidato tenga contexto científico confiable: ¿es un objeto conocido?, ¿a qué distancia
aproximada está?, ¿qué espectro tiene?, ¿cómo se compara con lo que sería un Planeta X? Y elegir los **campos
de demostración** que mejor cuentan la historia.

**Tus rutas:** `pipeline/errante/science/` · `pipeline/errante/config/fields.toml` · `pipeline/tests/test_science_*.py`
· `notebooks/ws3_*` · `docs/SCIENCE.md` (revisión científica).

**Recibís:** `Candidate` (WS2), frames con MJD. **Entregás:** `KnownObject[]` por campo, `crossmatch` (status
`known` + `known_match`), `DistanceEstimate`, `SpectrumPoint[]`, región del Planeta Nueve, campos curados.

**Leé primero:** `docs/SCIENCE.md` (todo), `pipeline/errante/science/*.py`, `docs/DATA.md` §5.

## Estado actual
- ✅ `motion.py`: movimiento lineal desde detecciones; distancia aproximada por velocidad en oposición (solo
  orden de magnitud — SPHEREx mira a ~90° del Sol, ver SCIENCE §1).
- ⛔ `known_objects.objects_in_frame/ephemeris/crossmatch`, `spectra.*`, `planet_x.*`.

## Tareas

- [ ] **WS3-1 (P0) `objects_in_frame`** con SkyBoT (más simple) o JPL SBIdent; caché; devuelve `KnownObject`
  con posición en esa época (x/y con `imaging.grid.sky_to_png_xy`). *Acepta:* test `network` en un campo
  eclíptico real devuelve asteroides con magnitud.
- [ ] **WS3-2 (P0) `crossmatch`**: separación mediana por frame ≤ ~15″ → `status='known'`, `known_match`.
- [ ] **WS3-3 (P0) Campos curados** en `fields.toml`: (a) un campo eclíptico con un asteroide brillante
  conocido observado por SPHEREx (buscarlo con SBIdent sobre frames reales de WS1), (b) Makemake u otro TNO
  (`track_object`, posición desde Horizons a la fecha de las observaciones), (c) Barnard / WISE 0855 (movimiento
  propio, propagar posición), (d) un campo profundo NEP/SEP, (e) un campo dentro de la región del Planeta Nueve.
  *Acepta:* para cada uno, WS1 confirma ≥ 3 épocas útiles.
- [ ] **WS3-4 (P1) Distancia con geometría real**: velocidad aparente esperada vs distancia para órbitas
  circulares dada la posición/velocidad de la Tierra (astropy `get_body_barycentric_posvel`) o de SPHEREx
  (header `X_SC…`), apuntado y fecha; invertir para estimar r con rango. Reemplaza `opposition_rate` en el pipeline.
- [ ] **WS3-5 (P1) Espectros**: `candidate_spectrum` (fotometría de apertura en el FITS, MJy/sr → mJy con
  `OMEGA_MEDIAN`, errores de `VARIANCE`) + `color_class` con advertencias. Validar con estrellas/asteroides conocidos.
- [ ] **WS3-6 (P1) Región del Planeta Nueve** (`planet_nine_search_region`) desde el paper (citado) para el mapa
  del cielo de WS5, y `detectability()` para un widget "¿Lo vería SPHEREx?" usando los límites de WS2-6.
- [ ] **WS3-7 (P1) Revisión científica** de todos los textos de la UI y del pitch (WS6): nada exagerado,
  números con fuente.
- [ ] **WS3-8 (P2) Ephemeris overlay**: posiciones predichas de objetos conocidos en todos los frames (ya
  soportado por `KnownObject.positions`) para que la UI muestre "dónde debería estar" vs "dónde lo vimos".

## Gotchas
- SPHEREx está en órbita baja: para asteroides cercanos usá la posición de la nave (no geocéntrica).
- Efemérides siempre a la fecha de cada frame (`mjd`), nunca una posición fija para objetos que se mueven.
- Citá fuentes (Brown & Batygin 2021, JPL, IMCCE) en la UI y la entrega.

## Prompt de arranque

> Sos el agente del workstream WS3 (ciencia) del repo Errante para NASA Space Apps 2026. Leé `AGENTS.md`,
> `docs/SCIENCE.md`, `docs/DATA.md`, `docs/CONTRACT.md` y `tasks/WS3-science.md`. Trabajá SOLO en
> `pipeline/errante/science/`, `pipeline/errante/config/fields.toml` y sus tests. Empezá por WS3-1 y WS3-2
> (SkyBoT/JPL SBIdent con caché, tests offline con respuestas guardadas + tests `network`). No inventes
> coordenadas ni parámetros orbitales: obtenelos de los servicios o papers y citá la fuente. Corré `make check`
> y mostrame el diff antes de commitear.
