# video-tutorial · cursos y demos narradas

Para la demo final de Errante hay un [perfil de 30 segundos](reference/errante-demo.md):
**narración en inglés, sin subtítulos**, estética oscura, tomas reales y
verificación estricta del MP4 final. Se puede usar desde Codex o Claude Code.

```text
python scripts/scaffold.py demo <carpeta-de-produccion>
```

La plantilla deja nombre del equipo e integrantes pendientes de confirmar; exige esos
datos para la entrega final. No graba ni publica nada al inicializarla. Los detalles
y comandos de producción están en la referencia enlazada.
La distribución incluye solo el preset neutro con fuentes del sistema; el diseño
personalizado requiere recursos con derechos acreditados. No incluye fuentes comerciales
ni presets corporativos de terceros. Las condiciones de publicación de la voz generada
se revisan por separado; ver [voz](reference/voice.md).

Produce cursos en video narrados, de punta a punta, y los itera línea por línea:
**guion → deck → slides → locución IA → tomas de pantalla automáticas → montaje → publicación**.

La guía visual completa está en [`guia.html`](guia.html): ábrela en el navegador.

## Empezar

No hace falta tipear comandos: se lo pides a Claude Code.

1. **Instala la skill.** En Claude Code, pide:
   > instala la skill video-tutorial desde `<carpeta o repo de la skill>`

   Claude la enlaza en tu carpeta de skills. Abre una sesión nueva para que la reconozca.
2. **Crea tu curso.** Abre Claude Code en la carpeta donde quieres el curso y pide:
   > configuremos un curso nuevo

   El wizard te hace unas pocas preguntas, **instala lo que falte** (dependencias de Python), verifica Chrome, te
   deja elegir la voz y el diseño, y te abre el login del producto si vas a grabar pantallas. Tú solo inicias
   sesión; tus credenciales nunca las tipea Claude.

Requisitos: Python 3.11+ y un agente compatible. El grabador conserva el requisito original
de Google Chrome; la exportación de slides admite los navegadores que ya soportaba la skill.

## Qué hay adentro

| Carpeta | Qué es |
|---|---|
| `SKILL.md` | Lo que Claude lee primero: el flujo, las reglas y a qué referencia ir en cada etapa |
| `reference/` | El wizard, el formato del guion, recetas de iteración, voz, grabación, deck, publicación |
| `scripts/` | El pipeline en Python (`scaffold`, `locutor`, `variantes`, `pausas`, `voces`, `slides`, `grabar`, `montar`, `verificar`) y sus tests |
| `templates/` | `course.yaml` documentado, convenciones del curso, guiones, deck neutro y presets de diseño |

Cada curso guarda lo suyo en su `course.yaml` (voz, velocidad, diccionario de pronunciación, URL a grabar, qué
difuminar, design system). El perfil de Errante agrega las convenciones específicas de esa demo.

## Instalación manual (si prefieres hacerlo a mano)

```
pip install edge-tts imageio-ffmpeg playwright pillow pyyaml
python scripts/kokoro_setup.py      # solo si vas a usar una voz Kokoro (local, sin internet); pide espeak-ng
```
- Windows (sin permisos de administrador):
  `New-Item -ItemType Junction -Path "$HOME\.claude\skills\video-tutorial" -Target "<carpeta de la skill>"`
- macOS / Linux: `ln -s "<carpeta de la skill>" ~/.claude/skills/video-tutorial`

## Tests de la skill

```
pip install pytest pytest-cov
python -m pytest scripts/tests
```

Los tests de grabación y de slides usan el Chrome del sistema y se saltean si no está.
