# Contrato de datos (pipeline ⇄ backend ⇄ frontend)

Fuente de verdad: [`pipeline/errante/models.py`](../pipeline/errante/models.py).
Generado: [`shared/schema/*.schema.json`](../shared/schema/) (`python scripts/dev.py schema`). Espejo TS:
[`frontend/src/api/types.ts`](../frontend/src/api/types.ts). Ejemplos reales del formato: [`data/demo/`](../data/demo/).

**Versión vigente: 0.1.0.** La 0.3.0 está **propuesta** (abajo) y se aplica con un único PR `contract:`
(dueño WS3; revisan WS2, WS4 y WS5). Hasta que se mergee, todos trabajan contra 0.1.0 + `data/demo`.
Solo se modifica vía PR `contract:` (ownership en [`AGENTS.md`](../AGENTS.md)).

## Estado actual: 0.1.0

### Archivos en disco (= lo que lee el frontend estático)

```
<root>/manifest.json                      Manifest         lista de campos (FieldSummary[])
<root>/fields/<id>/field.json             Field            grilla + frames (+ procedencia)
<root>/fields/<id>/candidates.json        CandidateList    candidatos detectados
<root>/fields/<id>/known.json             KnownObjectList  objetos conocidos predichos en cada frame
<root>/fields/<id>/frames/<frame_id>.png  imagen 8 bits en la grilla común
<root>/fields/<id>/thumb.png              miniatura
```
`<root>` = `data/demo` (sintético) o `data/products` (real, golden fields).
En 0.3.0 se suma `data/cache/views` (campos efímeros de `/api/view`, mismo layout, no se commitea).

### API (backend)

| Método y ruta | Respuesta | Estado |
|---|---|---|
| `GET /api/health` | `{status, version, schema_version, data_dir, synthetic}` | ✅ |
| `GET /api/manifest` | `Manifest` | ✅ |
| `GET /api/fields/{id}` | `Field` | ✅ |
| `GET /api/fields/{id}/candidates` | `CandidateList` | ✅ |
| `GET /api/fields/{id}/known` | `KnownObjectList` | ✅ |
| `GET /data/fields/{id}/...` | PNGs | ✅ |
| `GET /api/search?ra&dec[&detector]` | `SearchResult` (frames SPHEREx que cubren el punto) | 501 → WS1+WS4 |
| `GET /api/known-objects?ra&dec&mjd[&radius_deg]` | `KnownObject[]` | 501 → WS3+WS4 (P1/P2 en `PLAN.md`) |
| `GET /api/view`, `GET /api/photometry` | ver propuesta 0.3.0 | no existen todavía |

### Convenciones

- **Coordenadas**: ICRS, grados (`SkyCoord {ra, dec}`).
- **Tiempo**: `mjd` = **mitad de la exposición** (`MJD-AVG` del header, o `(t_min+t_max)/2` de la búsqueda).
  `MJD-OBS` es el **inicio** de la exposición: no usarlo como tiempo del frame. Además `date_obs` ISO-8601 UTC.
  (La descripción de `Frame.mjd` en `models.py` todavía dice `MJD-OBS`: se corrige en el PR 0.3.0.)
- **Píxeles (`x`, `y`)**: convención PNG en la grilla del campo — origen en el píxel de arriba a la izquierda,
  base 0, x → derecha, **y → abajo**; norte arriba, este a la izquierda. FITS: `x_fits = x + 1`, `y_fits = alto − y`.
  El centro del píxel (0,0) se dibuja en (0.5, 0.5) del SVG.
- **Grid.wcs**: tarjetas FITS (`CTYPE/CRVAL/CRPIX/CDELT`) por si el frontend quiere mostrar RA/Dec bajo el cursor.
- **Frame.image**: ruta relativa al directorio del campo.
- **Flujos**: `flux_mjy` en mJy; imágenes en MJy/sr (`Stretch.unit`).
- **Candidate.status**: `known` | `unconfirmed` | `artifact` | `injected` (ver SCIENCE §4). `score` ∈ [0, 1].
- **Provenance.synthetic = true** ⇒ la UI DEBE mostrar el badge de datos sintéticos.
- **Field.id**: slug `^[a-z0-9][a-z0-9-]*$`.

