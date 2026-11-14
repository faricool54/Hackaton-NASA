# Cierre de la revisión WS4 y conexión WS5

14/11/2026 — rpccp con asistencia de Codex. Evidencia técnica local; revisión humana pendiente.

## Integración y orden de revisión

1. [#32, contrato 0.3.0](https://github.com/faricool54/Hackaton-NASA/pull/32): modelos compartidos de jobs y
   resolver, schema generado, tipos/versión TS y casos válidos/inválidos. Requiere OK de un afectado.
2. [#33, backend](https://github.com/faricool54/Hackaton-NASA/pull/33): correcciones de abajo, usando #32.
3. [#34, frontend](https://github.com/faricool54/Hackaton-NASA/pull/34): formulario/mapa/visor sobre #33.
4. Este registro de coordinación y actualización de docs, sobre la integración anterior.

Los PRs están apilados: tras cada squash, traer `origin/main` a la siguiente rama mediante merge
(`git pull origin main`), correr check contra origin/main, pushear, retargetear ese PR a main y esperar CI.
Así su diff deja de incluir los cambios ya integrados. Sin rebase ni force push. Las ramas
incorporan main con los campos reales/comparaciones/fotometría de WS2; no se modificaron sus algoritmos.
La carpeta original del usuario no se cambió de rama: se trabajó en worktrees aislados.

## Problemas corregidos

| Problema reproducido | Corrección | Evidencia |
|---|---|---|
| Preflight CORS rechazaba POST | GET/POST y cabeceras JSON permitidos | OPTIONS → POST real desde Vite |
| Motor escribía en raíz distinta de la servida; primer campo 404 | Una raíz pública, creada antes de StaticFiles; estado de jobs separado | Arranque sin manifest → job → JSON/PNG/manifest legibles |
| Copia parcial/manifest no atómico/falso ready | Staging privado, validación JSON/PNG, rename y manifest atómico; lock entre batch/jobs | Fallo de copia/manifest conserva producto anterior; no ready falso |
| Admisión SELECT/INSERT concurrente | BEGIN IMMEDIATE; deduplicar antes del límite | Ocho solicitudes idénticas → un job; cupo nunca excedido |
| Recuperación insuficiente | Recibos de huellas, intento/generación, reconciliar publicación; cuarentena de datos dañados | Recuperación antes/después de instalar, staging dañado y producto corrupto |
| Hijo huérfano/lock liberado prematuramente | Verificar identidad, cerrar descendientes y retener lock hasta terminar | Proceso real + descendiente; regresiones Windows/Linux |
| Recursos/errores | Logs y disco acotados; caché contextual; validar resultado al reutilizar; errores sin traceback | Cuota/log/resultado desaparecido; sin cobertura solo ante consulta vacía válida |
| Nombres reales no resolvían | Preferir jradeg/jdedeg y soportar jpos con dos puntos; codificar nombre | XML real de CfA y búsqueda de R Draconis en navegador |
| Formulario sin flujo real | Un cliente para form y map click, POST/GET, errores, reintento, abort local y URL | Tres jobs reales, tres secuencias de 40 imágenes |
| Reproductor interfería con controles/ocultaba fallos | Atajos dentro del visor; precarga/errores/reintento, remount por campo/filtro | Navegador escritorio/móvil y prueba de carga completa |

Los límites de disco son muestreo supervisado; cuotas duras de CPU/memoria/disco pertenecen al host.
Una instancia/supervisor y un worker son suficientes para la configuración actual; no se agregó un cluster.

## Evidencia real del recorrido

- Formulario: RA 269.44623°, Dec +4.76870°, D2, FOV 0.05°, 40 frames.
- Click de mapa: RA 269.4401033°, Dec +4.8094009°, mismos filtros, 40 frames.
- Nombre: R Draconis → CfA `V* R Dra`, RA 248.16761083°, Dec +66.75497942°, D2, FOV 0.05°, 40 frames.
- Todos llegaron a ready; el navegador cargó 40 PNG con dimensiones reales y mostró fechas/λ/release.
  Móvil 390×844 sin desborde horizontal; play/pausa y restauración de enlace comprobados.
- RA=360 rechazado por UI; modo estático no envía builds y conserva badges de demo sintética.
- Antes de esta integración: batch real de cinco campos, 40 frames cada uno, validate correcto, 139.9 s.
  Ahora #17 incluye esos campos curados en main. Ninguna de estas pruebas certifica por sí sola R05.
- `scripts/dev.py check`: guardia, lint/formato, schema, productos demo, tests Python y frontend, build.
  En el entorno científico completo pasaron 352 tests Python (26 omitidos) y 66 frontend.
  CI agrega Windows backend y build/smoke de contenedor Linux. Red excluida de tests offline.

Metadatos de asistencia en backend/ai-usage.json y frontend/ai-usage.json; no se generaron imágenes del cielo
con IA. La evidencia gráfica local y los caches/FITS pesados no se agregan al repositorio.

## Qué falta y de quién depende

PRs abiertos vistos al cerrar: #35 mejora selección/λ y #37 las restas; todavía no están integrados.
Al entrar #35, revisar/subir `JobRequest.build_context.build_revision` para no reutilizar imágenes con la
selección anterior. #39 propone composites de falso color sobre versión 0.2.2: si #32 entra primero,
su autor debe actualizarlo a 0.3.1, regenerar schema/TS y traer main. No renumerar ambos por separado.
La publicación actual copia/hashea el árbol completo, incluido `color/`; al adoptar el modelo Composite,
ampliar también la validación de sus PNG antes de declararlos listos. El frontend de composites debe
integrarse encima de #34 para conservar precarga, errores y los atajos acotados al visor.

- WS4-4/6: destino/URL pública y prueba desde el origen final. Hosting aún no definido; no se contrató nada.
- WS4-8/9/10 (extras): WS2 #19/#31 ya aporta comparación/fotometría; falta contrato científico acordado,
  API y vistas con WS3/WS5. No consumir `compare.json` provisional como contrato estable.
- WS3 + WS1/2: validación científica de los cinco blancos (movimiento/variabilidad, controles y errores),
  espectros comparables y fuentes Gaia. Un preset o imagen visible no reemplaza esas mediciones.
- WS7: migrar galería ilustrativa a modelo físico con datos/incertidumbre; no inventar superficie/planetas.
- WS5/6: Lighthouse, pulido de accesibilidad, demo/materiales y enlaces sin login; envío confirmado.

El P0 local de coordenadas está cerrado en estas ramas; WS4 completo incluye pendientes de publicación y
contratos P1 que siguen marcados abiertos. Ver PARALLEL_PLAN.md y tasks/WS4-backend.md.
