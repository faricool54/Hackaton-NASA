# Plan realineado al enunciado oficial (2026-11-14)

> **Estado: PROPUESTA TÉCNICA para validar en el kickoff** (ver [`KICKOFF.md`](KICKOFF.md)).
> La escribió un asistente de IA (Claude) después de revisar el esqueleto contra el
> [texto oficial del reto](CHALLENGE.md) y verificar en vivo IRSA/S3. Las reglas de Space Apps dicen que la IA
> **no** debe usarse para idear la solución: el equipo tiene que discutir, decidir y escribir con sus propias
> palabras la idea, el nombre y los diferenciadores. Este documento es insumo técnico, no la decisión.
> Hallazgos y evidencia completos: [`REVIEW-2026-11-14.md`](REVIEW-2026-11-14.md).

## 1. Qué cambia y por qué (en una línea cada uno)

1. **El flujo principal pasa a ser "RA/Dec → video"**: el usuario ingresa coordenadas (o elige uno de los 5
   objetivos oficiales) y ve la serie de imágenes SPHEREx de ese parche. Es el objetivo literal del enunciado;
   en el esqueleto estaba como P1/P2.
2. **Backend obligatorio**: IRSA (TAP, SIA, cutouts) **no envía CORS** (verificado). El navegador no puede
   buscar frames solo. El backend FastAPI existente pasa a ser proxy + procesador con caché.
3. **Píxeles vía lectura por rangos HTTP en S3** (bucket público, con CORS y `Range`): ~0.4 MB / ~1 s por frame
   a 5′, contra ~4 MB / 4–15 s de un cutout de IRSA (que arrastra la tabla EPSF entera). Cutout IRSA = fallback.
4. **El "video" se arma por temporada × detector (coadds)**, no por exposición: dentro de una temporada cada
   exposición mide otra λ (filtro variable) y la estrella "parpadea" sin cambiar. El enunciado sugiere
   co-sumar por detector. Exposiciones individuales = modo secundario (asteroides dentro de una temporada).
5. **Los movimientos son de 1–2 píxeles** en toda la línea de base (Barnard 1.86 px, WISE 0855 1.36 px,
   Eps Ind B 1.10 px): sin **zoom pixelado, retícula, posición predicha y resta de épocas** no se ve nada.
6. **Los 5 objetivos oficiales** (Barnard, Eps Ind B, WISE 0855, RW Aur, R Dra) son atajos en la UI y
   **"golden fields" precomputados** (plan B si IRSA falla durante la demo). Los 5 ya están en `fields.toml` con centros propagados; faltan los
   golden fields construidos con datos reales.
7. **Variables (RW Aur, R Dra) no se mueven: cambian de brillo.** Método honesto: comparar coadds por
   temporada (cada temporada cubre todas las λ del detector) y espectros por temporada.
8. **Se baja a P2/DROP lo que el enunciado no pide**: detección/linking automático de asteroides,
   inyección-recuperación, página de límites, shift-and-stack, región del Planeta Nueve, distancia por
   velocidad, reporte de candidato. Planeta X queda como **motivación narrativa** (el título del reto).
9. **Reglas de entrega**: video **≤ 30 s** (o ≤ 7 slides), subtítulos en inglés si se habla otro idioma,
   declaración de uso de IA ("SI"), sin branding NASA, links públicos sin login. Ver [`CHALLENGE.md`](CHALLENGE.md) §3.
10. **Deadline: domingo 15/11 23:59 hora del Local Event** (confirmar zona horaria con el/la Local Lead).

## 2. Arquitectura objetivo

```
Usuario ──?ra=..&dec=..&fov=..&det=..──▶ Frontend (Vite/React, estático)
                                            │  /api/view, /api/photometry           (sin backend → golden fields)
                                            ▼
                                   Backend FastAPI (Python, caché en disco)
             ┌──────────────────────────────┼──────────────────────────────────┐
     WS1 search_frames                 WS1 read_patch                     WS2 imaging
  SIA2 (VOTable) sobre colecciones    lectura por Range en S3 de las     reproyección a grilla común
  configurables: spherex_dr1,         filas del recorte (IMAGE,          norte-arriba → coadd por
  spherex_qr3 (+ *_deep opcional)     VARIANCE, ZODI); fallback:         (temporada × detector) →
  fallback TAP; caché por consulta    cutout IBE de IRSA                 diferencia A−B → PNG + stretch común
             └──────────────────────────────┴──────────────────────────────────┘
                                            ▼
                     Field (contrato) efímero con id determinista + PNGs en data/cache/views/
```

- **`GET /api/view?ra&dec&fov_arcmin&det&group=season|exposure`** → `Field` (mismo contrato que los campos
  curados, así el `BlinkViewer` se reutiliza). Id determinista que cumple el slug de `Field.id` (sin puntos), p. ej. `v-2694462-p047687-f8-d3-season`
  (RA×10⁴, `p`/`m` + |Dec|×10⁴, FOV en arcmin, detector, agrupación). Fuente de datos en la URL del frontend:
  `?source=api|static` (`mode` queda para el viewer: `blink|diff`).
  Primera llamada: segundos a ~1 min según FOV/detectores; segunda: instantánea (caché).
