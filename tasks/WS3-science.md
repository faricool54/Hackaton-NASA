# WS3 · Ciencia: cinco blancos, variabilidad, espectros y contexto

**Objetivo:** validar los cinco objetos del enunciado, tanto movimiento como variabilidad, con identidad,
épocas y evidencia confiables. Después agregar espectros/contexto; Planeta X y candidatos son ampliaciones.

**Cobertura:** R05, C02/C05 y recursos de comparación. Leer `docs/VALIDATION.md` y `docs/REQUIREMENTS.md`.

**Tus rutas:** `pipeline/errante/science/` · `pipeline/errante/config/fields.toml` · `pipeline/tests/test_science_*.py`
· `notebooks/ws3_*` · `docs/SCIENCE.md` (revisión científica).

**Recibís:** frames con MJD, WCS, λ y calidad. **Entregás primero:** cinco identidades/presets verificados
y registros de validación; luego espectros/contexto. `Candidate`/cruce/distancia/Planeta X son entregables P2.

**Leé primero:** `docs/SCIENCE.md` (todo), `pipeline/errante/science/*.py`, `docs/DATA.md` §5.

## Estado actual
- ✅ `motion.py`: movimiento lineal desde detecciones; distancia aproximada por velocidad en oposición (solo
  orden de magnitud — SPHEREx mira a ~90° del Sol, ver SCIENCE §1).
