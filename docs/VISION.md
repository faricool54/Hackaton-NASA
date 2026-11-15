# Visión del producto (acordada por el equipo el 14/11/2026)

> **Origen de la idea:** la definió el equipo (faricool54, 14/11/2026). Claude se usó para comprobar la
> factibilidad contra los datos y servicios, probar el mapa en el navegador y redactar este documento, no para
> formular la idea (regla S08 de [`SUBMISSION_GUIDE.md`](SUBMISSION_GUIDE.md); registro en
> [`AI_USAGE.md`](../AI_USAGE.md)). Una propuesta de producto anterior, redactada por Claude, fue descartada por el
> equipo.

## En una frase

Un **mapa interactivo del cielo real de SPHEREx** donde se busca por nombre o coordenadas. Al hacer click en un
punto se abre un panel con **lo que SPHEREx vio ahí a lo largo del tiempo** y un **modelo 3D realista del objeto,
construido a partir de esas mediciones**.

## Recorrido

1. **Mapa (pantalla principal).**
   - Aladin Lite 3.8.2 (desde jsdelivr) con el cielo **SPHEREx DR1** de fondo (HiPS de IRSA).
   - Selector de longitud de onda propio: 102 planos de 0,75 a 5 µm.
   - Capa de contexto AllWISE (espejo de ESA).
   - Buscador por nombre (Sesame de CfA, vía `/api/resolve-name`) o por RA/Dec.
   - Las coordenadas quedan en la URL, para compartir (C06).
2. **Click en un punto → panel** con tres vistas:
   - **SPHEREx en el tiempo** (P0, R02–R04): video/blink de imágenes reales de esa posición, por fecha y por
     detector, con zoom, retícula y fecha/λ/release/flags de cada frame. Sale del job del backend
     (`/api/jobs` → `build_field`) o de los campos precomputados.
   - **Espectro SPHEREx** (P1, C02): 0,75–5 µm en esa posición, punto por punto desde las exposiciones (cada una
     mide otra λ en cada lugar del detector).
   - **Modelo 3D** (P1, parte central de la visión): construido desde mediciones (siguiente sección).
3. **Los cinco blancos del reto** como vitrina validada (R05), cada uno con su registro en `docs/validation/`.

## El 3D: realista y sin inventar nada

**Regla:** cada valor que define el modelo sale de una medición, con su fuente y su incertidumbre. Lo que no se
midió no se dibuja, o se muestra como "desconocido".

| Propiedad | De dónde sale | Si falta |
|---|---|---|
| Temperatura → color (cuerpo negro) | Ajuste del espectro SPHEREx | Sin color físico: gris y "unknown" |
| Radio / tamaño | Luminosidad (flujo SPHEREx integrado + distancia) con Stefan–Boltzmann. La distancia es de **Gaia DR3** (paralaje): SPHEREx no mide distancias | "Size unknown", no se escala |
| Variación de brillo (pulsación) | Curva de luz SPHEREx a λ compatible (por ejemplo R Draconis) | Modelo estático |
| Movimiento en el cielo | Posiciones SPHEREx por temporada (1–2 px por año) y Gaia | — |
| Rasgos del espectro (agua, metano, CO, exceso de polvo) | Espectro SPHEREx | Se indican en la ficha; no se dibujan como geometría |
| Planetas y compañeras | Solo confirmados en catálogo (NASA Exoplanet Archive, SIMBAD), con su fuente. **SPHEREx no ve planetas de otras estrellas** | Sin catálogo, no hay planetas |
| Superficie | No es medible: ninguna estrella se resuelve | Esfera lisa con color físico y oscurecimiento al borde; sin manchas, nubes ni bandas inventadas |

Siguen valiendo las reglas de [`VISION_3D.md`](VISION_3D.md) y de `AGENTS.md`: badge **"3D MODEL · NOT AN
IMAGE"**, `Fact.source`/`Fact.verified` en cada dato y nota de representación. Los presets actuales de WS7, con
texturas procedurales, tienen que migrar a esta regla.

## Si el punto no está catalogado

- El panel de SPHEREx (video y espectro) funciona siempre, en cualquier punto del cielo.
- Si SPHEREx detecta una fuente ahí: la temperatura sale de su espectro; sin distancia, el tamaño es desconocido.
  Se marca `unconfirmed` (puede ser un artefacto, un error o un objeto no catalogado; nunca un "descubrimiento",
  ver `docs/SCIENCE.md`).
- Si no hay fuente: "no source detected" y no hay 3D.

## Verificado el 14/11/2026

- Aladin Lite 3.8.2 (jsdelivr) dibuja el HiPS SPHEREx DR1 de IRSA
  (`https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube`, con CORS), y `on('click')` devuelve
  RA/Dec. Probado en el navegador con el plano de 4,6 µm sobre Barnard's Star.
- **Planos vacíos:** el 50 y el 51 (canales dicroicos) están vacíos a propósito y dan 404. Aladin arranca en el plano
  del medio (el 50), así que hay que fijar otro al iniciar.
- **Selector de λ:** el slider de cubo nativo de Aladin elige planos equivocados. Usar `setFrequency` con la fórmula
  de [`RECON_SPHEREX.md`](RECON_SPHEREX.md) §5.4 y un selector propio. La λ de cada plano está en
  `data_cube_crval3_arr` del archivo `properties`.