- **`GET /api/photometry?ra&dec`** (P1) → puntos `{frame, mjd, season, detector, λ, flujo, error, flags}`:
  sirve para el espectro al vuelo y para la curva de luz de las variables.
- **Golden fields**: `errante build <target>` usa **la misma función** (`build_patch(ra, dec, fov, …)`) y
  escribe en `data/products/`. El frontend estático los sirve sin backend (deploy gratis + plan B).
- **Overlays** (P1): Aladin Lite **3.8.2 desde jsdelivr** (no desde CDS), HiPS desde espejos de IRSA/ESA,
  Gaia DR3 vía VizieR de **CfA** (CDS Estrasburgo está degradado desde el 2026-11-09: alasky, VizieR y SIMBAD
  de Estrasburgo dan 404). Posición predicha por movimiento propio en cada época.
- **Nuevos releases**: las colecciones son configuración (`ERRANTE_COLLECTIONS`), nunca rutas ni versiones de
  pipeline hardcodeadas (varían por semana y detector): siempre usar la key/URI que devuelve la búsqueda.

## 3. Contrato 0.3.0 (propuesta, **solo campos opcionales**, un único PR `contract:` temprano)

> Se numera **0.3.0** porque la rama WS7 (§6) ya usa **0.2.0** para `SystemModel`. Si WS7 no entra, igual
> se usa 0.3.0 (saltear un número no rompe nada).

Dueño del PR: quien coordine el contrato (sugerido WS3), revisan WS2, WS4 y WS5. Hasta que se mergee, todos
trabajan contra 0.1.0 + `data/demo`.

| Modelo | Campo nuevo (opcional) | Para qué |
|---|---|---|
| `Frame` | `kind: "exposure" \| "coadd" \| "difference"` (default `"exposure"`) | coadds y restas en el mismo video |
| `Frame` | `season: int`, `mjd_start`, `mjd_end`, `n_inputs`, `input_ids: list[str]` | agrupar por temporada, mostrar Δt real |
| `Frame` | `wavelength_min_um`, `wavelength_max_um` | rango de λ de un coadd |
| `Frame` | `flag_fractions: dict[str, float]`, `flags_at_target: list[str]` | metadata de contaminación (consideración oficial) |
| `Field` | `query: {ra, dec, fov_arcmin, detectors, group, collections}` | campos efímeros de `/api/view`, URL embebible |
| `Field` | `target: {name, ra, dec, ref_epoch, pm_ra_cosdec_mas_yr, pm_dec_mas_yr, parallax_mas, source}` | posición predicha por época |
| `KnownObject` | `pm_*`, `parallax_mas`, `ref_epoch`, `mag`, `mag_band`; `MatchSource += gaia_dr3, catwise2020, simbad` | overlays de estrellas con movimiento propio |
| `SpectrumPoint` | `mjd`, `season`, `detector`, `flags` | espectro por temporada, curva de luz |
| `Release` | pasar de `Literal` a `str` con patrón `^((dr\|qr)\d+(_deep)?\|synthetic)$` | que un release nuevo no rompa la validación |

Además: documentar `Frame.mjd` = **mitad de la exposición** (`MJD-AVG`; `MJD-OBS` es el *inicio*).
Glosario fijo: **exposición** (1 archivo, 1 detector) · **visita** (exposiciones separadas < 6 h) ·
**temporada / pasada** (bloques separados > 30 días; SPHEREx vuelve a cada punto cada ~6 meses). Con 20 d algunos objetivos
se parten en bloques chicos (ver `docs/DATA.md` §4.2); el umbral final se fija en el PR de contrato.

## 4. Prioridades por workstream (reemplazan las de `tasks/`)

**P0 = sin esto no hay demo · P1 = lo que nos diferencia · P2 = si sobra tiempo · DROP = no hacer.**

