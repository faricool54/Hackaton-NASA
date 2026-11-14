# Errante *(nombre provisorio)* · NASA Space Apps Challenge 2026 — "Planet X and SPHEREx"

> "Errante" es un nombre de trabajo que salió del esqueleto armado con un asistente de IA. **El equipo decide el
> nombre, la idea y el tagline con sus palabras en el kickoff** (regla de SI, ver [docs/KICKOFF.md](docs/KICKOFF.md)).

Herramienta web pública para el reto "Planet X and SPHEREx". El usuario ingresa las coordenadas (RA/Dec) de un
parche de cielo, o elige uno de los cinco objetivos de prueba del enunciado (Barnard's Star, Epsilon Indi B,
WISE 0855, RW Aurigae y R Draconis). La herramienta muestra la serie de imágenes infrarrojas reales de **NASA
SPHEREx** de ese parche como un pequeño video, para que cualquiera vea qué se movió o cambió entre épocas.
Texto oficial y reglas: [docs/CHALLENGE.md](docs/CHALLENGE.md).

## Estado (sáb 14/11, ~11:40 UTC−3)

- ✅ **Esqueleto funcional de punta a punta con datos SINTÉTICOS**, etiquetados como tales (badge en la UI). El
  contrato pipeline → backend → frontend y la CI (`python`, `frontend`) andan.
- ⏳ **Datos reales: pendientes.** Búsqueda en IRSA, lectura de S3, coadds y `/api/view` son stubs o todavía no
  existen. El flujo "RA/Dec → video" es el P0 del plan.
- ⏳ Faltan deploy público, repo público (hoy privado) y `LICENSE`.
- 📌 Plan vigente: [docs/PLAN.md](docs/PLAN.md), una propuesta que se valida en el kickoff. Hallazgos con
  evidencia: [docs/REVIEW-2026-11-14.md](docs/REVIEW-2026-11-14.md). Cierre de la entrega: **dom 15/11 23:59,
  hora del Local Event**.

## Empezar en 5 minutos

Requisitos: **Python ≥ 3.11** (la CI usa 3.12; `uv` es opcional y acelera el setup), **Node ≥ 20** y git.

```bash
git clone https://github.com/faricool54/Hackaton-NASA && cd Hackaton-NASA   # hoy privado: hay que ser colaborador
python scripts/dev.py setup     # venv + pipeline/backend + frontend   (Windows: py scripts/dev.py setup)
python scripts/dev.py web       # http://localhost:5173  (datos demo, sin backend)
python scripts/dev.py api       # opcional: backend en http://localhost:8000/docs; web con ?mode=api (pasa a ?source=api, WS5)
python scripts/dev.py check     # lo mismo que la CI: correrlo antes de cada push
```

Otras tareas: `doctor` (qué falta instalar), `setup-science` (libs científicas pesadas), `demo`, `schema`,
`validate`, `test`, `test-py`, `test-web`, `lint`, `fmt`. En Mac/Linux, `make <tarea>` sigue funcionando: es un
wrapper de `scripts/dev.py`.

**Cómo contribuir:** rama `wsN/descripcion-corta` (o `contract/…`, `chore/…`; las ramas `claude/*` de Claude Code
web se aceptan si el título del PR empieza con `wsN:`) → PR a `main` → CI verde → squash merge. Commits:
`wsN: verbo + qué`. Detalle en [docs/WORKFLOW.md](docs/WORKFLOW.md) y [AGENTS.md](AGENTS.md).

## Por dónde empezar a leer

1. [docs/KICKOFF.md](docs/KICKOFF.md): agenda y decisiones del kickoff.
2. [docs/PLAN.md](docs/PLAN.md): prioridades P0/P1/P2, arquitectura, contrato 0.3.0 y cronograma.
3. [docs/REVIEW-2026-11-14.md](docs/REVIEW-2026-11-14.md): qué está bien, qué falta, con evidencia.
4. Tu archivo en [tasks/](tasks/) y [AGENTS.md](AGENTS.md).

Referencia: [docs/CHALLENGE.md](docs/CHALLENGE.md) (reto, reglas, trazabilidad) ·
[docs/TEAM.md](docs/TEAM.md) · [docs/WORKFLOW.md](docs/WORKFLOW.md) ·
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/CONTRACT.md](docs/CONTRACT.md) ·
[docs/DATA.md](docs/DATA.md) (hechos verificados sobre los datos) · [docs/SCIENCE.md](docs/SCIENCE.md) ·
[docs/submission/](docs/submission/) (checklist, demo, formulario).

## Workstreams y dueños

Somos 5. La asignación de personas se decide en el kickoff y queda en [docs/TEAM.md](docs/TEAM.md). Cada WS
marca casillas solo en su propio `tasks/WSx-*.md`.

