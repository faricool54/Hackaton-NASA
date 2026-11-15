# ${name}

Curso en video hecho con la skill **video-tutorial** de Claude Code. Cada video sale de un guion con una
*hoja de montaje*: una fila es una frase de locución más una imagen (una slide o una toma de pantalla).
Todo lo demás (slides, voz, grabación y montaje) se genera desde ahí.

Le hablas a Claude en lenguaje natural, dentro de esta carpeta. Abajo tienes los pedidos típicos de cada etapa.

## 1. Arrancar un video

> armemos guion, deck y slides para un video sobre *X*
> nuevo video "03 - Permisos": explica cómo se piden y quién los aprueba

Claude crea la carpeta del video, escribe el guion verificando contra el producto y arma el deck.

## 2. Guion

> líneas 5 a 8: no trataremos *X* ahora, quita esta frase
> mueve la línea 8 al principio, empezaremos por este tema
> línea 3: cámbiala por "…" (o: dame opciones)

Si pides opciones de redacción, Claude genera audios numerados para que elijas de oído.

## 3. Slides

> slide 2: el subtítulo no me gusta, cámbialo por algo sobre *X*
> slide 4: divídela en dos, una para A y otra para B
> slide 6: agrega un diagrama de flujo para explicar *X*
> que la slide 3 vaya sumando cada punto a medida que la voz lo nombra

## 4. Locución

> línea 8: no me gusta cómo pronuncia "team", dame opciones
> línea 5: agrega una pausa después de "Identity"
> sube la velocidad a 1.05x en este video

Las correcciones de pronunciación se guardan en el diccionario del curso (`course.yaml`) y valen para
todos los videos. En el guion y en pantalla las palabras quedan como son.

## 5. Tomas de pantalla

> grabemos todas las escenas del deck
> la toma de la línea 9 dura demasiado, hazla 1.5 s más corta
> cuando dice "el botón Guardar", ponle un recuadro rojo
> en la toma 4, una flecha que señale el menú de la izquierda
> difumina el nombre de la persona en la toma 2

**Anotaciones que puedes pedir sobre una toma:** recuadro sobre un elemento o sobre una zona entera, flecha
que señala un elemento desde un lado, difuminado de un elemento o de una palabra suelta, spotlight que
oscurece todo lo demás, etiqueta de texto, pasos numerados, zoom a una zona y el recorrido del cursor (por
dónde pasa, dónde hace clic o escribe). Dile a Claude
cuándo aparece cada una ("cuando la voz dice X") y cuándo se va. Ninguna se agrega si no la pides.

## 6. Montaje y publicación

> rearma el montaje
> la slide 4 se va muy rápido, déjala 2 s más
> está listo para subir

Claude deja el video final y su descripción en `${publish}/`. Subir, enviar o publicar siempre te lo
confirma antes.

## Si algo falla

- **El sitio no carga al grabar:** suele ser la VPN.
- **Te pide login al grabar:** pídele a Claude que abra el login; inicias sesión tú, en la ventana que abre.
- **Una voz salió cortada o rara:** pide regenerar esa línea; el pipeline ya reintenta los audios cortados.
