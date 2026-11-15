# WS6 · Producto, narrativa, deploy y entrega

**Objetivo:** que el proyecto **se entienda, se vea y se entregue bien**: nombre, historia, textos, video/demo,
deploy público y formulario de Space Apps completo y a tiempo.

**Cobertura:** R01/R05, estado público de C01–C08, **S01–S10** y todos los recursos efectivamente usados.

**Tus rutas:** `docs/submission/` · textos de `frontend/src/pages/AboutPage.tsx` y del hero de `HomePage.tsx`
(coordinando con WS5) · config de deploy del frontend (con WS4).

**Leé primero:** `docs/CHALLENGE.md`, `docs/SUBMISSION_GUIDE.md`, `docs/JUDGING_GUIDE.md`, `docs/SCIENCE.md` §4, `README.md` y
`docs/submission/CHECKLIST.md`. PDF inalterado en `docs/references/`. Sede UP Buenos Aires; cierre
15/11/2026 23:59 ART; objetivo interno de envío 21:00 ART. Horario de evaluación local pendiente.

## Tareas

- [x] **WS6-1a (P0) Incorporar íntegro el enunciado aportado** en `docs/CHALLENGE.md`, con procedencia
  y matriz R01–R05/C01–C08. Hecho 2026-11-14; el texto no fue cotejado con la página oficial inaccesible.
- [ ] **WS6-1b (P0, S01) Cotejar página del reto y evaluación local** con la organización. Las reglas
  generales ya constan en el PDF y la sede/zona fueron confirmadas por usuario; falta el horario local
  de evaluación/premios y lectura de términos/privacidad/marca completos. La guía de evaluación ya se
  incorporó desde el PDF aportado. Registrar fuentes en CHECKLIST.
  Volver a revisar la pestaña Resources antes de la entrega por posibles recursos agregados al reto.
- [x] **WS6-1c (P0) Incorporar la guía PDF** (14/11/2026): copia byte a byte en docs/references,
  procedencia/hash, síntesis por página y S01–S10 en matriz/checklist. No implica formulario enviado.
- [x] **WS6-1d (P0) Incorporar Judging & Awards Guide** (14/11/2026): PDF íntegro con hash,
  síntesis de elegibilidad, escala 1–5, fases/diez premios y plantilla JUDGING_REVIEW.md; S09/S10 actualizados.
  No equivale a haber evaluado oficialmente el proyecto ni verificado inscripción/nominación.
- [ ] **WS6-2 (P0) Nombre e identidad**: confirmar o cambiar "Errante" (historia: *planḗtēs* = errante), tagline,
  logo propio simple; no generar/incorporar/modificar elementos de marca NASA mediante SI.
- [x] **WS6-3 (P0) Deploy público del frontend**, con WS4: web/API en Google Compute Engine,
  https://errante.34-148-242-13.sslip.io; aceptación técnica #84/#95/#96. Demo y formulario no quedan enviados por esto.
- [ ] **WS6-4 (P0) Texto de la entrega** en `docs/submission/PROJECT.md` (en inglés): problema, solución, cómo
  funciona, datos NASA usados, beneficios, límites honestos, herramientas y uso de IA, equipo.
  Actualizado 15/11 por pedido del usuario: URL pública, cinco campos reales, jobs, espectros/comparaciones,
  curvas de luz y resultados offline revisados por WS3. About y créditos actualizados en la misma entrega.
  Faltan enlace de demo, datos de integrantes y revisión final del inventario/autoría por el equipo;
  no se marca el formulario como enviado ni revisión humana completada.
