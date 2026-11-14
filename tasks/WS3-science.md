# WS3 · Ciencia y objetivos: los 5 objetivos, variabilidad y contrato 0.3.0

**Objetivo:** que los 5 objetivos de prueba del enunciado (Barnard, ε Indi B y WISE 0855 se mueven; RW Aurigae y
R Draconis cambian de brillo) se vean y se expliquen bien: posición predicha en cada época, movimiento esperado
contra medido y un método honesto para la variabilidad. Además sos dueño del **PR de contrato 0.3.0** y de que los
textos científicos sean correctos.

**Tus rutas:** `pipeline/errante/science/**` · `pipeline/errante/config/**` · `docs/SCIENCE.md` ·
`pipeline/tests/test_science_*.py`. Además, dueño del PR de contrato 0.3.0: las rutas de CONTRATO
(`pipeline/errante/models.py`, `pipeline/errante/products.py`, `shared/schema/**`, `frontend/src/api/types.ts`,
`data/demo/**`) se tocan **solo** en ese PR `contract:`.

**Recibís:**
- **WS1:** `search_frames`, `group_seasons`, `fetch_cutouts` / `read_patch`, `read_spherex` (`mjd` = MJD-AVG),
  `wavelength_at` (P1).
- **WS2:** `GridFrame` y coadds por (temporada × detector) vía `build_patch`, para medir movimiento y brillo.
- **WS5 / WS6:** borradores de textos (Home, About, pitch) para revisar los números.

**Entregás** (firmas propuestas):

```python
# config/targets.toml (nuevo): un [[target]] por objetivo, con el mismo `id` que fields.toml
# science/targets.py (nuevo)
load_targets() -> dict[str, Target]          # Target = campos de Field.target (0.3.0) + id, kind, default_detectors
predicted_position(target: Target, mjd: float) -> tuple[float, float]       # (ra, dec) ICRS deg, pm lineal
target_track(target: Target, frames: list[Frame], grid: Grid) -> KnownObject  # source="simbad", x/y PNG por frame
# science/photometry.py (nuevo)
aperture_flux(gf: GridFrame, x: float, y: float, r_px: float, annulus_px: tuple[float, float]) -> tuple[float, float]  # mJy, error
photometry_at(ra, dec, refs) -> list[SpectrumPoint]                          # P1, lógica de /api/photometry
# science/known_objects.py (P1)
objects_in_frame(ra, dec, radius_deg, mjd) -> list[EphemerisHit]           # SkyBoT, registros livianos
track_known(ra, dec, radius_deg, frames, grid) -> list[KnownObject]        # fusiona por designación
```

Más: el PR `contract:` 0.3.0, la tabla "esperado vs medido" y los resultados de variabilidad en `docs/SCIENCE.md`,
y la revisión científica de los textos públicos.

**Leé primero:** [`AGENTS.md`](../AGENTS.md) · [`docs/PLAN.md`](../docs/PLAN.md) §3–§4 ·
[`docs/CONTRACT.md`](../docs/CONTRACT.md) ("Propuesta 0.3.0") · [`docs/COLLABORATION.md`](../docs/COLLABORATION.md)
(§4, archivos calientes) · [`docs/SCIENCE.md`](../docs/SCIENCE.md) completo (§0 objetivos, §3.2 variabilidad, §4
números para textos) · [`docs/DATA.md`](../docs/DATA.md) §4.2 (cobertura) · `pipeline/errante/config/fields.toml` ·
`pipeline/errante/science/*.py` · `pipeline/errante/models.py`.

## Estado actual (verificado 2026-11-14)

