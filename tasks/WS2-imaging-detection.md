# WS2 · Imágenes y detección de objetos en movimiento

**Objetivo:** convertir cutouts SPHEREx en (a) PNGs alineados norte-arriba en una grilla común para el blink y
(b) productos opcionales de comparación. La detección automática y sus límites vienen después del visor real.

**Cobertura:** R02/R04/R05, C02/C03/C07/C08. Orden: grilla/render → ensayos → operaciones → detección.

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
- [ ] **WS2-3 (P2) `find_sources`** (photutils) sobre imagen sin fondo, con SNR desde `VARIANCE`.
  *Acepta:* fixture de imágenes en unidades físicas con verdad de referencia; no calcular SNR desde PNGs.
- [ ] **WS2-4 (P2) `link_tracks`** para asteroides dentro de una visita (horas): pares primer/último frame →
  predicción en frames intermedios → tolerancia ~1 px. Excluir fuentes estáticas.
  *Acepta:* en `demo-ecliptic` encuentra SYN-AST-1 y SYN-TNO-1 y no reporta estrellas.
- [ ] **WS2-5 (P2) `score_tracks`** → `Candidate` (`status='unconfirmed'`, `artifact` si es de 1 frame o toca
  flags malos, con `notes` en lenguaje simple). Usar `science.motion.motion_from_detections`.
- [ ] **WS2-6 (P2) Inyección-recuperación** (`inject.py`): plantar movers en frames **reales**, grilla de
  flujo × velocidad, tabla de eficiencia → `data/products/limits.json` (proponer modelo a WS4/WS5 vía PR
  `contract:`). Es la base de la página "¿Qué tan lejos podemos ver?".
- [ ] **WS2-7 (P1, C03) Restas de épocas**: permitir A−B y opcionalmente `frame − cielo_estático`.
  WCS, PSF, fondo, unidades, máscara y λ compatibles; propagar errores y guardar entradas de la operación.
  Exponer PNG y metadatos con contrato aditivo coordinado con WS4/WS5.
- [ ] **WS2-8 (P0, R05) Validación visual/astrométrica entre pasadas.** Ayudar a WS3 con Barnard,
  Epsilon Indi B y WISE 0855; comprobar registro de fondo, épocas y desplazamiento/incertidumbre.
  Para RW Aurigae/R Draconis, garantizar render consistente; el brillo científico se mide desde FITS.
  No depende de implementar `link_tracks`. Evidencia según `docs/VALIDATION.md`.
- [ ] **WS2-9 (P2) Shift-and-stack** a lo largo de velocidades hipotéticas para objetos lentos y débiles
  (demo educativa del método de búsqueda del Planeta X).
- [ ] **WS2-10 (P1, C02/C03) Sumas y coadds por detector.** Alinear y combinar por detector y visita,
  con pesos derivados de VARIANCE, máscara/coverage y lista de miembros. Mantener separados los seis detectores;
  no borrar la secuencia temporal al sumar todas las épocas. Mostrar λ efectiva/rango y método de combinación.
  Validar el cambio de SNR en una fuente estable y preservar originales para comparar.
- [ ] **WS2-11 (P1, C07) Resumen de calidad.** Flags de contaminación y cobertura por frame/recorte,
  significado y política de máscara. SOURCE no implica contaminación; OUTLIER/TRANSIENT requieren contexto.
  Ausencia de flags se declara desconocida, no limpia. Coordinar contrato con WS4-10 y panel con WS5-10.

## Gotchas
- La misma estrella cambia de brillo entre frames porque **cambia la longitud de onda**: compará posiciones,
  o frames del mismo detector y λ parecida.
- `OUTLIER`/`TRANSIENT` pueden marcar justo al objeto que se mueve: no los enmascares para la búsqueda de movers.
- PSF ~1–1.2 px (7.5″): fuentes casi sin resolver; aperturas chicas, centroides con cuidado.
- Cutouts pueden venir no cuadrados con NaN en bordes.

## Hechos verificados (2026-11-14) — leelos antes de implementar

- **El video tiene que ser por temporada × detector (coadds), no por exposición:** cada exposición mide otra λ
  (filtro lineal variable) y la misma estrella cambia de brillo sin ser variable. Ver [`docs/SCIENCE.md`](../docs/SCIENCE.md) §0.4.
- **Los objetivos se mueven 1–2 px en toda la línea de base** (Barnard 1,86 · WISE 0855 1,36 · ε Ind B 1,10):
  hacen falta resta de temporadas (dipolo +/−), stretch común por detector y zoom en la UI.
- **`build.py`**: (1) corta en 40 frames ordenados por tiempo (todo de la 1.ª temporada) → elegir por temporada ×
  detector; (2) `frame_id` sale del nombre del archivo de caché (un hash) → derivarlo de `obs_id` + detector.
  (Ya resuelto en `main`: el campo se escribe antes del análisis, que es opcional con `--analyze`.)
- **Flags:** `SOURCE` (bit 21) marca estrellas, no es "malo"; `OUTLIER`/`TRANSIENT` pueden caer justo sobre el
  objeto que se mueve. No enmascarar los píxeles mostrados; exportar fracciones de flags como metadata.
- Restar `ZODI` (`IMAGE − ZODI`) y pesar coadds con `1/VARIANCE`.

## Prompt de arranque

> Sos el agente del workstream WS2 (imágenes y detección) del repo Errante para NASA Space Apps 2026. Leé
> `AGENTS.md`, `docs/SCIENCE.md`, `docs/DATA.md` §2, `docs/CONTRACT.md` y `tasks/WS2-imaging-detection.md`.
> Trabajá SOLO en `pipeline/errante/imaging/`, `pipeline/errante/detect/` y sus tests. Leé también
> `docs/REQUIREMENTS.md` y `docs/VALIDATION.md`. Empezá por WS2-1 y WS2-2: cerrar un campo real visible
> sin análisis automático. Después WS2-8 y las consideraciones de comparación. Librerías pesadas se importan dentro de las funciones
> (extra `science`). Corré `python scripts/dev.py check` y mostrame el diff antes de commitear.
