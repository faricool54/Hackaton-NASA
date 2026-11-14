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

## Estructura

```
src/api/        types.ts (espejo del contrato) · client.ts (static|api) · format.ts
src/components/ BlinkViewer · CandidateList · CandidatePanel · SpectrumChart · SkyMap (placeholder) · SyntheticBadge
src/pages/      HomePage · FieldPage · AboutPage
src/App.tsx     router por hash: #/ · #/field/<id> · #/about
```
