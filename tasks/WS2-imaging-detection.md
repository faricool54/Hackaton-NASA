# WS2 · Imagen: reproyección, coadds y diferencias (el "video")

**Objetivo:** convertir los frames de un parche RA/Dec en la serie de imágenes que pide el enunciado: alineadas
norte-arriba en una grilla común, **co-sumadas por (temporada × detector)** para subir la S/N y sacar el
parpadeo por longitud de onda, con resta de épocas y un stretch común. Todo detrás de `build_patch`, que usan el
CLI (golden fields) y `/api/view` (WS4).

**Tus rutas:** `pipeline/errante/imaging/**` · `pipeline/errante/detect/**` · `pipeline/errante/build.py` (dueño,
coordina con WS1) · `pipeline/errante/synthetic.py` · subcomandos `build` / `demo` de `cli.py` · tests
`test_imaging_*` / `test_detect_*` / `test_build_*`.

**Recibís:**
- **WS1:** `search_frames(...) -> SearchResult` · `group_seasons(refs) -> list[Season]` ·
  `fetch_cutouts(refs, ra, dec, size_arcmin) -> (ok: [(FrameRef, Path)], failed: [(FrameRef, str)])` ·
  `read_spherex(path) -> SpherexImage` (`mjd` = MJD-AVG; `flags=None` en el camino S3 hasta WS1-9) ·
  `frame_id(ref)` · `wavelength_at(...)` (P1).
- **WS3:** centros de los 5 objetivos en `config/fields.toml` (ya propagados) · `config/targets.toml` (pm/plx en
  formato legible por máquina, mismos `id`) + `science.targets.target_track(target, frames, grid) -> KnownObject`
  (posición predicha por frame) · contrato 0.3.0.

**Entregás** (firmas propuestas; acordalas con WS1/WS4 en la primera hora):

```python
# imaging/reproject.py
@dataclass
class GridFrame:               # todo en orientación PNG (fila 0 = norte) sobre la grilla del campo
    data: np.ndarray           # IMAGE − ZODI − fondo residual [MJy/sr], NaN sin cobertura
    variance: np.ndarray       # [(MJy/sr)^2]
    flags: np.ndarray | None   # int32, vecino más cercano; None si el frame no trae FLAGS
    coverage: np.ndarray       # bool: dentro del frame y finito
    meta: dict                 # frame_id, obs_id, detector, mjd, release, season, wavelength_um, ...
reproject_to_grid(img: SpherexImage, grid: Grid, subtract_zodi=True) -> GridFrame
# imaging/stack.py (nuevo)
# agrupar por (meta["season"], meta["detector"]): la temporada sale de group_seasons (WS1); no recalcularla acá
coadd(frames: list[GridFrame], bad=DEFAULT_BAD) -> GridFrame        # pesos 1/VARIANCE
difference(a: GridFrame, b: GridFrame) -> GridFrame                 # variance = var_a + var_b
# imaging/render.py
common_stretch(frames: list[GridFrame]) -> Stretch                  # uno por detector, todas las temporadas
save_png(img, path, stretch, coverage=None) -> Stretch              # PNG "LA": alfa 0 sin cobertura
# build.py
build_patch(ra, dec, fov_arcmin, detectors=None, group="season", out=..., field_id=None,
            name=None, target=None) -> SkyField
```

**Leé primero:** [`AGENTS.md`](../AGENTS.md) · [`docs/PLAN.md`](../docs/PLAN.md) §1–§4 ·
[`docs/CONTRACT.md`](../docs/CONTRACT.md) · [`docs/COLLABORATION.md`](../docs/COLLABORATION.md) ·
[`docs/DATA.md`](../docs/DATA.md) §0, §2.3 (FLAGS) y §4.2 (cobertura por temporada y detector) ·
[`docs/SCIENCE.md`](../docs/SCIENCE.md) §0.2 y §3.2 (qué esperar y la trampa de la λ) ·
`pipeline/errante/imaging/*.py` · `build.py`.

## Estado actual (verificado 2026-11-14)

