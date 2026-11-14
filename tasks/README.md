# Tareas por workstream

Cada archivo es **autocontenido**: objetivo, rutas que te pertenecen, qué recibís y qué entregás, tareas con
criterio de aceptación y un **prompt de arranque** para pegarle a tu agente (Claude Code o Codex).

| Archivo | Workstream |
|---|---|
| [WS1-data-access.md](WS1-data-access.md) | Acceso a datos SPHEREx |
| [WS2-imaging-detection.md](WS2-imaging-detection.md) | Imágenes y detección de objetos en movimiento |
| [WS3-science.md](WS3-science.md) | Objetos conocidos, distancia, espectros, Planeta X |
| [WS4-backend.md](WS4-backend.md) | Backend API, integración, CI |
| [WS5-frontend.md](WS5-frontend.md) | Frontend |
| [WS6-product-submission.md](WS6-product-submission.md) | Producto, narrativa, deploy y entrega |
| [WS7-3d-systems.md](WS7-3d-systems.md) | Sistemas 3D: modelos de los objetos, órbitas animadas, fichas |

Prioridades: **P0** = sin esto no hay demo · **P1** = lo que hace ganar · **P2** = si sobra tiempo.
Marcá `[x]` al terminar (solo en tu archivo) y poné el link al PR.

Plantilla para pedirle una tarea concreta al agente:

> Leé `AGENTS.md`, `docs/CONTRACT.md` y `tasks/WSx-....md`. Implementá la tarea **WSx-N** respetando las rutas
> de mi workstream. Agregá tests, corré `make check`, y mostrame el diff y cómo lo probaste antes de commitear.
