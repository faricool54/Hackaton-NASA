# WS7 · Sistemas 3D (modelos de los objetos que seguimos)

**Objetivo:** que cada objeto que mostramos en las imágenes SPHEREx se pueda **abrir en 3D**: ver el cuerpo,
ver su sistema animado (órbitas, pulsaciones) y **entrar a cada planeta/estrella** con su ficha de datos. Buen
diseño y representación fiel a los datos, siempre etiquetada como modelo.

**Alcance y prioridad:** extensión **P2 del equipo**, no requisito R01–R05 ni sustituto de imágenes reales.
Aplican las guías de entrega/evaluación en `docs/SUBMISSION_GUIDE.md` y `docs/JUDGING_GUIDE.md`: parámetros
con fuente y verificación, atribución SI, medios/permisos y textos públicos en inglés. Un modelo de cada
blanco no completa los cinco ensayos. Verificar valores es condición para anunciarlos como medidos.

**Prioridad actualizada (15/11, WS7):** según `docs/VISION.md` y `docs/PARALLEL_PLAN.md` (§8 y filas V4, V12–V14), el
3D construido desde mediciones es **P1** (V4 era P0: bloqueaba la entrega). V14 (3D para un click arbitrario) queda
como trabajo futuro si el equipo acepta D7; WS7-3/5/6/7 siguen P2 y la propuesta D10 los congela hasta después del
envío.

