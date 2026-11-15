# WS7 · Sistemas 3D (modelos de los objetos que seguimos)

**Objetivo:** que cada objeto que mostramos en las imágenes SPHEREx se pueda **abrir en 3D**: ver el cuerpo,
ver su sistema animado (órbitas, pulsaciones) y **entrar a cada planeta/estrella** con su ficha de datos. Buen
diseño y representación fiel a los datos, siempre etiquetada como modelo.

**Alcance y prioridad:** extensión **P2 del equipo**, no requisito R01–R05 ni sustituto de imágenes reales.
Aplican las guías de entrega/evaluación en `docs/SUBMISSION_GUIDE.md` y `docs/JUDGING_GUIDE.md`: parámetros
con fuente y verificación, atribución SI, medios/permisos y textos públicos en inglés. Un modelo de cada
blanco no completa los cinco ensayos. Verificar valores es condición para anunciarlos como medidos.

**Tus rutas:** `pipeline/errante/systems/`, `frontend/src/three/`, `frontend/src/components/SystemViewer.tsx`,
`frontend/src/components/BodyPanel.tsx`, `frontend/src/pages/SystemsPage.tsx`, `frontend/src/pages/SystemPage.tsx`,
`data/demo/systems/` (regenerado con `make demo`), `docs/VISION_3D.md`.

**Recibís:** objetos de los campos (WS3: `config/fields.toml`, `known.json`), candidatos (WS2/WS3).
**Entregás:** `<root>/systems/<id>.json` (contrato `SystemModel`) + las vistas 3D.

**Leé primero:** `docs/VISION_3D.md`, `docs/CONTRACT.md`, `pipeline/errante/models.py` (sección "3D systems"),
`pipeline/errante/systems/catalog.py`, `frontend/src/three/SystemScene.ts`.

## Estado actual
- ✅ Contrato `SystemModel` (schema 0.2.1, con `Orbit.quality`), `Manifest.systems`, `GET /api/systems/{id}`, `errante systems`.
- ✅ 5 sistemas de los objetivos de prueba, **verificados** (WS7-2) contra NASA Exoplanet Archive, SIMBAD, Gaia DR3,
  VizieR y papers + 1 sintético ligado a `demo-ecliptic`.
- ✅ `#/systems`, `#/system/<id>[/<cuerpo>]`: órbitas keplerianas animadas, colores por temperatura, texturas
  procedurales, disco, pulsación, clic/etiqueta → la cámara entra y sigue al cuerpo, ficha con fuente/verified,
  distancias comprimidas/lineales, enlaces campo ⇄ sistema, responsive.
- 🔶 Rama `ws7/procedural-3d` (14/11, sin PR a `main` todavía): cuerpos derivados de física y catálogo con tier por
  propiedad, SPHEREx IR por defecto, esferas lisas en los blancos reales (texturas procedurales solo en el sistema
  sintético), modo **Dataset time** y panel "Where SPHEREx should see it". Detalle en `docs/VISION_3D.md`
  ("Derivaciones, niveles (tiers) y mapeos de visualización" y "Tiempo del dataset SPHEREx").
- ⛔ Órbitas reales de asteroides, modelos de forma, vista de movimiento por el espacio.

## Tareas

- [ ] **WS7-1 (P2) Integración con el flujo principal**: que desde un candidato/objeto conocido del blink se pueda
  ir a su cuerpo 3D (`Body.candidate_id`; coordinar con WS5 para el botón en `CandidatePanel`) y agregar campos
  `epsilon-indi`, `r-draconis`, `rw-aurigae` a `config/fields.toml` (con WS3) para que todos los sistemas
  tengan su campo SPHEREx. Los presets/ensayos de esos blancos son P0 de WS3-3/9 y se pueden completar sin 3D;
  no copiar coordenadas del catálogo ilustrativo sin fuente/época/propagación verificadas.
- [x] **WS7-2 (P2; requisito para afirmar valores verificados) Verificar valores**: implementar `sources.exoplanet_archive_system` y `sources.simbad_star`
  (tests `network`), reemplazar los valores de `catalog.py` y poner `verified=True` **solo** en lo comprobado,
  con la fuente exacta (tabla/URL/paper). Corregir lo que esté mal. Criterio: badge "UNVERIFIED VALUES"
  desaparece en los sistemas verificados.
- [ ] **WS7-3 (P2) Asteroides reales**: `sources.sbdb_orbit` → para cada candidato `known` de un campo real, crear
  un sistema heliocéntrico (Sol + Tierra + Júpiter + el asteroide) con su órbita real y la posición en la fecha
  de cada frame. Mostrar "dónde estaba la Tierra/SPHEREx cuando lo vio".