| Pieza | Estado |
|---|---|
| `imaging/grid.py` | ✅ correcto: TAN norte-arriba, este a la izquierda, vuelta de RA en 0/360. La cadena detector (TAN-SIP real) → cielo → grilla da 0,025 px de error. Conservar. |
| `imaging/flags.py` | ✅ coincide bit a bit con las tarjetas `MSKN` de un FITS DR1 real; `SOURCE` no cuenta como malo. |
| `imaging/render.py` | ⚠ anda, pero el stretch es por frame (demo: vmax 1,80–2,17 entre frames del mismo detector), satura a 255 toda fuente > ~40σ (una variación ×2 no se ve), NaN → negro y `vmax == vmin` → imagen negra + warning. |
| `imaging/reproject.py` | ⛔ stub; la firma `-> (data, bad)` pierde VARIANCE, FLAGS y cobertura. |
| `detect/*` | ⛔ stubs (`find_sources` sin varianza, `score_tracks` sin `Grid`). Pasan a P2/DROP. |
| `build.py` | ⚠ corta a 40 frames ordenados por tiempo (en Barnard, todos de la 1.ª temporada); `frame_id` = hash del archivo de caché; **no escribe nada** hasta que existan detección y objetos conocidos (stubs); `zip(strict=True)` con `fetch_cutouts`; pasa `size_deg` como radio; usa la λ del `FrameRef` (banda del detector, no la del objetivo). |
| `synthetic.py` | demo sin WCS (no sirve para probar la reproyección), cadencia irreal (3 exposiciones cada 2 h) y movimiento propio exagerado (~120″/año). |
| Entorno | ✅ `.venv`: astropy 8.0.2, numpy 2.5.4, pillow 13.0.0; **sin** reproject/photutils/scipy. El CI instala solo `pipeline[dev]`. |

## Tareas (ordenadas por prioridad)

- [ ] **WS2-1 (P0) `GridFrame` + `reproject_to_grid` solo con numpy + astropy.** Un mapa de píxeles por frame:
  centros de la grilla → `all_pix2world` (grilla) → `all_world2pix` (WCS del detector con SIP; el header trae los
  inversos AP/BP) → bilineal para data/variance, vecino más cercano para flags; `coverage` = dentro del frame y
  finito. Restar ZODI y después la mediana σ-clipeada del frame (residuo de fondo).
  *Acepta:* `test_imaging_reproject.py` con un `SpherexImage` sintético armado sobre un header TAN-SIP real
  (guardado como texto en `pipeline/tests/fixtures/ws2/`; pedíselo a WS1 o bajalo con un Range de 57,6 KB) rotado
  −18,9° y ~175°, con una estrella gaussiana en un RA/Dec conocido: el centroide cae en `sky_to_png_xy` ± 0,3 px;
  `coverage` es falso fuera del frame; anda con `flags=None`; corre en CI sin el extra `science`.
- [ ] **WS2-2 (P0) Coadd por (temporada × detector) y diferencia** (`imaging/stack.py`). Media ponderada por
  1/VARIANCE. Con FLAGS: excluir `DEFAULT_BAD` (si un píxel queda sin ningún input, usar todos y anotarlo). Sin
  FLAGS: p. ej. recorte σ por píxel cuando hay ≥ 5 inputs. `meta` del coadd con exactamente los campos de 0.3.0:
  `kind="coadd"`, `season`, `mjd` (media de los inputs), `mjd_start`, `mjd_end`, `n_inputs`, `input_ids`,
  `wavelength_min_um` / `wavelength_max_um` (cuando haya λ). `difference(a, b)` entre coadds del mismo detector.
  *Acepta:* tests: N frames de varianza σ² → coadd = media y varianza σ²/N; un píxel `HOT` queda excluido; la
  diferencia de dos coadds con una estrella corrida 2 px da un dipolo con el signo correcto donde se espera.
- [ ] **WS2-3 (P0) Render honesto.** Modo `fixed`: stretch común por detector para todas las temporadas,
  calculado sobre el coadd con más rango dinámico y con vmax alto (sirve para ver variabilidad). Modo
  `per_frame`: para ver movimiento. Diferencias con stretch simétrico alrededor de 0. PNG "LA" con alfa 0 donde
  no hay cobertura; proteger `vmax <= vmin`.
  *Acepta:* tests: un fondo que pasa de 0,30 a 0,45 MJy/sr ya no mueve el gris mediano más de ±5 niveles (hoy
  39 → 109); una estrella ×2 entre frames da picos distintos en modo `fixed` (hoy ambos 255); NaN → alfa 0;
  `vmax == vmin` no rompe.
