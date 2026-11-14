# WS6 · Entrega: reglas, textos, video y formulario

> Prioridades y alcance: manda [`docs/PLAN.md`](../docs/PLAN.md). Leyenda: ✅ verificado 2026-11-14 ·
> 📄 según documentación · ❓ abierto.

## Objetivo

Que el proyecto sea **elegible** y se entienda: formulario completo en inglés, video ≤ 30 s (deck ≤ 7 slides de
respaldo), declaración de SI honesta, sin branding NASA, links públicos sin login, y **"Submit for Judging" el
dom 20:00** (se puede reenviar hasta las 23:59).

**Quién:** con 5 personas no hay dueño exclusivo ([PLAN §4](../docs/PLAN.md)): textos y video entre WS3 y WS5 al
final; el formulario lo carga quien coordina. **La idea, el nombre, el tagline, los diferenciadores y el texto del
guion los escribe el equipo** (regla de SI): ni este archivo ni un agente los proponen.

## Tus rutas

| WS | Rutas (dueño) |
|---|---|
| **WS6** Entrega | `docs/submission/**`, `docs/CHALLENGE.md`, sección "Use of SI" y créditos del README |

Tabla completa: [`tasks/README.md`](README.md). Los textos de la web (About y hero, en `frontend/`) los edita WS5
con el texto que le pases. Marcá casillas solo en este archivo.

## Recibís / Entregás

| Recibís | De | Cuándo |
|---|---|---|
| Idea, nombre, tagline y diferenciadores escritos por el equipo | kickoff ([`docs/KICKOFF.md`](../docs/KICKOFF.md)) | sáb 12:30 |
| Respuestas del/la Local Lead (zona horaria del cierre, presentación local) | coordinación | sáb |
| Revisión científica de afirmaciones y números | WS3 | antes del freeze |
| URLs públicas (frontend y backend) | WS4 | dom 12:00 |
| Versión congelada de la app con datos reales; capturas | WS5 | dom 17:00 |

**Entregás:** `PROJECT.md` sin `TODO`, guion de `PITCH.md` escrito por el equipo, video ≤ 30 s con subtítulos en
inglés, deck ≤ 7 slides, sección "Use of SI" y créditos del README confirmados, `CHECKLIST.md` tildado, el envío.

## Leé primero

[`docs/CHALLENGE.md`](../docs/CHALLENGE.md) §3 (reglas de entrega verificadas) ·
[`docs/submission/CHECKLIST.md`](../docs/submission/CHECKLIST.md) · [`PITCH.md`](../docs/submission/PITCH.md) ·
[`PROJECT.md`](../docs/submission/PROJECT.md) · [`docs/KICKOFF.md`](../docs/KICKOFF.md) ·
[`docs/PLAN.md`](../docs/PLAN.md) §1 y §5 · [`docs/SCIENCE.md`](../docs/SCIENCE.md) §4 ·
[`README.md`](../README.md) ("Use of SI" y créditos) · [`docs/REVIEW-2026-11-14.md`](../docs/REVIEW-2026-11-14.md)
§4 Entrega y §5.4.

## Estado actual

**Reglas ✅** (guía oficial de entrega, FAQ y guía de jurado, leídas el 2026-11-14; detalle en CHALLENGE §3):
- Cierre: **dom 15/11 23:59 en la zona horaria del Local Event** (❓ confirmar la zona con el/la Local Lead). Se
  puede editar y reenviar hasta el cierre; se juzga el último envío guardado.
- Demo: **video ≤ 30 s o deck ≤ 7 slides** (incluye título e intro); si se excede, el proyecto queda fuera del
  Global Judging. Video en otro idioma → **subtítulos en inglés obligatorios**. Estructura sugerida: [0:00]
  equipo · [0:02] reto · [0:05] nombre + tagline · [0:10] idea/demo · [0:20–0:30] futuro.
- Formulario, todo en inglés: Project Name, High-Level Project Summary, Link to Project Demo, Link to Final
  Project, Detailed Project Description, Use of Super Intelligence (SI), NASA Data, Space Agency Partner Data and
  Other References, + casillas "Terms and Conditions" y "Confirm All Work is Original".
- Links sin password, permiso ni registro. Para premio global, ≥ 1 dato o recurso NASA. Nadie menor de 18 en
  imagen o voz. Máximo 6 integrantes.
