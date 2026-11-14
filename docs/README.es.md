# Errante · SPHEREx sky explorer

**NASA Space Apps Challenge 2026 — reto "Planet X and SPHEREx"** · nombre provisorio (WS6 decide el final)

Una herramienta web pública para ingresar **ascensión recta y declinación (RA/Dec)** y reproducir imágenes
reales de **NASA SPHEREx** de la misma región en distintas fechas, reconociendo movimiento y cambios de brillo.
Validación exigida: **Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis**.
Detección automática y Planeta X son extensiones posteriores al explorador temporal.

> Estado: **esqueleto funcional**. La web ya corre de punta a punta con **datos sintéticos** (etiquetados como tales).
> El trabajo del equipo es reemplazar cada stub por la versión real. Ver [`tasks/`](../tasks/).
> Todavía faltan imágenes reales, ingreso público RA/Dec, construcción bajo demanda y los cinco ensayos.
> El build básico ya se separó del análisis opcional: `errante build <id>` / `errante build <id> --analyze`.

## Alcance y orden de implementación

1. **P0:** imágenes reales alineadas → RA/Dec → animación pública → cinco ensayos documentados.
2. **P1:** releases actualizables, bandas/coadds/espectros, sumas/restas, FOV, Gaia/WISE, URL/embebido,
   metadatos/flags y herramientas públicas. Son consideraciones opcionales del enunciado, todas planificadas.
3. **P2:** detección, catálogos de asteroides, distancia, límites de detección y Planeta X.

La [matriz de cobertura](../docs/REQUIREMENTS.md) asigna cada punto a tareas y criterios de aceptación.
La web estática actual permite campos curados; el producto por coordenadas arbitrarias requiere el servicio
de construcción de WS4-5 (o un equivalente probado). Consultar archivos sin generar una secuencia no alcanza.

## Empezar (5 minutos)

```bash
git clone https://github.com/faricool54/Hackaton-NASA && cd Hackaton-NASA
python scripts/dev.py setup        # Python venv + pipeline + backend + frontend
python scripts/dev.py web          # http://localhost:5173  (datos demo, sin backend)
```

Opcional: `python scripts/dev.py api` (backend en http://localhost:8000/docs) y abrir la web con `?mode=api`.

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
| WS1 | Acceso a datos SPHEREx (IRSA TAP/SIA, S3, cutouts) | `pipeline/errante/data/` | [tasks/WS1-data-access.md](../tasks/WS1-data-access.md) |
| WS2 | Imágenes alineadas y comparación; detección opcional | `pipeline/errante/imaging/`, `detect/` | [tasks/WS2-imaging-detection.md](../tasks/WS2-imaging-detection.md) |
| WS3 | Cinco blancos, astrometría, variables, espectros y contexto | `pipeline/errante/science/` | [tasks/WS3-science.md](../tasks/WS3-science.md) |
| WS4 | Backend API | `backend/` | [tasks/WS4-backend.md](../tasks/WS4-backend.md) |
| WS5 | Frontend (blink comparator, mapa, reportes) | `frontend/` | [tasks/WS5-frontend.md](../tasks/WS5-frontend.md) |
| WS6 | Producto, narrativa, deploy y entrega | `docs/submission/` | [tasks/WS6-product-submission.md](../tasks/WS6-product-submission.md) |
| WS7 | Modelos 3D opcionales, valores sin verificar | `pipeline/errante/systems/`, `frontend/src/three/` | [tasks/WS7-3d-systems.md](../tasks/WS7-3d-systems.md) |

Con 5 personas: WS6 se reparte entre WS4 y WS5 (ver [docs/TEAM.md](../docs/TEAM.md)).
Cada persona trabaja con su agente (Claude Code / Codex) usando el prompt que está al final de su archivo de tareas.

## Guía de entrega

La guía aportada fija los límites de demo, idioma y envío. Ver [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md).
Sede confirmada: Universidad de Palermo, Buenos Aires. Cierre según guía: 15/11/2026 23:59 ART;
objetivo interno 21:00 ART. README público/materiales de evaluación en inglés; este archivo es guía interna.
La [guía de evaluación](JUDGING_GUIDE.md) incorpora el segundo PDF: cinco criterios 1–5, inscripción local
1–6 con Team Owner/Members y proceso de nominaciones/premios. Ver [revisión interna](submission/JUDGING_REVIEW.md).

## Documentación

- [docs/CHALLENGE.md](../docs/CHALLENGE.md) — el reto, cómo lo interpretamos, criterios de evaluación
- [docs/REQUIREMENTS.md](../docs/REQUIREMENTS.md) — todos los objetivos/consideraciones y sus responsables
- [docs/VALIDATION.md](../docs/VALIDATION.md) — protocolo para los cinco objetos, resultados y evidencia
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) — arquitectura y flujo de datos
- [docs/CONTRACT.md](../docs/CONTRACT.md) — formato de datos/API entre pipeline, backend y frontend
- [docs/DATA.md](../docs/DATA.md) — **hechos verificados** sobre los datos SPHEREx (S3, FITS, flags, IRSA)
- [docs/SCIENCE.md](../docs/SCIENCE.md) — física necesaria: velocidades, paralaje, límites, encuadre honesto
- [docs/WORKFLOW.md](../docs/WORKFLOW.md) — git, PRs, cómo usar los agentes, cronograma del hackatón
- [AGENTS.md](../AGENTS.md) — reglas para agentes y humanos

## Estructura

```
pipeline/   paquete Python `errante` (datos → imágenes → detección → ciencia → productos JSON/PNG) + CLI
backend/    FastAPI `errante_api`: sirve productos + endpoints en vivo (IRSA, JPL)
frontend/   Vite + React + TypeScript: home, blink viewer, candidatos, espectro, about
shared/     JSON Schema generado del contrato (no editar a mano: `python scripts/dev.py schema`)
data/demo/  datos SINTÉTICOS de ejemplo (commiteados)   data/products/: productos reales   data/cache/: descargas (ignorado)
docs/ tasks/ notebooks/
```

## Créditos de datos

SPHEREx: NASA / JPL-Caltech / IPAC, vía NASA/IPAC Infrared Science Archive (IRSA). Efemérides: JPL Solar System
Dynamics, IMCCE SkyBoT.
