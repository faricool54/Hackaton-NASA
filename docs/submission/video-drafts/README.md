# Borradores del video de demo (V0id47 + Claude)

Dos cortes para que el equipo los vea y opine. **Ninguno es el final:** el corte final se regraba sobre
el deploy que anunció faricool54 para las ~22:05 (#100). Estos archivos viven solo en esta rama; no hace
falta mergearla.

Los dos videos se hicieron con la herramienta `docs/submission/skills/video-tutorial/` y el perfil
`errante-demo`:

- **Formato:** 1920×1080 a 30 fps, H.264 + AAC.
- **Voz:** en inglés, con edge-tts (en-US-JennyNeural), sin subtítulos.
- **Fuente de las tomas:** grabadas con Playwright sobre la URL pública.
- **Write guard activo:** cada toma corre con la protección de escritura encendida.
- **Verificación:** `verificar.py --final` da 0 errores y 0 advertencias en los dos.

## 02 · Recorrido (`02-walkthrough-d06896f.mp4`, 28,2 s)

Sigue el recorrido que propuso faricool54 en #100. Está grabado sobre `d06896f`.
Para revisarlo sin abrir el video, hay hoja de contacto: `02-walkthrough-sheet.jpg`, un cuadro cada 2 s.

| # | Narración | Visual | Entra | Dura |
|---|---|---|---|---|
| 1 | Errante connects real NASA images, spectra, and light curves in one public explorer. | Placa 1 (equipo, integrantes, reto) | 0:00.1 | 6,5 s |
| 2 | Pick Barnard's Star to blink its real SPHEREx frames. | D1: click en el chip de Barnard; se abre Time y arranca el blink (fechas de agosto de 2025) | 0:06.7 | 4,2 s |
| 3 | Hover a Gaia star for its catalog card; click to select it. | D2: hover en el marcador Gaia DR3 de Barnard, aparece la tarjeta y el click la selecciona | 0:10.8 | 4,9 s |
| 4 | Object lists its catalog facts, each with a source. | D3: click en Object, con la ficha completa (M4V, 1,828 pc, BY, 4 planetas) | 0:15.7 | 4,5 s |
| 5 | 3D models its confirmed planets from catalog data. | D4: click en 3D, con el sistema de Barnard y la etiqueta «3D MODEL · NOT AN IMAGE» | 0:20.2 | 4,3 s |
| 6 | Explore the changing sky with Errante. | Placa 2 (URL, créditos NASA/IRSA, DOIs, voz IA) | 0:24.4 | 3,7 s |

Notas de grabación:

- Cada toma prepara fuera de cámara todo lo que necesita: los frames, los marcadores Gaia, la consulta
  de catálogo (con Retry si algún servicio no responde) y el modelo 3D.
- El primer lookup de Object a veces dio «5 of 6 without answer»; el Retry lo completó. En la grabación
  no se ve, porque la consulta se resuelve antes.
- Al seleccionar una estrella, la app hace `POST /api/spectra`, y el write guard lo bloqueó. No se ve
  en el video, porque la pestaña Spectrum no aparece.
- No se muestra el build por click: tarda ~80 s y obligaría a meter un corte.
- El guion y las tomas están en `02-walkthrough-source/`.

## 01 · Demo general (`01-demo.mp4`, 25,7 s)

Es el primer corte. Hoja de contacto: `01-demo-sheet.jpg`.

| # | Narración | Visual |
|---|---|---|
| 1 | Errante connects real NASA images, spectra, and light curves in one public explorer. | Placa 1 |
| 2 | Search the infrared sky and investigate how it changes. | D1: búsqueda «Barnard» y selección de la secuencia |
| 3 | Barnard shifts between seasons. Its flagged core limits brightness measurements. | D2: diferencia de estaciones D2_S2−S0, con su advertencia de núcleo marcado |
| 4 | Inspect brightness measurements and uncertainties in a light curve. | D3: curva de luz de R Draconis, con errores |
| 5 | Explore the changing sky with Errante. | Placa 2 |

## Qué falta

- **Regrabar el 02 sobre el deploy de las ~22:05.** En ese deploy:
  - el click tiene color;
  - el 3D funciona en estrellas comunes.

  Se puede cambiar D2–D4 a una estrella Gaia común en lugar de Barnard, como sugirió faricool54.
- **Subir el video final y conseguir un link sin login.** Lo decide V0id47.
- **Completar el formulario y hacer Submit for Judging** antes de las 23:59 ART. En el formulario va la
  declaración de IA: voz TTS, guion y tomas asistidos por Claude.
