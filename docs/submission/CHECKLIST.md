# Checklist de entrega - WS6

Fuente: [Project Submission Guide](<../references/NASA Space Apps Challenge.pdf>), 13/11/2026.
Síntesis y páginas: [SUBMISSION_GUIDE.md](../SUBMISSION_GUIDE.md). El PDF se conserva sin cambios.
La página del reto sigue sin cotejo web; las reglas de esta checklist provienen de la guía aportada.
Complemento: [Judging & Awards Guide](<../references/NASA Space Apps Challenge Judging & Awards Guide.pdf>),
con síntesis en [JUDGING_GUIDE.md](../JUDGING_GUIDE.md) y [revisión interna](JUDGING_REVIEW.md).

## Sede y fechas (S01)

- [x] Sede confirmada por el usuario el 14/11/2026: **Universidad de Palermo, Buenos Aires, Argentina**.
- [x] Zona aplicable: **America/Argentina/Buenos_Aires, ART (UTC-3)**.
- [x] Apertura según guía: **sábado 14/11/2026, 09:00 ART**.
- [x] Cierre según guía: **domingo 15/11/2026, 23:59 ART** = **16/11/2026, 02:59 UTC**.
- [ ] Confirmar con Local Lead horarios de evaluación/premios locales, que pueden diferir.
- [ ] Objetivo interno: **enviado y confirmado el domingo 15/11 a las 21:00 ART**, con margen al cierre.

## Formulario y envío efectivo (S05/S09)

- [ ] Responsable de edición/envío: TODO; coordinar uso del lock, que otro miembro puede quitar.
- [ ] **1–6 integrantes locales** (Universal 2–6); todos aceptados en la misma sede, **Team Owner incluido**,
  sin lista de espera y visibles en **Members**. No contar agentes como integrantes.
- [ ] Revisar/terminar altas de integrantes antes del cierre; después no se pueden agregar personas.
- [ ] Confirmar correspondencia con un reto oficial; el cotejo de la página del reto sigue pendiente.
- [ ] Project Name completo.
- [ ] High-Level Project Summary completo, con resultados y pendientes reales.
- [ ] Link to Project Demo público y válido.
- [ ] Link to Final Project público y válido.
- [ ] Detailed Project Description completa: función, método, beneficio, objetivos, herramientas y equipo.
- [ ] Use of Super Intelligence (SI) completo según el uso real.
- [ ] NASA Data: al menos un dato/recurso NASA usado, identificado con precisión.
- [ ] Space Agency Partner Data and Other References: inventario completo de código/texto/imágenes/datos/herramientas.
- [ ] Formulario y materiales enlazados en inglés; sin TODOs que aparenten una entrega final.
- [ ] Revisar declaraciones de comprensión de la guía, **Participant Terms and Conditions y Privacy Policy**;
  originalidad, inventario completo de referencias y permisos, antes de aceptar.
- [ ] Revisar con la organización la determinación de elegibilidad que le corresponde a NASA (guía pág. 4),
  si aplica; no inferir afiliaciones ni guardar datos personales de esa revisión en el repo.
- [ ] Pulsar **Submit for Judging antes del cierre**; Save Progress por sí solo no envía a evaluación.
- [ ] Ver banner y mensaje de confirmación; guardar evidencia con fecha/hora.
- [ ] Si se edita después, guardar/reenviar y volver a verificar confirmación antes del cierre.

## Demo obligatoria y acceso (S02/S03/S04)

- [ ] Elegir **video <= 30 segundos O presentación <= 7 diapositivas**, contando portada/introducción/créditos.
- [ ] Medir el archivo final; exceder los límites excluye de Global Judging según el PDF.
- [ ] Nombre del equipo, integrantes y reto identificados; proyecto/prototipo y experiencia de uso visibles.
- [ ] Inglés; si la voz del video es otra lengua, subtítulos en inglés.
- [ ] Demo alojada externamente, sin login, permisos, registro ni contraseña.
- [ ] Proyecto final y todos los materiales enlazados probados en incógnito/otra sesión y celular.
  El repositorio actual es privado; su URL sola no pasa este control. Elegir/publicar materiales accesibles
  para evaluación sin asumir que se autorizó cambiar la visibilidad del repositorio.
- [ ] Solo imágenes JPG/PNG/GIF <= 10 MB en la Project page; video/documentos se comparten por enlace externo.
- [ ] Sin imagen, video, audio u otra representación de menores de 18 años en demo/proyecto final.
- [ ] Opcional: evaluar clasificación FortiGuard de la web nueva; no es condición de entrega.

## Fuentes, uso de IA y marca (S06/S07/S08)

