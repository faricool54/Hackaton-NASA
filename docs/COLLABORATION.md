# Cómo trabajamos en paralelo sin pisarnos

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
- La referencia es la tabla de [`AGENTS.md`](../AGENTS.md); [`scripts/owners.py`](../scripts/owners.py) la implementa
  para la guardia. Las dos se mantienen iguales (las cambia quien coordina, en un PR `chore:`).

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
| `AGENTS.md`, `CLAUDE.md`, `docs/PLAN.md`, `tasks/README.md` | Solo quien coordina (`chore/...`). Cambios de prioridades se anotan en `docs/PLAN.md`. |

## 5. Reservar tareas y comunicarse

- **Reserva = issue de GitHub asignado** (atómico, no genera conflictos de merge). Título `WS2-3: coadd por temporada`.
  Si no hay issue, alcanza con avisar en el chat "tomo WS2-3" antes de empezar.
- Al abrir el PR, linkear la tarea (`tasks/WS2-...md` · WS2-3) o el issue (`Closes #N`).
- **Sync de 10 min cada ~4 h**: qué mergeé, qué sigue, qué me bloquea. Cambios de alcance → `docs/PLAN.md`.
- Ventanas: el **contrato 0.3.0** se mergea temprano (sáb ~15:00); después, cambios de contrato solo si son
  imprescindibles. **Feature freeze dom 17:00**: desde ahí solo bugs.

## 6. Checklist antes de cada push

- [ ] Estoy en **mi** rama (`git branch --show-current`), no en `main` ni en la de otro.
- [ ] `git status` solo muestra archivos de mi workstream.
- [ ] `git pull origin main` hecho.
- [ ] `python scripts/dev.py check` verde.
- [ ] Commits con mensaje `wsN: ...` (+ trailer `Co-Authored-By:` si los hizo un agente).

## 7. Integrar una rama que ya tocó archivos de otros (caso WS7)

La rama `claude/ecstatic-turing-rcu8jq` (WS7, 3D) se hizo antes de estas reglas y toca contrato, frontend,
backend y docs de coordinación. Para traerla a `main` sin pisar a nadie:

1. **Primero se decide en el kickoff** si entra y con qué prioridad ([`PLAN.md`](PLAN.md) §6).
2. Si entra: quien la maneja actualiza su rama con `main` y abre **un** PR
   `contract: add SystemModel (WS7, 0.2.0)`:
   ```bash
   git fetch origin
   git switch claude/ecstatic-turing-rcu8jq      # o la rama local donde trabaja
   git merge origin/main                          # merge, sin rebase ni force
   ```
   Conflictos esperables y cómo resolverlos:
   - `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACT.md`, `docs/TEAM.md`, `tasks/README.md`,
     `docs/CHALLENGE.md`: **quedarse con la versión de `main`**: `git checkout --theirs -- <archivo>` (en este merge
     *theirs* = `origin/main`) y `git add <archivo>`; después volver a agregar solo las líneas propias de
     WS7 (fila de ownership ya está; link a `docs/VISION_3D.md`). `CHALLENGE.md` de `main` ya trae el texto oficial.
   - `shared/schema/`, `data/demo/`: regenerar (`python scripts/dev.py schema` y `demo`), nunca a mano.
   - `frontend/package-lock.json`: tomar el de la rama WS7 (es la única que agrega `three`) y correr `npm install`.
3. `python scripts/dev.py check` verde. La guardia `owners` va a marcar archivos de WS4/WS5: es esperado en este
   PR puntual; lo revisan **WS5** (rutas y `App.tsx`), **WS4** (`/api/systems`) y quien coordina, y se mergea.
4. Desde ahí, WS7 trabaja en ramas `ws7/...` y solo en sus rutas; lo que necesite de `App.tsx`, `client.ts` o el
   backend se lo pide a WS5/WS4.

