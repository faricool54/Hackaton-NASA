# AGENTS.md — reglas para agentes (Codex, Claude Code y humanos)

> Codex lee este archivo automáticamente. Claude Code lo lee vía `CLAUDE.md`.
> Si sos un agente: leé esto completo + el archivo `tasks/WSx-*.md` de tu workstream ANTES de tocar código.

## Qué estamos construyendo

**Errante** (nombre provisorio) — NASA Space Apps Challenge 2026, reto **"Planet X and SPHEREx"**.
Una herramienta web pública donde se ingresan **RA/Dec** y se reproduce una secuencia de imágenes reales
de **NASA SPHEREx** de la misma región en distintas fechas. Se valida con **Barnard's Star, Epsilon Indi B,
WISE 0855, RW Aurigae y R Draconis**, incluyendo movimiento y cambios de brillo.
La detección automática y el hipotético Planeta X son extensiones del equipo; no bloquean el visor.
WS7 agrega una galería **3D opcional (P2)**: modelos ilustrativos, no imágenes SPHEREx ni validaciones R05.
La versión importada tiene parámetros introducidos a mano, todavía sin verificar; ver `docs/VISION_3D.md`.

Contexto obligatorio: `docs/CHALLENGE.md` (el reto), `docs/ARCHITECTURE.md` (cómo encaja todo),
`docs/CONTRACT.md` (formato de datos), `docs/DATA.md` (hechos verificados sobre los datos SPHEREx).
Leer también `docs/REQUIREMENTS.md` (R01–R05 obligatorios, C01–C08 opcionales y responsables)
y `docs/VALIDATION.md` (protocolo para los cinco blancos).
Reglas de entrega obligatorias: `docs/SUBMISSION_GUIDE.md` (S01–S10), derivadas del PDF inalterado en
`docs/references/`. Uso conocido de IA y pendientes: `AI_USAGE.md` y `docs/submission/ai-usage.json`.
Leer `docs/JUDGING_GUIDE.md`: elegibilidad, criterios **1–5 cada uno**, fases y premios del segundo PDF.
Revisión interna con evidencia: `docs/submission/JUDGING_REVIEW.md`; no inventar pesos, totales o notas oficiales.

**Sede confirmada por el usuario:** Universidad de Palermo, Buenos Aires, Argentina. Cierre según guía:
**15/11/2026 23:59 ART (UTC-3)**; objetivo interno de envío confirmado: **21:00 ART**. No usar H+40:
la ventana del PDF es de 38 h 59 min. El horario de evaluación local se confirma aparte.

**Prioridades:** P0 = recorrido obligatorio y publicación; P1 = consideraciones opcionales del enunciado;
P2 = ampliaciones propias. No iniciar detección/Planeta X dejando bloqueado RA/Dec → imágenes → blink.

## Cómo trabajamos sin pisarnos (obligatorio)

Leé [`docs/COLLABORATION.md`](docs/COLLABORATION.md) antes de tocar nada. Resumen: una persona = un workstream =
sus carpetas; una rama `wsN/...` por tarea; un worktree por agente; nunca `git add -A` (stageá por nombre), nunca
`push --force` ni commits en `main`; `git pull origin main` (merge) antes de pushear; `python scripts/dev.py check`
(incluye la guardia de ownership `scripts/owners.py`) antes de cada push. La tabla detallada de dueños está en
`docs/COLLABORATION.md` §1 y la aplica `scripts/owners.py`.

Plan vigente de pendientes y dependencias: [`docs/PARALLEL_PLAN.md`](docs/PARALLEL_PLAN.md).
WS4 reservado por el usuario de esta sesión con Codex; otros responsables por confirmar en TEAM.md.

## Mapa del repo y dueños

