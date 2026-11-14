# Tareas por workstream

> **Manda [`docs/PLAN.md`](../docs/PLAN.md).** Sus prioridades (§4) y su cronograma (§5) reemplazan cualquier
> otra cosa; si un archivo de `tasks/` lo contradice, gana PLAN.md y se avisa a quien coordina. Los cambios de
> alcance se deciden en el sync y se anotan solo en PLAN.md.

Cada archivo es autocontenido: objetivo, rutas, qué recibís y qué entregás, estado verificado, tareas con criterio
de aceptación, DROP, gotchas, dependencias y un **prompt de arranque** para pegarle a tu agente (Claude Code o
Codex). Quién hace qué se decide en el kickoff ([`docs/KICKOFF.md`](../docs/KICKOFF.md)) y queda en
[`docs/TEAM.md`](../docs/TEAM.md). Las reglas de git y de trabajo en paralelo están en
[`docs/COLLABORATION.md`](../docs/COLLABORATION.md).

| Archivo | Workstream | P0 en una línea |
|---|---|---|
| [WS1-data-access.md](WS1-data-access.md) | WS1 Datos | `search_frames` (SIA2 VOTable + TAP), `read_patch` por Range en S3 con caché, fallback cutout IBE, índice SIA de los 5 objetivos, `docs/DATA.md` corregido |
| [WS2-imaging-detection.md](WS2-imaging-detection.md) | WS2 Imagen | `reproject_to_grid`, coadd por (temporada, detector), `difference(a, b)`, stretch común, `build_patch` que escribe aunque no haya detección |
| [WS3-science.md](WS3-science.md) | WS3 Ciencia / objetivos | los 5 objetivos con pm/plx/época en el repo, movimiento esperado, método de variabilidad, PR de contrato 0.3.0, textos científicos |
| [WS4-backend.md](WS4-backend.md) | WS4 Backend + deploy + coordinación | `main` protegida, `/api/view` con caché, API endurecida, tests sin red, deploy público |
| [WS5-frontend.md](WS5-frontend.md) | WS5 Frontend | estado en la URL, caja RA/Dec + 5 chips + FOV, viewer con zoom ×8, retícula, posición predicha y Blink/Diferencia, metadata |
| [WS6-product-submission.md](WS6-product-submission.md) | WS6 Entrega | idea/nombre del equipo, CHECKLIST, video ≤ 30 s, deck ≤ 7, PROJECT.md, "Use of SI", links públicos, envío dom 20:00 |

Hitos ([PLAN §5](../docs/PLAN.md), hora local UTC−3, confirmar la zona del Local Event): kickoff sáb 12:00 ·
contrato 0.3.0 sáb 15:00 · **I1** sáb 20:00 · **I2** dom 08:00 · deploy público dom 12:00 · freeze dom 17:00 ·
**Submit for Judging dom 20:00**. Sync de 10 min cada ~4 h.

## Cómo leer las prioridades

- **P0** = sin esto no hay demo · **P1** = lo que nos diferencia · **P2** = si sobra tiempo · **DROP** = no
  hacer (retomarlo se discute en el sync y se anota en PLAN.md).
- Dentro de cada archivo las tareas están **ordenadas**: tomá la primera P0 libre de tu WS.
- *Acepta:* es el criterio verificable. Una tarea está terminada con eso cumplido + `python scripts/dev.py check`
  verde + PR mergeado.
- Hechos externos: ✅ verificado 2026-11-14 · 📄 según documentación · ❓ abierto (no lo des por cierto).

## Quién es dueño de qué

| WS | Rutas (dueño) |
|---|---|
| **WS1** Datos | `pipeline/errante/data/**`, `pipeline/errante/settings.py`, `pipeline/tests/test_data_*.py`, `test_network.py`, `pipeline/tests/fixtures/ws1/**`, `data/index/**`, `docs/DATA.md` (dueño; los demás le pasan hechos o agregan en la sección "Notas de otros WS" al final), `cli.py search` |
| **WS2** Imagen | `pipeline/errante/imaging/**`, `pipeline/errante/detect/**`, `pipeline/errante/build.py` (dueño, coordina con WS1), `pipeline/errante/synthetic.py`, `data/products/**` (golden fields), `cli.py build/demo`, tests `test_imaging_*` / `test_detect_*` / `test_build_*` / `test_synthetic.py` / `test_grid_motion_flags.py`, `pipeline/tests/fixtures/ws2/**` |
| **WS3** Ciencia/objetivos | `pipeline/errante/science/**`, `pipeline/errante/config/**`, `docs/SCIENCE.md`, `pipeline/tests/test_science_*.py`; además es dueño del PR de contrato 0.3.0 |
| **CONTRATO** (solo vía PR `contract:`) | `pipeline/errante/models.py`, `pipeline/errante/products.py`, `shared/schema/**`, `frontend/src/api/types.ts`, `data/demo/**` (se regenera con `python scripts/dev.py demo`), `pipeline/tests/test_contract.py` |
| **WS4** Backend+deploy+coordinación | `backend/**`, `.github/**`, `Makefile`, `scripts/**`, config de deploy; coordina `main` (mergea `contract:`/`chore:`, revierte si se rompe; los PR de carpeta propia los mergea su autor) |
| **WS5** Frontend | `frontend/**` (salvo `types.ts` → contrato; textos largos de About/hero coordinados con WS6) |
| **WS6** Entrega | `docs/submission/**`, `docs/CHALLENGE.md`, sección "Use of SI" y créditos del README |
| **WS7** Sistemas 3D (rama `claude/ecstatic-turing-rcu8jq`, **PR pendiente**; prioridad a decidir en el kickoff ([PLAN §6](../docs/PLAN.md))) | `pipeline/errante/systems/**`, `pipeline/tests/test_systems.py`, `frontend/src/three/**`, `frontend/src/components/{SystemViewer,BodyPanel}.tsx`, `frontend/src/pages/{SystemsPage,SystemPage}.tsx`, `docs/VISION_3D.md` |
| **Coordinación** (quien coordine, sugerido WS4) | `AGENTS.md`, `CLAUDE.md`, `README.md` (resto), `docs/PLAN.md`, `docs/KICKOFF.md`, `docs/TEAM.md`, `docs/WORKFLOW.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACT.md`, `docs/REVIEW-*.md`, `tasks/README.md` |

