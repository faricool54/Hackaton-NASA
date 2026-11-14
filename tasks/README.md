# Tareas por workstream

**Para arrancar en paralelo:** leer [plan compartido y dependencias](../docs/PARALLEL_PLAN.md).
**WS4 está reservado por rpccp (rocco) con Codex**; los otros responsables deben confirmar su reserva.

Cada archivo es **autocontenido**: objetivo, rutas que te pertenecen, qué recibís y qué entregás, tareas con
criterio de aceptación y un **prompt de arranque** para pegarle a tu agente (Claude Code o Codex).

| Archivo | Workstream |
|---|---|
| [WS1-data-access.md](WS1-data-access.md) | Acceso a datos SPHEREx |
| [WS2-imaging-detection.md](WS2-imaging-detection.md) | Imágenes alineadas y comparación; detección opcional |
| [WS3-science.md](WS3-science.md) | Cinco blancos, astrometría, variables, espectros y contexto |
| [WS4-backend.md](WS4-backend.md) | Backend API, integración, CI |
| [WS5-frontend.md](WS5-frontend.md) | Frontend |
| [WS6-product-submission.md](WS6-product-submission.md) | Producto, narrativa, deploy y entrega |
| [WS7-3d-systems.md](WS7-3d-systems.md) | Sistemas 3D: modelos de los objetos, órbitas animadas, fichas |

Fuente de alcance: [enunciado completo](../docs/CHALLENGE.md), [matriz de cobertura](../docs/REQUIREMENTS.md)
y [validación de cinco blancos](../docs/VALIDATION.md). Los IDs R01–R05 son objetivos obligatorios;
C01–C08 son consideraciones opcionales, todas con tareas asignadas.
La [guía de entrega](../docs/SUBMISSION_GUIDE.md) incorpora **S01–S10** del PDF: plazo, demo obligatoria,
idioma, hosting, formulario/envío, NASA, referencias, SI/IA, elegibilidad y evaluación. Se aplica transversalmente.
La [guía de evaluación](../docs/JUDGING_GUIDE.md) precisa elegibilidad y escala 1–5 por criterio;
la [revisión interna](../docs/submission/JUDGING_REVIEW.md) exige evidencia sin adjudicar notas oficiales.

Prioridades: **P0** = RA/Dec → imágenes reales → blink público + cinco ensayos · **P1** = consideraciones
opcionales del enunciado · **P2** = ampliaciones propias (detección automática, distancias, límites, Planeta X).
Marcá `[x]` al terminar (solo en tu archivo) y poné el link al PR.

Orden de integración: I1 imágenes reales sin detección → I2 coordenadas y publicación → I3 cinco validaciones
→ I4 consideraciones → I5 análisis avanzado. Los IDs de tareas existentes se conservan aunque cambie su prioridad.

**Entrega UP Buenos Aires:** 15/11/2026 23:59 ART según guía; objetivo interno 21:00 ART. Demo <= 30 s o
<= 7 slides, inglés y enlaces anónimos. Todo aporte SI se registra en AI_USAGE.md y ai-usage.json según S08.

Plantilla para pedirle una tarea concreta al agente:

> Leé `AGENTS.md`, `docs/CONTRACT.md` y `tasks/WSx-....md`. Implementá la tarea **WSx-N** respetando las rutas
> de mi workstream. Agregá tests, corré `python scripts/dev.py check`, y mostrame el diff y cómo lo probaste antes de commitear.
