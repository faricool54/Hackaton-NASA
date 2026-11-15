# backend/ — `errante_api` (FastAPI) · WS4

```bash
python scripts/dev.py api   # = cd backend && uvicorn errante_api.main:app --reload --port 8000 (API_PORT to change it)
open http://localhost:8000/docs
```

Datos servidos: `ERRANTE_DATA_DIR` si está definido; si no, `data/products` si existe; si no, `data/demo`.
CORS: `ERRANTE_CORS_ORIGINS` (coma-separado, default `*`; restringir en producción).

Endpoints vigentes: [CONTRACT.md](../docs/CONTRACT.md). Tests: `pytest -q backend/tests`.
Asistencia de código/documentación: OpenAI Codex, metadata en [ai-usage.json](ai-usage.json). La ficha del
objeto (`/api/object`) se hizo con Claude Code (trailer `Co-Authored-By` en sus commits); falta registrarla en
el inventario de IA (coordinación): agregar claves a `ai-usage.json` rompe el espejo que exige WS2.

| Endpoint | Respuesta |
|---|---|
| `GET /api/health`, `/api/manifest`, `/api/fields/{id}[/candidates\|/known]`, `/api/systems/{id}` | productos publicados |
| `GET /api/search?ra&dec[&detector]`, `/api/known-objects?ra&dec&mjd` | archivo en vivo (WS1/WS3) |
| `GET /api/resolve-name?name=` | `ResolvedRegion` (Sesame CfA) |
| `GET /api/object?name=` o `?ra=&dec=[&epoch_mjd&radius_arcsec]` | `ObjectContextResponse`: ficha de catálogo (C05, abajo) |
| `POST /api/jobs`, `GET /api/jobs/{id}` | construcción por coordenadas |
| `POST /api/spectra`, `POST /api/fields/{id}/comparisons` | espectros y comparaciones (0.4.0) |
| `GET /api/lightcurves`, `GET /api/lightcurves/{target_id}` | offline light-curve index/product (proposed 0.6.0; WS3 review pending) |
| `GET /data/...` | PNG y análisis publicados |

## Implementado en WS4

- IDs de campos/sistemas restringidos al slug del contrato; lecturas fuera del directorio público rechazadas,
  incluso mediante symlinks. JSON corrupto/indisponible devuelve 503; `health.data_dir` conserva su tipo string
  pero devuelve `configured`, sin publicar rutas locales.
- Búsqueda/objetos conocidos: ejecución fuera del event loop, límite de concurrencia y deadline por solicitud.
  Respuestas JSON con `detail` string: 501 integración pendiente, 502 fallo/respuesta inválida del proveedor,
  504 timeout y 503 capacidad ocupada (con `Retry-After`). No se filtran URLs ni excepciones internas.
- Caché validada contra el modelo: TTL en memoria y disco, escrituras atómicas y cantidad acotada de entradas.
  Solo respuestas correctas se cachean (incluido vacío válido). La clave incluye operación, todos sus parámetros,
  fuentes configuradas, versión de pipeline y schema. Detectores repetidos se normalizan.
- CORS configurable con espacios eliminados; los tests simulan WS1/WS3, no consultan archivos en vivo.

| Variable | Default | Uso |
|---|---|---|
| `ERRANTE_DATA_DIR` | productos si hay manifest; si no demo | Árbol público; nunca apuntar a descargas/caché |
| `ERRANTE_CORS_ORIGINS` | `*` | Orígenes separados por coma; restringir al frontend en producción |
| `ERRANTE_API_CACHE_DIR` | `data/cache/api` | Caché privada, siempre fuera del árbol público |
| `ERRANTE_API_TIMEOUT_S` | `30` | Deadline de respuesta de cada llamada de archivo |
| `ERRANTE_API_MAX_CONCURRENT` | `2` | Llamadas activas por proceso |
| `ERRANTE_API_CACHE_TTL_S` | `300` | Frescura de resultados, incluso respuestas vacías |
| `ERRANTE_API_CACHE_ENTRIES` | `128` | Máximo de entradas en memoria y disco |

Un deadline de respuesta **no puede matar un hilo Python**. Su cupo queda ocupado hasta terminar: nuevos
requests reciben 503 mientras tanto. WS1/WS3 deben configurar también timeout de transporte/reintentos en sus
clientes. Una llamada que termina después del 504 puede poblar la caché con un resultado válido.
El límite es por proceso, no global entre réplicas. Empezar con un worker/réplica; ajustar antes de escalar.

