# Kickoff (sáb 14/11, 12:00–12:30, hora local UTC−3)

> Esta agenda la preparó un asistente de IA (Claude). **A propósito no trae ideas de producto**: la regla de SI
> de Space Apps dice que la IA no se usa para idear cómo resolver el reto. La idea, el nombre y las decisiones
> de abajo las toman y las escriben ustedes. Insumo técnico: [`PLAN.md`](PLAN.md) y
> [`REVIEW-2026-11-14.md`](REVIEW-2026-11-14.md).

**Antes de entrar (5 min, cada uno):** leer en [`CHALLENGE.md`](CHALLENGE.md) el texto oficial (§1, sobre todo
*Objectives*) y las reglas de entrega (§3), y `PLAN.md` §1 y §4.

## Agenda (30 min)

| Minuto | Tema | Salida |
|---|---|---|
| 00–03 | El enunciado en voz alta (*Objectives* de `CHALLENGE.md` §1) y el reloj: cierre dom 15/11 23:59 hora del Local Event, quedan ~36 h | todos con el mismo objetivo |
| 03–10 | **Idea y nombre, con sus palabras**: qué problema resolvemos, para quién, cómo se llama. Escribirlo acá mismo | decisiones 1 y 2 |
| 10–14 | `PLAN.md`: aceptar o modificar el alcance (P0 / P1 / DROP) y el cronograma | decisión 3 |
| 14–19 | Asignar workstreams y roles en [`TEAM.md`](TEAM.md) | decisiones 4 y 5 |
| 19–23 | Reglas de juego ([`WORKFLOW.md`](WORKFLOW.md), [`COLLABORATION.md`](COLLABORATION.md)): `main` + PR + squash, `git pull origin main` sin force, `python scripts/dev.py check` antes de push, un PR por tarea, reglas de SI (trailer `Co-Authored-By:`, sin branding NASA, marca de agua en imágenes/videos con IA), honestidad (los objetivos se mueven 1–2 px) | — |
| 23–27 | Logística: Local Lead, repo público o URL del sitio, quién carga el formulario, canal del equipo, horarios de los syncs de 10 min (cada ~4 h) | decisiones 6 a 9 |
| 27–30 | Ronda: cada persona dice su primer PR chico y a qué hora lo abre | lista en el chat |

## Decisiones que tienen que tomar las personas

1. **La idea**, escrita por el equipo con sus palabras (regla de SI). El enunciado fija el "qué" (RA/Dec → serie
   de imágenes SPHEREx como video, probado en 5 objetivos); el enfoque y la interpretación son de ustedes.
2. **El nombre** (y tagline si quieren), también con sus palabras. `errante` queda solo como nombre técnico del
   paquete Python, salvo que decidan otra cosa.
3. **Aceptar o modificar `PLAN.md`**: alcance P0/P1/DROP y cronograma. Lo que cambie se anota en `PLAN.md`.
4. **Asignar workstreams** (logins en `TEAM.md`). No lo decide ningún agente.
5. **Dueño del deploy.** `PLAN.md` y `tasks/WS4` lo ponen en WS4; la versión anterior de `AGENTS.md` decía WS6.
6. **Zona horaria y juzgamiento local** con el/la Local Lead: si el cierre es 23:59 UTC−3 y si hay presentación
   o juzgamiento local antes. Si cambia, se corre el cronograma.
7. **Repo público o URL del sitio.** Los links de la entrega tienen que abrirse sin login. Hoy el repo es privado;
   no hay secretos trackeados y falta `LICENSE`. Opciones: hacerlo público antes de entregar, o usar la URL del
   sitio desplegado como "Final Project".
8. **Quién carga el formulario** (sugerido: quien coordina) y a qué hora (Submit for Judging dom 20:00).
9. **Idioma del video**: si hablan en español, los subtítulos en inglés son obligatorios.
10. **WS7 "Sistemas 3D"** (rama `claude/ecstatic-turing-rcu8jq`, ya pusheada, sin PR): ¿entra?, ¿con qué
    prioridad frente al P0?, ¿quién la sigue? Datos para decidir en [`PLAN.md`](PLAN.md) §6; cómo integrarla sin
    pisar a nadie en [`COLLABORATION.md`](COLLABORATION.md) §7.

### Registro de decisiones

| # | Decisión | Qué decidimos | Responsable | Hora |
|---|---|---|---|---|
| 1 | Idea (con nuestras palabras) | | | |
| 2 | Nombre / tagline | | | |
| 3 | `PLAN.md` aceptado / cambios | | | |
| 4 | Asignación de WS | | | |
| 5 | Dueño del deploy | | | |
| 6 | Zona horaria y juzgamiento local | | | |
| 7 | Repo público o URL del sitio | | | |
| 8 | Quién carga el formulario | | | |
| 9 | Idioma del video | | | |
| 10 | WS7 (3D): entra / prioridad / responsable | | | |
| | | | | |

