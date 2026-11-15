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
- ✅ `render.py`: PNG 8 bits asinh; `field_stretches` = mismo contraste por detector dentro del campo, anclado al
  cielo de cada frame y sin píxeles malos; sin datos (NaN) → PNG gris+alfa transparente.
- ✅ `synthetic.add_gaussian` (reutilizable para inyección).
- ✅ `reproject.py`: `reproject_to_grid` (TAN-SIP → grilla norte-arriba, bilineal numpy, máscara por vecino + peso,
  `IMAGE − ZODI`, núcleos saturados y defectos reparados solo para mostrar). Validado en datos reales (abajo).
- ✅ `build.py`: `select_frames` temporada × detector (temporadas ≤ 60 d), `frame_id = obs_id + 'D' + detector`,
  reemplazo de frames fallidos, `thumb.png`, error "descarga fallida" ≠ "sin cobertura".
- ✅ `imaging/compare.py` + `errante compare <id>`: coadds por temporada × detector y restas temporada − temporada
  con escala de flujo ajustada en estrellas del campo (WS2-7). `detect/difference.py`: `static_sky`, `residuals`.
- ✅ `imaging/photometry.py` + `errante spectrum --ra --dec [--pm-ra --pm-dec]`: fotometría forzada en los píxeles
  nativos de cada exposición (apertura r=2 px, cielo local, corrección de apertura por detector vs λ, errores de
  VARIANCE, λ/Δλ de WCS-WAVE, flags). Base de WS3-5/WS4-8/WS5-12 (espectro en el panel de la visión).
  Validado: estrella normal del campo de ε Ind vs 2MASS J/H/Ks = 1,025/1,058/1,062; WISE 0855 a 4,4–5 µm = 0,57 mJy
  (W2 = 0,57 mJy). Las estrellas saturadas (Barnard) quedan marcadas `saturated`: no hay flujo confiable.
- ⛔ `find_sources`, `link_tracks`, `score_tracks`, `inject_mover`.

## Tareas

- [x] **WS2-1 (P0) `reproject_to_grid`** con `reproject.reproject_interp` (extra `science`), WCS completo con SIP,
  máscara de flags reproyectada con vecino más cercano, NaN fuera del cutout, orientación PNG.
  *Acepta:* test con una imagen sintética con WCS rotado: una estrella cae en el x/y esperado ±0.3 px.
  ✅ Hecho sin el paquete `reproject` (misma matemática con numpy + astropy, así corre en CI sin el extra `science`).
  Tests en `test_imaging_reproject.py`; en datos reales Barnard cae a 0,10–0,20 px (mediana) de su posición predicha.
- [x] **WS2-2 (P0) Render consistente por campo.** Restar `ZODI`; stretch común por detector dentro de un campo
  (que el blink no "parpadee" en brillo por la normalización); opcional WebP (pendiente).
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
- [~] **WS2-7 (P1, C03) Restas de épocas**: permitir A−B y opcionalmente `frame − cielo_estático`.
  WCS, PSF, fondo, unidades, máscara y λ compatibles; propagar errores y guardar entradas de la operación.
  Exponer PNG y metadatos con contrato aditivo coordinado con WS4/WS5.
  🟡 Hecho en el pipeline: `errante compare <id>` escribe `compare/coadd_*.png`, `compare/diff_*.png` (naranja = más
  brillante ahora, cian = antes, damero = sin datos) y `compare/compare.json` **provisional** (fuera del contrato).
  En el campo real de Barnard la resta de un año muestra el dipolo norte en los 6 detectores. Falta: contrato aditivo
  (`contract:`, WS3) y la capa en la UI (WS5); restas por frame individual y λ emparejada (`wavelength_at` ya está en main, #23/#25).
  🟡 Blancos débiles (2026-11-15, `compare.py`, claves nuevas y aditivas en `compare.json`): si el límite de color del
  campo es ≥ 2× el de la región del blanco (círculo `target_exclude_px`, nunca < 10σ), el límite sale de esa región
  (`limit_rule`, `field_limit_mjy_sr`, `target_limit_mjy_sr` + nota "field-star residuals clip"); el softening del asinh
  es `max(0.05, 3σ/límite)` (`display_softening`) para que el ruido quede oscuro. Notas nuevas: diferencia sin escala
  (s = 1) y núcleo del blanco saturado/marcado (`target_core_flagged`; `core_*_px` por coadd). Cada coadd exporta
  `weights` (1/mediana de VARIANCE, mismo orden que `frame_ids`; `weights_definition`). En los 5 campos dorados la regla
  se activa en WISE 0855 16/18 y ε Ind B 1/30; Barnard, RW Aur y R Dra quedan con PNG idénticos bit a bit. WISE 0855
  con 2 frames por temporada × detector: D5 S2−S0/S2−S1 muestran un residuo positivo en la posición de S2 sin lóbulo
  negativo claro (S0/S1 a 4,04–4,08 µm, donde el objeto es más débil que en S2 a 4,18–4,22 µm, y el corrimiento es de
  0,7–1,3 px): mezcla movimiento y color, no es un dipolo limpio. En D6 no se ve (SNR del coadd 1,0–4,4).
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

**WS2 en datos reales** (12 cutouts IBE de Barnard: DR1 temporada 2 + QR3 temporada 3, 6 detectores; script manual
porque `search_frames`/`fetch_cutouts` siguen en stub):
- El núcleo saturado de Barnard viene **NaN** con `OVERFLOW|SUR_ERROR|SOURCE|BLOOM`: sin rellenar sale un agujero negro.
- Píxeles sueltos `NONFUNC`/`PERSIST`/`SUR_ERROR` (sin `OVERFLOW`) llegan a cientos–miles de MJy/sr con vecinos de cielo,
  cambian entre épocas y en el blink parecen movers de 1–2 px: se reparan con la mediana de vecinos (siguen en `bad`).
  Los píxeles muertos NaN también traen `OVERFLOW`: los aislados van a mediana, solo los núcleos (≥ 2 px) a máximo.
- Si el contraste se calcula con el núcleo relleno, el resto de las estrellas sale casi negro: el stretch ignora `bad`.
- La resta temporada 3 − temporada 2 muestra el dipolo norte de Barnard en los 6 detectores (~0,7 px en 5 meses).
- `em_min`/`em_max` de SIA son el rango del **detector entero**, no la λ en la posición: para elegir frames por λ hace
  falta `wavelength_at` (WS1). Sin λ, la selección usa el centro de cada temporada.
- SIA de `spherex_dr1` devolvió **HTTP 502** de forma intermitente (temporada 1 de Barnard nunca respondió en ~15 intentos);
  `spherex_qr3` respondió bien. TAP sync tardó > 240 s. Reintentos con backoff son obligatorios en WS1.
- El header trae `MJD-AVG` (ej. 61281.65977 vs `MJD-OBS` 61281.65910): `read_spherex` todavía usa `MJD-OBS` (WS1).

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
