# WS7 · Sistemas 3D (modelos de los objetos que seguimos)

**Objetivo:** que cada objeto que mostramos en las imágenes SPHEREx se pueda **abrir en 3D**: ver el cuerpo,
ver su sistema animado (órbitas, pulsaciones) y **entrar a cada planeta/estrella** con su ficha de datos. Buen
diseño y representación fiel a los datos, siempre etiquetada como modelo.

**Tus rutas:** `pipeline/errante/systems/`, `frontend/src/three/`, `frontend/src/components/SystemViewer.tsx`,
`frontend/src/components/BodyPanel.tsx`, `frontend/src/pages/SystemsPage.tsx`, `frontend/src/pages/SystemPage.tsx`,
`data/demo/systems/` (regenerado con `make demo`), `docs/VISION_3D.md`.

**Recibís:** objetos de los campos (WS3: `config/fields.toml`, `known.json`), candidatos (WS2/WS3).
**Entregás:** `<root>/systems/<id>.json` (contrato `SystemModel`) + las vistas 3D.

**Leé primero:** `docs/VISION_3D.md`, `docs/CONTRACT.md`, `pipeline/errante/models.py` (sección "3D systems"),
`pipeline/errante/systems/catalog.py`, `frontend/src/three/SystemScene.ts`.

## Estado actual
- ✅ Contrato `SystemModel` (schema 0.3.0, con `Orbit.quality`), `Manifest.systems`, `GET /api/systems/{id}`, `errante systems`.
- ✅ 5 sistemas de los objetivos de prueba (valores **tipeados a mano, sin verificar**) + 1 sintético ligado a
  `demo-ecliptic`.
- ✅ `#/systems`, `#/system/<id>[/<cuerpo>]`: órbitas keplerianas animadas, colores por temperatura, texturas
  procedurales, disco, pulsación, clic/etiqueta → la cámara entra y sigue al cuerpo, ficha con fuente/verified,
  distancias comprimidas/lineales, enlaces campo ⇄ sistema, responsive.
- ⛔ Valores verificados, órbitas reales de asteroides, modelos de forma, vista de movimiento por el espacio.

## Tareas

- [ ] **WS7-1 (P0) Integración con el flujo principal**: que desde un candidato/objeto conocido del blink se pueda
  ir a su cuerpo 3D (`Body.candidate_id`; coordinar con WS5 para el botón en `CandidatePanel`) y agregar campos
  `epsilon-indi`, `r-draconis`, `rw-aurigae` a `config/fields.toml` (con WS3) para que todos los sistemas
  tengan su campo SPHEREx.
- [ ] **WS7-2 (P0) Verificar valores**: implementar `sources.exoplanet_archive_system` y `sources.simbad_star`
  (tests `network`), reemplazar los valores de `catalog.py` y poner `verified=True` **solo** en lo comprobado,
  con la fuente exacta (tabla/URL/paper). Corregir lo que esté mal. Criterio: badge "UNVERIFIED VALUES"
  desaparece en los sistemas verificados.
- [ ] **WS7-3 (P1) Asteroides reales**: `sources.sbdb_orbit` → para cada candidato `known` de un campo real, crear
  un sistema heliocéntrico (Sol + Tierra + Júpiter + el asteroide) con su órbita real y la posición en la fecha
  de cada frame. Mostrar "dónde estaba la Tierra/SPHEREx cuando lo vio".
- [ ] **WS7-4 (P1) Pulido visual**: limb darkening y granulación en estrellas (shader simple), glow que respire en
  la Mira (R Dra) siguiendo la curva de luz, bandas/tormentas en gigantes, inclinación y anillos si hay datos,
  transición de cámara más cinematográfica, leyenda de escala. Lighthouse sin regresiones.
- [ ] **WS7-5 (P1) "Moverse por el espacio"**: vista de vecindario solar con `SpaceMotion` (paralaje, movimiento
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

## Reglas
- Toda vista 3D muestra "3D MODEL · NOT AN IMAGE" y la `representation_note`. Nada de presentarlo como imagen real.
- Nunca inventar parámetros: si no hay dato, no se dibuja (o se dibuja marcado como supuesto, en amarillo).
- three.js se carga solo en las páginas 3D (dynamic import). No agregar React Three Fiber u otras capas sin
  justificarlo en el PR.
- Cambios a `SystemModel` = cambio de contrato (`contract:` PR, `make schema`, `types.ts`).

## Prompt de arranque

> Sos el agente del workstream WS7 (sistemas 3D) del repo Errante para NASA Space Apps 2026. Leé `AGENTS.md`,
> `docs/VISION_3D.md`, `docs/CONTRACT.md` y `tasks/WS7-3d-systems.md`. Trabajá SOLO en las rutas de WS7. Corré
> `make web` y abrí `#/systems`. Empezá por WS7-2 (verificar valores contra NASA Exoplanet Archive / SIMBAD, con
> tests `network`) y WS7-1. Si un servicio no responde desde tu entorno, no inventes valores: dejalos
> `verified=False`. Verificá en el navegador (desktop y celular), corré `make check` y mostrame el diff antes de
> commitear.