- [ ] **WS7-4 (P2) Pulido visual**: limb darkening y granulación en estrellas (shader simple), glow que respire en
  la Mira (R Dra) siguiendo la curva de luz, bandas/tormentas en gigantes, inclinación y anillos si hay datos,
  transición de cámara más cinematográfica, leyenda de escala. Lighthouse sin regresiones.
  - [x] Cambiar el selector de velocidad del visor 3D por un slider accesible con el estilo del playback de frames.
  - Avance en la rama `ws7/procedural-3d` (14/11; typecheck, vitest y build en verde en la última revisión):
  - [x] Limb darkening y enrojecimiento del borde con una atmósfera gris de Eddington (MODEL), en visible, en IR
    (centro de cada canal) y en D1–D6 (`astro.ts`, `colorModes.ts`, `starMaterial.ts`).
  - [x] Celdas de convección solo donde son resolubles (< 64 a lo ancho; hoy solo R Dra): escala 10 H_p (MODEL),
    contraste ±15 % (ILLUSTRATIVE), renovación en tiempo de modelo. No observadas en R Dra: solo con el toggle
    class-typical (apagado por defecto), como pide `VISION.md`.
  - [x] Glow de la Mira que sigue la curva V en modo visible (fijo en los modos SPHEREx: no hay curva IR modelada);
    radio ±10 % class-typical (Ireland+2004, Woodruff+2004), en fase con la luz solo por display.
  - [x] Modos de color: SPHEREx IR falso color por defecto (chip FALSE COLOUR), visible CIE 1931 y D1–D6 en gris,
    con leyendas que dicen qué no se modela (exceso IR de RW Aur, H₂O/CO y TiO de la Mira, < 2500 K cualitativo).
  - [x] Superficies: esferas lisas en los cinco blancos; toggle "show class-typical features (illustrative)" apagado
    por defecto (solo ε Ind Ba y ε Ind Ab, con fuentes de clase). El sintético conserva sus texturas.
  - [x] Spin solo desde un período verificado (Barnard, 145 ± 15 d) o la regla de marea (Barnard b–e, THEORY).
  - [x] Ficha "How this body is drawn" / "At SPHEREx scale": valor, método, cita y tier de cada propiedad
    (`appearanceNotes.ts`, carga diferida).
  - [x] Chunk principal: los helpers del visor y de la ficha cargan bajo demanda (`viewerKit.ts`, `DatasetTimeline`,
    `appearanceNotes`); `index-*.js` 212.8 kB (gzip 69.5) en el último build revisado. Lighthouse sin medir.
  - [ ] Bandas/tormentas en gigantes con datos medidos: ningún blanco tiene mapa de superficie ni amplitud de
    modulación verificada (S5 queda solo como toggle ilustrativo).
  - [ ] Inclinación y anillos si hay datos; transición de cámara más cinematográfica; leyenda de escala.
  - [ ] Revisión visual en el navegador (escritorio y 375 px) y Lighthouse.
- [ ] **WS7-5 (P2) "Moverse por el espacio"**: vista de vecindario solar con `SpaceMotion` (paralaje, movimiento
  propio, velocidad radial): ver Barnard, WISE 0855 y Eps Indi moviéndose en 3D en miles de años, y por qué eso
  se ve como desplazamiento en las imágenes SPHEREx.
- [ ] **WS7-6 (P2) Modelos de forma**: `appearance.model = "mesh"` + `mesh_url` (glTF) con `GLTFLoader`; fuentes:
  NASA 3D Resources, DAMIT. Archivos < 1 MB, licencia anotada.
- [ ] **WS7-7 (P2) Planeta Nueve hipotético**: sistema solar externo con Neptuno, TNOs extremos y una órbita
  hipotética (Brown & Batygin 2021: a = 380 +140/−80 AU, q = 300 +85/−60 AU, i = 16 ± 5°; dibujar la mediana y
  sombrear la banda 1σ de a) con `Orbit.quality = "hypothetical"` (violeta + aviso), conectado con el
  widget "¿Lo vería SPHEREx?" de WS3.
- [ ] **WS7-8 (P2) Espectro en 3D**: color del cuerpo calculado desde el espectro SPHEREx medido (si WS3 lo tiene)
  en lugar de la temperatura de catálogo, con explicación.
