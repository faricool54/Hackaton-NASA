# AGENTS.md — reglas para agentes (Codex, Claude Code y humanos)

> Codex lee este archivo automáticamente. Claude Code lo lee vía `CLAUDE.md`.
>
> **Antes de empezar:** leé [`docs/PLAN.md`](docs/PLAN.md) (prioridades vigentes: P0 / P1 / P2 / DROP) + tu
> `tasks/WSx-*.md`. Si algo de tu `tasks/` contradice a `PLAN.md`, gana `PLAN.md`. Después leé esto completo
> ANTES de tocar código.

## Qué estamos construyendo

NASA Space Apps Challenge 2026, reto **"Planet X and SPHEREx"** (texto oficial en [`docs/CHALLENGE.md`](docs/CHALLENGE.md)).
El enunciado pide una **herramienta web pública** donde el usuario **ingresa RA/Dec** de un parche de cielo y ve
**la serie de imágenes de NASA SPHEREx de ese parche como un pequeño video**, para notar lo que cambia con el
tiempo. Hay que probarla en 5 objetivos: **Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis**.

El nombre del producto, la idea con sus palabras y los diferenciadores **los decide y escribe el equipo**
(regla de SI, ver [`docs/KICKOFF.md`](docs/KICKOFF.md)). `errante` es solo el nombre técnico del paquete Python.

Contexto obligatorio: [`docs/PLAN.md`](docs/PLAN.md) (prioridades) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
(cómo encaja todo) · [`docs/CONTRACT.md`](docs/CONTRACT.md) (formato de datos y API) · [`docs/DATA.md`](docs/DATA.md)
(hechos verificados sobre SPHEREx) · [`docs/SCIENCE.md`](docs/SCIENCE.md) (física y encuadre honesto).

## Mapa del repo y dueños (única fuente de ownership)

| Dueño | Rutas y responsabilidades |
|---|---|
| **WS1 Datos** | `pipeline/errante/data/**`, `pipeline/errante/settings.py`, `pipeline/tests/test_data_*.py`, `test_network.py`, `pipeline/tests/fixtures/ws1/**`, `data/index/**`, `docs/DATA.md` (dueño; los demás le pasan hechos o agregan en la sección "Notas de otros WS" al final), `cli.py search` |
| **WS2 Imagen** | `pipeline/errante/imaging/**`, `pipeline/errante/detect/**`, `pipeline/errante/build.py` (dueño, coordina con WS1), `pipeline/errante/synthetic.py`, `data/products/**` (golden fields), `cli.py build/demo`, tests `test_imaging_*` / `test_detect_*` / `test_build_*` / `test_synthetic.py` / `test_grid_motion_flags.py`, `pipeline/tests/fixtures/ws2/**` |
| **WS3 Ciencia/objetivos** | `pipeline/errante/science/**`, `pipeline/errante/config/**`, `docs/SCIENCE.md`, `pipeline/tests/test_science_*.py`; además es dueño del PR de contrato 0.3.0 |
| **CONTRATO** (solo vía PR `contract:`) | `pipeline/errante/models.py`, `pipeline/errante/products.py`, `shared/schema/**`, `frontend/src/api/types.ts`, `data/demo/**` (se regenera con `python scripts/dev.py demo`), `pipeline/tests/test_contract.py` |
| **WS4 Backend+deploy+coordinación** | `backend/**`, `.github/**`, `Makefile`, `scripts/**`, config de deploy; coordina `main` (mergea `contract:`/`chore:`, revierte si se rompe; los PR de carpeta propia los mergea su autor) |
| **WS5 Frontend** | `frontend/**` (salvo `types.ts` → contrato; textos largos de About/hero coordinados con WS6) |
| **WS6 Entrega** | `docs/submission/**`, `docs/CHALLENGE.md`, sección "Use of SI" y créditos del README |
| **WS7 Sistemas 3D** (rama `claude/ecstatic-turing-rcu8jq`, **PR pendiente**; prioridad a decidir en el kickoff ([PLAN §6](docs/PLAN.md))) | `pipeline/errante/systems/**`, `pipeline/tests/test_systems.py`, `frontend/src/three/**`, `frontend/src/components/{SystemViewer,BodyPanel}.tsx`, `frontend/src/pages/{SystemsPage,SystemPage}.tsx`, `docs/VISION_3D.md` |
| **Coordinación** (quien coordine, sugerido WS4) | `AGENTS.md`, `CLAUDE.md`, `README.md` (resto), `docs/PLAN.md`, `docs/KICKOFF.md`, `docs/TEAM.md`, `docs/WORKFLOW.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACT.md`, `docs/REVIEW-*.md`, `tasks/README.md` |