| Pieza | Estado |
|---|---|
| `config/fields.toml` | ✅ ya tiene los 5 objetivos (`barnards-star`, `eps-indi-b`, `wise-0855`, `rw-aurigae`, `r-draconis`) centrados en la posición propagada a la época media de sus frames. J2000, pm, plx y fuente están **solo en comentarios**, porque `FieldConfig` (`build.py`) rechaza claves desconocidas. |
| `docs/SCIENCE.md` | ✅ reescrito hoy: §0 astrometría (Sesame/SIMBAD CfA), qué esperar y notas por objetivo; §3.2 método de variabilidad (INFERIDO, a validar); §4 números correctos para textos. Falta la columna "medido". |
| `science/motion.py` | ✅ `motion_from_detections` y la fórmula de oposición son correctas y están testeadas. ⚠ La distancia por velocidad sobreestima ×3 en la geometría de SPHEREx (DROP en la UI). |
| `science/spectra.py` | ✅ la constante 0,889 mJy por (MJy/sr · píxel de 6,15″) es correcta. ⛔ funciones stub. |
| `science/known_objects.py` | ⛔ stubs. La firma de `objects_in_frame` no puede llenar `frame_id`/`x`/`y`; `build.py` no fusiona por designación y pasa `size_deg` como radio. |
| `science/planet_x.py` | ⛔ stubs → DROP. |
| Contrato 0.1.0 | ✅ coherente: el schema regenerado con pydantic 2.13.3 es idéntico al commiteado, `data/demo` valida y `types.ts` es un espejo fiel. ⚠ No representa coadds, diferencias, temporadas, objetivo, flags ni curvas de luz; `Release` es `Literal`; `Frame.mjd` dice `MJD-OBS`. La propuesta 0.3.0 completa está en `docs/CONTRACT.md`. |
| Servicios | ✅ SIMBAD, VizieR y alasky de CDS dan 404; los espejos de CfA andan. Por eso pm/plx van al repo. |
| UI | ⚠ `frontend/src/pages/HomePage.tsx:20` dice "Stars stay put" y `AboutPage.tsx:16` "a few arcseconds per hour" para el Planeta X: errores de 1–2 órdenes de magnitud. |

## Tareas (ordenadas por prioridad)

- [ ] **WS3-1 (P0, mergeado antes del sáb 15:00) PR de contrato 0.3.0.** Contenido = tabla "Propuesta 0.3.0" de
  `docs/CONTRACT.md` (la misma de PLAN §3). Pasos exactos:
  1. Rama `contract/0.3.0` desde `main` actualizado.
  2. `pipeline/errante/models.py`: **solo campos opcionales** de la tabla; `Release` → `str` con patrón
     `^((dr|qr)\d+(_deep)?|synthetic)$`; `MatchSource` += `gaia_dr3`, `catwise2020` (`simbad` ya existe);
     descripción de `Frame.mjd` = `MJD-AVG` (mitad de la exposición); glosario (exposición / visita / temporada) en
     los docstrings; documento de respuesta de `/api/photometry` (p. ej. `PhotometryResult {center, points}`) en
     `ALL_MODELS`; `SCHEMA_VERSION = "0.3.0"` (antes de regenerar: entra en el schema como default de
     `Manifest.schema_version`).
  3. `python scripts/dev.py schema` → regenera `shared/schema/*.json`.
  4. `frontend/src/api/types.ts` a mano, en el mismo PR (`Release` como `string` + constantes de los conocidos).
  5. `python scripts/dev.py demo` **solo si** el demo tiene que mostrar los campos nuevos (si WS2-10 está listo, va
     acá) y después `python scripts/dev.py validate`.
  6. `python scripts/dev.py check` verde → PR `contract: 0.3.0 ...`; revisan WS2, WS4 y WS5; al mergear, avisar
     en el chat "contrato 0.3.0 mergeado, hagan `git pull origin main`" y avisar a WS2, WS4 y WS5.
  Decisiones a cerrar en el PR (anotalas en la descripción; `docs/CONTRACT.md` lo actualiza coordinación):
  - **Umbral de temporada:** 20 d (glosario) + fusión de colas chicas (WS1-3) o 30 d. Con 20 d Barnard da 3 colas
    de 10, 8 y 2 frames y WISE 0855 parte su 2.ª temporada en 110 + 18 (`DATA.md` §4.2).
  - **Coadds y diferencias:** qué llevan los campos obligatorios `obs_id`, `release`, `date_obs` y `detector`
    (p. ej. `obs_id` = id del coadd, `mjd` = media de los inputs). Productos sin un único detector (falso color,
    coadd de todos los detectores) no entran: `Frame.detector` es obligatorio (1–6).
  - `Field.target.ref_epoch` en años julianos (J2000.0 = 2000.0; Gaia DR3 = 2016.0).
  - Con WS4: codificación del id `v-<ra>-<dec>-<fov>-d<det>-<group>` (slug sin `.` ni `+`), FOV por defecto y
    tope, ruta para servir los PNG de `data/cache/views`.
  *Acepta:* PR mergeado, revisado por WS2, WS4 y WS5 (mínimo 1 OK para mergear, `docs/COLLABORATION.md` §2);
  `python scripts/dev.py check` verde; `data/demo` sigue validando.
