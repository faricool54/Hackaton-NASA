# Plan de frontend: Errante cómodo, lindo y con todo a la vista

> Estado: **propuesta para anotarse** (15/11/2026, 16:25 ART; revisión crítica 16:50, ver §11). Base: `main` en
> `53f10fa`. Insumos: auditoría UX (`survey`), mapa de colisiones (`collisions`) y mediciones en la URL pública.
> **Reloj vigente:** según faricool54 (coordinación) en #100, **no hay freeze a las 17:00**; se mergea y deploya de
> forma continua, último deploy ~**22:30** y cierre de video y entrega a las **23:59**. `AGENTS.md`,
> `docs/COLLABORATION.md` §5 y `docs/PARALLEL_PLAN.md` todavía dicen "freeze 17:00 / envío 21:00": coordinación
> los alinea en el mismo PR `chore:` que sube este plan.
> Ubicación sugerida en el repo: `docs/FRONTEND_PLAN.md` (PR `chore:` de coordinación) + un issue
> "FE: plan de frontend, anotarse acá" con la tabla de la §10.
> Docs internos en español; **todo texto de la UI, en inglés**.

## 0. Resumen

- **Qué cambia:** la home pasa a ser una **app a pantalla completa**: mapa grande, buscador y chips de los cinco
  blancos flotando encima, y a la derecha un **panel fijo con pestañas Object · Time · Spectrum · 3D**. Nada de
  scroll de página ni saltos. Al pasar el mouse por una estrella aparece un **popup junto al cursor** con los datos
  Gaia (al instante) y, al hacer click, la ficha completa en el panel. La ficha de campo se vuelve un **dashboard**.
- **Cómo nos repartimos:** 13 paquetes (FE-0 a FE-12) con **archivos disjuntos**. Solo FE-1 toca `styles.css`,
  `App.tsx`, `main.tsx` e `index.html`. Cada paquete trae su propio CSS (`src/styles/<paquete>.css`) con un prefijo
  de clases propio.
- **Orden:** primero entran los PRs abiertos de mateoa007 (#114 → #111 → #116, **lo antes posible, objetivo
  17:15**). Después, FE-4a.0 (mapa a pantalla completa) y FE-1 (tokens), que destraban a FE-2, y el resto según
  dependencias.