- SI: permitida, pero **no para idear cómo resolver el reto**; código y datos con SI → reconocerlo en texto
  descriptivo y metadata; imágenes y videos con SI → marca de agua visible; prohibido usar o modificar branding
  NASA (logos, banderas, identificadores de misión). Los jueces no ven la respuesta de SI, pero sí lo que hay
  dentro del proyecto.
- Jurado: 5 criterios de 1 a 5: Impact, Creativity, Validity, Relevance (que el proyecto responda de forma
  completa y directa al reto y use datos NASA como parte central) y Presentation.

**Archivos (estructura lista, contenido pendiente):**
- `CHECKLIST.md`: checklist por hito (kickoff → submit) con responsables y preguntas al/la Local Lead; nada tildado.
- `PITCH.md`: reglas, tabla del video de 30 s y plan del deck de 7 slides; todo el texto es `TODO(team)`.
- `PROJECT.md`: un encabezado por campo del formulario, con hechos técnicos tomados de PLAN.md y `TODO(team)`.
- README: sección "Use of SI / AI disclosure" y créditos de datos en borrador, con `TODO(team)`.

**Repo ✅:** privado (anónimo → 404); falta `LICENSE`; no hay secretos trackeados (`git grep` de
key/secret/token/password vacío); no hay logos. El esqueleto, el nombre provisorio y el plan los generó Claude
(commit inicial a nombre de "Claude"): por eso la idea y el nombre se reescriben en el kickoff. Hay ~15 repos
públicos de otros equipos para este reto ✅: no copiar código ajeno.

## Tareas

- [ ] **WS6-1 (P0) Kickoff → idea, nombre y tagline del equipo** (sáb 12:00–12:30). Las personas discuten y
  escriben con sus palabras (en inglés para la entrega) la idea, el nombre (mantener o cambiar el provisorio), el
  tagline y qué los diferencia; queda en `docs/KICKOFF.md` y de ahí pasa a `PROJECT.md`, README y hero (vía WS5).
  Un agente puede corregir ortografía o traducir, no idear.
  *Acepta:* textos escritos por personas del equipo; si un agente tradujo o corrigió, queda declarado en "Use of SI".
- [ ] **WS6-2 (P0) `CHECKLIST.md` al día.** Las preguntas al/la Local Lead (zona horaria del cierre,
  presentación o juzgamiento local, requisitos de la sede) respondidas y anotadas; cada casilla tildada en su hito.
  *Acepta:* las casillas del kickoff tildadas el sábado; las preguntas sin respuesta quedan ❓ con hora de reintento.
- [ ] **WS6-3 (P0) "Use of SI" confirmada por el equipo** (README + campo del formulario en `PROJECT.md`):
  herramientas que usó realmente cada persona y para qué, cómo decidió el equipo la idea y el nombre, imágenes o
  videos generados con SI (si los hay, con marca de agua). *Acepta:* sin `TODO(team)` en ambas secciones; cada
  integrante leyó y aprobó el texto.
- [ ] **WS6-4 (P0) `PROJECT.md` completo** (en inglés). El equipo escribe Name, Summary y la parte narrativa de
  la descripción; los hechos técnicos se actualizan a lo que realmente está desplegado el domingo (P1 solo si
  llegaron). NASA Data y Partner/Other References: **solo lo usado** (SPHEREx L2 DR1 + QR3 vía IRSA ✅; el resto,
  si se usó). Límites honestos: movimientos de 1–2 px en ~1–1,4 años de datos, variables comparadas por temporada, nada de
  "discovered". *Acepta:* sin `TODO`; WS3 revisó las afirmaciones científicas y los números (todos medidos).
- [ ] **WS6-5 (P0) Video ≤ 30 s** con la estructura de `PITCH.md`: el equipo escribe el texto de cada bloque;
  solo datos reales; subtítulos en inglés; sin branding NASA; créditos en texto. Protagonista según el spike de
  WS2/WS3: WISE 0855 en D5/D6 si se ve bien, si no Barnard (plan B). Grabar dom 17:00–19:30 sobre la URL pública.
  *Acepta:* duración ≤ 30,0 s medida en el archivo final; subtítulos en inglés; link público que abre en incógnito.
- [ ] **WS6-6 (P0) Deck ≤ 7 slides de respaldo** (plan de `PITCH.md`), en inglés, con capturas reales.
  *Acepta:* ≤ 7 slides contando título e intro, exportado con link público.
- [ ] **WS6-7 (P0) Auditoría de branding NASA**: repo, web (con WS5: favicon, encabezados), video y deck sin
  logos, banderas, parches ni identificadores de misión; créditos solo en texto. *Acepta:* casilla tildada en
  `CHECKLIST.md` con quién lo revisó.
