@AGENTS.md

## Notas para Claude Code

- Antes de empezar, leé el archivo de tu workstream en `tasks/` (te lo indica la persona que te usa) y
  `docs/CONTRACT.md`. Trabajá solo en las rutas que ese archivo marca como tuyas.
- Usá `make check` como verificación final; para el frontend, además mirá la página en el navegador
  (`make web`) antes de decir que algo funciona.
- Si un servicio externo (IRSA, JPL, SkyBoT) no responde desde tu entorno, no inventes la respuesta:
  dejá el código con un test marcado `network` y explicá qué falta verificar.