- [ ] **WS3-2 (P0) Objetivos legibles por máquina + `predicted_position`.** Crear
  `pipeline/errante/config/targets.toml` (entra solo al paquete: `config/*.toml` ya está en `package-data`) con un
  `[[target]]` por objetivo y el mismo `id` que `fields.toml`: `name`, `simbad_id`, `kind` (`proper_motion` |
  `variable`), `ra`, `dec`, `ref_epoch = 2000.0`, `pm_ra_cosdec_mas_yr`, `pm_dec_mas_yr`, `parallax_mas`,
  `source`, `default_detectors` (lo pide WS5; se llena con WS3-5) y `notes`. Valores: tabla de `SCIENCE.md` §0.1
  (RW Aur: guardá también la paralaje de Gaia DR3, que es la que hay que usar). `science/targets.py`:
  `load_targets`, `predicted_position` (lineal: Δt = (mjd − 51544,5) / 365,25 años desde J2000.0; ignora paralaje
  y aceleración de perspectiva, ambas despreciables) y `target_track`. Documentá la fórmula y los casos de test en
  `SCIENCE.md` para que WS5 la replique en TypeScript con los mismos números.
  *Acepta:* `test_science_targets.py`: `predicted_position` a la época media reproduce los centros de
  `fields.toml` ± 0,5″ (Barnard MJD 61104 → 269.44623, +4.76870; ε Ind B MJD 61042 → 331.09665, −56.80066;
  WISE 0855 MJD 61035 → 133.75980, −7.24219); WISE 0855 en 2026.0 queda a ~126″ al oeste de la coordenada del
  enunciado; `target_track` devuelve un x/y por frame en convención PNG.
- [ ] **WS3-3 (P0, chica) Textos científicos de la UI.** Los edita WS5 (`frontend/`, tarea WS5-7) y la redacción
  es del equipo (con WS6): vos pasás los hechos y aprobás. Hechos en `SCIENCE.md` §4: Barnard (objetivo oficial)
  se mueve ~10,4″/año, así que "Stars stay put" es falso; un cuerpo tipo Planeta Nueve a 500 UA va a ~0,28″/h en
  oposición y ~0,013″/h a 90° del Sol, no "a few arcseconds per hour"; ε Ind B se ve como una sola fuente; el video
  va por temporada por la λ.
  *Acepta:* aprobaste el PR de WS5-7 y no queda ninguno de los dos textos.