- [ ] **WS6-8 (P0) Links públicos.** `LICENSE` (la licencia la elige el equipo). Repo público (lo hace quien sea
  dueño del repo, después de volver a revisar que no haya secretos) y/o URL del sitio como "Link to Final
  Project"; si el repo va como link, README entendible en inglés (ver `CHECKLIST.md`). *Acepta:* los links de demo
  y de proyecto abren en incógnito y en el celular sin login.
- [ ] **WS6-9 (P0) Enviar el dom 20:00** siguiendo la sección "Submit for Judging" de `CHECKLIST.md` (casillas
  Terms y Original, banner de confirmación); volver a abrir los links en incógnito después; reenviar antes de las
  23:59 solo si hay una mejora real. *Acepta:* captura del banner de confirmación en el chat del equipo.
- [ ] **WS6-10 (P1) Prueba con 3 personas ajenas** (2 min cada una, sin explicarles nada): dónde se traban, qué no
  entienden. *Acepta:* notas en `docs/submission/USER-TESTS.md` y un issue para WS5 por cada problema.
- [ ] **WS6-11 (P1) Textos de About y créditos para WS5** (en inglés): créditos de cada fuente con su texto de
  reconocimiento oficial (buscarlo en la web de cada una, no inventarlo), declaración corta de SI y límites
  honestos. *Acepta:* WS3 los revisó y WS5 los pegó.

## DROP

- Guion largo (70–100 s) con bloques de "candidato no confirmado", "página de límites" y "a qué distancia estaría
  un Planeta X".
- "Results" con objetos recuperados y límites de detección: no hay detección automática.
- Logo propio: no suma ante el jurado; si se hiciera con SI necesitaría marca de agua visible.
- Deploy (es de WS4).

## Gotchas

- El formulario dice **"Use of Super Intelligence (SI)"**, no "AI".
- La hora de cierre es la del **Local Event**, no la de cada integrante (❓ zona).
- Un video o PDF que pide login (Drive privado, etc.) invalida el link: probá siempre en incógnito.
- Branding NASA incluye el logo y el parche de SPHEREx. Las imágenes SPHEREx que muestra nuestra herramienta van
  con créditos en texto.
- Nada sintético en el video ni en las capturas; si aparece, con el badge visible.
- Lenguaje: "unconfirmed" ≠ "discovery". El Planeta X es la motivación narrativa (título del reto), no un resultado.
- Si se habla en español en el video, los subtítulos en inglés son obligatorios.
- Lo que haya dentro del repo, del video y del deck tiene que ser coherente con la declaración de SI.
- `TODO(team)` = lo escribe una persona. Un agente que vea ese marcador lo deja como está.

## Dependencias

- **Ya:** WS6-1 (kickoff), WS6-2, WS6-3 y la parte de WS6-4 que no depende de la app (Name, Summary, SI).
- **Dom 12:00** (URLs de WS4) → WS6-8 y prueba de links. **Dom 17:00** (freeze) → grabación (WS6-5) y deck (WS6-6).
- Si el deploy falla: grabar con la versión local sobre golden fields reales y usar el repo público como "Link to
  Final Project".

## Prompt de arranque

> Sos el agente de WS6 (entrega) del repo de NASA Space Apps 2026, reto "Planet X and SPHEREx". Leé `AGENTS.md`,
> `docs/PLAN.md`, `docs/CONTRACT.md`, `docs/CHALLENGE.md` §3, `docs/KICKOFF.md` y
> `tasks/WS6-product-submission.md`. Trabajá SOLO en `docs/submission/`, `docs/CHALLENGE.md` y las secciones
> "Use of SI" y créditos del `README.md`. Regla de SI: NO propongas ni completes idea, nombre, tagline,
> diferenciadores ni texto del guion; dejá cada `TODO(team)` como está. Podés: corregir ortografía o traducir
> texto que escribió el equipo (y avisarme para declararlo), actualizar los hechos técnicos de `PROJECT.md` a lo
> que realmente está desplegado, y verificar que `CHECKLIST.md` cubra las reglas de `CHALLENGE.md` §3. Sin
> números que no estén medidos y nada de "discovered". Si revisás links, abrilos en el navegador en incógnito, en
> desktop y en el celular. Corré `python scripts/dev.py check` (Windows: `py scripts/dev.py check`), mostrame el
> diff antes de commitear y commiteá como `ws6: verbo + qué` con el trailer `Co-Authored-By:` del agente.