- [ ] **WS2-4 (P0) `build_patch` y arreglo de `build.py`.** Una sola función para el CLI y `/api/view`:
  `search_frames` → `group_seasons` (WS1) → selección **estratificada** por (temporada, detector), sin el corte
  de 40 → `fetch_cutouts` (pares + fallas; las fallas van a `provenance.notes`) → `read_spherex` →
  `reproject_to_grid` → coadds + diferencia primera vs última temporada → PNGs → `Field`.
  - `frame_id` desde `irsa.frame_id(ref)` (nunca del path); `date_obs` y `mjd` del header (MJD-AVG).
  - Detección, linking y objetos conocidos **opcionales**: si tiran `NotImplementedError`, listas vacías + nota,
    y el `Field` se escribe igual.
  - Si hay objetivo, `target_track` de WS3 → `known.json` (posición predicha en cada frame).
  - Un detector por defecto (parámetro `detectors`); `view_id(...)` determinista para WS4 (formato de PLAN §2,
    respetando el patrón `^[a-z0-9][a-z0-9-]*$` de `SkyField.id`).
  - CLI: `errante build <id>` y `errante build --ra --dec --fov-arcmin --det --group`.
  *Acepta:* `test_build_patch.py` offline (funciones de WS1 mockeadas con parches sintéticos) escribe un `Field`
  que pasa `errante validate`; con red, Barnard D1 a 5′ (`group=season`) da 3 coadds + 1 diferencia en < 90 s la
  primera vez y < 5 s la segunda (caché). Es la parte de WS2 del hito I1 (sáb 20:00).
- [ ] **WS2-5 (P0) Golden fields de los 5 objetivos** en `data/products/` (plan B de la demo, se sirven sin
  backend): `errante build <id>` con los `id` y centros de `fields.toml`, el índice SIA de WS1 y `targets.toml`
  de WS3. Para cada objetivo, los detectores donde mejor se ve; WISE 0855 probablemente solo en D5/D6 (❓ medirlo
  antes, junto con WS3); R Dra sin `*_deep` o acotado con `mjd_min`/`mjd_max` (2493 frames con deep).
  *Acepta:* `errante validate --dir data/products` OK; 5 campos, cada uno con ≥ 3 coadds de temporada (bins de
  tiempo en R Dra) en al menos un detector + diferencia + `known.json` con la posición predicha; total < 20 MB
  (regla de `AGENTS.md`); hito I2 (dom 08:00).
  `data/products/**` es de WS2 (ya mapeado en `scripts/owners.py`).
- [ ] **WS2-6 (P1) Flags como metadata** (con FLAGS de WS1-9 o de cutouts de IRSA): `flag_fractions` por frame
  (fracción de la cobertura con cada bit), `flags_at_target` (bits en el píxel del objetivo), descripciones de las
  tarjetas `MSKD`. `valid_fraction` = fracción de **cobertura**, no de flags. **Nunca** enmascarar los píxeles que
  se muestran.
  *Acepta:* test con flags sintéticos; en Barnard y R Dra se reportan `OVERFLOW`/`NONLINEAR` si aparecen.
- [ ] **WS2-7 (P1) Suma de temporadas elegidas** (`seasons=[...]` en `build_patch`).
  *Acepta:* coadd de las temporadas 0 + 2 con los `input_ids` de ambas.
- [ ] **WS2-8 (P1) Modo exposición** (`group="exposure"`, para asteroides dentro de una temporada): frames
  individuales reproyectados, stretch `per_frame`, λ por frame (`wavelength_at`), tope de frames por temporada y
  la nota "el brillo cambia por λ".
  *Acepta:* Barnard D1, temporada 0: N frames ordenados por mjd con su λ.
- [ ] **WS2-9 (P1) Falso color D1/D3/D6 y coadd con todos los detectores por temporada.** ⚠ `Frame.detector` es
  obligatorio (1–6): acordá con WS3 (contrato) y WS5 cómo se publican **antes** de implementarlo.
  *Acepta:* el acuerdo queda escrito en el PR; un campo real (p. ej. Barnard) con un frame de falso color por
  temporada que pasa `errante validate`.