- **Sin freeze a las 17:00** (#100): se mergea de forma continua con check verde y una revisión, y se deploya en
  ventanas anunciadas en #100 (propuesta: ~18:30, ~20:00, ~21:30 y **último deploy ~22:30**). Después de las 22:30
  solo reverts. Lo que no llegue queda en su rama.
- **Capacidad real:** hay ~5 h hasta el último deploy y los paquetes suman ~27 h. Con 4 personas, entra el bloque
  **A** (~13 h) y algo de **B**. El bloque C queda para después de la entrega (§7.3).

---

## 1. Dónde estamos hoy (medido)

Medido a las 16:20 en `https://errante.34-148-242-13.sslip.io` (modo live API), con emulación de viewport en
Chromium. Una laptop de 1366×768 deja unos **1366×650** de viewport útil después de la barra del navegador.

| Vista | Hoy | Objetivo de este plan |
|---|---|---|
| Home, 1366×650 | La página mide **3307 px** de alto. Hero (228 px) y buscador (128 px) quedan arriba. El mapa (iframe de 738×470) **empieza en y = 546**: sin scroll se ven **104 px de mapa**. El formulario mide 677 px y las tarjetas 1975 px | **0 px de scroll**. Mapa de unos 940×600 visible al cargar, buscador y chips encima, panel con pestañas siempre visible |
| Ficha `#/field/barnards-star`, 1366×650 | La página mide **2010 px**. La imagen de 764×764 empieza en y = 411: se ven 239 px. **Light curve** cerrada en y = 1690 y Spectrum en y = 1609 | **0 px de scroll**. Reproductor completo (imagen de al menos 460 px + controles) y panel lateral con la curva de luz abierta |
| Home, 375×812 (teléfono) | La página mide **8975 px**. El mapa **empieza en y = 856, fuera de la primera pantalla** | Mapa visible desde y ≤ 56, con hoja inferior para el panel |

Los 15 problemas detallados, con archivo y línea, están en la auditoría. Los más graves: el click en el mapa
hace scroll del resultado hacia abajo (`SkyExplorer.tsx:65-69`), la ficha del objeto queda al fondo del
formulario (`:211`), la pestaña Time incrusta una página entera (`PositionResults.tsx:69`), los resultados
quedan escondidos en `<details>` y el mapa no reacciona al pasar el mouse.

---

## 2. Objetivos y principios

1. **Todo a la vista.** A 1366×650 ninguna página principal (home, ficha de campo, 3D) tiene scroll de página. Si
   algo no entra, se usan pestañas o un "Expand", y como último recurso un scroll **interno** de un panel. Nunca
   se scrollea la página ni se mueve el mapa.
2. **Cómodo.** Un solo camino para elegir algo: click en el mapa, chip, búsqueda o URL compartida terminan en el
   mismo estado (panel abierto con ese objeto). El resultado aparece al lado de donde se hizo click, sin saltos.
   Atajos de teclado para lo frecuente.
3. **Lindo y vistoso, sin ruido.** Estética de "cielo nocturno": fondo oscuro, superficies de vidrio sobre el
   mapa, un acento cian (SPHEREx), tipografía con números tabulares y coordenadas en monoespaciada. Animaciones
   cortas (≤ 200 ms) y desactivadas con `prefers-reduced-motion`.
4. **Honestidad intacta** (AGENTS.md, reglas 3 y 4). Cada vista dice de dónde vienen sus datos con una insignia
   visible: **"SPHEREx · real frames"**, **"Catalog · not SPHEREx"**, **"Gaia DR3 catalog · not SPHEREx"**,
   **"3D MODEL · NOT AN IMAGE"**, **"SYNTHETIC DATA · NOT SPHEREx"** y "Static coadd · not a video" en el mapa. La
   procedencia puede ir plegada; **el resultado y la etiqueta, no**. No se inventan porcentajes de progreso (el
   backend no los informa) ni distancias con paralajes inciertos. **El color nunca es la única señal de
   procedencia**: cada insignia lleva texto (el cian de Gaia `#6ff4f1` y el azul SPHEREx `#7cc4ff` se parecen).
   El crédito "NASA/SPHEREx · Caltech/IPAC" y "Static coadd · not a video" quedan **siempre visibles sobre el
   mapa**, nunca solo dentro de un menú plegado; lo mismo con los créditos de Gaia DR3 y AllWISE mientras esas
   capas estén encendidas.
5. **Laptop 1366×768 y teléfono 375×812 (y 360×640) como pantallas de referencia.** Cada paquete incluye en su CSS
   sus propias reglas para ≤ 900 px. FE-10 agrega la hoja inferior y hace la pasada táctil.
6. **Sin librerías nuevas.** Nada de UI kits, Tailwind, librerías de gráficos ni router. Tabs, tooltip, hoja
   inferior y gráficos se escriben a mano (son pocos y chicos). `package.json` y el lock quedan congelados.
7. **Rendimiento.** Cada paquete agrega como mucho **+15 kB gzip** al chunk principal (comparar la salida de
   `npm run build` antes y después). three.js sigue en su chunk lazy. Nada de pedidos a `/api/object` al pasar el
   mouse (4 workers en el servidor, 6 a 20 s por ficha). Las consultas a Gaia por vista llevan debounce y abort.
   Cambiar de pestaña no vuelve a bajar las imágenes de la secuencia.
8. **Accesibilidad.** Contraste AA (texto 4.5:1, controles 3:1), foco visible en todo, pestañas con flechas, todo
   lo del popup también disponible por click o teclado, `aria-live` para el progreso del build y Lighthouse
   Accessibility ≥ 90. Ojo: `--line` (1,3:1) sirve para separadores, **no** para el borde de inputs, chips o
   botones; para eso está `--line-control` (≥ 3,2:1 sobre `--surface-0/1/2`).

**Fuera del plan:** cambios de contrato (`types.ts`), endpoints nuevos, textos de About (son de WS6), funciones
P2 congeladas por D10 (UI-1 Band Equalizer, detección, Planeta X) y precargar la ficha al pasar el mouse.

---

## 3. Dirección visual

### 3.1 Grilla

Escritorio (≥ 1100 px):

```
┌──────────────────────── topbar 48 px (sticky) ────────────────────────┐
│ Errante · SPHEREx sky explorer   Explore  3D models  About  [Live API] │
├──────────────────────────────────────────────┬────────────────────────┤
│ MAPA (llena todo)                            │ DOCK  (--dock-w)       │
│ ┌ search ─────────────┐ ┌ Layers ▾ ┐         │ Barnard's Star  [Catalog]
│ └─────────────────────┘ └──────────┘         │ 17h57m48.5s +04°41′36″ │
│ (Barnard's Star) (Epsilon Indi B) (WISE 0855)│ [Object][Time][Spectrum][3D]
│ (RW Aurigae) (R Draconis) · hover card ┐     │ ┌────────────────────┐ │
│                           next to    │       │ │ contenido de la    │ │
│                           the cursor ┘       │ │ pestaña (scroll    │ │
│ RA 17h57m47s Dec +04°46′  · Static coadd     │ │ interno si hace    │ │
│ (readout del cursor)        NASA/IPAC credit │ │ falta)             │ │
└──────────────────────────────────────────────┴────────────────────────┘
```

- Entre 900 y 1100 px, el dock se angosta a 340 px.
- En ≤ 900 px, el mapa ocupa toda la pantalla y el dock pasa a ser una **hoja inferior** con tres alturas: peek
  (nombre + pestañas), mitad y completa.
- Ficha de campo en escritorio: barra de título de 44 px, reproductor a la izquierda (cuadrado, tan alto como
  quepa) y a la derecha un panel con pestañas: **Light curve · Spectrum · Seasons · Evidence · Object**.

### 3.2 Tokens (nombres concretos; FE-1 los define en `:root`)

Los nombres actuales (`--bg`, `--panel`, `--border`, `--text`, `--muted`, `--accent`, `--button-*`, `--known`,
`--unconfirmed`, `--artifact`, `--injected`, `--error`) **se mantienen como alias** para no romper nada.
Mientras FE-1 no esté en `main`, programá contra estos nombres con fallback: `var(--sp-3, 12px)`.

```css
:root {
  /* Superficies */
  --surface-0: #07090f;              /* fondo de la app (= --bg) */
  --surface-1: #0f1422;              /* paneles, dock */
  --surface-2: #171e31;              /* hover, elementos elevados */
  --surface-glass: rgb(9 13 24 / 0.9); /* 0.78 dejaba --muted en 3,4:1 sobre una zona blanca del mapa; 0.9 → 5,2:1 */
  --glass-blur: 10px;
  --line: #232a3d;                   /* = --border; solo separadores (1,3:1) */
  --line-strong: #34405e;
  --line-control: #626d88;           /* bordes de inputs, chips y botones: 3,55:1 sobre --surface-1 */
  /* Texto */
  --text: #e6e9f2;
  --text-2: #b4bdd1;                 /* secundario: debe pasar AA sobre --surface-1 */
  --muted: #8e97ad;                  /* solo textos chicos de apoyo */
  /* Acento y fuentes de datos (insignias de honestidad) */
  --accent: #7cc4ff;
  --accent-strong: #a6e0ff;
  --accent-ink: #07111c;
  --src-spherex: #7cc4ff;            /* datos SPHEREx reales */
  --src-catalog: #f5c26b;            /* SIMBAD, VSX, exoplanetas, 2MASS/AllWISE */
  --src-gaia: #6ff4f1;               /* marcadores Gaia DR3 (mismo color que #111) */
  --src-model: #c4a5ff;              /* modelos 3D. El contorno de la secuencia de #111 usa este violeta: FE-4 lo
                                        pasa a --src-spherex, porque es la grilla SPHEREx y no un modelo */
  --src-synthetic: #f472b6;          /* SYNTHETIC (mismo color que hoy) */
  --ok: #4ade80;
  --warn: #fbbf24;
  /* Tipografía (sin fuentes externas: cero pedidos de red) */
  --font-ui: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  --fs-2xs: 0.6875rem;  /* 11 px: solo eyebrows en mayúsculas */
  --fs-xs: 0.75rem;     /* 12 px: fuentes, notas */
  --fs-sm: 0.8125rem;   /* 13 px: tablas, controles */
  --fs-md: 0.9375rem;   /* 15 px: cuerpo */
  --fs-lg: 1.0625rem;   /* 17 px: títulos de panel */
  --fs-xl: 1.25rem;     /* 20 px: nombre del objeto */
  --fs-2xl: 1.625rem;   /* 26 px: títulos de página */
  --lh-tight: 1.2;
  --lh: 1.45;
  --fw-medium: 500;
  --fw-bold: 650;
  /* Espaciado (base 4) */
  --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px; --sp-5: 24px; --sp-6: 32px; --sp-7: 48px;
  /* Radios y sombras */
  --r-xs: 4px; --r-sm: 6px; --r-md: 10px; --r-lg: 14px; --r-pill: 999px;
  --shadow-1: 0 1px 2px rgb(0 0 0 / 0.35);
  --shadow-2: 0 6px 20px rgb(0 0 0 / 0.45);
  --shadow-pop: 0 12px 32px rgb(0 0 0 / 0.55);
  /* Layout */
  --topbar-h: 48px;
  --dock-w: clamp(340px, 30vw, 460px);
  --gutter: 12px;
  --control-h: 34px;
  --button-height: 40px;             /* se mantiene */
  --touch-min: 44px;
  /* Capas */
  --z-map-ui: 10; --z-dock: 20; --z-topbar: 30; --z-popover: 40; --z-sheet: 50; --z-modal: 60; --z-toast: 70;
  /* Movimiento */
  --ease-out: cubic-bezier(0.2, 0.8, 0.2, 1);
  --dur-fast: 120ms;
  --dur: 200ms;
  /* Foco */
  --focus-ring: 0 0 0 2px var(--surface-0), 0 0 0 4px var(--accent-strong);
}
@media (prefers-reduced-motion: reduce) { :root { --dur-fast: 0ms; --dur: 0ms; } }
```

### 3.3 Clases utilitarias (FE-1, en `styles.css`, para que nadie más tenga que tocarlo)

| Clase | Para qué |
|---|---|
| `.u-glass` | panel flotante sobre el mapa: `--surface-glass`, `backdrop-filter: blur(var(--glass-blur))`, `--r-md`, `--shadow-2` |
| `.u-panel` | superficie sólida `--surface-1` con borde `--line` |
| `.u-eyebrow` | rótulo chico en mayúsculas (`--fs-2xs`, `letter-spacing: .08em`, `--text-2`) |
| `.u-chip` (+ `[aria-pressed=true]`) | pastilla de 28 px para blancos y filtros |
| `.u-badge` + `--spherex`, `--catalog`, `--gaia`, `--model`, `--synthetic`, `--warn` | insignias de procedencia (borde y texto del color `--src-*`) |
| `.u-btn`, `.u-btn--primary`, `.u-btn--ghost`, `.u-btn--icon` | **una** familia de botones. Primario (el gradiente actual) solo para la acción principal de cada vista (Play, Build). Icono: 32 px (44 px en táctil) |
| `.u-kv` | grilla de dos columnas etiqueta/valor (`dl`) |
| `.u-mono`, `.u-num` | coordenadas e IDs en mono; `font-variant-numeric: tabular-nums` |
| `.u-scroll` | scroll interno con `overscroll-behavior: contain` y barra fina |
| `.u-sr-only`, `.u-truncate` | accesibilidad y texto largo |

### 3.4 Cómo se ven los componentes

- **Sobre el mapa:** todo es `.u-glass` (buscador, chips, capas, lectura del cursor, popup). El mapa nunca queda
  tapado por más del 25 % de su área. **Zonas fijas** para que FE-2/FE-3 y FE-4 no se encimen:
  arriba a la izquierda, buscador y chips (FE-2/FE-3, montados por FE-2 **fuera** de `ExplorerMap`); arriba a la
  derecha, "Layers ▾" (FE-4); abajo a la izquierda, lectura del cursor (FE-4); abajo a la derecha, créditos
  (FE-4); el popup sigue al cursor (FE-4, `--z-popover`). El contenedor de cada zona lleva `pointer-events: none`
  y solo sus controles `pointer-events: auto`, para que el mapa siga arrastrándose por debajo.
- **Dock:** superficie sólida. La cabecera tiene nombre (`--fs-xl`), insignias y coordenadas en mono. Debajo van
  las pestañas, con subrayado de 2 px del acento. Si hay que scrollear, scrollea el contenido, no la página.
- **Pestañas:** muestran su estado en el rótulo, por ejemplo "Time · 40 frames", "Time · building…" con un punto
  animado y "Spectrum · quick look".
- **Gráficos:** un único estilo (FE-8). Ejes y grilla en `--line`, puntos SPHEREx en `--src-spherex`, barras de
  error en `--text-2` y referencias de catálogo en línea punteada `--src-catalog`. Al pasar el mouse se muestra
  un tooltip de vidrio con los valores.
- **Estados:** skeletons con brillo suave en lugar de "Loading…", pasos del build en vez de "Stage: x" y un
  estado vacío con una acción clara.

---

## 4. Reglas para no pisarnos (leer antes de tomar un paquete)

1. **Un paquete = sus archivos.** La lista "Archivos" de cada paquete es exclusiva: nadie más los edita hasta que
   ese paquete se mergee o se libere en el issue. Para verificarlo antes del PR, corré
   `git diff --name-only origin/main...HEAD`: tiene que ser un subconjunto de tu lista.
2. **Archivos congelados para todos los paquetes:** `src/api/types.ts` (contrato), `src/api/client.ts`,
   `src/api/format.ts`, `frontend/ai-usage.json`, `package.json`, `package-lock.json`, `vite.config.ts`,
   `frontend/README.md`, `src/pages/AboutPage.tsx` (textos de WS6) y `tasks/WS5-frontend.md` (el estado se lleva
   en el issue). Los helpers nuevos van en **un archivo nuevo de tu paquete**, no al final de `format.ts`, porque
   dos agregados al final del mismo archivo chocan.
3. **CSS:** solo FE-1 edita `src/styles.css`. Cada paquete crea `src/styles/<paquete>.css`, lo importa desde su
   componente (`import '../styles/map.css'`) y usa **su prefijo de clases**. No redefinas clases viejas de
   `styles.css`: usá clases nuevas en tu JSX. Si una regla vieja molesta, anotala en el issue y FE-1b la borra
   al final.

   | Paquete | Prefijo | Archivo CSS |
   |---|---|---|
   | FE-1 | `.app-`, `.u-` | `src/styles.css` |
   | FE-2 | `.xp-` | `src/styles/explorer.css` |
   | FE-3 | `.sx-` | `src/styles/search.css` |
   | FE-4 | `.mp-` | `src/styles/map.css` |
   | FE-5 | `.oc-` | `src/styles/object-card.css` |
   | FE-6 | `.fd-` | `src/styles/field.css` |
   | FE-7 | `.pl-` | `src/styles/player.css` |
   | FE-8 | `.sci-` | `src/styles/science.css` |
   | FE-9 | `.kit-` (no `.ui-`: se confunde con `.u-` de FE-1) | `src/styles/kit.css` |
   | FE-10 | `.sh-` | `src/styles/sheet.css` |
   | FE-11 | `.kb-` | `src/styles/shortcuts.css` |
   | FE-12 (WS7) | `.s3d-` | `src/three/system.css` |

4. **Orden de carga del CSS:** hoy `main.tsx` importa `./App` **antes** que `./styles.css`, así que lo global se
   carga después y les gana, a igual especificidad, a los CSS de componente. FE-1 invierte ese orden. Mientras
   tanto, los prefijos evitan choques entre paquetes, **pero no alcanzan** cuando hay que pisar una regla vieja
   sobre el mismo elemento (por ejemplo `.sky-map-frame { height: 470px }` o `main { max-width: 1200px }`). En ese
   caso, subí la especificidad una clase (`.mp-root .mp-frame`, `main.xp-app`) en tu propio CSS. Nunca
   `!important`.
5. **Registro de IA por paquete:** nadie toca `frontend/ai-usage.json` (cada PR de WS5 choca en la línea
   `scope`). Cada paquete escribe `frontend/ai-usage/fe-<n>.json` con el mismo esquema. WS7 sigue usando
   `src/three/ai-usage.json`. **Antes del envío** (no después), coordinación agrega esos archivos a la lista de
   registros de `docs/submission/ai-usage.json` y a `AI_USAGE.md` en un PR `chore:`. Fusionarlos en un solo archivo
   puede esperar.
6. **Interfaces entre paquetes (§6):** si necesitás un componente de otro paquete que todavía no está en `main`,
   **no lo crees en su archivo**. Usá lo que hay hoy y cambiá al nuevo con un PR chico después del merge. Las
   props nuevas son **opcionales**, para que nada se rompa.
7. **WS7 es de DankoLiv:** `src/three/*`, `SystemViewer.tsx`, `BodyPanel.tsx`, `SystemsPage.tsx` y
   `SystemPage.tsx` solo se tocan desde una rama `ws7/...`. La guardia `owners` rechaza una rama `ws5/` que los
   toque. Desde WS5 solo se cambia el **contenedor**.
8. **No tocar en `public/sky-map.html` las líneas de `applyPlane`/`setPlane`** (fix del mapa negro, #86). Además,
   **el iframe del mapa no se desmonta ni se oculta** (`display: none`, `hidden`, `key` que cambie, render
   condicional) en ningún layout: escritorio, hoja inferior, modo teatro ni cambio de pestaña. Cada remontaje
   reinicia Aladin y su WebGL, vuelve a correr la carrera del plano 90 y vuelve a bajar el HiPS. Cambiarle el
   tamaño sí se puede (Aladin escucha el resize).
9. **Probar en los tres modos:** live API (`?mode=api` o la URL pública), estático real
   (`?mode=static&dataset=real`) y estático sintético (`?mode=static`, donde tiene que verse SYNTHETIC).
10. **Nada de subcarpetas nuevas en `src/components/`.** El test de WS7 `three/colorModes.test.ts` ("main-chunk
    safety") recorre solo `components/*.{ts,tsx}`, `pages/*`, `api/*.ts` y `three/*`. Si algo alcanzable desde
    `SystemViewer.tsx`, `BodyPanel.tsx` o `SystemsPage.tsx` (por ejemplo `SyntheticBadge.tsx` o
    `ErrorBoundary.tsx`) importa de `components/ui/…`, el import no se resuelve y **CI falla**. Los componentes
    nuevos van planos en `src/components/`. Los `.css` sí pueden ir en `src/styles/` (el test los saltea).
11. **Exports compartidos: solo agregar.** No cambies la firma de algo que importa otro paquete:
    `searchSequences` y `SearchSequence` (FE-3 → FE-2 y FE-4), `useScienceRequest` (FE-8 → FE-6),
    `ErrorBoundary` y `SyntheticBadge` (FE-9 → FE-1, FE-2, FE-6 y WS7), `ObjectLookup`, `lookupKey`,
    `positionLookup` y `matchSummary` (FE-5 → WS7), `SHOWCASE_TARGETS` (FE-3 → FE-5), `validPosition` (FE-9 → FE-4).
12. **Un solo `map.on` por evento.** Aladin guarda un único callback por nombre (`callbacksByEventName[name] = fn`).
    Hoy solo está `click` (#114). FE-4 es el único que registra `objectHovered`, `objectHoveredStop`,
    `objectClicked`, `mouseMove`, `positionChanged` y `zoomChanged`; nadie más agrega otro `map.on` con esos nombres.

---

## 5. Paquetes

Formato: **Objetivo · Resultado visible · Archivos (exclusivos) · Nuevos · Depende de · Aceptación (medible) ·
Horas · Dueño sugerido · Rama · Prioridad.** Prioridad **A** = apunta a una ventana de merge de hoy; **B** = si
llega; **C** = después del envío.

### FE-0 · Merge de los PRs abiertos (bloquea al resto)
- **Objetivo:** liberar los archivos del mapa, el explorador y el reproductor.
- **Pasos:** #114 → #111 → #116. #111 **tiene conflicto con `main`** desde #107: hay que hacer
  `git pull origin main` en `ws5/v17-gaia-footprint`, conservar el import de `ObjectSystemPreview` y borrar el de
  `separationArcsec`. **Sin force-push.** Los tres son disjuntos entre sí (`merge-tree` limpio).
- **Archivos:** los de los tres PRs (`public/sky-map.html`, `ExplorerMap.tsx`, `gaiaLayer.ts`, `skyFootprint.ts`,
  `skySearch.ts`, `PositionResults.tsx`, `SkyExplorer.tsx`, `SystemPreview.tsx`, `FieldPage.tsx`,
  `BlinkViewer.tsx` + test, 2 líneas de `styles.css`, `ai-usage.json`).
- **Aceptación:** los tres en `main` con CI verde; el mapa no carga negro; Barnard's Star se reproduce.
- **Horas:** 0,5–1 · **Dueño:** mateoa007 (revisa faricool54) · **Prioridad:** A, **lo antes posible (objetivo
  17:15)**. Ya no hay freeze a las 17:00, pero FE-2, FE-3, FE-4, FE-6 y FE-7 esperan por esto.
- Al resolver el conflicto de `PositionResults.tsx`, conservar también `import type { ObjectLookup }` y la prop
  `lookup` de #107 (WS7, V14); `TARGET_RADIUS_ARCSEC` se va con #111 (lo reemplaza `localTargetSequences`).

### FE-1 · Shell, tokens y navegación (+ FE-1b limpieza al final)
- **Objetivo:** base visual común y una barra superior que oriente.
- **Resultado visible:** topbar fija de 48 px con la marca, **Explore · 3D models · About**, el link activo marcado
  y una pastilla "Live API" o "Static data". Favicon. Tipografía y espaciado consistentes en todas las páginas.
  Footer compacto, sin footer en la home (los créditos de NASA/IPAC quedan en el mapa).
- **Archivos:** `src/styles.css`, `src/App.tsx`, `src/main.tsx`, `index.html`.
- **Nuevos:** `public/favicon.svg`, `frontend/ai-usage/fe-1.json`.
- **Detalle:**
  - Tokens y utilitarias de la §3, con los nombres viejos como alias.
  - `main.tsx` importa `styles.css` antes que `App`.
  - `App.tsx` marca `aria-current="page"` y pone `document.documentElement.dataset.page` (`home`, `field`,
    `system`, `systems`, `about`) en un efecto. **`App.tsx` no renderiza `<main>`**: cada página trae el suyo, así
    que la regla de ancho completo de la home la pone FE-2 en su CSS (`main.xp-app`), no FE-1.
  - Oculta el footer en la home (`data-page="home"`). Los créditos siguen visibles en el mapa (§2.4).
  - La topbar mide **exactamente** `--topbar-h` y no se parte en dos líneas a ≥ 900 px. FE-2 calcula el alto del
    mapa con ese token.
  - Favicon propio, sin el logo, la "meatball" ni otros elementos de marca de la NASA (AGENTS.md, regla 14).
  - **No borra reglas viejas** en esta etapa: eso queda para FE-1b.
- **Depende de:** FE-0 (#111 cambia 2 líneas de `styles.css`).
- **Aceptación:**
  - Capturas antes y después de `#/about`, `#/field/barnards-star` y `#/systems`: sin cambios de layout salvo la
    topbar y la tipografía. La home tampoco cambia, salvo la topbar y el footer.
  - La topbar sigue visible al scrollear `#/about` y mide `--topbar-h` a 900, 1366 y 1920 px de ancho.
  - En la home, el link activo tiene `aria-current`.
  - Contraste (calculado en esta revisión; confirmar en DevTools): `--text-2` 9,7:1 y `--muted` 6,3:1 sobre
    `--surface-1`; `--line-control` 3,55:1.
  - `python scripts/dev.py check` en verde.
- **FE-1b (prioridad C, al final):** borra de `styles.css` las reglas que quedaron sin uso (explorador viejo,
  sección 3D que FE-12 movió a `three/system.css`) y monta `ShortcutsHelp` de FE-11 en la topbar. **Antes de
  borrar una clase, buscala en todo `src/`, `three/` incluido**: `SystemViewer.tsx` (WS7) usa `.blink-controls`,
  `.transport-btn`, `.segmented` y `.overlay-toggle`, que son clases del reproductor. Aunque FE-7 deje de usarlas,
  el 3D las sigue necesitando.
- **Horas:** 1,5 (+0,5 para FE-1b) · **Dueño:** **libre** (candidato: V0id47, que cerró WS2 según #100; a
  confirmar). Si a las 17:15 sigue libre, lo toma faricool54+Claude porque desbloquea FE-2. · **Rama:**
  `ws5/fe-1-shell-tokens` · **Prioridad:** A.

### FE-2 · Home como explorador a pantalla completa (mapa + dock)
- **Objetivo:** el recorrido mapa → click → video sin scroll.
- **Resultado visible:**
  - El mapa llena `100dvh - var(--topbar-h)`, con el buscador y los chips de los cinco blancos flotando arriba a
    la izquierda.
  - A la derecha, el **dock** con cabecera (nombre, insignias, coordenadas, Copy link, Open field page) y las
    pestañas **Object · Time · Spectrum · 3D**, siempre visibles.
  - Sin selección, el dock muestra la bienvenida en lugar del hero: "Watch the infrared sky change" y una línea
    "Pick a challenge target, search a name, or click any star". **El texto lo revisa WS6 (rpccp).**
  - Desaparecen el hero, el formulario largo y la grilla "Available sequences" (y con ella las tarjetas `job-*`,
    pendiente de #100). Las secuencias guardadas siguen al alcance desde la búsqueda y los chips.
- **Archivos:** `src/pages/HomePage.tsx`, `src/components/SkyExplorer.tsx`, `src/components/PositionResults.tsx`,
  `src/components/SystemPreview.tsx`.
- **Nuevos:** `src/components/ExplorerDock.tsx`, `src/styles/explorer.css`, `frontend/ai-usage/fe-2.json`.
- **Detalle:**
  - **Un solo camino `select(point, origin)`** para click en el mapa, chip, búsqueda y URL compartida: abre el dock
    y fija el objeto. Si hay una secuencia guardada a < 3″, la abre en Time. Si no, se aplica D-1 (§9). Por defecto,
    conservador: el click en el mapa sigue lanzando el build en modo live, como hoy, y chip o búsqueda **no**
    lanzan builds nuevos, sino que muestran **Build SPHEREx sequence** bien visible. **No existe un endpoint para
    cancelar jobs**: abortar en el cliente solo deja de mirar, y el servidor sigue construyendo.
  - **El mapa no se recentra cuando la selección viene del propio mapa** (`origin === 'map'`). Hoy `locate()` cambia
    `center`, `ExplorerMap` manda `position` y Aladin hace `gotoRaDec`: la estrella clickeada salta al centro y el
    popup fijado de FE-4 queda apuntando a otra cosa. Se recentra solo con chip, búsqueda o URL. Esto pide
    separar `mapCenter` de `selection` en `SkyExplorer.tsx`.
  - Si el click cae dentro del contorno de la secuencia abierta, se conserva ese campo (seguimiento de #111). El
    dato llega hecho desde FE-4 (`onSelect` trae `insideFieldId`), así FE-2 no necesita tocar `skyFootprint.ts`.
  - **Se borra el `scrollIntoView`** (`SkyExplorer.tsx:65-69`).
  - RA/Dec, lado del campo y detector pasan a **"Build options"** plegado dentro de Time, con el botón **Build
    SPHEREx sequence** siempre visible.
  - El progreso del job usa `<JobProgress>` de FE-9 cuando esté; mientras tanto, el texto actual.
  - La pestaña Time **no se desmonta** al cambiar de pestaña (`hidden`), y **se pausa** al ocultarse. La `key` del
    panel deja de depender de `quickLook`, así no se vuelven a bajar los frames. La pestaña 3D sí se desmonta al
    salir, para liberar su contexto WebGL.
  - Al terminar el build, la pestaña muestra "Time · ready". **No cambia de pestaña sola.**
  - La home ocupa todo el ancho con `main.xp-app { max-width: none; padding: 0 }` en `explorer.css`; la
    especificidad (0,1,1) le gana a `main` de `styles.css` sin depender de FE-1. El alto del mapa es
    `calc(100dvh - var(--topbar-h, 49px))`.
  - En modo estático sintético, al quitar la grilla "Available sequences" desaparece su `SyntheticBadge`: el dock
    o la cabecera de la home tienen que mostrar **"SYNTHETIC DATA · NOT SPHEREx"** sin interacción.
  - En ≤ 900 px, versión mínima apilada (mapa ≥ 50vh y el dock debajo) hasta que entre FE-10.
- **Depende de:** FE-0 (#111), **FE-4a.0** (`ExplorerMap layout="fill"`: sin eso la barra de capas queda arriba
  del iframe y el iframe sigue con 470 px fijos de `styles.css`) y FE-1 (footer oculto en la home y `--topbar-h`).
  Adopta cuando estén: FE-3 (`TargetChips`), FE-5 (`ObjectCard variant`), FE-6 (`SequencePlayer`, que reemplaza
  `FieldPage embedded`), FE-7 (`compact`), FE-9 (`Tabs`, `JobProgress`, `EmptyState`), FE-10 (`BottomSheet`) y
  FE-12 (`ObjectSystemPreview compact` y `SystemViewer compact`).
- **Aceptación (1366×650, `#/`)**, en dos etapas, porque parte depende de otros paquetes:
  - **Etapa 1 (FE-2 solo, con FE-0 + FE-4a.0 + FE-1 en `main`):**
    - `scrollHeight - innerHeight ≤ 1` y `scrollWidth - innerWidth ≤ 1` (snippet en la §8). Hoy: 3307 px de alto.
    - El iframe del mapa mide al menos 880×580 y empieza en y ≤ 50. Hoy: 738×470 en y = 546.
    - Al cargar se ven el buscador, los cinco chips (o el selector actual hasta FE-3) y el dock con sus cuatro
      pestañas.
    - Click en el mapa → el dock se actualiza, `scrollY` sigue en 0 y **la vista de Aladin no se recentra**.
    - Ir de Time a Spectrum y volver a Time **conserva el fotograma** en el que estaba el reproductor, y no
      reaparece "Loading sequence images n/N". El caché de Network igual sirve los PNG, así que contar pedidos no
      prueba nada.
    - A 1920×1080 el dock no pasa de 460 px y el mapa crece.
    - Las insignias de procedencia se ven en cada pestaña y el crédito del mapa sigue visible.
    - Funciona en `?mode=static&dataset=real`, y en `?mode=static` se ve "SYNTHETIC DATA · NOT SPHEREx".
    - Chip o búsqueda **no** crean jobs nuevos (D-1 por defecto): Network muestra 0 `POST /api/jobs`.
  - **Etapa 2 (después de FE-6 `SequencePlayer` + FE-7 `compact`):** chip "Barnard's Star" → Time reproduce la
    secuencia guardada, con la imagen ≥ 360 px y los controles enteros **dentro del dock sin scroll interno**. Con
    el reproductor actual, los controles miden unos 350 px y no entran: hasta la etapa 2 se acepta un scroll
    interno del dock.
- **Horas:** **4** (3 era optimista: es el nudo de integración, con `select()`, el dock, las pestañas, el centro
  separado de la selección y D-1) · **Dueño:** **mateoa007** (ya conoce estos archivos) · **Rama:**
  `ws5/fe-2-explorer-layout` · **Prioridad:** A.

### FE-3 · Buscador y chips de los cinco blancos
- **Objetivo:** encontrar algo en un paso y tener los cinco blancos de la demo a un click.
- **Resultado visible:**
  - Buscador de una línea (≤ 44 px) con la lista de resultados **superpuesta**, sin empujar el layout. Se maneja
    con ↑/↓/Enter/Esc, `/` lo enfoca y muestra la pista "Name or RA Dec".
  - `<TargetChips>`: cinco pastillas con los nombres de `SHOWCASE_TARGETS` (Barnard's Star, Epsilon Indi B,
    WISE 0855−0714, RW Aurigae, R Draconis) y un mini estado: cantidad de frames de la secuencia guardada y el
    **caso de prueba** ("motion test" o "brightness test"). Nunca "detected", "confirmed" ni "measured motion":
    `showcase.ts` aclara que son presets de búsqueda, no validaciones R05 cerradas. Si la secuencia es sintética,
    el chip lleva SYNTHETIC. En modo estático, los chips de campos reales usan el `href` del otro dataset (recarga
    completa, como hoy `selectSearchSequence`).
- **Archivos:** `src/components/SkySearch.tsx`, `src/api/skySearch.ts` + test, `src/api/showcase.ts` (solo
  agregar).
- **Nuevos:** `src/components/TargetChips.tsx`, `src/styles/search.css`, `frontend/ai-usage/fe-3.json`.
- **Interfaz:** `SkySearch` mantiene sus props. `TargetChips` recibe `{ sequences, activeName?,
  onPick(target, sequence?) }`. `searchSequences`, `localTargetSequences`, `SearchSequence` y `SHOWCASE_TARGETS`
  solo se amplían (§4.11): los usan FE-2, FE-4 y FE-5.
- **Atajo `/`:** lo implementa FE-3 dentro de `SkySearch` (ignorando el foco en inputs). FE-11 no lo duplica.
- **Depende de:** FE-0 (#111 toca `skySearch.ts`).
- **Aceptación:**
  - La lista de resultados abierta no cambia la altura del bloque del buscador (mide ≤ 44 px).
  - Teclado: `/` enfoca, ↓ y Enter eligen, Esc cierra (probado sin mouse).
  - Los cinco chips entran en una o dos filas sobre un mapa de 900 px de ancho.
  - A 375 px los chips scrollean en horizontal **dentro de su fila**, sin scroll de página.
  - Tests de `skySearch` en verde, con los nuevos casos.
- **Horas:** 1,5 · **Dueño:** **libre** · **Rama:** `ws5/fe-3-search-chips` · **Prioridad:** A.

### FE-4 · Mapa: popup junto al mouse, lectura del cursor y capas
- **Objetivo:** lo que pidió el usuario: **los datos de la estrella aparecen al lado del mouse.**
- **Resultado visible:**
  - **Hover sobre un marcador Gaia:** tarjeta de vidrio en el cursor (+14 px, se da vuelta cerca de los bordes).
    Ejemplo con Barnard's Star (valores de la auditoría, **sin verificar en esta revisión**; los textos finales salen
    del fixture TSV real): "Gaia DR3 4472832130942575872", "G 8.19 · BP−RP 2.83", "Parallax 546.98 ± 0.04 mas →
    ≈ 1.83 pc (1/parallax)", "Proper motion 10.39″/yr", "RV −110.5 km/s" y "Position predicted for <date> from
    Gaia DR3 proper motion". Pie: "Gaia DR3 catalog · not SPHEREx measurements · Click to select" (en modo live
    se agrega "· builds a SPHEREx sequence"; en estático no se promete una secuencia).
    **Sin Teff ni `Dist` de GSP-Phot en el popup:** la ficha ya muestra la temperatura con la lógica revisada de
    WS3 (#117, con el respaldo de Gaia y sus advertencias). Dos temperaturas distintas para la misma estrella, una
    en el popup y otra en el dock, confundirían. GSP-Phot además tiene sesgos conocidos en enanas M como Barnard.
  - **Hover sobre un blanco o una secuencia guardada:** "Barnard's Star · Challenge target", "40 SPHEREx frames ·
    <date> → <date>" y "Click to play". Si la secuencia es sintética (`?mode=static`): "40 **synthetic** frames ·
    not SPHEREx".
  - **Cielo vacío:** lectura fija del cursor abajo a la izquierda ("RA 17h57m47.1s · Dec +04°46′07″") y, si
    corresponde, "Inside saved sequence: Barnard's Star · Click to inspect".
  - **Click en una estrella:** la selecciona **en su posición propagada**, no donde está el cursor. El popup queda
    fijado (× o Esc lo cierra) y la ficha completa aparece en el dock. Si la ficha ya se cargó en esta sesión, el
    popup fijado muestra el resumen (`ObjectSummary` de FE-5). El popup fijado **se cierra al arrastrar o hacer
    zoom** (mensaje `view`), porque su `x, y` deja de valer; el dock conserva el dato. Esto supone que FE-2 no
    recentra el mapa en los clicks del propio mapa (ver FE-2).
  - **Capas** en un menú flotante "Layers ▾": longitud de onda, AllWISE, contorno, Gaia y "Zoom to sequence". Lleva
    la leyenda de los círculos cian (seguimiento de la revisión de #111). **Los créditos no van dentro del menú**:
    quedan en la esquina inferior derecha, compactos y siempre visibles (§2.4). El contorno de la secuencia pasa
    del violeta `#c4a5ff`, que es el color de "modelo 3D" en los tokens, a `--src-spherex`.
- **Archivos:** `public/sky-map.html`, `src/components/ExplorerMap.tsx`, `src/api/gaiaLayer.ts` + test,
  `src/api/skyFootprint.ts`.
- **Nuevos:** `src/components/MapHoverCard.tsx`, `src/api/mapHover.ts` + `mapHover.test.ts` (formateadores y
  reglas de honestidad), `src/styles/map.css`, `frontend/ai-usage/fe-4.json`.
- **Fases:**
  - **FE-4a.0 (primer PR, ~45 min, desbloquea FE-2):** `ExplorerMap` acepta `layout?: 'panel' | 'fill'` (por
    defecto `'panel'`, igual que hoy). En `'fill'`: el iframe ocupa el 100 % del contenedor, con
    `.mp-root .mp-frame` para ganarle a `.sky-map-frame { height: 470px }`; la barra de herramientas pasa a
    "Layers ▾" flotante y los créditos pasan a la esquina. Sin hover todavía. FE-2 lo usa con `layout="fill"`.
  - **FE-4a** (hover + cursor + click preciso sobre los marcadores que ya existen, más una capa nueva de blancos y
    secuencias). Ojo: hoy los marcadores Gaia de #111 **solo existen con una secuencia abierta y la casilla "Gaia
    DR3" encendida, que por defecto está apagada** (`showGaia = false`). Sin FE-4b ni D-4, al cargar la home no hay
    ninguna estrella con popup, solo los cinco blancos y la lectura del cursor.
  - **FE-4b** (Gaia **por vista en cualquier parte del cielo**: si el FoV es ≤ 1°, consulta a VizieR CfA con
    debounce de 500 ms, `-sort=Gmag`, ≤ 500 filas, abort de la anterior y LRU de 20 vistas. Si el FoV es mayor,
    muestra la pista "Zoom in to see Gaia stars"). **Es lo que pidió el usuario al pie de la letra** ("los datos de
    la estrella al lado del mouse" en cualquier estrella), así que sube a prioridad **A−**: va justo después de
    4a, antes que cualquier B. Comparte el catálogo `gaia` del iframe con las predicciones por secuencia de #111:
    el padre decide qué conjunto manda; si hay una secuencia abierta, ganan sus predicciones a la época mediana.
  - **Se puede empezar ya** por los archivos nuevos (`MapHoverCard`, `mapHover.ts` y sus tests), que no tocan
    #111/#114. El cableado en `sky-map.html` y `ExplorerMap.tsx` va después de FE-0.
- **Protocolo `postMessage`:** ver §6.2. Se usan los eventos de Aladin 3.8.2 `objectHovered`,
  `objectHoveredStop`, `objectClicked`, `mouseMove`, `positionChanged` y `zoomChanged`. Revisado de nuevo en
  `dist/aladin.js` en esta revisión:
  - `mouseMove`, `objectHovered` y `objectHoveredStop` solo se disparan en modo PAN y sin arrastre. `mouseMove` se
    llama **antes** que `objectHovered` en el mismo movimiento, así que el padre le da prioridad a `hover`.
  - `objectHovered` se llama **una vez por cada objeto nuevo** de `closestObjects(x, y, 5)`, y eso incluye el
    contorno de #111. El iframe manda solo el primer objeto que no sea footprint (`!k.isFootprint()`).
  - `objectClicked` también se llama por cada objeto, footprints incluidos, y **antes** que `click` en el mismo
    evento. Se manda un único `select` con el primer objeto que no sea footprint, y el padre descarta el `select`
    genérico **inmediatamente siguiente** (≤ 300 ms) a uno con `sourceId`. Así no se toca la línea de #114.
  - En táctil, `touchend` usa 15 px de tolerancia: un tap sobre una estrella dispara `objectClicked` (D-2).
  - Ningún evento de Aladin avisa cuando el mouse sale del iframe: escuchar `mouseleave` en `#map` (iframe) y
    `pointerleave` en el `<iframe>` (padre), y ocultar el popup no fijado.
  - El bloque nuevo va **después** del `map.on('click')` y sin reescribir el handler de mensajes (§4.12).
  - `sourceSize: 4` de #111 con 5 px de tolerancia cuesta de apuntar: subirlo a 7–8 y agregar `hoverColor`.
- **Reglas de honestidad (con test):**
  - La distancia ≈ 1/paralaje se muestra solo si `Plx > 0` y `Plx/e_Plx > 5`. Si no, "Parallax too uncertain for
    a distance".
  - Sin `Teff` ni `Dist` (GSP-Phot) en el popup; la temperatura vive en la ficha (WS3).
  - Las posiciones se propagan a la mediana de la secuencia abierta o a MJD 61000 (`astrometricPlace`) y el popup
    dice para qué fecha.
  - Toda tarjeta Gaia lleva "Gaia DR3 catalog · not SPHEREx".
  - Las columnas Gaia nuevas (`e_Plx`, `BP-RP`, `VarFlag`) se verifican contra un TSV real de VizieR guardado como
    fixture. El encabezado que espera `readMarkers` cambia con las columnas: actualizar también el test de
    "cono vacío". Si VizieR no responde, test `network` y nota en el PR, sin inventar.
  - Ningún texto externo pasa por `innerHTML`: el iframe solo manda `id` y números, y React dibuja el resto.
- **Depende de:** FE-0 (#111 y #114). Usa `ObjectSummary` y `peekObjectContext` de FE-5 cuando estén.
- **Aceptación:**
  - El popup aparece en ≤ 100 ms sobre un marcador con datos en memoria (Performance, o `performance.now()` entre
    el mensaje y el render).
  - En las cuatro esquinas del mapa el popup no se sale del contenedor (`getBoundingClientRect` dentro del
    `.explorer-map`).
  - **Pasar por 20 estrellas hace 0 pedidos a `/api/object`** (Network).
  - Click en un marcador → el `ra/dec` del `select` (y de la URL compartida) coincide con el del marcador en
    ≤ 1e-6° (≈ 0,004″). Se mide en el payload y no en el texto del dock, que redondea.
  - Click sobre el contorno de la secuencia, sin estrella cerca → `select` genérico, nunca la posición de una
    esquina del polígono.
  - Sacar el mouse del mapa por cualquier borde oculta el popup no fijado.
  - FE-4a.0: con `layout="fill"`, en un contenedor de 956×602 el iframe mide 956×602, y en `'panel'` todo queda
    igual que hoy (captura).
  - FE-4b: mover y hacer zoom produce ≤ 1 consulta a VizieR cada 500 ms de reposo; las anteriores salen
    canceladas.
  - El mapa no queda negro (#86) y arrastrar no selecciona (#114).
  - Táctil (`pointer: coarse`): un tap selecciona y el dato completo va al dock (no hay hover).
  - Los tests de `mapHover` cubren la regla de distancia, el movimiento propio total y los rótulos.
- **Interfaz extra para FE-2:** `onSelect` trae `insideFieldId?: string` cuando el click cae dentro del contorno
  visible (FE-4 agrega `pointInFootprint` a su `skyFootprint.ts`). Así FE-2 no toca ese archivo.
- **Horas:** 0,75 (4a.0) + 2 (4a) + 1,5 (4b) · **Dueño:** **faricool54 + Claude** · **Rama:**
  `ws5/fe-4a0-map-fill`, `ws5/fe-4-map-hover` y `ws5/fe-4b-gaia-view` · **Prioridad:** 4a.0 A (primero), 4a A,
  4b A− (ver D-4).

### FE-5 · Ficha del objeto compacta + caché
- **Objetivo:** que los datos de la estrella se lean de un vistazo dentro del dock y que el popup pueda
  reutilizarlos.
- **Resultado visible:**
  - **Cabecera** (≤ 64 px): nombre, tipo, insignia de coincidencia e insignia **"Catalog · not SPHEREx"** siempre
    visible.
  - **Datos clave en grilla de dos columnas**, una fila por dato (valor y estado en la misma línea; la fuente en
    `title` y en una nota de 11 px): distancia, Teff, tipo espectral, movimiento propio, variabilidad y planetas.
  - Fotometría y servicios siguen plegados.
  - Skeleton mientras carga (FE-9), en lugar del texto largo.
- **Archivos:** `src/components/ObjectCard.tsx`, `src/api/objectCard.ts` + test (**solo agregar**: WS7 importa
  `ObjectLookup`).
- **Nuevos:**
  - `src/api/objectCardCache.ts` + test: LRU de 50 entradas `lookupKey → ObjectContextResponse`,
    `peekObjectContext(lookup)` y `getObjectContextCached(lookup, signal)`. Guarda también **el pedido en vuelo**
    (single-flight) y cuenta quién lo espera: si la ficha se desmonta, no aborta un pedido que todavía espera la
    pestaña 3D. Los errores no se guardan.
  - `src/components/ObjectSummary.tsx`: ≤ 6 líneas, para el popup fijado.
  - `src/styles/object-card.css` y `frontend/ai-usage/fe-5.json`.
- **Interfaz:** `<ObjectCard lookup variant?="dock" | "full" />`, `<ObjectSummary data />` y
  `peekObjectContext(lookup)`.
- **Depende de:** nada (se puede empezar ya). Adopta `Skeleton` de FE-9 cuando esté.
- **Aceptación:**
  - En un dock de 420 px, la ficha de Barnard's Star con los detalles plegados mide ≤ 480 px.
  - Volver a elegir el mismo objeto en la sesión hace **0 pedidos nuevos a `/api/object` desde la ficha**. Ojo:
    `three/ObjectSystemPreview.tsx` (WS7) llama a `client.getObjectContext` por su cuenta. Hasta que FE-12 cambie
    a `getObjectContextCached`, abrir la pestaña 3D hace su propio pedido (el backend lo resuelve con
    single-flight y caché, pero ocupa un worker). La medición se hace con la pestaña 3D cerrada.
  - Siguen visibles "Catalog context, not SPHEREx measurements", el aviso de "Partial" y "Identity not secure".
  - Los tests de `objectCard` siguen en verde, más los nuevos de la caché.
- **Horas:** 1,5 · **Dueño:** **faricool54 + Claude** · **Rama:** `ws5/fe-5-object-card` · **Prioridad:** A.

### FE-6 · Ficha de campo como dashboard
- **Objetivo:** `#/field/<id>` sin scroll, con el video y la evidencia lado a lado.
- **Resultado visible:**
  - Barra de título de 44 px: "← Explore", nombre, insignias (SPHEREx o SYNTHETIC), "3D model" y "Copy link".
  - A la izquierda, el reproductor. A la derecha, un panel con pestañas **abiertas por defecto: Light curve**
    (si existe el producto) · **Spectrum** · **Seasons** · **Evidence** · **Object**.
  - "No candidate measurements provided…" pasa a una línea dentro de Evidence, en vez de ocupar el mejor lugar de
    la pantalla. El texto sigue diciendo que **el análisis no se ejecutó**, no que "no se encontró nada" (AGENTS.md,
    regla 12).
  - Botón **Expand** (modo teatro) en el reproductor; Esc lo cierra.
- **Archivos:** `src/pages/FieldPage.tsx`, `src/components/FieldComparisons.tsx`,
  `src/components/CandidateList.tsx`, `src/components/CandidatePanel.tsx`, `src/components/SkyMap.tsx`.
- **Nuevos:** `src/components/SequencePlayer.tsx`, `src/styles/field.css`, `frontend/ai-usage/fe-6.json`.
  `SequencePlayer` carga el campo y arma la barra de modo/detector + `BlinkViewer` + Expand: es la pieza que FE-2
  usa en Time.
- **Interfaz:** `<SequencePlayer fieldId compact? />`. `FieldPage embedded` **sigue funcionando** hasta que FE-2
  cambie a `SequencePlayer`; después, FE-1b o FE-6 lo borran.
- **Depende de:** FE-0 (#111 toca `FieldPage`) y **FE-7** para el criterio de la imagen: 650 − 48 − 44 = 558 px
  libres, que alcanzan para 460 px de imagen solo con el transporte en una fila de ≤ 56 px. Usa `Tabs` de FE-9 y
  las variantes de FE-8 cuando estén.
- **Aceptación (1366×650, `#/field/barnards-star` y `#/field/rw-aurigae`):**
  - Sin scroll de página. Hoy: 2010 px.
  - Con FE-7 en `main`: la imagen mide ≥ 460 px y los controles se ven enteros. Antes de FE-7: imagen ≥ 380 px y
    scroll interno en la columna del reproductor.
  - En ≤ 900 px, el reproductor va primero y las pestañas debajo. El criterio era de FE-10, pero el CSS es de
    FE-6.
  - En RW Aur la curva de luz se ve **sin ningún click**. Hoy está cerrada en y = 1690.
  - La procedencia sigue disponible (plegada).
  - La predicción de catálogo y la retícula de WS7 siguen funcionando.
- **Horas:** 2,5 · **Dueño:** **libre** (natural para mateoa007 después de FE-2) · **Rama:**
  `ws5/fe-6-field-dashboard` · **Prioridad:** B.

### FE-7 · Reproductor (BlinkViewer) compacto
- **Objetivo:** que el reproductor entre en el dock y en el dashboard sin perder funciones.
- **Resultado visible:**
  - El escenario se ajusta al alto disponible (cuadrado, `min(ancho, alto libre)`).
  - El transporte va en **una fila de ≤ 56 px**: play, paso, scrubber con fechas, velocidad, zoom 1/2/4× y
    predicción.
  - Las notas ("Source and method", ayuda de teclado) pasan a un popover (i).
  - La calidad por fotograma de #116 se muestra como chips compactos.
- **Archivos:** `src/components/BlinkViewer.tsx` + `BlinkViewer.test.tsx`, `src/components/blinkModes.ts` + test,
  `src/components/framePrediction.ts` + test.
- **Nuevos:** `src/styles/player.css`, `frontend/ai-usage/fe-7.json`.
- **Restricción:** no cambiar la llamada a `three/blinkTarget.ts` (WS7). Las clases `.blink-controls`,
  `.transport-btn`, `.segmented` y `.overlay-toggle` las comparte `SystemViewer.tsx` (WS7). FE-7 puede dejar de
  usarlas en `BlinkViewer` y pasar a `.pl-`, pero sus reglas en `styles.css` se quedan (§FE-1b).
- **Depende de:** FE-0 (#116).
- **Aceptación:**
  - Dentro de un contenedor de 396×470 px, imagen y transporte entran sin overflow.
  - Space y ←/→ siguen funcionando.
  - Tests de #116 en verde, más un test nuevo de la variante compacta.
  - Las etiquetas "catalog prediction" y SYNTHETIC se mantienen.
- **Horas:** 2 · **Dueño:** **libre**. Era natural para mateoa007, autor de #116, pero con FE-0 + FE-2 ya tiene
  ~5 h hasta las 22:30. Candidato: V0id47, a confirmar · **Rama:** `ws5/fe-7-player` · **Prioridad:** B+ (lo
  necesitan la etapa 2 de FE-2 y el criterio de imagen de FE-6).

### FE-8 · Curva de luz y espectro
- **Objetivo:** resultado primero y un solo estilo de gráfico.
- **Resultado visible:**
  - **LightCurvePanel `variant="inline"`:** carga al montarse, sin abrir un `<details>`. Muestra la línea titular
    (periodo y cambio, con los textos de `lightcurve.ts`) y el gráfico (≤ 240 px de alto) con un tooltip por
    punto: fecha, Δmag y flags.
  - **PositionSpectrum:** gráfico primero, después el resumen ("N usable / M measured"). Los controles van en
    "Options" plegado y el quick look sigue siendo automático.
  - **`SciencePlot`** compartido por el espectro, la curva y `SpectrumChart`.
- **Archivos:** `src/components/LightCurvePanel.tsx`, `src/api/lightcurve.ts` + test (**cuidado**: el test compara
  contra los bundles reales; no cambiar expectativas sin avisar a rpccp), `src/components/PositionSpectrum.tsx`,
  `src/components/SpectrumChart.tsx`, `src/components/useScienceRequest.ts`, `src/api/science.ts` + test (solo
  agregar).
- **Nuevos:** `src/components/SciencePlot.tsx` + test, `src/styles/science.css`, `frontend/ai-usage/fe-8.json`.
- **Interfaz:** `<LightCurvePanel targetId variant?="inline" | "panel" />` (por defecto, el comportamiento actual)
  y `<PositionSpectrum ... compact? />`. `useScienceRequest` también lo usa `FieldComparisons` (FE-6): solo
  ampliar su firma (§4.11).
- **Depende de:** nada (se puede empezar ya).
- **Aceptación:**
  - En RW Aur y R Dra la curva y su titular se ven sin clicks en la variante inline.
  - En un contenedor de 420×480 px, el gráfico del espectro y su resumen se ven sin scroll.
  - Las leyendas honestas siguen ahí ("Static surface brightness (MJy/sr)…" y "do not interpret a mixed-epoch
    curve as a simultaneous spectrum").
  - `lightcurve.test.ts` pasa sin tocar las expectativas.
- **Horas:** 2,5 · **Dueño:** **faricool54 + Claude** si llegan después de FE-4a.0, FE-4a, FE-5 y FE-4b (eso ya
  son ~6 h, más revisiones y deploys de coordinación). Si no, que lo tome otra persona. · **Rama:**
  `ws5/fe-8-science-panels` · **Prioridad:** A (curva abierta, ~1 h) / C (`SciencePlot` unificado).

### FE-9 · Estados de carga, vacío y error + primitivas UI
- **Objetivo:** que la app nunca parezca colgada y que todos usen las mismas piezas.
- **Resultado visible:**
  - **Skeletons** en la ficha, el espectro y la secuencia.
  - **`JobProgress`:** pasos Queued → Building real observations (`status: running`, `stage: build`) →
    Publishing (`stage: publish`; el backend pasa por un estado interno `publishing` antes de `ready`) → Ready, con
    tiempo transcurrido y **sin porcentaje inventado** (el backend no lo informa). Estados finales claros: no
    coverage, failed (también `stage: interrupted`) y pipeline unavailable, con su acción (Retry o "Try another
    position"). Un `stage` desconocido (es `string` en el contrato) se muestra tal cual, sin romper.
  - **`EmptyState`** con acción, e **`ErrorBoundary`** con estilo y botón "Reload view". Mantiene las props
    `what` y `children`: lo usan `App.tsx`, `SystemPreview`, `SystemPage` y `ObjectSystemPreview` (WS7).
- **Archivos:** `src/components/SyntheticBadge.tsx` (el texto "SYNTHETIC DATA · NOT SPHEREx" no cambia),
  `src/components/ErrorBoundary.tsx`, `src/api/jobs.ts` + test (**solo agregar** `stageLabel`/`jobSteps`).
- **Nuevos, planos en `src/components/` (§4.10, no `components/ui/`):** `Skeleton.tsx`, `JobProgress.tsx`,
  `EmptyState.tsx`, `Tabs.tsx` (`role="tablist"`, flechas, Home/End, `aria-controls`) y `SourceBadge.tsx`
  (`kind: 'spherex' | 'catalog' | 'gaia' | 'model' | 'synthetic' | 'injected'`). Tests con
  `renderToStaticMarkup` (como #116), `src/styles/kit.css` y `frontend/ai-usage/fe-9.json`. `SourceBadge` usa las
  clases `.u-badge u-badge--<kind>` de FE-1 (más `.badge` como respaldo mientras FE-1 no esté en `main`), y para
  `synthetic` delega en `SyntheticBadge`. Así hay **una sola** familia de insignias y un solo texto de SYNTHETIC.
  `SyntheticBadge` lo importa `SystemsPage` (WS7): si `SyntheticBadge` importara de una subcarpeta, fallaría el
  test de WS7.
- **Depende de:** nada. **Conviene que entre temprano**, porque FE-2, FE-5, FE-6 y FE-8 lo adoptan.
- **Aceptación:**
  - Tests de las cinco primitivas en verde, y `three/colorModes.test.ts` (WS7) sigue en verde.
  - `JobProgress` renderiza los seis estados de `PublicJobStatus` (`queued`, `running`, `ready`, `failed`,
    `no_coverage`, `pipeline_not_ready`), distingue `stage: build` de `stage: publish` y no rompe con un `stage`
    desconocido.
  - Con `prefers-reduced-motion` no hay brillo animado.
  - `Tabs` se usa entero con teclado.
- **Horas:** 1,5 · **Dueño:** **libre** · **Rama:** `ws5/fe-9-ui-states` · **Prioridad:** A.

### FE-10 · Móvil: hoja inferior y pasada táctil
- **Objetivo:** usar la app con el pulgar.
- **Resultado visible:**
  - En ≤ 900 px, el mapa ocupa la pantalla y el dock es una **hoja inferior**: peek con nombre y pestañas, después
    mitad y completa. Se arrastra o se toca para cambiar de altura; Esc o el botón × la cierran. **Sin tocar el
    historial** (`pushState` para "atrás"): `SkyExplorer` ya usa `history.replaceState` para el link compartido y
    el router es por hash, así que se pisarían. La hoja tapa el mapa, pero **no lo oculta ni lo desmonta** (§4.8).
  - Buscador y chips arriba. Botones de al menos 44 px.
- **Archivos:** ninguno existente.
- **Nuevos:** `src/components/BottomSheet.tsx`, `src/components/useMediaQuery.ts`, `src/styles/sheet.css` y
  `frontend/ai-usage/fe-10.json`.
- **Interfaz:** `<BottomSheet label snap onSnapChange>{children}</BottomSheet>` y `useMediaQuery(query)`. La
  integración (una línea en `ExplorerDock`) la hace FE-2 cuando FE-10 entra.
- **Pasada táctil:** recorrer home, ficha y 3D a 375×812 y 360×640 y dejar los bugs **en el issue, con dueño**
  (sin editar archivos ajenos). Verificar también que el iframe de Aladin no atrape el scroll (sin verificar en
  dispositivo hasta hoy).
- **Depende de:** FE-2 para integrarse; el componente se puede hacer ya.
- **Aceptación (375×812), medida después del PR de adopción de FE-2** (antes solo se prueba el componente):
  - El mapa se ve al cargar desde y ≤ 56. Hoy empieza en y = 856.
  - Sin scroll horizontal y sin scroll de página en la home.
  - El peek ocupa ≤ 30 % del alto.
  - Un tap en el mapa selecciona y la hoja muestra el nombre.
  - Abrir y cerrar la hoja tres veces no deja el mapa negro ni lo recarga (no aparece de nuevo "Loading Aladin sky
    map…").
  - Tests de `BottomSheet` (estados peek, mitad y completa; Esc) con `renderToStaticMarkup`.
  - (El criterio "ficha de campo: reproductor primero" pasó a FE-6, que es dueño de ese CSS.)
- **Horas:** 2 · **Dueño:** **libre** · **Rama:** `ws5/fe-10-mobile-sheet` · **Prioridad:** B (sin FE-10, FE-2
  deja la versión apilada mínima).

### FE-11 · Accesibilidad y atajos
- **Objetivo:** que se pueda recorrer la demo con teclado y lector de pantalla.
- **Resultado visible:**
  - Atajos: `/` (buscar; lo implementa FE-3), `Esc` (cerrar popup, hoja o teatro; cada dueño lo implementa en lo
    suyo), `1`–`4` (pestañas del dock), `Space` (play/pause, ya existe y es local al reproductor, no global) y `?`
    (ayuda). FE-11 aporta `useShortcut` para `1`–`4` y `?`, ignora teclas con foco en inputs, y documenta los
    demás sin duplicarlos.
  - **Orden de Esc:** cierra primero lo de más arriba (popup > teatro > hoja). Quien lo consume llama a
    `preventDefault()` y los demás miran `event.defaultPrevented`: así un Esc no cierra dos cosas a la vez.
  - Diálogo de ayuda de atajos.
- **Archivos:** ninguno existente.
- **Nuevos:** `src/components/useShortcuts.ts` + test, `src/components/ShortcutsHelp.tsx`,
  `src/styles/shortcuts.css` y `frontend/ai-usage/fe-11.json`. FE-1b los monta en la topbar.
- **Auditoría:** Lighthouse (Chrome DevTools, sin dependencias nuevas) en `#/`, `#/field/barnards-star` y
  `#/system/<id>`, más un recorrido solo con teclado. Los hallazgos van **como comentarios en el PR de cada
  paquete**, que los corrige su dueño.
- **Depende de:** FE-2 para auditar el layout final.
- **Aceptación:**
  - Lighthouse Accessibility ≥ 90 en las tres rutas.
  - Recorrido escrito y probado solo con teclado: Tab → `/` → "Barnard" → Enter → Time → Space reproduce → `3` →
    Spectrum.
  - Foco visible (`--focus-ring`) en todo control.
  - El popup del mapa tiene equivalente por click y teclado.
- **Horas:** 1,5 · **Dueño:** **libre** · **Rama:** `ws5/fe-11-a11y` · **Prioridad:** C (los atajos `/` y Esc,
  B).

### FE-12 · 3D (WS7)
- **Objetivo:** mismo lenguaje visual que el resto y un 3D que entre en el dock.
- **Resultado visible:**
  - **SystemPage** sin scroll a 1366×650: visor y panel lado a lado.
  - **SystemsPage** con tarjetas en el mismo estilo (chips e insignias).
  - **`ObjectSystemPreview compact`** para la pestaña 3D: visor de ≤ 320 px de alto, BodyPanel reducido a los
    datos clave y "Open full 3D view →".
  - **`SystemViewer compact`** también: para los cinco blancos, la pestaña 3D renderiza `SystemPreview` (WS5) →
    `SystemViewer` (WS7), no `ObjectSystemPreview`. Hoy `.scene-stage` mide `min(70vh, 620px)` y no entra en el
    dock. FE-2 le pasa `compact` desde `SystemPreview.tsx`.
  - `ObjectSystemPreview` pasa a `getObjectContextCached` de FE-5 (cuando esté) para no repetir el pedido a
    `/api/object` que ya hizo la ficha.
  - **"3D MODEL · NOT AN IMAGE"**, `representation_note` y los flags `Fact.verified` siempre visibles sin scroll.
- **Archivos:** `src/three/*` (incluidos `ObjectSystemPreview.tsx` y `three/ai-usage.json`),
  `src/components/SystemViewer.tsx`, `src/components/BodyPanel.tsx`, `src/pages/SystemsPage.tsx`,
  `src/pages/SystemPage.tsx`.
- **Nuevos:** `src/three/system.css`, que reemplaza los estilos inline y usa los tokens de FE-1 con fallback. Las
  reglas de la sección 3D de `styles.css` (líneas 223-303) se pasan ahí **con clases nuevas `.s3d-`** en el JSX,
  no con los mismos nombres. Si se copian con el mismo nombre, mientras FE-1 no invierta el orden de carga la
  regla vieja de `styles.css` gana los empates y el cambio de estilo "no hace nada". Las reglas viejas las borra
  FE-1b, porque una rama `ws7/` no puede tocar `styles.css`. Los `import './system.css'` no afectan el test
  "main-chunk safety" (saltea `.css`).
- **Depende de:** nada (la rama es `ws7/`, así que no choca con nadie). FE-2 adopta `compact` después.
- **Aceptación:**
  - Los `style={{` en `SystemViewer.tsx` (12), `BodyPanel.tsx` (6), `SystemsPage.tsx` (0) y `SystemPage.tsx` (22)
    bajan de 40 a ≤ 5, solo valores dinámicos. `DatasetTimeline.tsx` (50) y `SkyTrackPanel.tsx` (43) quedan
    fuera de este paquete. Si no llega, ≤ 10 también vale: lo que importa es que se vea igual que el resto.
  - `SystemPage` sin scroll a 1366×650.
  - En la pestaña 3D del dock (contenedor de 420×480 px), visor, etiqueta y nota se ven sin scroll.
  - three.js sigue en un chunk aparte (`npm run build`).
- **Horas:** 2–3 · **Dueño:** **DankoLiv** · **Rama:** `ws7/fe-12-3d-polish` · **Prioridad:** B.

### Matriz de archivos (para chequear que nadie se pisa)

| Archivo existente | Paquete |
|---|---|
| `index.html`, `src/main.tsx`, `src/App.tsx`, `src/styles.css` | FE-1 |
| `src/pages/HomePage.tsx`, `components/SkyExplorer.tsx`, `PositionResults.tsx`, `SystemPreview.tsx` | FE-2 |
| `components/SkySearch.tsx`, `api/skySearch.ts` (+test), `api/showcase.ts` | FE-3 |
| `public/sky-map.html`, `components/ExplorerMap.tsx`, `api/gaiaLayer.ts` (+test), `api/skyFootprint.ts` | FE-4 |
| `components/ObjectCard.tsx`, `api/objectCard.ts` (+test) | FE-5 |
| `pages/FieldPage.tsx`, `components/FieldComparisons.tsx`, `CandidateList.tsx`, `CandidatePanel.tsx`, `SkyMap.tsx` | FE-6 |
| `components/BlinkViewer.tsx` (+test), `blinkModes.ts` (+test), `framePrediction.ts` (+test) | FE-7 |
| `components/LightCurvePanel.tsx`, `PositionSpectrum.tsx`, `SpectrumChart.tsx`, `useScienceRequest.ts`, `api/lightcurve.ts` (+test), `api/science.ts` (+test) | FE-8 |
| `components/SyntheticBadge.tsx`, `ErrorBoundary.tsx`, `api/jobs.ts` (+test) | FE-9 |
| `src/three/*`, `components/SystemViewer.tsx`, `BodyPanel.tsx`, `pages/SystemsPage.tsx`, `SystemPage.tsx` | FE-12 (WS7) |
| `api/types.ts`, `api/client.ts` (+test), `api/format.ts` (+test), `pages/AboutPage.tsx`, `frontend/ai-usage.json`, `package*.json`, `vite.config.ts`, `frontend/README.md` | **nadie** (congelados) |

FE-10 y FE-11 solo crean archivos nuevos.

---

## 6. Contratos entre paquetes

### 6.1 Componentes (todas las props nuevas son opcionales)

| Lo da | Lo usa | Interfaz |
|---|---|---|
| FE-3 | FE-2 | `<SkySearch sequences onSelectSequence onLocate />` (igual que hoy) · `<TargetChips sequences activeName? onPick(target, sequence?) />` |
| FE-4 | FE-2 | `<ExplorerMap center footprintFieldId? sequences? layout?="panel" \| "fill" onSelect(p: SkyCoord & { sourceId?: string; label?: string; insideFieldId?: string; origin: 'map' }) onView?(v) />` |
| FE-5 | FE-2, FE-4, FE-6, FE-12 | `<ObjectCard lookup variant?="dock" \| "full" />` · `<ObjectSummary data />` · `peekObjectContext(lookup)` · `getObjectContextCached(lookup, signal)` (single-flight) |
| FE-6 | FE-2 | `<SequencePlayer fieldId compact? />` (incluye Expand/teatro) |
| FE-7 | FE-6 | `<BlinkViewer ... compact? />` |
| FE-8 | FE-2, FE-6 | `<LightCurvePanel targetId variant?="inline" \| "panel" />` · `<PositionSpectrum position fieldId? inline? quickLook? compact? />` · `<SciencePlot />` |
| FE-9 | todos | `<Skeleton lines? height? />` · `<JobProgress job />` · `<EmptyState title hint? action? />` · `<Tabs items value onChange idBase />` · `<SourceBadge kind />` |
| FE-10 | FE-2 | `<BottomSheet label snap onSnapChange>` · `useMediaQuery(query)` |
| FE-11 | FE-1b, FE-2, FE-3 | `useShortcut(key, handler, { when? })` · `<ShortcutsHelp />` |
| FE-12 | FE-2 | `<ObjectSystemPreview position lookup compact? />` · `<SystemViewer ... compact? />` (vía `SystemPreview`) |

### 6.2 Protocolo del mapa (FE-4; amplía el de hoy, no lo reemplaza)

Iframe → padre (`source: 'errante-sky'`, validado como hoy por `origin` y `source`):

| `type` | Campos | Cuándo |
|---|---|---|
| `hover` | `layer: 'gaia' \| 'targets', id, ra, dec, x, y` | `objectHovered`: solo el primer objeto nuevo que no sea footprint (`!k.isFootprint()`); `x, y` son px del iframe y el padre les suma el `getBoundingClientRect()` del iframe |
| `hover-end` | `id` | `objectHoveredStop`, `mouseleave` de `#map` |
| `cursor` | `ra \| null, dec \| null, x, y` | `mouseMove`, a lo sumo uno por `requestAnimationFrame` y solo sin objeto debajo (el iframe lleva la cuenta con `hover`/`hover-end`). Con `ra: null` o `mouseleave`, se oculta |
| `select` | `ra, dec, sourceId?, layer?` | `objectClicked` (posición de la estrella; un solo mensaje, sin footprints) y el `click` de #114 (posición del cursor). El padre descarta el `select` sin `sourceId` que llega **justo después** (≤ 300 ms) de uno con `sourceId` |
| `view` | `ra, dec, fov` | `positionChanged`/`zoomChanged` (Aladin ya los limita), con debounce de 500 ms en el iframe. También cierra el popup fijado (FE-4a) y dispara la consulta Gaia (FE-4b) |

Padre → iframe (`source: 'errante-ui'`): los mensajes de hoy (`position`, `zoom-footprint`, `plane`, `allwise`,
`footprint`, `gaia`) siguen igual. Cambia que cada marcador `gaia` lleva su `id` en `data` (los datos completos se
quedan en el padre, que los busca por `id`). Se agrega `targets` (`markers: [{ id, ra, dec, label }]`, con `label`
validado como string corto, igual que hoy se valida `sourceId`). El texto del popup **nunca** pasa por
`innerHTML`: lo dibuja React. No se usa el popup nativo de Aladin (`showPopup`), que arma HTML con `innerHTML`.
Todo mensaje nuevo se valida como hoy (`event.source`, `origin` y `source`), y en el padre con un validador por
`type` (como `validPosition`).

---

## 7. Ramas, orden de merge y freeze

### 7.1 Ramas y PRs
- Ramas: `ws5/fe-1-shell-tokens`, `ws5/fe-2-explorer-layout`, `ws5/fe-3-search-chips`, `ws5/fe-4a0-map-fill`,
  `ws5/fe-4-map-hover`,
  `ws5/fe-4b-gaia-view`, `ws5/fe-5-object-card`, `ws5/fe-6-field-dashboard`, `ws5/fe-7-player`,
  `ws5/fe-8-science-panels`, `ws5/fe-9-ui-states`, `ws5/fe-10-mobile-sheet`, `ws5/fe-11-a11y`,
  `ws5/fe-1b-css-cleanup` y **`ws7/fe-12-3d-polish`**.
- PR con título en inglés: `ws5: FE-4 map hover card and cursor readout` (`ws7:` para FE-12). Commits
  `wsN: ...` con el trailer `Co-Authored-By:` si hubo IA. En el cuerpo: el paquete, la lista de archivos, las
  mediciones de aceptación (números y capturas a 1366×650 y 375×812) y los modos probados (live y estático).
- Un agente = un worktree: `git worktree add -b ws5/fe-5-object-card ../hn-fe-5 origin/main` y, adentro,
  `python scripts/dev.py setup`. Con backend local, un `API_PORT` distinto por agente.
- **Actualizar con `git pull origin main` (merge)** antes de abrir el PR y antes de cada merge. **No rebase de
  ramas ya pusheadas** (requiere `push --force`, prohibido por COLLABORATION §3). Rebase solo si la rama nunca
  se pusheó.
- Si hay conflicto al actualizar, lo resuelve el autor del PR que llegó segundo, en su rama.
- `python scripts/dev.py check` en verde (incluye la guardia `owners`) y **mirar la página en el navegador**
  antes de cada push.

### 7.2 Orden de merge (por dependencias, no por importancia)

```
FE-0 (#114 → #111 → #116)        lo antes posible (objetivo 17:15)
  ├─ FE-4a.0 mapa "fill" (45 min) ┐
  └─ FE-1 tokens/shell ───────────┤
FE-9 primitivas  ─┐               │
FE-5 ficha  ──────┤ independientes, entran apenas estén
FE-8 curva abierta┤
FE-12 3D (ws7) ───┘               │
FE-3 buscador/chips (tras FE-0)   │
FE-4a popup (tras FE-4a.0) ───────┤
FE-4b Gaia por vista (tras 4a)    │
FE-7 reproductor (tras FE-0) ─────┤
FE-6 dashboard (tras FE-0; imagen grande tras FE-7)
                                  └─ FE-2 layout, etapa 1 (tras FE-0 + FE-4a.0 + FE-1)
                                       └─ PRs chicos de adopción: TargetChips, SequencePlayer + compact (etapa 2),
                                          Tabs/JobProgress, ObjectSystemPreview/SystemViewer compact, BottomSheet
FE-10, FE-11, FE-1b, SciencePlot  al final (prioridad B/C)
```

FE-2 puede mergearse antes que FE-3, FE-5, FE-6 y FE-8 usando los componentes actuales. Las adopciones son
PRs de pocas líneas del dueño de FE-2. FE-4a.0 y FE-2 se desarrollan en paralelo: FE-2 programa contra
`layout="fill"` y, mientras no esté en `main`, mide la etapa 1 en un worktree temporal con las dos ramas
mergeadas, sin commitear ese merge en su rama.

### 7.3 Merges y deploys (reloj vigente de #100: sin freeze a las 17:00, último deploy ~22:30, cierre 23:59)

Se mergea **de forma continua**: check en verde, una revisión de otra persona y la página mirada en el navegador.
Se deploya en ventanas anunciadas en #100 (deploya coordinación), con smoke test (§8.3) en la URL pública.

| Hora (ART) | Qué pasa |
|---|---|
| ~17:15 | FE-0 en `main`. El plan está publicado y la gente se anota en el issue |
| ~18:30 · deploy D1 | Lo que esté: FE-4a.0, FE-1, FE-9, FE-5, FE-8 (curva abierta), FE-3 |
| ~20:00 · deploy D2 | FE-2 (etapa 1), FE-4a, FE-12 si llega |
| ~21:30 · deploy D3 | FE-4b, FE-7, adopciones de FE-2 (etapa 2) y FE-6 si llega |
| **~22:30 · último deploy** | Solo arreglos de lo ya mergeado. Después de esto, solo reverts |
| 22:30–23:59 | WS6 graba el video y saca capturas **contra la versión ya deployada**, y se hace la entrega. Si el video se grabó antes con la UI vieja, rpccp decide si lo regraba |
| después de 23:59 | No se toca el deploy público durante la evaluación sin acuerdo del equipo. Lo pendiente (FE-10, FE-11, FE-1b, SciencePlot) espera en sus ramas |

**Si el equipo vuelve al freeze de las 17:00** (`docs/COLLABORATION.md` §5 todavía lo dice), vale la variante
conservadora: todo queda en ramas y se mergea solo con el OK en el issue, en ventanas a las 18:30 y 19:30, con
corte a las 20:00.

Cada deploy es "todo o nada" por paquete. Si un paquete rompe el smoke test, se revierte con `git revert` en una
rama `chore/revert-...` y no se arregla en caliente.

---

## 8. Cómo medir y verificar

### 8.1 Tamaños de referencia
- Laptop: viewport de **1366×650** (DevTools → Device toolbar → Responsive 1366×650, o `resize_window` en el
  panel del navegador).
- Teléfono: **375×812** y **360×640**.
- Escritorio grande: 1920×1080.

### 8.2 Snippets para la consola

```js
// Scroll de página: los dos valores tienen que ser <= 1
(() => { const s = document.scrollingElement; return { y: s.scrollHeight - innerHeight, x: s.scrollWidth - innerWidth }; })()
// Posición y tamaño del mapa
(() => { const b = document.querySelector('iframe[title="Interactive SPHEREx sky map"]').getBoundingClientRect(); return { top: b.top, w: b.width, h: b.height }; })()
```

- Pedidos: en Network, filtrar `/api/object` (0 al pasar el mouse) y `.png` (0 al volver a la pestaña Time).
- Bundle: comparar la salida de `npm run build` antes y después (≤ +15 kB gzip por paquete en el chunk principal).
- Accesibilidad: Lighthouse → Accessibility; contraste en el inspector de DevTools.

### 8.3 Smoke test de cada ventana (live y estático)
1. La home carga y el mapa **no queda negro**: plano de 4,6 µm (#86).
2. Los cinco chips (o el selector actual) abren su secuencia y **la reproducen**.
3. RW Aur o R Dra muestran la curva de luz. Barnard's Star muestra la predicción de catálogo.
4. Hover sobre un marcador Gaia → popup con "not SPHEREx" (cuando entre FE-4a).
5. Click en cielo vacío → panel con coordenadas, sin scroll ni salto.
6. La pestaña 3D muestra "3D MODEL · NOT AN IMAGE".
7. `?mode=static&dataset=real` sigue andando, y en `?mode=static` (sintético) la home muestra "SYNTHETIC DATA ·
   NOT SPHEREx" sin interacción.
8. Teléfono (375×812): el mapa se ve sin scrollear.
9. Cambiar el tamaño de la ventana (1366 → 900 → 1366) no deja el mapa negro ni lo recarga.
10. Chip o búsqueda no crean jobs (Network: 0 `POST /api/jobs`) mientras D-1 siga con el valor por defecto.
11. Los créditos "NASA/SPHEREx · Caltech/IPAC" y "Static coadd · not a video" se ven sobre el mapa sin abrir nada.

---

## 9. Riesgos y decisiones abiertas

| # | Tema | Propuesta por defecto | Quién decide |
|---|---|---|---|
| D-1 | ¿Buscar o elegir un chip también lanza el build, como el click? | **No, por ahora** (cambiado en la revisión). Si hay una secuencia guardada a < 3″, se abre esa. Si no, el dock muestra **Build SPHEREx sequence** bien visible, a un click. El click en el mapa sigue construyendo, como hoy. Motivo: **no hay endpoint para cancelar jobs** (`routes/jobs.py` solo tiene `POST /jobs` y `GET`); "abortar" solo deja de mirar, y el propio texto de la UI lo dice ("The server may continue the build"). `reuse_until` (15 min) solo reutiliza jobs ya terminados. Con un popup que invita a explorar estrellas, construir en cada búsqueda multiplica la carga justo durante la evaluación | equipo (WS4/rpccp por la carga del server) |
| D-2 | Hover en táctil | Tap = seleccionar (Aladin usa 15 px de tolerancia en `touchend`); los datos van a la hoja inferior. Sin popup en táctil | FE-4 + FE-10 |
| D-3 | Texto de bienvenida que reemplaza al hero | Reusar el h1 actual y una línea de ayuda. WS6 revisa | rpccp (WS6) |
| D-4 | ¿Capa Gaia encendida por defecto? | Hoy arranca apagada (`showGaia = false`) y solo existe con una secuencia abierta. Propuesta: encenderla por defecto con una secuencia abierta (FE-4a) y, con FE-4b, en cualquier vista con FoV ≤ 1°. Sin esto, el popup "de la estrella" casi no aparece en la demo. Costo: una consulta a VizieR CfA por vista (0,4–3,9 s medidos) | faricool54 (FE-4) + mateoa007 (autor de #111) |
| D-5 | ¿El mapa se recentra al hacer click? | Hoy sí (`locate` → `center` → `gotoRaDec`). Propuesta: no recentrar cuando el click viene del mapa; sí con chip, búsqueda y URL | mateoa007 (FE-2) |
| R-1 | Rendimiento de Aladin con 500 fuentes y etiquetas | Sin etiquetas fijas para Gaia (solo `hoverColor`). Limitar a 500 y medir FPS al arrastrar | FE-4 |
| R-2 | VizieR CfA lento o caído (como ESA Gaia hoy) | El popup de blancos y cielo vacío no depende de Gaia. Si Gaia falla: "Gaia DR3 unavailable", sin datos inventados | FE-4 |
| R-3 | `FieldPage` embebida y página propia a la vez | `SequencePlayer` (FE-6) separa las dos. Hasta entonces, FE-6 no rompe `embedded` | FE-6 + FE-2 |
| R-4 | Poco tiempo antes del corte | Prioridad A primero. Ningún paquete grande entra después del deploy D3 (~21:30); después de las 22:30, solo reverts | todos |
| R-5 | Video y capturas desactualizados | Grabar después del último deploy (~22:30) o congelar la UI del video | rpccp (WS6) |
| R-6 | CI de WS7 rota por una subcarpeta nueva | `three/colorModes.test.ts` no resuelve imports a `components/<subcarpeta>/`. Componentes planos (§4.10) | todos |
| R-7 | Docs de coordinación con el reloj viejo | `AGENTS.md`, `COLLABORATION.md` §5 y `PARALLEL_PLAN.md` dicen freeze 17:00 / envío 21:00, y #100 dice lo contrario. Alinearlos en el PR `chore:` del plan | faricool54 (coordinación) |
| R-8 | Registros de IA sin enlazar al enviar | Los `frontend/ai-usage/fe-*.json` se agregan a `docs/submission/ai-usage.json` y `AI_USAGE.md` **antes** de las 23:59 | faricool54 (coordinación) |
| R-9 | Sobrecarga de mateoa007 y de faricool54+Claude | mateoa007: FE-0 + FE-2 ≈ 5 h. faricool54+Claude: FE-4a.0 + FE-4a + FE-5 + FE-4b ≈ 5,75 h, más coordinación y deploys. FE-7, FE-6, FE-8, FE-1, FE-3 y FE-9 necesitan otras manos (¿V0id47, que cerró WS2? A confirmar) o quedan para después | coordinación |

---

## 10. Tabla para el issue de anotación

Copiar en un issue nuevo, **"FE: plan de frontend, anotarse acá"**. Para tomar un paquete, comentá
`tomo FE-N · rama ws5/fe-N-...` y asignate el issue o editá la fila. Avisá cuando abras el PR y cuando lo
liberes.

| Paquete | Prioridad | Horas | Depende de | Dueño | Rama | Estado |
|---|---|---|---|---|---|---|
| FE-0 · Merge #114 → #111 → #116 | A (objetivo 17:15) | 0,5–1 | — | mateoa007 (revisa faricool54) | (las de los PRs) | pendiente |
| FE-4a.0 · Mapa `layout="fill"` + Layers flotante + créditos | A (primero) | 0,75 | FE-0 | faricool54 + Claude | `ws5/fe-4a0-map-fill` | propuesto |
| FE-1 · Shell, tokens y navegación | A | 1,5 | FE-0 | libre (¿V0id47?) | `ws5/fe-1-shell-tokens` | libre |
| FE-2 · Home a pantalla completa (mapa + dock) | A | 4 | FE-0, FE-4a.0, FE-1 (etapa 2: FE-6, FE-7) | mateoa007 | `ws5/fe-2-explorer-layout` | propuesto |
| FE-3 · Buscador y chips de los 5 blancos | A | 1,5 | FE-0 | libre | `ws5/fe-3-search-chips` | libre |
| FE-4a · Popup junto al mouse + cursor + click preciso | A | 2 | FE-4a.0 | faricool54 + Claude | `ws5/fe-4-map-hover` | propuesto |
| FE-4b · Gaia por vista en todo el cielo | A− | 1,5 | FE-4a, D-4 | faricool54 + Claude | `ws5/fe-4b-gaia-view` | propuesto |
| FE-5 · Ficha del objeto compacta + caché | A | 1,5 | — | faricool54 + Claude | `ws5/fe-5-object-card` | propuesto |
| FE-6 · Ficha de campo como dashboard | B | 2,5 | FE-0 (imagen grande: FE-7) | libre | `ws5/fe-6-field-dashboard` | libre |
| FE-7 · Reproductor compacto | B+ | 2 | FE-0 | libre (¿V0id47?) | `ws5/fe-7-player` | libre |
| FE-8 · Curva de luz abierta (A) y `SciencePlot` (C) | A/C | 1 + 1,5 | — | faricool54 + Claude si llegan; si no, libre | `ws5/fe-8-science-panels` | propuesto |
| FE-9 · Estados de carga/vacío/error + primitivas | A | 1,5 | — | libre | `ws5/fe-9-ui-states` | libre |
| FE-10 · Móvil: hoja inferior | B | 2 | FE-2 (integración) | libre | `ws5/fe-10-mobile-sheet` | libre |
| FE-11 · Accesibilidad y atajos | C (`1`–`4` y `?`: B) | 1,5 | FE-2 (auditoría) | libre | `ws5/fe-11-a11y` | libre |
| FE-12 · 3D: estilo y modo compacto (WS7) | B | 2–3 | — | DankoLiv | `ws7/fe-12-3d-polish` | propuesto |
| FE-1b · Limpieza de CSS + montar atajos | C | 0,5 | todo lo anterior | dueño de FE-1 | `ws5/fe-1b-css-cleanup` | libre |

Suma: ~27 h. Bloque A (FE-0, 4a.0, 1, 2, 3, 4a, 5, curva de FE-8 y 9): ~14 h. Con 4 personas y ~5 h útiles
hasta las 22:30, entra A, FE-4b y parte de B.

Checklist del PR (pegar en el cuerpo):
- [ ] Solo toqué los archivos de mi paquete (`git diff --name-only origin/main...HEAD`)
- [ ] CSS en `src/styles/<paquete>.css` con mi prefijo; no edité `styles.css` (salvo FE-1)
- [ ] `frontend/ai-usage/fe-<n>.json` actualizado; no toqué `frontend/ai-usage.json`
- [ ] `python scripts/dev.py check` en verde y página revisada en el navegador (live y estático)
- [ ] Mediciones de aceptación pegadas (1366×650 y 375×812)
- [ ] Insignias de procedencia visibles (SPHEREx / Catalog / Gaia / 3D MODEL / SYNTHETIC), con texto y no solo color
- [ ] Componentes nuevos planos en `src/components/` (sin subcarpetas) y exports compartidos solo ampliados
- [ ] El iframe del mapa no se desmonta ni se oculta; probé que no queda negro
- [ ] Probado en live, `?mode=static&dataset=real` y `?mode=static` (SYNTHETIC visible)
- [ ] Una revisión de otra persona; merge continuo, deploy solo en las ventanas que anuncia #100 (último ~22:30)

---

## 11. Revisión crítica (15/11, 16:50 ART)

Revisé el plan contra `collisions.md`, el código de `main` (`53f10fa`), los diffs de #111, #114 y #116
(`gh pr view N --json files` y `git diff origin/main...origin/<rama>`), el bundle `aladin-lite@3.8.2/dist/aladin.js`,
el backend de jobs y el issue #100. Los cambios ya están aplicados arriba. Este es el resumen.

### 11.1 Reloj
- **#100 (faricool54, 16:08 ART): "no hay freeze a las 17:00"**, último deploy ~22:30 y cierre a las 23:59. El plan
  decía freeze a las 17:00, ventanas a las 18:30 y 19:30, corte a las 20:00 y envío a las 21:00. Cambié el
  encabezado, §0, §7.3 (merge continuo y deploys D1 a D3 más el último a las ~22:30), R-4, R-5 y R-7. La variante
  con freeze quedó como alternativa. `AGENTS.md`, `COLLABORATION.md` §5 y `PARALLEL_PLAN.md` siguen con el reloj
  viejo: hay que alinearlos en el PR `chore:` del plan.

### 11.2 Archivos compartidos y secuencia con los PRs abiertos
- La matriz de archivos **es disjunta**: ningún archivo existente aparece en dos paquetes. Todo paquete que toca
  archivos de #111, #114 o #116 (FE-1, FE-2, FE-3, FE-4, FE-6 y FE-7) depende de FE-0, y ninguno toca
  `ai-usage.json`. Eso está bien.
- **Choques escondidos que encontré y corregí:**
  1. **FE-2 no podía cumplir su propio criterio de mapa sin editar `ExplorerMap.tsx` (FE-4).** La barra de capas
     está arriba del iframe y el alto de 470 px sale de `.sky-map-frame` en `styles.css`. Agregué **FE-4a.0**
     (`layout="fill"`, ~45 min, primer PR de FE-4) y la dependencia de FE-2.
  2. **`main.app-full` en FE-1 no funciona**, porque `App.tsx` no renderiza `<main>` (lo trae cada página). La regla
     pasó a FE-2 (`main.xp-app`, en `explorer.css`), y FE-1 solo pone `data-page` y oculta el footer en la home.
  3. FE-2, para "conservar el campo si el click cae dentro del contorno", habría necesitado `skyFootprint.ts`
     (FE-4). Ahora FE-4 manda `insideFieldId` en `onSelect`.
  4. FE-10 tenía un criterio sobre `FieldPage` (archivo de FE-6). Lo pasé a FE-6.
  5. FE-12 solo daba `ObjectSystemPreview compact`, pero para los cinco blancos la pestaña 3D renderiza
     `SystemPreview` → `SystemViewer`, cuyo `.scene-stage` mide `min(70vh, 620px)`. Agregué `SystemViewer compact`.
  6. **FE-9 en `components/ui/` habría roto CI.** `three/colorModes.test.ts` (WS7, "main-chunk safety") recorre
     solo `components/*.{ts,tsx}`, y `SystemsPage` importa `SyntheticBadge`. Si `SyntheticBadge` importa de
     `ui/SourceBadge`, el import no se resuelve. Los componentes pasan a ir planos (regla 4.10 y R-6). El prefijo
     `.ui-` pasó a `.kit-` para no confundirlo con `.u-`.
  7. FE-9 `SourceBadge` y FE-1 `.u-badge` eran dos familias de insignias. Ahora `SourceBadge` usa `.u-badge` y,
     para SYNTHETIC, delega en `SyntheticBadge`: un solo texto.
  8. FE-1b iba a borrar clases "sin uso" que `SystemViewer.tsx` (WS7) comparte con el reproductor
     (`.blink-controls`, `.transport-btn`, `.segmented`, `.overlay-toggle`). Quedó una advertencia en FE-1b y en
     FE-7.
  9. FE-12 iba a copiar la sección 3D con **los mismos nombres de clase**. Mientras FE-1 no invierta el orden de
     carga, la regla vieja gana los empates. Ahora usa clases `.s3d-` nuevas.
  10. Atajos duplicados: `/` (FE-3 y FE-11) y Esc (FE-4, FE-6, FE-10 y FE-11). Definí quién implementa cada uno
      y en qué orden cierra Esc.
  11. La regla 4.11 (exports compartidos, solo ampliar) lista quién importa qué: `searchSequences`,
      `useScienceRequest`, `ErrorBoundary`, `SyntheticBadge`, la API de `objectCard` que usa WS7,
      `SHOWCASE_TARGETS` y `validPosition`.
  12. La caché de FE-5 no cubría el pedido propio de `ObjectSystemPreview` (WS7) a `/api/object`. Ahora FE-12
      adopta `getObjectContextCached` (single-flight con conteo de quién espera), y el criterio de FE-5 se mide con
      la pestaña 3D cerrada.
- FE-0: el conflicto de #111 (verificado con `git merge-tree`, solo `PositionResults.tsx`) también tiene que
  conservar `import type { ObjectLookup }` y la prop `lookup` de #107.

### 11.3 ¿Se pueden medir los criterios de aceptación?
- **FE-2 era imposible tal como estaba:** pedía la imagen ≥ 360 px **y** los controles enteros sin scroll dentro
  del dock (~470 px útiles), pero los controles actuales del reproductor miden ~350 px. Lo dividí en etapa 1
  (solo FE-2) y etapa 2 (con FE-6 y FE-7).
- "0 pedidos nuevos de PNG al volver a Time" no prueba nada, porque un remontaje los sirve desde la caché HTTP.
  Lo cambié por "se conserva el fotograma y no reaparece *Loading sequence images*".
- FE-6: 650 − 48 − 44 = 558 px libres, y 460 px de imagen solo entran con el transporte de FE-7 (≤ 56 px). Agregué
  la dependencia y un umbral previo de 380 px.
- FE-4: la precisión "≤ 0,01″ en el dock" no se puede leer en un texto redondeado. Ahora se mide en el payload de
  `select` (≤ 1e-6°). Agregué casos para el click sobre el contorno y para la salida del mouse.
- Contraste calculado: `--text-2` 9,7:1, `--muted` 6,3:1 y `--line` **1,3:1**, que no sirve para controles (WCAG
  pide 3:1). Agregué `--line-control: #626d88` (3,55:1). El vidrio al 78 % dejaba `--muted` en 3,4:1 sobre una zona
  blanca del mapa; lo subí al 90 % (5,2:1).
- FE-10 se mide después del PR de adopción de FE-2, con un test del componente y una prueba de "abrir y cerrar sin
  dejar el mapa negro".

### 11.4 ¿Funciona el popup con Aladin 3.8.2 en el iframe y `postMessage`? Sí, con condiciones
Verificado leyendo `dist/aladin.js` (no en un navegador):
- Existen `objectHovered`, `objectHoveredStop`, `objectClicked`, `mouseMove`, `positionChanged` y `zoomChanged`.
  `map.on` guarda **un callback por evento**, y hoy solo se usa `click`: de ahí la regla 4.12.
- `mouseMove`, `objectHovered` y `objectHoveredStop` solo se disparan en modo PAN y sin arrastre. `mouseMove` va
  antes que `objectHovered`, y `objectHovered` se repite por cada objeto nuevo, **contorno incluido**.
- `objectClicked` se llama por cada objeto cercano, contornos incluidos, y **antes** que `click`, en el mismo
  evento. Filtrar footprints y descartar el `select` genérico siguiente funciona sin tocar la línea de #114.
- Aladin no avisa cuando el mouse sale del iframe: hay que escuchar `mouseleave` y `pointerleave`.
- En táctil, `touchend` usa 15 px de tolerancia, así que el tap selecciona la estrella (D-2).
- **Dos problemas de diseño que el plan no veía:**
  - Los marcadores Gaia de #111 **arrancan apagados y solo existen con una secuencia abierta**. Sin FE-4b o D-4, la
    home no tiene ninguna estrella con popup. Subí FE-4b a A− y agregué D-4.
  - **El click en el mapa recentra la vista** (`locate` → `center` → `gotoRaDec`), así que el popup fijado
    quedaría apuntando a otro lado. Ahora FE-2 no recentra en los clicks del propio mapa (D-5), y el popup fijado se
    cierra con `view`.

### 11.5 Estimaciones
- La suma pasó de ~25 h a **~27 h**: FE-2 de 3 a 4 h, FE-4a de 1,5 a 2 h, y se agregó FE-4a.0 (0,75 h). Con 4
  personas y ~5 h útiles hasta el último deploy, entra el bloque A (~14 h), FE-4b y algo de B. FE-10, FE-11, FE-1b
  y `SciencePlot` quedan para después.
- mateoa007 tenía FE-0, FE-2, FE-6 y FE-7 (~9 h). Le dejé FE-0 y FE-2 (~5 h).
- faricool54+Claude tenían 4a, 4b, 5 y 8 (~7 h) además de coordinar. FE-8 quedó condicional. Propuse a V0id47 para
  FE-1 y FE-7, porque según #100 cerró WS2. **Falta confirmarlo con él** (R-9).

### 11.6 Etiquetas de honestidad y el fix de #86
- **Honestidad, lo que se agregó:**
  - créditos de NASA/IPAC y "Static coadd · not a video" siempre visibles sobre el mapa, nunca solo dentro de
    "Layers";
  - SYNTHETIC visible en la home estática al quitar la grilla (FE-2 y smoke 7);
  - chips con "motion test" o "brightness test", nunca "detected";
  - popup de blancos sintéticos marcado como sintético;
  - el texto del click no promete una secuencia SPHEREx en modo estático;
  - "Position predicted for <date>" en el popup Gaia;
  - **sin Teff ni Dist de GSP-Phot en el popup**, para no contradecir la temperatura de la ficha (WS3, #117);
  - Evidence dice "análisis no ejecutado" y no "nada encontrado";
  - el color nunca es la única señal de procedencia;
  - el contorno de la secuencia deja el violeta de "modelo 3D" y pasa al color SPHEREx;
  - favicon sin marcas de la NASA;
  - nada de `innerHTML` ni del popup nativo de Aladin.
- **#86:** ningún paquete toca las líneas 28-49. Agregué la regla 4.8: el iframe **no se desmonta ni se oculta** en
  ninguna variante (hoja inferior, teatro, pestañas ni `key`), porque cada remontaje repite la carrera del plano
  90. También agregué los smoke 9 y 11 y un criterio en FE-10.

### 11.7 D-1 cambió
El plan proponía que chip y búsqueda también lanzaran builds, con "abortar al cambiar de selección" como
mitigación. **No existe un endpoint para cancelar jobs** (`backend/errante_api/routes/jobs.py`: `POST /jobs` y
`GET`; abortar en el cliente solo deja de mirar, como dice la propia UI). Además, `reuse_until` (900 s) solo
reutiliza jobs terminados. El nuevo valor por defecto es conservador: chip y búsqueda no construyen, y el click en
el mapa sigue como hoy. Se mide con 0 `POST /api/jobs` (smoke 10).

### 11.8 Lo que no verifiqué
- No volví a medir las cifras de §1 (3307 px, 2010 px, 8975 px). Las tomo del autor del plan.
- No consulté VizieR: las columnas `e_Plx`, `BP-RP` y `VarFlag`, y los valores de ejemplo de Barnard's Star,
  vienen de la auditoría y los tiene que fijar el fixture de FE-4.
- El comportamiento de Aladin lo leí en el bundle, pero no lo probé en un navegador. Tampoco probé que el padre
  reciba `pointerleave` del `<iframe>` (por eso se piden los dos listeners) ni el gesto táctil en un dispositivo.
- Falta confirmar que V0id47 está libre y que mateoa007 acepta FE-2.
