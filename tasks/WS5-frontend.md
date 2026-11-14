# WS5 · Frontend

**Objetivo:** la experiencia pública: que cualquier persona entienda en 30 segundos qué está viendo, vea el
cielo **cambiar** y explore qué se movió y qué significa. Es lo que el jurado ve primero.

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

- [ ] **WS5-1 (P0) Pulido del blink**: zoom/pan, lupa en el candidato, crosshair con RA/Dec (usar `grid.wcs`),
  modo "comparar 2 épocas" lado a lado / cortina, timeline con espacio proporcional al tiempo (horas vs meses).
- [ ] **WS5-2 (P0) Onboarding**: primer uso guiado ("estas son estrellas, esto se movió, por eso es un
  asteroide") en ≤ 3 pasos. Medir: alguien ajeno entiende en < 30 s.
- [ ] **WS5-3 (P0) Responsive y accesible**: celular, teclado, contraste, `alt`/`aria`. Lighthouse ≥ 90.
- [ ] **WS5-4 (P1) Mapa del cielo** con Aladin Lite (CDN, carga diferida): campo, trazas, surveys 2MASS/AllWISE;
  vista de todo el cielo en Home con nuestros campos + eclíptica + región del Planeta Nueve (de WS3).
- [ ] **WS5-5 (P1) Reporte de candidato** como página propia y compartible (`#/field/<id>/c/<cand>`), con
  recortes por detección, espectro, "qué podría ser" y advertencias.
- [ ] **WS5-6 (P1) Página "Límites"**: tabla/heatmap de inyección-recuperación (WS2-6) + widget "¿Lo vería
  SPHEREx?" (WS3-6).
- [ ] **WS5-7 (P1) Búsqueda por coordenadas o nombre** (modo api): llama `/api/search` y muestra cuántas épocas
  hay; si no hay backend, explicar amablemente.
- [ ] **WS5-8 (P2) Capa de diferencia** (si WS2-7 la produce), composición en falso color de bandas, exportar
  GIF del blink para redes.

## Reglas
- Si `synthetic` es true en cualquier dato mostrado → badge visible siempre.
- Lenguaje: "unconfirmed" ≠ "discovery". Nada de "¡Encontramos el Planeta X!".
- No agregues dependencias pesadas sin necesidad (Aladin por CDN on-demand está bien).

## Prompt de arranque

> Sos el agente del workstream WS5 (frontend) del repo Errante para NASA Space Apps 2026. Leé `AGENTS.md`,
> `docs/CONTRACT.md`, `docs/SCIENCE.md` §4 y `tasks/WS5-frontend.md`. Trabajá SOLO en `frontend/`. Corré
> `make web` y mirá la app con los datos demo. Empezá por WS5-1 y WS5-3 (blink con zoom/pan, timeline
> proporcional, responsive). Usá los tipos de `src/api/types.ts`; si necesitás un dato nuevo, proponelo como
> PR `contract:` aparte. Verificá en el navegador (desktop y ancho de celular), corré `npm run build` y
> `npm test`, y mostrame el diff antes de commitear.
