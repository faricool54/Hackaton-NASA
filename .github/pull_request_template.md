<!-- Título: `wsN: verbo + qué` · `contract: ...` · `chore: ...`  (docs/COLLABORATION.md) -->

## Workstream
<!-- WS1 / WS2 / WS3 / WS4 / WS5 / WS6 / contract / chore -->

## Qué cambia
<!-- 1-3 líneas. Link a la tarea: tasks/WSx-...md (WSx-N) o issue #N -->

## Cómo lo probé
- [ ] `python scripts/dev.py check` pasa (incluye la guardia de ownership)
- [ ] (UI) lo miré en el navegador, desktop y celular
- [ ] (datos) probado con datos reales / solo demo

## Checklist
- [ ] Solo toqué archivos de mi workstream (`python scripts/dev.py owners`) o lo avisé en el chat
- [ ] Actualizado con `main` justo antes de abrir/actualizar el PR (`git pull origin main`, sin rebase ni force)
- [ ] Si cambié el contrato: `python scripts/dev.py schema`, `types.ts` actualizado, `SCHEMA_VERSION` revisado, aviso a WS2/WS4/WS5
- [ ] Nada sintético presentado como real; ningún "descubrimos"
- [ ] Commits hechos con IA llevan el trailer `Co-Authored-By:` (regla de uso de SI)
