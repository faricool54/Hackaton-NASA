# Arquitectura del explorador temporal SPHEREx

Fuente de alcance: [CHALLENGE.md](CHALLENGE.md). Cobertura: [REQUIREMENTS.md](REQUIREMENTS.md).
La siguiente estructura distingue **lo implementado** de **lo diseñado y pendiente**.
Entrega: [SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md), condiciones S01–S10 del PDF. El video/slides de envío
es un artefacto distinto del visor temporal: <= 30 s o <= 7 slides, en inglés y accesible sin login.
El servicio público y sus materiales deben estar disponibles antes del cierre UP Buenos Aires: 15/11/2026
23:59 ART; objetivo interno de envío 21:00 ART. Reglas de SI/atribución se aplican a código, datos y medios.
La [rúbrica de evaluación](JUDGING_GUIDE.md) refuerza el camino crítico: datos NASA reales como núcleo
(Relevance), viabilidad/completitud/usabilidad (Validity) y relato/formulario/demo legibles (Presentation).
No agregar módulos solo para aparentar cobertura de diez premios ni sustituir validación por extras.

## Recorrido principal (P0, R01–R05)

```text
Usuario: RA/Dec → validar coordenadas → consultar cobertura SPHEREx
                                            │
                                   archivo / caché (WS1)
                                            │
                        seleccionar épocas y bandas comparables
                                            │
                  cutouts FITS → WCS/flags → grilla común → PNG (WS2)
                                            │
                  ProductStore: field + frames + procedencia + manifest
                                            │
                    API / archivos estáticos → visor temporal (WS5)
                                            │
             play / pausa / paso / fechas → cinco ensayos de validación (WS3)

Enriquecimiento opcional (P1/P2), después de guardar el campo visible:
  coadds / diferencias / espectros / Gaia-WISE / detección / catálogos / límites
```

La inspección visual de movimiento y brillo es una funcionalidad completa por sí misma.
Ni candidatos, ni JPL/SkyBoT, ni inferencia de distancia son dependencias del visor.

## Componentes y límites

| Componente | Responsabilidad principal | Ampliaciones previstas |
|---|---|---|
| `pipeline/errante/data/` (WS1) | Descubrimiento, consultas por coordenadas, cutouts, caché y FITS | Releases configurables, refresco, selección temporal, λ desde WCS-WAVE |
| `pipeline/errante/imaging/` (WS2) | Registro WCS, máscara de calidad y PNGs comparables | Coadds por detector/visita; suma/resta de épocas; metadatos de contaminación |
| `pipeline/errante/science/` (WS3) | Identidad, astrometría y protocolo de los cinco blancos | Fotometría de variables, espectros en cualquier posición, Gaia DR3; detección y Planeta X como extras |
| `pipeline/errante/build.py`, `cli.py` | Publicar primero el campo visible | `--analyze` opta por detección y cruce sin impedir conservar las imágenes |
| `backend/` (WS4) | Servir productos y ejecutar jobs persistentes por coordenadas con límites | Operaciones científicas bajo demanda y publicación pública |
| `frontend/` (WS5) | Mapa/nombre/RA-Dec → job → secuencia local; FOV/λ/capas y URL | Suma/resta, flags, modo embebido compacto y recorrido público |
| `docs/submission/` (WS6) | Demo pública, evidencia, fuentes, límites y entrega | Todos los puntos C01–C08 declarados con su estado real |
| `pipeline/errante/systems/`, `frontend/src/three/` (WS7) | Galería ilustrativa actual; migración P1 a modelos físicos | Mediciones WS3, incertidumbre/fuentes y compañeras confirmadas |

Los módulos de ampliación nuevos se crean cuando se implementa su tarea; no agregar carpetas vacías ni
funciones que aparenten estar disponibles. NEOSSat/CADC son recursos opcionales de comparación,
identificados por misión, no sustitutos de SPHEREx. WiseView es referencia de interacción.

## Construcción por etapas: comportamiento actual

`build_field(cfg, out, analyze=False)` publica PNGs, `field.json`, listas vacías de candidatos/objetos y
`manifest.json` sin llamar al análisis. La procedencia aclara que no se ejecutó detección ni cruce.
Un campo sin frames genera error y no se agrega al manifest como si hubiera datos.

`--analyze` ejecuta fuentes → linking → scoring → catálogo después de publicar el campo básico.
Si una etapa opcional falla, el comando informa el fallo y el campo básico sigue visible. Una lista vacía
con análisis no ejecutado no significa que se haya buscado y no se hayan encontrado objetos.

```bash
errante search --ra 269.4463 --dec 4.7665
errante build barnards-star               # primero: imágenes y metadatos
errante build barnards-star --analyze     # opcional; análisis todavía contiene stubs
errante validate --dir data/products
python scripts/dev.py web                                 # abrir ?dataset=real
```