| WS | Tema | Rutas de las que es dueño | Tareas |
|---|---|---|---|
| WS1 | Datos | `pipeline/errante/data/**`, `pipeline/errante/settings.py`, `pipeline/tests/test_data_*.py`, `test_network.py`, `pipeline/tests/fixtures/ws1/**`, `data/index/**`, `docs/DATA.md` (dueño; los demás le pasan hechos o agregan en la sección "Notas de otros WS" al final), `cli.py search` | [WS1](tasks/WS1-data-access.md) |
| WS2 | Imagen | `pipeline/errante/imaging/**`, `pipeline/errante/detect/**`, `pipeline/errante/build.py` (dueño, coordina con WS1), `pipeline/errante/synthetic.py`, `data/products/**` (golden fields), `cli.py build/demo`, tests `test_imaging_*` / `test_detect_*` / `test_build_*` / `test_synthetic.py` / `test_grid_motion_flags.py`, `pipeline/tests/fixtures/ws2/**` | [WS2](tasks/WS2-imaging-detection.md) |
| WS3 | Ciencia / objetivos | `pipeline/errante/science/**`, `pipeline/errante/config/**`, `docs/SCIENCE.md`, `pipeline/tests/test_science_*.py`; además es dueño del PR de contrato 0.3.0 | [WS3](tasks/WS3-science.md) |
| CONTRATO | solo vía PR `contract:` | `pipeline/errante/models.py`, `pipeline/errante/products.py`, `shared/schema/**`, `frontend/src/api/types.ts`, `data/demo/**` (se regenera con `python scripts/dev.py demo`), `pipeline/tests/test_contract.py` | [docs/CONTRACT.md](docs/CONTRACT.md) |
| WS4 | Backend + deploy + coordinación | `backend/**`, `.github/**`, `Makefile`, `scripts/**`, config de deploy; coordina `main` (mergea `contract:`/`chore:`, revierte si se rompe; los PR de carpeta propia los mergea su autor) | [WS4](tasks/WS4-backend.md) |
| WS5 | Frontend | `frontend/**` (salvo `types.ts` → contrato; textos largos de About/hero coordinados con WS6) | [WS5](tasks/WS5-frontend.md) |
| WS6 | Entrega | `docs/submission/**`, `docs/CHALLENGE.md`, sección "Use of SI" y créditos del README | [WS6](tasks/WS6-product-submission.md) |
| WS7 | Sistemas 3D (rama `claude/ecstatic-turing-rcu8jq`, **PR pendiente**; prioridad a decidir en el kickoff ([PLAN §6](docs/PLAN.md))) | `pipeline/errante/systems/**`, `pipeline/tests/test_systems.py`, `frontend/src/three/**`, `frontend/src/components/{SystemViewer,BodyPanel}.tsx`, `frontend/src/pages/{SystemsPage,SystemPage}.tsx`, `docs/VISION_3D.md` | en su rama: `tasks/WS7-3d-systems.md` |
| Coordinación | quien coordine (sugerido WS4) | `AGENTS.md`, `CLAUDE.md`, `README.md` (resto), `docs/PLAN.md`, `docs/KICKOFF.md`, `docs/TEAM.md`, `docs/WORKFLOW.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACT.md`, `docs/REVIEW-*.md`, `tasks/README.md` | [tasks/README.md](tasks/README.md) |

## Estructura

```
pipeline/   paquete Python `errante`: búsqueda IRSA/S3 → reproyección/coadds → productos JSON/PNG + CLI `errante`
backend/    FastAPI `errante_api`: sirve productos y (plan) /api/view para coordenadas arbitrarias
frontend/   Vite + React + TypeScript: home, visor tipo blink, espectro, about
shared/     JSON Schema generado del contrato (no editar a mano: `python scripts/dev.py schema`)
data/       demo/ = datos SINTÉTICOS commiteados · products/ = productos reales · cache/ = descargas (ignorado)
scripts/    dev.py: runner multiplataforma (lo mismo que la CI) · owners.py: guardia de ownership
docs/       plan, reto, arquitectura, contrato, datos, ciencia, entrega (docs/submission/)
tasks/      tareas por workstream con prompt de arranque para agentes
notebooks/  exploración
```

## Use of SI / AI disclosure

*Owned by WS6. TODO(team): confirm every line before submitting.*

- **Tools:** AI coding assistants were used in this project. TODO(team): exact list (for example Claude Code by
  Anthropic; add others such as Codex if used).
- **Code and docs:** the initial repository scaffold (commit authored by "Claude", 2026-11-14), its review
  against the official challenge text, and this documentation were produced with an AI assistant. Code written
  since then is AI-assisted and reviewed by team members. Commits made with an agent carry a `Co-Authored-By:`
  trailer that names the tool.
- **Idea and decisions:** the project idea, name, tagline and key decisions are the team's own. TODO(team):
  state how the team decided them.
- **Images and video:** any SI-generated image or video carries a visible watermark. No NASA branding (logos,
  flags, mission patches or identifiers) is used anywhere.
- **Data:** all science images shown as SPHEREx are real SPHEREx data. Synthetic demo data are labeled as
  synthetic.

## Créditos de datos (solo texto, sin logos)

- **SPHEREx:** NASA / JPL-Caltech / IPAC, vía NASA/IPAC Infrared Science Archive (IRSA). Releases DR1 y QR3.
- Solo si se usan: **Gaia DR3** (ESA/Gaia/DPAC) · **Aladin Lite** (CDS, Estrasburgo) · **Sesame** (CDS; espejo de
  CfA) · HiPS **2MASS / AllWISE** (espejos de IRSA) · **SkyBoT** (IMCCE).
- Inspiración citada por el reto: WiseView y Backyard Worlds.
