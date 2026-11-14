# Equipo y asignaciones

Se completa en el [kickoff](KICKOFF.md). Una persona por fila, cada una con su(s) agente(s).
Qué rutas tiene cada WS: tabla de ownership en [`AGENTS.md`](../AGENTS.md) (única fuente).
Prioridades de cada WS: [`PLAN.md`](PLAN.md) §4.

## Asignación (equipo de 5)

| WS | Tema | Persona (login GitHub) | Agente(s) | Perfil ideal | P0 en una línea |
|---|---|---|---|---|---|
| WS1 | Datos | | | Python, APIs, paciencia con servicios lentos | `search_frames` (SIA) + `read_patch` (Range S3) + índice SIA de los 5 objetivos |
| WS2 | Imagen | | | Python + numpy, procesamiento de imágenes | reproyección → coadd por temporada × detector → diferencia → PNG; `build_patch` |
| WS3 | Ciencia/objetivos **+ contrato** | | | el/la más "astro" del grupo | PR de contrato 0.3.0 (temprano) + los 5 objetivos con pm/plx/época + variables |
| WS4 | Backend + deploy **+ coordinación** | | | backend, devops | cuidar `main` (ya creada y protegida); `/api/view` con caché y errores JSON; deploy público temprano |
| WS5 | Frontend | | | React/TS, ojo para UX | caja RA/Dec + 5 objetivos + estado en la URL; zoom, retícula, Blink/Diferencia |
| WS6 | Entrega (repartido) | — | | comunicación, video | textos y video: WS3 + WS5 al final; formulario: quien coordina |

Logins disponibles en el repo: `BenjaminPondal`, `DankoLiv`, `faricool54`, `rpccp`, `V0id47`.

## Roles (completar en el kickoff)

| Rol | Persona (login GitHub) | Sugerido en `PLAN.md` |
|---|---|---|
| Coordinación de `main` (crea `main`, mergea, cuida el cronograma) | | WS4 |
| Dueño del PR de contrato 0.3.0 | | WS3 |
| Dueño del deploy (frontend + backend) | | WS4 |
| Quien carga el formulario de Space Apps | | quien coordina |
| Contacto con el/la Local Lead (zona horaria, juzgamiento local) | | |
| Canal del equipo (chat) | | |

## Variantes

**4 personas** (una sola coordina `main` y el contrato):

| Persona | Workstreams |
|---|---|
| A | WS1 + WS4 (datos, API, deploy) |
| B | WS2 |
| C | WS5 |
| D | WS3 + WS6 (objetivos, contrato, textos, video y formulario) |

**6 personas:** un dueño por WS, WS6 incluido (video ≤ 30 s, deck ≤ 7 slides, `PROJECT.md`, `CHECKLIST`,
formulario, prueba con 3 personas ajenas). Igual que con 5: una sola persona coordina `main` (sugerido WS4)
y una sola es dueña del contrato (sugerido WS3).

## Dependencias entre WS (quién espera a quién)

- **WS1 + WS2 → `/api/view` (WS4 lo expone).** WS1 entrega `search_frames` y `read_patch`; WS2, la reproyección,
  el coadd, la diferencia y `build_patch`. Mientras tanto WS2 trabaja con recortes reales bajados a mano por
  Range desde S3 y con `data/demo`; WS4 arma `/api/view` con esas funciones mockeadas en los tests.
- **WS3 primero el contrato** (PR 0.3.0 antes de las 15:00 del sábado): todos trabajan contra 0.1.0 + `data/demo`
  hasta que se mergee. WS3 también mantiene los 5 objetivos de `fields.toml` (ya están, centrados en la época de
  los datos; pm/plx/época pasan de comentarios a datos con `Field.target`), que necesitan WS2 (golden fields),
  WS5 (atajos) y la posición predicha.
- **WS5 arranca ya** sobre `data/demo`: caja RA/Dec, 5 atajos, estado en la URL, zoom, retícula, Blink/Diferencia.
  Se conecta a `/api/view` en I1 (sáb 20:00).
- **WS4 hace el deploy temprano** con los campos demo (frontend estático + backend), para encontrar los problemas
  del host antes del domingo; después cambia a datos reales.
- **WS6** necesita la idea y el nombre del kickoff, capturas reales (I2, dom 08:00) y la URL pública
  (dom 12:00).