**Estado actual:** búsqueda/cutouts/reproyección y selección por temporada están implementados. #17 aporta
los cinco campos reales, #19 las comparaciones y #31 fotometría por exposición. Las mediciones y su
interpretación/validación científica siguen siendo tareas separadas; la demo continúa siendo sintética.

## Coordenadas arbitrarias implementadas; publicación pendiente

La web estática actual sirve campos preconstruidos; es útil para desarrollo, demostración y caché.
**No cumple sola R03** para posiciones arbitrarias. El servicio WS4-5 y formulario/mapa WS5-7 están implementados y probados localmente;
falta elegir destino/URL y verificar el recorrido público (WS4-4/6). No hace falta hosting para uso local.

1. La UI acepta RA/Dec con unidades claras, valida rangos y muestra FOV; formato sexagesimal se normaliza
   a grados ICRS. C04 agrega elección pública del FOV dentro de límites del servidor.
2. El servidor valida y normaliza la solicitud; su clave de caché incluye posición, FOV, releases, filtros,
   selección temporal y versión de pipeline. No basta cachear por coordenadas.
3. Reutiliza un producto compatible o encola un job. Devuelve ID y estado; la UI muestra progreso y puede
   dejar de consultar. No se mantiene abierto un request de descarga/reproyección largo.
4. El worker ejecuta el pipeline de imágenes. El job distingue sin cobertura, fallo parcial y error del
   servicio. Debe publicar la misma estructura JSON/PNG que los campos curados.
5. Cuando termina, el visor abre el campo devuelto. Encontrar URIs sin generar una secuencia no cierra R03.

POST `/api/jobs` y GET `/api/jobs/{id}` usan contrato 0.3.0. El mapa Aladin/IRSA y el formulario comparten
ese flujo; Sesame/CfA resuelve nombres. El HiPS es un coadd estático; la secuencia usa exposiciones reales.
Productos servidos y construidos comparten raíz; SQLite serializa admisión y un supervisor posee el worker.
Batch y jobs comparten lock de publicación, validación PNG y manifest atómico. Límites y recuperación en
[backend/README.md](../backend/README.md), tipos/estados en [CONTRACT.md](CONTRACT.md).

## Consideraciones opcionales dentro del flujo (P1)

- **C01, releases:** consultar colecciones y versiones de forma configurable, preferir las recomendadas por
  IRSA, conservar procedencia y evitar reprocesados duplicados. Refrescar sin redesplegar la UI.
- **C02, bandas y espectros:** selector de detector/λ; coadds separados por detector y visita con máscara y
  pesos. Un coadd de detector es un producto de banda ancha, no una medición monocromática. El espectro se
  calcula desde FITS en una posición elegida aunque no haya un candidato detectado, con fechas y errores.
- **C03, aritmética:** suma/media y resta A−B después de alinear WCS y controlar unidades, PSF, fondo,
  cobertura y compatibilidad espectral. Conservar miembros y propagación de incertidumbre.
- **C04, FOV:** limitar área, píxeles, frames, concurrencia y descarga; mostrar costo estimado/progreso.
- **C05, contexto:** Gaia DR3 con propagación cuando exista astrometría; WISE con misión/banda/fecha visibles.
  Aladin es una capa de contexto, sin reemplazar el blink de observaciones SPHEREx.
- **C06, enlaces:** URL implementada `?mode=api&ra=<deg>&dec=<deg>&fov=<deg>&detector=<1..6>`; restaurar el estado
  al abrirla, y ofrecer modo embebido. El host debe permitir el iframe de prueba desde otro origen.
  `job` opcional retoma el polling; sin él no se construye al cargar. Modo compacto y prueba de iframe externo pendientes.
- **C07, calidad:** panel por frame con MJD/fecha, release, origen, detector, λ/ancho, fracción válida y flags;
  las flags deben tener significado y procedencia. Si falta una medida, mostrar desconocido.
- **C08, herramientas:** Astropy ya se usa para FITS/WCS; evaluar notebooks IRSA, Aladin y licencias antes
  de agregar dependencias. Ver el registro de recursos en DATA.md.

## Galería 3D integrada y migración a mediciones (WS7, P1)

Se conserva la ampliación importada: `SystemModel`, `Manifest.systems`, `errante systems`,
`GET /api/systems/{id}`, rutas `#/systems` y `#/system/<id>[/<body>]`. `demo` incluye seis modelos.
La migración a modelos físicos desde mediciones es P1 según VISION.md. Three.js se importa dinámicamente al abrir el visor 3D. Los cinco modelos de blancos usan parámetros
introducidos a mano y `verified=False`; el modelo orbital del demo es sintético. Ver VISION_3D.md.
Son ilustraciones educativas, no observaciones, inferencias 3D desde un punto luminoso ni cinco ensayos R05.
Verificar los valores y publicar sus fuentes es condición para presentarlos como datos medidos.