- [x] **WS6-4a (P0) README y documentos de estado.** Actualizados contra main 3ed5c91 (#97); publicación verificada 3ed5c91 (#97): hosting,
  contrato 0.7.0, funciones reales y pendientes. Se conservan fuentes/evidencias históricas como tales.
  Alcance pedido: documentación, sin producir demo, completar integrantes/formulario ni certificar revisión humana.
- [ ] **WS6-5 (P0, S02/S04) Demo obligatoria:** video **<= 30 s** o presentación **<= 7 slides**, contando
  portada/introducción. Guion actualizado en PITCH.md. Inglés; voz en otro idioma con subtítulos ingleses.
  Mostrar el estado real: si solo hay simulaciones, declararlo; nunca presentarlas como SPHEREx real.
  Incluir equipo/integrantes/reto, producto, experiencia y uso NASA. Medir archivo final y alojarlo externamente.
- [x] **WS6-5a (S02/S04/S08) Herramienta reutilizable para producir la demo.** Skill aportada por el usuario,
  adaptada e incorporada en `docs/submission/skills/video-tutorial/`; descarga/uso en
  [VIDEO_SKILL.md](../docs/submission/VIDEO_SKILL.md). Perfil con narración inglesa sin subtítulos,
  propuesta de valor en los primeros ~10 s, créditos y verificación estricta de 30 s sobre el MP4 final.
  No equivale a video producido, revisión humana, publicación ni envío; WS6-5 sigue pendiente.
- [ ] **WS6-6 (P0; herramientas opcionales C08) About/Créditos**: SPHEREx/IRSA y recursos realmente usados;
  Astropy/Aladin, Gaia/WISE, CSA/CADC/NEOSSat o JPL/IMCCE solo cuando corresponda. Revisar términos de uso,
  licencias del tutorial y cita requerida por IRSA; registrar acceso fallido sin inventar contenido.
  Equipo y declaración de IA según reglas verificadas. No atribuir datos WISE/NEOSSat a SPHEREx.
- [ ] **WS6-7 (P0, R01/R03/R04) Prueba con usuarios**: 3 personas ajenas ingresan RA/Dec, reproducen la
  secuencia y reconocen fecha/misión; al menos una prueba en celular. Anotar confusiones para WS5.
- [ ] **WS6-8 (P0, R05) Evidencia y estado de cobertura.** Publicar resultado de los cinco ensayos,
  separar intentos de recuperaciones y marcar C01–C08 como hechos/pendientes según evidencia. El pitch no
  promete detección automática ni espectros reales mientras sean stubs. Plantillas en PROJECT/PITCH/CHECKLIST.
- [ ] **WS6-9 (P0, S01/S05/S09) Registro y envío efectivo.** Integrantes aceptados en la sede;
  **1–6 locales (Universal 2–6)**, Team Owner en misma sede, todos en Members y sin waitlist. Resolver altas
  antes del cierre; después no pueden agregarse. Revisar guía, términos, privacidad y declaración de originalidad/referencias.
  Asignar responsable/backup; completar todos los campos en inglés, revisar términos/originalidad y pulsar
  Submit for Judging con confirmación antes de 15/11 23:59 ART (objetivo 21:00). Save Progress no basta.
  Conservar evidencia; reenviar/verificar tras cambios. Certificado posterior opcional según guía pág. 14.
- [ ] **WS6-10 (P0, S07/S08/S09) Fuentes, medios y SI/IA.** Completar AI_USAGE.md/ai-usage.json,
  historia del scaffold y origen de la idea; revisar regla SI sobre formular la idea. Inventario/permisos,
  marcas visibles para imágenes/videos SI y texto+metadata para audio/código/datos SI. Sin elementos de
  marca NASA en contenido generado ni representaciones de menores en demo/proyecto final. No dar por auditado lo pendiente.
- [ ] **WS6-11 (P0, S03/S04) Acceso e inglés.** README público ya traducido; revisar todos los materiales
  finales enlazados y probar sin login. La Project page admite imágenes <= 10 MB; videos/documentos por URL.
  FortiGuard recomendado, no obligatorio. No publicar documentación interna española como material de evaluación.
- [ ] **WS6-12 (P0, S10) Revisión por criterios.** Impact, Creativity, Validity, Relevance, Presentation;
  cada uno **1–5** en todos los niveles. Completar JUDGING_REVIEW.md con persona/fecha/versión y evidencia:
  usuarios/beneficio, aporte frente a referencias, viabilidad/usabilidad, NASA como núcleo y comunicación.
  Revisar descripción **y** demo, sin inventar pesos/total ni notas oficiales. Los diez premios no son diez
  requisitos de producto ni categorías que nos autoasignamos. Registro posterior de nominación/premio solo
  con fuente oficial; distinguir premio local, Global Nominee, Finalist, Honorable Mention y Global Winner.

## Prompt de arranque

> Sos el agente del workstream WS6 (producto y entrega) del repo Errante para NASA Space Apps 2026. Leé
> `AGENTS.md`, `docs/CHALLENGE.md`, `docs/SUBMISSION_GUIDE.md`, `docs/JUDGING_GUIDE.md`, `docs/SCIENCE.md` §4 y `tasks/WS6-product-submission.md`. Trabajá en
> `docs/submission/`. Ayudame con WS6-4: un borrador en inglés de `docs/submission/PROJECT.md` usando la
> plantilla, sin exagerar resultados (nada de "descubrimos"), dejando marcados con TODO los números que todavía
> no tenemos (límites medidos, objetos recuperados).