- [ ] **WS7-9 (P2) Tiempo del dataset SPHEREx** (2025-04 → 2026-11): que el reloj de la escena corra sobre las
  fechas reales de las pasadas SPHEREx de cada blanco, sin cambio de contrato. Detalle en `docs/VISION_3D.md`.
  - [x] M4: reloj "Dataset time" junto a "Free-running"; ventanas de archivo de los cinco blancos
    (`spherexCoverage.ts`, de DATA.md §3.0 y RECON §4.2); línea de tiempo con pasadas rayadas, "Pass N",
    marcador "today" y marcas por detector para frames construidos (sintético); línea "Real epoch / Arbitrary phase".
  - [x] M5: Barnard b–e en la fase del t0 de Basant+2025 (Tabla 3), leído como conjunción inferior, con la flecha
    "toward Earth" y la advertencia en nota, ficha y "On this date". Implementado; **falta la aceptación del equipo**.
  - [x] S2: arcos de ±2σ de fase para órbitas fechadas; anillos, atenuación y "(phase unknown)" para las demás, con
    la razón y la fuente de cada fase desconocida.
  - [x] S3: R Dra en la fase V predicha por la efeméride VSX (HJD 2457370.00, P 246.12 d), banda ±6.6 d (RMS del
    O−C); RW Aur A/B como irregulares; una sola regla de variabilidad (`variabilityPhase`).
  - [x] S4: panel "Where SPHEREx should see it" (movimiento espacial + paralaje sobre la grilla de 6.15″, un punto
    por pasada), que marca también la fecha del 3D en Dataset time.
  - [x] Tests: `ephemerides.test.ts`, `spherexCoverage.test.ts`, `skyTrack.test.ts` (vectores de RECON §4.1,
    ERFA `epv00`) y pytest (Basant b → Tc de González Hernández+2024; valores VSX iguales en `catalog.py` y en la
    tabla del frontend).
  - [ ] Aceptación del equipo de la lectura de t0 como conjunción (M5); si no se acepta, revertir M5.
  - [ ] Revisión visual en el navegador: arcos y anillos de 4 px, etiqueta de la flecha, atenuación, tope de 60 s,
    filas del panel del cielo a 375 px.
  - [ ] Línea "On this date: phase X ± σ" en la ficha (`bodyFormat.ts` / `BodyPanel.tsx`); hoy está solo en el visor.
  - [ ] Banda de R Dra con un término de Eddington–Plakidis con fuente, y contraste con los máximos AAVSO 2025–2026.
  - [ ] Pasar de ventanas de archivo a frames reales cuando existan campos construidos de los cinco blancos
    (hoy `data/demo` solo tiene campos sintéticos).
  - [ ] Campos de contrato para épocas y errores (`epoch_err_days`, `spherex_passes`, astrometría de ε Ind B):
    diferidos, hoy en tablas WS7 del frontend; solo vía PR `contract:` del dueño del contrato.

## Pendiente para coordinación

Lo que WS7 no puede cerrar solo (14/11/2026):

- **(a) Uso de IA (regla 14 / S08)**, para quien coordina `AI_USAGE.md` y `docs/submission/ai-usage.json` (WS7 no
  edita esos archivos): el 3D procedural de WS7, el modo Dataset time y el panel del cielo (código, tests,
  investigación bibliográfica y esta documentación) se escribieron con Claude Code en la sesión del 14/11; la
  revisión humana está a cargo de DankoLiv. El plan de trabajo lo propuso el flujo de Claude Code y DankoLiv
  eligió las decisiones de diseño (IR por defecto, solo superficies medidas + toggle ilustrativo, sin cambio de
  contrato). No registrar la revisión como terminada hasta que se haga.
- **(b) M5 necesita aceptación del equipo:** leer el t0 de Basant+2025 como conjunción inferior es una decisión de
  criterio (el paper dice periastro; el código de juliet/RadVel y el acuerdo con González Hernández+2024 apoyan la
  conjunción). Si no se acepta: volver Barnard b–e a `epoch_mjd = null` en `catalog.py`, quitarlas de
  `ORBIT_EPHEMERIDES` y ajustar sus tests y el JSON demo. Se puede consultar a los autores.