**Tus rutas:** `pipeline/errante/systems/`, `frontend/src/three/`, `frontend/src/components/SystemViewer.tsx`,
`frontend/src/components/BodyPanel.tsx`, `frontend/src/pages/SystemsPage.tsx`, `frontend/src/pages/SystemPage.tsx`,
`data/demo/systems/` (regenerado con `make demo`), `docs/VISION_3D.md`.
Desde V13 además: `pipeline/errante/systems/targets.toml`, `pipeline/errante/systems/inputs/`, los registros de uso de IA
`pipeline/errante/systems/ai-usage.json` y `frontend/src/three/ai-usage.json`. Los JSON de sistemas se regeneran con
`errante systems --out data/demo` y `errante systems --out data/products --real-only` (no con `errante demo`, que
reescribe también los campos sintéticos); `data/demo/` es camino de contrato y `data/products/` de WS2, así que la
guardia de ownership los marca (precedentes #47 y #64, declarados en el PR).

**Recibís:** objetos de los campos (WS3: `config/fields.toml`, `known.json`), candidatos (WS2/WS3).
**Entregás:** `<root>/systems/<id>.json` (contrato `SystemModel`) + las vistas 3D.

**Leé primero:** `docs/VISION_3D.md`, `docs/CONTRACT.md`, `pipeline/errante/models.py` (sección "3D systems"),
`pipeline/errante/systems/catalog.py`, `frontend/src/three/SystemScene.ts`.

## Estado actual
- ✅ Contrato `SystemModel` (0.2.0 en #1; `Orbit.quality` y `Orbit.note` en 0.2.1, #8; `main` va por 0.7.0 y WS7 no
  lo cambió después), `Manifest.systems`, `GET /api/systems/{id}`, `errante systems`.
- ✅ 5 sistemas de los objetivos de prueba, **verificados** (WS7-2) contra NASA Exoplanet Archive, SIMBAD, Gaia DR3,
  VizieR y papers + 1 sintético ligado a `demo-ecliptic`.
- ✅ `#/systems`, `#/system/<id>[/<cuerpo>]`: órbitas keplerianas animadas, colores por temperatura, texturas
  procedurales, disco, pulsación, clic/etiqueta → la cámara entra y sigue al cuerpo, ficha con fuente/verified,
  distancias comprimidas/lineales, enlaces campo ⇄ sistema, responsive.
- ✅ #47 (mergeado el 15/11, rama `ws7/procedural-3d`): cuerpos derivados de física y catálogo con tier por
  propiedad, SPHEREx IR por defecto, esferas lisas en los blancos reales (texturas procedurales solo en el sistema
  sintético), modo **Dataset time** y panel "Where SPHEREx should see it". Detalle en `docs/VISION_3D.md`
  ("Derivaciones, niveles (tiers) y mapeos de visualización" y "Tiempo del dataset SPHEREx").
- ✅ #64 (15/11): los cinco sistemas publicados en el dataset real (`data/products/systems/`), cada uno con el
  `field_id` de su campo.
- ✅ Revisión científica de WS3 del 3D mergeado (#65, `docs/SCIENCE.md`, "Revisión científica del 3D (WS7, #47)"): 17
  filas, todas de WS7; el estado de cada una está en [Revisión del 3D](#revisión-del-3d-65-y-revisión-de-textos).
- 🔶 Rama `ws7/measured-3d` (15/11, V13 con V4 y V12, sin PR todavía): sin valores elegidos a mano, lo desconocido se
  dibuja como desconocido, sin toggle class-typical, capa de mediciones (snapshots del contexto de WS3 + registro) y
  chips de origen en la ficha. Ver WS7-10 y `docs/VISION_3D.md` ("Capa de mediciones (V13)").
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
  - Avance mergeado en #47 (rama `ws7/procedural-3d`; typecheck, vitest y build en verde en la última revisión), con
    los cambios de V13 (rama `ws7/measured-3d`) anotados en cada ítem:
  - [x] Limb darkening y enrojecimiento del borde con una atmósfera gris de Eddington (MODEL), en visible, en IR
    (centro de cada canal) y en D1–D6 (`astro.ts`, `colorModes.ts`, `starMaterial.ts`).
  - [x] Celdas de convección solo donde son resolubles (< 64 a lo ancho; hoy solo R Dra): escala 10 H_p (MODEL),
    contraste ±15 % (ILLUSTRATIVE), renovación en tiempo de modelo. No observadas en R Dra: solo con el toggle
    class-typical (apagado por defecto), como pide `VISION.md`.
    **V13: quitadas de los blancos reales** junto con el toggle (y R Dra ya no tiene el radio ni la masa que las
    dimensionaban); el cálculo queda solo para el sistema sintético.
  - [x] Glow de la Mira que sigue la curva V en modo visible (fijo en los modos SPHEREx: no hay curva IR modelada);
    radio ±10 % class-typical (Ireland+2004, Woodruff+2004), en fase con la luz solo por display.
    **V13 (V12b, D3 tomada por WS7, a confirmar por el equipo): radio constante**; solo el brillo sigue la curva V de
    catálogo, y la leyenda remite al panel "Light curve" de la página del campo (WS5, #83) para la curva SPHEREx.
  - [x] Modos de color: SPHEREx IR falso color por defecto (chip FALSE COLOUR), visible CIE 1931 y D1–D6 en gris,
    con leyendas que dicen qué no se modela (exceso IR de RW Aur, H₂O/CO y TiO de la Mira, < 2500 K cualitativo).
  - [x] Superficies: esferas lisas en los cinco blancos; toggle "show class-typical features (illustrative)" apagado
    por defecto (solo ε Ind Ba y ε Ind Ab, con fuentes de clase). El sintético conserva sus texturas.
    **V13: toggle quitado** (pedido de DankoLiv: "quitar el detalle de superficie inventado"), con su chip, sus bandas y
    sus textos; el sintético conserva sus texturas, rotuladas SYNTHETIC.
  - [x] Spin solo desde un período verificado (Barnard, 145 ± 15 d) o la regla de marea (Barnard b–e, THEORY).
  - [x] Ficha "How this body is drawn" / "At SPHEREx scale": valor, método, cita y tier de cada propiedad
    (`appearanceNotes.ts`, carga diferida).
  - [x] Chunk principal: los helpers del visor y de la ficha cargan bajo demanda (`viewerKit.ts`, `DatasetTimeline`,
    `appearanceNotes`); `index-*.js` 212.8 kB (gzip 69.5) en el último build revisado. Lighthouse sin medir.
  - [ ] Bandas/tormentas en gigantes con datos medidos: ningún blanco tiene mapa de superficie ni amplitud de
    modulación verificada (el toggle ilustrativo S5 se quitó en V13: sin datos medidos no se dibujan).
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
  - Prioridad P1 según `PARALLEL_PLAN.md` (la parte "después" de V13). Depende de **V18 de WS3** (ajuste de Teff desde el
    espectro SPHEREx; `color_class` en `pipeline/errante/science/spectra.py` sigue sin implementar), que no existe.
    Solo ε Ind B (mezcla Ba+Bb) y WISE 0855 (D5/D6) tienen espectros SPHEREx sin saturar.
  - [ ] Cuando WS3 publique la Teff ajustada: agregarla como valor con fuente "SPHEREx …" en la capa de mediciones
    (WS7-10) y dibujar el color con ella; hasta entonces el color es de catálogo, rotulado "catalog, not measured by
    SPHEREx".
  - [ ] Igual para el radio desde la luminosidad SPHEREx integrada + distancia Gaia (tampoco existe en WS3).
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
    El contraste ya está hecho (registro de R Dra, 818 observaciones AAVSO): V13 toma su O−C (−3.8, −14.8, −3.1 d) para
    la banda de **9.0 d** (variante corta de V12a). Falta la variante completa (fechar la fase con los máximos medidos
    dentro de la ventana SPHEREx, banda de ±3 d) y el término de Eddington–Plakidis.
  - [x] Pasar de ventanas de archivo a frames reales cuando existan campos construidos de los cinco blancos:
    `errante systems --out data/products --real-only` (15/11) publica los cinco sistemas en el dataset real, cada
    uno con el `field_id` de su campo; en `?dataset=real` el "Dataset time" marca los frames construidos
    ("frames built in this dataset (field …)") y la página del sistema y la del campo se enlazan en los dos sentidos
    (verificado en el navegador). `data/demo` sigue solo con campos sintéticos. El enlace al campo nombra su
    blanco con el nombre del manifiesto ("See Epsilon Indi B in SPHEREx images →"): el campo de ε Ind es de B
    (0,15°, centrado en Ba+Bb) y no contiene a A, cuyas coordenadas muestra la página (`three/fieldLink.ts`).
  - [ ] Campos de contrato para épocas y errores (`epoch_err_days`, `spherex_passes`, astrometría de ε Ind B):
    diferidos, hoy en tablas WS7 del frontend; solo vía PR `contract:` del dueño del contrato.
- [ ] **WS7-10 (P1) 3D desde mediciones (V13 de `PARALLEL_PLAN.md`, con V4 y V12)**: migrar los presets (parámetros a
  mano y texturas procedurales) a modelos construidos desde mediciones según la tabla de `docs/VISION.md`, quitar el
  detalle de superficie inventado y dejarlo escalable para sumar datos. Rama `ws7/measured-3d` (15/11, sin PR todavía).
  Detalle en `docs/VISION_3D.md` ("Capa de mediciones (V13)" y "Diferencias con `VISION.md`").
  - [x] Quitar los valores elegidos a mano de `catalog.py`: Teff 3000 K, radio 250 R☉ y masa class-typical ~1 M☉ de
    R Dra (con sus `Fact` y la cita de Feast 2009); radio 0.9 R♃ de ε Ind Ba y Bb; masa 5 M♃ de WISE 0855. Quedan
    `null` y se explican en `provenance.notes`. El rango de Teff de R Dra y el de masa de WISE 0855 siguen como `Fact`.
  - [x] Radio de RW Aur A conservado como valor **derivado** (Herczeg & Hillenbrand 2014 a la distancia Gaia, 1.34 R☉),
    rotulado "(derived …)" y unverified: RW Aur sigue con el badge UNVERIFIED VALUES. No se cambió ningún otro valor
    dibujado (ni la Teff de ε Ind A ni distancias).
  - [x] Capa de mediciones: snapshots congelados del contexto de WS3 en `pipeline/errante/systems/inputs/objects/`
    (Barnard's Star, eps Ind B, WISE 0855, R Dra, RW Aur; grabados offline desde los fixtures de WS3), registro
    `targets.toml` y `measured.py` (facts "seen by SPHEREx" del bloque A5, facts de cruce de catálogo rotulados
    "catalog, not measured by SPHEREx", nota "Not measured, so not drawn" por cada campo desconocido). El build y los
    tests leen solo JSON (sin red, sin código de WS3).
  - [x] CLI: `errante systems --explain` (cuerpo, parámetro, valor, origen, razón) y `errante systems --record
    <slug|all>` (solo desarrollo; `--live` para consultar los archivos).
  - [x] Frontend: color desconocido (gris neutro, "colour unknown (no single temperature adopted)") y tamaño desconocido
    (marcador fijo, "size unknown · not to scale"); sin toggle class-typical ni sus bandas y celdas; radio de R Dra
    constante; chips de origen por `Fact` (`three/factOrigin.ts`: "SPHEREx-measured", "derived", "catalog, not
    measured by SPHEREx"); `spherexReliability` mantiene las razones Mira / exceso IR / < 2500 K aunque falten Teff o
    radio.
  - [x] Registros de uso de IA de WS7: `pipeline/errante/systems/ai-usage.json` y `frontend/src/three/ai-usage.json`
    (Claude Code; revisión de DankoLiv en curso, no terminada).
  - [x] Constructor genérico de un sistema solo desde su snapshot (`measured.system_from_snapshot`: estrella/enana
    marrón según el tipo SIMBAD y solo con match seguro, Teff/radio/masa/distancia solo si WS3 los da verificados,
    planetas con órbita solo con P y a), para sumar un blanco sin función en `catalog.py`. Probado offline con el
    snapshot de Barnard's Star como si fuera un blanco nuevo; ningún sistema publicado lo usa todavía.
  - [ ] Snapshots de ε Ind A y de RW Aur A y B por id de Gaia DR3: no están en los fixtures de WS3 y hay que grabarlos
    con `errante systems --record <slug> --live` mientras responda el archivo Gaia de ESA (con el respaldo de VizieR no
    hay FLAME ni Bailer-Jones). Para RW Aur, antes hace falta que WS3 resuelva V15 (nombres A/B invertidos en SIMBAD).
  - [ ] Valores dibujados desde SPHEREx: Teff del ajuste del espectro (**V18, de WS3**, no existe) → WS7-8; radio desde
    la luminosidad SPHEREx + distancia Gaia; pulsación desde la curva de luz SPHEREx (producto de WS3/WS4 con revisión
    pendiente; hoy la muestra el panel "Light curve" de WS5, #83, no el 3D).
  - [ ] **V14** (3D para un click arbitrario, cualquier estrella con Gaia, sin inventar nada): **trabajo futuro**
    (propuesta D7). Necesita además que WS5 ofrezca el botón (`FieldPage`, `SkyExplorer`).
  - [ ] Decisiones a confirmar por el equipo, tomadas por WS7 en esta rama: D3 (radio de R Dra constante), quitar el
    toggle class-typical en lugar de dejarlo ILLUSTRATIVE, y D7 (valores de catálogo rotulados "catalog, not measured
    by SPHEREx" como fuente dibujada hasta V18).
  - [ ] Revisión visual en el navegador (escritorio y 375 px) de R Dra, ε Ind Ba/Bb en gris o con marcador fijo, los
    chips de origen y la ausencia del toggle; y revisión humana de DankoLiv antes del PR.

## Revisión del 3D (#65) y revisión de textos

Filas de `docs/SCIENCE.md` para WS7 ("Revisión científica del 3D (WS7, #47)": 1 bloquea, 5 importantes, 11 menores; y
la revisión de textos). Estado en la rama `ws7/measured-3d` (15/11); "hecho" = aplicado en el código de la rama, sin
revisión humana todavía.

- [x] **V4 · bloquea** (`astro.ts`, `IR_EXCESS_CITE`): la cita de RW Aur ya no presenta como "SPHEREx measured" las
  magnitudes D5/D6 de núcleos saturados; texto literal de la revisión (2MASS/AllWISE: 1.4, 1.9 y 2.8 mag sobre la
  fotosfera A+B; ningún flujo SPHEREx). Comentario: "(RW Aur: 1.4–2.8 mag at 2.2–4.6 µm, 2MASS/AllWISE)".
- V12 · importantes:
  - [ ] **V12a** (`ephemerides.ts`, R Dra): hecha la variante corta (banda de 9.0 d con el O−C de los máximos AAVSO
    2025–2026); falta la completa (fase fechada con los máximos medidos, ±3 d).
  - [x] **V12b** (`sceneLayout.ts`, `ephemerides.ts`, leyenda en `colorModes.ts`): radio de R Dra constante; ya no hay
    toggle, así que la parte "With class-typical features on: ±10 %" de la leyenda propuesta no aplica.
  - [x] **V12c** (`ephemerides.ts`, `IRREGULAR_TEXT`): "irregular: cannot be predicted" y, para RW Aur, lo medido
    offline en D1 y que ninguna exposición D2–D6 está limpia.
  - [x] **V12d** (`skyTrack.ts`, Barnard): saturada (OVERFLOW) en 357 de 358 exposiciones, en los seis detectores.
  - [x] **V12e** (`skyTrack.ts`, WISE 0855): solo en D5/D6, S/N mediana 3.4–3.8 por exposición, 21–25 por detector.
- Menores:
  - [x] `skyTrack.ts` R Dra (OVERFLOW en las 2,488 exposiciones, píxeles finitos), estrella de campo de WISE 0855
    (D1–D4) y solución adoptada de WISE 0855 (Kirkpatrick et al. 2021; el ajuste de RECON §4.1 como control).
  - [x] `catalog.py` órbitas de Barnard b–e: e ajustadas (0.03–0.08) y el error de hasta 2e rad del dibujo circular.
  - [x] `ephemerides.ts` `MIRA_PREDICTION_CAVEAT`: amplitud IR medida (0.5–1.3 mag) y retraso de los máximos.
  - [x] `colorModes.ts`: chip del modo visible "VISIBLE · BLACKBODY COLOUR MODEL".
  - [ ] `astro.ts` / `appearanceNotes.ts`: el resultado de saturación de los registros en lugar de "check the
    OVERFLOW/NONLINEAR pixel flags" para los cinco blancos.
  - [x] `spherexCoverage.ts` R Dra: "R Dra is 8.6° from the north ecliptic pole, inside the footprint of the SPHEREx
    deep collections (1,954 of its 2,493 frames)".
  - [ ] `spherexCoverage.ts` ε Ind: conteo principal 458 (`spherex_dr1: 338`; pasadas 118, 146, 74 y 120) en lugar de
    460, con la nota de la revisión.
  - [x] `appearanceNotes.ts` RW Aur A: "AAVSO VSX lists 2.64 d for RW Aur …: not adopted".
  - [ ] `docs/DATA.md:439-440` (notas WS7 de ε Ind B y WISE 0855): `docs/DATA.md` es de WS1 según
    `scripts/owners.py`; queda para WS1 o coordinación con el texto de la revisión.
- Revisión de textos (WS3-7):
  - [x] `SystemsPage.tsx`: "What SPHEREx measured for each target is listed as “Seen by SPHEREx”. Every other value is a
    catalog value, not measured by SPHEREx." (solo la segunda variante: la primera dejó de ser cierta con los facts A5).
  - [x] `field_id` de los cinco sistemas y sistemas publicados en el dataset real (#64).
  - [x] ε Ind: "an orange dwarf star" en lugar de "a Sun-like star".
  - [x] WISE 0855: "~Y4 (Kirkpatrick et al. 2021); SIMBAD lists Y2".
  - [x] Nota de R Dra con las mediciones SPHEREx offline (0.5–1.3 mag, ~260 d) y "The animation is not that light
    curve".
  - [x] ε Ind Ba+Bb: también una sola fuente para SPHEREx (≤ ~1″ contra píxeles de 6.15″).
  - [x] Facts "seen by SPHEREx" del bloque A5 (Barnard, ε Ind Ba, WISE 0855, RW Aur A, R Dra) vía `targets.toml`, y
    `VERIFIED_NOTE` dice que se copiaron de los registros de validación (revisión humana pendiente).
  - [ ] README "illustrative, unverified models": es de coordinación; HomePage/AboutPage son de WS5/WS6.

## Pendiente para coordinación

Lo que WS7 no puede cerrar solo (14/11/2026; actualizado el 15/11 con V13):

- **(a) Uso de IA (regla 14 / S08)**, para quien coordina `AI_USAGE.md` y `docs/submission/ai-usage.json` (WS7 no
  edita esos archivos): el 3D procedural de WS7, el modo Dataset time y el panel del cielo (código, tests,
  investigación bibliográfica y esta documentación) se escribieron con Claude Code en la sesión del 14/11; la
  revisión humana está a cargo de DankoLiv. El plan de trabajo lo propuso el flujo de Claude Code y DankoLiv
  eligió las decisiones de diseño (IR por defecto, solo superficies medidas + toggle ilustrativo, sin cambio de
  contrato). No registrar la revisión como terminada hasta que se haga.
  Desde el 15/11 WS7 tiene sus registros por carpeta, con el formato de `pipeline/errante/imaging/ai-usage.json`
  (#68): `pipeline/errante/systems/ai-usage.json` y `frontend/src/three/ai-usage.json` (PRs #1, #7, #8, #9, #47 y #64,
  más la rama `ws7/measured-3d`, con cómo se grabaron los snapshots). Falta que coordinación los refleje en
  `AI_USAGE.md` (que todavía dice que los presets 3D son "hand-entered and unverified") y en
  `docs/submission/ai-usage.json` (`PARALLEL_PLAN.md`, fila A5). La revisión de DankoLiv sigue en curso.
- **(b) M5 necesita aceptación del equipo:** leer el t0 de Basant+2025 como conjunción inferior es una decisión de
  criterio (el paper dice periastro; el código de juliet/RadVel y el acuerdo con González Hernández+2024 apoyan la
  conjunción). Si no se acepta: volver Barnard b–e a `epoch_mjd = null` en `catalog.py`, quitarlas de
  `ORBIT_EPHEMERIDES` y ajustar sus tests y el JSON demo. Se puede consultar a los autores.
- **(c) JSON de `data/demo/systems/` a coordinar con el dueño del contrato:** `scripts/owners.py` los marca como
  `contract` y COLLABORATION.md dice que `data/demo/` se regenera solo en PRs `contract:`. Los cambios de la tanda
  del 14/11 entraron con #47, y `data/products/systems/` (camino de WS2) con #64, con la guardia de ownership como
  aviso (en CI es advisory). V13 vuelve a regenerar los JSON de sistemas de los dos datasets y los dos
  `manifest.json` (`rebuild_manifest` reescribe `schema_version` al `SCHEMA_VERSION` vigente y la descripción de
  ε Ind): hay que declararlo en el PR. `errante demo` también reescribe `data/demo/fields/*` y `manifest.json` con
  ruido (`built_at`, dígitos finales): usar `errante systems --out …` y restaurar el ruido antes de commitear.
- **(d) Pendientes que reportaron los agentes de esta tanda y no se hicieron:**
  - revisión visual en el navegador: el panel del navegador estaba oculto (0×0), así que arcos, flechas, atenuación,
    rim y modos D1–D6 no se vieron; solo se leyó el texto de las páginas;
  - badge de página "FALSE COLOUR · MODEL" en `SystemPage.tsx`: lo reemplaza el chip dentro del visor;
  - la ficha (`BodyPanel`) no ve el modo de color activo del visor: lista todos los modos (el toggle ya no existe
    desde V13);
  - ~~parches de amplitud medida para S5~~ y ~~Metchev et al. 2015 para un patrón en ε Ind Bb~~: ya no aplican, V13
    quitó los patrones class-typical (S5);
  - citas no re-descargadas en esta tanda: fuentes de `SURFACE_NOT_DRAWN_NOTES` (Esplin 2016, Wilson 2025,
    Miles 2026, Hitchcock 2020, Chen 2022, tomadas de la investigación del 14/11), Matthews 2024 (del `Fact` del
    catálogo) y Astronomical Almanac / Meeus (comprobados numéricamente contra ERFA `epv00`); Feast 2009 ya no se
    cita (V13 quitó la masa class-typical de R Dra);
  - ε Ind B: la astrometría del panel del cielo es una constante copiada de RECON §4.1. **Resuelto por WS3 (#65):**
    coincide con Gaia DR3 6412596012146801152 en el TAP de ESA (fixture de WS3 del 2026-11-15); reemplazarla solo si el
    contrato suma un `target_body` o la astrometría de B;
  - WISE 0855: **resuelto por WS3 (#65):** se usa Kirkpatrick+2021 (la solución publicada, la de `fields.toml` y del
    registro); el ajuste propio de RECON §4.1 queda como control a 0.31″ (0.05 px). El panel del cielo ya lo dice;
  - los puntos de cada pasada están a mitad de la ventana: sin `MJD-AVG` por frame de los blancos reales;
  - R Dra: las fechas VSX no se corrigen por la media del O−C (la banda, ahora de 9.0 d con los máximos AAVSO
    2025–2026, la incluye) y no hay término de Eddington–Plakidis;
  - Barnard: para errores asimétricos se usó el lado mayor y para e la σP del paper (0.0028 d), así que e va de
    23.2° a 31.0° (con 0.003 d serían 23.6° a 32.3°);
  - ε Ind Bb: un T0 derivado de la Tabla 3 de Chen+2022 no se usa (no publicado); Bb y Ab quedan como anillos.
- **(e) Resuelto:** las celdas de convección de R Dra pasaron detrás del toggle class-typical (apagado por
  defecto); la vista por defecto es una esfera lisa, como pide `VISION.md`. Desde V13 el toggle ya no existe y
  ningún blanco real tiene celdas ni bandas.
- **(f) Decisiones del equipo que V13 toma provisoriamente** (`PARALLEL_PLAN.md` §4): D3 (radio de R Dra constante,
  como pide la revisión de WS3 y `VISION.md`: "si falta, modelo estático"), quitar el toggle class-typical en lugar de
  dejarlo ILLUSTRATIVE, y D7 (los valores de catálogo, rotulados "catalog, not measured by SPHEREx", se dibujan hasta
  que exista V18; V14 y WS7-8 como trabajo futuro). Confirmarlas en el PR.
- **(g) Para WS3:** V18 (Teff desde el espectro SPHEREx) es el insumo que falta para dibujar color desde SPHEREx; V15
  (nombres A/B de RW Aur invertidos en SIMBAD) impide asignar el contexto de WS3 a un componente; el archivo Gaia de
  ESA hace falta para grabar ε Ind A y RW Aur A/B por id de Gaia (`errante systems --record … --live`). Los snapshots
  de WS7 se leen como datos: un cambio de WS3 en `context.py` no rompe el build de WS7 hasta que alguien re-graba.

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