- [ ] **WS2-10 (P1) Demo sintético con temporadas** (`synthetic.py`): un campo con coadds por temporada y una
  diferencia usando los campos 0.3.0, para que WS5 desarrolle el modo Diferencia sin backend. `data/demo` se
  regenera en un PR `contract:` (`python scripts/dev.py demo`). El movimiento exagerado tiene que quedar indicado.
  *Acepta:* `python scripts/dev.py validate` OK; el campo demo trae frames `kind="coadd"` con `season` y al menos
  uno `kind="difference"`, con `provenance.synthetic = true`.
- [ ] **WS2-11 (P2) `find_sources` solo para centroidar el objetivo** (desplazamiento entre la primera y la última
  temporada, para la tabla esperado/medido de WS3). Si WS3 ya lo mide con un centroide simple, no lo dupliques.
  *Acepta:* Barnard: 1,86 ± 0,5 px en la dirección del movimiento propio.
- [ ] **WS2-12 (P2) Plantilla estática** (`detect/difference.static_sky`): frame − mediana de todas las temporadas
  como capa opcional.
  *Acepta:* test con frames sintéticos: una fuente fija desaparece en la resta y una que se mueve queda.

## DROP (no hacer)

- **`link_tracks` / `score_tracks`** (linking de asteroides): el enunciado pide mostrar, no detectar; además la
  cadencia real (ráfagas de ~2 min, visitas separadas por horas o días) no se parece a la del demo.
- **Inyección-recuperación** (`inject.py`, `limits.json`, página de límites): fuera del enunciado.
- **Shift-and-stack:** fuera del enunciado y caro.
- **`reproject` / `photutils` / `scipy` en el camino P0:** el CI no instala `science`; numpy + astropy alcanza.
- **Poner en NaN los píxeles con flags en las imágenes mostradas:** el enunciado pide flags como metadata, y
  GHOST*/PERSIST caerían justo sobre los objetivos brillantes.
- **Blink de exposiciones individuales como modo principal:** parpadea por cambio de λ, no por cambio en el cielo.
- **WebP y mapas de color:** no suman para la demo.

## Gotchas (✅ verificado 2026-11-14 · 🧮 cálculo nuestro · 📄 según documentación · ❓ abierto)

- 🧮 **El movimiento total en los datos es de 1–2 píxeles:** Barnard 1,86 px, WISE 0855 1,36 px, Eps Ind B
  1,10 px; paralaje < 0,09 px; RW Aur y R Dra ~0. Nada de suavizar ni bajar resolución: grilla a los 6,15″
  nativos; el zoom ×8 (vecino más cercano) lo hace WS5.
- ✅ Cada exposición mide otra λ (filtro lineal variable, LVF): por eso el coadd es por (temporada × detector).
  Que cada temporada cubra todo el rango de λ del detector es INFERIDO (❓): verificalo con
  `wavelength_min/max_um` de los coadds.
- ✅ Barnard: ~17–25 exposiciones por detector y temporada; los pares D1/D4, D2/D5 y D3/D6 tienen tiempos
  idénticos; 181 apuntados en 48 visitas, ~2 min entre apuntados de una misma visita.
- ✅ Cobertura despareja (elegí detectores con esto): Eps Ind B tiene D1/D4 con 3 frames en la 1.ª temporada y 0 en
  la última; WISE 0855 no tiene QR3 y su 1.ª temporada trae 3–8 frames por detector; R Dra tiene ~89 frames en
  D2/D5 contra ~580 en el resto. Mostrá siempre `n_inputs`.
- ✅ Sin restar ZODI (cambia con la temporada y la λ), un stretch fijo hace "titilar" el fondo: con un fondo
  sintético de 0,30 → 0,45 MJy/sr el gris mediano pasa de 39 a 109.
- ✅ `SOURCE` marca ~68 % de los píxeles (no es malo). `OUTLIER`/`TRANSIENT` pueden caer sobre un objeto que se
  mueve: no los sumes a la máscara del coadd (`DEFAULT_BAD` no los incluye).
