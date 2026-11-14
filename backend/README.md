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

**WS1/WS2 integrados:** búsqueda, recortes, reproyección y selección de temporadas ya construyen los cinco
objetivos con el pipeline oficial. Un stub futuro se informa como `pipeline_not_ready`, nunca éxito.
La validación científica de señal/variabilidad sigue separada de esta validación técnica.

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
Solo preparar/ejecutar el workflow no demuestra el recorrido desde una URL pública.

Referencias de configuración: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
y [contexto Docker/Dockerfile específico](https://docs.docker.com/build/concepts/context/#dockerignore-files).

## Jobs por coordenadas: implementación y conexión

Contrato compartido **0.3.0** en `errante.models`, `shared/schema` y tipos TS (PR #32). Las rutas usan
esos mismos modelos: no mantienen copias locales. WS5 consume POST/GET y el resolver desde ese contrato.

Activar con `ERRANTE_ENABLE_JOBS=1`. El backend sirve y construye en **el mismo directorio**:
`ERRANTE_DATA_DIR` si se definió, o `ERRANTE_PRODUCTS_DIR` aunque todavía no haya manifest. Al activar jobs
se prepara el directorio público antes de montar `/data`. La demo sigue disponible con jobs desactivados.

- `POST /api/jobs` devuelve 202, también al reutilizar un job activo/listo compatible.
- `GET /api/jobs/{id}` devuelve estado persistido; `publishing` se representa públicamente como `running`.
- Estados terminales: `ready`, `failed`, `no_coverage`, `pipeline_not_ready`. En `ready`, abrir
  `/api/fields/{result_field_id}` y las imágenes en `/data/fields/{result_field_id}/...`.
- Parámetros inválidos: 422; cola/capacidad agotada: 429 con Retry-After; almacenamiento ocupado/indisponible:
  503; ID desconocido: 404. Los errores públicos no incluyen tracebacks ni rutas locales.
- CORS admite GET y POST. Configurar el origen completo del frontend (puerto incluido).

```json
{"ra":269.44623,"dec":4.76870,"size_deg":0.25,"detectors":[1],"max_frames":40}
```

`mjd_min`/`mjd_max` son opcionales. RA [0,360), Dec [-90,90], lado [0.01,0.5] grados, detectores 1–6 y
2–120 frames. Se conservan las coordenadas; no se redondea RA a 360. La clave de reutilización incluye
parámetros, contexto de colecciones/fuentes, revisión de procesamiento y versiones de pipeline/schema.
Las publicaciones usan IDs inmutables por intento, imágenes verificadas y un manifest atómico. Batch y jobs
comparten lock de publicación entre procesos. Un fallo del manifest no se confirma como éxito.

### Recuperación y recursos

Una sola instancia/supervisor por directorio privado, protegido por lock del SO. SQLite serializa admisión y
claims. Un shutdown que no terminó mantiene la exclusividad. Al reiniciar, se verifica la identidad de un
hijo anterior antes de detenerlo; se reconcilian publicaciones con sus huellas y se repara el manifest antes
de confirmar `ready`. No se mata un PID ajeno reutilizado. `psutil` permite controlar y verificar procesos en
Windows/Linux; es una dependencia runtime del backend.

| Variable | Default | Uso |
|---|---|---|
| `ERRANTE_JOBS_DIR` | `data/cache/jobs` | SQLite, solicitudes/resultados y logs; fuera del árbol público |
| `ERRANTE_JOB_MAX_BYTES` | 768 MiB | Presupuesto supervisado del staging de un intento, incluida su caché |
| `ERRANTE_JOBS_MAX_BYTES` | 2 GiB | Admisión: espacio utilizado por estado privado y productos públicos |

Un build activo, hasta ocho trabajos activos/en cola y 900 s de deadline por build. Los logs se drenan sin
crecer por encima de 5 MiB. Se limpia caché/productos de staging terminales; diagnóstico privado por 24 h.
Los productos públicos no se borran automáticamente: al alcanzar el presupuesto se rechaza trabajo nuevo.
Hay que mantener al menos 128 MiB libres. El muestreo de disco es aproximado; cuotas duras de memoria/CPU/disco
son responsabilidad del host/contenedor. Los resultados desaparecidos o inválidos no se reutilizan.

`no_coverage` requiere una consulta válida vacía; errores genéricos de proyección/descarga no se interpretan
como ausencia de cobertura. Una secuencia técnica correcta tampoco certifica movimiento/variabilidad R05.
La integración de espectros, comparaciones y fichas científicas sigue las dependencias de WS2/WS3 de VISION.md.

Para verificar un PR apilado contra su base inmediata: `ERRANTE_BASE_REF=origin/<rama-base>` antes de
`python scripts/dev.py check` (PowerShell: `$env:ERRANTE_BASE_REF=...`). La guardia mantiene las mismas
reglas de dueños y CI usa la base del PR. Sin la variable sigue comparando con `origin/main`.
