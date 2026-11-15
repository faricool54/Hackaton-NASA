# Cobertura del enunciado

Fuentes: [CHALLENGE.md](CHALLENGE.md), texto íntegro aportado por el equipo, y [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md),
reglas del PDF de entrega, más [JUDGING_GUIDE.md](JUDGING_GUIDE.md), síntesis del PDF de evaluación/premios.
Ambas referencias se conservan sin cambios. Actualizado: **2026-11-15**, main `4d88aa0` (#96).
Esta matriz es la fuente de prioridades. Cada tarea cita sus IDs para que ningún punto se pierda.
**Asignado o diseñado no significa implementado.** Las casillas se marcan solo con evidencia verificable.

## Prioridades

- **P0:** recorrido exigido y entrega pública: RA/Dec → imágenes SPHEREx reales → animación → validación.
- **P1:** consideraciones opcionales del enunciado, después de estabilizar P0.
- **P2:** ampliaciones del equipo y optimizaciones. Detección automática y Planeta X entran aquí.

## Objetivos explícitos

| ID | Requisito | Responsable y tareas | Criterio de aceptación | Estado actual |
|---|---|---|---|---|
| R01 | Herramienta web pública para cualquier persona | WS5-2/3, WS4-4/6, WS6-3/7 | URL pública abre en incógnito y celular; una persona nueva reproduce un campo sin instalar herramientas | Implementado y publicado (#84/#95/#96); aceptación técnica pública y viewports móviles; prueba con usuarios pendiente |
| R02 | Imágenes reales SPHEREx de la misma región en distintas fechas | WS1-1/2/3/4/6, WS2-1/2, WS4-3 | PNGs sobre grilla común, fechas ordenadas, release y URI de origen; al menos dos épocas útiles por secuencia | Implementado: cinco campos reales de 40 frames, WCS/fechas/release/URI; 200 PNG verificados en #95 |
| R03 | Ingresar ascensión recta y declinación | WS5-7, WS4-2/5 | Coordenadas válidas producen una secuencia de esa región, no solo una lista de archivos o un campo cercano precargado; errores y ausencia de cobertura explícitos | Implementado: formulario/nombre/mapa → job → imágenes reales; jobs nuevos y persistencia probados públicamente |
| R04 | Mostrar una secuencia como video para reconocer cambios | WS5-1/2, WS2-2 | Play/pausa, paso, velocidad, fecha y filtro espectral; imágenes alineadas y sin depender de candidatos automáticos | Implementado sobre datos reales: reproducción/paso/velocidad/detector; zoom y predicción Gaia de Barnard en #96 |
| R05 | Probar Barnard, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis | WS3-3/9, WS1-4/5/6, WS2-8, WS5-7, WS6-4 | Cinco registros con coordenadas/época/fuente, cobertura, imágenes, resultado y limitaciones según VALIDATION.md | Cinco registros FITS offline success y re-mediciones por agentes; aprobación humana y cierre del paso 6 pendientes |

## Consideraciones opcionales: todas contempladas

| ID | Punto del enunciado | Diseño y tareas | Evidencia de aceptación | Prioridad / estado |
|---|---|---|---|---|
| C01 | Actualizar con nuevos releases | WS1-9, WS4-3: descubrir colecciones, registrar release/versión, refrescar consulta e invalidar caché por versión | Una actualización incorpora nuevas épocas sin editar nombres de tablas en la UI; sin duplicar reprocesados | P1; parcial: colecciones configurables/caché con versión; descubrimiento y Release abierto pendientes (V20) |
| C02 | 102 bandas, sumar por cada uno de los seis detectores, espectros bajo demanda | WS1-5, WS2-10, WS3-5, WS4-8, WS5-12 | Selector detector/λ; coadds por detector y visita con miembros/pesos; espectro en una posición con errores y fechas | P1; implementado: mapa DR1, coadds, espectros reales cubo/L2 y curvas; movimiento propio L2 en API desde 0.7.0, UI aún pendiente |
| C03 | Sumar o restar imágenes de distintas fechas | WS2-7/10, WS4-9, WS5-8 | Elegir A/B o conjunto; resultado sobre WCS común con unidades, máscara y épocas de entrada; advertir diferencias espectrales | P1; implementado: medias/restas compatibles, API/UI live y 196 PNG exportables (#82/#95); su UI estática y SNR del coadd pendientes |
| C04 | Elegir campo de visión y explicar costo de transferencia | WS1-3, WS4-5, WS5-9 | FOV configurable con límites documentados; validación en cliente/servidor; se refleja en descarga, tamaño de grilla y estimación/progreso | P1; implementado: FOV público, validación, cupos y progreso; sin estimación de bytes previa exacta |
| C05 | Superponer datos de Gaia o WISE | WS3-10, WS5-4 | Gaia DR3 con movimiento propio a cada época cuando esté disponible; WISE identificado por misión, banda y fecha; capas activables y crédito | P1; parcial: AllWISE y ficha Gaia/catálogos integradas; capa Gaia propagada y footprint pendientes |
| C06 | Coordenadas en URL para compartir e integrar en otros sitios | WS5-11, WS4-5/6 | URL con RA/Dec/FOV/detector restaura el estado en una sesión nueva; modo embebido probado desde otro origen | P1; parcial: URL/restauración y app completa/jobs en iframe externo verificados (#95); falta vista compacta WS5 |
| C07 | Mostrar metadatos, por ejemplo flags de contaminación | WS1-4, WS2-11, WS4-10, WS5-10 | Fecha, detector, λ si existe, release, origen, cobertura válida y flags explicados; desconocido no equivale a limpio | P1; parcial: fecha/λ/release/origen y valid_fraction en contrato/API; UI de calidad y nuevas fracciones de flags pendientes |
| C08 | Evaluar herramientas públicas de datos y visualización | WS1-1, WS2-1, WS5-4, WS6-6 | Astropy para FITS/WCS; evaluación de notebooks IRSA y Aladin; decisión/licencias/créditos registrados | P1; Astropy y Aladin Lite 3.8.2 integrados, fuentes visibles; revisión final de licencias/inventario pendiente |

## Recursos y función dentro del proyecto

| Recurso del enunciado | Uso previsto | Tarea |
|---|---|---|
| NASA/IPAC IRSA SPHEREx | Datos principales, documentación, releases y procedencia | WS1-1/2/9 |
| Notebooks SPHEREx | Consultas, cutouts, WCS espacial/espectral y ejemplos reproducibles | WS1-1/3/5, WS2-1 |
| WiseView | Referencia para coordenadas, FOV, blink, capas y comparación; sus imágenes no son SPHEREx | WS5-1/7/9, WS6-6 |
| Gaia en MAST | Catálogo/contexto Gaia DR3 solicitado por el texto, release explícito | WS3-10, WS5-4 |
| CSA NEOSSat | Contexto educativo y referencia de misión distinta | WS3-11, WS6-6 |
| CADC | Evaluar acceso a archivos de comparación y condiciones de uso | WS3-11 |
| Tutorial NEOSSat en GitHub | Referencia de extracción y visualización; revisar licencia antes de reutilizar código | WS3-11, WS6-6 |
| Dataset NEOSSat | Posible comparación futura, opcional y separada por misión | WS3-11 |

Ver [DATA.md §7](DATA.md#7-comprobación-de-los-enlaces-del-enunciado-2026-11-14) para resultados de acceso.
Poder leer una página no demuestra que consultas API, descargas FITS, CORS o cobertura funcionen.

## Extensiones propias (P2)

Detección/linking/scoring (WS2-3/4/5), JPL/SkyBoT y cruce de candidatos (WS3-1/2/8), distancia
(WS3-4), inyección-recuperación (WS2-6), shift-and-stack y Planeta X (WS2-9, WS3-6), reportes avanzados
(WS5-5/6), GIF/MP4 y composiciones adicionales. No son requisitos del texto aportado.
El 3D de catálogo de WS7 es P1 según VISION.md: cinco blancos y un ejemplo sintético, con fuentes y
verificación por valor. Las correcciones V4/V12/V13 están en PR #90 abierto. Contrato vigente 0.7.0.
Ver VISION_3D.md y tareas WS7. Estos modelos no cumplen por sí solos R02/R05,
no cuentan como imágenes NASA y no desplazan el recorrido por coordenadas ni las pruebas de variabilidad.

## Condiciones de entrega del PDF (S01–S10, P0)

| ID | Condición / fuente PDF | Responsable y tareas | Aceptación / estado |
|---|---|---|---|
| S01 | Ventana y zona horaria, págs. 2/12 | WS6-1b/9; WORKFLOW | Sede UP Buenos Aires confirmada por usuario; cierre 15/11/2026 23:59 ART; objetivo 21:00; evaluación local pendiente |
| S02 | Demo obligatoria, video <= 30 s o <= 7 slides con portada/intro, págs. 6/10/11 | WS6-5 | Archivo final medido, guion acorde; demo aún pendiente |
| S03 | Enlaces públicos sin login y hosting externo; JPG/PNG/GIF <= 10 MB, págs. 4/6/7/10 | WS4-4/6, WS6-3/5 | Proyecto, demo y materiales accesibles en incógnito; FortiGuard recomendado, no obligatorio |
| S04 | Inglés en formulario/materiales; video en otro idioma con subtítulos ingleses, págs. 10/12 | WS5-13, WS6-4/5/11 | README público/plantilla en inglés; revisar toda pieza final antes de publicar |
| S05 | Campos completos y Submit for Judging, no solo Save Progress, págs. 3/6–9/12 | WS6-4/9 | Plantilla alineada; envío y banner de confirmación pendientes |
| S06 | Al menos un dato/recurso NASA para Global Award, pág. 8 | WS1/WS3, WS6-6/8 | Citar recursos efectivamente usados; no confundir documentación con imágenes procesadas |
| S07 | Inventario de todo código/texto/imágenes/datos/herramientas y permisos, pág. 9 | WS6-6/10 | Listado completo y atribuciones revisados; inventario aún incompleto |
| S08 | Uso SI/IA declarado, marcas/metadata y límites de idea/marca NASA, pág. 8 | WS5-13, WS6-10 | AI_USAGE.md y ai-usage.json iniciados; completar origen/autoría y revisión de todos los aportes |
| S09 | Entrega pág. 12; evaluación págs. 3–4: 1–6 integrantes locales (Universal 2–6), Team Owner/misma sede/Members, sin waitlist ni altas tras cierre; revisión de medios y declaraciones | WS6-9/10 | Inscripción/medios pendientes; revisar guía, términos, privacidad, originalidad y referencias; elegibilidad final por organización |
| S10 | Evaluación págs. 5–7: Impact, Creativity, Validity, Relevance, Presentation, cada uno 1–5 | WS3-7, WS6-8/12 | JUDGING_REVIEW.md con evidencia y revisión pendiente; sin pesos/fórmula inventados ni notas oficiales autoadjudicadas |

La demo de entrega S02 es distinta de la animación interactiva R04. Cumplir una no sustituye la otra.
Datos de agencias asociadas están recomendados, no exigidos por la guía. Certificado: seguimiento opcional,
no condición para construir el producto. Ver protocolo operativo en SUBMISSION_GUIDE.md.

La integración central de datos NASA de **Relevance** va más allá de citar un recurso para S06.
R02/R03/R04 siguen P0: una secuencia sintética o un catálogo de extras no prueban el recorrido real.
La rúbrica incluye completitud/usabilidad en **Validity** y relato de demo/proyecto completo en **Presentation**.

## Proceso de premios: informativo, no requisito para terminar el MVP

Ver JUDGING_GUIDE.md: nominación oficial Local/Universal → Global Nominees → Global Finalists → comité
ejecutivo/Global Winners. Premios locales son independientes; Honorable Mentions no avanzan a Executive Judging.
Anuncios según PDF: 03/12/2026, 17/12/2026 y 26/01/2027. No hay hora/zona publicada ni garantía de avance.
Los diez premios son categorías del comité, no diez funcionalidades nuevas ni una autoinscripción del equipo.

## Condición para declarar el MVP cumplido

- [ ] R01–R04 funcionan de punta a punta con datos reales y pruebas de interfaz.
- [ ] Se realizaron y documentaron los cinco ensayos R05; resultados negativos se explican sin inventar señal.
- [ ] No se afirma una recuperación exitosa sin evidencia de posición, fecha, banda y calidad suficiente.
- [ ] Cada C01–C08 figura como implementado con evidencia o pendiente; las mejoras no se anuncian como hechas.
- [ ] Fuentes, créditos, límites y requisitos de entrega verificados constan en la publicación.
- [ ] S01–S10 revisados; demo/formulario completos y envío confirmado dentro del plazo de la sede.
- [ ] Revisión de los cinco criterios con evidencia real, responsables y brechas; no presentar autoevaluación como resultado del jurado.
