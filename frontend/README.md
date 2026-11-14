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

Actualmente solo se interpretan `mode`/`dataset` y rutas hash por ID de campo. La entrada RA/Dec y el
recorrido hasta construir una secuencia son **P0 pendientes (WS5-7 + WS4-5)**. El modo estático sigue
sirviendo para desarrollo y campos curados, pero no cubre posiciones arbitrarias.

Consideraciones P1: FOV, bandas/coadds/espectro, suma/resta, Gaia DR3/WISE, flags y URL con coordenadas/modo
embebido. Su formato propuesto y el estado de implementación están en `docs/ARCHITECTURE.md` y
`docs/REQUIREMENTS.md`; las URLs de coordenadas todavía no están implementadas.

## Estructura

```
src/api/        types.ts (espejo del contrato) · client.ts (static|api) · format.ts
src/components/ BlinkViewer · CandidateList · CandidatePanel · SpectrumChart · SkyMap (placeholder) · SyntheticBadge
src/pages/      HomePage · FieldPage · AboutPage
src/App.tsx     router por hash: #/ · #/field/<id> · #/about
src/three/      escena 3D opcional y helpers; Three.js con carga diferida
src/pages/      SystemsPage · SystemPage: #/systems · #/system/<id>[/<body>]
```

Los modelos 3D son una extensión P2, no observaciones SPHEREx ni ensayos R05; los parámetros actuales
están introducidos a mano y marcados sin verificar. El build principal usa contrato 0.2.0 con `Manifest.systems`.
`VITE_ALLOW_ALL_HOSTS=1` es una opción de preview remoto introducida por WS7; dejarla desactivada por defecto.
