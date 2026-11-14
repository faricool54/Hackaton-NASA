# Cómo trabajamos en paralelo sin pisarnos

Plan de ejecución actual: [PARALLEL_PLAN.md](PARALLEL_PLAN.md) (pendientes, entregables y dependencias).
WS4 está reservado por **rpccp** (rocco) con Codex; ver [TEAM.md](TEAM.md).

Somos 5 personas, cada una con uno o más agentes (Claude Code / Codex), todos sobre el mismo repo y con
~36 h. La idea es que **los conflictos no puedan pasar por diseño**, y que cuando pasen sean chicos y obvios.

## TL;DR — las 8 reglas

1. **Una persona = un workstream = sus carpetas.** Nadie edita carpetas ajenas. ¿De quién es un archivo?
   `python scripts/owners.py --who <ruta>`.
2. **Nadie pushea a `main`.** Todo entra por **PR chico** (squash). `main` está protegida (PR + CI verde).
3. **Una rama por tarea**: `wsN/<tarea>-<desc>` (ej. `ws5/coord-input`), de vida corta (1–3 h).
4. **Un agente = una rama = una carpeta de trabajo (worktree).** Nunca dos agentes en la misma carpeta.
5. **Archivos compartidos tienen un único dueño** (tabla abajo). El contrato cambia solo en un PR `contract:`.
6. **Antes de cada push**: `git pull origin main` (merge, sin rebase) → `python scripts/dev.py check`
   (incluye la guardia de ownership) → `git push`. **Nunca** `push --force`.
7. **Los archivos generados no se resuelven a mano**: se regeneran (`schema`, `data/demo`, `package-lock.json`).
8. **Reservá antes de empezar**: issue asignado a vos (o aviso en el chat "tomo WS2-3"). Sin reserva, no se arranca.

## 1. Quién es dueño de qué

| Dueño | Rutas | Tipo de rama |
|---|---|---|
| **WS1** Datos | `pipeline/errante/data/`, `pipeline/errante/settings.py`, `pipeline/tests/test_data_*`, `test_network.py`, `pipeline/tests/fixtures/ws1/`, `data/index/`, `docs/DATA.md` | `ws1/...` |
| **WS2** Imagen | `pipeline/errante/imaging/`, `detect/`, `build.py`, `synthetic.py`, `data/products/` (golden fields), `pipeline/tests/test_imaging_*`, `test_detect_*`, `test_build_*`, `test_synthetic.py`, `test_grid_motion_flags.py`, `pipeline/tests/fixtures/ws2/` | `ws2/...` |
| **WS3** Ciencia | `pipeline/errante/science/`, `pipeline/errante/config/`, `pipeline/tests/test_science_*`, `docs/SCIENCE.md` | `ws3/...` |
| **WS4** Backend/CI | `backend/`, `.github/`, `scripts/`, `Makefile`, config de deploy | `ws4/...` |
| **WS5** Frontend | `frontend/` (salvo `src/api/types.ts`) | `ws5/...` |
| **WS6** Entrega | `docs/submission/`, `docs/CHALLENGE.md` | `ws6/...` |
| **WS7** Sistemas 3D (PR pendiente, ver §7) | `pipeline/errante/systems/`, `pipeline/tests/test_systems.py`, `frontend/src/three/`, `frontend/src/components/{SystemViewer,BodyPanel}.tsx`, `frontend/src/pages/{SystemsPage,SystemPage}.tsx`, `docs/VISION_3D.md` | `ws7/...` |
| **Contrato** (dueño: WS3) | `pipeline/errante/models.py`, `products.py`, `shared/schema/`, `frontend/src/api/types.ts`, `data/demo/`, `test_contract.py` | `contract/...` |
| **Coordinación** (dueño: quien coordina) | `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/*.md` (resto), `tasks/README.md` | `chore/...` |

- Cada WS marca casillas solo en **su** `tasks/WSx-*.md`.
- Compartidos de bajo riesgo (cualquiera, cambios chicos y aditivos): `pipeline/errante/cli.py`,
  `pipeline/pyproject.toml` (agregar dependencias: una línea por PR), `notebooks/`.
