# Revisión interna con la rúbrica 2026

Fuente: [Judging & Awards Guide](<../references/NASA Space Apps Challenge Judging & Awards Guide.pdf>),
págs. 5–7; síntesis en [JUDGING_GUIDE.md](../JUDGING_GUIDE.md). Responsable: WS6, con WS3/WS5.
**No es una evaluación oficial.** Cada criterio admite 1–5; no se publican pesos ni fórmula total.
No rellenar notas sin revisión humana y evidencia. La confianza 0–1 de un candidato no se usa aquí.

Revisor/a: pendiente. Fecha: pendiente. Versión/commit/productos revisados: pendiente.

| Criterio | Evidencia necesaria | Evidencia / brecha actual | Responsable | Nota interna (1–5) |
|---|---|---|---|---|
| Impact | Usuario/problema concretos, beneficio observado o hipótesis declarada | Beneficio educativo propuesto; tres pruebas con usuarios de WS6-7 pendientes | WS5/WS6 | Sin evaluar |
| Creativity | Inspiraciones acreditadas y mejora propia significativa, demostrable | Referencias WiseView/IRSA y galería 3D integrada; demostrar aporte propio sin atribuir verificación a los modelos | WS3/WS5/WS6/WS7 | Sin evaluar |
| Validity | Funcionalidad real, base científica, usabilidad, pruebas y límites | App pública, jobs reales, cinco registros FITS offline y aceptación técnica #95/#96 disponibles; revisión humana R05 y prueba con usuarios pendientes | WS1/WS2/WS3/WS4/WS5 | Sin evaluar |
| Relevance | R01–R05 e integración central de observaciones NASA con procedencia | SPHEREx DR1/QR3 impulsa RA/Dec → secuencia, espectros/comparaciones y curvas; verificar el relato y las limitaciones con los registros | WS1/WS4/WS5/WS6 | Sin evaluar |
| Presentation | Formulario/demo completos, inglés, claridad y enlaces anónimos | Borradores y guion; faltan demo final, links y revisión de la entrega | WS5/WS6 | Sin evaluar |

Actualizar evidencia con rutas/URLs reales y fecha; un esquema o test con mocks no equivale a haber
consultado el archivo y validado observaciones. Un ensayo sin señal/cobertura se documenta sin convertirlo
en recuperación positiva ni ocultar el límite del producto.
La galería 3D usa contexto de catálogo con fuentes/estados de verificación por valor; PR #90 sigue abierto.
Su presencia no completa R05 ni representa imágenes SPHEREx. Las observaciones reales del visor sí están
integradas. Esta actualización de estado no realiza una evaluación ni asigna puntuaciones.

## Preguntas para la revisión

- **Impact:** ¿quién puede usarlo y qué dificultad resuelve? ¿Qué observaron usuarios ajenos al equipo?
  ¿Separamos beneficio esperado de alcance medido?
- **Creativity:** ¿qué aprendimos de WiseView/IRSA y qué mejora agregamos? ¿Podemos demostrarla sin
  llamar descubrimiento a una simulación ni atribuirnos herramientas ajenas?
- **Validity:** ¿otra persona reproduce una secuencia real? ¿Fechas, WCS, bandas, calidad y cinco ensayos
  tienen fuente? ¿Fallos, incertidumbres y etapas pendientes son visibles?
- **Relevance:** ¿RA/Dec devuelve imágenes reales de esa región y permite comparar fechas? ¿Los datos
  NASA sostienen el funcionamiento o aparecen únicamente como enlace/crédito?
- **Presentation:** ¿se entienden reto, solución e importancia en formulario **y** demo? ¿Cumple 30 s/7
  slides, inglés/subtítulos y acceso público? ¿Texto y pantalla cuentan la misma historia?

## Decisiones antes de congelar

- [ ] Priorizar bloqueos de R01–R05 y evidencia real antes de extras P1/P2.
- [ ] Registrar notas solo con revisor/a, versión, evidencia y explicación; no crear total o pesos.
- [ ] Reservar relato/diseño aunque haya buen código; revisar demo y proyecto completo.
- [ ] Corregir afirmaciones sin evidencia o que excedan lo implementado.
- [ ] Pasar S01–S10, incluida inscripción 1–6 local, en CHECKLIST.md.
- [ ] Separar autoevaluación de nominación/premios; la elegibilidad final corresponde a la organización.

Pendiente de primera revisión por el equipo. Esta plantilla no completa WS6-12 ni asigna notas a Errante.