## Construir los cinco campos (WS4-3)

```bash
python scripts/dev.py setup-science
python scripts/dev.py build-fields
# Una selección, otro destino o plazo por campo:
.venv/Scripts/python.exe scripts/build_fields.py --field barnards-star --timeout 900 --out data/products
```

En Unix usar `.venv/bin/python`; `make build-fields` llama al mismo runner. Construye en procesos separados,
sin `--analyze`, con timeout duro por campo. Reporta JSON y continúa tras errores: salida 0 = todos listos,
1 = uno o más fallaron, 2 = no pudo arrancar/configuración inválida.

Antes de publicar exige producto no sintético, dos temporadas separadas >30 días para al menos un detector,
PNGs válidos sobre la grilla y origen por frame. Es una comprobación mínima de integración, **no evidencia R05**
ni garantía de compatibilidad λ/fotométrica. WS3 sigue revisando señal/calidad.
Staging fuera del árbol público, manifest escrito atómicamente y rollback del campo previo si falla publicación.
Una actualización puede producir un 404/503 transitorio durante el intercambio de directorios; no sirve un
directorio parcialmente escrito. Un lock impide dos publicaciones batch en el mismo destino. Si el proceso
muere y queda `.build.lock`, confirmar que no hay otro build antes de retirarlo manualmente.
Si también falla la restauración, el reporte incluye `recovery_dir`: conserva el producto anterior allí;
no retirar ese directorio hasta recuperarlo. Un proceso muerto requiere revisión manual del staging/backup.

**WS1/WS2 integrados:** búsqueda, recortes, reproyección y selección de temporadas ya construyen los cinco
objetivos con el pipeline oficial. Un stub futuro se informa como `pipeline_not_ready`, nunca éxito.
La validación científica de señal/variabilidad sigue separada de esta validación técnica.

## Despliegue preparado; URL pública pendiente (WS4-4/6)

Desde la raíz del repo:

```bash
docker build -f backend/Dockerfile -t errante-api .
docker run --rm -p 8000:8000 errante-api
```

El contenedor instala ambos paquetes y el extra científico, corre sin root y usa `PORT` (default 8000).
Inicialmente sirve la demo sintética; eso no satisface R02/R03. Para productos reales configurar
`ERRANTE_DATA_DIR=/app/data/products`, persistir productos y caché en volúmenes separados, ambos escribibles
por UID 10001, y fijar el origen HTTPS del frontend en `ERRANTE_CORS_ORIGINS`.
El host debe permitir salida a IRSA/S3, ofrecer HTTPS y almacenamiento persistente. El usuario confirmó que
todavía no se eligió hosting: proveedor/cuenta y URL pública pendientes. No se creó un servicio externo ni
se activó facturación.

Producción sin Docker: instalar `pipeline[science]` y `backend` juntos, configurar rutas persistentes y correr
`python -m errante_api.serve`. No usar `--reload`. CI construye el contenedor y prueba health/manifest.

El workflow [pages.yml](../.github/workflows/pages.yml) publica el frontend cuando un administrador habilite
Pages con fuente GitHub Actions y la variable `ENABLE_PAGES=true`. Configurar `VITE_DATA_MODE=api` y
`VITE_API_BASE=https://<backend>` para conectarlo; por defecto publica la demo estática etiquetada. Para este
repo privado, confirmar que el plan de GitHub habilita Pages; no cambiar la visibilidad del repo para evitarlo.
Validar la URL resultante sin login, con un campo no precargado y el frontend del equipo antes de marcar R01/R03.
Solo preparar/ejecutar el workflow no demuestra el recorrido desde una URL pública.

