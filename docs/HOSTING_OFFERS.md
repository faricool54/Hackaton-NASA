# Ofertas gratuitas de Space Apps 2026 (hosting y herramientas)

> Fuente: anuncio "Global Offers" de NASA Space Apps recibido por el equipo el **2026-11-14** (copiado abajo).
> Son **opcionales**. Antes de usar una, verificar en el portal de Space Apps cómo se reclama, plazos, límites y si
> pide tarjeta de crédito: nada de eso está verificado acá. Dueño de las decisiones de hosting: **WS4** (deploy),
> con WS6 para lo que se publique en la entrega.

## Texto del anuncio

> The hackathon is kicking off, and Global Offers are now LIVE! Use these optional free tools & resources for your project:
>
> **GoDaddy:** Unleash your creativity with a free domain and one year of website hosting, exclusively available to all
> NASA Space Apps participants. Embark on your digital journey and showcase your project to the universe.
>
> **Google Cloud:** NASA Space Apps Challenge participants can use the Google Cloud Platform and its many products and
> services, including Firebase and the Google Maps API, to easily launch cloud-based applications (mobile, web, Internet
> of Things, and more) utilizing the best in big data, super intelligence, and machine learning.
>
> **Meteomatics:** Access the world's most accurate weather, marine, environmental, and climate data. Use the API to
> customize data formats and integrate seamlessly into your project.
>
> **Microsoft:** NASA Space Apps Challenge participants can use Microsoft Azure, Planetary Computer, Microsoft Copilot,
> Github Copilot, and Teams to collaborate with your team, harness the power of coding assistants, access environmental
> monitoring data, process data sets, and more with these tools.
>
> **Miro:** A collaborative online whiteboard platform including Miro Education Plan, Miro Business Plan, and NASA Space
> Apps Hackathon Miro Board Templates.

## Para qué nos puede servir (propuesta, a decidir por WS4/WS6)

Lo que necesita nuestro deploy (ver [`ARCHITECTURE.md`](ARCHITECTURE.md) y [`../backend/README.md`](../backend/README.md)):

- **Frontend estático** (Vite): ya hay workflow de GitHub Pages (`.github/workflows/pages.yml`). Ojo: el repo es privado.
- **Backend Python** (FastAPI + astropy) con **disco para caché**, requests de varios segundos y, si se puede, cerca
  de **S3 us-east-1** (donde están los datos SPHEREx). Ya hay `backend/Dockerfile`.
- **Links públicos sin login** para la entrega (reglas de Space Apps).

| Oferta | Uso posible para nosotros | A tener en cuenta |
|---|---|---|
| **GoDaddy** (dominio + 1 año de hosting) | **Dominio propio** para la URL pública del proyecto (más presentable en el formulario y el video); apuntarlo al frontend. | ❓ Qué tipo de hosting incluye: si es hosting web tradicional, probablemente no sirve para el backend Python con caché; sí para un sitio estático o una redirección. |
| **Google Cloud** (incluye Firebase) | **Cloud Run** para el contenedor del backend (`backend/Dockerfile`) en una región del este de EE. UU. (cerca de S3 us-east-1); **Firebase Hosting** para el frontend estático. | ❓ Créditos/condiciones. Cloud Run no tiene disco persistente por defecto: la caché sería por instancia (o usar un bucket). |
| **Microsoft** (Azure, GitHub Copilot, Teams…) | **Azure Container Apps / App Service** (región East US) como alternativa para el backend; Teams para coordinar. | Si alguien usa **GitHub Copilot** o **Microsoft Copilot**, declararlo como uso de SI (`AI_USAGE.md`, formulario). |
| **Miro** | Tablero del equipo: plan, arquitectura, guion del video de 30 s. | Plantillas de Space Apps disponibles. |
| **Meteomatics** | No aplica a SPHEREx (datos meteorológicos/climáticos). | — |

Reglas que siguen valiendo con cualquier proveedor:

- **Sin secretos en el repo**: credenciales y API keys van en las variables de entorno del proveedor, nunca en Git.
- Lo que se use se lista en las referencias/herramientas de la entrega (`docs/submission/PROJECT.md`).
- Decidir **un** proveedor para el backend antes del domingo 12:00 (deploy público del cronograma) y anotarlo en
  [`TEAM.md`](TEAM.md) o en el PR de deploy de WS4.
