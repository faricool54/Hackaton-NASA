# WS5 · Frontend

> Prioridades y alcance: manda [`docs/PLAN.md`](../docs/PLAN.md). Leyenda: ✅ verificado 2026-11-14 ·
> 📄 según documentación · ❓ abierto.

## Objetivo

Que cualquiera **ingrese RA/Dec (o elija uno de los 5 objetivos oficiales) y vea la serie de imágenes SPHEREx de
ese parche como un pequeño video**, con las ayudas que hacen falta para ver movimientos de 1–2 píxeles. Es lo
primero (y casi lo único) que ve el jurado.

## Tus rutas

| WS | Rutas (dueño) |
|---|---|
| **WS5** Frontend | `frontend/**` (salvo `types.ts` → contrato; textos largos de About/hero coordinados con WS6) |
| **CONTRATO** (solo vía PR `contract:`) | `pipeline/errante/models.py`, `pipeline/errante/products.py`, `shared/schema/**`, `frontend/src/api/types.ts`, `data/demo/**` (se regenera con `python scripts/dev.py demo`), `pipeline/tests/test_contract.py` |

Tabla completa: [`tasks/README.md`](README.md). Marcá casillas solo en este archivo.

## Recibís / Entregás

| Recibís | De | Mientras no está |
|---|---|---|
| `Field` por consulta: `GET /api/view?ra&dec&fov_arcmin&det&group` (+ errores 400/422/502/504 en JSON, ver `docs/CONTRACT.md`) | WS4 (con WS1+WS2) | modo fake de WS4 o un `Field` fixture local |
| Golden fields de los 5 objetivos en `data/products` → `public/data/real` (los copia `sync-data`) | WS2 + WS3 | `data/demo` (sintético, con badge) |
| Tipos 0.3.0: `Frame.kind/season/mjd_start/mjd_end/n_inputs/wavelength_min_um/wavelength_max_um/flag_fractions/flags_at_target`, `Field.query`, `Field.target` | PR `contract:` (WS3) | 0.1.0 |
| Posiciones y pm de los objetivos; textos científicos corregidos | WS3 | — |
| `/api/photometry` (P1) | WS4 + WS3 | — |
| Nombre, hero y textos de About | equipo / WS6 | `TODO(WS6)` |

**Entregás:** sitio estático (`npm run build`) que anda **sin backend** (golden fields) y **con backend**
(`/api/view`), con el estado en la URL y modo embed.

## Leé primero

[`AGENTS.md`](../AGENTS.md) · [`docs/PLAN.md`](../docs/PLAN.md) §1, §2, §4 · [`docs/CONTRACT.md`](../docs/CONTRACT.md)
· [`docs/SCIENCE.md`](../docs/SCIENCE.md) §4 (cómo hablar de resultados) ·
[`docs/REVIEW-2026-11-14.md`](../docs/REVIEW-2026-11-14.md) §4 Frontend ·
[`docs/COLLABORATION.md`](../docs/COLLABORATION.md) · `frontend/src/App.tsx` · `frontend/src/api/*.ts` ·
`frontend/src/components/BlinkViewer.tsx` · `frontend/src/pages/*.tsx`.

## Estado actual

**Anda** (leído en el código): React 18 + Vite 5 + TS estricto, sin librerías de UI; router por hash (`#/`,
`#/field/<id>`, `#/about`); modos `static`/`api` con la misma API (`client.ts`); Home con tarjetas;
`BlinkViewer` con play/pausa, slider, velocidad, teclado, marcadores y filtro por detector; espectro SVG; badge
sintético; `image-rendering: pixelated` en los frames (`styles.css:57`). La convención de píxeles de los overlays
es correcta ✅ (contra los PNG y la WCS del demo: diferencia 0,0″).

**Falta / problemas (con línea):**
- Sin entrada RA/Dec (`HomePage.tsx:25` es un TODO) ni estado en la URL (`App.tsx:12` solo parsea el hash;
  `client.ts:26-29` solo lee `dataset` y `mode`). `#/field/x?ra=1` rompe: el id queda `x?ra=1`.
