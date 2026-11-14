# Arquitectura

> Detalle técnico de [`PLAN.md`](PLAN.md) §2 (propuesta a validar en el [kickoff](KICKOFF.md)). Si algo de acá
> contradice a `PLAN.md`, gana `PLAN.md`. Evidencia de cada medición: [`REVIEW-2026-11-14.md`](REVIEW-2026-11-14.md).
> Estados: ✅ verificado 2026-11-14 · 📄 según documentación · ❓ abierto / inferido.

## 1. Vista general

```
Usuario ──?ra=..&dec=..&fov=..&det=..──▶ frontend/ (WS5)  Vite + React + TS, estático
                                           caja RA/Dec + 5 objetivos · Blink / Diferencia · zoom ×8 · retícula
                                           posición predicha · metadata por frame
              ┌──────── modo static ────────┴──────────── modo api ─────────────┐
              ▼                                                                 ▼
  frontend/public/data/<dataset>/  ◀── sync-data              backend/ FastAPI (WS4), caché en disco
  (data/demo sintético o golden fields de data/products)      /api/view · /api/photometry · /api/fields/… · /data
                                                                                │
                                                    build_patch(ra, dec, fov, det, group)   (WS2, errante/build.py)
              ┌──────────────────────────────────────┬──────────────────────────┴────────────────────────┐
      WS1 search_frames                       WS1 read_patch                                  WS2 imaging
  SIA2 (VOTable) sobre colecciones       Range HTTP en S3: solo las filas del            reproject_to_grid → GridFrame
  configurables (spherex_dr1,            recorte de IMAGE, VARIANCE, ZODI                coadd 1/VAR por (temporada × det)
  spherex_qr3, *_deep opcional)          fallback: cutout IBE de IRSA                    difference(A, B) · stretch común
  fallback TAP · dedupe · group_seasons  caché en data/cache/                            PNG con alfa
              │                                      │                                             │
     IRSA SIA / TAP (sin CORS)         s3://nasa-irsa-spherex (CORS + Range)                         │
              └──────────────────────────────────────┴─────────────────────────────────────────────┘
                                                     ▼
                     Field (contrato) + PNGs, mismo layout que ProductStore:
                     · efímero  data/cache/views/fields/<id>/   ← GET /api/view (id determinista)
                     · golden   data/products/fields/<id>/      ← errante build <target> (misma función)

En el navegador, sin backend: Aladin Lite 3.8.2 (jsdelivr) + HiPS de IRSA/ESA · Gaia DR3 vía VizieR CfA ·
nombres → coordenadas con Sesame CfA.
```

Principios que siguen valiendo del esqueleto:

- **El navegador nunca toca FITS**: solo PNG + JSON del contrato. WCS, SIP y reproyección viven en Python.
- **Todos los frames de un campo van a una grilla común norte-arriba** (TAN, píxel nativo SPHEREx 6.15″): el blink
  es apilar PNGs y los overlays usan `x/y` sin WCS en el navegador.
- **Contrato primero** (`models.py` → JSON Schema → `types.ts`) + `data/demo` sintético: todos los WS avanzan
  en paralelo sin esperar al pipeline real.

## 2. Flujo de `GET /api/view` paso a paso

Parámetros y respuesta exactos: [`CONTRACT.md`](CONTRACT.md) §"Propuesta 0.3.0".

