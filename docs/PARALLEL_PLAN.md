# Plan paralelo actualizado — 14/11/2026

Estado de la integración WS4/WS5; no acredita validaciones científicas ni publicación pública.
Visión vigente: [VISION.md](VISION.md). Reglas: [COLLABORATION.md](COLLABORATION.md).
Detalle técnico y evidencias: [WS4_INTEGRATION.md](WS4_INTEGRATION.md).

## Ya disponible

- WS1: búsqueda real SIA/TAP, caché, recortes S3/IBE, λ y MJD medio (#21–#25).
- WS2: reproyección/selección temporal y cinco campos reales, 40 imágenes cada uno (#16/#17).
- WS2: coadds/restas por temporada (#19) y fotometría forzada por exposición (#31). Sus productos públicos
  nuevos requieren acuerdo de contrato; una resta con λ distinta no certifica variabilidad.
- WS4: endpoints robustos, batch de cinco campos, motor persistente y publicación verificada.
- Integración #32 → #33 → PR WS5: contrato 0.3.0, correcciones de la revisión y mapa/formulario → job → PNG.
  Aceptación local con datos reales. Tras cada squash, actualizar la rama siguiente con merge de main, check/push y retarget a main.
- Demo sintética conservada y etiquetada; los cinco campos reales se pueden abrir en modo estático.

## Qué se puede hacer en paralelo ahora

| Frente | Trabajo concreto | Puede arrancar ya con | Dependencia para cerrar |
|---|---|---|---|
| WS1 | Revisar estabilidad/latencia, coverage y errores de archivos; conservar metadatos y atribución | Funciones reales y cachés existentes | IRSA/S3 accesibles para pruebas de red; coordinar firma si cambia |
| WS2 | Revisar mediciones/restas, compatibilidad espectral, máscaras y fallos parciales; apoyar R05 | #17/#19/#31 y FITS reales | WS3 acuerda método científico; contrato antes de nuevas vistas |
| WS3 | Ensayos de los cinco blancos; espectro por posición con incertidumbre/época/calidad; Gaia y modelos físicos | Imágenes reales y fotometría WS2 #31; protocolo VALIDATION.md | Acceso a FITS/catálogos y revisión de métodos; acordar modelos en PR contract |
| WS4 (rpccp) | Integrar PRs de corrección; destino público si el equipo lo elige; exponer próximos productos científicos | Motor/API/CI/container listos, contrato 0.3.0 | Destino/URL para publicación; contrato científico acordado para espectros/compare |
| WS5 | Pulir accesibilidad/onboarding, zoom/retícula, vista de calidad y operaciones | Mapa, jobs y secuencia real ya conectados | Contrato de espectro/compare y datos medidos; Lighthouse por medir |
| WS7 | Sustituir parámetros/superficies inventadas por un modelo físico trazable | Reglas VISION.md y catálogos confirmados | Espectro/fotometría/temperatura/distancia WS3; sin dato, unknown |
| WS6 | Demo en inglés, referencias/licencias/IA, formulario y envío | Recorrido local y cinco campos de respaldo | Evidencia R05, URLs sin login, miembros y aceptación humana de la entrega |

No hace falta esperar a un nuevo endpoint para definir un ensayo o revisar una medición. El consumidor
puede usar fixtures del modelo **acordado**, pero no inventar otro formato compartido por su cuenta.

## Acuerdos todavía necesarios

1. **Espectro por posición:** solicitud, tarea/caché, puntos λ/flujo/error/fecha, fracción válida, máscaras,
   no cobertura/fallos parciales y procedencia. WS2 produce fotometría; WS3 define interpretación; WS4/5
   acuerdan consumo. El `Candidate.spectrum` existente no reemplaza el caso sin candidato.
2. **Comparación:** `compare/compare.json` de #19 es provisional. Definir miembros/pesos, temporadas,
   detector/λ, escala de flujo, incertidumbre y limitaciones antes de API/UI (WS2+WS3+WS4+WS5).
3. **Ficha física/3D:** Gaia/distancia, incertidumbre, temperatura/radio derivados y compañeras confirmadas,
   con fuentes. No derivar planetas o superficies del video (WS3+WS7).
4. **Publicación:** elegir destino y configuración verificable. Una URL estática con campos curados sirve
   para mostrarlos; coordenadas arbitrarias requieren servicio activo. Uso local no requiere contratar hosting.

Contrato de jobs ya acordado e implementado: [CONTRACT.md](CONTRACT.md). No crear otra API de jobs.

## Aceptaciones que siguen abiertas

- **R05:** cinco registros con método, épocas/λ, controles, incertidumbre y resultado positivo/negativo/
  inconcluso según VALIDATION.md. Publicar 40 PNG no demuestra recuperación ni variabilidad.
- **R01/R03 público:** abrir una posición no precargada desde el origen final, sin login; probar CORS,
  fallo externo y sin cobertura. Configurar persistencia, worker y raíces públicas/privadas.
- **Entrega:** video ≤30 s o ≤7 diapositivas incluyendo portada, materiales en inglés, acceso anónimo,
  referencias/medios/IA revisados y confirmación de Submit for Judging.

Los estados pendientes se conservan en tareas; no marcar todos los opcionales de un WS como terminados por
haber cerrado la integración P0 local. [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md),
[JUDGING_GUIDE.md](JUDGING_GUIDE.md), [VALIDATION.md](VALIDATION.md) y TEAM.md conservan sus responsables.

## Tomar una tarea e integrar

Reservar en issue/chat con WS/entregable/dependencias; una rama/worktree propio, solo sus rutas. Cambios de
contrato: un PR contract a la vez, modelos/schema/versión/TS juntos y revisión afectada. Antes de cada push:
`git pull origin main` (merge), `python scripts/dev.py check`, revisar diff y stage por nombres. Sin force
ni commits a main. Para PRs apilados, `ERRANTE_BASE_REF=origin/<base-inmediata>` hace que la guardia local
compare contra la misma base que CI; no cambia los permisos de ownership.

Freeze: domingo 15/11 17:00 ART. Objetivo interno de envío: 21:00 ART; cierre de guía: 23:59 ART, sede UP
Buenos Aires. Confirmar editor/envío y backup en TEAM.md. No inferir que Save Progress sea envío confirmado.