Cada WS marca casillas **solo en su propio** `tasks/WSx-*.md`. ¿Necesitás algo de otra ruta? Dejá
`TODO(WSy): ...` y avisá en el chat; nada de "arreglos de paso" en carpetas ajenas. ¿De quién es un archivo?
`python scripts/owners.py --who <ruta>`; `python scripts/dev.py check` incluye esa guardia.

## Cómo tomar ("reservar") una tarea

1. Fijate que nadie la tenga (chat del equipo e issues abiertos).
2. **Antes de empezar**, abrí un issue con la plantilla "Tarea", asignado a vos y titulado `WSx-N: ...` (labels
   `wsN` y `task` cuando existan, ver WS4-1), y/o avisá en el chat ("tomo WS5-3"). Sin reserva no se arranca.
3. Una tarea = una rama = un PR: `wsN/descripcion-corta` (`contract/...` para el contrato, `chore/...` para
   infraestructura). Las ramas `claude/*` que crea Claude Code web se aceptan si el título del PR empieza con `wsN:`.
4. PR a `main`, CI verde, squash merge (quién mergea y cuándo hace falta un OK: COLLABORATION §2). Commits
   `wsN: verbo + qué`; los hechos con un agente llevan el trailer `Co-Authored-By:`.
5. En ese mismo PR marcá `[x]` en tu archivo con el link: `- [x] **WS5-3 (P0) ...** — #12` (el número existe
   recién al abrir el PR: agregalo en un commit más antes del merge).
6. Si quedás trabado más de ~30 min o la tarea cambia de manos, avisá en el chat y actualizá el issue.

## Plantilla para pedirle una tarea al agente

> Leé `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACT.md` y `tasks/WSx-....md`. Implementá la tarea **WSx-N** tocando
> solo las rutas de mi workstream (si necesitás algo de otra ruta, dejá un `TODO(WSy)` y decímelo). Agregá tests,
> corré `python scripts/dev.py check` (Windows: `py scripts/dev.py check`) y, si toca la UI, mirala en el navegador
> en desktop y en ancho de celular. Mostrame el diff y cómo lo probaste antes de commitear. Commit
> `wsN: verbo + qué` con el trailer `Co-Authored-By:` del agente.

Al empezar cada sesión, pegale además el mensaje fijo de reglas de git de
[`docs/COLLABORATION.md`](../docs/COLLABORATION.md) §3.

## Gotchas para todos

- Runner único: `python scripts/dev.py <tarea>` (Windows: `py scripts/dev.py <tarea>`). Tareas: `setup`,
  `setup-science`, `doctor`, `demo`, `schema`, `validate`, `api`, `web`, `test`, `test-py`, `test-web`, `lint`,
  `fmt`, `owners`, `check`. `check` = lo mismo que CI (+ la guardia de ownership). En Mac/Linux `make <tarea>`
  sigue andando (el `Makefile` es un wrapper de `dev.py`); en Windows `make` no está instalado ✅.
- Varios agentes en la misma máquina: un `git worktree` por tarea y **un `.venv` por worktree**
  (`python scripts/dev.py setup` adentro); las instalaciones editables apuntan al checkout donde se instalaron ✅.
- Archivos generados no se resuelven a mano: `data/demo/` (contrato) solo se regenera en PRs `contract:`; ante
  un conflicto, tomá la versión de `main` y regenerá (`python scripts/dev.py demo` / `schema`).
- No inventes respuestas de servicios externos: tests de red con `@pytest.mark.network`. CDS Estrasburgo está
  degradado ✅: usá los espejos de IRSA y CfA que indica cada archivo.
- Nada sintético presentado como real; nada de "descubrimos".