- Requiere WebGL2. Licencia GPL-3: mantener el logo y el link de Aladin.
- El HiPS es un promedio del cielo, sin dimensión temporal: el cambio en el tiempo va en el panel.
- Datos reales: los cinco blancos se arman con `errante build` (WS1 + WS2 #16/#19) en ~20–30 s cada uno.

## Prioridades (freeze: domingo 15/11 17:00; envío: 21:00 ART)

Estado al 15/11/2026, 03:30 ART (`main` `c333390`). La lista viva, con IDs, dueños, esfuerzo y dependencias, está en
[`PARALLEL_PLAN.md`](PARALLEL_PLAN.md).

1. **P0:** mapa + búsqueda + click → panel con el video SPHEREx real (el núcleo del reto), y deploy público.
   *Funciona en local con la API (#34): click → job → 40 frames reales en ~20-30 s. Faltan el deploy público (V2,
   decisión D1), el arreglo del mapa negro intermitente (V1) y la retícula/zoom del video (V3).*
2. **P0:** los cinco blancos validados (R05). *Cinco registros `success` en [`validation/`](validation/) (#36, #46);
   faltan la revisión humana y el recorrido en la URL pública (V5, A9).*
3. **P1:** espectro en el panel. *Hecho con la API (cubo DR1 o fotometría L2, #53-#55), sin movimiento propio (V9).
   La ficha del objeto (contexto de catálogo de WS3, #58) está en curso en `integ/object-card` (V6).*
4. **P1:** 3D desde mediciones; primero los cinco blancos, después cualquier estrella con datos de Gaia. *Hoy hay un
   3D de catálogo verificado para los cinco (#47, #64), todavía no construido desde mediciones SPHEREx (V13, V14).*
5. **P2:** detección automática y Planeta X. *Sin empezar; propuesta: congelarlos hasta después del envío (D10).*

## Qué hace cada workstream

Responsables según [`TEAM.md`](TEAM.md). «De facto» indica quién hizo el trabajo sin haber reservado el workstream.

| WS | Responsable | Ya hecho | Lo que sigue (IDs de `PARALLEL_PLAN.md`) |
|---|---|---|---|
| **WS5** (frontend) | Sin reserva. Aportes: rpccp (#34, #55), V0id47 (#40), BenjaminPondal (#15, #20, #26) | Mapa Aladin con SPHEREx, selector de λ, buscador, coordenadas en la URL, click → job → blink, modos de color, paneles de espectro y comparación | Mapa negro (V1), retícula y zoom (V3), `ObjectCard` (V6, en curso), panel de tres vistas (V7), calidad por frame (V8), About y filas de la revisión de textos (A2, A13), onboarding y Lighthouse (A10) |
| **WS7** (3D) | Sin reserva; de facto DankoLiv (#47) | Valores de los cinco verificados contra catálogos (#9); 3D procedural con esferas lisas, *Dataset time* y panel del cielo (#47); publicado en el dataset real (#64) | Fila «bloquea» (V4), filas «importante» (V12), alimentar el 3D desde `physical_parameters` y después desde mediciones SPHEREx (V13), 3D para un click arbitrario (V14) |
| **WS3** (ciencia) | faricool54 + Claude (#51) | Validación de los cinco (#36, #46), contexto del objeto (#58), espectro por temporada y curvas de luz (#59), revisión de textos (#60) y del 3D (#65) | Nombre A/B de RW Aur (V15), textos de `fields.toml` (V16), temperatura desde el espectro (V18), curva de luz como producto (V10) |
| **WS2** (imágenes) | V0id47 + Claude (#13) | Reproyección y selección (#16, #35), cinco campos reales (#17, #41), restas y coadds (#19, #37, #69), fotometría forzada (#31), chequeo de productos y animaciones (#70, #71) | Comparaciones visibles sin backend (V11), SNR del coadd (V21), flags por frame (V8) |
| **WS4** (backend y deploy) | rpccp + Codex | Jobs por coordenadas y nombre (#18, #32, #33), espectros y comparaciones (#53, #54), caché (#52, #57) | `GET /api/object` (V6, en curso), deploy (V2, A12), espectro con movimiento propio (V9) |
| **WS1** (datos) | faricool54 + Claude (#10) | Búsqueda SIA/TAP, S3, λ y MJD (#21-#23), cubo DR1 (#42), todas las exposiciones de un punto (#45, #50), snapshots para caídas de IRSA (#43) | Probar en vivo el fallback TAP; releases nuevos (V20) |
| **WS6** (entrega) | Sin reserva. TEAM.md: deploy → WS4; textos, About, pitch y video → WS5 + quien termine antes (normalmente WS3) | Guías y borradores en `docs/submission/` | Todo §3 de `PARALLEL_PLAN.md`: textos (A1-A3, A7), demo (A4), registro de IA (A5), fuentes (A6), envío (E1-E9) |

**Pendiente:** reservar WS5, WS6 y WS7 en [`TEAM.md`](TEAM.md), y definir en qué workstream trabajan BenjaminPondal y
mateoa007 (decisión D8).