- El detector arranca en `'all'` (`FieldPage.tsx:17`): mezcla λ y stretches distintos por frame (en el demo,
  `vmax` 1,90 vs 2,17 ✅).
- `BlinkViewer.tsx:28,66-75` monta todos los `<img>` a la vez y arranca a reproducir antes de que carguen.
  WISE 0855 tiene 258 frames DR1 ✅.
- Teclado global en `window` (`BlinkViewer.tsx:43-54`): solo ignora `INPUT`, hace `preventDefault` de Espacio
  sobre botones, no filtra modificadores, y con `n = 0` da `NaN`.
- `<FieldPage fieldId={arg}/>` sin `key` (`App.tsx:41`) y sin cancelación de fetch (`FieldPage.tsx:19-29`).
- `getJson` sin timeout, sin chequeo de content-type y sin mostrar `detail` (`client.ts:47-51`). En dev, un JSON
  inexistente devuelve `index.html` con 200 (fallback SPA de Vite ✅) → "Unexpected token <".
- Autoplay sin `prefers-reduced-motion` y velocidad mínima de 150 ms (`BlinkViewer.tsx:28,149`).
- Badge sintético solo en el `h1`; `alt="SPHEREx frame …"` también en datos sintéticos (`BlinkViewer.tsx:70`).
- `vite.config.ts:6` lee `process.env.VITE_BASE` sin `loadEnv`: `.env.local` no cambia `base` (📄 doc de Vite).
- `SkyMap.tsx:15` es un link a `aladin.cds.unistra.fr` con `P/2MASS/color` de alasky (CDS degradado ✅).
- Textos incorrectos: `HomePage.tsx:20` ("Stars stay put": las estrellas cercanas sí se mueven, es el caso de
  Barnard), `AboutPage.tsx:16` (velocidad del Planeta X) y `AboutPage.tsx:20` (promete "detect moving sources").

**La física que manda en el diseño ✅:** en toda la línea de base disponible Barnard se mueve **1,86 px**,
WISE 0855 **1,36 px** y Eps Ind B **1,10 px** (píxel de 6,15″). RW Aur y R Dra no se mueven: cambian de brillo.
Dentro de una temporada cada exposición mide otra λ, así que el brillo "parpadea" sin que nada cambie → el video
por defecto es **por temporada × detector (coadds)**.

## Tareas

P0 en este orden (WS5-1, WS5-2 y WS5-6 no dependen de nadie: arrancá ya sobre `data/demo`).

- [ ] **WS5-1 (P0) Estado en la URL.** El query string es la fuente de verdad:
  `?ra&dec&fov&det&mode&embed=1`, más `?field=<id>` para golden fields (ids de `fields.toml`: `barnards-star`,
  `eps-indi-b`, `wise-0855`, `rw-aurigae`, `r-draconis`) y `?target=<nombre>` resuelto con Sesame de CfA
  (`https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?<nombre>`, con CORS ✅, devuelve pm).
  - RA/Dec en grados o sexagesimal (`ra=08:55:10.831&dec=-07:14:42.53`, y también `08h55m10.831s` /
    `-7d14m42.53s` como en el enunciado); `fov` en arcmin; `det` un entero 1–6 (como `/api/view` en P0);
    `mode=blink|diff`.
  - Cambios de controles → `history.replaceState` (sin recargar ni llenar el historial). `#/field/<id>` queda
    como alias. `embed=1` oculta header y footer; botón "copiar link".
  - Parseo y serialización como funciones puras con tests de `vitest`.
  - *Acepta:* pegar `/?ra=269.44623&dec=4.76870&fov=10&det=3` (Barnard) abre la vista directo; cambiar detector
    o modo actualiza la URL; recargar restaura el mismo estado; tests de decimal, sexagesimal, `+` decodificado
    como espacio y valores fuera de rango.

