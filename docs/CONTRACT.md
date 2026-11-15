# Contrato de datos (pipeline ⇄ backend ⇄ frontend)

Fuente de verdad: [`pipeline/errante/models.py`](../pipeline/errante/models.py).
Generado: [`shared/schema/*.schema.json`](../shared/schema/) (`python scripts/dev.py schema`). Espejo TS:
[`frontend/src/api/types.ts`](../frontend/src/api/types.ts). Versión de esta integración: **0.4.0** (#53),
después de **0.3.1** composites (#39, ya mergeado). **0.3.0** (#32) agregó `JobSubmitRequest`, `JobStatusResponse` y `ResolvedRegion`.
0.2.0 agregó sistemas 3D y 0.2.1 `Orbit.quality`/`note`. Los productos anteriores siguen siendo compatibles.
Ejemplos sintéticos: [`data/demo/`](../data/demo/). Los cinco campos reales de WS2 están en
[`data/products/`](../data/products/); sus imágenes no equivalen a cinco validaciones científicas R05.

## Archivos en disco (= lo que lee el frontend estático)

```
<root>/manifest.json                      Manifest         lista de campos (FieldSummary[])
<root>/fields/<id>/field.json             Field            grilla + frames (+ procedencia)
<root>/fields/<id>/candidates.json        CandidateList    candidatos detectados
<root>/fields/<id>/known.json             KnownObjectList  objetos conocidos predichos en cada frame
<root>/fields/<id>/frames/<frame_id>.png  imagen 8 bits en la grilla común
<root>/fields/<id>/thumb.png              miniatura
<root>/systems/<id>.json                  SystemModel      modelo 3D de un sistema/objeto (WS7)
```
`<root>` = `data/demo` o `data/products`. El nombre del directorio no prueba verificación ni origen real:
leer `Provenance.synthetic`, notas y `Fact.verified`. Un SystemModel es un modelo, no una imagen SPHEREx.

## API (backend)

| Método y ruta | Respuesta | Estado |
|---|---|---|
| `GET /api/health` | `{status, version, schema_version, data_dir, synthetic}` | ✅ |
| `GET /api/manifest` | `Manifest` | ✅ |
| `GET /api/fields/{id}` | `Field` | ✅ |
| `GET /api/fields/{id}/candidates` | `CandidateList` | ✅ |
| `GET /api/fields/{id}/known` | `KnownObjectList` | ✅ |
| `GET /data/fields/{id}/...` | PNGs | ✅ |
| `GET /api/systems/{id}` | `SystemModel` | ✅ |
| `GET /api/search?ra&dec[&detector]` | `SearchResult` (frames SPHEREx que cubren el punto) | ✅ WS1+WS4; 502/504 ante fallo/timeout externo |
| `POST /api/jobs` | `JobStatusResponse`, HTTP 202 | ✅ habilitar `ERRANTE_ENABLE_JOBS=1` |
| `GET /api/jobs/{id}` | `JobStatusResponse` | ✅ |
| `GET /api/resolve-name?name=...` | `ResolvedRegion` | ✅ Sesame/CfA |
| `POST /api/spectra` | `SpectrumResponse` | ✅ WS1 cube/point + WS2 photometry; extra science |
| `POST /api/fields/{id}/comparisons` | `ComparisonResponse` | ✅ WS2 temporadas/diferencias; extra science |
| `GET /data/analyses/{sha256}/...` | PNG y `analysis.json` | ✅ publicación independiente e inmutable |
| `GET /api/known-objects?ra&dec&mjd[&radius_deg]` | `KnownObject[]` | 501 → WS3+WS4 |

## Convenciones

- **Coordenadas**: ICRS, grados (`SkyCoord {ra, dec}`). **Tiempo**: MJD (`mjd`), además `date_obs` ISO-8601 UTC.
- **Píxeles (`x`, `y`)**: convención PNG en la grilla del campo — origen en el píxel de arriba a la izquierda,
  base 0, x → derecha, **y → abajo**; norte arriba, este a la izquierda. FITS: `x_fits = x + 1`, `y_fits = alto − y`.
  El centro del píxel (0,0) se dibuja en (0.5, 0.5) del SVG.
- **Grid.wcs**: tarjetas FITS (`CTYPE/CRVAL/CRPIX/CDELT`) por si el frontend quiere mostrar RA/Dec bajo el cursor.
- **Frame.image**: ruta relativa al directorio del campo.
- **Flujos**: `flux_mjy` en mJy; imágenes en MJy/sr (`Stretch.unit`).
- **Candidate.status**: `known` | `unconfirmed` | `artifact` | `injected` (ver SCIENCE §4). `score` ∈ [0, 1].
- **Provenance.synthetic = true** ⇒ la UI DEBE mostrar el badge de datos sintéticos.
- **SystemModel** (3D): unidades `radius_km`, `mass_kg`, `teff_k`, órbitas en AU/días/grados, `Orbit.parent` =
  `Body.id` del padre (`orbit = null` ⇒ cuerpo raíz en el origen), `epoch_mjd = null` ⇒ fase arbitraria.
  `Orbit.quality`: `fitted` | `assumed` (no ajustada) | `hypothetical`; la UI marca todo lo que no sea `fitted`.
  `Fact.verified = false` ⇒ la UI marca el valor como "unverified". Siempre se muestra `representation_note`.
  `Manifest.systems` puede faltar en productos viejos (tratar como `[]`).

## Campo visible sin análisis automático

`errante build <id>` publica `Field`, imágenes, manifest y listas vacías compatibles de `CandidateList` y
`KnownObjectList`. `Provenance.notes` aclara que no se ejecutó detección/cruce. **Vacío no significa búsqueda
negativa si el análisis no se ejecutó.** `--analyze` opta por esas etapas una vez guardado el campo básico.
Esta separación no cambia `SCHEMA_VERSION` ni agrega campos al contrato actual.

## Construcción por coordenadas (0.3.0, R03/C04/C06)

POST recibe `ra` [0,360), `dec` [-90,90], `size_deg` [0.01,0.5] (default 0.25), `detectors` 1–6
(vacío = todos), `mjd_min`/`mjd_max` opcionales ordenados y `max_frames` 2–120 (default 40).
Todos los números son finitos. JSON Schema y modelos son la fuente de validación; OpenAPI usa esos modelos.

```json
{"ra":269.44623,"dec":4.76870,"size_deg":0.15,"detectors":[2],"max_frames":40}
```

POST devuelve 202 incluso si reutiliza un job compatible. GET devuelve el mismo formato:
`id`, `status`, `stage`, `created_at`, `updated_at`, `result_field_id` y `error_detail` (ambos nullable).
Estados públicos: `queued`, `running`, `ready`, `failed`, `no_coverage`, `pipeline_not_ready`.
La transición interna `publishing` se representa como `running`. Stage describe una etapa, no un porcentaje.
En `ready`, `result_field_id` abre `/api/fields/{id}`; cada `Frame.image` se lee bajo `/data/fields/{id}/`.
Los resultados se confirman solo tras validar y publicar JSON/PNG/manifest.

422 = validación (detail puede ser string o lista estándar FastAPI), 429 = cupo/cola con Retry-After,
503 = motor desactivado/almacenamiento no disponible, 404 = job desconocido. Un fallo genérico de descarga
no es `no_coverage`. El frontend no reenvía un POST al fallar el polling y “Stop watching” no cancela el worker.
Los errores públicos no exponen tracebacks; diagnóstico en directorio privado.

El resolver devuelve `ra`, `dec`, `object_type`, `resolved_name`, `source`. Su coordenada de catálogo no
certifica cobertura ni está propagada automáticamente a la época SPHEREx; los cinco presets sí tienen
centros propagados documentados en `fields.toml`. CfA puede devolver decimal o jpos sexagesimal con dos puntos.

## Espectros y comparaciones (0.4.0, C02/C03)

`SpectrumRequest`: RA/Dec finitos, `source` (`dr1_cube` default o `l2_exposures`), `detectors` (vacío = todos),
`field_id` opcional, `aperture_px` 0–3 para cubo; L2 admite `mjd_min/max` ordenados y `max_frames` 2–60.
El cubo rechaza filtro temporal; L2 rechaza apertura del cubo distinta de cero. Un campo adjunto exige
procedencia real y posición dentro de su WCS. Sin campo la extracción funciona por coordenadas.

`SpectrumResponse`: centro/fuente, puntos λ/ancho, flujo/error nullable, detector, MJD/release, URI, flags,
`usable`, nhits/n_used/corrección de apertura si existen; notas, fallos parciales, stale/truncated.
Cubo = `static_coadd: true`, MJy/sr sin cielo sustraído ni error de flujo. L2 = `static_coadd: false`, mJy
con cielo local sustraído, errores por exposición. No interpolar ni convertir null a cero; conservar negativos.
Un cubo de 102 planos no garantiza 102 mediciones válidas. No se afirma simultaneidad ni seguimiento de movimiento.

`ComparisonRequest`: `detectors` y `frame_ids` opcional (2–60 IDs únicos y existentes). El servidor filtra
el campo, exige 2–60 entradas y grilla ≤512², mantiene detectores separados y llama WS2 compare_field.
`ComparisonResponse`: id SHA-256, field_id/época original, fecha de cálculo, unidad MJy/sr, método, todos
los Frame de entrada, productos, fallos y notas. Cada `ComparisonImage` conserva IDs, detector, épocas,
λ/cobertura si existen. `weighted_mean` identifica temporada; `scaled_difference` referencia dos medias
y escala later − scale × earlier, ajuste/estrellas/ruido/límite de display. Pesos individuales desconocidos
son `null`; no inventarlos. No hay suma cruda arbitraria ni interpretación automática de variabilidad.

`ComparisonImage.image` es relativa a la raíz pública: `analyses/{id}/compare/{name}.png`, a diferencia
de `Frame.image`, relativa al campo. Validadores cruzan IDs/épocas/detectores y referencias. Se publica
`analyses/{id}/analysis.json` junto a PNG verificados sin cambiar field.json ni el manifest original.
Las respuestas científicas exigen `synthetic: false`; un campo sintético se rechaza con 409.
422 = selección/posición inválida, 413 = exceso, 503 = cupo/disco, 502/504 = fallo/deadline.
Sin cobertura o cero puntos utilizables sigue siendo un resultado explícito, nunca una detección inventada.

Contrato, backend y UI se integraron en main en orden #53 → #54 → #55, después de la caché #52.
Se conservaron composites y modos de color #39/#40/#41 sin modificar sus ramas. Para futuras pilas, tras
cada squash traer main, check/push y retargetear el siguiente PR. `compare.json` interno de WS2 no se consume directamente en UI.

## Extensiones aún sin contrato publicado

- `Field.composites` (falso color por temporada) está integrado desde #39 en 0.3.1; 0.4.0 lo conserva.
- C01/C07: metadatos ampliados de selección, cobertura y flags con significado.
- C02/C03: revisión de interpretación científica y futuras medidas adicionales con WS3; no duplicar la API 0.4.0.
- C05: ficha Gaia y mediciones para modelos físicos 3D; no usar el esquema ilustrativo como mediciones nuevas.

Las coordenadas/FOV/detector/job en URL ya se restauran en el frontend. Modo compacto/iframe externo pendiente.

## Cómo cambiar el contrato

1. Rama `contract/<cambio>`; editar `models.py` (preferir campos **opcionales nuevos**).
2. Subir versión, regenerar `python scripts/dev.py schema` y actualizar tipos/constante TS en el mismo PR.
3. Si rompe compatibilidad: versión mayor y regeneración de `data/demo`.
4. PR `contract: ...` con revisión afectada WS4/WS5; CI verifica schema y versión TS.
