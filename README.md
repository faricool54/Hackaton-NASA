# Errante · SPHEREx sky explorer

**NASA Space Apps Challenge 2026 — reto "Planet X and SPHEREx"** · nombre provisorio (WS6 decide el final)

Una herramienta web pública para **ver cómo cambia el cielo infrarrojo** con imágenes reales de **NASA SPHEREx**
y **encontrar lo que se mueve**: asteroides, objetos del cinturón de Kuiper, enanas marrones cercanas… y entender
cómo se buscaría un hipotético **Planeta X**. *Planeta* viene del griego *planḗtēs*: **errante**.

## La idea en dos capas

1. **Ver el cielo cambiar (lo que pide el reto).** Ingresás coordenadas (o elegís un objeto) y ves las imágenes
   SPHEREx de ese parche como un *flip-book*: lo que se mueve o cambia de brillo salta a la vista.
2. **Entrar al objeto en 3D (nuestro diferencial).** Cada objeto que seguimos tiene un **modelo 3D** construido con
   sus datos de catálogo: el cuerpo (tamaño, color por temperatura, tipo), su **sistema animado** (órbitas,
   compañeras, pulsaciones) para ver cómo evoluciona, y la posibilidad de **entrar a cada planeta o estrella** con
   su ficha de información. Diseño cuidado y siempre etiquetado como *modelo, no imagen*.
   → [docs/VISION_3D.md](docs/VISION_3D.md) · ya navegable en `#/systems`.

> Estado: **esqueleto funcional**. La web ya corre de punta a punta con **datos sintéticos** (etiquetados como tales).
> El trabajo del equipo es reemplazar cada stub por la versión real. Ver [`tasks/`](tasks/).

## Empezar (5 minutos)

```bash
git clone https://github.com/faricool54/Hackaton-NASA && cd Hackaton-NASA
make setup        # Python venv + pipeline + backend + frontend
make web          # http://localhost:5173  (datos demo, sin backend)
```

Opcional: `make api` (backend en http://localhost:8000/docs) y abrir la web con `?mode=api`.
Vista previa remota (sesión en la nube, Codespaces, celular en la misma red): `VITE_ALLOW_ALL_HOSTS=1 make web`
(Vite bloquea por defecto cualquier host que no sea `localhost`).

<details><summary>Sin <code>make</code> (Windows)</summary>

```powershell
py -m venv .venv
.venv\Scripts\pip install -e "pipeline[dev]" -e "backend[dev]"
cd frontend; npm ci; npm run dev
# backend: cd backend; ..\.venv\Scripts\uvicorn errante_api.main:app --reload
# tests:   .venv\Scripts\pytest -q pipeline/tests backend/tests
```
</details>

## Cómo se reparte el trabajo

| WS | Tema | Carpeta | Tareas |
|---|---|---|---|
| WS1 | Acceso a datos SPHEREx (IRSA TAP/SIA, S3, cutouts) | `pipeline/errante/data/` | [tasks/WS1-data-access.md](tasks/WS1-data-access.md) |
| WS2 | Imágenes y detección de objetos en movimiento | `pipeline/errante/imaging/`, `detect/` | [tasks/WS2-imaging-detection.md](tasks/WS2-imaging-detection.md) |
| WS3 | Ciencia: objetos conocidos, distancia, espectros, Planeta X | `pipeline/errante/science/` | [tasks/WS3-science.md](tasks/WS3-science.md) |
| WS4 | Backend API | `backend/` | [tasks/WS4-backend.md](tasks/WS4-backend.md) |
| WS5 | Frontend (blink comparator, mapa, reportes) | `frontend/` | [tasks/WS5-frontend.md](tasks/WS5-frontend.md) |
| WS6 | Producto, narrativa, deploy y entrega | `docs/submission/` | [tasks/WS6-product-submission.md](tasks/WS6-product-submission.md) |
| WS7 | **Sistemas 3D**: modelos de los objetos, órbitas animadas, fichas | `pipeline/errante/systems/`, `frontend/src/three/` | [tasks/WS7-3d-systems.md](tasks/WS7-3d-systems.md) |

Con 5 personas: WS6 se reparte entre WS4 y WS5 y WS7 lo toma quien tenga más perfil 3D/diseño (ver
[docs/TEAM.md](docs/TEAM.md)).
Cada persona trabaja con su agente (Claude Code / Codex) usando el prompt que está al final de su archivo de tareas.

## Documentación

- [docs/CHALLENGE.md](docs/CHALLENGE.md) — el reto, cómo lo interpretamos, criterios de evaluación
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — arquitectura y flujo de datos
- [docs/CONTRACT.md](docs/CONTRACT.md) — formato de datos/API entre pipeline, backend y frontend
- [docs/VISION_3D.md](docs/VISION_3D.md) — la capa 3D: objetos, sistemas animados, fichas; reglas de honestidad
- [docs/RECON_SPHEREX.md](docs/RECON_SPHEREX.md) — **relevamiento técnico** (endpoints probados, CORS, colecciones DR1/QR3, LVF, objetos de prueba con coordenadas propagadas, arquitecturas)
- [docs/DATA.md](docs/DATA.md) — **hechos verificados** sobre los datos SPHEREx (S3, FITS, flags, IRSA)
- [docs/SCIENCE.md](docs/SCIENCE.md) — física necesaria: velocidades, paralaje, límites, encuadre honesto
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — git, PRs, cómo usar los agentes, cronograma del hackatón
- [AGENTS.md](AGENTS.md) — reglas para agentes y humanos

## Estructura

```
pipeline/   paquete Python `errante` (datos → imágenes → detección → ciencia → productos JSON/PNG) + CLI
            `errante/systems/`: modelos 3D de sistemas (WS7)
backend/    FastAPI `errante_api`: sirve productos + endpoints en vivo (IRSA, JPL)
frontend/   Vite + React + TypeScript: home, blink viewer, candidatos, espectro, about, sistemas 3D (three.js)
shared/     JSON Schema generado del contrato (no editar a mano: `make schema`)
data/demo/  datos SINTÉTICOS de ejemplo + sistemas 3D (commiteados)   data/products/: productos reales   data/cache/: descargas (ignorado)
docs/ tasks/ notebooks/
```

## Créditos de datos

SPHEREx: NASA / JPL-Caltech / IPAC, vía NASA/IPAC Infrared Science Archive (IRSA). Efemérides: JPL Solar System
Dynamics, IMCCE SkyBoT.