- [ ] **WS5-2 (P0) Home: caja de coordenadas + 5 chips + FOV.** Una caja "RA Dec o nombre", selector de FOV
  (default ≥ 8′, acordado con WS4) y chips para Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y
  R Draconis. Las coordenadas de los chips salen de WS3: hoy los 5 están en `fields.toml`, centrados en la época
  media de sus datos (pm/plx en comentarios hasta que exista `Field.target`); nunca tipeadas de memoria. Las
  tarjetas de campos curados pasan a segundo plano. Copy del hero: `TODO(WS6)`.
  *Acepta:* cada chip abre su vista con un click; un nombre se resuelve vía Sesame; error amable si Sesame no
  responde; usable a 375 px de ancho.

- [ ] **WS5-3 (P0) Resolver la consulta.**
  - Modo estático: buscar el golden field cuyo footprint (`center` + `size_deg` del manifest) contenga el punto;
    si no hay, explicar que esa coordenada necesita el backend y ofrecer los 5 chips.
  - Modo api: `GET /api/view` con estado de carga visible (la primera llamada tarda de segundos a ~1 min según
    FOV y detectores; la segunda sale de caché), `AbortController` al cambiar de consulta y un mensaje distinto
    para 400 (pedir menos: `hint`), 422 (sin datos SPHEREx en ese punto), 502 y 504 (`detail`). Si el backend
    falla, caer al golden field si existe y ofrecer los 5 objetivos.
  - *Acepta:* sin backend, Barnard abre su golden field (o el demo con badge mientras no exista); con backend, un
    punto cualquiera muestra la carga y después el video; con el backend apagado aparece el mensaje y la UI no
    queda colgada.

- [ ] **WS5-4 (P0) Viewer para movimientos de 1–2 px.** Se puede partir en tres PRs:
  - **4a** Un detector por defecto (el de más temporadas, o el que indique WS3 por objetivo; `?det=` lo pisa);
    precarga con `img.decode()` y "cargando k/N"; autoplay recién con todo cargado; timeline por temporada con el
    Δt real entre cuadros (días/meses, no el índice).
  - **4b** Zoom pixelado ×8 (`image-rendering: pixelated`, overlays dentro del mismo contenedor transformado) y
    pan con mouse y touch; retícula con lectura RA/Dec desde `grid.wcs` (TAN inversa; `x_fits = x + 1`,
    `y_fits = H − y`, ver `docs/CONTRACT.md`).
  - **4c** Círculo de posición predicha en cada cuadro (desde `Field.target`: pm propagado al `mjd` del cuadro;
    el paralaje, < 0,55″, se ignora ✅) y modo **Blink | Diferencia**. La diferencia la produce WS2 como
    `Frame.kind = "difference"`; si el campo no la trae, el botón queda deshabilitado con una explicación.
  - *Acepta:* en Barnard (golden field o `/api/view`) se ve el corrimiento respecto del círculo predicho con
    zoom ×8; tests de la WCS (píxel → cielo → píxel) y de la propagación; probado en desktop y celular.

- [ ] **WS5-5 (P0) Tira de metadata por frame:** `obs_id`, release, detector, λ (o rango
  `wavelength_min_um`–`wavelength_max_um` en coadds), fecha (o `mjd_start`–`mjd_end` y `n_inputs` en coadds),
  % válido (`valid_fraction`), flags (`flag_fractions` / `flags_at_target` cuando existan) y link a IRSA
  (`source_uri`). *Acepta:* cada campo presente se muestra; los ausentes no rompen nada.

- [ ] **WS5-6 (P0) Bugs conocidos.** Teclado acotado al viewer (`tabIndex=0` + `onKeyDown` en el stage, ignorar
  modificadores, nada con `n < 2`); `<FieldPage key={arg}>` + cancelación de fetch; `getJson` con
  `AbortSignal.timeout(...)`, chequeo de `content-type` y lectura de `body.detail`; `mode` validado con whitelist;
  `prefers-reduced-motion` → arranca en pausa, e intervalo mínimo ≥ 334 ms (≤ 3 destellos/s); badge sintético
  dentro del stage + `alt` condicional; `VITE_BASE` con `loadEnv`.
  *Acepta:* Espacio activa el botón con foco; cambiar de campo resetea selección y detector; un JSON inexistente
  muestra un error claro (no "Unexpected token <"); un build con `VITE_BASE=/sub/` en `.env.local` genera assets
  bajo `/sub/`.

