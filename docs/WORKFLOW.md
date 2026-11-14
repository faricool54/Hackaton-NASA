# Cómo trabajamos (git, agentes, cronograma)

## Git

- `main` siempre verde (CI pasa) y desplegable. **Nadie pushea directo a `main`**: todo por PR.
- Ramas: `ws1/tap-search`, `ws5/aladin-map`, `contract/add-difference-image`. Cortas (1–3 h de trabajo).
- Antes de abrir PR: `git pull --rebase origin main` y `make check`.
- PR chico, con la plantilla. Lo revisa **otra persona** (o su agente) en ≤ 15 min; si es solo de tu carpeta y
  CI está verde, se puede mergear con 1 aprobación. Squash merge.
- Conflictos: casi no debería haber, porque cada WS tiene su carpeta. Los archivos compartidos
  (`models.py`, `types.ts`, `build.py`, `Makefile`, docs de coordinación) se tocan solo con aviso en el chat.
- `data/demo/` se regenera con `make demo`; si dos PRs lo tocan, regenerarlo después de rebasear en vez de
  resolver el conflicto a mano.

## Trabajar con agentes (Claude Code / Codex)

1. Abrí tu agente en la raíz del repo. Ambos cargan `AGENTS.md` (Claude vía `CLAUDE.md`).
2. Pegale el **prompt de arranque** que está al final de tu `tasks/WSx-*.md` (o escribí "trabajá en la tarea
   WSx-N de tasks/WSx-....md").
3. **Una tarea por sesión/PR.** Pedile que: lea el archivo de tareas, implemente, agregue tests, corra
   `make check`, y te muestre el diff antes de commitear.
4. **Vos revisás.** El agente no decide cambios de contrato ni toca carpetas ajenas: si lo propone, frenalo y
   coordiná con el equipo.
5. Si el agente no puede acceder a un servicio (IRSA, JPL), que **no invente** respuestas: dejá un test
   `@pytest.mark.network` y corrélo vos desde tu máquina.
6. Para trabajos en paralelo con varios agentes en tu propia máquina usá `git worktree`
   (`git worktree add ../hn-ws2b ws2/linking`) para que no se pisen.

## Cronograma sugerido (~48 h; ajustar al deadline oficial de su sede)

| Hora | Hito | Qué debería estar |
|---|---|---|
| H+0 | Kickoff (30 min) | Leer CHALLENGE + ARCHITECTURE; asignar WS en `docs/TEAM.md`; todos corren `make setup && make web` |
| H+2 | Primeros PRs | WS1: búsqueda TAP real devuelve frames de un campo · WS5: UI pulida sobre demo · WS3: lista de campos validada |
| H+6 | **I1** | Un campo real con frames SPHEREx reales en el blink (WS1 + WS2 reproject/render) |
| H+12 | **I2** | Detección y linking de asteroides en el campo real + cruce con JPL/SkyBoT |
| H+20 | Feature freeze de ciencia | 3–5 campos curados construidos; límites por inyección medidos |
| H+24 | Deploy público v1 | URL pública funcionando (WS6) |
| H+30 | Polish | UX, textos, accesibilidad, página About/Limits, video grabado |
| H+36 | **Freeze total** | Solo bugs. Ensayo del pitch |
| H+40 | Entrega | Formulario Space Apps completo (WS6), con margen ante problemas |

Sync rápido (10 min) cada ~4–6 h: qué hice, qué sigue, qué me bloquea. Actualizar casillas en `tasks/`.

## Definición de "terminado"

- Código + tests (o justificación de por qué no) + `make check` verde.
- Si toca la UI: probado en el navegador, desktop y celular.
- Si aprendiste algo de los datos: anotado en `docs/DATA.md`.
- Nada sintético presentado como real; nada que diga "descubrimos".