| # | Paso | Quién | Detalle | Costo medido |
|---|---|---|---|---|
| 0 | Validar | WS4 | `ra` [0,360), `dec` [-90,90], `fov_arcmin` (≤ tope), `det` 1–6, `group=season\|exposure`. Error → 400. | — |
| 1 | Caché | WS4 | Id determinista `v-<ra>-<dec>-<fov>-d<det>-<group>` (codificado para cumplir el slug `^[a-z0-9][a-z0-9-]*$`). Si existe `data/cache/views/fields/<id>/field.json`, se devuelve tal cual. | instantáneo |
| 2 | Búsqueda | WS1 `search_frames` | **SIA2 en VOTable** sobre `ERRANTE_COLLECTIONS` (hoy `spherex_dr1`, `spherex_qr3`; `*_deep` opcional con `TIME`/`MAXREC`). Fallback: TAP. Dedupe por `(obs_id, detector)`; `mjd = (t_min+t_max)/2`. Se guarda la **key S3 que devuelve la búsqueda** (`cloud_access`): nunca se arma la ruta a mano. Caché por consulta. | SIA 1–4 s ✅ · TAP 8–19 s ✅ |
| 3 | Agrupar y elegir | WS1 `group_seasons` | Temporadas = bloques separados > 20 días. Se eligen las exposiciones del detector pedido en cada temporada. En `group=exposure`, exposiciones individuales con tope. | Barnard: 358 exposiciones, ~60 por detector, 3 temporadas ✅ |
| 4 | Leer píxeles | WS1 `read_patch` | `requests` con `Range:` sobre `https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/<key>`: primero el header, parseado con `astropy.io.fits.Header.fromstring`; con el WCS se calculan las filas del recorte y se leen solo esas filas de IMAGE, VARIANCE y ZODI. ≤ 16 conexiones; caché en `data/cache/`. FLAGS (RICE_1, tiles de 1 fila) en P1. Fallback: cutout IBE (≤ 6 hilos, reintentos; 422 = sin solape). | header 57.6 KB en 0.65 s ✅ · recorte 5′ ≈ 0.4 MB en 1–1.4 s ✅ |
| 5 | Reproyectar | WS2 `reproject_to_grid` | A la grilla común norte-arriba centrada en (ra, dec) → `GridFrame(data−ZODI, variance, flags, coverage)`, solo numpy + astropy. | ❓ sin medir |
| 6 | Co-sumar | WS2 `coadd` | Media pesada 1/VAR por (temporada × detector) → frame `kind="coadd"` con `season`, `mjd_start/mjd_end`, `n_inputs`, `input_ids`, rango de λ. | ❓ |
| 7 | Restar | WS2 `difference` | A − B entre temporadas (p. ej. primera − última) → frame `kind="difference"`. Un movimiento de 1–2 px aparece como dipolo. | ❓ |
| 8 | Renderizar | WS2 | Stretch común por detector (para que el brillo sea comparable entre frames), PNG con alfa donde no hay cobertura. | ❓ |
| 9 | Escribir y responder | WS2 `build_patch` + WS4 | `Field` (contrato, con `query` y `target` si es un objetivo conocido) + PNGs en `data/cache/views/fields/<id>/`; se devuelve el `Field`. Se escribe **aunque no haya detección**. | — |

Tiempos totales estimados (❓ inferidos de lo medido): 1 detector (~60 exposiciones) ≈ 5–10 s; los 6 detectores
≈ 20–40 s desde acá, menos desde un host en US-East. Segunda llamada: instantánea por la caché.
`GET /api/photometry` reutiliza los mismos frames ya leídos (sin descargas extra) para el espectro al vuelo y la
curva de luz de las variables (P1).

## 3. Golden fields: misma función, sin backend

- `errante build <target>` llama a **la misma** `build_patch(ra, dec, fov, …)` que `/api/view` y escribe en
  `data/products/` (manifest + `fields/<id>/`). No hay un segundo pipeline que mantener.
- Los 5 objetivos oficiales (WS3 los define en `pipeline/errante/config/fields.toml`, con posición propagada a la
  época de los datos y pm/plx/época guardados en el repo) se construyen así y se commitean livianos (< ~20 MB).
- El **índice SIA de los 5 objetivos** también va al repo (WS1): con él se pueden reconstruir aunque IRSA esté
  caído, porque S3 no depende de IRSA.
- El frontend estático los sirve sin backend: deploy gratis y **plan B de la demo**.

## 4. Modo estático vs modo api

| | `static` (default) | `api` |
|---|---|---|
| Qué lee | `frontend/public/data/<dataset>/`, copiado por `sync-data` desde `data/demo` (sintético) o `data/products` (`?dataset=real`) | backend: `/api/manifest`, `/api/fields/…`, `/data/…`, y en 0.3.0 `/api/view`, `/api/photometry` |
| RA/Dec arbitrario | no: solo los golden fields (la UI tiene que decirlo) | sí |
| Deploy | cualquier host estático | frontend estático + backend Python con disco, en US-East |
| Cómo se activa | por defecto | `VITE_DATA_MODE=api` + `VITE_API_BASE=…` (hoy también `?mode=api`; pasa a `?source=api`) |

