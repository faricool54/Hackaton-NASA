# Contrato de datos (pipeline ⇄ backend ⇄ frontend)

Fuente de verdad: [`pipeline/errante/models.py`](../pipeline/errante/models.py).
Generado: [`shared/schema/*.schema.json`](../shared/schema/) (`python scripts/dev.py schema`). Espejo TS:
[`frontend/src/api/types.ts`](../frontend/src/api/types.ts). Versión actual: **0.2.0** (0.2.0 agregó los sistemas 3D, aditivo).
Ejemplos reales del formato: [`data/demo/`](../data/demo/).

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
- **SystemModel** (3D): unidades `radius_km`, `mass_kg`, `teff_k`, órbitas en AU/días/grados, `Orbit.parent` =
  `Body.id` del padre (`orbit = null` ⇒ cuerpo raíz en el origen), `epoch_mjd = null` ⇒ fase arbitraria.
  `Fact.verified = false` ⇒ la UI marca el valor como "unverified". Siempre se muestra `representation_note`.
  `Manifest.systems` puede faltar en productos viejos (tratar como `[]`).

## Campo visible sin análisis automático

`errante build <id>` publica `Field`, imágenes, manifest y listas vacías compatibles de `CandidateList` y
`KnownObjectList`. `Provenance.notes` aclara que no se ejecutó detección/cruce. **Vacío no significa búsqueda
negativa si el análisis no se ejecutó.** `--analyze` opta por esas etapas una vez guardado el campo básico.
Esta separación no cambia `SCHEMA_VERSION` ni agrega campos al contrato actual.

## Extensiones diseñadas, todavía sin contrato publicado

WS4-10 coordina, en cambios aditivos versionados, lo necesario para:

- R03/C04: solicitud por RA/Dec/FOV/filtros, caché, job ID y estados/progreso/error/sin cobertura.
- C01/C07: versión de procesamiento, selección de épocas, cobertura y flags de contaminación con significado.
- C02/C03: coadds y suma/resta con miembros, pesos/método, fechas, bandas, máscaras y unidades.
- C02: espectro en una posición elegida, independiente de candidatos, con λ/ancho, flujo/error y fecha.
- C05: contexto Gaia DR3/WISE con catálogo/misión, época, propagación y procedencia.

Estos puntos son **diseño pendiente**, no nuevas rutas API ni campos que el frontend pueda consumir hoy.
La URL propuesta de exploración está en ARCHITECTURE.md; la restauración de coordenadas aún no existe.

## Cómo cambiar el contrato

1. Rama `contract/<cambio>`; editar `models.py` (preferir campos **opcionales nuevos**).
2. `python scripts/dev.py schema` y actualizar `frontend/src/api/types.ts` en el mismo PR.
3. Si el cambio rompe compatibilidad: subir la versión mayor de `SCHEMA_VERSION` y regenerar `data/demo` (`python scripts/dev.py demo`).
4. PR titulado `contract: ...`, avisar en el chat a WS4 y WS5. CI falla si el schema commiteado quedó viejo.
