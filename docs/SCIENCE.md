# Ciencia mínima para el equipo

Lectura obligatoria para WS2 y WS3; recomendada para todos (sirve para el pitch).

## 1. ¿Por qué se mueven las cosas en el cielo?

Las estrellas están tan lejos que, en meses, casi no se mueven (salvo las muy cercanas: *movimiento propio*,
p. ej. Barnard 10″/año). Los objetos del Sistema Solar se mueven por dos razones:

1. **Su propio movimiento orbital** (un objeto a r UA va a ≈ 29.8/√r km/s).
2. **El movimiento de la Tierra/SPHEREx** (29.8 km/s), que produce un desplazamiento aparente (paralaje)
   inversamente proporcional a la distancia.

### SPHEREx mira a ~90° del Sol (¡importante!)

SPHEREx observa en círculos perpendiculares a la dirección del Sol (como WISE). En la eclíptica a 90° del Sol,
la Tierra se mueve **a lo largo de la línea de visión**, así que el paralaje *dentro de una visita* casi
desaparece y los objetos lejanos se ven **casi quietos durante horas**. Entre pasadas separadas ~6 meses, en
cambio, la Tierra está del otro lado de su órbita → **desplazamientos enormes** por paralaje.

Órdenes de magnitud (órbitas circulares, aproximación r ≫ 1; píxel SPHEREx = 6.15″):

| r [UA] | ejemplo | en oposición ["/h] | a ~90° del Sol ["/h] | a ~90° [px/día] | entre pasadas a 6 meses |
|---|---|---|---|---|---|
| 2.7 | cinturón principal | 34 | ~decenas | ~100+ | otro lugar del cielo |
| 5.2 | troyanos de Júpiter | 20 | ~10 | ~50 | otro lugar del cielo |
| 30 | Neptuno / Plutinos | 4.2 | 0.9 | 3.5 | ~2200 px |
| 45 | Makemake / KBO clásico | 2.9 | 0.5 | 1.9 | ~1500 px |
| 100 | disco disperso | 1.3 | 0.15 | 0.6 | ~670 px |
| 500 | tipo Planeta Nueve | 0.28 | 0.013 | 0.05 | ~130 px |
| 800 | Planeta Nueve lejano | 0.18 | 0.007 | 0.03 | ~85 px |

Fórmulas: oposición `≈ 147.8″/h · (1 − 1/√r)/(r − 1)` (implementada en `errante.science.motion`);
a 90° `≈ 147.8″/h / (√r · √(r² − 1))`; paralaje entre pasadas `≈ 2 UA / r` rad (geometría real: WS3).

**Consecuencias para el diseño:**
- Asteroides: se ven moverse **dentro de una visita** (horas) → linking lineal simple (WS2, P0). Es lo que
  seguro funciona y lo que más vamos a mostrar.
- TNOs: ~1–4 px/día a 90° → se necesitan observaciones separadas por ≥ 1 día del mismo campo (ver en DATA
  cuántas hay; los **campos profundos** de los polos eclípticos tienen muchas más épocas).
- Un Planeta Nueve: prácticamente **quieto dentro de una visita** y saltando ~100 px entre pasadas. Buscarlo
  requiere *shift-and-stack* a lo largo de órbitas hipotéticas (rango de distancias) entre pasadas — es una
  demo/visualización educativa valiosa, no un resultado que vayamos a lograr en 48 h.
- La estimación de distancia "por velocidad en oposición" del demo es **solo orden de magnitud**; WS3 debe
  reemplazarla por la geometría real usando la posición de SPHEREx (`X_SC…` en el header) y la fecha.

## 2. ¿Qué tan débil es un Planeta X?

- Predicciones para el Planeta Nueve (Brown & Batygin 2021, AJ 162, 219): semieje ≈ 380 UA (perihelio
  ≈ 300 UA, hoy probablemente cerca del afelio, a varios cientos de UA), ≈ 6 masas terrestres, inclinación
  ≈ 16°, brillo en el visible del orden de **V ≈ 20–23** según distancia y albedo. **Verificar los números en
  el paper antes de citarlos** en la UI o el pitch (tarea de WS3).
- SPHEREx no está optimizado para objetos tan débiles en una sola exposición. **No sabemos** su profundidad
  real para nuestros métodos → la medimos con **inyección-recuperación** (WS2): plantamos objetos falsos en
  imágenes reales y vemos cuáles recuperamos. Esa tabla de límites es parte central del producto.

## 3. Lo que SPHEREx sí hace genial: espectros

Cada exposición mide una longitud de onda distinta en cada punto (filtro lineal variable). Un objeto observado
varias veces junta un **espectro 0.75–5 µm** gratis:
- **asteroides**: luz solar reflejada; banda de hidratación ~3 µm en algunos tipos.
- **enanas marrones frías**: muy rojas, absorción de metano ~3.3 µm, brillantes en 4–5 µm.
- **estrellas**: caen hacia longitudes de onda largas.

Ojo: la misma estrella cambia de brillo entre exposiciones *porque cambia la longitud de onda*, no porque varíe.
Comparar brillos solo entre exposiciones de longitud de onda parecida (o usar solo posiciones).

## 4. Encuadre honesto (para UI, pitch y entrega)

- "Planeta X es nuestra motivación científica, no un resultado prometido."
- Estados: `known` (coincide con catálogo), `unconfirmed` (sin match: puede ser artefacto, error de medición u
  objeto no catalogado), `artifact` (rechazado por validación), `injected` (simulado).
- Mostrar siempre: cuántas detecciones, residuo del ajuste, flags tocados, límites medidos.
- Validar con objetos conocidos: asteroides (JPL), Makemake u otro TNO, estrellas de alto movimiento propio
  (Barnard, WISE 0855). "Recuperamos X de Y objetos conocidos" es un argumento fortísimo para el jurado.

## 5. Glosario rápido

**MJD**: fecha juliana modificada (días). **RA/Dec**: coordenadas ecuatoriales (grados). **PA**: ángulo de
posición, desde el norte hacia el este. **UA**: distancia Tierra–Sol. **TNO/KBO**: objeto transneptuniano /
del cinturón de Kuiper. **Blink comparator**: alternar imágenes de distintas fechas para ver qué cambia (así se
descubrió Plutón en 1930). **Cutout**: recorte de una imagen. **HiPS**: formato de imágenes de todo el cielo por
teselas (lo usa Aladin). **Shift-and-stack**: sumar imágenes desplazadas según un movimiento supuesto para
detectar objetos débiles.