Referencias de configuración: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
y [contexto Docker/Dockerfile específico](https://docs.docker.com/build/concepts/context/#dockerignore-files).

## Jobs por coordenadas: implementación y conexión

Contrato compartido **0.3.0** en `errante.models`, `shared/schema` y tipos TS (PR #32). Las rutas usan
esos mismos modelos: no mantienen copias locales. WS5 consume POST/GET y el resolver desde ese contrato.

Activar con `ERRANTE_ENABLE_JOBS=1`. El backend sirve y construye en **el mismo directorio**:
`ERRANTE_DATA_DIR` si se definió, o `ERRANTE_PRODUCTS_DIR` aunque todavía no haya manifest. Al activar jobs
se prepara el directorio público antes de montar `/data`. La demo sigue disponible con jobs desactivados.

- `POST /api/jobs` devuelve 202, también al reutilizar un job activo/listo compatible.
- `GET /api/jobs/{id}` devuelve estado persistido; `publishing` se representa públicamente como `running`.
- Estados terminales: `ready`, `failed`, `no_coverage`, `pipeline_not_ready`. En `ready`, abrir
  `/api/fields/{result_field_id}` y las imágenes en `/data/fields/{result_field_id}/...`.
- Parámetros inválidos: 422; cola/capacidad agotada: 429 con Retry-After; almacenamiento ocupado/indisponible:
  503; ID desconocido: 404. Los errores públicos no incluyen tracebacks ni rutas locales.
- CORS admite GET y POST. Configurar el origen completo del frontend (puerto incluido).

```json
{"ra":269.44623,"dec":4.76870,"size_deg":0.25,"detectors":[1],"max_frames":40}
```

`mjd_min`/`mjd_max` son opcionales. RA [0,360), Dec [-90,90], lado [0.01,0.5] grados, detectores 1–6 y
2–120 frames. Se conservan las coordenadas; no se redondea RA a 360. La clave de reutilización incluye
parámetros, contexto de colecciones/fuentes, revisión de procesamiento y versiones de pipeline/schema.
Las publicaciones usan IDs inmutables por intento, imágenes verificadas y un manifest atómico. Batch y jobs
comparten lock de publicación entre procesos. Un fallo del manifest no se confirma como éxito.

### Recuperación y recursos

Una sola instancia/supervisor por directorio privado, protegido por lock del SO. SQLite serializa admisión y
claims. Un shutdown que no terminó mantiene la exclusividad. Al reiniciar, se verifica la identidad de un
hijo anterior antes de detenerlo; se reconcilian publicaciones con sus huellas y se repara el manifest antes
de confirmar `ready`. No se mata un PID ajeno reutilizado. `psutil` permite controlar y verificar procesos en
Windows/Linux; es una dependencia runtime del backend.

| Variable | Default | Uso |
|---|---|---|
| `ERRANTE_JOBS_DIR` | `data/cache/jobs` | SQLite, solicitudes/resultados y logs; fuera del árbol público |
| `ERRANTE_JOB_MAX_BYTES` | 768 MiB | Presupuesto supervisado del staging de un intento, incluida su caché |
| `ERRANTE_JOBS_MAX_BYTES` | 2 GiB | Admisión: espacio utilizado por estado privado y productos públicos |

Un build activo, hasta ocho trabajos activos/en cola y 900 s de deadline por build. Los logs se drenan sin
crecer por encima de 5 MiB. Se limpia caché/productos de staging terminales; diagnóstico privado por 24 h.
Los productos públicos no se borran automáticamente: al alcanzar el presupuesto se rechaza trabajo nuevo.
Hay que mantener al menos 128 MiB libres. El muestreo de disco es aproximado; cuotas duras de memoria/CPU/disco
son responsabilidad del host/contenedor. Los resultados desaparecidos o inválidos no se reutilizan.

`no_coverage` requiere una consulta válida vacía; errores genéricos de proyección/descarga no se interpretan
como ausencia de cobertura. Una secuencia técnica correcta tampoco certifica movimiento/variabilidad R05.
Espectros y comparaciones se exponen mediante el contrato científico 0.4.0 descrito abajo.
Las fichas y el modelo físico 3D siguen las dependencias de WS3/WS7 en VISION.md.

Para verificar un PR apilado contra su base inmediata: `ERRANTE_BASE_REF=origin/<rama-base>` antes de
`python scripts/dev.py check` (PowerShell: `$env:ERRANTE_BASE_REF=...`). La guardia mantiene las mismas
reglas de dueños y CI usa la base del PR. Sin la variable sigue comparando con `origin/main`.

La selección de pool con λ emparejada de WS2 #35 usa revisión `wavelength-pool-v3` en la clave de jobs.
No se reutilizan resultados de `season-grid-v2`; los pedidos persistidos conservan su contexto original.


### Invalidación de procesamiento (15/11)

La revisión `display-mask-v4` incluye los cambios de máscara/render de WS2 #48. La clave captura también
un SHA-256 del contenido de build/settings/models/products/data/imaging/detect y versiones de las librerías de imagen.
El hash usa nombres relativos: mover un worktree no cambia el resultado. Cambiar código o dependencias
invalida resultados viejos sin tener que recordar subir una constante. Cada pedido conserva su contexto;
un pedido en cola cuyo procesamiento cambió falla y debe reenviarse, en lugar de publicar bajo otra clave.
`detect/` también participa sin `--analyze`: registro y color (#41) importan helpers de `detect/difference.py`.
Se incluyen todos sus módulos Python recursivamente, además de `products.py`; la huella compartida invalida
tanto jobs como espectros/comparaciones. Los pedidos ya persistidos mantienen su identidad original.

## Espectros y comparaciones (15/11, C02/C03)

Requieren instalar `pipeline[science]` junto al backend. Funcionan localmente; no requieren contratar hosting.
Contrato compartido **0.4.0**, PR `contract/science-api` (depende de `contract/composites` #39).

- `POST /api/spectra`: `{ "ra": 269.44623, "dec": 4.76870, "source": "dr1_cube", "aperture_px": 0 }`.
  Cubo DR1 estático, 102 planos antes de filtrar detector, brillo superficial MJy/sr, sin sustracción de cielo
  ni errores de flujo. Apertura 0–3 píxeles. No acepta filtro temporal: el cubo no tiene eje de tiempo.
  Núcleos faltantes/saturados y canales dicroicos 50/51 permanecen inválidos; no se interpolan.
- La misma ruta con `source: "l2_exposures"`, `max_frames: 24`, `detectors: [2]`, `mjd_min/max` opcionales:
  fotometría forzada WS2 en stamps nativos IMAGE − ZODI, apertura y cielo local, flujo mJy y error por
  exposición. 2–60 frames. `field_id` opcional usa las exposiciones del campo y exige posición dentro de él;
  sin campo busca por coordenadas. Retiene flujos negativos, fechas, λ, release, fuente, flags y fallos.
  Sin corrección de apertura disponible devuelve flujo de apertura sin corregir, identificado como tal.
  No propaga movimiento propio/paralaje; λ y tiempo varían juntos. No es un espectro simultáneo.
- `POST /api/fields/{id}/comparisons`: `{ "detectors": [2], "frame_ids": ["id1", "id2"] }`.
  Sin `frame_ids` selecciona los del campo para esos detectores. 2–60 frames, grilla hasta 512² píxeles,
  procedencia real obligatoria. Reconstruye medias ponderadas por temporada/detector y diferencias
  `later − scale × earlier` mediante WS2. Devuelve entradas, épocas, λ, escala/ruido y limitaciones;
  pesos individuales no exportados se indican como `null`. No ofrece suma arbitraria ni mezcla detectores.
  Los PNG y `analysis.json` se publican atómicamente en `/data/analyses/{sha256}/`, conservando el campo.

Todos los resultados llevan `synthetic: false`; un campo sintético se rechaza con 409. Sin cobertura o
sin puntos utilizables no se inventa una detección. Filtro/posición inválidos: 422; selección demasiado
grande: 413; ocupado/almacenamiento: 503; fallo remoto: 502; deadline: 504. OpenAPI incluye los modelos.

Procesamiento científico en un hijo por instancia, independiente del worker de jobs: deadline duro 140 s,
staging de 512 MiB, log de 1 MiB, watchdog del padre y terminación al apagar. Cupo ocupado hasta terminar;
pedidos idénticos comparten trabajo y dejar de esperar en el frontend no cancela a otros clientes.
Caché TTL memoria/disco en `ERRANTE_API_CACHE_DIR/science-results`, staging privado en `science-work`.
La identidad incluye parámetros, campo/época, fuentes, schema, huella del pipeline y adaptador científico.
Un PNG ausente/dañado invalida la reutilización. Admisión hasta 1 GiB de staging + análisis publicados y
512 MiB libres; los productos públicos no se eliminan automáticamente. Para liberar espacio, detener el
servicio y archivar/eliminar análisis viejos; nunca limpiar los campos originales para renovar esta caché.

## Ficha del objeto (15/11, C05)

`GET /api/object?name=Barnard%27s%20Star` o `GET /api/object?ra=331.09665&dec=-56.80066` (exactamente uno de
`name` o `ra`+`dec`; opcionales `epoch_mjd` de la posición, default MJD 61000 = era SPHEREx, y `radius_arcsec`
0–12, default 8 ≈ 1.3 píxeles SPHEREx; WS3 adopta una fuente mucho más brillante del radio porque "domina el
píxel", lo que deja de valer con radios grandes). Devuelve `ObjectContextResponse` (contrato 0.5.0): identidad
SIMBAD/Gaia DR3 con estado de match (`name`, `matched`, `ambiguous`, `loose`, `none`, `unavailable`), `facts`
(`Fact`, `unknown` si no se midió), variabilidad VSX, planetas confirmados, huéspedes cercanos que NO son el
objeto, fotometría 2MASS/AllWISE marcada `other_mission: true`, advertencias y procedencia por servicio. **Contexto de catálogo, no mediciones
SPHEREx.** La ciencia está en WS3 (`errante.science.context.object_context` + `to_response`); el backend solo la acota.

- Fuera del event loop, en un `LiveService` propio: `ERRANTE_OBJECT_MAX_CONCURRENT` (4) llamadas activas,
  single-flight por consulta, caché validada en memoria/disco (`ERRANTE_API_CACHE_DIR/object-context`, TTL
  `ERRANTE_API_CACHE_TTL_S`) más la caché cruda de WS3 (`ERRANTE_CONTEXT_CACHE_DIR`, default `data/cache/context`,
  TTL `ERRANTE_CONTEXT_CACHE_TTL_S` = 7 días). La clave incluye el hash de `science/context.py`.
- Plazos por debajo de `ERRANTE_API_TIMEOUT_S` (30 s): búsqueda completa `ERRANTE_OBJECT_DEADLINE_S` (default
  timeout − min(5 s, 20 %) = 25 s), timeout de transporte por servicio `ERRANTE_OBJECT_SERVICE_TIMEOUT_S`
  (default min(25 s, plazo/2) = 12.5 s). Al vencer el plazo la búsqueda sigue en segundo plano y la respuesta es
  **parcial**: se re-lee offline lo que ya llegó a la caché de WS3 y los servicios pendientes figuran con
  `status: "error"` y nota "no answer within the N s API deadline" (desconocido, no negativo). Un resultado
  `partial: true` nunca se sirve desde la caché de la API: el reintento recalcula y usa la caché de WS3.
- Códigos: 200 (también para un punto sin nada catalogado: `match: "none"`, nunca 404), 404 solo si SIMBAD/Sesame
  no conoce el NOMBRE, 422 parámetros inválidos, 502 resolvedor de nombres inalcanzable o fallo inesperado,
  503 cupo ocupado (`Retry-After: 2`), 504 solo si al vencer el plazo ni siquiera se había resuelto el nombre.
- Tests (`backend/tests/test_object.py`): búsqueda de WS3 simulada (validación, plazos, single-flight, caché,
  errores, parcial por plazo, cupo) y código real de WS3 re-leyendo offline las respuestas grabadas en
  `pipeline/tests/fixtures/ws3/context/` (Barnard por nombre, centro del campo eps Ind B, cielo vacío), sin red.

## Precomputed light curves (R05/C04, proposed contract 0.6.0)

This implementation depends on the **draft [contract proposal #78](https://github.com/faricool54/Hackaton-NASA/pull/78)**,
prepared at the user's request for **WS3 / faricool54**. WS3 must review units, relative-magnitude interpretation,
comparison controls, period significance and completeness before integration. These routes are available on
this branch; they are not yet part of `main`. No WS3 algorithm or threshold has been changed.

`GET /api/lightcurves` lists target IDs, method, build date, point/usable counts, readiness and partial status.
`GET /api/lightcurves/rw-aurigae` and `/api/lightcurves/r-draconis` return validated `LightCurveProduct` JSON.
Products contain all exposure measurements, dates/MJD, wavelength, flags/exclusions, relative magnitudes,
statistical errors, comparison-star measurements, target/control statistics, matched-wavelength pairs,
source FITS URLs and selection/processing provenance. Period results retain alternative peaks, bootstrap
interval, visit-permutation false-alarm probability and the native significance flag; an untested candidate
has `significant: null`. `ready` means at least one usable relative measurement, not a confirmed detection.
`no_usable_points` is an explicit successful calculation without usable relative points.

The API reads small packaged snapshots from `errante_api/curated/lightcurves/`. A file with the same target
ID in `ERRANTE_DATA_DIR/lightcurves/` overrides its packaged snapshot. An invalid override returns 503 rather
than silently serving older data. Missing products return 404; invalid path parameters return 422. Products
are validated before every conditional response, with content-based cached validation (32 entries), a
strong ETag, `If-None-Match`/304 and `Cache-Control: public, max-age=60, must-revalidate`. Each read is capped
at 8 MiB and the index at 32 targets. GET performs no archive access or scientific computation.

### Reproduce or refresh offline

Install the local `pipeline[science]` extra and backend, then run from the repository root:

```bash
python -m errante_api.lightcurve_build --preset rw-aurigae --out data/products/lightcurves
python -m errante_api.lightcurve_build --preset r-draconis --out data/products/lightcurves
```

Use the worktree's virtual environment (`.venv/Scripts/python.exe` on Windows). The CLI requires an explicit
publication directory. Presets use DR1 + QR3, fixed sky coordinates and a historical MJD cutoff (RW: 61300,
Dra: 61315). RW uses detector 1 aperture photometry; Dra uses all detectors and PSF-wing photometry with a
period search over 20–800 days, 100 bootstraps and 100 visit permutations. Defaults: 600 frames (allowed
2–2500), archive deadline 180 s, total deadline 600 s (up to 1800 s), private staging budget 2 GiB and log
limit 1 MiB. CLI flags: `--max-frames`, `--bootstrap`, `--permutations`, `--archive-deadline`, `--deadline`,
`--max-bytes`, `--work-dir`. Private work and public output directories must be separate.

WS1 obtains native stamps with WS3's method-specific planes and box sizes. WS3's `exposures_from_series`,
`light_curve_from_exposures` and `matched_pairs` do the measurements. The supervised child has a parent
watchdog; timeout/disk overrun stops the owned process tree and removes staging. Admission requires up to
512 MiB free space (or the smaller requested budget). Disk usage is sampled; hard memory/CPU/disk quotas
remain a host concern. Only a complete validated result matching the requested target, parameters and
processing fingerprint is atomically published. Failures preserve the previous product. Fields and manifest
are not modified. The fingerprint covers science modules, the adapter, shared WS1/WS2 code and library versions.
Old packaged snapshots remain explicitly dated snapshots; refreshing them is an offline action.

### Real-data acceptance and interpretation

The two packaged JSON products were calculated from real SPHEREx FITS on 2026-11-15. Both preserve
`synthetic: false`, `stale_search: true` and `partial: true`: archive selection used a cached search snapshot;
these are not fresh exhaustive archive queries. Inspect `n_found`, `n_selected`, failures and sources before
interpreting the curve. Selection truncation, stale searches and failed measurements remain explicit.

| Target | Measured / usable | Interpretation |
|---|---:|---|
| RW Aurigae | 56 / 10 | Uncorrected aperture flux in **mJy**; 8 matched pairs; excluded saturation/bad pixels/bin cuts retained; no period fitted |
| R Draconis | 538 / 450 | Relative PSF-wing surface brightness in **MJy/sr**, not total flux; best period ≈259 d, bootstrap 95% ≈240–276 d, FAP 1/101 with 100 permutations; aliases retained |

Relative magnitudes are normalized separately per detector/wavelength bin; negative means brighter.
`zero_point_mag` is reported but not applied. Statistical `rel_mag_err` does not include comparison-star
systematics; read the control scatter as well. Null uncertainties stay null. Fixed-position measurements do
not track proper motion/parallax, and wavelength and time vary together. These products provide technical
acceptance of the WS4 adapter; independent scientific R05 validation remains with WS3. A significant grid
sinusoid still needs comparison with independent observations/catalog periods.

WS5 can consume the index and typed product to add the light-curve panel after WS3 approves the proposal;
no frontend panel or static-site publication is included here. Static deployments may copy these JSON
snapshots explicitly. Recalculation never runs in a public request.

Offline regression tests in `backend/tests/test_lightcurves.py` cover real snapshot integrity, API/ETags,
invalid overrides, content-cache invalidation, atomic publication, real child termination, result identity,
disk admission and native WS3 integration on explicitly synthetic test stamps. Synthetic test products are
never bundled. Code/document assistance: OpenAI Codex; numerical products come from the unchanged WS3
algorithms applied to real FITS, not generated imagery. Human scientific review remains pending.