| WS | P0 | P1 | P2 / DROP |
|---|---|---|---|
| **WS1 Datos** | `search_frames` con SIA2 (VOTable) + TAP fallback, colecciones configurables, dedupe, `group_seasons`; `read_patch` por Range en S3 (IMAGE/VARIANCE/ZODI) con caché y ≤16 conexiones; fallback cutout IBE (≤6 hilos, reintentos, 422 = sin solape); índice SIA de los 5 objetivos guardado en el repo; corregir `docs/DATA.md` | `wavelength_at` (WCS-WAVE leyendo `TDIM`, la grilla depende del detector); FLAGS por Range (RICE por fila) | DROP: fallback escaneando semanas en S3 |
| **WS2 Imagen** | `reproject_to_grid` → `GridFrame(data−ZODI, variance, flags, coverage)` con numpy+astropy; `coadd` ponderado 1/VAR por (temporada, detector); `difference(a, b)`; stretch común por detector; PNG con alfa; `build_patch` que escribe el campo aunque no haya detección | suma de épocas elegidas; capa/porcentajes de flags; falso color D1/D3/D6 | P2: `find_sources` solo para centroidar el objetivo; DROP: linking/scoring, inyección, shift-and-stack |
| **WS3 Ciencia / objetivos** | los 5 objetivos en `fields.toml` con posición propagada a la época de los datos + pm/plx/época guardados en el repo (no depender de SIMBAD en vivo); tabla de movimiento esperado; método de variabilidad (coadds y espectros por temporada); PR de contrato 0.3.0; corregir textos científicos de la UI | `/api/photometry` + espectro al vuelo; overlay de asteroides conocidos (SkyBoT) | DROP: distancia por velocidad, región del Planeta Nueve, `detectability` |
| **WS4 Backend + deploy** | `/api/view` (+ caché en disco, timeouts, 502/504 JSON, semáforo hacia IRSA); validar `field_id` (path traversal); mockear funciones en tests; deploy público del backend (US-East, con disco) y del frontend; CORS al dominio del frontend | `/api/photometry`; proxy de catálogos (Gaia/CatWISE) si hace falta | DROP: `/api/limits` |
| **WS5 Frontend** | caja RA/Dec (decimal, sexagesimal, nombre vía Sesame CfA) + 5 chips de objetivos + FOV; estado en la query `?ra&dec&fov&det&mode&embed=1`; un detector por defecto; precarga; zoom pixelado ×8, retícula, posición predicha; modo Blink / Diferencia; tira de metadata por frame; textos corregidos | Aladin Lite (jsdelivr 3.8.2 + HiPS IRSA) con overlay Gaia; click → espectro; curva de luz | P2: GIF, falso color; DROP: página de límites, reporte de candidato |
| **WS6 Entrega** | idea/nombre/tagline escritos por el equipo; video ≤ 30 s con plantilla oficial + subtítulos en inglés; deck ≤ 7 slides de respaldo; `CHECKLIST` y `PROJECT.md` completos; sección "Use of SI" en README; repo público o URL del sitio; enviar con margen | prueba con 3 personas ajenas | — |

**Equipo de 5** (logins del repo: BenjaminPondal, DankoLiv, faricool54, rpccp, V0id47 — asignar en el
kickoff): WS1 · WS2 · WS3 (+ contrato + parte de WS6) · WS4 (+ deploy + coordinación de `main`) · WS5.
WS6 se reparte: textos y video entre WS3 y WS5 al final; el formulario lo carga quien coordina.

## 5. Cronograma (hora local UTC−3; **confirmar la zona del Local Event**)

| Cuándo | Hito | Criterio |
|---|---|---|
| Sáb 12:00–12:30 | **Kickoff** | asignaciones en `TEAM.md`, idea/nombre por el equipo, alcance congelado |
| Sáb 13:00 | Todos con `python scripts/dev.py setup && python scripts/dev.py web` andando | |
| Sáb 15:00 | Contrato 0.3.0 mergeado · `search_frames` real · lectura S3 de Barnard por CLI | |
| Sáb 20:00 | **I1 – vertical slice real**: `/api/view` de Barnard (1 detector, por temporada) se ve en el frontend | |
| Dom 08:00 | **I2**: los 5 objetivos con coadds + diferencia + posición predicha; golden fields construidos | |
| Dom 12:00 | **Deploy público** (frontend + backend) probado en incógnito y celular | |
| Dom 17:00 | **Feature freeze** (solo bugs) | |
| Dom 17:00–19:30 | Video ≤ 30 s, deck ≤ 7 slides, formulario completo | |
| Dom 20:00 | **Submit for Judging** (se puede reenviar hasta 23:59) | |

Sync de 10 min cada ~4 h. Cualquier cambio de alcance se anota acá.

## 6. WS7 "Sistemas 3D" (apareció hoy en una rama, sin PR)

Un integrante subió `claude/ecstatic-turing-rcu8jq` (CI verde): modelos 3D (three.js) de los sistemas de los
5 objetivos, órbitas animadas y fichas por cuerpo, ver `docs/VISION_3D.md` y `tasks/WS7-3d-systems.md` **en esa
rama**. Toca el contrato (lo sube a **0.2.0**: `SystemModel`, `Manifest.systems`), `products.py`, `cli.py`,
el frontend de WS5, el backend de WS4 y docs de coordinación: la guardia `owners` marca 34 archivos ajenos.

**Decisión del equipo en el kickoff** (no técnica): ¿entra, con qué prioridad y quién la sigue?
Datos para decidir: el enunciado no pide 3D; el criterio *Relevance* premia resolver el objetivo central; quedan
~36 h para 5 personas. Si entra, conviene **mergearla temprano** (cambia el contrato) como **un PR**
`contract: add SystemModel (WS7, 0.2.0)` revisado por WS5 y quien coordina, y que WS7 no siga tocando
archivos de WS5/WS4 sin avisar. Cómo integrarla con `main` sin choques: `docs/COLLABORATION.md` §7.