## Primera hora de cada persona (12:30–13:30)

1. **Repo:** `git clone https://github.com/faricool54/Hackaton-NASA` (privado: tenés que ser colaborador) o
   `git fetch origin` si ya lo tenés. Cuando exista `main`: `git switch main`.
   Lo preparado antes del kickoff (`scripts/dev.py`, `scripts/owners.py`, `.gitattributes`, CI y estos docs)
   tiene que estar commiteado en `main` antes de que nadie abra ramas (objetivo: 13:00, lo verifica WS4).
2. **Entorno** (Windows: `py` en vez de `python`; en PowerShell 5.1, de a un comando):
   ```bash
   python scripts/dev.py setup
   python scripts/dev.py doctor
   python scripts/dev.py web        # http://localhost:5173 → demo con el badge SYNTHETIC DATA
   ```
   WS1, WS2 y WS3 además: `python scripts/dev.py setup-science`.
3. **Tu Claude en tu worktree / rama** (si vas a tener un solo agente, alcanza con
   `git switch -c wsN/primer-pr origin/main` en tu checkout):
   ```bash
   git worktree add -b wsN/primer-pr ../hn-wsN-primer-pr origin/main
   cd ../hn-wsN-primer-pr
   python scripts/dev.py setup
   ```
4. **Pegale el prompt** que está al final de tu `tasks/WSx-*.md` (y pedile que lea `docs/PLAN.md` primero), más
   el mensaje fijo de reglas de git de [`COLLABORATION.md`](COLLABORATION.md) §3. Reservá la tarea (issue
   asignado o aviso en el chat) antes de arrancar.
5. **Primer PR chico** (≤ 1 h), sacado de los P0 de `PLAN.md` §4:

   | WS | Primer PR sugerido |
   |---|---|
   | WS1 | Colecciones configurables (`ERRANTE_COLLECTIONS` en `settings.py`) + `search_frames` por SIA2 en VOTable, con un test sobre una respuesta guardada (sin red) |
   | WS2 | Hacer opcionales la detección y los objetos conocidos en `build.py` (hoy no escribe nada mientras sean stubs) |
   | WS3 | Abrir el PR de contrato 0.3.0 (tabla de [`CONTRACT.md`](CONTRACT.md)); los 5 objetivos ya están en `fields.toml`, con pm/plx en comentarios hasta que exista `Field.target` |
   | WS4 | Crear y proteger `main` con lo preparado hoy ya commiteado (lo que falte, en un PR `chore:`); después, el esqueleto de `/api/view` con funciones mockeadas en los tests |
   | WS5 | Caja RA/Dec + estado en la URL sobre `data/demo` (`?mode=` queda para Blink/Diferencia; la fuente de datos de `client.ts` pasa a `?source=`) |

6. `python scripts/dev.py check` → push → PR a `main` con título `wsN: ...` (ver [`WORKFLOW.md`](WORKFLOW.md)).

## Qué ya está hecho

- **Esqueleto funcional**: pipeline (`errante` CLI con `demo`, `schema`, `validate`; `search` y `build` con stubs),
  backend FastAPI con los endpoints de productos y tests, y frontend con el blink corriendo sobre datos
  **sintéticos** etiquetados como tales.
- **Contrato 0.1.0** (pydantic → JSON Schema → TypeScript), coherente entre las tres copias ✅.
- **CI verde** en GitHub: jobs `python` y `frontend` ✅ (2026-11-14).
- **Runner multiplataforma** `scripts/dev.py` (Windows/macOS/Linux, solo stdlib; el Makefile es un wrapper),
  guardia de ownership `scripts/owners.py`, CI con `concurrency` y `.gitattributes` (LF en todos los OS): listos
  en la copia local, falta que lleguen a `main`.
- **Revisión verificada en vivo** ([`REVIEW-2026-11-14.md`](REVIEW-2026-11-14.md)): IRSA sin CORS, S3 con CORS y
  Range, SIA más rápido que TAP, cutouts IBE caros, temporadas de cada objetivo, movimiento de 1–2 px, CDS
  Estrasburgo caído.
- **Texto oficial del reto** y reglas de entrega en [`CHALLENGE.md`](CHALLENGE.md), **plan técnico** en
  [`PLAN.md`](PLAN.md), y `DATA.md` corregido con lo verificado hoy.
- **Los 5 objetivos oficiales** en `pipeline/errante/config/fields.toml`, centrados en la época media de sus datos.

Lo de esta revisión está en la copia local de quien preparó el repo: tiene que llegar a `main` antes de abrir ramas.
Lo que **no** está (para no confundir): la rama `main`, `/api/view`, el contrato 0.3.0, golden fields reales y el
deploy.