⚠️ Hoy `frontend/src/api/client.ts` usa el parámetro de URL `?mode=` para elegir static/api, y `PLAN.md` usa
`?mode=` para Blink/Diferencia. Resolución (`tasks/WS5-frontend.md`, gotchas): `mode=blink|diff` queda para el
viewer, como en `PLAN.md`, y la fuente de datos pasa a `?source=api|static`; `mode=api|static` se sigue aceptando
por compatibilidad.

❓ Falta decidir cómo sirve el backend los PNG efímeros de `data/cache/views/` (hoy `/data` solo monta el
`data_dir` de productos). Se fija en el PR de contrato 0.3.0.

## 5. Overlays y servicios en el navegador

| Qué | De dónde | Estado |
|---|---|---|
| Aladin Lite | `https://cdn.jsdelivr.net/npm/aladin-lite@3.8.2/dist/aladin.js` (nunca desde `aladin.cds.unistra.fr`) | ✅ 200 |
| HiPS de contexto | espejos IRSA (`irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color`, `.../CDS/AllWISE/RGB-W4-W2-W1`) o ESA (`skies.esac.esa.int`) | ✅ 200 con CORS |
| Cubo HiPS SPHEREx DR1 (102 canales) | `irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube/` | ✅ 200 con CORS; que Aladin lo renderice: ❓ |
| Gaia DR3 | VizieR de CfA (`vizier.cfa.harvard.edu`, `I/355/gaiadr3`) | ✅ con CORS |
| Nombre → coordenadas | Sesame de CfA | ✅ con CORS (devuelve pm) |
| Gaia en ESA TAP, CatWISE en IRSA TAP | solo vía backend | ✅ sin CORS |

## 6. Decisiones y por qué

| Decisión | Por qué (mediciones) |
|---|---|
| **Backend obligatorio** (FastAPI = proxy + procesador con caché) | IRSA (TAP, SIA, cutouts IBE) responde sin cabeceras `Access-Control-*` ✅: el navegador no puede buscar frames solo. S3 sí tiene CORS ✅, pero reimplementar WCS+SIP, RICE y reproyección en JS es demasiado riesgo. |
| **Píxeles por Range en S3**; cutout IBE solo como fallback | Recorte de 5′ por Range ≈ 0.4 MB en ~1 s ✅ contra ~4 MB en 4–15 s del cutout IBE ✅, que siempre arrastra la tabla EPSF entera (≈ 3.86 MB) ✅. IMAGE es float32 sin comprimir ✅. |
| **`requests` + `Header.fromstring`**, sin fsspec | `.venv` no tiene fsspec/s3fs/aiohttp ✅ y la receta con `anon` es de s3fs, no de https ❓. No suma dependencias. |
| **SIA2 en VOTable**, TAP de respaldo | SIA 1–4 s contra TAP 8–19 s ✅. El CSV de SIA está roto (filas con más columnas que el header) ✅. SIA ya trae key S3, polígono y tiempo ✅. SIA tiene ~1 día de retraso respecto de TAP 📄. |
| **Video por temporada × detector (coadds)** | Dentro de una temporada cada exposición mide otra λ (filtro variable): la estrella "parpadea" sin cambiar 📄. El enunciado sugiere co-sumar por detector. Además mejora S/N. |
| **Zoom pixelado, retícula, posición predicha y resta** | Movimiento real en toda la línea de base: Barnard 1.86 px, WISE 0855 1.36 px, Eps Ind B 1.10 px ✅ (cálculo con la base real de datos). Sin ayudas no se ve nada. |
| **Colecciones como configuración** (`ERRANTE_COLLECTIONS`, a crear por WS1) | Colecciones vigentes: `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep` ✅; QR2 ya no es buscable ✅ (0 filas en SIA/TAP). Las versiones de pipeline varían por semana y detector (solo en Barnard: `-228` a `-243`) ✅. |
| **λ por archivo leyendo `TDIM`** | La grilla WCS-WAVE depende del detector ✅: D1 9×9, D2 11×11, D3 9×14, D4 13×20, D5 11×11, D6 9×9. No suponer forma cuadrada. |
| **Golden fields con la misma `build_patch`** | Plan B ante IRSA/S3 lentos y deploy estático gratis, sin duplicar lógica. |
| **Frontend estático por defecto** | Deploy en cualquier host estático; el backend agrega RA/Dec arbitrario. |
| **Píxeles en convención PNG** en el contrato | Es lo que necesita la UI; la conversión FITS↔PNG vive solo en `imaging/grid.py`. |
| Python base: numpy/astropy/pydantic/pillow; scipy/photutils/reproject/astroquery como extra `science` | CI y backend livianos; el camino de `/api/view` no debería necesitar el extra. |
| Sin librerías de UI/routing en el frontend | Menos dependencias; el estado vive en la query (`?ra&dec&fov&det&…&embed=1`) para poder embeber. |

