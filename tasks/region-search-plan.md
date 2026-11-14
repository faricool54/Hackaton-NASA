# Plan: búsqueda por región con filtros de tipo de objeto

**Workstream:** WS5 (frontend) + WS4 (backend proxy).
**Prioridad:** P1 (C06 parcial) · no bloquea R01–R05.
**Dependencias:** el backend debe estar corriendo (`python scripts/dev.py api`) para las búsquedas libres;
la lista curada funciona en modo estático.

---

## Resumen

Agregar a la `HomePage` una barra de búsqueda que permita al usuario:

1. Escribir el nombre de una región, objeto o coordenadas.
2. Filtrar los resultados por tipo de objeto antes de seleccionar (planetas, estrellas, cometas, etc.).
3. Al elegir un resultado, rellenar el formulario RA/Dec existente y navegar al campo.

La arquitectura tiene **tres capas**:

- **Lista curada local** (`frontend/src/data/curated-regions.ts`): los 5 targets de validación +
  regiones notables del cielo. Búsqueda fuzzy offline, instantánea.
- **Backend proxy** (`/api/resolve-name`): llama a Sesame/CfA para nombres arbitrarios y devuelve
  coordenadas + tipo de objeto. Evita CORS y agrega lógica de categorías.
- **Componente `RegionSearchBox`** en el frontend: autocomplete unificado sobre ambas fuentes,
  con chips de filtro de tipo.

---

## Sub-tarea 1 — Lista curada de regiones

**Estado:** `[ ] pendiente`

### Intent
Crear el dataset local que alimenta el autocomplete sin necesidad de red ni backend. Debe incluir los
5 targets de validación del enunciado y regiones notables del cielo cubriendo todos los tipos de objeto.

