# data/

| Carpeta | Qué hay | ¿Se commitea? |
|---|---|---|
| `demo/` | Dataset **sintético** generado con `python scripts/dev.py demo` (2 campos falsos). Sirve para desarrollar UI/backend sin red. | ✅ sí |
| `products/` | Productos **reales** generados con `errante build <field-id>` (mismo formato que demo). | Solo campos curados y livianos (< ~20 MB en total) |
| `cache/` | Descargas de IRSA/S3, resultados de consultas. | ❌ nunca (ignorado) |

Formato: ver `docs/CONTRACT.md`. Validar: `errante validate --dir data/products`.
