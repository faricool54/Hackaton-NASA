# Cómo trabajamos (git, agentes, cronograma)

Prioridades vigentes: [`PLAN.md`](PLAN.md). Quién es dueño de qué: tabla de ownership en [`AGENTS.md`](../AGENTS.md).
Protocolo detallado para trabajar en paralelo (archivos calientes, reservas, mensaje fijo para tu agente):
[`COLLABORATION.md`](COLLABORATION.md).

## Git

✅ **`main` existe desde el 2026-11-14 (sáb 11:45)**: es la rama por defecto y está **protegida** — PR obligatorio,
checks `python` y `frontend` en verde, historia lineal, solo squash merge, sin force-push, borrado automático de
ramas al mergear (quien es admin puede saltearla en una emergencia). La rama vieja
`claude/affectionate-gauss-rsem1g` apunta al mismo commit inicial: **no se usa más** (se puede borrar cuando
nadie la tenga en uso). Lo preparado (runner, guardia, CI, docs) entró con el primer PR `chore:`.

Reglas:

- **Nadie pushea directo a `main`**: todo por PR. `main` siempre verde y desplegable. **Nunca `push --force`.**
- **Ramas:** `wsN/descripcion-corta` (ej. `ws1/sia-search`), `contract/...` para el contrato, `chore/...` para
  infraestructura. Las ramas `claude/*` que crea Claude Code web se aceptan, pero el **título del PR empieza con
  `wsN:`**. Ramas cortas: 1–3 h de trabajo. Reservá la tarea antes de empezar (issue asignado o aviso en el chat).
- **Commits:** `wsN: verbo + qué`. Los hechos con agentes llevan el trailer `Co-Authored-By:`.
- **Antes de cada push:** `git pull origin main` (merge, sin rebase ni force) y `python scripts/dev.py check`
  (incluye la guardia de ownership `python scripts/dev.py owners`).
- **PR:** chico, con la plantilla, una tarea por PR, siempre **squash**. WS4 es responsable de `main`: mergea los
  PRs `contract:` y `chore:` (con 1 OK de alguien afectado) y revierte si algo rompe `main`. Un PR que solo toca
  tu carpeta y tiene CI verde lo podés mergear vos (ver `COLLABORATION.md` §2). Al hacer squash, **no borres los
  trailers `Co-Authored-By:`** del mensaje.
- **Conflictos:** casi no debería haber, porque cada WS tiene sus rutas. Los archivos compartidos (`models.py`,
  `types.ts`, `build.py`, `scripts/dev.py`, `Makefile`, docs de coordinación) se tocan solo con aviso en el chat.
  Si el conflicto es en un archivo que no es tuyo, pará y avisá a su dueño.
- **`data/demo/`** se regenera solo en PRs de contrato (`python scripts/dev.py demo`). Si choca, no se resuelve a
  mano: se toma la versión de `main` y se regenera. `manifest.json` cambia `generated_at` en cada regeneración:
  es esperable.
- **`docs/DATA.md`** lo edita WS1. Los demás agregan al final, en "Notas de otros WS", o le pasan el hecho a WS1.
- **Finales de línea:** `.gitattributes` fuerza LF en todos los OS. Si ves un diff de archivo completo, avisá antes
  de commitearlo.

## Trabajar con agentes (Claude Code / Codex)

1. Abrí tu agente en la raíz de **tu** checkout (o worktree). Ambos cargan `AGENTS.md` (Claude vía `CLAUDE.md`).
2. Pegale el **prompt de arranque** que está al final de tu `tasks/WSx-*.md`, o pedile una tarea concreta:
   "leé `docs/PLAN.md` y `tasks/WSx-....md`, implementá WSx-N".
3. **Una tarea por sesión y por PR.** Pedile que lea las tareas, implemente, agregue tests, corra
   `python scripts/dev.py check` y te muestre el diff antes de commitear. Sumale el mensaje fijo de reglas de git
   de `COLLABORATION.md` §3 (nada de `git add -A`, `push --force` ni cambiar de rama).
