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

## Sede y cronograma de entrega (S01/S05)

Fuente: `docs/SUBMISSION_GUIDE.md`, PDF págs. 2/12. Sede confirmada por usuario: **Universidad de Palermo,
Buenos Aires, Argentina**, zona **America/Argentina/Buenos_Aires, ART (UTC-3)**.
Abre **14/11/2026 09:00 ART**; cierra **15/11/2026 23:59 ART** (**16/11 02:59 UTC**).
Ventana: **38 h 59 min**. El cronograma anterior de 48 h/H+40 excedía el cierre y queda reemplazado.
La evaluación/premiación local puede tener otro horario: consultarlo con Local Lead.

H+0 corresponde a la apertura; horas orientativas para organizar trabajo, con envío interno a las 21:00.

| Hora | Hito | Qué debería estar |
|---|---|---|
| H+0 | Kickoff (30 min) | Leer CHALLENGE + REQUIREMENTS + VALIDATION + ARCHITECTURE; asignar WS; correr demo |
| H+2 | Primeros PRs / inscripción | Consulta/render/identidades/jobs; WS6 verifica 1–6 integrantes UP, Team Owner y Members aceptados, sin waitlist |
| H+6 | **I1 (P0)** | Campo SPHEREx real en el blink sin análisis automático |
| H+12 | **I2 (P0)** | Entrada RA/Dec → construcción/caché → secuencia; preparar deploy público de UI y servicio |
| H+20 | **I3 (P0)** | Cinco ensayos documentados, incluidos RW Aurigae/R Draconis; resultados y límites honestos |
| H+24 (dom. 09:00 ART) | Deploy público verificable | Probar URL en incógnito/celular con coordenadas no precargadas |
| H+28 (dom. 13:00 ART) | **I4 (P1), según tiempo** | Congelar extras; C01–C08 explícitos; revisar brechas de los cinco criterios en JUDGING_REVIEW.md |
| H+30 (dom. 15:00 ART) | Demo y formulario | Video <= 30 s o <= 7 slides, inglés; fuentes, declaración SI y URLs comprobadas |
| H+32 (dom. 17:00 ART) | **Freeze total** | Solo bugs; ensayo, S01–S10 y revisión de evidencia/relato en formulario y demo |
| H+36 (dom. 21:00 ART) | **Envío interno objetivo** | Submit for Judging + banner/mensaje; guardar evidencia y verificar última versión |
| H+38:59 (dom. 23:59 ART) | **Cierre según guía** | No usar como hora objetivo; cualquier reenvío debe estar confirmado antes |

**I5 (P2)** — detección automática, JPL, distancias, inyección y Planeta X — solo después de estabilizar
el recorrido obligatorio. Las horas intermedias son planificación interna; apertura/cierre provienen del PDF.

Sync rápido (10 min) cada ~4–6 h: qué hice, qué sigue, qué me bloquea. Actualizar casillas en `tasks/`.

## Definición de "terminado"

- Código + tests (o justificación de por qué no) + `make check` verde.
- Si toca la UI: probado en el navegador, desktop y celular.
- Si aprendiste algo de los datos: anotado en `docs/DATA.md`.
- Nada sintético presentado como real; nada que diga "descubrimos".
- Tarea vinculada a Rxx/Cxx; REQUIREMENTS refleja el estado real. R05 tiene cinco ensayos con evidencia;
  sin cobertura/señal se documenta como tal. Ninguna lista vacía sin análisis significa búsqueda negativa.
- Entrega vinculada a S01–S10: demo dentro del límite, inglés, URLs anónimas, inventario y declaración SI,
  formulario completo, envío confirmado. Coordinar una persona editora; el lock es solo una señal y puede quitarse.
- Guardar avances con frecuencia; **Save Progress no envía** a evaluación. Tras editar una entrega,
  reenviar y comprobar confirmación antes del cierre. El equipo revisa términos/originalidad antes de aceptarlos.
- Rúbrica revisada según JUDGING_GUIDE.md: cinco criterios 1–5, sin pesos/fórmula inventados. Datos NASA
  centrales y usabilidad tienen evidencia; la presentación no queda pospuesta por agregar extras.
- Inscripción final revisada antes del cierre: después no se pueden agregar integrantes. Nominación/premios
  son etapas posteriores de la organización; un premio local no garantiza Global Judging.
