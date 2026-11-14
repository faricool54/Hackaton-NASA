# Equipo y asignaciones

Completar en el kickoff. Una persona por fila; cada una con su(s) agente(s).

**Local Event confirmado por el usuario (14/11/2026): Universidad de Palermo, Buenos Aires, Argentina.**
Zona: America/Argentina/Buenos_Aires (ART, UTC-3). Cierre según PDF: 15/11/2026 23:59 ART;
objetivo interno: 21:00 ART. Horario de evaluación local y aceptación de integrantes: pendientes.
**Responsable de edición/envío y backup:** _nombres_. Coordinar el lock y verificar Submit for Judging.
Según la guía de evaluación, este Local Event admite **1–6 integrantes** (Universal 2–6): todos aceptados
en la misma sede, incluido Team Owner, sin waitlist y visibles en Members. Verificar antes del cierre;
no se agregan personas después. Workstreams y agentes no son integrantes adicionales.

| WS | Tema | Persona | Agente(s) | Perfil ideal |
|---|---|---|---|---|
| WS1 | Acceso a datos SPHEREx | _nombre_ | Claude / Codex | Python, APIs, paciencia con servicios lentos |
| WS2 | Grilla, render y comparación; detección opcional | _nombre_ | | Python + numpy, procesamiento de imágenes |
| WS3 | Cinco blancos, astrometría, variables, espectros y contexto | _nombre_ | | el/la más "astro" del grupo |
| WS4 | Backend + integración + CI | _nombre_ | | backend, devops |
| WS5 | Frontend | _nombre_ | | React/TS, ojo para UX |
| WS6 | Producto, narrativa, deploy, entrega | _nombre_ | | comunicación, diseño, video |
| WS7 | Galería 3D opcional, modelos y procedencia | _nombre/rol compartido_ | | gráficos y datos; P2 después del recorrido obligatorio |

**Coordinador/a de integración:** _nombre_ (cuida `main`, el contrato y el cronograma; suele ser WS4).

### Si son 5 personas
Los siete workstreams son **roles**, no siete integrantes. Repartir WS7 y WS6 entre las personas del equipo;
se mantiene el máximo de seis miembros registrados. La galería 3D no exige otra persona ni retrasa el MVP.
- WS6 se reparte: **deploy** → WS4; **textos/About/pitch/video** → WS5 + quien termine antes (normalmente WS3 en
  la recta final). El formulario de entrega lo completa el/la coordinador/a.

### Dependencias entre WS (quién espera a quién)
- WS2 necesita frames reales de WS1 para pasar del demo a lo real (mientras tanto: trabaja sobre `data/demo` y
  sobre cutouts que baje a mano desde S3/IRSA).
- WS3 comienza por identidades/coordenadas/épocas de los cinco blancos y el protocolo de variables;
  no necesita candidatos automáticos. Para evidencia real necesita cobertura de WS1 y grilla/render de WS2.
- WS4/WS5 pueden desarrollar con el demo; el cierre de R03 requiere integrar solicitud RA/Dec → job → campo.
  El backend de construcción es P0; el frontend estático solo sirve campos curados.
- WS6 necesita la URL de deploy (WS4) y capturas reales (WS5) hacia H+24.
- WS6 lidera demo obligatoria (<= 30 s o <= 7 slides), formulario en inglés, inventario de fuentes/SI,
  revisión de medios/equipo y envío confirmado. El PDF define una ventana menor que 48 h: ver WORKFLOW.
- WS3/WS5/WS6 revisan evidencia de Impact/Creativity/Validity/Relevance/Presentation con JUDGING_REVIEW.md.
  Reservar tiempo de comunicación/diseño; cada criterio es 1–5, sin pesos oficiales publicados.

Orden compartido: I1 imágenes reales → I2 coordenadas/público → I3 cinco ensayos → I4 consideraciones
→ I5 análisis avanzado. Ninguna integración JPL/Planeta X bloquea I1–I3. Ver `docs/REQUIREMENTS.md`.
La ampliación 3D está integrada como P2; su verificación/catálogo tiene dueño WS7, sin bloquear datos reales.