- [ ] Identificar qué recurso/dato NASA se usó realmente; documentación consultada no equivale a FITS procesado.
- [ ] Inventario de todas las fuentes y licencias/permisos, incluso si son gratuitas/open source.
- [ ] Reconocimientos de SPHEREx/IRSA y demás fuentes efectivamente usadas.
- [ ] Declarar origen de la idea y revisión del equipo respecto a la limitación de SI para formularla.
- [x] Crear atribución del uso conocido de Codex en AI_USAGE.md y metadata ai-usage.json (borrador).
- [ ] Completar/revisar scaffold previo, generador sintético, otros agentes/herramientas y contribuciones.
- [ ] Imágenes/videos SI con marca de agua visible, cuando existan.
- [ ] Audio/código/datos SI con reconocimiento en texto descriptivo **y metadatos**, cuando existan.
- [ ] Contenido generado sin incorporar/modificar elementos de marca/diseño NASA; revisar la guía enlazada.
- [ ] Declaración pública coherente con formulario SI; no asumir que el campo privado basta.

## Evidencia del reto (R01-R05)

Estado técnico al 15/11, main 3ed5c91 (#97); publicación verificada 3ed5c91 (#97): app/API públicas, cinco campos reales, jobs por coordenadas,
espectros/comparaciones y curvas verificados; #95 comprobó 396 PNG y persistencia de un job en iframe.
Los cinco registros FITS ya existen. Las casillas de aceptación final se conservan para revisión del
equipo: no significan que falten esos módulos, ni autorizan cerrar R05 sin revisión humana/paso 6.
Ver [matriz actualizada](../REQUIREMENTS.md) y [estado de integración](../WS4_INTEGRATION.md).

- [x] Enunciado íntegro y recursos incorporados en CHALLENGE.md.
- [x] R01-R05 y C01-C08 asignados a tareas en REQUIREMENTS.md (planificación, no implementación).
- [x] PDF leído, preservado y reglas S01-S10 integradas con referencia de página.
- [x] Segundo PDF de evaluación leído y preservado; escala 1–5 y ampliaciones de S09/S10 incorporadas.
- [ ] R01: frontend y servicio necesarios accesibles en URL pública, incógnito y celular.
- [ ] R02: imágenes SPHEREx reales alineadas con fechas, detector, release y URI de origen.
- [ ] R03: RA/Dec no precargadas producen secuencia, con progreso/errores/sin cobertura explícitos.
- [ ] R04: reproducción, paso, velocidad y fecha funcionan sin análisis automático.
- [ ] R05: registro de Barnard's Star según VALIDATION.md.
- [ ] R05: registro de Epsilon Indi B, con componente/identidad verificados.
- [ ] R05: registro de WISE 0855, con posición/época/propagación verificadas.
- [ ] R05: registro de RW Aurigae, con comparación fotométrica compatible.
- [ ] R05: registro de R Draconis, con comparación fotométrica compatible.
- [ ] Tabla distingue ensayos de resultados positivos; simulaciones etiquetadas y límites honestos.
- [ ] Modelos 3D identificados como modelos, con fuentes/estado de verificación por valor; no contarlos como cinco ensayos reales.

## Consideraciones opcionales: estado al entregar

- [ ] C01: actualización de releases/caché/versiones.
- [ ] C02: bandas, coadds por detector/visita y espectros en posición elegida.
- [ ] C03: suma/resta con procedencia y compatibilidad científica.
- [ ] C04: FOV configurable con costo/límites de transferencia.
- [ ] C05: Gaia DR3/WISE con misión, época y crédito.
- [ ] C06: URL con coordenadas restaurable y modo embebido probado.
- [ ] C07: metadatos/flags explicados.
- [ ] C08: herramientas públicas evaluadas y decisiones/licencias registradas.

Registrar cuáles se implementaron y cuáles quedaron pendientes; estas opciones no pasan a ser obligatorias.
Detección, distancias, inyección y Planeta X solo se anuncian si hay evidencia.

## Evaluación y seguimiento (S10)

- [ ] Completar JUDGING_REVIEW.md: Impact, Creativity, Validity, Relevance y Presentation, **cada uno 1–5**,
  con persona/fecha/versión/evidencia. No sumar, ponderar ni presentar notas internas como oficiales.
- [ ] Impact: problema/público definidos; observaciones de usuarios separadas de beneficios esperados.
- [ ] Creativity: inspiración WiseView/IRSA acreditada y contribución propia demostrada, sin novedad inventada.
- [ ] Validity: recorrido reproducible y usable, base científica, resultados/limitaciones de cinco ensayos.
- [ ] Relevance: observaciones NASA como parte central de RA/Dec → secuencia, no solo citas/créditos.
- [ ] Presentation: claridad y coherencia de demo **y proyecto completo**; reservar tiempo de narrativa/diseño.
- [ ] La descripción escrita está completa: la mayoría de la evaluación se basa en la presentación del proyecto.
- [x] Leer la Judging & Awards Guide aportada; criterios y fases documentados en JUDGING_GUIDE.md.
- [ ] Leer términos/privacidad/guía de marca completos; la guía de evaluación no sustituye esos documentos.
- [ ] Tras envío, comprobar certificado en perfil si se desea; nombre completo y formato Letter.

Seguimiento posterior opcional según PDF: Global Nominees **03/12/2026**; Finalists/Honorable Mentions
**17/12/2026**; Global Winners **26/01/2027**. No son plazos de construcción ni recordatorios creados.
Un premio local no acredita nominación oficial; Honorable Mentions no pasan a Executive Judging ni Global Awards.
No marcar estos estados como logrados sin anuncio oficial.