4. **Vos revisás el diff.** El agente no decide cambios de contrato ni toca rutas ajenas: si lo propone,
   frenalo y coordiná con el equipo. Tampoco escribe la idea, el nombre ni los textos de producto (regla de SI).
5. Si el agente no puede acceder a un servicio (IRSA, S3, CfA), que **no invente** respuestas: dejá un test
   `@pytest.mark.network` y corrélo vos desde tu máquina.
6. **Varios agentes en la misma máquina:** un worktree por agente, con rama nueva (`-b`) y su propio entorno.
   Las instalaciones editables del `.venv` apuntan al checkout donde se crearon, así que compartir el `.venv`
   testea el código equivocado ✅.
   ```bash
   git fetch origin
   git worktree add -b wsN/x ../hn-wsN-x origin/main
   cd ../hn-wsN-x
   python scripts/dev.py setup
   ```
   Al terminar: `git worktree remove ../hn-wsN-x`.
7. **Puertos:** Vite toma el siguiente puerto libre si 5173 está ocupado. El backend usa 8000 por defecto; con
   dos backends en la misma máquina, el segundo usa `API_PORT` y su frontend apunta ahí con `VITE_API_BASE`:
   ```bash
   API_PORT=8001 python scripts/dev.py api
   VITE_API_BASE=http://localhost:8001 VITE_DATA_MODE=api python scripts/dev.py web
   ```
   En PowerShell: `$env:API_PORT="8001"; py scripts/dev.py api` (y lo mismo con `$env:VITE_API_BASE`).

## Cronograma (hora local UTC−3; **confirmar la zona del Local Event**)

Reemplaza al plan anterior de ~48 h. Fuente: [`PLAN.md`](PLAN.md) §5.

| Cuándo | Hito | Criterio / quién |
|---|---|---|
| Sáb 12:00–12:30 | **Kickoff** ([`KICKOFF.md`](KICKOFF.md)) | asignaciones en `TEAM.md`, idea/nombre por el equipo, alcance congelado |
| Sáb 13:00 | Entorno andando | todos con `python scripts/dev.py setup` y `python scripts/dev.py web` funcionando (en PowerShell 5.1, por separado) |
| Sáb 15:00 | Contrato y datos reales | contrato 0.3.0 mergeado (WS3) · `search_frames` real · lectura S3 de Barnard por CLI (WS1) |
| Sáb 20:00 | **I1 – vertical slice real** | `/api/view` de Barnard (1 detector, por temporada) se ve en el frontend (WS1+WS2+WS4+WS5) |
| Dom 08:00 | **I2** | los 5 objetivos con coadds + diferencia + posición predicha; golden fields construidos |
| Dom 12:00 | **Deploy público** | frontend + backend probados en incógnito y en celular (WS4) |
| Dom 17:00 | **Feature freeze** | solo bugs |
| Dom 17:00–19:30 | Entrega | video ≤ 30 s, deck ≤ 7 slides, formulario completo |
| Dom 20:00 | **Submit for Judging** | se puede reenviar hasta las 23:59 |

Sync de 10 min cada ~4 h: qué hice, qué sigue, qué me bloquea. Cualquier cambio de alcance se anota en `PLAN.md`.

## Definición de "terminado"

- Código + tests (o la justificación de por qué no) + `python scripts/dev.py check` verde + CI verde.
- Si toca la UI: probado en el navegador, desktop y celular.
- Si aprendiste algo de los datos: en `docs/DATA.md` (WS1) o en "Notas de otros WS", con fecha y estado
  (✅ / 📄 / ❓).
- Nada sintético presentado como real; nada que diga "descubrimos".
- Uso de IA declarado: commits hechos con agentes con trailer `Co-Authored-By:`; imágenes o videos generados con
  IA con marca de agua visible; nada de branding NASA.
- Casilla marcada en tu `tasks/WSx-*.md` con el link al PR.