- La referencia es **esta tabla**; [`scripts/owners.py`](../scripts/owners.py) la implementa para la guardia y la
  tabla de [`AGENTS.md`](../AGENTS.md) se alinea con ella. Las cambia quien coordina, en un PR `chore:`.

### La guardia automática

`python scripts/dev.py owners` (y por lo tanto `check`) mira los archivos que tu rama cambió respecto de
`origin/main` y **falla si una rama `wsN/...` toca archivos de otro dueño**. El workstream se deduce del nombre
de la rama, del título del PR (`wsN: ...`) o de `ERRANTE_WS`. En CI corre como job `owners` en cada PR
(es informativo: quien coordina puede mergear igual si tiene sentido).

## 2. Ramas, PRs y merges

```bash
git fetch origin
git switch -c ws2/coadd origin/main      # rama nueva desde main actualizado
# ... trabajo, commits chicos ...
git pull origin main                     # traer lo último de main (merge; sin rebase, sin force)
python scripts/dev.py check              # lint + tests + schema + build + ownership
git push -u origin ws2/coadd
gh pr create --fill --base main          # título: "ws2: add per-season coadd"
```

- **Título del PR**: `wsN: verbo + qué` · `contract: ...` · `chore: ...`. Commits igual.
- **Merge**: squash. Si el PR solo toca tu carpeta y CI está verde, **lo mergeás vos** (no hace falta review).
  PRs `contract:` y `chore:` necesitan 1 OK de alguien afectado (WS2/WS4/WS5 para el contrato).
- **Conflicto al actualizar**: lo resuelve **el autor del PR que llegó segundo**, en su rama
  (`git pull origin main`, resolver, `check`, push). Si el conflicto es en un archivo que no es tuyo, pará y
  avisá al dueño en vez de "arreglarlo".
- **PRs chicos**: idealmente < 300 líneas y < 3 h de trabajo. Mejor 3 PRs que uno gigante.
- **`main` roto**: primero se revierte (`git revert <sha>` en una rama `chore/revert-...`), después se arregla.
- **Ramas `claude/*`** (Claude Code web las crea solas): están bien, pero el **título del PR** tiene que
  empezar con `wsN:` (la guardia lo usa).

## 3. Varios agentes (en una máquina o en varias)

- **Cada agente en su worktree y su rama.** Dos agentes en la misma carpeta se pisan el working tree
  aunque estén en "ramas distintas".
  ```bash
  git fetch origin
  git worktree add -b ws2/coadd ../hn-ws2-coadd origin/main
  cd ../hn-ws2-coadd
  python scripts/dev.py setup        # venv propio: los editables apuntan a la carpeta donde se instalaron
  ```
  Al terminar: `git worktree remove ../hn-ws2-coadd`.
- **Puertos**: el frontend busca puerto libre solo; el backend usa `API_PORT` (`API_PORT=8001 python scripts/dev.py api`).
- **Mensaje fijo para tu agente** (pegalo al empezar cada sesión, además del prompt de tu `tasks/WSx`):

  > Trabajás en la rama `<tu-rama>` y SOLO en las rutas de WS<N> (ver `docs/COLLABORATION.md`).
  > Reglas de git: nunca `git add -A` ni `git add .` — stageá archivos por nombre; nunca `git push --force`,
  > `reset --hard` ni `checkout`/`switch` a otra rama; nunca commitees en `main`. Antes de commitear corré
  > `python scripts/dev.py check` (incluye la guardia de ownership) y mostrame el diff. Si necesitás cambiar
  > un archivo de otro workstream o del contrato, NO lo hagas: decime qué hace falta y lo coordino yo.
  > Commits con el trailer `Co-Authored-By:` del agente.

## 4. Archivos calientes: protocolo