## Contrato y compatibilidad

Se mantiene `models.py` → `shared/schema/` → `frontend/src/api/types.ts` como contrato vigente.
Jobs/resolver usan **0.3.0**. La integración científica **0.4.0** (#53) agrega espectros/comparaciones,
preservando composites 0.3.1 (#39); schema y espejo TS sincronizados. Ver orden en CONTRACT.md.
La separación del build usa los campos actuales, sin otro cambio de schema.
WS4-10 coordina las próximas ampliaciones aditivas para cobertura/calidad, productos combinados y espectros en
posiciones arbitrarias. Cada cambio real requiere versión, schema, tipos TS y pruebas en el mismo PR.
No escribir campos propuestos en los JSON publicados hasta implementar su contrato.

### Servicio científico y caché (15/11/2026)

El mapa/campo solicita espectro sin candidato; el campo real selecciona entradas para comparar temporadas.
FastAPI valida los modelos compartidos y ejecuta WS1/WS2 en un proceso científico supervisado independiente
del worker de jobs (un cupo por instancia, 140 s, 512 MiB staging, log 1 MiB). Peticiones idénticas comparten
trabajo; cancelar la espera del cliente no libera un cupo aún ocupado. No se agregó otro sistema de colas.

La caché de jobs usa `display-mask-v4` y SHA-256 de código/dependencias del procesamiento; no reutiliza
renders anteriores cuando cambia WS2. La caché científica incluye también inputs/campo/época y adaptador.
TTL memoria/disco; PNG ausente/dañado fuerza regeneración. Análisis se publican con lock/rename atómico en
`data/analyses/{sha256}`, sin mutar campos ni manifest. Directorios de trabajo/cache permanecen privados.
Límites de disco/deadline son supervisados; cuotas duras pertenecen al entorno. Configuración y errores:
[backend/README.md](../backend/README.md). Uso local no necesita contratar hosting.

El cubo mide brillo superficial estático sin errores; L2 mide flujo de apertura por exposición con flags,
error y cielo local. La UI separa unidades, conserva negativos/huecos y advierte mezcla temporal/espectral.
Las comparaciones son medias ponderadas y restas escaladas por detector, con procedencia y limitaciones;
no afirman variabilidad ni reconstruyen por sí solas un sistema físico 3D.

## Hitos y dependencias

| Hito | Resultado verificable | Depende de |
|---|---|---|
| I0 (existente) | Demo sintética etiquetada; contratos, backend de lectura y visor | Ninguno |
| I1 (P0) | Un campo SPHEREx real alineado, visible sin detección automática | WS1-1/2/3/4, WS2-1/2 |
| I2 (P0) | Ingreso RA/Dec → construcción/caché → animación en URL pública | WS4-2/5/6, WS5-1/2/3/7, WS6-3 |
| I3 (P0) | Cinco ensayos documentados, incluidos RW Aurigae y R Draconis | WS1-5/6, WS3-3/9, WS2-8, VALIDATION.md |
| I4 (P1) | C01–C08 implementados con evidencia o con estado pendiente explícito | Tareas de REQUIREMENTS.md |
| I5 (P2) | Detección, JPL, distancias, límites e historia de Planeta X | Campo real y MVP estable |

La aceptación de un hito se basa en comportamiento y evidencia, no en cantidad de módulos creados.

## Restricciones verificadas (2026-11-14)

Medidas en vivo; detalle en [`DATA.md`](DATA.md) §3.0.

- **IRSA no envía CORS** → el navegador no puede buscar frames ni bajar cutouts: el flujo RA/Dec → video necesita
  el backend como proxy (con caché en disco). **S3 sí tiene CORS y `Range`**: los píxeles pueden leerse por rangos
  (desde el backend o, con más trabajo, desde el navegador).
- **Búsqueda:** SIA2 en VOTable (1–4 s) mejor que TAP (8–19 s). **Píxeles:** lectura por Range en S3 (~1 s por
  frame a 5′) mejor que cutouts de IRSA (~4 MB y 4–15 s cada uno). Cutouts = fallback.
- **El "video" se arma por temporada × detector:** los objetivos tienen ~250–460 exposiciones en 3–4 temporadas
  (R Dra ~2500), cada exposición en otra λ, y se mueven solo 1–2 px en total.
- **Plan B de la demo:** campos precomputados de los 5 objetivos servidos estáticos si IRSA o S3 fallan.
- **Hosting:** ofertas gratuitas de Space Apps (dominio GoDaddy, Google Cloud/Firebase, Azure) y para qué
  podrían servirnos: [`HOSTING_OFFERS.md`](HOSTING_OFFERS.md).