- [ ] **WS3-4 (P0) Variabilidad de RW Aur y R Dra sobre coadds por temporada** (paso 1 del método de
  `SCIENCE.md` §3.2). `science/photometry.py`: `aperture_flux` sobre `GridFrame` (`IMAGE − ZODI`, apertura chica
  por la PSF de ~1,2 px, anillo para el fondo local, error desde `VARIANCE`, conversión a mJy con 0,889 u
  `OMEGA_MEDIAN`). Objetivo + 1–3 estrellas de comparación del mismo campo y detector (brillo parecido, sin flags de
  saturación); sus coordenadas y cómo se eligieron van a `targets.toml`. Resultado: cociente
  objetivo/comparación por (temporada, detector). R Dra tiene cobertura casi continua: usá bins de tiempo
  (`max_season_days` de WS1-3) en vez de temporadas.
  *Acepta:* test con `GridFrame` sintéticos (`synthetic.add_gaussian`): el cociente de dos estrellas de flujo
  conocido sale ± 5 %; con datos reales, tabla temporada × detector para RW Aur y R Dra en `SCIENCE.md`, con error;
  los cocientes entre comparaciones quedan constantes dentro del error (control) o se documenta por qué no.
- [ ] **WS3-5 (P0) Tabla "esperado vs medido" + visibilidad por detector** (`SCIENCE.md` §0.2). Lo esperado ya
  está (Barnard 1,86 px, ε Ind B 1,10 px, WISE 0855 1,36 px; variables ~0). Medido: centroide simple (momentos en
  una ventana de ~5×5 px alrededor de la posición predicha) sobre coadds del mismo detector, primera contra última
  temporada, con dirección comparada contra la PA del movimiento propio. Visibilidad: SNR del objetivo en el coadd
  de cada detector (`aperture_flux`, WS3-4); con eso se llena `default_detectors` y se decide si WISE 0855 sirve
  para el video (plan B: Barnard).
  *Acepta:* columna "medido" (px y PA, con error) para los 3 objetivos con movimiento; Barnard dentro de
  1,86 ± 0,5 px o una explicación escrita; decisión escrita "WISE 0855 se ve / no se ve en D5/D6".
- [ ] **WS3-6 (P1) Fotometría por exposición + espectro al vuelo** (lógica de `/api/photometry`; WS4 la cablea):
  para cada exposición que cubre (ra, dec): λ en el objetivo (`wavelength_at`, WS1-8), `aperture_flux` sobre el
  parche reproyectado, flags en el objetivo si existen → `SpectrumPoint` con `mjd`, `season`, `detector` y `flags`
  (0.3.0). Pasos 2 y 3 de `SCIENCE.md` §3.2: espectros por temporada superpuestos y curva de luz
  `flujo / espectro medio interpolado en esa λ` contra MJD por detector, normalizada con las comparaciones.
  *Acepta:* RW Aur y R Dra: un espectro 0,75–5 µm por temporada; las comparaciones superponen sus espectros
  (control); R Dra: curva por detector comparada con el período de SIMBAD (≈ 247 d) o explicación escrita (flags,
  saturación, aliasing); tests offline con parches sintéticos.
- [ ] **WS3-7 (P1) Overlay de asteroides conocidos con SkyBoT** para el modo exposición (WS2-8) y campos cerca de
  la eclíptica (RW Aur está a +7,5°). `objects_in_frame` devuelve registros livianos (designación, nombre, tipo,
  V, ra, dec, mjd), con caché por (ra, dec, mjd); `track_known` fusiona por designación y calcula x/y con
  `imaging.grid.sky_to_png_xy`; radio = semidiagonal del campo + margen. En coadds de temporada no tiene sentido:
  los asteroides se diluyen.
  *Acepta:* test `network` sobre un frame eclíptico real devuelve asteroides con V; test offline con una respuesta
  guardada en `pipeline/tests/fixtures/ws3/`; sin duplicados por designación.
