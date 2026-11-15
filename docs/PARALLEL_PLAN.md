# Plan paralelo y estado del proyecto — 15/11/2026, 03:30 ART

Guía viva del equipo: qué está hecho, qué falta, quién lo toma y en qué orden. Relevado sobre `main` `c333390`
(#72), sin PRs abiertos. No acredita validaciones científicas ni publicación pública: la evidencia está en cada PR y
en [`validation/`](validation/). Esta página es de coordinación: si algo cambió, avisá en el chat o abrí un PR
`chore:`.

Visión: [VISION.md](VISION.md) · reglas: [COLLABORATION.md](COLLABORATION.md) · responsables: [TEAM.md](TEAM.md) ·
integración WS4/WS5: [WS4_INTEGRATION.md](WS4_INTEGRATION.md) · protocolo R05: [VALIDATION.md](VALIDATION.md) ·
entrega: [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md) y [submission/CHECKLIST.md](submission/CHECKLIST.md).

**Reloj (ART, UTC-3):** freeze **17:00** · envío interno **21:00** · cierre del portal **23:59** (sede UP Buenos
Aires). Después del freeze solo entran textos, deploy y entrega. Save Progress no es envío.

**Ficha del objeto: hecha (15/11, ~06:00 ART).** El contexto de catálogo de WS3 ya llega al panel del click: contrato `ObjectContextResponse` 0.5.0 (#73), adaptador `to_response` de WS3 (#74), tarjeta `ObjectCard` en «Explore a position» (WS5, #75) y `GET /api/object` (WS4, #76). Los atajos y la búsqueda por nombre consultan por nombre; el click y las coordenadas, por posición. Un servicio caído nunca se muestra como «no catalogado». rpccp: revisá #76 cuando puedas (está en tu carpeta).

## 1. Estado en una mirada

Leyenda: **hecho** · **parcial** · **falta** · **en curso**.

| Parte de la visión | Estado | Qué hay y qué falta | PRs | Quién |
|---|---|---|---|---|
| Mapa SPHEREx DR1: Aladin Lite 3.8.2 + HiPS de IRSA, selector propio de 102 planos, capa AllWISE | parcial | Funciona, con un bug intermitente de mapa negro (§5). Falta la capa Gaia (C05) | #34 | rpccp (WS5 sin dueño) |
| Búsqueda por nombre (Sesame/CfA) y por RA/Dec; presets de los cinco | hecho con API | En modo estático no hay búsqueda (`frontend/src/api/client.ts:113`, `:117`) | #11, #32, #33, #34 | BenjaminPondal, rpccp |
| Coordenadas en la URL (C06) | parcial | `?ra=&dec=&fov=&detector=&job=` (`frontend/src/api/jobs.ts:22-41`). Falta el modo compacto/iframe | #34 | rpccp |
| Click → job → hasta 40 frames reales → video | hecho en local con API | ~20-30 s por campo. Requiere `ERRANTE_ENABLE_JOBS=1` y `?mode=api`. En un deploy estático el click no construye nada | #18, #32, #33, #34 (datos: #16, #21-#23, #35) | rpccp, faricool54, V0id47 |
| Blink: play, paso, velocidad, fecha · D · λ · release; B/W, falso color por detectores y J/H/K | hecho | Faltan zoom, retícula y posición del blanco, y flags/`valid_fraction` por frame (C07) | #15, #39, #40, #41 | BenjaminPondal, V0id47 |
| Cinco campos reales curados (40 frames cada uno) sin backend | hecho | `?mode=static&dataset=real`. `data/products` pesa 2,4 MB | #17, #41 | V0id47 |
| Espectro de un punto (cubo DR1 o fotometría forzada L2) | parcial | Panel plegado y manual. L2 mide una posición fija, sin movimiento propio (`backend/errante_api/science_ops.py:184`) | #31, #42, #45, #53, #54, #55 | V0id47, faricool54, rpccp |
| Comparación de temporadas (medias ponderadas y restas escaladas) | hecho con API | Sin backend no se ve (`frontend/src/components/FieldComparisons.tsx:37`). Los campos no traen comparaciones precomputadas | #19, #37, #69, #53-#55 | V0id47, rpccp |
| Ficha del objeto: SIMBAD, Gaia DR3, VSX, planetas confirmados, 2MASS/AllWISE, como Facts con fuente | hecho | Tarjeta en el panel del click (por nombre o por posición) con `GET /api/object`; contexto de catálogo, no mediciones SPHEREx | #58, #73–#76 | faricool54 + Claude (WS3; contrato, WS4 y WS5 con aviso); rpccp revisa #76 |
| Curva de luz de R Dra y RW Aur | parcial | Solo pipeline y CLI (`errante lightcurve`). Sin API ni UI | #59 | faricool54 |
| 3D de los cinco blancos | parcial | Procedural desde valores de catálogo verificados, reloj *Dataset time*, publicado en el dataset real. No sale de mediciones SPHEREx ni de `physical_parameters`. No hay 3D para un click arbitrario. Una fila «bloquea» abierta (§6) | #9, #47, #64; revisión #65 | DankoLiv (WS7 de facto), faricool54 |
| Validación R05 de los cinco | hecho, con salvedades | Cinco registros `success`. Falta la revisión humana. Analizan el build de #17, no el de #41. Los scripts originales no están versionados. El paso 6 (URL pública) sigue pendiente | #36, #46, #62, #66, #70, #71 | faricool54 + Claude, V0id47 |
| Deploy público | falta | Repo privado. Pages sin habilitar (`gh api repos/faricool54/Hackaton-NASA/pages` → 404). No hay backend hospedado | — | WS4 (rpccp) + WS6 |
| Materiales de entrega (About, README, PROJECT, demo, registro de IA) | falta | Dicen que no hay datos reales. La demo no está grabada | — | WS6 (sin dueño) |
| Objetos conocidos (SkyBoT/JPL) | falta (P2) | `/api/known-objects` → 501 (`backend/errante_api/live_service.py:167-168`) | — | WS3 |
| Detección automática y Planeta X | falta (P2) | Stubs con `NotImplementedError` | — | WS2, WS3, WS7 |

## 2. Falta para la visión

Esfuerzo en horas aproximadas para una persona con su agente. «Sin dueño» significa que nadie reservó ese
workstream en [TEAM.md](TEAM.md): reservalo antes de arrancar (§9). Citá el ID (V1, A3…) en tu PR.

### P0 (antes del freeze)

| ID | Tarea | Dueño | Esfuerzo | Depende de | Dónde | Estado |
|---|---|---|---|---|---|---|
| V1 | Arreglar el mapa negro: aplicar el plano inicial cuando la capa esté lista (o reintentar `setFrequency` hasta que cargue un tile). Probar recargando varias veces | WS5 (sin dueño) | 0,5 h | — | `frontend/public/sky-map.html:25`, `:28`, `:34`; `frontend/src/components/ExplorerMap.tsx:31-33` | falta |
| V2 | Que el recorrido mapa → click → video se pueda probar en la URL pública | WS4 (rpccp) + WS6 | 1,5-4 h | D1, D2 | `.github/workflows/pages.yml:18`, `:38-39`; `frontend/src/api/client.ts:35-37`; `backend/Dockerfile:11-12` | falta |
| V3 | Retícula y posición predicha del blanco sobre el video, y zoom pixelado. Barnard se corre ~1,7 px en todo el baseline ([registro](validation/barnards-star.md)): sin retícula no se ve. Rotular «predicted from catalog, not a measurement» | WS5 (sin dueño), con la matemática de WS7 | 3 h | D5 | `frontend/src/components/BlinkViewer.tsx:266` (TODO); `field.json` ya trae `grid.wcs`; predicción con paralaje en `frontend/src/three/skyTrack.ts`; movimientos propios en los comentarios de `pipeline/errante/config/fields.toml` (para un click arbitrario, de la ficha del objeto, V6); `known.json` está vacío en los cinco campos | falta |
| V4 | Fila «bloquea» del 3D: la ficha de RW Aur cita como «SPHEREx measured» magnitudes D5/D6 de núcleos saturados | WS7 (de facto DankoLiv, #47) | 0,25 h | — | `frontend/src/three/astro.ts:1150-1151`; texto listo en [SCIENCE.md](SCIENCE.md) (fila de `astro.ts:1150-1151`) | falta |
| V5 | Cerrar R05: revisión humana de los cinco registros (E7) y párrafos del chequeo de productos publicados de #70 en cada registro (A8) | coordinación (sin reserva; registros de faricool54) + una persona que revise | 2 h | — | [`validation/`](validation/) | falta |

### P1

| ID | Tarea | Dueño | Esfuerzo | Depende de | Dónde | Estado |
|---|---|---|---|---|---|---|
| V6 | Ficha del objeto en el panel del click. Si un servicio externo se cae, no bloquea el video | faricool54 + Claude; revisión posterior de rpccp (WS4) en #76 | — | contrato 0.5.0 | #73 (contrato), #74 (WS3), #75 (WS5), #76 (WS4) | hecho |
| V7 | Panel del click con tres vistas (Tiempo / Espectro / 3D). Abrir el panel al hacer click y lanzar el espectro del cubo (rápido) solo | WS5 (sin dueño) | 2 h | V6 | `frontend/src/components/SkyExplorer.tsx:168-171`; `PositionSpectrum.tsx:46` (`<details>` cerrado) y `:72` | falta |
| V8 | Calidad por frame (C07): `valid_fraction` y origen del frame en el blink. Un flag ausente no es «limpio». Las fracciones de flags necesitan contrato | WS5 (WS5-10) + WS2 (WS2-11) + contrato (WS4-10) | 1,5 h solo UI; 5 h con flags | contrato, para los flags | `BlinkViewer.tsx:179-180`; `pipeline/errante/models.py:97` | falta |
| V9 | Espectro L2 con movimiento propio: `pm_ra`/`pm_dec`/época opcionales en `SpectrumRequest`, pasados a la fotometría. El pipeline ya lo sabe hacer (`photometry.propagate`, CLI `errante spectrum --pm-ra --pm-dec`, y `position_spectrum` de WS3); falta el contrato y la API | contrato + WS4 + WS3 | 2 h | V6 (pm del objeto) | `models.py:511`; `backend/errante_api/science_ops.py:184`; `pipeline/errante/imaging/photometry.py:319`; `pipeline/errante/science/spectra.py:380` | falta |
| V10 | Curva de luz de R Dra y RW Aur en la app. Lo más barato: precomputarla con la CLI y publicarla como producto estático (necesita un modelo de contrato) | WS3 + contrato + WS4 + WS5 | 3-4 h | D6 | `pipeline/errante/science/variability.py:1098`; `pipeline/errante/cli.py:538` | falta |
| V11 | Comparaciones visibles sin backend: `ComparisonResponse` precomputado o los stills/GIF de #71 | WS2 + WS4 | 2 h | D1 | `data/products/fields/*/` (sin comparaciones) | falta |
| V12 | Las 5 filas «importante» de la revisión del 3D: máximos medidos de R Dra, radio de R Dra fijo por defecto, «look at the frames» en RW Aur, saturación de Barnard y S/N de WISE 0855 en el panel del cielo | WS7 (de facto DankoLiv) | 1,5 h | D3 | [SCIENCE.md](SCIENCE.md), tabla del 3D (filas de `ephemerides.ts`, `sceneLayout.ts`, `skyTrack.ts`) | falta |
| V13 | 3D alimentado por `physical_parameters` de WS3 (Teff, radio, distancia como Facts con fuente), rotulado «catalog, not measured by SPHEREx». Después: color, radio y pulsación desde SPHEREx (WS7-8) | WS7 + WS3 | 2 h el mínimo; 6 h completo | V6, V18 | `pipeline/errante/systems/catalog.py`; [VISION_3D.md](VISION_3D.md) («Diferencias con VISION.md que siguen abiertas») | falta |
| V14 | 3D para un click arbitrario (cualquier estrella con Gaia). Sin dato: «unknown», nada inventado | WS7 + WS3 | 5 h | V6, V13 | `frontend/src/pages/FieldPage.tsx:38` (hoy solo enlaza si `manifest.systems` tiene el campo) | falta |
| V15 | RW Aur: el contexto llama «V* RW Aur B» a Gaia DR3 156430817820015232, que según el WDS es A. Corregir o advertir antes de que la ficha lo muestre | WS3 (faricool54) | 1 h | — | `pipeline/errante/science/context.py`; `pipeline/tests/test_science_context.py:237`; [SCIENCE.md](SCIENCE.md) («Para WS3 (pendiente propio)») | falta (la rama en curso solo lo marca `ambiguous`) |
| V16 | Textos de `fields.toml` de la revisión: RW Aur, R Dra, WISE 0855, Barnard, y A/B invertidos en los comentarios | WS3 | 1 h | — | [SCIENCE.md](SCIENCE.md), filas de `fields.toml` | falta |
| V17 | Capa Gaia DR3 propagada a la época y footprint en el mapa (C05, WS5-4) | WS5 (sin dueño) | 3 h | V6 | `ExplorerMap.tsx`; `sky-map.html` | falta |
| V18 | Temperatura desde el espectro SPHEREx (ajuste) y `color_class` | WS3 | 4 h | — | `pipeline/errante/science/spectra.py:571` (stub) | falta |
| V19 | Modo compacto/embebido y prueba en un iframe de otro origen (C06, WS5-11) | WS5 + WS4 | 2 h | V2 | `frontend/src/api/jobs.ts` | falta |
| V20 | Releases nuevos (C01, WS1-9): las colecciones ya se configuran con `ERRANTE_COLLECTIONS`, pero `Release` es un `Literal` fijo y no hay descubrimiento | WS1 + contrato | 3 h | PR `contract:` | `pipeline/errante/settings.py:40`; `models.py:30` | parcial |
| V21 | Validar el cambio de SNR del coadd en una fuente estable (WS2-10) | WS2 (V0id47) | 2 h | — | `tasks/WS2-imaging-detection.md:91` | parcial |

### P2 (propuesta: congelar hasta después del envío, D10)

| Tarea | Dueño | Dónde |
|---|---|---|
| Detección automática: `find_sources`, `link_tracks`, `score_tracks`, inyección y shift-and-stack (WS2-3/4/5/6/9). Hoy `errante build --analyze` sale con código 3 | WS2 | `pipeline/errante/detect/sources.py:36`, `linking.py:40`, `scoring.py:19`, `inject.py:28`; `cli.py:403-405` |
| Objetos conocidos con SkyBoT/JPL, cruce y efemérides (WS3-1/2/8), y `/api/known-objects` | WS3 + WS4 | `pipeline/errante/science/known_objects.py:29`, `:38`, `:47` |
| Planeta X / Nueve: región y detectabilidad (WS3-6) y vista 3D hipotética (WS7-7). Si se muestra: hipotético, sin afirmar detección | WS3 + WS7 | `pipeline/errante/science/planet_x.py:21`, `:32` |
| Límites de inyección-recuperación (WS2-6 → WS4-7 → WS5-6) | WS2, WS4, WS5 | `pipeline/errante/detect/inject.py` |
| Distancia con geometría real (WS3-4), decisión CSA/CADC/NEOSSat (WS3-11), búsqueda sin IRSA en un punto arbitrario (WS1-7) | WS3, WS1 | `pipeline/errante/science/motion.py`; `pipeline/errante/data/s3.py` |
| WS7-3/5/6 (SBDB, SpaceMotion, glTF), restos de WS7-4 y WS7-9, UI-1 Band Equalizer, WS5-5 reporte de candidato | WS7, WS5 | `pipeline/errante/systems/sources.py:171`, `:182` |

## 3. Falta para la entrega

Todo esto es P0: sin ello no hay envío válido. Detalle de cada regla en [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md)
(S01–S10) y en [JUDGING_GUIDE.md](JUDGING_GUIDE.md).

### Decisión humana (ningún agente puede hacerlo por ustedes)

| ID | Qué | Quién | Para cuándo | Referencia |
|---|---|---|---|---|
| E1 | Visibilidad del repo y hosting (D1) | equipo; ejecuta WS4 | cuanto antes; [HOSTING_OFFERS.md](HOSTING_OFFERS.md) pedía decidir el backend antes de las 12:00 | S03, R01 |
| E2 | Integrantes en el portal: 1–6 aceptados en UP Buenos Aires, Team Owner incluido, sin waitlist, visibles en Members. El repo tiene 6 colaboradores (BenjaminPondal, DankoLiv, faricool54, mateoa007, rpccp, V0id47); TEAM.md lista 3. Los agentes no cuentan | Team Owner | antes de las 23:59 (después no se agregan) | S09; [TEAM.md](TEAM.md) |
| E3 | Editor único y backup. Submit for Judging, no Save Progress, con captura y hora. Si se edita después, reenviar | a designar | 21:00 | TEAM.md (línea «Responsable de edición/envío») |
| E4 | Leer Terms, privacidad y guía de marca. Volver a mirar la pestaña Resources del reto. Confirmar el horario de evaluación local con la organización (WS6-1b) | Team Owner / WS6 | antes del envío | [submission/CHECKLIST.md](submission/CHECKLIST.md) |
| E5 | Confirmar el nombre «Errante» (WS6-2) y el formato de la demo: video ≤ 30 s o ≤ 7 slides con portada | equipo | antes de grabar | `docs/submission/PROJECT.md:15` («working title») |
| E6 | Confirmar el origen de la idea y del scaffold para el registro de IA | equipo | antes del envío | `docs/submission/ai-usage.json:51` (`pending_team_confirmation`) |
| E7 | Revisión humana de los cinco registros de validación y quién la firma (D9) | una persona del equipo | antes del freeze | línea «Reviewer / date» de cada [registro](validation/) |
| E8 | Grabar la demo. Voz en otro idioma → subtítulos en inglés. Sin menores de 18. Sin marcas NASA generadas | quien grabe (WS6) | ~20:00 | S02, S04 |
| E9 | Prueba con 3 personas ajenas, una en celular (WS6-7) | WS6 | después del deploy | `docs/submission/PROJECT.md:97` |

### Trabajo de agente (se puede repartir ya)

| ID | Qué | Dueño | Esfuerzo | Depende de | Dónde |
|---|---|---|---|---|---|
| A1 | Las 8 filas «bloquea» de la revisión de textos (About 2, README 1, PROJECT.md 5): texto falso en materiales de evaluación | WS6 (sin dueño; TEAM.md reparte textos a WS5 + quien termine antes, normalmente WS3) y coordinación (README) | 1,5 h | — | §6 |
| A2 | Página About: hoy dice «numerically simulated data», «hand-entered, unverified parameters», que los productos reales «have not yet been integrated» y declara solo Codex | WS5 (archivo) + WS6 (texto) | 0,5 h | A1 | `frontend/src/pages/AboutPage.tsx:20`, `:26`, `:41`, `:45` |
| A3 | PROJECT.md final: quitar «Draft», High-Level Summary (bloque A4 de SCIENCE.md), estado (A2b), NASA Data (A6), herramientas y licencias, equipo y roles, links | WS6 | 2 h | E1, E2, E5 | `docs/submission/PROJECT.md:3`, `:15`, `:30`, `:36`, `:113`, `:150` |
| A4 | Demo: guion en PITCH.md con las frases sugeridas en SCIENCE.md, medios con `python -m errante.imaging.animate` (#71), recorrido mapa → click → video. Usar `docs/validation/figures/barnards-star/fig2_track.png`, no el blink saturado. Alojar sin login | WS6 + WS5 (capturas) | 3-4 h | E1, E5 | `docs/submission/PITCH.md:21-22` |
| A5 | Registro de IA: `AI_USAGE.md` y `docs/submission/ai-usage.json` (hoy `"tool": "OpenAI Codex"` y `real_spherex_observations: false`). Falta Claude en WS1, WS2, WS3 y WS7. Faltan metadatos para `pipeline/errante/data` (WS1), `science` (WS3) y `systems` + `frontend/src/three` (WS7) | coordinación + cada WS | 1,5 h | E6 | `docs/submission/ai-usage.json:6`, `:41`, `:51` |
| A6 | Inventario de fuentes, créditos y licencias (S06/S07): bloque A3 de SCIENCE.md más Aladin Lite 3.8.2 (GPL-3), three, scipy/photutils/reproject/astroquery/pyvo y httpx/psutil. Separar recursos consultados de procesados | WS6 + WS3 | 1,5 h | — | `docs/submission/PROJECT.md:106-111` (herramientas) y `:132-163` (datos y referencias) |
| A7 | Las 12 filas «importante» de WS6 y coordinación (README, AI_USAGE, PROJECT, PITCH, JUDGING_REVIEW, CHECKLIST) | WS6 / coordinación | 1,5 h | — | §6 |
| A8 | Llevar a cada registro el párrafo del chequeo de productos publicados de #70 y su «límite común». Hoy ningún registro cita `productcheck` | coordinación (sin reserva; registros de faricool54) | 1 h | — | cuerpo de #70; [`validation/`](validation/) |
| A9 | Paso 6 de VALIDATION.md en la URL final para los cinco, anotado en cada registro. Probar todos los links en incógnito y en celular | WS6 + WS5 | 1 h | V2 | [VALIDATION.md](VALIDATION.md) paso 6 |
| A10 | Onboarding en ≤ 3 pasos (WS5-2) y responsive/accesible con Lighthouse medido sobre la URL pública (WS5-3). No afirmar ≥ 90 sin medir | WS5 (sin dueño) | 3 h + 3 h | V2 | `tasks/WS5-frontend.md:32`, `:34` |
| A11 | CHECKLIST.md (R05: «registro hecho; revisión humana y paso 6 pendientes») y JUDGING_REVIEW.md con evidencia, sin notas oficiales | WS6 + WS3 + WS5 | 1,5 h | A3 | `docs/submission/CHECKLIST.md:79-85`; `docs/submission/JUDGING_REVIEW.md:14-22` |
| A12 | Contenedor del backend con los cinco campos y los snapshots de búsqueda (`COPY data/products` y `data/index`, o `ERRANTE_SEARCH_SNAPSHOTS`) | WS4 (rpccp) | 0,5 h | D1 (si hay backend) | `backend/Dockerfile:11-12`; `tasks/WS1-data-access.md:71-72` |
| A13 | Textos públicos que la revisión no cubre: HomePage dice «illustrative 3D models» y tiene un TODO del buscador que ya existe; README tiene líneas viejas (§8) | WS5; coordinación | 0,5 h | — | `frontend/src/pages/HomePage.tsx:32`, `:34` |

## 4. Decisiones pendientes del equipo

| ID | Decisión | Opciones y consecuencias | Quién |
|---|---|---|---|
| D1 | Hosting y visibilidad del repo | (a) Repo público + GitHub Pages (`vars.ENABLE_PAGES=true`): también resuelve el link anónimo al código (S03, WS6-11). (b) Repo privado + sitio estático en Firebase/Vercel/Netlify (o Pages, si el plan lo permite en privado: verificarlo); el link al código pediría login. Backend: (i) contenedor con jobs hospedado (por ejemplo Cloud Run, ver [HOSTING_OFFERS.md](HOSTING_OFFERS.md)) con A12 y CORS: el click → video funciona para cualquier punto; (ii) solo estático: cinco campos, y el click, la búsqueda, el espectro y las comparaciones piden backend, cosa que PROJECT.md tiene que decir | equipo; ejecuta WS4 |
| D2 | Dataset por defecto del sitio estático | Hoy `demo`, sintético (`pages.yml:39`, `client.ts:35`). Propuesta del relevamiento: `VITE_DATASET=real` | WS4 |
| D3 | Radio de R Dra en el 3D | Constante por defecto, como pide la revisión de WS3, o mantener la pulsación ilustrativa (`frontend/src/three/sceneLayout.ts:25`) | WS7 + WS3 |
| D4 | t0 de Barnard b–e (M5) | Aceptar la lectura de Basant et al. 2025 como conjunción inferior (WS3 lo recomienda, [SCIENCE.md](SCIENCE.md) «Decisiones de WS3») o revertir a `epoch_mjd = null` (`tasks/WS7-3d-systems.md:101`) | equipo |
| D5 | ¿V3 (retícula, trayectoria y zoom) entra antes del freeze? | Sin V3, el movimiento de ~1-2 px no se ve en el blink (por año: Barnard ~1,7 px, WISE 0855 ~1,3 px, ε Ind B ~0,8 px; [SCIENCE.md](SCIENCE.md) §0.2) | equipo + WS5 |
| D6 | Curvas de luz | Exponerlas antes del freeze (V10) o citar solo los registros offline en la demo | WS3 + WS4 + WS5 |
| D7 | Alcance del 3D en la entrega | Aceptar el 3D de catálogo de los cinco, declarado como no medido por SPHEREx, más V13 mínimo; dejar WS7-8 y V14 como trabajo futuro | equipo + WS7 |
| D8 | Responsables | WS5, WS6 (textos, demo, formulario), WS7 (DankoLiv de facto, sin reserva), coordinación, editor de envío y backup. En qué WS trabajan BenjaminPondal y mateoa007 | equipo |
| D9 | Revisión humana de R05 | Quién firma los cinco registros (E7) | equipo |
| D10 | Congelar P2 | Detección, SkyBoT, Planeta X, WS7-3/5/6/7 y UI-1 hasta después del envío; presentarlos como trabajo futuro en README, About y pitch | equipo |
| D11 | `tasks/region-search-plan.md` | Cerrarlo como superado por SkyExplorer (#34) o completar las sub-tareas 1, 4 y 5 | WS5 + coordinación |
| D12 | Protección de `main` | Hoy: PR obligatorio, checks `python` y `frontend`, historia lineal, **0 aprobaciones**. WS4-1 pedía 1 review. ¿Se deja así hasta el envío? | WS4 + coordinación |

## 5. Bugs y riesgos conocidos

| Bug o riesgo | Impacto | Qué hacer | Dueño |
|---|---|---|---|
| Mapa negro intermitente: `setPlane(90)` corre justo después de `setBaseImageLayer` (`sky-map.html:28`, `:34`), Aladin lo ignora y se queda en el plano vacío 50 (tiles 404). `ExplorerMap.tsx:31-33` reenvía el mismo 90 tras `ready`. Hay doble capa base (`survey` en `A.aladin`, `:25`, más `setBaseImageLayer`) | La pantalla principal arranca negra en la demo | V1 | WS5 |
| En modo estático, nombre, coordenadas, jobs, espectros y comparaciones lanzan error (`client.ts:113`, `:117`, `:123`, `:127`, `:133`) | Un deploy solo estático no muestra el núcleo de la visión | D1; decirlo en PROJECT.md | WS4 + WS6 |
| El build de Pages usa `demo` (sintético) por defecto (`pages.yml:39`) | El público vería datos sintéticos | D2 | WS4 |
| El contenedor solo copia `data/demo` (`backend/Dockerfile:11`); `data/products` queda vacío y no hay snapshots de búsqueda | Un backend desplegado no sirve los cinco campos ni sobrevive a una caída de IRSA | A12 | WS4 |
| Repo privado | El link al código no cumple el acceso anónimo (S03) | D1 | equipo |
| Sin `ERRANTE_DATA_DIR`, la API (con o sin jobs) escribe en `data/products` (versionado, de WS2): lo elige apenas tiene campos reales, y hoy tiene cinco (`backend/errante_api/settings.py:54`). Jobs → `fields/` y `manifest.json`; comparaciones de temporadas («Build comparisons») → `analyses/<id>` (`backend/errante_api/science_service.py:187`), que `.gitignore` no ignora (solo `data/products/**/*.fits`, `.gitignore:22`) | Archivos ajenos ensuciados por accidente, también con un simple `python scripts/dev.py api` sin jobs | Siempre `ERRANTE_DATA_DIR` apuntando a una copia (§7), con o sin jobs; nunca commitear esos archivos | todos |
| Espectro L2 en posición fija: apertura de 2 px (`pipeline/errante/imaging/photometry.py:36`) y Barnard se corre ~1,7 px | Flujo subestimado en las épocas extremas | V9; mientras tanto la nota de `science_ops.py:184` lo advierte | contrato + WS4 + WS3 |
| Barnard, RW Aur y R Dra saturan; ninguna pantalla lo avisa (revisión de textos) | Un juez puede leer mal el blink | Filas de WS5 en §6; en la demo usar las figuras de los registros | WS5 |
| RW Aur A/B invertido en el contexto del objeto | La ficha mostraría el nombre equivocado | V15 | WS3 |
| Los números de validación son análisis offline de los FITS, con scripts no versionados, sobre el build de #17. En el repo se reproducen con `pipeline/tests/test_science_validation_network.py` (RW Aur, R Dra, ε Ind B, WISE 0855; tests `network`) y con `python -m errante.imaging.productcheck` (#70) | Un juez puede pedir reproducibilidad | Citar «offline FITS analysis»; A8 | coordinación |
| Servicios externos: CDS Estrasburgo degradado (usar espejos de CfA/IRSA); fallback TAP de IRSA sin probar en vivo (WS1-2); snapshots solo para los cinco blancos (WS1-7); cada job tarda ~20-30 s y depende de IRSA/S3 | Un punto arbitrario puede fallar en vivo durante la demo | Grabar la demo con un recorrido que ya funcionó; tener los cinco campos estáticos de respaldo | WS1 + WS4 |
| El schema pasó a 0.5.0 con #73 (ficha del objeto) | Ramas viejas con `shared/schema/` desactualizado | `git pull origin main` y `python scripts/dev.py schema`; nunca resolver a mano los generados | todos |
| Textos públicos falsos (About, README, PROJECT, `ai-usage.json`) | Afecta Validity y Presentation, y las declaraciones del formulario | A1, A2, A5, A7 | WS6 + coordinación |

## 6. Correcciones de texto listas para aplicar

WS3 no edita archivos ajenos: cada dueño aplica sus filas. Los textos sugeridos están en inglés para la UI y la
entrega. Los números de línea son del commit que cita cada tabla: verificá el archivo antes de pegar.

**Revisión científica de textos** (WS3-7, #60): [SCIENCE.md](SCIENCE.md), sección «Revisión científica de textos»,
con los textos completos en «Textos listos para pegar» (bloques A1–A6). 47 filas: 8 bloquea, 24 importante,
15 menor. Ya resueltas en main: la de `catalog.py` `field_id` (sistemas publicados por #64) y la de la nota de
`field.json` (#41 reconstruyó los campos). **Abiertas: 45** (8 / 22 / 15).

| Dueño (columna de la tabla) | Filas | Bloquea | Importante | Menor | Abiertas |
|---|---|---|---|---|---|
| WS6 (PROJECT, PITCH, JUDGING_REVIEW, CHECKLIST) | 11 | 5 | 6 | 0 | 11 |
| WS6 + WS5 (AboutPage) | 4 | 2 | 2 | 0 | 4 |
| coordinación + WS6 (README, AI_USAGE) | 5 | 1 | 4 | 0 | 5 |
| coordinación + WS7 (README) | 1 | 0 | 0 | 1 | 1 |
| WS5 (Home, index.html, SkyExplorer, showcase, ExplorerMap, Blink, SpectrumChart) | 11 | 0 | 4 | 7 | 11 |
| WS5 + WS3 (FieldPage) | 2 | 0 | 2 | 0 | 2 |
| WS7, incluidas «+ WS3» y «+ WS4» (`catalog.py`, SystemsPage) | 7 | 0 | 3 | 4 | 6 |
| WS3 (`fields.toml`) | 5 | 0 | 2 | 3 | 5 |
| WS2 + WS4 (nota de `field.json`) | 1 | 0 | 1 | 0 | 0 |

**Revisión científica del 3D** (#65): [SCIENCE.md](SCIENCE.md), sección «Revisión científica del 3D (WS7, #47)»,
más «Decisiones de WS3» y «Sigue abierto». 17 filas, todas de WS7: 1 bloquea (V4), 5 importantes (V12) y 11 menores.
Las 17 siguen abiertas en main (por ejemplo `astro.ts:1151`, `ephemerides.ts:423`, `sceneLayout.ts:25`).

## 7. Cómo correr todo en local

```bash
python scripts/dev.py setup            # venv + paquetes Python + npm ci
python scripts/dev.py setup-science    # reproject, photutils, astroquery…: necesarios para jobs y espectros
```

**Solo estático** (sin backend): `python scripts/dev.py web` y abrir
`http://localhost:5173/?mode=static&dataset=real#/` (cinco campos reales y 3D).

**Recorrido completo** (mapa → click → job → video, espectro y comparaciones). La API publica en su carpeta de datos,
con o sin jobs: apuntala a una **copia** de `data/products` con ruta absoluta, nunca a `data/products` (§5).

```bash
# bash (macOS/Linux/Git Bash)
cp -r data/products "$HOME/errante-products"
ERRANTE_ENABLE_JOBS=1 ERRANTE_DATA_DIR="$HOME/errante-products" python scripts/dev.py api   # :8000, docs en /docs
python scripts/dev.py web                                                                     # en otra terminal
```

```powershell
# PowerShell (Windows)
Copy-Item -Recurse data\products "$env:TEMP\errante-products"
$env:ERRANTE_ENABLE_JOBS = '1'; $env:ERRANTE_DATA_DIR = "$env:TEMP\errante-products"; python scripts/dev.py api
python scripts/dev.py web    # en otra terminal
```

Abrir `http://localhost:5173/?mode=api&dataset=real`. Dos agentes en la misma máquina: `API_PORT=8001` para la API
y `VITE_API_BASE=http://localhost:8001` para la web.

Herramientas útiles (con el venv activo; `--out` fuera de `data/products` salvo que seas WS2):

```bash
errante build barnards-star --out <carpeta>                      # un campo real (sin análisis)
errante object --name "Barnard's Star"                           # ficha del objeto (WS3)
errante cube-spectrum --ra 269.4463 --dec 4.7665                 # espectro rápido del cubo DR1
errante lightcurve --help                                        # curvas de luz (WS3)
python -m errante.imaging.productcheck --products data/products --out <carpeta>   # chequeo de los PNG publicados
python -m errante.imaging.animate --products data/products --out <carpeta>        # GIF y stills para la demo
python scripts/dev.py check                                      # lo mismo que CI + guardia de ownership
```

## 8. Tareas con checkbox desactualizado

Cada dueño actualiza **su** archivo de `tasks/` (nadie marca casillas ajenas). Coordinación no los tocó en este PR.

| Archivo:línea | Dice | Realidad | Dueño |
|---|---|---|---|
| `tasks/WS1-data-access.md:21-23` | #21, #22 y #23 «En PR» | Mergeados el 14/11 | WS1 |
| `tasks/WS1-data-access.md:41`, `:45-46` | Falta el registro de Barnard; falta que `build.py` llene `wavelength_um` | #46 y #25 | WS1 |
| `tasks/WS1-data-access.md:48` | WS1-6 sin marcar | Cubierto por #16, #21 y #35 (selección por temporada × detector, deduplicación, pool emparejado en λ) | WS1 |
| `tasks/WS1-data-access.md:64`, `:70` | WS1-10 «PR en curso»; WS1-13 «PR `ws1/deploy-spectra-facts`» | #45 + #50; #49 | WS1 |
| `tasks/WS3-science.md:19` | ⛔ `spectra.*` | Implementado en #59, salvo `color_class` (`spectra.py:571`) | WS3 |
| `tasks/WS3-science.md` (falta) | — | No lista V15 (RW Aur A/B), V16 (`fields.toml`) ni V18 (temperatura desde el espectro) | WS3 |
| `tasks/WS4-backend.md:27`, `:56-57`, `:84` | Conexión WS5 y frontend «en PR dependiente» | #34 y #55 mergeados | WS4 |
| `tasks/WS4-backend.md` (falta) | — | No lista la revisión de `GET /api/object` (#76, ya mergeado), curva de luz (V10), Dockerfile (A12) ni pm en espectros (V9) | WS4 |
| `tasks/WS5-frontend.md:24` | Pendiente «validación científica R05» | Registros en #36 y #46 | WS5 |
| `tasks/WS5-frontend.md:55-58` | WS5-11: la URL propuesta no está implementada | Implementada en #34; falta solo el iframe (V19) | WS5 |
| `tasks/WS5-frontend.md:160`, `:178` | Orden de integración #32→#33 y #39→#53→… | Todo mergeado | WS5 |
| `tasks/WS5-frontend.md` (falta) | — | No lista V1, V3, V7 ni las 13 filas de WS5 de la revisión de textos | WS5 |
| `tasks/WS6-product-submission.md:46` | No prometer «espectros reales mientras sean stubs» | Hay espectros reales (#31, #54, #55, #59) | WS6 |
| `tasks/WS7-3d-systems.md:7`, `:83` | 3D y WS7-8 son P2 | El 3D desde mediciones es P1 (AGENTS.md, VISION.md) | WS7 |
| `tasks/WS7-3d-systems.md:23`, `:29`, `:53` | Schema 0.2.1; rama `ws7/procedural-3d` sin PR | Schema 0.4.0 (`models.py:28`); #47 mergeado | WS7 |
| `tasks/WS7-3d-systems.md:130` y siguientes | JSON de demo por coordinar; ε Ind B y WISE 0855 sin decidir | JSON entraron con #47; WS3 decidió en #65 | WS7 |
| `tasks/WS7-3d-systems.md` (falta) | — | No lista las 17 filas de la revisión del 3D (V4, V12) | WS7 |
| `tasks/region-search-plan.md:64` y sub-tarea 3 | Sub-tareas 2 y 3 pendientes; `ResolvedRegion` «UI-only» | #11/#33 y #34; `ResolvedRegion` es contrato desde #32 | WS5 (D11) |
| `tasks/README.md:4`, `:27-28` | Solo WS4 reservado; P1 sin el 3D | WS1 (#10), WS2 (#13), WS3 (#51) reservados; 3D desde mediciones = P1 | coordinación |

WS2 está al día tras #72 (WS2-8 queda `[~]` hasta A8).

**Otros documentos desactualizados** (no se editaron en este PR; cada uno tiene su dueño):

| Archivo:línea | Qué está viejo | Dueño |
|---|---|---|
| `README.md:17` | «Shared contract: 0.3.0» (es 0.4.0) | coordinación |
| `README.md:20-21` | R05 «still pending» (fila de la revisión) | coordinación + WS6 |
| `README.md:23-26` | 3D «illustrative, unverified»; comparaciones «separate work» (#53-#55) | coordinación |
| `README.md:37`, `:42` | Por defecto sintético; «Public hosting has not been selected» (actualizar tras D1/D2) | coordinación |
| `README.md:116-119`, `:121-124` | «Real SPHEREx observations have not yet been integrated»; IA solo Codex (filas «bloquea» e «importante») | coordinación + WS6 |
| `docs/REQUIREMENTS.md:19-36` | Columna de estado de R01–R05 y C01–C08 anterior a #17, #34 y #53-#55 | coordinación |
| `docs/SCIENCE.md:710-711` | «`manifest.json` tiene `systems: []`» (#64 los publicó) | WS3 |
| `docs/VISION_3D.md:316-317` | WS7-9 «implementado en la rama» (mergeado en #47) | WS7 |
| `docs/COLLABORATION.md:4`, `:32` | Solo WS4 reservado; WS7 «PR pendiente» | coordinación |
| `backend/errante_api/main.py:3-15` | `/api/search` «501 until done» (implementado); no lista `/api/spectra`, comparaciones ni `/api/systems` | WS4 |

## 9. Cómo tomar una tarea

1. Leé [COLLABORATION.md](COLLABORATION.md) y el archivo de tu workstream en `tasks/`.
2. **Reservá** en el chat o en un issue: «tomo V3» (ID de este plan) o «tomo WS5-10». Si el workstream no tiene
   dueño en [TEAM.md](TEAM.md), avisá también a coordinación.
3. Una rama `wsN/...` (o `contract/...`, `chore/...`) por tarea, en tu propio worktree:
   `git worktree add -b wsN/x ../hn-wsN-x origin/main`, y adentro `python scripts/dev.py setup`.
4. Tocá solo tus rutas: `python scripts/owners.py --who <ruta>`. Lo de otro dueño va como `TODO(WSx)` o pedido.
   Cambios de contrato: un PR `contract:` a la vez, con modelos, schema, versión y `types.ts` juntos.
5. Antes de cada push: `git pull origin main` (merge), `python scripts/dev.py check`, revisar el diff y stagear por
   nombre. Nunca `push --force`, `git add -A` ni commits a `main`. En PRs apilados, `ERRANTE_BASE_REF=origin/<base>`
   hace que la guardia local compare contra la misma base que CI; después de cada squash, traer main al siguiente y
   retargetearlo a main.
6. Al terminar: marcá tu casilla en tu `tasks/WSx-*.md` con el PR, y avisá para que coordinación actualice esta
   página.

No hace falta esperar a un endpoint nuevo para definir un ensayo o revisar una medición: se puede trabajar con
fixtures del modelo **acordado**, pero no inventar otro formato compartido. Contrato de jobs ya acordado:
[CONTRACT.md](CONTRACT.md); no crear otra API de jobs. Una resta con λ distinta no certifica variabilidad. Haber
cerrado el P0 local no marca como terminados los opcionales de un WS.
