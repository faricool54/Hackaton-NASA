# frontend/ — Vite + React + TypeScript · WS5

```bash
npm ci
npm run dev        # http://localhost:5173 (copia ../data/demo y ../data/products a public/data antes de arrancar)
npm run build      # typecheck + build estático en dist/
npm test           # vitest
```

## Modos de datos

| Parámetro | Valores | Default |
|---|---|---|
| `?dataset=` / `VITE_DATASET` | `demo` (sintético) · `real` (data/products) | `demo` |
| `?mode=` / `VITE_DATA_MODE` | `static` (archivos en public/data) · `api` (backend) | `static` |
| `VITE_API_BASE` | URL del backend | `http://localhost:8000` |
| `VITE_BASE` | sub-ruta de deploy (ej. `/Hackaton-NASA/` en GitHub Pages) | `/` |

Ver `.env.example`.

## Mapa → posición → imágenes reales

El home carga Aladin Lite 3.8.2 bajo demanda desde jsdelivr en un iframe que libera su contexto WebGL al
salir. SPHEREx DR1 HiPS (IRSA) es un **coadd estático**, no una serie temporal. El selector usa las λ del
`properties` de IRSA y `setFrequency` (RECON_SPHEREX §5.4): se omiten los planos 0 (problema de sufijo
Aladin/IRSA), 50 y 51 (dicroicos vacíos). Arranca en 4.600 µm. AllWISE W4/W2/W1 de ESA es una capa de
contexto opcional identificada como otra misión/época. Logo/créditos Aladin conservados.

Para posiciones arbitrarias instalar el backend con extras científicos y arrancarlo con
`ERRANTE_ENABLE_JOBS=1` (PowerShell: `$env:ERRANTE_ENABLE_JOBS='1'`; luego `python scripts/dev.py api`).
Ejecutar el frontend y abrir `?mode=api`. `VITE_API_BASE` debe apuntar a ese backend y su CORS debe admitir
el origen completo del frontend. No hace falta hosting para usarlo localmente.

El formulario admite RA/Dec ICRS en grados o HH:MM:SS / ±DD:MM:SS, nombre por Sesame/CfA, FOV 0.01–0.5°,
un detector y hasta 40 frames. Los cinco presets proceden de `fields.toml` (astrometría propagada a la época
media; fuentes/fecha en `src/api/showcase.ts`); no certifican R05. Un nombre resuelto puede referir una época
más antigua: para blancos de alto movimiento propio usar los presets propagados.

Click en mapa y formulario comparten POST `/api/jobs`, polling GET, errores/sin cobertura/reintento y visor.
El contrato compartido es 0.3.0. No se envían solicitudes de build desde el modo estático. Cambiar de posición
o salir detiene la observación local; no cancela un build del servidor. “Stop watching” y “Resume watching”
lo explican; un timeout/error de red no dispara otra solicitud automáticamente.

Enlaces `?mode=api&ra=...&dec=...&fov=...&detector=...&job=...#/` conservan subruta/dataset y restauran el
formulario; con `job` retoman el polling, sin `job` no construyen al cargar. El panel abre el campo listo y
sus PNG reales. El blink espera las imágenes, muestra fallos/reintento y limita los atajos al reproductor.
Notas de procedencia visibles; listas sin análisis no se interpretan como ausencia de objetos.

Espectros por posición, comparaciones de épocas, Gaia, flags detallados, 3D físico y modo embebido compacto
siguen siendo dependencias P1 de ciencia/contrato. No se fabrican mediciones para completar esas vistas.

## Estructura

```
src/api/        types.ts (espejo del contrato) · client.ts (static|api) · format.ts
src/components/ BlinkViewer · CandidateList · CandidatePanel · SpectrumChart · ExplorerMap · SkyExplorer · SkyMap (field link) · SyntheticBadge
src/pages/      HomePage · FieldPage · AboutPage
src/App.tsx     router por hash: #/ · #/field/<id> · #/about
src/three/      escena 3D opcional y helpers; Three.js con carga diferida
src/pages/      SystemsPage · SystemPage: #/systems · #/system/<id>[/<body>]
```

Los modelos 3D actuales son ilustrativos, no observaciones SPHEREx ni ensayos R05; los parámetros actuales
están introducidos a mano y marcados sin verificar. El build principal usa contrato 0.3.0 con `Manifest.systems`.
`VITE_ALLOW_ALL_HOSTS=1` es una opción de preview remoto introducida por WS7; dejarla desactivada por defecto.