- [ ] **WS3-8 (P2) Limpieza narrativa.** Unificar o borrar el docstring de `planet_x.py` ("~400–800 AU, V ~
  21–25", inconsistente con `SCIENCE.md` §2); el Planeta X queda como una línea de motivación para WS6 con las dos
  citas verificadas (Brown & Batygin 2021; Pan-STARRS 2024). Verificar con `SPS_ELON` y la fecha de los headers que
  SPHEREx observa a ~90° del Sol (`SCIENCE.md` §1, hoy 📄).
  *Acepta:* `planet_x.py` y `SCIENCE.md` §2 no se contradicen; §1 pasa de 📄 a ✅ (con `SPS_ELON` medido) o queda
  ❓ con el motivo.
- [ ] **WS3-9 (P2) Que `types.ts` no se desincronice:** generarlo desde `shared/schema` y comparar en CI (con WS4 y
  WS5), y fijar la versión menor de pydantic (con otra versión `schema --check` podría fallar sin cambios: ❓).
  *Acepta:* cambiar un campo en `models.py` sin tocar `types.ts` hace fallar `python scripts/dev.py check`.

## DROP (no hacer)

- **Distancia por velocidad en la UI:** sobreestima ×3 a 90° del Sol (3,04″/h → 42 UA con oposición contra 13 UA)
  y no está en el enunciado.
- **Región del Planeta Nueve y `detectability()`:** fuera del enunciado; el Planeta X es una línea de motivación.
- **Shift-and-stack de órbitas hipotéticas:** fuera del enunciado y caro.
- **Campos de TNO/asteroides con Horizons (`ephemeris`, Makemake):** el foco son los 5 objetivos; un campo eclíptico
  con un asteroide conocido queda en P2 (comentario en `fields.toml`).
- **`crossmatch` de candidatos:** no hay detección automática (DROP en WS2).
- **AAVSO VSX:** responde con un challenge de Cloudflare; no intentar saltearlo.
- **SIMBAD/VizieR de CDS en vivo:** caídos; todo sale del repo o de los espejos de CfA.
- **Claves nuevas en `fields.toml`** (pm, plx): `FieldConfig` las rechaza y rompe `errante build`; van a
  `targets.toml`.

## Gotchas (✅ verificado 2026-11-14 · 🧮 cálculo nuestro · 📄 según documentación · ❓ abierto)

- ✅ CDS Estrasburgo degradado (aviso del 2026-11-09): SIMBAD, VizieR y alasky dan 404. Usar
  `simbad.cfa.harvard.edu`, Sesame de CfA (trae pm) y VizieR CfA (Gaia DR3 `I/355/gaiadr3` y AllWISE `II/328`, con
  CORS; CatWISE `II/365` devuelve el esquema con 0 filas). El TAP de Gaia en ESA anda, pero sin CORS (solo backend);
  CatWISE vía `catwise_2020` en el TAP de IRSA, también solo backend.
- ✅ Épocas: las posiciones de SIMBAD son J2000.0; Gaia DR3 es 2016.0 (Barnard DR3 4472832130942575872 en
  269.448503, +4.739420 coincide con SIMBAD propagado). No mezcles épocas.
- ✅/🧮 WISE 0855: la coordenada del enunciado es de época ~2010; a la época media de los datos el objeto está ~126″
  (~20 px) al oeste. Decirlo en la UI.
- ✅ ε Indi B: SIMBAD no tiene entradas separadas para Ba y Bb; con píxeles de 6,15″ SPHEREx ve una sola fuente.
  ε Ind A (brillante) está a ~402″ al oeste: entra con FOV ≥ ~14′.
- 🧮 Movimiento total en los datos: Barnard 1,86 px, WISE 0855 1,36 px, ε Ind B 1,10 px; paralaje ≤ 0,09 px;
  variables ~0. PSF ≈ 7,5″ ≈ 1,2 px en D1: el movimiento total es del orden de un ancho de PSF.
- ✅ R Dra: Mira, P ≈ 247 d; 2493 frames (1954 de `*_deep`), cobertura casi continua entre MJD 60916 y 61310; D2/D5
  con ~89 frames. RW Aur: `TT*` sin período, 3 temporadas con 18–19 frames por detector; paralaje de Hipparcos
  (15,42 ± 3,69 mas) contra Gaia DR3 A (6,406 mas): usar Gaia.
- ✅ El brillo de exposiciones sueltas cambia por λ (LVF) aunque la estrella sea constante, y el PNG satura (un
  cambio ×2 da el mismo 255): medí siempre sobre el FITS o el `GridFrame`, nunca sobre el PNG.
- ❓ Saturación (`OVERFLOW`/`NONLINEAR`) en Barnard (K = 4,5) y R Dra.
- ❓ Que cada temporada cubra todo el rango de λ de cada detector es INFERIDO: chequealo con
  `wavelength_min/max_um` de los coadds antes de comparar temporadas.
- ✅ SkyBoT conesearch responde 200 con `Access-Control-Allow-Origin: *`; JPL SBIdent responde 200.
- ✅ Constantes: K = 147,84″/h; 1 MJy/sr en un píxel de 6,15″ ≈ 0,889 mJy; corrimiento por la órbita baja de
  SPHEREx ~9,7″ a 1 UA, 3,2″ a 3 UA y 0,24″ a 40 UA.
- ✅ `Frame.mjd` = `MJD-AVG` (mitad de la exposición); `MJD-OBS` es el inicio.
- ✅ Planeta Nueve: Brown & Batygin 2021 (AJ 162, 219) y Pan-STARRS 2024 (AJ 167, 146: excluye el 78 % del espacio
  de parámetros). "V ≈ 20–23" no aparece en el abstract: ❓ no usarlo.

## Dependencias

- **WS3-1 (contrato):** nadie te bloquea; arrancá apenas termine el kickoff. WS2, WS4 y WS5 esperan el merge (sáb
  15:00) y mientras tanto trabajan contra 0.1.0 + `data/demo`.
- **WS3-2 y WS3-3:** no dependen de nadie. WS2 (golden fields) y WS5 (chips, posición predicha) esperan `targets.toml`.
- **WS3-4 y WS3-5:** necesitan coadds reales de WS2 (hitos I1 sáb 20:00 e I2 dom 08:00). Mientras: funciones y
  tests con `GridFrame` sintéticos, y el método escrito.
- **WS3-6:** necesita `wavelength_at` (WS1-8) y los parches de WS1-4; WS4 cablea `/api/photometry`.
- **WS6:** le pasás los números verificados para el pitch y la narrativa del Planeta X.
- **Sin red:** valores de `SCIENCE.md` §0 + tests `@pytest.mark.network` para lo vivo
  (`ERRANTE_NETWORK_TESTS=1 python scripts/dev.py test-py`; PowerShell: `$env:ERRANTE_NETWORK_TESTS=1; py scripts/dev.py test-py`).

## Prompt de arranque (pegalo en Claude Code / Codex)

> Sos el agente de WS3 (ciencia y objetivos) del repo del equipo para NASA Space Apps 2026, reto "Planet X and
> SPHEREx". Leé `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACT.md`, `docs/COLLABORATION.md`, `docs/SCIENCE.md` y
> `tasks/WS3-science.md`. Trabajá SOLO en tus rutas: `pipeline/errante/science/`, `pipeline/errante/config/`,
> `docs/SCIENCE.md` y `pipeline/tests/test_science_*.py`; los archivos del contrato (`models.py`, `products.py`,
> `shared/schema/`, `frontend/src/api/types.ts`, `data/demo/`) solo en la rama `contract/0.3.0`. Empezá por WS3-1
> (PR de contrato 0.3.0, con los pasos exactos de la tarea) y WS3-2 (`targets.toml` + `predicted_position` con
> tests). No inventes coordenadas, movimientos propios, períodos ni servicios: usá los valores verificados de
> `docs/SCIENCE.md` §0 o consultalos en los espejos de CfA citando la fuente; si no tenés red, dejá un test
> `@pytest.mark.network` y decímelo. Corré `python scripts/dev.py check` (Windows: `py scripts/dev.py check`; en
> Mac/Linux `make check` también sirve), mostrame el diff antes de commitear y commiteá como `ws3: <verbo + qué>`
> (o `contract: ...` en el PR de contrato) con el trailer `Co-Authored-By:` del agente.