Cada WS marca casillas **solo en su propio** `tasks/WSx-*.md`. Quién es cada WS: [`docs/TEAM.md`](docs/TEAM.md).
¿De quién es un archivo? `python scripts/owners.py --who <ruta>`. Protocolo para trabajar en paralelo sin pisarse:
[`docs/COLLABORATION.md`](docs/COLLABORATION.md).

## Reglas de oro

1. **El objetivo central es "RA/Dec → video".** Todo P0 sirve a eso: coordenadas (o uno de los 5 objetivos) →
   serie de imágenes SPHEREx reales del parche. **No te desvíes a lo DROP** de `PLAN.md` §4 (detección/linking
   automático, inyección-recuperación, página de límites, shift-and-stack, región del Planeta Nueve, distancia
   por velocidad, reporte de candidato). Si no es P0/P1 de tu WS, preguntá antes de hacerlo.
2. **Quedate en tu carpeta.** Solo editá rutas de tu WS (tabla de arriba). Si necesitás algo de otra, dejá un
   `TODO(WSx): ...` o pedilo en el chat del equipo / issue. Nada de "arreglos de paso" en carpetas ajenas.
   `docs/DATA.md` lo edita **WS1**: los demás le pasan el hecho o lo agregan en "Notas de otros WS" al final.
3. **El contrato es sagrado.** `models.py` es la fuente de verdad. Cambiarlo = PR titulado `contract: ...`,
   `python scripts/dev.py schema`, `types.ts` en el mismo PR, subir `SCHEMA_VERSION`, avisar a WS2/WS4/WS5.
   Preferí **agregar campos opcionales**. **No regeneres `data/demo/`** salvo en un PR de contrato.
4. **Nunca hagas pasar datos falsos por reales.** Lo sintético lleva `synthetic: true` y la UI muestra el badge
   "SYNTHETIC DATA". Nada de imágenes de otras misiones presentadas como SPHEREx.
5. **Honestidad científica.** No afirmamos descubrir el Planeta X ni "objetos nuevos". Los objetivos se mueven
   **1–2 píxeles** en todos los datos disponibles (Barnard 1.86 px, WISE 0855 1.36 px, Eps Ind B 1.10 px): no lo
   exageres en textos ni en el video. Ver `docs/SCIENCE.md`.
6. **No inventes datos de servicios externos.** Tablas, endpoints, coordenadas, bits de flags, versiones:
   verificalos contra la fuente (o un archivo real) y anotalos (ver regla 2). Si no pudiste verificar, decilo.
   **CDS Estrasburgo está degradado desde el 2026-11-09** (SIMBAD, VizieR y alasky dan 404): usá espejos —
   CfA (SIMBAD/VizieR/Sesame), IRSA o ESA (HiPS), jsdelivr (Aladin Lite 3.8.2). Nunca rutas ni versiones de
   pipeline armadas a mano: usá la key/URI que devuelve la búsqueda.
7. **Uso de IA ("SI" en las reglas oficiales).** Permitida para código, pero la **idea** de cómo resolver el reto,
   el nombre y los textos de producto los escribe el equipo. Commits hechos con agentes llevan el trailer
   `Co-Authored-By:`. **No generes imágenes ni videos con IA** sin marca de agua visible. **Nada de branding
   NASA** (logos, banderas, identificadores/parches de misión); créditos de datos solo en texto.
8. **Tiempo = `MJD-AVG`.** `Frame.mjd` es la **mitad** de la exposición (`MJD-AVG` del header, o
   `(t_min+t_max)/2` de la búsqueda). `MJD-OBS` es el **inicio**: no lo uses como tiempo del frame.
9. **`python scripts/dev.py check` antes de cada push.** Es exactamente lo que corre CI.
10. **Un PR por tarea**, rama `wsN/descripcion-corta`, PR a `main`, squash merge, CI verde. Actualizá con
    `git pull origin main` (merge); nunca `push --force`, `git add -A` ni commits en `main`.
    Ver [`docs/WORKFLOW.md`](docs/WORKFLOW.md).
