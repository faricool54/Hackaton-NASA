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

## 04 · Final (27,2 s): candidato a final con lo que pidió el equipo

Pedido del equipo:
- un arranque comercial;
- que no parezca un PowerPoint, con más movimiento y algo más vistoso;
- una voz mejor;
- elementos del video de referencia: titulares, subtítulos y entradas animadas.

**Equipo:** RetMax. La app sigue siendo Errante.

Hay dos versiones:
- `04-final-captions-08dfb85.mp4`: **la recomendada**, con titulares por sección y subtítulos en inglés.
  Es un postproceso del montaje verificado, hecho con `04-final-source/overlays.py`.
- `04-final-08dfb85.mp4`: el montaje sin titulares. `verificar.py --final` da 0 errores y 0 advertencias.

Hoja de contacto (versión con subtítulos): `04-final-sheet.jpg`.

**Recorrido.** Es el mismo del 03, contado igual de honesto.

**Contenido, de 0 a 27 s:**
- **Apertura (0–7 s):** el blink real en falso color del campo del 03, con «Expand» a pantalla completa.
  Encima, el título animado «ERRANTE · Watch the infrared sky change» y un acercamiento lento.
- **Build:** build real en 76.73397°, +30.23697°. El cartel del corte usa el tiempo medido por la API del
  job (`ca52180e`): «Edited cut: this build took 1 min 11 s».
- **Object y 3D:** zoom de 1,55× sobre la ficha y de 1,6× sobre el 3D; «3D MODEL · NOT AN IMAGE» queda visible.
- **Cierre:** placa de créditos con acercamiento lento. Dice «Team: RetMax».

**Voz:** en-US-AvaMultilingualNeural (edge-tts) a +6%. Está declarada como IA en la placa, en la metadata y
en `descripcion.md`.

**En la VM** quedó publicado un campo de job más: `ca52180e`.

## 03 · Build por click (`03-build-08dfb85.mp4`, 27,8 s): candidato a final

Sigue el recorrido que pidió faricool54 después de `e89ab45`, grabado sobre `08dfb85`.
Hoja de contacto: `03-build-sheet.jpg`. Guion y tomas: `03-build-source/`.

| # | Narración | Visual | Entra | Dura |
|---|---|---|---|---|
| 1 | Errante connects real NASA images, spectra, and light curves in one public explorer. | Placa 1 | 0:00.1 | 6,5 s |
| 2 | Pick a point in the sky and build its SPHEREx sequence. | D1: el punto elegido (76.7330°, +30.2370°) y el click en «Build SPHEREx sequence» (All detectors · color); el panel muestra el job real arrancando («Preparing SPHEREx observations · queued») | 0:06.7 | 4,2 s |
| 3 | After a two-minute cut, its real frames blink in false color. | D2: el mismo job terminado, con el cartel «Edited cut: this build took 1 min 53 s»; click en «Color · detectors» y blink de las 3 temporadas en falso color | 0:10.9 | 4,7 s |
| 4 | Hover a Gaia star for its card; click it for its catalog facts. | D3: hover sobre Gaia DR3 156328460158131584 (la estrella de #160), con su tarjeta; click y Object: «Matched», 2371 pc por paralaje, 4779 K | 0:15.6 | 5,0 s |
| 5 | 3D draws it from catalog values. | D4: 3D, con «CATALOG MODEL · built from the object card» y «3D MODEL · NOT AN IMAGE» | 0:20.7 | 3,4 s |
| 6 | Explore the changing sky with Errante. | Placa 2 | 0:24.1 | 3,7 s |

Notas:

- **El tiempo del corte es el medido.** El job grabado en D1 (`7aa7d11f`, en 76.73297°, +30.23697°) tardó
  1 min 53 s: de 01:07:34Z a 01:09:27Z. D2–D4 reabren ese mismo punto, así que muestran el resultado
  de ese build. El punto está 3″ al este de la estrella para que D1 arranque un build nuevo: el punto
  exacto ya lo había armado fuera de cámara a las 21:58 ART, y el servidor reutiliza un job listo durante
  15 min.
- **Los dos builds que quedaron publicados en la VM:**
  - `62c21411`, en 76.73197°, el de la exploración;
  - `7aa7d11f`, en 76.73297°, el grabado.
- **Gaia en la vista ancha:** después del build, el mapa en vista ancha mostró «Gaia DR3 stars did not
  load for this wide view (VizieR did not answer)». Para D3 se acerca el zoom fuera de cámara, a ~17′.

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
