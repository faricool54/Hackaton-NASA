@AGENTS.md

## Notas para Claude Code

- Antes de empezar: leé tu archivo de workstream en `tasks/` y [`docs/COLLABORATION.md`](docs/COLLABORATION.md)
  (cómo trabajamos sin pisarnos). Trabajá **solo** en las rutas de tu workstream
  (`python scripts/owners.py --who <ruta>` te dice de quién es un archivo).
- Comandos (Windows, macOS y Linux; en Windows podés usar `py` en lugar de `python`):
  `python scripts/dev.py setup | web | api | check`. `check` = lo mismo que CI + la guardia de ownership.
  Corrélo antes de cada commit/push. `make check` sigue funcionando en macOS/Linux (llama al mismo script).
- Git (estricto, ver `docs/COLLABORATION.md` §3): una rama `wsN/...` por tarea; nunca commitees en `main`;
  nunca `git add -A` / `git add .` (stageá por nombre); nunca `push --force`, `reset --hard` ni cambiar de rama
  sin que te lo pidan; actualizá con `git pull origin main` (merge). Commits `wsN: ...` con trailer `Co-Authored-By:`.
- Si hay varios agentes en la misma máquina: cada uno en su worktree
  (`git worktree add -b wsN/x ../hn-wsN-x origin/main`, después `python scripts/dev.py setup` adentro) y con
  `API_PORT` distinto si levantan el backend.
- Para el frontend, además de `check`, mirá la página en el navegador antes de decir que algo funciona.
- Si un servicio externo (IRSA, JPL, SkyBoT, CDS) no responde, no inventes la respuesta: dejá el código con un
  test marcado `network` y explicá qué falta verificar. CDS Estrasburgo está degradado desde el 2026-11-09:
  usá espejos (VizieR/Sesame de CfA, HiPS de IRSA, Aladin Lite desde jsdelivr).