11. **Nada pesado al repo.** FITS y descargas van a `data/cache/` (ignorado). Productos reales en el repo: solo
    golden fields livianos (< ~20 MB en total) y el índice SIA de los 5 objetivos.
12. **Sin secretos.** Ninguna API que usamos requiere clave. Si algo la pide, consultá antes.
13. **Stubs: respetá la firma o cambiala con cuidado.** Si no alcanza (pasa con varias, ver `PLAN.md` §4),
    cambiala en tu módulo y actualizá a quien la llama, o coordiná si es de otro WS.

## Convenciones

- Código, identificadores, comentarios y textos de la UI: **inglés** (la entrega es internacional).
  Docs del equipo y tareas: **español**.
- Python ≥ 3.11 (CI usa 3.12), `ruff` (`ruff.toml`), tests con `pytest`. Librerías pesadas (scipy, photutils,
  reproject, astroquery, pyvo) se importan **dentro de las funciones** (extra `science`). El camino de `/api/view`
  debería andar solo con numpy + astropy + requests.
- Tests que usan internet: `@pytest.mark.network` (se saltean salvo `ERRANTE_NETWORK_TESTS=1`). CI nunca le
  pega a IRSA ni a S3: mockeá.
- TypeScript estricto, React con componentes funcionales, sin librerías nuevas salvo que aporten mucho
  (justificalo en el PR).
- Coordenadas: ICRS en grados. Tiempos: MJD = `MJD-AVG` (regla 8). Píxeles en el contrato: **convención PNG**
  (origen arriba-izquierda, y hacia abajo, norte arriba, este a la izquierda).
- Glosario (fijo en el contrato): **exposición** (1 archivo, 1 detector) · **visita** (exposiciones separadas
  < 6 h) · **temporada / pasada** (bloques separados > 20 días; SPHEREx vuelve a cada punto cada ~6 meses).
- Colecciones SPHEREx (`spherex_dr1`, `spherex_qr3`, …) = **configuración**, nunca constantes en el código.
- Commits: `wsN: verbo + qué` (ej. `ws1: implement SIA search with disk cache`) + trailer `Co-Authored-By:` si
  lo escribió un agente.

## Comandos

```bash
python scripts/dev.py setup          # .venv + pipeline/backend (editable) + npm ci   (Windows: py scripts/dev.py ...)
python scripts/dev.py setup-science  # libs científicas pesadas (WS1/WS2/WS3)
python scripts/dev.py doctor         # versiones y qué falta
python scripts/dev.py demo           # regenera data/demo (SOLO en PR de contrato)
python scripts/dev.py schema         # regenera shared/schema desde models.py
python scripts/dev.py validate       # valida data/demo (y data/products si existe)
python scripts/dev.py api            # backend en :8000 (docs en /docs); otro puerto: API_PORT=8001
python scripts/dev.py web            # frontend en :5173 (lee data/demo por defecto)
python scripts/dev.py test           # test-py + test-web
python scripts/dev.py lint           # ruff check + format --check   (fmt = arreglar)
python scripts/dev.py owners         # ¿mi rama solo toca archivos de mi WS?
python scripts/dev.py check          # lo mismo que CI (+ owners): correr antes de cada push
errante --help                       # CLI del pipeline: demo | schema | validate | search | build
```

En Mac/Linux `make check` (y el resto) sigue funcionando: el Makefile es un wrapper opcional de `dev.py`.
En Windows usá `py` (no `python3`, que puede ser el de MSYS2) y en PowerShell 5.1 no hay `&&`: corré los
comandos por separado.

## Cuando termines una tarea

1. `python scripts/dev.py check` en verde (y si tocaste la UI, la miraste en el navegador, desktop y celular).
2. Hechos nuevos sobre datos/servicios: si sos WS1, en `docs/DATA.md`; si no, en "Notas de otros WS" al final de
   `docs/DATA.md` (o pasáselos a WS1). Siempre con fecha y estado (✅ verificado / 📄 según documentación / ❓ abierto).
3. Marcá la casilla en tu `tasks/WSx-*.md` (solo tu archivo) con el link al PR.
4. Commit `wsN: ...` con trailer `Co-Authored-By:` si lo hizo un agente → PR a `main` con la plantilla, título
   `wsN: ...`. Contá qué probaste y con qué datos (reales o demo).
