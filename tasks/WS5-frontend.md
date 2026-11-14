# WS5 · Frontend

**Objetivo:** la experiencia pública: que cualquier persona entienda en 30 segundos qué está viendo, vea el
cielo **cambiar** y explore qué se movió y qué significa. Es lo que el jurado ve primero.

**Cobertura:** R01/R03/R04/R05 y C02–C08. Primera entrega: coordenadas → secuencia real pública;
los candidatos automáticos no son requisito para explorar o extraer un espectro.

**Tus rutas:** `frontend/` (todo) — salvo los textos largos de About/pitch que coordinás con WS6.

**Recibís:** JSON + PNG según `docs/CONTRACT.md` (ya hay datos demo en `data/demo`). **Entregás:** sitio estático
desplegable (`npm run build`) que también funciona contra el backend (`?mode=api`).

**Leé primero:** `docs/CONTRACT.md`, `frontend/src/api/*.ts`, `frontend/src/components/BlinkViewer.tsx`,
`docs/SCIENCE.md` §4 (cómo hablar de los resultados).

## Estado actual
- ✅ Home con tarjetas de campos, página de campo con **blink** (play/pausa, slider, velocidad, teclado),
  marcadores de candidatos y objetos conocidos, traza del candidato seleccionado, panel de evidencia, espectro
  SVG, filtro por detector, About, badge de datos sintéticos, modos `static`/`api`.
- ⛔ Mapa del cielo (placeholder), búsqueda por coordenadas, zoom, capa de diferencia, mobile pulido.

## Tareas

- [ ] **WS5-1 (P0, R04) Blink estable sobre datos reales**: play/pausa, paso, velocidad y fechas; precarga,
  carga/fallos explícitos y reinicio correcto al cambiar campo/filtro. Funciona con candidatos/known vacíos.
  Zoom/pan, crosshair, comparación lado a lado/cortina y timeline proporcional son mejoras P1.
