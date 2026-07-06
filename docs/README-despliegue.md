# juliamoreno.yoga — guía de despliegue y SEO

## Estructura
- `index.html` — página principal en español
- `en/index.html` — versión inglesa completa
- `fr/index.html` — versión francesa completa
- `de/index.html` — versión alemana completa (público clave en Nerja)
- `assets/style.css` — estilos compartidos
- `robots.txt` y `sitemap.xml` — listos para indexación

## Antes de publicar: rellenar marcadores
Buscar y sustituir en ambos HTML:
- `[TELÉFONO]` / `[PHONE]` y el número en los enlaces `wa.me/34XXXXXXXXX`
- `[DIRECCIÓN]` / `[ADDRESS]` (también en el JSON-LD del <head>)
- `[DÍA]`, `[HORA]`, `[PRECIO]` en la tabla de horarios
- `[USUARIO]` / `[USERNAME]` de Instagram
- Añadir fotos reales cuando las haya (clases, espacio, Julia) — pesan mucho en conversión

## Despliegue en Cloudflare Pages (gratis)
1. Crear cuenta en Cloudflare → Workers & Pages → Create → Pages → Upload assets.
2. Subir la carpeta completa. Nombre del proyecto: `yogaconjulia`.
3. En GoDaddy (donde está el dominio): apuntar los nameservers a los que
   indique Cloudflare al añadir el dominio (Websites → Custom domains),
   o bien crear un CNAME `juliamoreno.yoga` → `yogaconjulia.pages.dev`.
4. HTTPS es automático.

Alternativa igual de válida: GitHub Pages con un repo y CNAME.

## Después de publicar (en este orden)
1. **Google Business Profile** — crear/reclamar ficha "Yoga con Julia",
   categoría "Estudio de yoga", enlazar la web, subir fotos, y empezar a
   pedir reseñas tras cada clase (QR o WhatsApp). Es la palanca nº 1.
2. **Google Search Console** — verificar el dominio y enviar `sitemap.xml`.
3. **Bing Webmaster Tools** — importa desde Search Console en 2 clics
   (los residentes británicos usan Bing más de lo que parece).
4. Directorios: bookyogaretreats/Tripaneer (si hace retiros), guías locales
   de Nerja, grupos de Facebook de expats Nerja/Frigiliana.
5. Instagram con geotag Nerja/Playa Burriana enlazando a la web.

## Palabras clave objetivo ya integradas
ES: yoga en Nerja · clases de yoga Nerja · hatha yoga Nerja · yoga para
mayores Nerja · yoga infantil Nerja
EN: yoga in Nerja · yoga classes Nerja · hatha yoga Nerja · yoga for
seniors Nerja · yoga classes in English Nerja

## Palabras clave FR/DE ya integradas
FR: yoga à Nerja · cours de yoga Nerja · hatha yoga Nerja
DE: Yoga Nerja · Yogakurse Nerja · Hatha Yoga Nerja · Yoga für Senioren Nerja

## Nota importante de honestidad comercial
Las páginas FR y DE dejan claro que las clases se imparten en español e
inglés (no en francés/alemán). Si Julia habla alguno de esos idiomas,
actualizar la frase "Unterricht auf Spanisch und Englisch" / "Cours donnés
en espagnol et en anglais" en el héroe, la sección Julia y el FAQ.

## Despliegue en VPS propio (recomendado dado que ya hay uno)
Opción A — Docker + Traefik (carpeta `deploy/`):
1. `rsync -av --delete ./ vps:/opt/yogaconjulia/` (o git clone del repo)
2. Ajustar `certresolver` al nombre usado en el Traefik del VPS.
3. `cd /opt/yogaconjulia/deploy && docker compose up -d`
4. DNS en GoDaddy: registro A de `juliamoreno.yoga` y `www` a la IP del VPS.

Opción B — nginx sin Docker (`deploy/nginx-vhost-sin-docker.conf`):
1. Copiar el sitio a `/var/www/yogaconjulia`.
2. Instalar el vhost, `certbot --nginx`, recargar nginx.

En ambos casos, ANTES de apuntar el DNS: verificar en GoDaddy qué web
está publicada ahora mismo en el dominio (ver nota de reputación: hay
contenido indexado de una "Yoga con Julia" que puede no ser suya).

## Ubicaciones Maro y Almuñécar (añadido)
- Horarios ahora con columna Lugar: Nerja, Maro (local municipal, 2 días)
  y Almuñécar (escuela de baile, viernes). Local Almuñécar: Centro Profesional de Danza Juan Pablo García.
- areaServed añadido al JSON-LD: Nerja, Maro, Almuñécar.
- Claves nuevas: yoga Maro · yoga Almuñécar · yoga La Herradura.
- Ficha de Google: añadir Maro y Almuñécar como zonas de servicio.
