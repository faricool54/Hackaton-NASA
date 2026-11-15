# data/

| Carpeta | Qué hay | ¿Se commitea? |
|---|---|---|
| `demo/` | Dataset **sintético** generado con `python scripts/dev.py demo` (2 campos falsos). Sirve para desarrollar UI/backend sin red. | ✅ sí |
| `products/` | Productos **reales** generados con `errante build <field-id>` (mismo formato que demo). | Solo campos curados y livianos (< ~20 MB en total) |
| `cache/` | Descargas de IRSA/S3, resultados de consultas. | ❌ nunca (ignorado) |

Formato vigente 0.7.0: ver [CONTRACT.md](../docs/CONTRACT.md). Validar: `errante validate --dir data/products`.
Hay cinco campos reales curados de 40 frames cada uno. Los productos de curvas y comparaciones congeladas
viven en `backend/errante_api/curated/` y se pueden exportar con `scripts/export_static_science.py`.
El runner API usa una copia privada en `data/cache/local/products`; la VM conserva `/app/runtime` en volumen.
No usar `data/products` como destino de jobs de desarrollo ni confundir fixtures `demo` con la app pública real.