- [ ] **WS5-2 (P0) Onboarding**: primer uso guiado ("estas son estrellas, esto se movió, por eso es un
  asteroide") en ≤ 3 pasos. Medir: alguien ajeno entiende en < 30 s.
- [ ] **WS5-3 (P0) Responsive y accesible**: celular, teclado, contraste, `alt`/`aria`. Lighthouse ≥ 90.
- [ ] **WS5-4 (P1, C05/C08) Mapa y capas** con Aladin Lite (carga diferida): campo y WISE/AllWISE,
  catálogo Gaia DR3 de WS3-10 propagado por época cuando sea posible; mostrar misión, release, banda, fecha
  y créditos. Mantener disponible el blink si una capa falla. Eclíptica y región de Planeta X quedan P2.
- [ ] **WS5-5 (P2) Reporte de candidato** como página propia y compartible (`#/field/<id>/c/<cand>`), con
  recortes por detección, espectro, "qué podría ser" y advertencias.
- [ ] **WS5-6 (P2) Página "Límites"**: tabla/heatmap de inyección-recuperación (WS2-6) + widget "¿Lo vería
  SPHEREx?" (WS3-6).
- [ ] **WS5-7 (P0, R03/R05) Ingreso RA/Dec → secuencia.** Unidades claras, grados y formato sexagesimal
  normalizado; validar rangos y mostrar errores de campo. Consultar y construir/cargar mediante WS4-5,
  con progreso/sin cobertura/reintento; contar archivos sin abrir imágenes no alcanza. Accesos a los cinco
  blancos de VALIDATION.md con fuente/época verificadas. Resolver nombres es opcional. El modo estático
  explica su límite de campos curados y no simula una búsqueda arbitraria.
- [ ] **WS5-8 (P1, C03) Suma/resta de épocas.** Elegir A/B o conjunto y ver suma/media/resta generada
  por WS2/WS4, con fechas, banda y advertencias. Color compuesto y exportación GIF/MP4 quedan P2.
- [ ] **WS5-9 (P1, C04) Campo de visión configurable.** Control con unidades y límites del servidor;
  explicar que más área implica más transferencia/procesamiento; progreso y estimación cuando exista.
  El FOV seleccionado afecta la solicitud, el producto y el enlace compartido.
- [ ] **WS5-10 (P1, C07) Panel de metadatos/calidad.** Fecha/MJD, detector, λ/ancho si existen, release,
  URI de origen, fracción válida y flags de contaminación explicados. No confundir flag ausente con cero.
- [ ] **WS5-11 (P1, C06) Coordenadas en URL y modo embebido.** Propuesta:
  `?mode=api&ra=<deg>&dec=<deg>&fov=<deg>&detector=<1..6>`. Restaurar formulario y secuencia en nueva sesión;
  copiar enlace, validar parámetros y ofrecer modo compacto. Probar iframe desde otro origen con WS4.
  La URL propuesta aún no está implementada; preservar las rutas hash y `mode`/`dataset` existentes.
- [ ] **WS5-12 (P1, C02) Bandas, coadds y espectro al seleccionar una posición.** Elegir detector/λ,
  activar coadd por detector/visita y solicitar espectro con flujo/error/fecha desde WS4-8. Funciona sin
  detector automático. Explicar que detector no equivale a una única λ ni garantiza 102 muestras disponibles.
- [ ] **WS5-13 (P0, S04/S08) Textos públicos y atribución.** UI/materiales de evaluación en inglés;
  About declara estado real y asistencia conocida de Codex (texto actualizado). Completar con WS6 el
  inventario/revisión de aportes y medios; no presentar datos/catálogos futuros como implementados.
  Mantener sincronizados About, README, AI_USAGE.md y metadata al publicar; no basta el campo SI privado.

## Reglas
- Si `synthetic` es true en cualquier dato mostrado → badge visible siempre.
- Lenguaje: "unconfirmed" ≠ "discovery". Nada de "¡Encontramos el Planeta X!".
- No agregues dependencias pesadas sin necesidad (Aladin por CDN on-demand está bien).

## Hechos verificados (2026-11-14) — leelos antes de implementar

- **CDS Estrasburgo está caído** (alasky, VizieR, la URL "latest" de Aladin): cargar **Aladin Lite 3.8.2 desde
  jsdelivr**, HiPS desde espejos de IRSA/ESA y Gaia DR3 desde VizieR de **CfA** (tiene CORS). Detalle en
  [`docs/DATA.md`](../docs/DATA.md) §3.0. IRSA no tiene CORS: búsquedas e imágenes reales vienen del backend.
- **Los objetivos se mueven 1–2 px en total:** sin zoom pixelado, retícula, posición predicha por época y resta
  de temporadas, en el video no se ve nada. Arrancar con **un detector** (no "all", que mezcla λ).
- WISE 0855 está ~126″ al oeste de la coordenada del enunciado: FOV por defecto ≥ 8′.
- `?mode=` ya se usa para `static`/`api` en `client.ts`: si el viewer necesita `mode=blink|diff`, renombrar uno.
- Bugs vistos: el teclado (espacio/flechas) se captura en todo el documento; `FieldPage` no se remonta al cambiar
  de campo (usar `key`); el blink monta todos los `<img>` sin precarga.

## Prompt de arranque

> Sos el agente del workstream WS5 (frontend) del repo Errante para NASA Space Apps 2026. Leé `AGENTS.md`,
> `docs/CONTRACT.md`, `docs/SCIENCE.md` §4 y `tasks/WS5-frontend.md`. Trabajá SOLO en `frontend/`. Corré
> `python scripts/dev.py web` y mirá la app con los datos demo. Leé `docs/REQUIREMENTS.md` y `docs/VALIDATION.md`.
> Empezá por WS5-7, WS5-1 y WS5-3 (coordenadas → secuencia estable, responsive). Usá los tipos de
> `src/api/types.ts`; si necesitás un dato nuevo, proponelo como
> PR `contract:` aparte. Verificá en el navegador (desktop y ancho de celular), corré `npm run build` y
> `npm test`, y mostrame el diff antes de commitear.
