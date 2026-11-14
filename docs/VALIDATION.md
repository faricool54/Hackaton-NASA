# Validación de los cinco objetos del enunciado (R05)

Responsable: **WS3**, con WS1 (cobertura), WS2 (imágenes), WS5 (recorrido público) y WS6 (evidencia).
Estado inicial: **pendiente en los cinco casos**. Los datos sintéticos no cuentan como validación SPHEREx.
Esta evidencia sostiene **Validity** y **Relevance** de la rúbrica 1–5 del proyecto; ver
[JUDGING_GUIDE.md](JUDGING_GUIDE.md). No sustituir observaciones por tests con mocks ni asignar notas de
jurado desde `Candidate.score`. La revisión interna queda separada en `submission/JUDGING_REVIEW.md`.

| Objetivo | Qué se busca comprobar | Identidad / posición | Estado |
|---|---|---|---|
| Barnard's Star | Movimiento propio entre épocas separadas, registro WCS estable respecto al fondo | Preset `barnards-star` existente; verificar fuente, época y propagación antes de usarlo como evidencia | Pendiente |
| Epsilon Indi B | Visualización del sistema de enanas marrones y su cambio entre épocas | Resolver el componente B y distinguirlo de Epsilon Indi A; no asumir que Ba/Bb se resuelven en SPHEREx | Pendiente |
| WISE 0855 | Objeto débil con movimiento propio; escoger bandas y épocas adecuadas | Texto: RA **08h55m10.831s**, Dec **−07°14′42.53″**. Época no indicada; resolver y propagar con fuente | Pendiente |
| RW Aurigae | Cambios de brillo, sin confundir espectro, calibración o mezcla de fuentes con variabilidad | Resolver identidad, componentes relevantes, coordenadas y época con fuente | Pendiente |
| R Draconis | Serie temporal de una variable; comparación consistente de brillo entre épocas | Resolver identidad, coordenadas y época con fuente | Pendiente |

No rellenar coordenadas faltantes a partir de la memoria ni tomar una posición antigua como posición actual.
`config/fields.toml` contiene presets de desarrollo; no es un registro de validaciones aprobadas.
✅ 2026-11-14: los cinco presets están en `fields.toml` con astrometría de Sesame/SIMBAD (CfA) propagada a la
época media de los datos SPHEREx ([`SCIENCE.md`](SCIENCE.md) §0). Siguen siendo presets: la validación con
imágenes reales está pendiente.
Los cinco SystemModel de WS7 son modelos ilustrativos de esos nombres, no registros de ensayo.
No copiar posiciones, períodos u órbitas de `systems/catalog.py` como datos verificados para esta validación.

## Protocolo por objeto

1. **Identidad y astrometría:** registrar nombre resuelto, catálogo/URL, RA/Dec ICRS, época, movimiento propio,
   paralaje si existe y método de propagación. Conservar posición de búsqueda y posición predicha por época.
   Gaia no cubre necesariamente todos los blancos; una ausencia de catálogo no excluye el objeto.
2. **Cobertura:** consultar SPHEREx y conservar consulta, fecha, release, URIs, MJD, detector, λ y ancho
   de banda cuando estén disponibles. Seleccionar visitas con separación útil; no tomar solo los primeros
   40 archivos ni duplicar la misma exposición de diferentes releases.
3. **Imágenes:** descargar cutouts reales, reproyectar a grilla común, verificar estrellas de fondo,
   máscaras, cobertura, PSF y normalización. Conservar los FITS en caché, fuera de git.
4. **Movimiento:** comparar centroides o posición esperada sobre el fondo, con incertidumbre astrométrica.
   Animación y verificación manual son válidas para el MVP; el detector automático no es obligatorio.
5. **Variables:** comparar mediciones a λ compatible, con fondo, PSF/apertura y calibración controlados;
   usar flujo y error del FITS, no intensidad de PNG autoescalados. No basta con igual detector, porque
   la longitud de onda varía dentro de cada detector. Documentar mezcla de componentes o saturación.
6. **Recorrido público:** ingresar RA/Dec en la web, generar/cargar la secuencia y usar play/pausa/paso.
   Guardar URL del campo y, cuando C06 exista, URL con coordenadas. Adjuntar captura o animación y resumen.
7. **Resultado:** registrar éxito, cobertura insuficiente, señal insuficiente o inconcluso con su causa.
   Una prueba negativa documentada cuenta como ensayo realizado, nunca como detección exitosa.

## Registro que debe acompañar cada ensayo

Los resultados reales se guardarán en `docs/validation/<slug>.md`; los productos livianos en
`data/products/fields/<id>/`. Crear el registro cuando se ejecute el ensayo, sin archivos vacíos de evidencia.

```text
Target / resolved catalog ID:
Astrometry source URL / reference epoch / propagation:
Query RA, Dec / FOV / query date:
SPHEREx releases / observation IDs / MJDs / detectors / wavelengths:
Useful epochs / time baseline / coverage and quality flags:
Alignment check / photometry or astrometry method / uncertainties:
Expected behavior / observed behavior:
Result: success | insufficient_coverage | insufficient_signal | inconclusive
Limitations and failed downloads:
Product field ID / public URL / screenshot or animation:
Reviewer / date:
```

WS6 publica una tabla que separa ensayos realizados de resultados positivos. Si la cobertura no alcanza,
se ajustan épocas, banda o FOV cuando sea justificable y se deja constancia del intento original.
