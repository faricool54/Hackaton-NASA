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

## Estado de implementación — 15/11/2026, main 3ed5c91 (#97); publicación verificada 3ed5c91 (#97)

La visión de arriba es el objetivo del producto; no implica que todas sus inferencias físicas estén
implementadas. La [matriz de requisitos](REQUIREMENTS.md) y el [plan paralelo](PARALLEL_PLAN.md) mantienen
la cobertura, evidencias y dependencias. Freeze 17:00 ART; envío interno 21:00; cierre del portal 23:59.

1. **Mapa → posición → video real, público:** implementado. Google Compute Engine sirve web/API y jobs
   persistentes; cinco campos de 40 imágenes y coordenadas nuevas probados (#84/#95/#96). Mapa negro corregido #86.
2. **Visor:** reproducción/paso/filtros y zoom 1×/2×/4×; retícula Gaia de Barnard en #96. Esa retícula es
   una predicción de catálogo, no una posición medida por SPHEREx. Otros blancos y UI de calidad pendientes.
3. **Cinco ensayos R05:** registros FITS offline y re-mediciones de agentes disponibles. Aprobación humana
   y cierre del paso 6 en cada registro pendientes; la aceptación técnica pública no los sustituye.
4. **Espectros y curvas:** cubo DR1/L2, comparaciones y curvas reales en la app. L2 admite movimiento propio
   en API 0.7.0; la UI aún no lo expone. #93–#95 actualizaron métodos/productos/notas; WS5 integró avisos/floors/selección en #97, publicados y verificados; restan vistas adicionales.
5. **3D:** contexto de catálogo con fuentes por valor. PR #90 abierto trabaja V4/V12/V13 mínimo; no se
   presenta como integrado. Temperatura/radio desde SPHEREx y 3D para clicks arbitrarios siguen pendientes.
6. **P2:** detección, JPL/SkyBoT, límites e hipotético Planeta X son extensiones; no bloquean el visor.

| Workstream | Estado / foco restante |
|---|---|
| WS1 (faricool54) | Acceso SIA/TAP/S3, cubo y snapshots integrados; releases nuevos requieren contrato |
| WS2 (V0id47) | Campos reales, render/fotometría/comparaciones integrados; SNR del coadd y flags ampliados pendientes |
| WS3 (faricool54) | Registros, contexto y curvas/espectros integrados; temperatura/color y RW Aur V15 pendientes |
| WS4 (rpccp) | Entrega actual cerrada #95; nuevas integraciones esperan datos/contratos. Redeploy manual, no automático |
| WS5 (actividad confirmada por usuario) | #96 publicado; avisos de curvas y carga estática entraron #97; faltan compacto, vistas adicionales, Gaia/footprint y calidad |
| WS7 | PR #90 abierto; modelos físicos SPHEREx completos dependen de WS3 |
| WS6 / coordinación | README/estado en esta tarea; demo, datos de equipo, inventario final, revisión y envío pendientes |

Reservas y responsables de envío se confirman en [TEAM.md](TEAM.md). El alcance actual de rpccp en WS6
es documentación de estado; no se asigna automáticamente la producción de demo ni el envío del formulario.
