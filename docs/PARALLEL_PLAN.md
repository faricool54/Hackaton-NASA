# Plan de trabajo paralelo y dependencias

Actualizado el 14/11/2026 sobre `main` en `859ae5e` (PRs #1, #2 y #3 integrados).
Este documento coordina trabajo pendiente; no acredita funcionalidades terminadas.
Asistencia de redacción: OpenAI Codex; ver [AI_USAGE.md](../AI_USAGE.md).

**Reserva confirmada: rpccp (rocco) con Codex toma WS4, backend/integración/CI.**
WS1, WS2, WS3 y WS5 deben confirmar sus responsables en [TEAM.md](TEAM.md) y reservar tareas antes de empezar.
No se asignan nombres ni se presume que alguien esté trabajando por tener una fila en este plan.

## Objetivo y estado de partida

Recorrido obligatorio: **RA/Dec → imágenes reales SPHEREx de distintas fechas → reproducción pública**
(R01–R04), con cinco ensayos documentados (R05). Ver [REQUIREMENTS.md](REQUIREMENTS.md).
La galería 3D, detección automática, JPL y Planeta X son P2; no bloquean ese recorrido.

Ya están integrados el enunciado, las dos guías, los cinco presets con coordenadas propagadas, la documentación
de consultas reales y las reglas de colaboración. El contrato publicado es **0.2.0**. Hay demo sintética,
visor y API de lectura de productos. El build básico ya publica antes del análisis opcional.

**Faltan** búsqueda y descarga reales implementadas, reproyección, comparación temporal útil, trabajos por
coordenadas, conexión al formulario, despliegue del recorrido completo y evidencia real. Un preset configurado,
un mock o un test de render no equivale a validar un objetivo con SPHEREx.

## Cinco frentes que pueden arrancar ahora

Los IDs conservan el significado de sus archivos en `tasks/`. El orden de integración no obliga a esperar
para desarrollar: usar fixtures y dependencias simuladas, luego sustituirlas por implementaciones reales.

| Frente | Qué hacer ahora | Qué entrega | Dependencia para cerrar con datos reales |
|---|---|---|---|
| **WS1 · datos** | WS1-2/3: búsqueda SIA VOTable, filtros, caché, recortes y fallos parciales. WS1-5/6: λ y selección temporal con WS2/3. Revisar la verificación ya aportada antes de repetir WS1-1. | `SearchResult`, `FrameRef`, FITS y asociación inequívoca referencia/descarga; ejemplo reproducible de Barnard. | Servicio externo accesible; acuerdo con WS2 para resultados parciales y metadatos. |
| **WS2 · imágenes** | WS2-1/2: reproyección y render consistente con fixtures FITS/WCS. Corregir selección temporal e identidad de frames en `build.py`. Preparar coadds por temporada × detector con WS3. | Campo con PNGs alineados y metadatos; build reproducible sin análisis. | FITS reales de WS1; método revisado por WS3; contrato si necesita campos nuevos. |
| **WS3 · ciencia/contrato** | WS3-3/7/9: aprovechar los cinco presets, definir mediciones y controles; coordinar el PR de contrato con WS1/2/4/5. | Contrato acordado, referencias y protocolo de movimiento/variabilidad; luego evidencia de los cinco ensayos. | Los criterios se definen ya; los resultados requieren FITS, épocas, λ, calidad y registro de WS1/2. |
| **WS4 · rpccp (rocco)** | WS4-2/5/10: robustecer API, validar entradas/rutas, acordar solicitud/estados; preparar ejecución y tests con funciones simuladas. Preparar WS4-3/4/6: construcción de campos y deploy. | Servicio por coordenadas, errores claros, límites/caché, lectura de productos y despliegue verificable. | Contrato de jobs para cerrar interfaz con WS5; funciones reales WS1/2 para cerrar R03. |
| **WS5 · frontend** | WS5-7/1/3/13: formulario, estados, reproducción estable, accesibilidad y textos honestos. Usar respuestas de prueba y demo; corregir teclado/cambio de campo. | Interfaz que solicita un campo y muestra la secuencia, fechas y errores. | Contrato de jobs y configuración de WS4; productos de WS2 para demostrar el recorrido real. |

**WS6 es transversal:** preparar desde ahora guion, referencias, atribución y formulario. Deploy: WS4;
textos/captura: WS5 con apoyo WS3. Confirmar quién edita/envía y su backup en TEAM.md. No esperar al final
para preparar la entrega. WS7 conserva sus rutas y su prioridad P2.

## Interfaces que hay que acordar primero

Acuerdo corto entre WS1/2/3/4/5 antes de implementar consumidores de campos nuevos.
El dueño del contrato es **WS3**; WS4 coordina la necesidad de jobs mediante WS4-10.
Esta sección enumera **decisiones pendientes, no endpoints ni campos disponibles**.

| Cruce | Acuerdo mínimo | Quién coordina |
|---|---|---|
| WS1 → WS2 | Vincular cada descarga con su `FrameRef`, incluso ante fallos; preservar WCS, IMAGE, VARIANCE, ZODI y FLAGS; declarar datos ausentes. No emparejar listas por posición si se omiten errores. | WS1 + WS2 |
| WS1/2 → WS3 | Épocas, detector/λ, unidades, cobertura, saturación y procedencia. Selección que cubra temporadas, sin duplicar reprocesados. | WS3 con WS1/2 |
| WS4 ↔ WS5 | Solicitud RA/Dec en grados, tamaño con unidad explícita, filtros y límites. Creación/consulta de job, identificador, estados, polling y referencias al campo/PNGs. | WS4 + WS5, contrato WS3 |
| WS2 → WS4/5 | Si hay coadds: miembros, método/pesos, fechas, detector, rango λ y cobertura; distinguir exposición de producto combinado. | WS2 + WS3, consumidores WS4/5 |

Estados a acordar: pendiente/en curso, listo, sin cobertura y fallo; decidir cómo informar resultados parciales.
No presentar descargas fallidas como «sin cobertura» ni un campo incompleto como éxito total. Fijar errores JSON,
reintentos, concurrencia/tiempos, claves de caché y publicación sin productos a medio escribir.
WS4 valida FOV/píxeles/frames para limitar recursos.

**Un único PR `contract:` a la vez**, con modelos Python, schemas generados, versión y tipos TS sincronizados,
ejemplos y aceptación de un consumidor. Hoy no hay rutas de jobs publicadas: no inventar una ruta por frente.
El PR documenta las rutas y valores definitivos. Ver [CONTRACT.md](CONTRACT.md).

Mientras se acuerda: WS4/5 avanzan con adaptadores y respuestas de prueba locales; WS2 con FITS de prueba;
WS3 con criterios/referencias y WS6 con guion. No modificar el contrato compartido por separado.

## Dependencias al integrar

```text
WS1: referencias + FITS → WS2: campo e imágenes → WS4: servicio → WS5: visor
          ↖ selección/medición WS3 ↗                 ↕ contrato WS3
                       evidencia real → WS6: demo y entrega
```

WS4 también consume directamente `search_frames` de WS1. WS5 ya puede mejorar el reproductor con campos
estáticos. WS3 no necesita candidatos automáticos para validar. Los campos precomputados son respaldo de la
demo, pero no sustituyen R03 (coordenadas arbitrarias).

## Riesgos conocidos y responsables

Hechos/mediciones reportados por el PR #3: [DATA.md](DATA.md) §3.0 y [SCIENCE.md](SCIENCE.md) §0.
Consultar esos registros; disponibilidad y tiempos de servicios externos no están garantizados.

- **WS1:** IRSA sin CORS exige backend para sus consultas; S3 permite Range. Preferir SIA VOTable (CSV
  defectuoso), TAP como fallback. Usar keys de la búsqueda, sin construir versiones a mano. Sin solape: 422;
  reintentar fallos transitorios. Optimizar con Range no debe perder flags/varianza necesarios para validar.
- **WS1/3:** tiempo medio: `MJD-AVG`, con fallback documentado; `MJD-OBS` es inicio. WCS-WAVE depende del
  detector: leer `TDIM`. Revisar comentarios antiguos que todavía digan otra cosa antes de implementarlos.
- **WS2:** primeros 40 frames pueden cubrir solo una temporada. Seleccionar épocas útiles y derivar identidad
  de observación/detector, no del hash de caché. `build.py` pertenece a WS2; cambios pedidos por WS1/4 se coordinan.
- **WS2/3/5:** movimiento esperado pequeño (~1–2 píxeles): registro estable, zoom y comparación de épocas.
  Cada exposición mide otra λ; el parpadeo aislado no prueba variabilidad. Comparar bandas compatibles,
  escala común y coadds/controles validados antes de afirmar cambios.
- **WS3:** WISE 0855 necesita centro propagado; visibilidad en D5/D6 sigue por medir. SPHEREx no resuelve
  ε Indi Ba/Bb como dos fuentes. Saturación/cobertura pueden volver un ensayo inconcluso. Registrar los cinco
  intentos aunque no haya señal; no prometer cinco detecciones.
- **WS4:** validar `field_id` antes de usar rutas (también separadores Windows), errores/tiempos externos,
  orígenes CORS y exposición de rutas locales. Mockear `/api/search` en CI antes de conectar WS1.
- **WS5:** limitar atajos al visor, reiniciar al cambiar campo, precargar imágenes y manejar fallos. `mode` ya
  significa `static`/`api`; no reutilizarlo para blink/diff. Usar espejos documentados si CDS sigue degradado.
- **Todos:** fixtures/demo con atribución sintética; análisis no ejecutado no es búsqueda negativa.
  Flags ausentes no significan calidad buena. FITS y cachés pesadas no van a Git.

## Puntos de encuentro y aceptación

1. **Interfaz acordada:** PR de contrato revisado; WS4/5 prueban los mismos ejemplos/estados. Los otros frentes
   siguen trabajando durante la revisión.
2. **Primer campo real (I1):** WS1+WS2 construyen Barnard sin `--analyze`, con épocas útiles, PNGs alineados,
   procedencia y errores registrados. WS3 revisa identidad/calidad. Que el comando termine no alcanza.
3. **Recorrido conectado (I2):** WS4+WS5 abren una posición no precargada desde la URL pública y muestran
   imágenes reales; probar fallo externo, sin cobertura y datos parciales. Acceso sin login.
4. **Cinco ensayos (I3):** WS3 coordina Barnard, ε Indi B, WISE 0855, RW Aur y R Dra con WS1/2/5. Guardar
   método, épocas, bandas, incertidumbre y resultado positivo/negativo/inconcluso según
   [VALIDATION.md](VALIDATION.md). WS6 reúne evidencia para la presentación.
5. **Entrega:** demo en inglés (video ≤30 s o ≤7 diapositivas), enlaces anónimos, referencias/licencias/IA y
   envío confirmado. Ver [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md) y
   [JUDGING_REVIEW.md](submission/JUDGING_REVIEW.md).

P1: espectros, overlays, controles de operaciones, calidad, URL/embebido y nuevas releases, después del
recorrido básico; incorporar antes lo imprescindible para una validación defendible. Aunque WS2-10 lista
coadds como P1, WS2/3 deben acordar qué combinación mínima necesita R05: no posponer comparabilidad de λ por
esa etiqueta. No iniciar P2 mientras I1–I3 estén bloqueados.

## Cómo tomar una tarea sin pisarse

1. Leer `AGENTS.md`, este plan, `docs/COLLABORATION.md`, `docs/CONTRACT.md` y tu `tasks/WSx-*.md`.
2. Reservar en issue o chat: «Tomo WSx-N; entrego X; necesito Y de WSz». Avisar cambios de interfaz.
3. Crear rama y worktree propios desde `origin/main`; instalar dependencias en ese worktree:

   ```bash
   git fetch origin
   git worktree add -b ws1/search ../hn-ws1-search origin/main
   cd ../hn-ws1-search
   python scripts/dev.py setup
   ```

   Adaptar WS/rama/ruta. En Windows se puede usar `py` en lugar de `python`. Cada agente usa su propia carpeta
   y puertos; nunca dos agentes en el mismo working tree.
4. Editar solo tus rutas según [COLLABORATION.md](COLLABORATION.md). Contrato → WS3; `build.py` → WS2;
   deploy/CI → WS4; tipos TS compartidos → contrato. Marcar casillas solo en tu archivo de tareas.
5. Antes de push: `git pull origin main` (merge, sin rebase), `python scripts/dev.py check`, revisar diff,
   stage por nombres y PR pequeño. Nunca `git add -A`, `git add .`, force push ni commits directos en `main`.
6. Compartir PR, entregable, cómo probarlo, qué queda simulado y qué dependencia falta. Tras merge, los
   consumidores traen `main` y sustituyen mocks. La prueba offline no cierra la prueba real; red separada de CI.

Freeze acordado en COLLABORATION.md: domingo 15/11 a las 17:00 ART. Objetivo interno de envío: 21:00 ART;
cierre según guía: 23:59 ART, sede UP Buenos Aires. Edición/envío y backup siguen pendientes de responsable.

## Siguiente bloque de WS4 (rpccp)

Primero WS4-2: validación de rutas, errores claros, límites/tiempos y tests offline con funciones simuladas.
Con esa preparación, coordinar WS4-10 con WS3/5 para cerrar contrato de jobs; luego WS4-5 lo implementa.
Integrar WS1/2 al estar listos y cerrar construcción de campos/deploy (WS4-3/4/6). No implementar por nuestra
cuenta los módulos de datos, imágenes ni tipos compartidos.