### Glosario (se fija en 0.3.0)

| Término | Definición |
|---|---|
| **exposición** | 1 archivo Level 2, 1 detector. Hoy `Frame` = una exposición. |
| **visita** | exposiciones separadas por menos de 6 h. |
| **temporada / pasada** | bloques de exposiciones separados por más de 20 días. SPHEREx vuelve a cada punto cada ~6 meses. |

## Propuesta 0.3.0 (pendiente de PR `contract:`)

> **0.2.0** está tomada por la rama WS7 (`claude/ecstatic-turing-rcu8jq`: `SystemModel`, `Body`, `Orbit`,
> `Manifest.systems`), todavía sin mergear. Por eso esta propuesta es 0.3.0. Si WS7 se mergea primero, el PR
> 0.3.0 se arma encima de esa versión (ambas son aditivas).

**Solo campos opcionales** (cambio menor: `SCHEMA_VERSION` 0.1.0 → 0.3.0, nada existente se rompe).
Tabla tomada de [`PLAN.md`](PLAN.md) §3:

| Modelo | Campo nuevo (opcional) | Para qué |
|---|---|---|
| `Frame` | `kind: "exposure" \| "coadd" \| "difference"` (default `"exposure"`) | coadds y restas en el mismo video |
| `Frame` | `season: int`, `mjd_start`, `mjd_end`, `n_inputs`, `input_ids: list[str]` | agrupar por temporada, mostrar Δt real |
| `Frame` | `wavelength_min_um`, `wavelength_max_um` | rango de λ de un coadd |
| `Frame` | `flag_fractions: dict[str, float]`, `flags_at_target: list[str]` | metadata de contaminación (consideración oficial) |
| `Field` | `query: {ra, dec, fov_arcmin, detectors, group, collections}` | campos efímeros de `/api/view`, URL embebible |
| `Field` | `target: {name, ra, dec, ref_epoch, pm_ra_cosdec_mas_yr, pm_dec_mas_yr, parallax_mas, source}` | posición predicha por época |
| `KnownObject` | `pm_*`, `parallax_mas`, `ref_epoch`, `mag`, `mag_band`; `MatchSource += gaia_dr3, catwise2020, simbad` | overlays de estrellas con movimiento propio |
| `SpectrumPoint` | `mjd`, `season`, `detector`, `flags` | espectro por temporada, curva de luz |
| `Release` | pasar de `Literal` a `str` con patrón `^((dr\|qr)\d+(_deep)?\|synthetic)$` | que un release nuevo no rompa la validación |

Además en el mismo PR: `Frame.mjd` documentado como `MJD-AVG`, el glosario de arriba en los docstrings, y el
documento de respuesta de `/api/photometry` (nombre a definir, p. ej. `PhotometryResult`) agregado a
`ALL_MODELS` para que tenga su `shared/schema/*.schema.json`.

### `GET /api/view` (P0)

Construye (o toma de caché) un campo para coordenadas arbitrarias. Devuelve un `Field` común, así el
`BlinkViewer` se reutiliza sin cambios.

| Parámetro | Tipo | Notas |
|---|---|---|
| `ra` | float, [0, 360) | grados ICRS (el frontend convierte sexagesimal y nombres antes de llamar) |
| `dec` | float, [-90, 90] | grados ICRS |
| `fov_arcmin` | float > 0 | default y tope a fijar en el PR (❓ la crítica final sugiere ≥ 8′ por defecto, para que WISE 0855 entre aun con la coordenada del enunciado; tope ~1°, que son ≈ 4.8 MB por exposición) |
| `det` | int 1–6 | un detector por pedido en P0; `Field.query.detectors` es lista para dejar abierta la puerta a varios |
| `group` | `season` \| `exposure` | default `season` (un coadd por temporada + diferencia); `exposure` = exposiciones individuales, con tope |
| `collections` | lista, opcional (P1) | default = `ERRANTE_COLLECTIONS` del backend |