- [ ] **WS5-7 (P0) Textos de Home y About corregidos** con WS3 (ciencia) y WS6 (redacción del equipo, en
  inglés): sin "Stars stay put", velocidad del Planeta X correcta, sin prometer detección automática, por qué el
  video va por temporada (λ), y que Eps Ind B ("a pair of brown dwarfs") se ve como **una sola fuente** con
  píxeles de 6,15″. Créditos solo en texto. *Acepta:* WS3 aprueba el PR.

- [ ] **WS5-8 (P1) Aladin Lite de contexto.** `https://cdn.jsdelivr.net/npm/aladin-lite@3.8.2/dist/aladin.js`
  (200, 2,39 MB ✅) cargado lazy en un panel colapsable. Surveys de IRSA con CORS ✅:
  `https://irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color`, `.../data/hips/CDS/AllWISE/RGB-W4-W2-W1` y el cubo
  SPHEREx DR1 `.../data/hips/SPHEREx/spherex_allsky_cube` (102 cortes ✅; que Aladin lo renderice es ❓). Nunca
  alasky ni `aladin.cds.unistra.fr` (404 ✅). Si Aladin falla, el blink sigue andando.
  *Acepta:* el script se baja solo al abrir el panel; con `*.unistra.fr` bloqueado en DevTools sigue andando.
- [ ] **WS5-9 (P1) Overlay Gaia DR3 sobre el blink.** VizieR de CfA
  (`https://vizier.cfa.harvard.edu/viz-bin/votable?-source=I/355/gaiadr3&-c=<ra> <dec>&-c.rs=<radio>`, 200 con
  CORS ✅); propagar cada estrella desde la época de Gaia DR3 (2016.0 📄) al `mjd` de cada cuadro y dibujarla con
  la WCS del campo; `ovl=gaia` en la URL. Para WISE 0855 la referencia sugerida es CatWISE (vía backend, WS4-10),
  no Gaia. *Acepta:* en Barnard el marcador Gaia acompaña a la estrella cuadro a cuadro.
- [ ] **WS5-10 (P1) Click → espectro.** Click en un píxel → `/api/photometry?ra&dec` → `SpectrumChart` con un
  color por temporada (no mezclar tiempo con λ). *Acepta:* RW Aur o R Dra muestran espectros por temporada.
- [ ] **WS5-11 (P1) Curva de luz** (flujo vs MJD por detector) para las variables, con el mismo patrón SVG.
  *Acepta:* R Dra muestra puntos por temporada con barras de error.
- [ ] **WS5-12 (P1) Toggle temporada / exposición** (`group=exposure`): exposiciones individuales para asteroides
  dentro de una temporada, con el aviso visible de que el brillo cambia por λ.
  *Acepta:* el toggle cambia `group` en la URL y en el pedido a `/api/view`; en modo exposición se ve el aviso.
- [ ] **WS5-13 (P2)** Exportar GIF del blink. *Acepta:* el GIF reproduce los mismos cuadros del viewer y lleva
  el badge si los datos son sintéticos.
- [ ] **WS5-14 (P2)** Falso color con coadds D1/D3/D6 (de WS2) y/o slider de los 102 canales del cubo HiPS.
  *Acepta:* en un golden field se ve el falso color (o el slider cambia de canal) sin romper el blink.
- [ ] **WS5-15 (P2)** Accesibilidad fina: área de click y foco en marcadores (hoy `fill: none` y trazo de 2 px,
  `styles.css`), caption debajo de la imagen. *Acepta:* Lighthouse (Accessibility) ≥ 90 y los marcadores se
  alcanzan con Tab.

## DROP

- Página "Límites" (inyección-recuperación) y widget "¿Lo vería SPHEREx?".
- Reporte de candidato como página propia (`#/field/<id>/c/<cand>`): lo reemplaza la URL con coordenadas.
- Mapa con la región del Planeta Nueve.
- Onboarding guiado de 3 pasos sobre candidatos: alcanza con textos cortos en la vista.

## Gotchas