- ✅ `context.py` (ficha del objeto, #58/#74, en la app con #73–#76; V15 nombres A/B de RW Aur corregidos), `spectra.py`
  (#59; V18 temperatura de color/clasificacion descriptiva en esta rama) y `variability.py` (#59; arreglos #93 y remanente LC24 en esta rama).
- ⛔ `known_objects.objects_in_frame/ephemeris/crossmatch`, `planet_x.*` (P2).

Tarea actual del usuario (15/11): rpccp con Codex completa V18 y el remanente LC24 sobre #93/#94/#97.
V15 de RW Aur lo resolvio faricool54 en #101, ya mergeado. No se duplica su implementacion.

## Tareas

- [ ] **WS3-1 (P2) `objects_in_frame`** con SkyBoT (más simple) o JPL SBIdent; caché; devuelve `KnownObject`
  con posición en esa época (x/y con `imaging.grid.sky_to_png_xy`). *Acepta:* test `network` en un campo
  eclíptico real devuelve asteroides con magnitud.
- [ ] **WS3-2 (P2) `crossmatch`**: separación mediana por frame ≤ ~15″ → `status='known'`, `known_match`.
- [x] **WS3-3 (P0, R05) Cinco blancos obligatorios** ✅ Los cinco registros están en `docs/validation/` (#36, #46), todos `success` sobre los FITS reales; nota post-#41 en #62. Revisión humana: DankoLiv, 2026-11-15 (#126; guiada, los análisis no se volvieron a correr). en `fields.toml` y evidencia según `docs/VALIDATION.md`:
  **Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis**. Resolver identidad/componentes,
  fuente/época de coordenadas y propagación; no confundir Epsilon Indi B con A ni exigir resolver Ba/Bb.
  Con WS1 seleccionar épocas y bandas útiles; documentar los cinco intentos incluso sin señal/cobertura.
  Presets de asteroides, TNOs y región de Planeta X quedan P2; los campos profundos pueden servir para desarrollo.
- [ ] **WS3-4 (P2) Distancia con geometría real**: velocidad aparente esperada vs distancia para órbitas
  circulares dada la posición/velocidad de la Tierra (astropy `get_body_barycentric_posvel`) o de SPHEREx
  (header `X_SC…`), apuntado y fecha; invertir para estimar r con rango. Reemplaza `opposition_rate` en el pipeline.
- [x] **WS3-5 (P1, C02) Espectros en una posición elegida** ✅ `science.spectra.position_spectrum` / `candidate_spectrum` sobre la fotometría de WS2, por temporada y con saturación (#59; CLI `errante position-spectrum`). WS4/WS5 ya sirven espectros acotados (#53–#55)., haya o no candidato automático. Fotometría
  de apertura/PSF en FITS, MJy/sr → mJy con ángulo sólido, errores de VARIANCE, λ/ancho de WCS-WAVE y fechas.
  `candidate_spectrum` puede reutilizar el servicio; clasificaciones son opcionales. No mezclar variabilidad
  temporal con forma espectral sin advertencia. Validar con una referencia y conectar WS4-8/WS5-12.
- [ ] **WS3-6 (P2) Región del Planeta Nueve** (`planet_nine_search_region`) desde el paper (citado) para el mapa
  del cielo de WS5, y `detectability()` para un widget "¿Lo vería SPHEREx?" usando los límites de WS2-6.
- [x] **WS3-7 (P0) Revisión científica** ✅ Tabla lista para aplicar en `docs/SCIENCE.md` § Revisión científica de textos (#60); los cambios los aplican WS5/WS6/WS7 en sus archivos. de todos los textos de la UI y del pitch (WS6): nada exagerado,
  números con fuente.
  S10 (Validity/Relevance): recorrido real reproducible, usabilidad y NASA como núcleo, con evidencia de
  WCS/épocas/bandas/calidad y cinco ensayos. Completar con WS6 JUDGING_REVIEW.md; no convertir mocks,
  simulaciones o confianza de candidatos en nota 1–5 del proyecto.
- [ ] **WS3-8 (P2) Ephemeris overlay**: posiciones predichas de objetos conocidos en todos los frames (ya
  soportado por `KnownObject.positions`) para que la UI muestre "dónde debería estar" vs "dónde lo vimos".
- [x] **WS3-9 (P0, R05) Variables RW Aurigae y R Draconis.** ✅ Validadas en `docs/validation/` (#36) y producto `science.variability.light_curve` (#59; CLI `errante lightcurve`). Revisión científica de los productos precalculados de #78/#79/#83 en `docs/SCIENCE.md` § Revisión científica de las curvas de luz (2026-11-15): sin bloqueantes; LC1–LC7 importantes; los de WS3 (LC6, LC7, LC23–LC29) se aplicaron en #87/#93, los productos se republicaron en #94/#95 y el panel de WS5 en #97. Construir comparación de brillo a λ
  compatible, con incertidumbre, fondo/PSF, saturación y mezcla de componentes controlados. Conservar flujo
  real y fechas; mismo detector no garantiza misma λ. Reportar resultado positivo, negativo o inconcluso.
- [x] **WS3-10 (P1, C05) Contexto Gaia DR3/WISE.** ✅ `science.context.object_context` + `physical_parameters` (Facts con fuente; 'unknown' si no se midió) y CLI `errante object` (#58). Conectado al panel del click por WS4/WS5 (#73–#76); falta que WS7 lo use en el 3D (V13, #90). Verificar catálogo, versión y condiciones de uso;
  propagar astrometría Gaia a épocas SPHEREx cuando haya datos. Exponer misión, banda, fecha y procedencia
  para WS5-4; no asumir que Gaia cubre enanas marrones débiles ni presentar WISE como SPHEREx.
- [ ] **WS3-11 (P2) Evaluar recursos CSA/CADC/NEOSSat.** Revisar página de misión, acceso CADC,
  tutorial y dataset del enunciado, licencias y posibles comparaciones. Decisión escrita con fuentes;
  cualquier adaptador futuro conserva misión y procedencia separadas y no bloquea SPHEREx.

- [x] **WS3-12 (P1, V18/C02) Temperatura de color y clasificación descriptiva IR.** `science.continuum` ajusta F_nu con escala libre, rango condicional y controles de calidad/cobertura; `spectra` interpreta cada temporada por separado y la CLI lo entrega en JSON/texto. No es Teff ni RGB. Rechazos explícitos; fixture real de ε Ind B y tests contra Astropy. Adaptador listo para que WS4 lo muestre en `SpectrumResponse.notes`, sin cambiar contrato.
- [x] **WS3-14 (LC24 restante) Resumen de dispersión.** No cuenta como medidas independientes los dos extremos de un único par. Bins de dos exposiciones conservados para pares, excluidos solo del resumen de dispersión; `scatter_over_control=null` si no hay muestra adecuada. Nuevos productos requieren republish WS4; los JSON empaquetados no se editan a mano.

## Gotchas
- SPHEREx está en órbita baja: para asteroides cercanos usá la posición de la nave (no geocéntrica).
- Efemérides siempre a la fecha de cada frame (`mjd`), nunca una posición fija para objetos que se mueven.
- Citá fuentes (Brown & Batygin 2021, JPL, IMCCE) en la UI y la entrega.

## Hechos verificados (2026-11-14) — leelos antes de implementar

- **Los 5 objetivos ya están en `fields.toml`** con astrometría de Sesame/SIMBAD (CfA) propagada a la época media
  de los datos; tabla completa, movimiento esperado y notas en [`docs/SCIENCE.md`](../docs/SCIENCE.md) §0.
- **WISE 0855:** la coordenada del enunciado es de ~2010; hoy el objeto está **~126″ al oeste**. Solo tiene datos
  DR1. Probablemente solo se ve en coadds D5/D6 (inferido por magnitudes: medirlo antes de usarlo en el video).
- **ε Ind B:** SPHEREx no separa Ba/Bb (una sola fuente); ε Ind A, brillante, está a ~402″.
- **Variables:** RW Aur y R Dra no se mueven; el método honesto (coadds y espectros por temporada, estrellas de
  comparación) está en `SCIENCE.md` §0.4. R Dra (2493 frames, ~2 ciclos) es el mejor caso para curva de luz.
- **CDS Estrasburgo está caído:** usar Sesame/VizieR de CfA y no depender de SIMBAD en vivo.
- `Release` es un `Literal` fijo en `models.py`: un release nuevo rompe la validación (proponerlo como `str` con
  patrón en el próximo PR de contrato). El docstring de `Frame.mjd` dice MJD-OBS: debería ser MJD-AVG.

## Prompt de arranque

> Sos el agente del workstream WS3 (ciencia) del repo Errante para NASA Space Apps 2026. Leé `AGENTS.md`,
> `docs/SCIENCE.md`, `docs/DATA.md`, `docs/CONTRACT.md` y `tasks/WS3-science.md`. Trabajá SOLO en
> `pipeline/errante/science/`, `pipeline/errante/config/fields.toml` y sus tests. Empezá por WS3-3 y WS3-9,
> siguiendo `docs/VALIDATION.md`; JPL/SkyBoT son posteriores al MVP. No inventes
> coordenadas ni parámetros orbitales: obtenelos de los servicios o papers y citá la fuente. Corré `python scripts/dev.py check`
> y mostrame el diff antes de commitear.