**Respuesta 200:** `Field` con `query` completo, `provenance.synthetic = false`, `frames` de `kind="coadd"` /
`"difference"` (o `"exposure"`) y `target` si las coordenadas corresponden a un objetivo conocido.
Id determinista `v-<ra>-<dec>-<fov>-d<det>-<group>`, codificado para cumplir el slug (p. ej. sin `.` ni `+`;
la codificación exacta se fija en el PR). Archivos en `data/cache/views/fields/<id>/`.
❓ Ruta para servir esos PNG (hoy `/data` solo monta los productos): se decide en el PR.

### `GET /api/photometry` (P1)

Fotometría por frame en una posición: alimenta el **espectro al vuelo** (x = λ, color = temporada) y la
**curva de luz** de RW Aur y R Dra (x = mjd, comparando la misma λ entre temporadas).

| Parámetro | Tipo | Notas |
|---|---|---|
| `ra`, `dec` | float | igual que `/api/view` |
| `det` | int 1–6, opcional | default: todos |
| `radius_arcsec` | float, opcional | radio de apertura; default a fijar por WS3 |

**Respuesta 200:** `{center: SkyCoord, points: SpectrumPoint[]}` con los campos nuevos de `SpectrumPoint`:
`{frame_id, mjd, season, detector, wavelength_um, bandwidth_um, flux_mjy, flux_err_mjy, flags}`.

### Códigos de error (ambas rutas)

| Código | Cuándo | Cuerpo |
|---|---|---|
| `400` | Parámetros inválidos o fuera de lo que se procesa en vivo (FOV > tope, demasiadas exposiciones). WS4 convierte el 422 de validación de FastAPI en 400 con un handler, para que 422 signifique solo "sin datos". | `{detail}` (+ `hint` si hay que pedir menos) |
| `422` | Ningún frame SPHEREx cubre la posición (mismo sentido que el 422 del cutout IBE). | `{detail}` |
| `502` | IRSA o S3 respondieron con error o respuesta inválida. | `{detail, upstream}` |
| `504` | IRSA o S3 no respondieron dentro del timeout. | `{detail, upstream}` |

Todo error devuelve JSON (también los 500 inesperados) para que el navegador no lo vea como error de CORS.
La UI muestra un mensaje distinto para cada caso y ofrece los 5 objetivos (golden fields) como alternativa.

## Cómo cambiar el contrato

1. Rama `contract/<cambio>`; editar `models.py` (preferir campos **opcionales nuevos**).
2. `python scripts/dev.py schema` y actualizar `frontend/src/api/types.ts` en el mismo PR.
3. Subir `SCHEMA_VERSION`: menor si es aditivo (0.1.0 → 0.3.0), mayor si rompe compatibilidad.
4. Solo si el demo tiene que mostrar los campos nuevos (o el cambio rompe): `python scripts/dev.py demo`.
   **`data/demo/` se regenera únicamente en PRs de contrato.**
5. `python scripts/dev.py check` (incluye `errante schema --check` y la validación de `data/demo`).
6. PR titulado `contract: ...`; revisan WS2, WS4 y WS5; aviso en el chat. CI falla si el schema commiteado
   quedó viejo.
7. Después del merge, quien coordina avisa "contrato 0.3.0 mergeado" y todos actualizan su rama con
   `git pull origin main` (merge, sin rebase ni force). Si `data/demo/` o `shared/schema/` chocan, no se resuelven
   a mano: se toma la versión de `main` y se regenera (`python scripts/dev.py demo` / `schema`).
   Detalle de archivos calientes: [`COLLABORATION.md`](COLLABORATION.md) §4.