### Expected Outcomes
- Archivo `frontend/src/data/curated-regions.ts` exporta un array tipado `CuratedRegion[]`.
- Incluye al menos: Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae, R Draconis (tipos verificados
  en `docs/DATA.md` §3.0), más ~10 regiones adicionales (NEP, Orion Nebula, Pleiades, Andromeda Galaxy,
  Jupiter, Halley's Comet, etc.) que cubran todos los `ObjectType` del contrato.
- Cada entrada tiene `name`, `ra`, `dec`, `object_type` (valor de `ObjectType` de `types.ts`),
  `description` opcional y flag `is_validation_target` para los 5 del enunciado.
- No usa coordenadas inventadas: las coordenadas se anotan con su fuente (en comentario).

### Todo
1. Leer `frontend/src/api/types.ts` para confirmar los valores de `ObjectType` disponibles.
2. Crear `frontend/src/data/curated-regions.ts` con la interfaz `CuratedRegion` y el array exportado.
3. Usar las coordenadas verificadas de `docs/DATA.md` §3.0 para los 5 targets.
4. Para el resto, anotar la fuente en comentario al lado de cada entrada (ej. `// SIMBAD 2026-11-14`).
5. Cubrir al menos: `star`, `brown_dwarf`, `comet`, `asteroid`, `planet`, `tno`, `unknown`.

### Relevant Context
- Coordenadas verificadas (DATA.md §3.0): Barnard (269.4463, 4.7665), Eps Ind B (331.0964, −56.8006),
  WISE 0855 (133.760, −7.2422), RW Aur (76.9565, 30.4014), R Dra (248.1676, 66.7550).
- `ObjectType` en `frontend/src/api/types.ts` línea 10–18: `asteroid | comet | tno | dwarf_planet |
  planet | star | brown_dwarf | unknown`.
- El NEP (RA 270°, Dec +66.56°) es el campo más profundo del survey (DATA.md §4).

---

## Sub-tarea 2 — Endpoint `GET /api/resolve-name` en el backend

**Estado:** `[ ] pendiente`

### Intent
Crear el proxy que resuelve un nombre libre llamando a Sesame/CfA y devuelve coordenadas + tipo de objeto.
Esto evita CORS desde el navegador y permite cachear resultados.

### Expected Outcomes
- `GET /api/resolve-name?name=<texto>` devuelve JSON `{ ra, dec, object_type, resolved_name, source }`.
- Si Sesame no encuentra el nombre devuelve HTTP 404 con mensaje claro.
- Si Sesame no está disponible devuelve HTTP 502 (no cuelga el frontend).
- Caché en memoria simple (LRU o dict) para no llamar Sesame dos veces por el mismo nombre.
- El tipo de objeto se infiere del tipo SIMBAD cuando está disponible; si no, `"unknown"`.
- El endpoint aparece en `/docs` (FastAPI autodoc).

### Todo
1. Crear `backend/errante_api/routes/resolve.py` con el router y la lógica.
2. Agregar el router en `backend/errante_api/main.py` (seguir el patrón de `live.py`).
3. Llamar a `https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?<nombre>` con timeout de 5 s.
4. Parsear la respuesta XML de Sesame: extraer `<jpos>` (RA Dec J2000) y `<otype>` si existe.
5. Mapear el otype de SIMBAD al `ObjectType` del contrato (tabla en la implementación).
6. Agregar caché `functools.lru_cache` o dict de módulo (máximo 200 entradas).
7. Escribir test en `backend/tests/` con un mock de httpx/requests (sin red).

### Relevant Context
- Sesame/CfA verificado con CORS en `docs/DATA.md` §5: `https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?NOMBRE`.
- Patrón de router existente: `backend/errante_api/routes/live.py` — importar lógica dentro de la función,
  capturar `NotImplementedError` → 501, externos → 502.
- `backend/errante_api/main.py` registra los routers: seguir el mismo `app.include_router(...)`.
- **CORS del backend:** verificar que el middleware existente permita la llamada desde el frontend local.

---

## Sub-tarea 3 — Método `resolveName` en el cliente frontend

**Estado:** `[ ] pendiente`

### Intent
Exponer la llamada al endpoint de resolución desde el `client.ts` existente, respetando el patrón
de los otros métodos (modo estático vs. api, tipado, `ApiError`).

### Expected Outcomes
- `client.resolveName(name)` devuelve `Promise<ResolvedRegion>` en modo `api`.
- En modo `static` lanza `ApiError` con mensaje claro (igual que `searchArchive`).
- Nuevo tipo `ResolvedRegion` exportado desde `types.ts` (sin tocar el contrato de producción,
  es un tipo auxiliar de UI).
- Ningún cambio a los tipos contractuales existentes (`Field`, `Manifest`, etc.).

### Todo
1. Agregar interfaz `ResolvedRegion` en `frontend/src/api/types.ts` (sección separada al final,
   marcada como "UI-only helpers").
2. Agregar método `resolveName(name: string): Promise<ResolvedRegion>` en `createClient` de `client.ts`.
3. El método usa `${apiBase}/api/resolve-name?name=<encodeURIComponent(name)>`.
4. En modo `static` lanza `ApiError('Name resolution needs the backend', 0)`.

### Relevant Context
- Patrón existente: `searchArchive` y `knownObjectsAt` en `frontend/src/api/client.ts` líneas 95–105.
- `ApiError` ya existe en `client.ts` línea 36.
- No modificar la estructura de `Manifest`, `Field` ni ningún tipo contractual.

---

## Sub-tarea 4 — Componente `RegionSearchBox`

**Estado:** `[ ] pendiente`

### Intent
Componente React autocontenido que combina búsqueda en la lista curada y resolución via backend,
con chips de filtro por tipo de objeto. Es la pieza central de la feature.

### Expected Outcomes
- Input de texto con debounce (300 ms).
- Chips de filtro por tipo: `all | star | brown_dwarf | planet | comet | asteroid | tno | unknown`.
  El chip activo filtra tanto la lista curada como los resultados de Sesame.
- Resultados en dropdown: primero los de la lista curada (match fuzzy sobre `name`), luego los de
  Sesame si el modo es `api` y el texto tiene ≥ 3 caracteres.
- Cada resultado muestra: nombre, tipo con ícono/badge, coordenadas, y badge "Validation target" para
  los 5 del enunciado.
- Al seleccionar: llama al callback `onSelect(ra, dec, name)` y cierra el dropdown.
- Estado de carga visible mientras espera Sesame; estado de error no bloquea (cae silencioso con mensaje).
- Si el modo es `static`, solo muestra la lista curada (Sesame no disponible).
- Accesible: roles ARIA `combobox`, `listbox`, `option`; navegable con teclado (↑↓ Enter Esc).

### Todo
1. Crear `frontend/src/components/RegionSearchBox.tsx`.
2. Importar `curated-regions.ts` y el `client` de `api/client.ts`.
3. Implementar filtro fuzzy sobre la lista curada (lowercase includes, sin librería externa).
4. Implementar llamada con debounce a `client.resolveName(text)` para búsqueda libre.
5. Renderizar chips de filtro por tipo con los valores de `ObjectType`.
6. Renderizar el dropdown con secciones "Suggested" (curada) y "From SIMBAD" (Sesame).
7. Manejar los estados: idle, loading, error, no-results.
8. Props: `onSelect: (ra: number, dec: number, name: string) => void`, `disabled?: boolean`.
9. Agregar ARIA básico (no requiere librería externa).
10. Usar estilos inline o clases CSS del `styles.css` existente, sin agregar nuevas dependencias.

### Relevant Context
- `frontend/src/styles.css` tiene las clases de `.card`, `.muted`, `.error`, `.small` — reutilizar.
- No agregar librerías de UI externas (regla de proyecto): implementar autocomplete propio.
- `ObjectType` importado desde `frontend/src/api/types.ts`.
- `CuratedRegion` de Sub-tarea 1 tiene `object_type: ObjectType`.

---

## Sub-tarea 5 — Integrar `RegionSearchBox` en `HomePage`

**Estado:** `[ ] pendiente`

### Intent
Conectar el nuevo componente en la página principal, reemplazando el `TODO(WS5)` existente, y hacer
que al seleccionar una región navegue al campo o pre-rellene el formulario de RA/Dec (R03).

### Expected Outcomes
- La `HomePage` muestra la barra de búsqueda arriba del listado de campos.
- Al seleccionar un resultado, el hash cambia a `#/field/<ra>/<dec>` si el campo ya existe, o muestra
  un formulario con RA/Dec pre-rellenados para disparar la consulta al backend (R03 en modo api).
- En modo `static`, la selección redirige al primer campo curado que coincida en nombre/coordenadas,
  o muestra las coordenadas para que el usuario las use manualmente.
- El texto del `hero` se mantiene; la barra aparece debajo del párrafo existente.
- El TODO comentado en `HomePage.tsx` línea 27 se elimina.

### Todo
1. Importar `RegionSearchBox` en `frontend/src/pages/HomePage.tsx`.
2. Agregar estado `selectedCoords: { ra: number; dec: number; name: string } | null`.
3. En el callback `onSelect`: buscar el `FieldSummary` del manifest más cercano a las coordenadas
   (distancia angular simple, sin librería). Si existe y la distancia es < 0.5°, navegar a `#/field/<id>`.
   Si no, **independientemente del modo**, mostrar un panel con las coordenadas pre-rellenadas y un botón
   "Fetch from SPHEREx" que en modo `api` dispara la consulta al backend y en modo `static` muestra
   un mensaje claro "Switch to API mode to fetch live data" — el botón siempre es visible.
4. Eliminar el comentario `TODO(WS5)` en línea 27.
5. El botón "Fetch from SPHEREx" llama a `client.searchArchive(ra, dec)` como primer paso visible
   (placeholder por ahora, marcado con `// TODO(WS4): job endpoint para construcción de campo`).

### Relevant Context
- `frontend/src/pages/HomePage.tsx` línea 27: `{/* TODO(WS6): ... TODO(WS5): coordinate/name search box */}`.
- El manifest ya contiene `FieldSummary[]` con `center: SkyCoord` y `id`. Distancia angular:
  `Math.acos(sin(d1)*sin(d2) + cos(d1)*cos(d2)*cos(ra1-ra2))` (en grados).
- Hash routing ya funciona en `App.tsx`: el patrón `#/field/<id>` está implementado.
- Modo estático vs. api se conoce via `client.config.mode`.

---

## Notas de integración

- **Sin cambios al contrato:** `models.py`, `shared/schema/` y los tipos contractuales de `types.ts`
  no se tocan. `ResolvedRegion` es un tipo auxiliar de UI solamente.
- **Sin librería nueva:** el autocomplete se implementa con React puro; el fuzzy match es `includes`
  lowercase. Si el texto no matchea la lista curada, cae a Sesame.
- **Sesame caído:** la lista curada siempre funciona. Si Sesame falla, el dropdown muestra solo resultados
  locales con una nota "SIMBAD unavailable".
- **CDS degradado (DATA.md §3.0):** usar **CfA** (`vizier.cfa.harvard.edu`), no `simbad.cds.unistra.fr`.
- **Botón "Fetch from SPHEREx" siempre visible:** en modo `static` informa la limitación; en modo `api`
  dispara la búsqueda. No hay rutas condicionales que oculten la funcionalidad según el modo.
- **Sub-tarea 2 (backend) se implementa después de Sub-tarea 4:** validar primero el componente
  frontend completo con datos locales (lista curada); agregar Sesame cuando el componente ya funciona.
  El orden de ejecución es: 1 → 3 → 4 → 5 → 2.
- **Regla de ownership:** Sub-tareas 1, 3, 4, 5 → WS5 (`frontend/`). Sub-tarea 2 → WS4 (`backend/`).
  No tocar `pipeline/`, `docs/*.md` (salvo este archivo de plan) ni archivos de otros workstreams.
