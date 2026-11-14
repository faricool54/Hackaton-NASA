# AGENTS.md — reglas para agentes (Codex, Claude Code y humanos)

> Codex lee este archivo automáticamente. Claude Code lo lee vía `CLAUDE.md`.
> Si sos un agente: leé esto completo + el archivo `tasks/WSx-*.md` de tu workstream ANTES de tocar código.

## Qué estamos construyendo

**Errante** (nombre provisorio) — NASA Space Apps Challenge 2026, reto **"Planet X and SPHEREx"**.
Una herramienta web pública que muestra imágenes infrarrojas reales de **NASA SPHEREx** tomadas en distintos
momentos para que cualquiera vea **cómo cambia el cielo** y encuentre **objetos que se mueven** (asteroides,
objetos transneptunianos, enanas marrones cercanas), con el hipotético **Planeta X** como motivación científica.

Contexto obligatorio: `docs/CHALLENGE.md` (el reto), `docs/ARCHITECTURE.md` (cómo encaja todo),
`docs/CONTRACT.md` (formato de datos), `docs/DATA.md` (hechos verificados sobre los datos SPHEREx).

## Mapa del repo y dueños

| Ruta | Qué es | Dueño |
|---|---|---|
| `pipeline/errante/data/` | búsqueda en IRSA (TAP/SIA), S3, cutouts, caché, lectura FITS | **WS1** |
| `pipeline/errante/imaging/`, `pipeline/errante/detect/` | grilla común, flags, reproyección, PNG, detección, linking, scoring, inyección | **WS2** |
| `pipeline/errante/science/`, `pipeline/errante/config/fields.toml` | objetos conocidos (JPL/SkyBoT), movimiento/distancia, espectros, Planeta X | **WS3** |
| `backend/` | API FastAPI | **WS4** |
| `frontend/` | web (Vite + React + TS) | **WS5** |
| `docs/submission/`, `frontend/src/pages/AboutPage.tsx` (textos), deploy | pitch, video, envío, deploy | **WS6** |
| `pipeline/errante/models.py`, `products.py`, `shared/schema/`, `frontend/src/api/types.ts` | **CONTRATO** | todos — solo vía PR `contract:` |
| `pipeline/errante/build.py`, `cli.py`, `synthetic.py` | integración | WS1 + WS2 (coordinar) |
| `AGENTS.md`, `CLAUDE.md`, `docs/*.md`, `tasks/*.md`, CI, Makefile | coordinación | coordinador/a (ver `docs/TEAM.md`) |

## Reglas de oro

1. **Quedate en tu carpeta.** Solo editá archivos de tu workstream. Si necesitás algo de otra carpeta, dejá un
   `TODO(WSx): ...` o pedilo en el chat del equipo / issue. Nada de "arreglos de paso" en carpetas ajenas.
2. **El contrato es sagrado.** `models.py` es la fuente de verdad. Cambiarlo = PR con título `contract: ...`,
   `make schema`, actualizar `frontend/src/api/types.ts` en el mismo PR, subir `SCHEMA_VERSION`, avisar a WS4+WS5.
   Preferí **agregar campos opcionales** antes que renombrar o borrar.
3. **Nunca hagas pasar datos falsos por reales.** Todo lo sintético lleva `synthetic: true` y la UI muestra el
   badge "SYNTHETIC DATA". Objetos inyectados → `status: "injected"`. Nada de imágenes de otras misiones
   presentadas como SPHEREx.
4. **Honestidad científica.** No afirmamos haber descubierto el Planeta X ni "objetos nuevos". Un candidato sin
   match en catálogos es `unconfirmed` y se explica qué puede ser (artefacto, error, objeto no catalogado).
   Ver `docs/SCIENCE.md`.
5. **No inventes datos de servicios externos.** Nombres de tablas, endpoints, coordenadas, bits de flags:
   verificalos contra la fuente (o contra un archivo real) y anotá el hallazgo en `docs/DATA.md`. Si no pudiste
   verificar, escribilo explícitamente.
6. **`make check` antes de cada push.** Lint + tests + schema + build del frontend. CI corre lo mismo.
7. **PRs chicos y frecuentes** a `main` (cada 1–3 h). Rama `wsN/descripcion-corta`. Ver `docs/WORKFLOW.md`.
8. **Nada pesado al repo.** FITS y descargas van a `data/cache/` (ignorado). Productos reales: solo campos
   curados y livianos (< ~20 MB en total).
9. **Sin secretos.** Ninguna API de las que usamos requiere clave. Si algo la pide, consultá antes.
10. **Las funciones stub se implementan respetando su firma.** Si la firma no alcanza, cambiala en tu propio
    módulo y actualizá a quien la llama (o coordiná si es de otro WS).

## Convenciones

- Código, identificadores, comentarios y textos de la UI: **inglés** (la entrega es internacional).
  Docs del equipo y tareas: **español**.
- Python ≥ 3.11, `ruff` (config en `ruff.toml`), tests con `pytest`. Librerías pesadas (scipy, photutils,
  reproject, astroquery, pyvo) se importan **dentro de las funciones** (extra `science`), así el resto no las necesita.
- Tests que usan internet: `@pytest.mark.network` (se saltean salvo `ERRANTE_NETWORK_TESTS=1`).
- TypeScript estricto, React con componentes funcionales, sin librerías nuevas salvo que aporten mucho
  (justificalo en el PR).
- Coordenadas: ICRS en grados. Tiempos: MJD (`MJD-OBS`). Píxeles en el contrato: **convención PNG**
  (origen arriba-izquierda, y hacia abajo, norte arriba, este a la izquierda).
- Commits: `wsN: verbo + qué` (ej. `ws1: implement TAP search with disk cache`).

## Comandos

```bash
make setup          # venv + paquetes Python + npm ci
make setup-science  # libs científicas pesadas (WS1/WS2/WS3)
make demo           # regenera datos sintéticos en data/demo
make api            # backend en :8000 (docs en /docs)
make web            # frontend en :5173 (lee data/demo por defecto)
make check          # lo mismo que CI: correr antes de push
errante --help      # CLI del pipeline: demo | schema | validate | search | build
```

## Cuando termines una tarea

1. Marcá la casilla en `tasks/WSx-*.md` (solo tu archivo).
2. Si aprendiste algo sobre los datos/servicios, agregalo a `docs/DATA.md` con fecha y cómo lo verificaste.
3. PR a `main` con la plantilla. Mencioná qué probaste.
