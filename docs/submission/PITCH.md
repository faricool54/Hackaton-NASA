# Demo: video de 30 s (plan A) y deck de 7 slides (plan B)

> **Dueño:** WS6 (al final lo arman WS3 y WS5) · **Revisión científica:** WS3. Se graba el **dom 17:00–19:30**,
> después del feature freeze ([`../PLAN.md`](../PLAN.md) §5).
> Reglas verificadas el 2026-11-14 en la
> [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) (detalle en
> [`../CHALLENGE.md`](../CHALLENGE.md) §3.4–3.5).
> **El texto del guion lo escribe el equipo con sus palabras** (regla de SI): acá solo hay estructura, reglas y
> notas técnicas. Los huecos van en inglés, o con subtítulos en inglés.

## Reglas que no se negocian

- **≤ 30 segundos**, títulos y créditos incluidos (o deck de **≤ 7 slides**, título e intro incluidos). Si se
  pasan, quedan **fuera de Global Judging**.
- Si se habla en otro idioma, **subtítulos en inglés** obligatorios. El deck va todo en inglés.
- **Solo datos reales** de SPHEREx en pantalla. Nada del demo sintético. Nada de "descubrimos".
- **Sin branding NASA**: ni logo NASA, ni banderas, ni parche o logo de SPHEREx, ni identificadores de misión.
  Los créditos van en texto ("SPHEREx data: NASA/JPL-Caltech/IPAC via IRSA").
- Si algo de la imagen o del video lo generó una SI (fondo, ícono, ilustración, animación), lleva **marca de
  agua visible**. Si la voz o la música las generó una SI, se declara en la descripción y en la metadata del
  video.
- **Nadie menor de 18 años** en imagen, video, voz ni semejanza.
- Link público, sin login ni permisos. Probarlo en una ventana de incógnito.

## Plan A · Video ≤ 30 s (estructura oficial)

| Tiempo | Qué pide la guía | Texto (EN o subtitulado en EN) | Qué se ve |
|---|---|---|---|
| **[0:00]** | quiénes son: nombre y nombre del equipo | TODO(team) | TODO |
| **[0:02]** | qué reto abordan y qué los inspiró | TODO(team) | TODO |
| **[0:05]** | nombre del proyecto y tagline | TODO(team) | TODO |
| **[0:10]** | la idea: cómo funciona, imágenes o prototipo, experiencia de uso, y cómo los datos abiertos de NASA (y de agencias socias, si se usan) la hacen posible | TODO(team) | TODO |
| **[0:20–0:30]** | el futuro: qué puede hacer la solución por la gente y el mundo | TODO(team) | TODO |

- [ ] Duración total medida: TODO s (≤ 30)
- [ ] Subtítulos en inglés (archivo `.srt` o quemados en el video): TODO
- [ ] Link público: TODO

### Tomas de pantalla que tienen sentido técnicamente (referencia, sin guion)

Elegir según lo que funcione con datos reales a las 17:00:

- **Entrada de coordenadas:** escribir RA/Dec o tocar uno de los 5 objetivos; la URL cambia a
  `?ra=…&dec=…` (muestra el objetivo central y la URL embebible).
- **Video por temporada:** coadds por (temporada × detector) reproduciéndose, con zoom pixelado, retícula y la
  posición predicha. Los movimientos son de **1–2 píxeles** (Barnard 1.86 px, WISE 0855 1.36 px, Eps Ind B
  1.10 px): sin zoom no se ve nada.
- **Resta de épocas:** temporada A − temporada B. Un objeto con movimiento propio deja un par positivo/negativo.
- **Espectro** en una posición (solo si llega el P1 `/api/photometry`).
- **Variable** (RW Aur o R Dra): coadds o espectros por temporada. Es INFERIDO que se vea bien: confirmarlo antes
  con datos.
- **Protagonista:** WISE 0855 solo si el spike medido en D5/D6 da bien; si no, **Barnard** (plan B del PLAN).
- Embebido en otra página con `embed=1` (si llega).

## Plan B · Deck ≤ 7 slides (en inglés)

La guía pide que el deck incluya: nombre del equipo, nombres de los integrantes, el reto elegido, una imagen del
proyecto, la experiencia de usuario y cómo los datos abiertos de NASA y de las agencias hacen posible la
solución. Letra legible y pocas palabras por slide.

| # | Slide | Contenido |
|---|---|---|
| 1 | Título | nombre del proyecto + tagline + nombre del equipo — TODO(team) |
| 2 | Equipo y reto | nombres de los integrantes + "Planet X and SPHEREx" — TODO(team) |
| 3 | El problema | con las palabras del equipo — TODO(team) |
| 4 | Experiencia de usuario | captura real: coordenadas → video — TODO |
| 5 | Cómo funciona + datos | SPHEREx (NASA/JPL-Caltech/IPAC vía IRSA); socios solo si se usan — TODO |
| 6 | Resultados en los objetivos oficiales | capturas reales y números **medidos** — TODO |
| 7 | Futuro + links | sitio, repo, video — TODO(team) |

- [ ] Exportado a PDF o Google Slides con link público. Contar las slides: **≤ 7**.

## Ensayo

- [ ] Cronometrado 2 veces (≤ 30 s) · [ ] lo vio alguien ajeno al equipo y entendió el reto ·
      [ ] WS3 revisó los números · [ ] checklist de [`CHECKLIST.md`](CHECKLIST.md) completo.