| Ruta | Qué es | Dueño |
|---|---|---|
| `pipeline/errante/data/` | búsqueda en IRSA (TAP/SIA), S3, cutouts, caché, lectura FITS | **WS1** |
| `pipeline/errante/imaging/`, `pipeline/errante/detect/` | grilla común, flags, reproyección, PNG, detección, linking, scoring, inyección | **WS2** |
| `pipeline/errante/science/`, `pipeline/errante/config/fields.toml` | cinco blancos, astrometría/variabilidad, espectros, Gaia; JPL/Planeta X opcionales | **WS3** |
| `backend/` | API FastAPI | **WS4** |
| `frontend/` | web (Vite + React + TS) | **WS5** |
| `docs/submission/`, `frontend/src/pages/AboutPage.tsx` (textos), deploy | pitch, video, envío, deploy | **WS6** |
| `pipeline/errante/systems/`, `frontend/src/three/`, `frontend/src/components/{SystemViewer,BodyPanel}.tsx`, `frontend/src/pages/{SystemsPage,SystemPage}.tsx` | modelos 3D opcionales y procedencia | **WS7** |
| `pipeline/errante/models.py`, `products.py`, `shared/schema/`, `frontend/src/api/types.ts` | **CONTRATO** | todos — solo vía PR `contract:` |
| `pipeline/errante/build.py`, `cli.py`, `synthetic.py` | integración: imágenes primero, análisis opcional | WS1 + WS2 + WS4 (coordinar) |
| `AGENTS.md`, `CLAUDE.md`, `docs/*.md`, `tasks/*.md`, CI, Makefile | coordinación | coordinador/a (ver `docs/TEAM.md`) |

## Reglas de oro

1. **Quedate en tu carpeta.** Solo editá archivos de tu workstream. Si necesitás algo de otra carpeta, dejá un
   `TODO(WSx): ...` o pedilo en el chat del equipo / issue. Nada de "arreglos de paso" en carpetas ajenas.
2. **El contrato es sagrado.** `models.py` es la fuente de verdad. Cambiarlo = PR con título `contract: ...`,
   `python scripts/dev.py schema`, actualizar `frontend/src/api/types.ts` en el mismo PR, subir `SCHEMA_VERSION`, avisar a WS4+WS5.
   Preferí **agregar campos opcionales** antes que renombrar o borrar.
3. **Nunca hagas pasar datos falsos por reales.** Todo lo sintético lleva `synthetic: true` y la UI muestra el
   badge "SYNTHETIC DATA". Objetos inyectados → `status: "injected"`. Nada de imágenes de otras misiones
   presentadas como SPHEREx.
   Toda vista 3D muestra **3D MODEL · NOT AN IMAGE**, su `representation_note`, flags `Fact.verified`
   y límites de escala/fase/parámetros. Un modelo de un blanco no prueba que se haya observado con SPHEREx.
4. **Honestidad científica.** No afirmamos haber descubierto el Planeta X ni "objetos nuevos". Un candidato sin
   match en catálogos es `unconfirmed` y se explica qué puede ser (artefacto, error, objeto no catalogado).
   Ver `docs/SCIENCE.md`.
5. **No inventes datos de servicios externos.** Nombres de tablas, endpoints, coordenadas, bits de flags:
   verificalos contra la fuente (o contra un archivo real) y anotá el hallazgo en `docs/DATA.md`. Si no pudiste
   verificar, escribilo explícitamente.
6. **`python scripts/dev.py check` antes de cada push.** Lint + tests + schema + build del frontend. CI corre lo mismo.
7. **PRs chicos y frecuentes** a `main` (cada 1–3 h). Rama `wsN/descripcion-corta`. Ver `docs/WORKFLOW.md`.
8. **Nada pesado al repo.** FITS y descargas van a `data/cache/` (ignorado). Productos reales: solo campos
   curados y livianos (< ~20 MB en total).
9. **Sin secretos.** Ninguna API de las que usamos requiere clave. Si algo la pide, consultá antes.
10. **Las funciones stub se implementan respetando su firma.** Si la firma no alcanza, cambiala en tu propio
    módulo y actualizá a quien la llama (o coordiná si es de otro WS).
