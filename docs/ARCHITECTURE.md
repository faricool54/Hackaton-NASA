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
| `backend/` (WS4) | Servir productos y conectar consulta → construcción de campo | Jobs de coordenadas arbitrarias, límites de recursos y operaciones científicas bajo demanda |
| `frontend/` (WS5) | RA/Dec → secuencia temporal pública | FOV, λ, suma/resta, flags, capas, URL restaurable y modo embebido |
| `docs/submission/` (WS6) | Demo pública, evidencia, fuentes, límites y entrega | Todos los puntos C01–C08 declarados con su estado real |
| `pipeline/errante/systems/`, `frontend/src/three/` (WS7) | Galería 3D opcional (P2), fichas y modelos animados | Parámetros verificados, enlaces a observaciones reales cuando existan |

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
make web                                 # abrir ?dataset=real
```

**Bloqueo actual:** IRSA search, cutouts y reproyección siguen sin implementar. Separar las etapas elimina
la dependencia del análisis, pero no convierte en reales los datos demo ni completa por sí solo R02.

## Coordenadas arbitrarias y despliegue público: diseño pendiente

La web estática actual sirve campos preconstruidos; es útil para desarrollo, demostración y caché.
**No cumple sola R03** para posiciones arbitrarias. El despliegue completo necesita WS4-5 (servicio de
construcción o equivalente verificable), además de WS5-7 (formulario).

1. La UI acepta RA/Dec con unidades claras, valida rangos y muestra FOV; formato sexagesimal se normaliza
   a grados ICRS. C04 agrega elección pública del FOV dentro de límites del servidor.
2. El servidor valida y normaliza la solicitud; su clave de caché incluye posición, FOV, releases, filtros,
   selección temporal y versión de pipeline. No basta cachear por coordenadas.
3. Reutiliza un producto compatible o encola un job. Devuelve ID y estado; la UI muestra progreso y puede
   dejar de consultar. No se mantiene abierto un request de descarga/reproyección largo.
4. El worker ejecuta el pipeline de imágenes. El job distingue sin cobertura, fallo parcial y error del
   servicio. Debe publicar la misma estructura JSON/PNG que los campos curados.
5. Cuando termina, el visor abre el campo devuelto. Encontrar URIs sin generar una secuencia no cierra R03.

Rutas de jobs, estados y campos de request/respuesta son **propuestas para WS4-10**, no endpoints existentes.
El contrato actual y la API existente están en [CONTRACT.md](CONTRACT.md).

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
- **C06, enlaces:** URL propuesta `?mode=api&ra=<deg>&dec=<deg>&fov=<deg>&detector=<1..6>`; restaurar el estado
  al abrirla, y ofrecer modo embebido. El host debe permitir el iframe de prueba desde otro origen.
  Es una interfaz planificada; actualmente solo se interpretan `mode` y `dataset` y rutas hash por campo.
- **C07, calidad:** panel por frame con MJD/fecha, release, origen, detector, λ/ancho, fracción válida y flags;
  las flags deben tener significado y procedencia. Si falta una medida, mostrar desconocido.
- **C08, herramientas:** Astropy ya se usa para FITS/WCS; evaluar notebooks IRSA, Aladin y licencias antes
  de agregar dependencias. Ver el registro de recursos en DATA.md.

## Galería 3D integrada (WS7, P2)

Se conserva la ampliación importada: `SystemModel`, `Manifest.systems`, `errante systems`,
`GET /api/systems/{id}`, rutas `#/systems` y `#/system/<id>[/<body>]`. `demo` incluye seis modelos.
Three.js se importa dinámicamente al abrir el visor 3D. Los cinco modelos de blancos usan parámetros
introducidos a mano y `verified=False`; el modelo orbital del demo es sintético. Ver VISION_3D.md.
Son ilustraciones educativas, no observaciones, inferencias 3D desde un punto luminoso ni cinco ensayos R05.
Verificar los valores y publicar sus fuentes es condición para presentarlos como datos medidos.

## Contrato y compatibilidad

Se mantiene `models.py` → `shared/schema/` → `frontend/src/api/types.ts` como contrato vigente.
La versión integrada es **0.2.0**, ampliación aditiva de sistemas 3D con schema y espejo TS importados juntos.
La separación del build usa los campos actuales, sin otro cambio de schema.
WS4-10 coordina ampliaciones aditivas para jobs, cobertura/calidad, productos combinados y espectros en
posiciones arbitrarias. Cada cambio real requiere versión, schema, tipos TS y pruebas en el mismo PR.
No escribir campos propuestos en los JSON publicados hasta implementar su contrato.

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