| Archivo | Protocolo |
|---|---|
| `models.py`, `types.ts`, `shared/schema/`, `products.py` | **Un único PR `contract:` a la vez**, del dueño del contrato. Pedidos de campos nuevos → al chat. Preferir campos opcionales. Al mergear: avisar "contrato X.Y mergeado, hagan `git pull origin main`". |
| `data/demo/` | Solo se regenera en PRs `contract:` (`python scripts/dev.py demo`). En conflicto: tomar la versión de `main` y regenerar. |
| `shared/schema/` | Generado: en conflicto, `python scripts/dev.py schema`. |
| `frontend/package-lock.json` | Solo WS5 agrega dependencias. En conflicto: `git checkout origin/main -- frontend/package-lock.json` y `npm install` (nunca a mano). |
| `pipeline/pyproject.toml` | Agregar una dependencia = una línea en un PR chico. En conflicto: quedarse con ambas líneas. |
| `build.py` | Dueño WS2. WS1 propone cambios por chat o PR revisado por WS2. |
| `docs/DATA.md` | Dueño WS1. Los demás agregan al final, en "Notas de otros WS" (solo agregar, nunca editar arriba). |
| `AGENTS.md`, `CLAUDE.md`, `tasks/README.md`, docs de coordinación | Solo quien coordina (`chore/...`). Los cambios de prioridades se anotan en un solo lugar (el doc de plan/alcance que el equipo elija en el kickoff). |

## 5. Reservar tareas y comunicarse

- **Reserva = issue de GitHub asignado** (atómico, no genera conflictos de merge). Título `WS2-3: coadd por temporada`.
  Si no hay issue, alcanza con avisar en el chat "tomo WS2-3" antes de empezar.
- Al abrir el PR, linkear la tarea (`tasks/WS2-...md` · WS2-3) o el issue (`Closes #N`).
- **Sync de 10 min cada ~4 h**: qué mergeé, qué sigue, qué me bloquea. Cambios de alcance → al doc de plan/alcance acordado.
- Ventanas: el **contrato 0.3.0** se mergea temprano (sáb ~15:00); después, cambios de contrato solo si son
  imprescindibles. **Feature freeze dom 17:00**: desde ahí solo bugs.

## 6. Checklist antes de cada push

- [ ] Estoy en **mi** rama (`git branch --show-current`), no en `main` ni en la de otro.
- [ ] `git status` solo muestra archivos de mi workstream.
- [ ] `git pull origin main` hecho.
- [ ] `python scripts/dev.py check` verde.
- [ ] Commits con mensaje `wsN: ...` (+ trailer `Co-Authored-By:` si los hizo un agente).

## 7. Integrar ramas grandes que ya tocaron archivos de otros (hoy: WS7 y `ws4/integrate-challenge-guides`)

**Registro histórico: integración completada.** Los PRs #1, #2 y #3 ya están en `main` (`859ae5e`).
No repetir estos pasos: las tareas nuevas parten de `origin/main` y siguen el plan enlazado arriba.

Antes de estas reglas se subieron dos ramas que tocan contrato, frontend, backend y docs de coordinación:
`claude/ecstatic-turing-rcu8jq` (WS7, sistemas 3D) y `ws4/integrate-challenge-guides` (rocco, construida **encima**
de WS7: guías del reto, matriz de requisitos, validación de los 5 objetivos, registro de uso de IA). Para traerlas a
`main` sin pisar a nadie:

1. **El equipo decide** si WS7 entra y con qué prioridad (el enunciado no pide 3D; el criterio *Relevance* premia
   el objetivo central). La rama de rocco ya incluye WS7: si entra una, entran las dos juntas.
2. **Un solo PR** desde `ws4/integrate-challenge-guides` hacia `main` (contiene los commits de WS7), revisado por
   WS5 (frontend), WS4 (backend) y quien coordina. La guardia `owners` lo va a marcar: es esperado en este PR puntual.
   Antes de abrirlo, quien lo maneja actualiza la rama:
   ```bash
   git fetch origin
   git switch ws4/integrate-challenge-guides
   git merge origin/main        # trae runner, guardia, CI y estas reglas: archivos nuevos, sin conflictos
   python scripts/dev.py check
   git push
   ```
   Si aparece algún conflicto: `shared/schema/` y `data/demo/` se regeneran (`python scripts/dev.py schema` /
   `demo`); `frontend/package-lock.json` se toma de la rama (es la que agrega `three`) y se corre `npm install`.
3. Después de ese merge, quien coordina integra **encima** las correcciones verificadas de datos y ciencia
   (`docs/DATA.md`, `docs/SCIENCE.md`, centros propagados en `fields.toml`, comandos `python scripts/dev.py`) en un
   PR `chore:` aparte. Así nadie resuelve los conflictos de otro.
4. Desde ahí, cada uno en ramas `wsN/...` y solo en sus rutas.