11. **Cada punto del enunciado tiene trazabilidad.** Citá Rxx/Cxx/Sxx al actualizar tareas. Una tarea asignada
    no está implementada; una prueba sin señal no es una recuperación exitosa. Guardá evidencia según VALIDATION.md.
12. **El campo visible no depende del análisis.** `errante build <id>` publica imágenes y metadatos;
    `--analyze` opta por detección/cruce. Las listas vacías con análisis no ejecutado no son resultados negativos.
13. **La entrega cumple la guía aportada.** Demo obligatoria: video <= 30 s o <= 7 diapositivas contando
    portada/introducción. Formulario/materiales enlazados en inglés; voz en otro idioma requiere subtítulos
    ingleses. Enlaces sin login. Save Progress no equivale a Submit for Judging y confirmación.
14. **Registrar el uso de SI/IA.** Actualizar atribución descriptiva y metadata para código/datos/audio
    generados con SI; imágenes/videos SI llevan marca visible. No incorporar/modificar elementos de marca
    NASA en contenido generado. Conservar origen de idea y revisión del equipo: la guía limita SI para
    formular la idea de solución. No afirmar que una auditoría/autoría está completa si sigue pendiente.
15. **Revisar medios y fuentes antes de enviar.** Inventario completo y permisos, al menos un dato/recurso
    NASA identificado para Global Award, integrantes confirmados y sin representaciones de menores de 18
    años en demo/proyecto final. Son condiciones del PDF, no prohibiciones de participación de menores.
16. **Elegibilidad y evaluación con evidencia.** Local Event admite 1–6 integrantes, Universal 2–6;
    todos aceptados en el mismo evento, incluido Team Owner, visibles en Members; no agregar personas tras
    el cierre. La organización decide elegibilidad y nominación. Un premio local no es nominación global.
    Impact/Creativity/Validity/Relevance/Presentation se evalúan por separado de 1 a 5. La confianza 0–1
    de candidatos no es esa rúbrica. Priorizar datos NASA reales, recorrido útil y presentación clara antes de extras.

## Convenciones

- Código, identificadores, comentarios y textos de la UI: **inglés** (la entrega es internacional).
  README público y materiales de entrega: **inglés**; docs internos del equipo y tareas: **español**.
  El README interno previo se conserva en `docs/README.es.md`.
- Python ≥ 3.11, `ruff` (config en `ruff.toml`), tests con `pytest`. Librerías pesadas (scipy, photutils,
  reproject, astroquery, pyvo) se importan **dentro de las funciones** (extra `science`), así el resto no las necesita.
- Tests que usan internet: `@pytest.mark.network` (se saltean salvo `ERRANTE_NETWORK_TESTS=1`).
- TypeScript estricto, React con componentes funcionales, sin librerías nuevas salvo que aporten mucho
  (justificalo en el PR).
- Coordenadas: ICRS en grados. Tiempos: MJD medio (`MJD-AVG`; fallback en `docs/DATA.md` §2;
  `MJD-OBS` es inicio). Píxeles en el contrato: **convención PNG**
  (origen arriba-izquierda, y hacia abajo, norte arriba, este a la izquierda).
- Commits: `wsN: verbo + qué` (ej. `ws1: implement TAP search with disk cache`).

## Comandos

```bash
python scripts/dev.py setup          # venv + paquetes Python + npm ci
python scripts/dev.py setup-science  # libs científicas pesadas (WS1/WS2/WS3)
python scripts/dev.py demo           # regenera datos sintéticos en data/demo
python scripts/dev.py api            # backend en :8000 (docs en /docs)
python scripts/dev.py web            # frontend en :5173 (lee data/demo por defecto)
python scripts/dev.py check          # lo mismo que CI: correr antes de push
errante --help      # CLI: demo | schema | validate | search | systems | build
```

## Cuando termines una tarea

1. Marcá la casilla en `tasks/WSx-*.md` (solo tu archivo).
2. Si aprendiste algo sobre los datos/servicios, agregalo a `docs/DATA.md` con fecha y cómo lo verificaste.
3. PR a `main` con la plantilla. Mencioná qué probaste.
