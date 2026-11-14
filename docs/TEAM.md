# Equipo y asignaciones

Completar en el kickoff. Una persona por fila; cada una con su(s) agente(s).

| WS | Tema | Persona | Agente(s) | Perfil ideal |
|---|---|---|---|---|
| WS1 | Acceso a datos SPHEREx | _nombre_ | Claude / Codex | Python, APIs, paciencia con servicios lentos |
| WS2 | Imágenes y detección | _nombre_ | | Python + numpy, procesamiento de imágenes |
| WS3 | Ciencia (objetos conocidos, distancia, espectros, Planeta X) | _nombre_ | | el/la más "astro" del grupo |
| WS4 | Backend + integración + CI | _nombre_ | | backend, devops |
| WS5 | Frontend | _nombre_ | | React/TS, ojo para UX |
| WS6 | Producto, narrativa, deploy, entrega | _nombre_ | | comunicación, diseño, video |
| WS7 | Sistemas 3D (modelos, órbitas, fichas) | _nombre_ | | three.js / gráficos 3D, ojo para diseño |

**Coordinador/a de integración:** _nombre_ (cuida `main`, el contrato y el cronograma; suele ser WS4).

### Si son 5 personas
- WS6 se reparte: **deploy** → WS4; **textos/About/pitch/video** → WS5 + quien termine antes (normalmente WS3 en
  la recta final). El formulario de entrega lo completa el/la coordinador/a.

### Dependencias entre WS (quién espera a quién)
- WS2 necesita frames reales de WS1 para pasar del demo a lo real (mientras tanto: trabaja sobre `data/demo` y
  sobre cutouts que baje a mano desde S3/IRSA).
- WS3 necesita detecciones de WS2 para el cruce (mientras tanto: efemérides y campos, sobre `data/demo`).
- WS4/WS5 no esperan a nadie: el contrato y el demo ya existen.
- WS7 no espera a nadie para la parte visual (ya hay 5 sistemas + 1 sintético); para verificar valores necesita
  acceso a NASA Exoplanet Archive/SIMBAD y, para asteroides reales, los candidatos `known` de WS2/WS3.
- WS6 necesita la URL de deploy (WS4) y capturas reales (WS5) hacia H+24.
