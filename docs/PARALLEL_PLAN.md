# Plan paralelo y estado del proyecto — 15/11/2026, main #97 (publicación verificada #97)

Guía viva del equipo, actualizada contra `main` **3ed5c91 (#97)**, también comprobado en la publicación pública del 15/11.
Los PR #91 y #95 actualizaron textos/backend; #96 agregó zoom y predicción Gaia de Barnard.
Los registros científicos siguen en [`validation/`](validation/): aprobación humana y cierre del paso 6 pendientes.
Las referencias de línea del relevamiento anterior pueden haberse desplazado; usar los IDs y rutas.
Esta edición actualiza estado y dependencias, sin preparar demo, completar el formulario ni declarar el envío.

Visión: [VISION.md](VISION.md) · reglas: [COLLABORATION.md](COLLABORATION.md) · responsables: [TEAM.md](TEAM.md) ·
integración WS4/WS5: [WS4_INTEGRATION.md](WS4_INTEGRATION.md) · protocolo R05: [VALIDATION.md](VALIDATION.md) ·
entrega: [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md) y [submission/CHECKLIST.md](submission/CHECKLIST.md).

**Reloj (ART, UTC-3):** freeze **17:00** · envío interno **21:00** · cierre del portal **23:59** (sede UP Buenos
Aires). Después del freeze solo entran textos, deploy y entrega. Save Progress no es envío.

**Ficha del objeto: hecha (15/11, ~06:00 ART).** El contexto de catálogo de WS3 ya llega al panel del click: contrato `ObjectContextResponse` 0.5.0 (#73), adaptador `to_response` de WS3 (#74), tarjeta `ObjectCard` en «Explore a position» (WS5, #75) y `GET /api/object` (WS4, #76). Los atajos y la búsqueda por nombre consultan por nombre; el click y las coordenadas, por posición. Un servicio caído nunca se muestra como «no catalogado». La aceptación técnica pública está registrada en #84/#95.

**URL pública (15/11, #84): https://errante.34-148-242-13.sslip.io.** Es una VM de Google Cloud con la web y la API en el mismo origen, jobs habilitados y los cinco campos reales, con DNS temporal de sslip.io. Un merge a `main` **no** se publica solo: hay que redeployar con `scripts/deploy_vm.py` (pasos en `backend/deploy/README.md`, cada uno con su login de gcloud). Sirve para probar los cambios en caliente, pero es la misma URL que van a ver los jueces.

**Curvas de luz (#78/#79/#83), revisión #85 y actualizaciones #93–#95.** Productos nuevos de SIA en vivo,
1000 bootstrap y 999 permutaciones; advertencias por producto, versiones/unidades y selección explícitas.
RW Aur: 56/10 mediciones/utilizables; R Dra: 538/450, solo sondeo ancho. WS5 integró y publicó notas, límites de error, selección de datos y carga estática de curvas en #97.
Quedan las vistas adicionales por detector/fase/pares y otras mejoras de UX. La revisión humana de R05 no se infiere de estos checks.

## 1. Estado en una mirada

Leyenda: **hecho** · **parcial** · **falta** · **en curso**.

| Parte de la visión | Estado | Qué hay y qué falta | PRs | Quién |
|---|---|---|---|---|
| Mapa SPHEREx DR1: Aladin Lite + HiPS IRSA, λ y AllWISE | parcial | Mapa negro corregido y publicado en #86. Faltan capa Gaia y footprint | #34, #86 | WS5 |
| Búsqueda por nombre (Sesame/CfA) y por RA/Dec; presets de los cinco | hecho con API | En modo estático no hay búsqueda (`frontend/src/api/client.ts:113`, `:117`) | #11, #32, #33, #34 | BenjaminPondal, rpccp |
| Coordenadas en la URL (C06) | parcial | RA/Dec/FOV/detector/job restaurables; iframe externo con imágenes y jobs probado (#95). Falta vista compacta | #34, #95 | WS5 + WS4 |
| Click → job → hasta 40 frames reales → video | hecho, también en la URL pública | ~20-30 s por campo. En local requiere `ERRANTE_ENABLE_JOBS=1` y `?mode=api`; en la URL pública (#84) funciona sin parámetros. En un deploy estático (Pages) el click no construye nada | #18, #32, #33, #34, #84 (datos: #16, #21-#23, #35) | rpccp, faricool54, V0id47 |
| Blink: reproducción, paso, velocidad, detector y color | parcial | Funciona con imágenes reales; zoom 1×/2×/4× y retícula Gaia de Barnard en #96. Predicción de los otros blancos y UI de calidad pendientes | #15, #39–#41, #96 | WS5, con WS7/WS3 para astrometría |
| Cinco campos reales curados (40 frames cada uno) sin backend | hecho | `?mode=static&dataset=real`. `data/products` pesa 2,4 MB | #17, #41 | V0id47 |
| Espectro de un punto (cubo DR1 o fotometría forzada L2) | parcial | Panel plegado y manual. Desde #81/#82 (V9), L2 acepta movimiento propio de catálogo y reporta la posición predicha de cada exposición. En Barnard, las 8 medidas D2 salen saturadas | #31, #42, #45, #53, #54, #55, #81, #82 | V0id47, faricool54, rpccp |
| Comparación de temporadas | parcial | API/UI live implementadas; 196 PNG y JSON congelados exportables (#82). La UI estática aún no consume esos snapshots | #19, #37, #53–#55, #69, #82 | WS2, WS4; UI estática WS5 |
| Ficha del objeto: SIMBAD, Gaia DR3, VSX, planetas confirmados, 2MASS/AllWISE, como Facts con fuente | hecho | Tarjeta en el panel del click (por nombre o por posición) con `GET /api/object`; contexto de catálogo, no mediciones SPHEREx | #58, #73–#76 | faricool54 + Claude (WS3; contrato, WS4 y WS5 con aviso); rpccp revisa #76 |
| Curva de luz de R Dra y RW Aur | hecho, mejoras adicionales pendientes | Productos actualizados #93–#95 y panel #97 publicados: límites, floors, selección y carga estática exportada. Vistas por detector/fase/pares pendientes | #79, #83, #85, #93–#97 | WS3, WS4, WS5 |
| 3D de los cinco blancos | parcial | Contexto de catálogo con fuentes y estados por valor. V4/V12/V13 mínimo en PR #90 abierto; sin 3D físico desde SPHEREx ni para clicks arbitrarios | #47, #64; PR #90 abierto | WS7 + WS3 |
| Validación R05 de los cinco | hecho, con salvedades | Cinco registros `success`. Falta la revisión humana. Analizan el build de #17, no el de #41. Los scripts originales no están versionados. El paso 6 ya se puede hacer en la URL pública de #84 (A9) | #36, #46, #62, #66, #70, #71 | faricool54 + Claude, V0id47 |
| Deploy público | hecho | Google Compute Engine, HTTPS, datos reales y jobs. Publicación verificada 3ed5c91 (#97); repo privado y dominio propio opcional. El merge no despliega automáticamente | #84, #95–#97 | WS4 |
| Materiales de entrega | parcial | About y PROJECT actualizados en #91; README/estado en esta edición. Demo final, integrantes, inventario completo, revisión y envío pendientes | #91; WS6-4a | WS6 + equipo |
| Objetos conocidos (SkyBoT/JPL) | falta (P2) | `/api/known-objects` → 501 (`backend/errante_api/live_service.py:167-168`) | — | WS3 |
| Detección automática y Planeta X | falta (P2) | Stubs con `NotImplementedError` | — | WS2, WS3, WS7 |

## 2. Falta para la visión

Esfuerzo en horas aproximadas para una persona con su agente. «Sin dueño» significa que nadie reservó ese
workstream en [TEAM.md](TEAM.md): reservalo antes de arrancar (§9). Citá el ID (V1, A3…) en tu PR.

### P0 (antes del freeze)

| ID | Tarea | Dueño | Esfuerzo | Depende de | Dónde | Estado |
|---|---|---|---|---|---|---|
| V1 | Arreglar el mapa negro: aplicar el plano inicial cuando la capa esté lista (o reintentar `setFrequency` hasta que cargue un tile). Probar recargando varias veces | WS5 (reserva formal pendiente) | 0,5 h | — | `frontend/public/sky-map.html:25`, `:28`, `:34`; `frontend/src/components/ExplorerMap.tsx:31-33` | hecho (#86), publicado/verificado |
| V2 | Que el recorrido mapa → click → video se pueda probar en la URL pública | WS4 (rpccp) + WS6 | 1,5-4 h | D1, D2 | `.github/workflows/pages.yml:18`, `:38-39`; `frontend/src/api/client.ts:35-37`; `backend/Dockerfile:11-12` | hecho (#84) |
| V3 | Retícula y posición predicha del blanco sobre el video, y zoom pixelado. Barnard se corre ~1,7 px en todo el baseline ([registro](validation/barnards-star.md)): sin retícula no se ve. Rotular «predicted from catalog, not a measurement» | WS5 (reserva formal pendiente), con la matemática de WS7 | 3 h | D5 | `frontend/src/components/BlinkViewer.tsx:266` (TODO); `field.json` ya trae `grid.wcs`; predicción con paralaje en `frontend/src/three/skyTrack.ts`; movimientos propios en los comentarios de `pipeline/errante/config/fields.toml` (para un click arbitrario, de la ficha del objeto, V6); `known.json` está vacío en los cinco campos | parcial (#96): zoom y retícula Barnard; otros blancos pendientes |
| V4 | Fila «bloquea» del 3D: la ficha de RW Aur cita como «SPHEREx measured» magnitudes D5/D6 de núcleos saturados | WS7 (de facto DankoLiv, #47) | 0,25 h | — | `frontend/src/three/astro.ts:1150-1151`; texto listo en [SCIENCE.md](SCIENCE.md) (fila de `astro.ts:1150-1151`) | en PR #90 abierto, no integrado |
| V5 | Cerrar R05: revisión humana de los cinco registros (E7) y párrafos del chequeo de productos publicados de #70 en cada registro (A8) | coordinación (sin reserva; registros de faricool54) + una persona que revise | 2 h | — | [`validation/`](validation/) | falta |

### P1

| ID | Tarea | Dueño | Esfuerzo | Depende de | Dónde | Estado |
|---|---|---|---|---|---|---|
| V6 | Ficha del objeto en el panel del click; caída de servicio no bloquea el video | WS3 + WS4 + WS5 | — | contrato 0.5.0, vigente en 0.7.0 | #73–#76 | hecho; aceptación pública #84/#95 |
| V7 | Panel del click con tres vistas (Tiempo / Espectro / 3D). Abrir el panel al hacer click y lanzar el espectro del cubo (rápido) solo | WS5 (reserva formal pendiente) | 2 h | V6 | `frontend/src/components/SkyExplorer.tsx:168-171`; `PositionSpectrum.tsx:46` (`<details>` cerrado) y `:72` | falta |
| V8 | Calidad por frame (C07): `valid_fraction` y origen del frame en el blink. Un flag ausente no es «limpio». Las fracciones de flags necesitan contrato | WS5 (WS5-10) + WS2 (WS2-11) + contrato (WS4-10) | 1,5 h solo UI; 5 h con flags | contrato, para los flags | `BlinkViewer.tsx:179-180`; `pipeline/errante/models.py:97` | falta |
| V9 | Espectro L2 con movimiento propio: `pm_ra`/`pm_dec`/época opcionales en `SpectrumRequest`, pasados a la fotometría. El pipeline ya lo sabe hacer (`photometry.propagate`, CLI `errante spectrum --pm-ra --pm-dec`, y `position_spectrum` de WS3); falta el contrato y la API | contrato + WS4 + WS3 | 2 h | V6 (pm del objeto) | `models.py:511`; `backend/errante_api/science_ops.py:184`; `pipeline/errante/imaging/photometry.py:319`; `pipeline/errante/science/spectra.py:380` | hecho (#81, #82) |
| V10 | Curva de luz de R Dra y RW Aur en la app. Lo más barato: precomputarla con la CLI y publicarla como producto estático (necesita un modelo de contrato) | WS3 + contrato + WS4 + WS5 | 3-4 h | D6 | `pipeline/errante/science/variability.py:1098`; `pipeline/errante/cli.py:538` | hecho (#79/#83/#95/#97); vistas adicionales pendientes WS5 |
| V11 | Comparaciones visibles sin backend: `ComparisonResponse` precomputado o los stills/GIF de #71 | WS2 + WS4 | 2 h | D1 | `data/products/fields/*/` (sin comparaciones) | datos/exportación hechos (#82); UI estática pendiente WS5 |
| V12 | Las 5 filas «importante» de la revisión del 3D: máximos medidos de R Dra, radio de R Dra fijo por defecto, «look at the frames» en RW Aur, saturación de Barnard y S/N de WISE 0855 en el panel del cielo | WS7 (de facto DankoLiv) | 1,5 h | D3 | [SCIENCE.md](SCIENCE.md), tabla del 3D (filas de `ephemerides.ts`, `sceneLayout.ts`, `skyTrack.ts`) | en PR #90 abierto |
| V13 | 3D alimentado por `physical_parameters` de WS3 (Teff, radio, distancia como Facts con fuente), rotulado «catalog, not measured by SPHEREx». Después: color, radio y pulsación desde SPHEREx (WS7-8) | WS7 + WS3 | 2 h el mínimo; 6 h completo | V6, V18 | `pipeline/errante/systems/catalog.py`; [VISION_3D.md](VISION_3D.md) («Diferencias con VISION.md que siguen abiertas») | mínimo en PR #90 abierto; parte SPHEREx depende de V18 |
| V14 | 3D para un click arbitrario (cualquier estrella con Gaia). Sin dato: «unknown», nada inventado | WS7 + WS3 | 5 h | V6, V13 | `frontend/src/pages/FieldPage.tsx:38` (hoy solo enlaza si `manifest.systems` tiene el campo) | falta |
| V15 | RW Aur: el contexto llama «V* RW Aur B» a Gaia DR3 156430817820015232, que según el WDS es A. Corregir o advertir antes de que la ficha lo muestre | WS3 (faricool54) | 1 h | — | `pipeline/errante/science/context.py`; `pipeline/tests/test_science_context.py:237`; [SCIENCE.md](SCIENCE.md) («Para WS3 (pendiente propio)») | falta (la ficha lo marca `ambiguous`) |
| V16 | Textos de `fields.toml` de la revisión: RW Aur, R Dra, WISE 0855, Barnard, y A/B invertidos en los comentarios | WS3 | 1 h | — | [SCIENCE.md](SCIENCE.md), filas de `fields.toml` | hecho (#87/#88), publicado |
| V17 | Capa Gaia DR3 propagada a la época y footprint en el mapa (C05, WS5-4) | WS5 (reserva formal pendiente) | 3 h | V6 | `ExplorerMap.tsx`; `sky-map.html` | falta |
| V18 | Temperatura desde el espectro SPHEREx (ajuste) y `color_class` | WS3 | 4 h | — | `pipeline/errante/science/spectra.py:571` (stub) | falta |
| V19 | Modo compacto/embebido y prueba en un iframe de otro origen (C06, WS5-11) | WS5 + WS4 | 2 h | V2 | `frontend/src/api/jobs.ts` | WS4 probado (#95); vista compacta pendiente WS5 |
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
| E1 | App/API ya públicas en Google Compute Engine (#84/#95/#96). Decidir solo si se publica el código; un repo privado no es el enlace público para jueces. Dominio propio opcional | equipo; operación WS4 | antes de enlazar materiales | S03, R01 |
| E2 | Integrantes en el portal: 1–6 aceptados en UP Buenos Aires, Team Owner incluido, sin waitlist, visibles en Members. El repo tiene 6 colaboradores (BenjaminPondal, DankoLiv, faricool54, mateoa007, rpccp, V0id47); TEAM.md lista 3. Los agentes no cuentan | Team Owner | antes de las 23:59 (después no se agregan) | S09; [TEAM.md](TEAM.md) |
| E3 | Editor único y backup. Submit for Judging, no Save Progress, con captura y hora. Si se edita después, reenviar | a designar | 21:00 | TEAM.md (línea «Responsable de edición/envío») |
| E4 | Leer Terms, privacidad y guía de marca. Volver a mirar la pestaña Resources del reto. Confirmar el horario de evaluación local con la organización (WS6-1b) | Team Owner / WS6 | antes del envío | [submission/CHECKLIST.md](submission/CHECKLIST.md) |
| E5 | Confirmar nombre/identidad del equipo y formato final de demo: video ≤30 s o ≤7 slides con portada | equipo | antes de producir la demo | WS6-2/5, PROJECT.md |
| E6 | Confirmar el origen de la idea y del scaffold para el registro de IA | equipo | antes del envío | `docs/submission/ai-usage.json:51` (`pending_team_confirmation`) |
| E7 | Revisión humana de los cinco registros de validación y quién la firma (D9) | una persona del equipo | antes del freeze | línea «Reviewer / date» de cada [registro](validation/) |
| E8 | Grabar la demo. Voz en otro idioma → subtítulos en inglés. Sin menores de 18. Sin marcas NASA generadas | quien grabe (WS6) | ~20:00 | S02, S04 |
| E9 | Prueba con 3 personas ajenas, una en celular: no la reemplazan screenshots/checks automatizados | WS6 | antes del envío | WS6-7 |

### Trabajo de agente (se puede repartir ya)

| ID | Qué | Dueño | Esfuerzo | Depende de | Dónde |
|---|---|---|---|---|---|
| A1 | Falsas afirmaciones de estado: About/PROJECT corregidos #91; README y documentos de estado actualizados aquí. No equivale a cerrar inventario/demo/envío | WS6 + coordinación | documentación | — | README, REQUIREMENTS, ARCHITECTURE |
| A2 | About con datos reales, fuentes y límites actualizado/publicado #91 | WS6 + WS5 | hecho | — | `frontend/src/pages/AboutPage.tsx` |
| A3 | PROJECT actualizado técnicamente #91; conserva borrador hasta completar integrantes, demo y revisión final del equipo | WS6 | pendiente de cierre humano | E2, E5, demo | `docs/submission/PROJECT.md` |
| A4 | Demo: guion en PITCH.md con las frases sugeridas en SCIENCE.md, medios con `python -m errante.imaging.animate` (#71), recorrido mapa → click → video. Usar `docs/validation/figures/barnards-star/fig2_track.png`, no el blink saturado. Alojar sin login | WS6 + WS5 (capturas) | 3-4 h | E1, E5 | `docs/submission/PITCH.md:21-22` |
| A5 | Inventario completo de IA, aportes/scaffold y origen de idea: disclosures existentes no son auditoría completa. `demo_data` describe solo fixtures sintéticos, no la app real. Mantener metadatos de cada WS | coordinación + cada WS | 1,5 h | E6 | `AI_USAGE.md`, metadatos de componentes y entrega |
| A6 | Inventario de fuentes, créditos y licencias (S06/S07): bloque A3 de SCIENCE.md más Aladin Lite 3.8.2 (GPL-3), three, scipy/photutils/reproject/astroquery/pyvo y httpx/psutil. Separar recursos consultados de procesados | WS6 + WS3 | 1,5 h | — | `docs/submission/PROJECT.md:106-111` (herramientas) y `:132-163` (datos y referencias) |
| A7 | Cotejar las filas restantes de la revisión de textos: esta edición corrige estado, no completa PITCH, inventario, envío ni aprobación humana | WS6 / coordinación | según revisión | — | §6 y SCIENCE.md |
| A8 | Llevar a cada registro el párrafo del chequeo de productos publicados de #70 y su «límite común». Hoy ningún registro cita `productcheck` | coordinación (sin reserva; registros de faricool54) | 1 h | — | cuerpo de #70; [`validation/`](validation/) |
| A9 | Paso 6 de VALIDATION.md y revisión humana en cada registro: #95 aporta 396 PNG, curvas y job/iframe verificados técnicamente; no firma el cierre R05 ni reemplaza usuarios reales | WS6 + WS5 + persona revisora | 1 h | V2 hecho | `VALIDATION.md` paso 6 |
| A10 | Onboarding, accesibilidad y Lighthouse. #96 corrigió layouts y se probaron home/Barnard a 390 px; no acredita prueba con 3 usuarios ni Lighthouse ≥90 | WS5 | por medir | V2 hecho | `tasks/WS5-frontend.md` |
| A11 | CHECKLIST.md (R05: «registro hecho; revisión humana y paso 6 pendientes») y JUDGING_REVIEW.md con evidencia, sin notas oficiales | WS6 + WS3 + WS5 | 1,5 h | A3 | `docs/submission/CHECKLIST.md:79-85`; `docs/submission/JUDGING_REVIEW.md:14-22` |
| A12 | ✅ **Hecho en #82.** Contenedor del backend con los cinco campos y los snapshots de búsqueda (`COPY data/products` y `data/index`, o `ERRANTE_SEARCH_SNAPSHOTS`) | WS4 (rpccp) | 0,5 h | D1 (si hay backend) | `backend/Dockerfile:11-12`; `tasks/WS1-data-access.md:71-72` |
| A13 | Textos de HomePage y otras piezas de UI por cotejar con la revisión WS3. README/estado corregidos en esta tarea | WS5 (UI); coordinación (docs) | 0,5 h | — | `frontend/src/pages/HomePage.tsx` |

## 4. Decisiones pendientes del equipo

| ID | Decisión | Opciones y consecuencias | Quién |
|---|---|---|---|
| D1 | Hosting decidido; visibilidad del código pendiente | Google Compute Engine con volumen persistente, web/API HTTPS y URL pública (#84). El repo sigue privado; decidir por separado el acceso al código. Pages opcional, no sustituto del servicio de jobs | equipo; operación WS4 |
| D2 | Dataset por defecto | Resuelto #82: Docker público usa API/real; Pages preparado usa real. Vite local sin variables sigue static/demo | WS4 |
| D3 | Radio de R Dra en el 3D | Constante por defecto, como pide la revisión de WS3, o mantener la pulsación ilustrativa (`frontend/src/three/sceneLayout.ts:25`) | WS7 + WS3 |
| D4 | t0 de Barnard b–e (M5) | Aceptar la lectura de Basant et al. 2025 como conjunción inferior (WS3 lo recomienda, [SCIENCE.md](SCIENCE.md) «Decisiones de WS3») o revertir a `epoch_mjd = null` (`tasks/WS7-3d-systems.md:101`) | equipo |
| D5 | V3 antes del freeze | Zoom y retícula de catálogo de Barnard ya entraron #96; extender a otros blancos es trabajo WS5/WS3, no detección medida | WS5 + WS3 |
| D6 | Curvas de luz | Publicadas, con notas/floors/selección y carga estática #97; restan vistas adicionales | WS3 + WS4 + WS5 |
| D7 | Alcance del 3D en la entrega | Aceptar el 3D de catálogo de los cinco, declarado como no medido por SPHEREx, más V13 mínimo; dejar WS7-8 y V14 como trabajo futuro | equipo + WS7 |
| D8 | Responsables | WS5, WS6 (textos, demo, formulario), WS7 (DankoLiv de facto, sin reserva), coordinación, editor de envío y backup. En qué WS trabajan BenjaminPondal y mateoa007 | equipo |
| D9 | Revisión humana de R05 | Quién firma los cinco registros (E7) | equipo |
| D10 | Congelar P2 | Detección, SkyBoT, Planeta X, WS7-3/5/6/7 y UI-1 hasta después del envío; presentarlos como trabajo futuro en README, About y pitch | equipo |
| D11 | `tasks/region-search-plan.md` | Cerrarlo como superado por SkyExplorer (#34) o completar las sub-tareas 1, 4 y 5 | WS5 + coordinación |
| D12 | Protección de main | Confirmar políticas efectivas con el administrador. El procedimiento del equipo exige PR y CI verde; esta actualización no modifica ni acredita la configuración de GitHub | administrador + coordinación |

## 5. Bugs y riesgos conocidos

| Bug o riesgo | Impacto | Qué hacer | Dueño |
|---|---|---|---|
| **Arreglado en #86:** mapa negro intermitente. `setPlane(90)` corre justo después de `setBaseImageLayer` (`sky-map.html:28`, `:34`), Aladin lo ignora y se queda en el plano vacío 50 (tiles 404). `ExplorerMap.tsx:31-33` reenvía el mismo 90 tras `ready`. Hay doble capa base (`survey` en `A.aladin`, `:25`, más `setBaseImageLayer`) | La pantalla principal arranca negra en la demo | V1 | WS5 |
| Modo estático: sin builds, búsqueda remota ni cálculo científico; curvas exportadas ya se cargan desde #97, comparaciones aún no | La UI de comparaciones sigue requiriendo API | Entrega live; exportar JSON para curvas estáticas y completar comparaciones en WS5 | WS5 + WS6 |
| **Resuelto en #82** (Pages usa `real` por defecto): el build de Pages usaba `demo` (sintético) por defecto (`pages.yml:39`) | El público vería datos sintéticos | D2 | WS4 |
| **Resuelto en #82:** el contenedor solo copiaba `data/demo` (`backend/Dockerfile:11`); `data/products` queda vacío y no hay snapshots de búsqueda | Un backend desplegado no sirve los cinco campos ni sobrevive a una caída de IRSA | A12 | WS4 |
| Repo privado | El link al código no cumple el acceso anónimo (S03) | D1 | equipo |
| El runner `scripts/dev.py api` ya inicializa una copia privada (#82); un uvicorn directo requiere revisar ERRANTE_DATA_DIR | Evitar escribir jobs/análisis en productos WS2 versionados | Runner recomendado (§7); directorio privado explícito en otros arranques | todos |
| **Resuelto en #81/#82** (movimiento propio opcional): espectro L2 en posición fija, con apertura de 2 px (`pipeline/errante/imaging/photometry.py:36`) y Barnard se corre ~1,7 px | Flujo subestimado en las épocas extremas | V9; mientras tanto la nota de `science_ops.py:184` lo advierte | contrato + WS4 + WS3 |
| Barnard, RW Aur y R Dra saturan | Brillo del PNG no es fotometría | Descripciones #87/#88, About #91, notas #95 y panel de límites/errores #97 publicados | WS5 + WS3 |
| RW Aur A/B invertido en el contexto del objeto | La ficha mostraría el nombre equivocado | V15 | WS3 |
| Los números de validación son análisis offline de los FITS, con scripts no versionados, sobre el build de #17. En el repo se reproducen con `pipeline/tests/test_science_validation_network.py` (RW Aur, R Dra, ε Ind B, WISE 0855; tests `network`) y con `python -m errante.imaging.productcheck` (#70) | Un juez puede pedir reproducibilidad | Citar «offline FITS analysis»; A8 | coordinación |
| Servicios externos: CDS Estrasburgo degradado (usar espejos de CfA/IRSA); fallback TAP de IRSA sin probar en vivo (WS1-2); snapshots solo para los cinco blancos (WS1-7); la duración de los jobs depende de la cobertura y de IRSA/S3 | Un punto arbitrario puede fallar en vivo durante la demo | Grabar la demo con un recorrido que ya funcionó; tener los cinco campos estáticos de respaldo | WS1 + WS4 |
| El schema está en 0.7.0 (0.5.0 ficha del objeto #73; 0.6.0 curvas de luz #78; 0.7.0 movimiento propio #81) | Ramas viejas con `shared/schema/` desactualizado | `git pull origin main` y `python scripts/dev.py schema`; nunca resolver a mano los generados | todos |
| Relato y materiales finales | El estado técnico fue corregido #91 y en esta edición; inventario, demo y aprobación siguen pendientes | A3–A7, A11; no confundir documentación actual con envío aprobado | WS6 + equipo |

## 6. Estado de las revisiones científicas de textos y 3D

La revisión original con sus textos y severidades está en [SCIENCE.md](SCIENCE.md). Sus conteos del
15/11 temprano son históricos: no se presentan como número de filas aún abiertas sin cotejar cada una.

| Área | Estado cotejado con main #97 (publicación verificada #97) |
|---|---|
| About y PROJECT | Texto técnico corregido #91; cierre de la entrega y revisión del equipo pendientes |
| README, arquitectura, matriz y documentos de estado | Actualizados en esta edición WS6, sin preparar demo/formulario |
| Descripciones de campos y comentarios RW Aur A/B | Corregidos #87/#88 y publicados |
| Curvas de luz | Revisión #85; WS3 #93 y republish #94/#95. #97 publicó notas/floors/selección y carga estática; restantes vistas aún WS5 |
| 3D V4/V12/V13 | PR #90 abierto, no integrado; no dar sus correcciones por publicadas |
| R05 | Cinco registros offline; revisión humana y cierre formal del paso 6 pendientes |
| Otros textos/UI e inventario | Cada dueño debe cotejar las filas de SCIENCE.md; esta actualización no certifica auditoría completa |

## 7. Cómo correr todo en local

```bash
python scripts/dev.py setup            # venv + paquetes Python + npm ci
python scripts/dev.py setup-science    # reproject, photutils, astroquery…: necesarios para jobs y espectros
```

**Solo estático** (sin backend): `python scripts/dev.py web` y abrir
`http://localhost:5173/?mode=static&dataset=real#/` (cinco campos reales y 3D).

**Recorrido completo local.** `scripts/dev.py api` siembra una copia privada en `data/cache/local/products`
y conserva su estado. El directorio fuente `data/products` no es destino de jobs. En otra terminal correr
`python scripts/dev.py web` y abrir `http://localhost:5173/?mode=api&dataset=real#/`.

```bash
# Bash
export ERRANTE_ENABLE_JOBS=1
python scripts/dev.py api
```

```powershell
# PowerShell (usar py si python no está disponible)
$env:ERRANTE_ENABLE_JOBS = '1'
py scripts/dev.py api
```

Para uvicorn directo configurar un `ERRANTE_DATA_DIR` privado. `API_PORT=8001` y `VITE_API_BASE` permiten
separar dos servidores locales. La [guía de deploy](../backend/deploy/README.md) documenta operación pública.

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

## 8. Estado de tareas y documentación

Las casillas de `tasks/WSx-*` las mantiene cada dueño. Este plan refleja evidencias, sin marcar tareas
ajenas por inferencia ni confundir un PR abierto con una publicación.

- WS4: entrega e integración actualizadas en #95; `/api/limits`, flags nuevos y releases esperan datos/contratos.
- WS5: #96 publicó zoom/retícula Barnard y correcciones móviles. Límites/floors/selección y carga estática de curvas publicados #97. Compacto, vistas adicionales,
  panel de tres vistas, Gaia/footprint, calidad y pruebas de usuarios/Lighthouse siguen pendientes.
- WS3: #87 y #93 integrados. Temperatura/color y contexto RW Aur V15 siguen en su ámbito.
- WS7: V4/V12/V13 mínimo en #90 abierto, con sus propias reservas/revisión.
- WS6: documentación de estado actualizada aquí. No se completan demo, integrantes, formulario, inventario
  final ni revisión humana en esta tarea; consultar `docs/submission/CHECKLIST.md`.

Los registros fechados de pruebas y ciencia conservan su contexto histórico. Para ejecución/versiones
vigentes usar README, CONTRACT, backend/deploy y la matriz REQUIREMENTS; no tomar una línea histórica
como especificación actual.

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