- **`?mode=` ya existe:** `client.ts:29` lo usa para `static|api`. El `mode` nuevo es del viewer (`blink|diff`).
  Mové la fuente de datos a `?source=api|static` (`frontend/README.md` también), seguí aceptando `mode=api|static` por
  compatibilidad (README y `docs/ARCHITECTURE.md` §4 ya anuncian el cambio a `?source=`).
- En el query string `+` se decodifica como espacio: `dec=+04:41:36` llega como ` 04:41:36`. El parser lo tolera y
  al serializar no se usa `+`.
- Sesame devuelve J2000 + pm. Las estrellas cercanas ya no están ahí: Barnard queda ~4,5′ de su posición J2000 y
  WISE 0855 ~125,7″ de la coordenada del enunciado (que es de ~2010) ✅. Propagá a la época de los datos antes de
  centrar.
- No restes PNG de 8 bits en canvas: cada frame tiene su propio stretch ✅. La diferencia la hace WS2.
- `image-rendering: pixelated` no aplica si dibujás en canvas sin `imageSmoothingEnabled = false`.
- Aladin Lite 3.8.2 trae hardcodeados `vizier.unistra.fr` (en `catalogFromVizieR`) y alasky para las surveys por
  defecto ✅: pasá URLs explícitas y usá `catalogFromURL` o `fetch` + `addSources`.
- En modo api el default es `http://localhost:8000` (`client.ts:30`): el deploy necesita `VITE_API_BASE`.
- `vitest` corre con `environment: 'node'` (`vite.config.ts:9`): testeá funciones puras (parseo, WCS,
  propagación); no agregues jsdom sin necesidad.
- Datos sintéticos: badge **siempre** visible, también en embed y capturas. "unconfirmed" ≠ "discovery".
- Sin branding NASA en la UI (logos, banderas, parche de la misión): créditos solo en texto.
- Sin librerías pesadas nuevas; Aladin por CDN y lazy está bien. ❓ si el host del deploy permite embeber en
  `<iframe>` (cabeceras `X-Frame-Options`): probarlo con la URL pública.

## Dependencias

- **Ya, sobre `data/demo`:** WS5-1, WS5-2 (el frontend no lee `fields.toml`: copiá sus centros a una constante
  con comentario de origen, o tomalos del manifest cuando existan los golden fields), WS5-6, y la parte de 4a/4b
  que no necesita datos nuevos.
- **`/api/view`:** modo fake de WS4 o un `Field` fixture. Params y errores ya están propuestos en
  `docs/CONTRACT.md`; en el PR de contrato (sáb ~15:00) se fijan con WS4 la ruta de los PNG de vistas y el FOV
  por defecto y tope.
- **Contrato 0.3.0 (sáb 15:00):** hasta el merge, código contra 0.1.0. Si necesitás un campo antes, pedile a WS3
  que adelante el PR; no edites `types.ts` fuera de un PR `contract:`.
- **Posición predicha y chips:** necesitan `Field.target` / `fields.toml` de WS3 (dejalo detrás de
  `if (field.target)`). **Diferencia:** necesita frames `kind = "difference"` de WS2.

## Prompt de arranque

> Sos el agente del workstream WS5 (frontend) del repo de NASA Space Apps 2026, reto "Planet X and SPHEREx".
> Leé `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACT.md`, `docs/SCIENCE.md` §4 y `tasks/WS5-frontend.md`.
> Trabajá SOLO en `frontend/` (salvo `src/api/types.ts`, que es contrato: si necesitás un campo nuevo, proponelo
> como PR `contract:` aparte). Empezá por WS5-1 (estado en la URL, con parseo sexagesimal y tests) y seguí los P0
> en orden. Levantá `python scripts/dev.py web` y mirá la app en el navegador, en desktop y en ancho de celular
> (375 px), antes de decir que algo funciona. Corré `python scripts/dev.py check` (Windows:
> `py scripts/dev.py check`), mostrame el diff y cómo lo probaste antes de commitear, y commiteá como
> `ws5: verbo + qué` con el trailer `Co-Authored-By:` del agente.
