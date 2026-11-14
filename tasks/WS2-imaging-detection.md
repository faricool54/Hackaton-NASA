# WS2 · Imágenes y detección de objetos en movimiento

**Objetivo:** convertir cutouts SPHEREx en (a) PNGs alineados norte-arriba en una grilla común para el blink y
(b) una lista de **candidatos que se mueven**, con puntaje y motivos; y medir qué tan débil/lento podemos detectar.

**Tus rutas:** `pipeline/errante/imaging/` · `pipeline/errante/detect/` · `pipeline/tests/test_imaging_*.py`,
`test_detect_*.py` · `notebooks/ws2_*` · `pipeline/errante/build.py` (coordinar con WS1).

**Recibís:** `SpherexImage` (WS1, `data/fits_io.py`). **Entregás:** PNG + `Frame` por exposición;
`list[Candidate]` (modelo en `models.py`) con `detections`, `motion`, `score`, `notes`.

**Leé primero:** `docs/SCIENCE.md` §1 y §3 (velocidades y la trampa de la longitud de onda), `docs/DATA.md` §2
(flags), `pipeline/errante/imaging/*.py`, `pipeline/errante/detect/*.py`.

## Estado actual
- ✅ `grid.py`: grilla común TAN norte-arriba, conversiones sky↔PNG (testeado).
- ✅ `flags.py`: bits reales de DR1, máscara de píxeles malos (SOURCE no es malo).
- ✅ `render.py`: PNG 8 bits con stretch asinh robusto.
- ✅ `synthetic.add_gaussian` (reutilizable para inyección).
- ⛔ `reproject_to_grid`, `find_sources`, `static_sky`, `residuals`, `link_tracks`, `score_tracks`, `inject_mover`.

## Tareas

- [ ] **WS2-1 (P0) `reproject_to_grid`** con `reproject.reproject_interp` (extra `science`), WCS completo con SIP,
  máscara de flags reproyectada con vecino más cercano, NaN fuera del cutout, orientación PNG.
  *Acepta:* test con una imagen sintética con WCS rotado: una estrella cae en el x/y esperado ±0.3 px.
- [ ] **WS2-2 (P0) Render consistente por campo.** Restar `ZODI`; stretch común por detector dentro de un campo
  (que el blink no "parpadee" en brillo por la normalización); opcional WebP.
- [ ] **WS2-3 (P0) `find_sources`** (photutils) sobre imagen sin fondo, con SNR desde `VARIANCE`.
  *Acepta:* en `data/demo` recupera > 90 % de las estrellas brillantes y los movers del demo.
- [ ] **WS2-4 (P0) `link_tracks`** para asteroides dentro de una visita (horas): pares primer/último frame →
  predicción en frames intermedios → tolerancia ~1 px. Excluir fuentes estáticas.
  *Acepta:* en `demo-ecliptic` encuentra SYN-AST-1 y SYN-TNO-1 y no reporta estrellas.
- [ ] **WS2-5 (P0) `score_tracks`** → `Candidate` (`status='unconfirmed'`, `artifact` si es de 1 frame o toca
  flags malos, con `notes` en lenguaje simple). Usar `science.motion.motion_from_detections`.
- [ ] **WS2-6 (P1) Inyección-recuperación** (`inject.py`): plantar movers en frames **reales**, grilla de
  flujo × velocidad, tabla de eficiencia → `data/products/limits.json` (proponer modelo a WS4/WS5 vía PR
  `contract:`). Es la base de la página "¿Qué tan lejos podemos ver?".
- [ ] **WS2-7 (P1) Capa de diferencia**: PNG de `frame − cielo_estático` por frame (`frames/<id>.diff.png`;
  agregar campo opcional `Frame.diff_image` vía PR `contract:`).
- [ ] **WS2-8 (P1) Movimiento propio entre pasadas** (estrellas cercanas / enanas marrones): comparar posiciones
  entre visitas separadas por meses. Validar con Barnard's Star (~10″/año ≈ 1.7 px/año).
- [ ] **WS2-9 (P2) Shift-and-stack** a lo largo de velocidades hipotéticas para objetos lentos y débiles
  (demo educativa del método de búsqueda del Planeta X).

## Gotchas
- La misma estrella cambia de brillo entre frames porque **cambia la longitud de onda**: compará posiciones,
  o frames del mismo detector y λ parecida.
- `OUTLIER`/`TRANSIENT` pueden marcar justo al objeto que se mueve: no los enmascares para la búsqueda de movers.
- PSF ~1–1.2 px (7.5″): fuentes casi sin resolver; aperturas chicas, centroides con cuidado.
- Cutouts pueden venir no cuadrados con NaN en bordes.

## Prompt de arranque

> Sos el agente del workstream WS2 (imágenes y detección) del repo Errante para NASA Space Apps 2026. Leé
> `AGENTS.md`, `docs/SCIENCE.md`, `docs/DATA.md` §2, `docs/CONTRACT.md` y `tasks/WS2-imaging-detection.md`.
> Trabajá SOLO en `pipeline/errante/imaging/`, `pipeline/errante/detect/` y sus tests. Empezá por WS2-3, WS2-4
> y WS2-5 usando `data/demo` como banco de pruebas (las posiciones verdaderas están en `candidates.json`), y en
> paralelo WS2-1 con imágenes sintéticas con WCS rotado. Librerías pesadas se importan dentro de las funciones
> (extra `science`). Corré `make check` y mostrame el diff antes de commitear.
