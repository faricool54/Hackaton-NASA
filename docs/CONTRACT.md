# Contrato de datos (pipeline ⇄ backend ⇄ frontend)

Fuente de verdad: [`pipeline/errante/models.py`](../pipeline/errante/models.py).
Generado: [`shared/schema/*.schema.json`](../shared/schema/) (`make schema`). Espejo TS:
[`frontend/src/api/types.ts`](../frontend/src/api/types.ts). Versión actual: **0.1.0**.
Ejemplos reales del formato: [`data/demo/`](../data/demo/).

## Archivos en disco (= lo que lee el frontend estático)

```
<root>/manifest.json                      Manifest         lista de campos (FieldSummary[])
<root>/fields/<id>/field.json             Field            grilla + frames (+ procedencia)
<root>/fields/<id>/candidates.json        CandidateList    candidatos detectados
<root>/fields/<id>/known.json             KnownObjectList  objetos conocidos predichos en cada frame
<root>/fields/<id>/frames/<frame_id>.png  imagen 8 bits en la grilla común
<root>/fields/<id>/thumb.png              miniatura
```
`<root>` = `data/demo` (sintético) o `data/products` (real).

## API (backend)

| Método y ruta | Respuesta | Estado |
|---|---|---|
| `GET /api/health` | `{status, version, schema_version, data_dir, synthetic}` | ✅ |
| `GET /api/manifest` | `Manifest` | ✅ |
| `GET /api/fields/{id}` | `Field` | ✅ |
| `GET /api/fields/{id}/candidates` | `CandidateList` | ✅ |
| `GET /api/fields/{id}/known` | `KnownObjectList` | ✅ |
| `GET /data/fields/{id}/...` | PNGs | ✅ |
| `GET /api/search?ra&dec[&detector]` | `SearchResult` (frames SPHEREx que cubren el punto) | 501 → WS1+WS4 |
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

## Cómo cambiar el contrato

1. Rama `contract/<cambio>`; editar `models.py` (preferir campos **opcionales nuevos**).
2. `make schema` y actualizar `frontend/src/api/types.ts` en el mismo PR.
3. Si el cambio rompe compatibilidad: subir la versión mayor de `SCHEMA_VERSION` y regenerar `data/demo` (`make demo`).
4. PR titulado `contract: ...`, avisar en el chat a WS4 y WS5. CI falla si el schema commiteado quedó viejo.
