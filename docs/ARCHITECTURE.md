# Arquitectura

```
                         ┌──────────────────────── pipeline/  (Python, offline o bajo demanda) ───────────────────────┐
 IRSA TAP/SIA ──search──▶│ WS1 data/   irsa.search_frames ─▶ cutouts.fetch_cutouts ─▶ fits_io.read_spherex           │
 IRSA cutouts / S3 ─────▶│                                                                                            │
                         │ WS2 imaging/ grid.make_grid ─▶ reproject_to_grid ─▶ render.save_png (PNG norte-arriba)     │
                         │ WS2 detect/  find_sources ─▶ static_sky/residuals ─▶ link_tracks ─▶ score_tracks          │
 JPL SBIdent/Horizons ──▶│ WS3 science/ objects_in_frame ─▶ crossmatch ─▶ motion/distance ─▶ spectra                 │
 IMCCE SkyBoT ──────────▶│                                                                                            │
                         │ build.build_field  (orquesta todo)  ─▶  products.ProductStore                              │
                         └───────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                                 ▼
                              data/products/  (o data/demo/ sintético)        ← EL CONTRATO (docs/CONTRACT.md)
                              manifest.json · fields/<id>/{field,candidates,known}.json · frames/*.png
                                     │                                   │
                       (modo static) │                                   │ (modo api)
                                     ▼                                   ▼
                     frontend/public/data/  ◀── sync-data      backend/ FastAPI (WS4)
                                     │                          /api/manifest, /api/fields/... (lee productos)
                                     │                          /api/search, /api/known-objects (en vivo, WS1/WS3)
                                     ▼                                   │
                         frontend/ (WS5)  Vite + React + TS  ◀───────────┘
                         Home (campos) · Field (blink + candidatos + espectro + mapa) · About
```

## Decisiones (y por qué)

| Decisión | Por qué |
|---|---|
| **Contrato primero** (`models.py` → JSON Schema → `types.ts`) + **datos demo sintéticos** commiteados | Los 6 workstreams arrancan en paralelo desde la hora 0 sin esperar al pipeline real |
| **Procesamiento pesado offline**, la web solo muestra PNG + JSON | Reproyectar/detectar sobre FITS no entra en un request web; la demo no depende de que IRSA responda en vivo |
| **Todas las imágenes de un campo reproyectadas a una grilla común norte-arriba** | El blink es trivial (apilar PNGs) y los overlays usan x/y sin WCS en el navegador |
| **Frontend estático por defecto** (modo `static`), backend opcional (modo `api`) | Deploy gratis en GitHub Pages/Vercel/Netlify; el backend agrega búsqueda en vivo si llegamos |
| **Cutouts de IRSA** en vez de archivos de 66 MB | Un campo de 15′ pesa KB–MB; S3 queda para lotes grandes o lectura por rangos |
| **Píxeles en convención PNG** en el contrato | Es lo que necesita la UI; la conversión FITS↔PNG vive solo en `imaging/grid.py` |
| Python: numpy/astropy/pydantic/pillow base; scipy/photutils/reproject/astroquery como extra `science` | CI y backend livianos; los WS científicos instalan el extra |
| Sin librerías de UI/routing en el frontend (hash router propio) | Menos dependencias, deploy en cualquier host estático |

## Flujo de un campo real (objetivo de integración)

```bash
errante search --ra 269.4463 --dec 4.7665          # WS1: ¿qué frames hay?
errante build barnards-star                         # todo el pipeline → data/products/
make web   # y abrir http://localhost:5173/?dataset=real
```

`build` se detiene con un mensaje claro en la primera etapa que todavía sea `NotImplementedError`, así se ve
qué falta para el primer campo real de punta a punta.

## Hitos de integración

1. **I0 (hecho)**: demo sintético de punta a punta (pipeline → JSON/PNG → web).
2. **I1**: un campo real (Barnard o campo profundo) con frames reales en el blink, sin detección (WS1 + WS2 render).
3. **I2**: candidatos reales en ese campo + cruce con objetos conocidos (WS2 + WS3).
4. **I3**: 3–5 campos curados + página de límites (inyección) + deploy público (todos).
