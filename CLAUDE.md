@AGENTS.md

## Notas para Claude Code

- **Antes de empezar:** leé `docs/PLAN.md` (prioridades vigentes) y el `tasks/WSx-*.md` de tu workstream (te lo
  indica la persona que te usa). Si vas a tocar datos o la API, también `docs/CONTRACT.md`. Trabajá solo en las
  rutas que la tabla de ownership de `AGENTS.md` le da a tu WS.
- **Verificación final:** `python scripts/dev.py check` (Windows: `py scripts/dev.py check`). No digas que algo
  está listo sin verlo en verde.
- **Frontend:** además mirá la página (`python scripts/dev.py web` → http://localhost:5173), en desktop y en
  ancho de celular, antes de decir que funciona.
- **Windows:** usá `py` (no `python3`: puede resolver al Python de MSYS2) y las herramientas de `.venv\Scripts\`
  (no `.venv/bin`). PowerShell 5.1 no tiene `&&`: corré los comandos por separado.
- **Servicios externos:** si IRSA, S3, CfA, JPL o SkyBoT no responden desde tu entorno, no inventes la respuesta:
  dejá el código con un test `@pytest.mark.network` y explicá qué falta verificar. CDS Estrasburgo está caído:
  usá los espejos de `AGENTS.md` (regla 6).
- **Varios agentes en la misma máquina:** cada uno en su worktree y con su propio entorno:
  ```bash
  git fetch origin
  git worktree add -b wsN/x ../hn-wsN-x origin/main
  cd ../hn-wsN-x
  python scripts/dev.py setup        # su propio .venv: el de otro checkout importa el código equivocado
  ```
  Si dos agentes levantan el backend, el segundo usa otro puerto: `API_PORT=8001 python scripts/dev.py api`.
- **Commits y PRs:** una tarea por sesión y por PR. Commit `wsN: verbo + qué` con el trailer `Co-Authored-By:`.
  Mostrale el diff a la persona antes de commitear y no cambies el contrato ni carpetas ajenas sin que lo pida.
  Reglas de git para agentes: `docs/COLLABORATION.md` §3 (stageá por nombre, nunca `git add -A`,
  `push --force`, `reset --hard` ni cambiar de rama; actualizá con `git pull origin main`).