- ✅ `GHOST`, `GHOST_FPA` y `GHOST_EXT` (fuente brillante en el frame, en otro detector o fuera del FOV) están en
  `DEFAULT_BAD`: alrededor de Barnard, R Dra o Eps Ind A (a 402″ de B; entra con FOV ≥ 14′) pueden marcar mucha
  área (INFERIDO). ❓ saturación (`OVERFLOW`/`NONLINEAR`) en Barnard y R Dra.
- ✅ Los cutouts de IRSA vienen rotados distinto según el frame (−19°, ~175°) y con `CRPIX` corridos (también
  `CRPIX1A`/`CRPIX1W`): usá siempre el WCS del archivo que leés.
- ✅ Header IMAGE: `RA---TAN-SIP` con A/B/AP/BP_ORDER = 3, escala ≈ 6,151″, `PSF_FWHM` ≈ 7,5″ en D1 (~1,2 px).
- ✅ El camino S3 (WS1-4) no trae FLAGS hasta WS1-9: `GridFrame.flags = None` tiene que funcionar en todo.
- ✅ `Frame.mjd` = mitad de la exposición (`MJD-AVG`); `MJD-OBS` es el inicio.
- ✅ Pillow 13 todavía acepta `Image.fromarray(..., mode="L")`, pero conviene no pasar `mode` (se infiere del dtype).
- ✅ WISE 0855: J = 25,0, W2 = 13,7 (Vega). Que solo se vea en D5/D6 es INFERIDO: nadie midió píxeles todavía.
- `*.fits` está en `.gitignore`: fixtures como texto (headers) o `.npz`.

## Dependencias

- **WS1:** hasta que estén `search_frames` y `read_patch`, trabajá con `SpherexImage` sintéticos (header real
  como fixture) y mockeá las funciones de WS1 en `test_build_*`.
- **Contrato 0.3.0 (WS3, objetivo sáb 15:00):** mientras tanto, lo nuevo va en `GridFrame.meta`. Con 0.1.0 un
  coadd ya entra como `Frame` (`obs_id` = id del coadd, `mjd` = media de los inputs); `kind`, `season`, etc. se
  vuelcan cuando se mergee. Decisiones pendientes que te afectan: qué llevan `obs_id`/`release`/`date_obs` en
  coadds y diferencias, y cómo se publica algo sin un único detector (WS2-9).
- **WS3:** `targets.toml` y `target_track` para los golden fields y la posición predicha.
- **WS4:** llama a `build_patch` desde `/api/view` (caché en `data/cache/views/`, timeouts): acordá `view_id` y
  la firma temprano.
- **WS5:** consume `Field`; avanza con `data/demo` (WS2-10 le da coadds y diferencia sintéticos).

## Prompt de arranque (pegalo en Claude Code / Codex)

> Sos el agente de WS2 (imagen) del repo del equipo para NASA Space Apps 2026, reto "Planet X and SPHEREx". Leé
> `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACT.md`, `docs/COLLABORATION.md` y `tasks/WS2-imaging-detection.md`.
> Trabajá SOLO en tus rutas: `pipeline/errante/imaging/`, `pipeline/errante/detect/`, `build.py`,
> `synthetic.py`, los subcomandos `build`/`demo` de `cli.py` y los tests `test_imaging_*`, `test_detect_*` y
> `test_build_*`. Empezá por WS2-1 (`GridFrame` + `reproject_to_grid` solo con numpy + astropy, testeado con un
> header TAN-SIP real rotado) y WS2-2 (coadd 1/VARIANCE + diferencia). No agregues `reproject`, `photutils` ni
> `scipy`: el CI no los instala. No cambies `models.py`: lo nuevo va en `GridFrame.meta` hasta el contrato 0.3.0.
> No inventes servicios ni formatos: verificá contra un archivo real; si no tenés red, dejá tests offline y un test
> `@pytest.mark.network`. Corré `python scripts/dev.py check` (Windows: `py scripts/dev.py check`; en Mac/Linux
> `make check` también sirve), mostrame el diff antes de commitear y commiteá como `ws2: <verbo + qué>` con el
> trailer `Co-Authored-By:` del agente.
