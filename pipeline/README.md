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
errante build barnards-star --analyze      # opcional: detección/cruce después de guardar imágenes
errante systems                           # modelos de catálogo con fuentes y límites de representación
pytest -q pipeline/tests                   # ERRANTE_NETWORK_TESTS=1 para tests con internet
```

| Módulo | WS | Estado |
|---|---|---|
| `models.py`, `products.py` | contrato | ✅ 0.7.0; jobs, espectros/comparaciones, catálogo, curvas y movimiento propio L2 |
| `synthetic.py`, `cli.py`, `build.py` | integración | ✅ build real independiente del análisis opcional |
| `data/` | WS1 | ✅ búsqueda SIA/TAP, snapshots, S3/Range, cutouts, FITS, cubo y λ por posición |
| `imaging/` | WS2 | ✅ registro/reproyección, flags/render, fotometría y comparaciones; SNR del coadd y flags ampliados pendientes |
| `detect/` | WS2 | ⛔ |
| `science/` | WS3 | ✅ contexto de catálogo, espectros y variabilidad; temperatura/color, JPL y Planeta X pendientes |
| `systems/` | WS7, P1 | ✅ contexto 3D de catálogo; correcciones V4/V12/V13 en PR #90 abierto, no integrado |

Variables de entorno: `ERRANTE_PRODUCTS_DIR`, `ERRANTE_DEMO_DIR`, `ERRANTE_CACHE_DIR`,
`ERRANTE_HTTP_TIMEOUT_S`, `ERRANTE_MAX_PARALLEL` (ver `errante/settings.py`).

El build básico no necesita detección ni catálogos: escribe listas vacías y aclara en procedencia que no
ejecutó análisis. Con `--analyze`, las imágenes sobreviven a un fallo de etapas opcionales. Sin cobertura,
el comando falla explícitamente sin publicar un campo vacío. Búsqueda, cutouts y reproyección reales están
integrados y se usan en los jobs públicos. Los cinco registros FITS tienen revisión humana pendiente.

Estado al 15/11/2026 sobre `main` 3ed5c91 (#97); publicación verificada 3ed5c91 (#97). La app/API pública está en
[Errante](https://errante.34-148-242-13.sslip.io); plan y dependencias en [PARALLEL_PLAN.md](../docs/PARALLEL_PLAN.md).
Los FITS/caches pesados no se versionan. Para experimentar fuera de WS2, pasar `--out` con una carpeta privada.

Alcance y selección de épocas/blancos: `docs/REQUIREMENTS.md` y `docs/VALIDATION.md`.