## 7. Riesgos y plan B

| Riesgo | Señal | Plan B |
|---|---|---|
| IRSA caído o lento | `/api/view` da 502/504 en la búsqueda | Índice SIA guardado en el repo + lectura directa de S3 (no depende de IRSA); golden fields estáticos. |
| S3 lento (o host lejos de us-east-1) | primera llamada > 1 min | Golden fields; caché precalentada antes de la demo; 1 detector por defecto; deploy en US-East (throughput ❓ sin medir). |
| CDS Estrasburgo caído (desde 2026-11-09 ✅) | Aladin/overlays vacíos | Espejos: CfA (SIMBAD, VizieR, Sesame), IRSA/ESA (HiPS), jsdelivr (Aladin). Nada depende de `*.cds.unistra.fr`. |
| El host corta requests largos o no tiene disco | timeouts del proxy, caché que se pierde | Elegir host con disco persistente; limitar FOV/detectores; precalentar los 5 objetivos. |
| Campos cerca de los polos eclípticos | miles de exposiciones (R Dra 2493, NEP 29 402 ✅) | Excluir `*_deep` por defecto, filtrar con `TIME`/`MAXREC`, tope de frames → 400 con sugerencia. |
| WISE 0855 poco visible | coadds de D1–D3 vacíos | Probar D5/D6 antes de elegirlo para el video (❓ inferido por magnitudes); protagonista alternativo: Barnard. |
| `build.py` hoy no escribe nada hasta que exista la detección ✅ | `errante build` falla en stubs de detección | `build_patch` hace la detección y los objetos conocidos **opcionales**. |
| Saturación (Barnard, R Dra) | bits OVERFLOW/NONLINEAR | ❓ sin revisar: mirar FLAGS (P1) y avisarlo en la UI. |

## 8. Hitos de integración (de `PLAN.md` §5, hora local UTC−3)

| Hito | Cuándo | Criterio |
|---|---|---|
| **I0** (hecho) | — | Demo sintético de punta a punta (pipeline → JSON/PNG → web). |
| Contrato + datos | Sáb 15:00 | Contrato 0.3.0 mergeado · `search_frames` real · lectura S3 de Barnard por CLI. |
| **I1 – vertical slice real** | Sáb 20:00 | `/api/view` de Barnard (1 detector, por temporada) se ve en el frontend. |
| **I2** | Dom 08:00 | Los 5 objetivos con coadds + diferencia + posición predicha; golden fields construidos. |
| **Deploy público** | Dom 12:00 | Frontend + backend probados en incógnito y en celular. |

## 9. Probarlo a mano

```bash
errante search --ra 269.44623 --dec 4.76870         # WS1: ¿qué frames hay? (Barnard, centro de fields.toml)
errante build barnards-star                          # golden field → data/products/
python scripts/dev.py web                            # y abrir http://localhost:5173/?dataset=real
python scripts/dev.py api                            # backend en :8000
curl "http://localhost:8000/api/view?ra=269.44623&dec=4.76870&fov_arcmin=8&det=1&group=season"   # cuando exista (I1)
```
