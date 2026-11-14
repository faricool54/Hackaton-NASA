# pipeline/ — paquete `errante`

```bash
pip install -e "pipeline[dev]"            # base (numpy, astropy, pydantic, pillow, requests)
pip install -e "pipeline[dev,science]"    # + scipy, photutils, reproject, astroquery, pyvo
errante --help
errante demo                               # datos sintéticos → data/demo
errante schema [--check]                   # JSON Schema del contrato → shared/schema
errante validate --dir data/demo           # valida un directorio de productos
errante search --ra 269.4463 --dec 4.7665  # (WS1) frames SPHEREx que cubren el punto
errante build barnards-star                # campo real de config/fields.toml → data/products
pytest -q pipeline/tests                   # ERRANTE_NETWORK_TESTS=1 para tests con internet
```

| Módulo | WS | Estado |
|---|---|---|
| `models.py`, `products.py` | contrato | ✅ |
| `synthetic.py`, `cli.py`, `build.py` | integración | ✅ (build llama stubs) |
| `data/` | WS1 | s3/cache/fits_io ✅ · irsa/cutouts/wavelength ⛔ |
| `imaging/` | WS2 | grid/flags/render ✅ · reproject ⛔ |
| `detect/` | WS2 | ⛔ |
| `science/` | WS3 | motion ✅ · known_objects/spectra/planet_x ⛔ |

Variables de entorno: `ERRANTE_PRODUCTS_DIR`, `ERRANTE_DEMO_DIR`, `ERRANTE_CACHE_DIR`,
`ERRANTE_HTTP_TIMEOUT_S`, `ERRANTE_MAX_PARALLEL` (ver `errante/settings.py`).
