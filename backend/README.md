# backend/ — `errante_api` (FastAPI) · WS4

```bash
python scripts/dev.py api   # = cd backend && uvicorn errante_api.main:app --reload --port 8000 (API_PORT to change it)
open http://localhost:8000/docs
```

Datos servidos: `ERRANTE_DATA_DIR` si está definido; si no, `data/products` si existe; si no, `data/demo`.
CORS: `ERRANTE_CORS_ORIGINS` (coma-separado, default `*`; restringir en producción).

Endpoints vigentes: [CONTRACT.md](../docs/CONTRACT.md). Tests: `pytest -q backend/tests`.
Asistencia de código/documentación: OpenAI Codex; metadata en [ai-usage.json](ai-usage.json).

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

**Dependencia pendiente WS1/WS2:** sus stubs impiden construir datos reales hoy. El runner lo informa como
`pipeline_not_ready`, no éxito. La selección de los primeros 40 frames en el pipeline puede ser rechazada por
falta de temporadas: WS2 debe corregirla con WS1/3. No se modifican sus módulos desde WS4.

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
Solo preparar/ejecutar el workflow no demuestra el flujo de jobs, todavía pendiente del contrato.

Referencias de configuración: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
y [contexto Docker/Dockerfile específico](https://docs.docker.com/build/concepts/context/#dockerignore-files).

## Propuesta para WS3 + WS5 (WS4-10): jobs por coordenadas

**Diseño para revisar, no implementado ni publicado en OpenAPI.** WS3 todavía no tiene responsable confirmado
al redactar esto. Su PR `contract:` debe agregar modelos/schema/tipos TS/versionado juntos y recibir revisión
de consumidores. WS4 no añade modelos compartidos ni publica rutas de jobs por separado.

Propuesta de rutas: `POST /api/field-jobs` → 202; `GET /api/field-jobs/{job_id}` → 200.
Solicitud propuesta (tamaño es lado del campo cuadrado, no radio):

```json
{
  "center": {"ra": 269.44623, "dec": 4.76870},
  "size_deg": 0.25,
  "detectors": [1],
  "mjd_min": null,
  "mjd_max": null,
  "max_frames": 40
}
```

Límites propuestos: RA [0,360), Dec [-90,90], valores finitos; lado [0.01,0.5] grados, detectores únicos 1–6,
MJD mínimo ≤ máximo, frames 2–120 y grilla ≤512×512. El cliente recibe los límites definitivos documentados.
El servidor determina releases/versiones y los registra: WS1 debe exponer esa selección al adaptador. La clave
de reutilización incluye TODOS los parámetros normalizados, releases/versiones, método de selección y pipeline.

Respuesta propuesta:

```json
{
  "job_id": "server-generated-id",
  "status": "queued",
  "field_id": null,
  "error": null,
  "warnings": [],
  "poll_after_s": 2
}
```

Estados propuestos: `queued`, `running`, `ready`, `no_coverage`, `failed`. Decidir con WS2/3 si producto parcial
es `ready` con advertencias y reporte de entradas fallidas o un estado aparte. `ready` requiere imágenes
legibles ya publicadas; `field_id` usa los endpoints existentes de campos/PNGs. `no_coverage` exige búsqueda
válida sin datos, nunca todas las descargas fallidas. Error estructurado sugerido: `code`, `message`, `retryable`.
Polling hasta estado terminal; 404 para ID desconocido/expirado, 422 para solicitud inválida, 503/Retry-After
para cola llena. Progreso solo si la etapa lo conoce; no inventar porcentajes.

Implementación prevista después del acuerdo: cola/estado persistente, límite de trabajos y bytes/frames,
deduplicación de solicitudes iguales, proceso aislado con deadline duro, publicación validada y recuperación
de estados interrumpidos al reiniciar. No reutilizar los hilos de búsqueda para ejecutar builds largos.
La función `build_field(FieldConfig, out, analyze=False)` es el adaptador de WS2; si cambian firmas/resultados
parciales o selección de releases, WS1/2 avisan antes de conectar. Espectros, operaciones y JPL quedan posteriores.