- **(c) JSON de `data/demo/systems/` a coordinar con el dueño del contrato:** `scripts/owners.py` los marca como
  `contract` y COLLABORATION.md dice que `data/demo/` se regenera solo en PRs `contract:`. Cambian respecto de
  `main`: `barnards-star.json` (épocas M5, `Fact` "Reference time t0", períodos con error, rotación, notas),
  `r-draconis.json` (masa class-typical y `field_id`; la nota de dos relojes está sin commitear),
  `epsilon-indi.json` (etiquetas de los `Fact` de Teff, `field_id`), `rw-aurigae.json` (`Fact` "Distance",
  `field_id`) y `manifest.json` (`field_id` de tres sistemas; `generated_at`). `errante demo` también reescribe
  `data/demo/fields/*` y `manifest.json` con ruido (`built_at`, dígitos finales): restaurarlos antes de commitear.
- **(d) Pendientes que reportaron los agentes de esta tanda y no se hicieron:**
  - revisión visual en el navegador: el panel del navegador estaba oculto (0×0), así que arcos, flechas, atenuación,
    rim y modos D1–D6 no se vieron; solo se leyó el texto de las páginas;
  - badge de página "FALSE COLOUR · MODEL" en `SystemPage.tsx`: lo reemplaza el chip dentro del visor;
  - la ficha (`BodyPanel`) no ve el modo de color ni el toggle activos del visor: lista todos los modos;
  - parches de amplitud medida para S5: ningún cuerpo del demo tiene una amplitud verificada;
  - Metchev et al. 2015 (L3–T8) podría justificar un patrón en ε Ind Bb (T6); no se revisó, así que Bb queda sin
    patrón;
  - citas no re-descargadas en esta tanda: fuentes de `SURFACE_NOT_DRAWN_NOTES` (Esplin 2016, Wilson 2025,
    Miles 2026, Hitchcock 2020, Chen 2022, tomadas de la investigación del 14/11), Matthews 2024 (del `Fact` del
    catálogo), Astronomical Almanac / Meeus (comprobados numéricamente contra ERFA `epv00`) y Feast 2009;
  - ε Ind B: la astrometría del panel del cielo es una constante copiada de RECON §4.1, no re-consultada en Gaia;
    reemplazarla si el contrato suma un `target_body` o la astrometría de B;
  - WISE 0855: el panel usa Kirkpatrick+2021, que queda a 0.31″ (0.05 px) del ajuste propio de RECON §4.1; elegir
    uno con WS3 para los recortes;
  - los puntos de cada pasada están a mitad de la ventana: sin `MJD-AVG` por frame de los blancos reales;
  - R Dra: las fechas VSX no se corrigen por la media del O−C (−4.7 d; la banda de 6.6 d la incluye) y no hay
    término de Eddington–Plakidis;
  - Barnard: para errores asimétricos se usó el lado mayor y para e la σP del paper (0.0028 d), así que e va de
    23.2° a 31.0° (con 0.003 d serían 23.6° a 32.3°);
  - ε Ind Bb: un T0 derivado de la Tabla 3 de Chen+2022 no se usa (no publicado); Bb y Ab quedan como anillos.
- **(e) Resuelto:** las celdas de convección de R Dra pasaron detrás del toggle class-typical (apagado por
  defecto); la vista por defecto es una esfera lisa, como pide `VISION.md`.

## Reglas
- Toda vista 3D muestra "3D MODEL · NOT AN IMAGE" y la `representation_note`. Nada de presentarlo como imagen real.
- Nunca inventar parámetros: si no hay dato, no se dibuja (o se dibuja marcado como supuesto, en amarillo).
- three.js se carga solo en las páginas 3D (dynamic import). No agregar React Three Fiber u otras capas sin
  justificarlo en el PR.
- Cambios a `SystemModel` = cambio de contrato (`contract:` PR, `make schema`, `types.ts`).
- La escena no fija posiciones/épocas para construir campos reales hasta verificarlas con WS3. Un radio
  exagerado, color aproximado, fase arbitraria o variabilidad ilustrativa deben seguir identificados como tales.
- Los agentes/roles no son integrantes adicionales: la sede local admite como máximo seis personas.

## Prompt de arranque

> Sos el agente del workstream WS7 (sistemas 3D) del repo Errante para NASA Space Apps 2026. Leé `AGENTS.md`,
> `docs/VISION_3D.md`, `docs/CONTRACT.md` y `tasks/WS7-3d-systems.md`. Trabajá SOLO en las rutas de WS7. Corré
> `make web` y abrí `#/systems`. Empezá por WS7-2 (verificar valores contra NASA Exoplanet Archive / SIMBAD, con
> tests `network`) y WS7-1. Si un servicio no responde desde tu entorno, no inventes valores: dejalos
> `verified=False`. Verificá en el navegador (desktop y celular), corré `make check` y mostrame el diff antes de
> commitear.
