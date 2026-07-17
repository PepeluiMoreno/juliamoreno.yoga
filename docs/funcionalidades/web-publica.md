# Web pública

## Qué es
El sitio de cara al público de Julia Moreno · Yoga. Presenta la
actividad, las clases, las ubicaciones y las vías de contacto. Es la
puerta de entrada y la herramienta de conversión (que alguien pase de
visitante a alumno).

## Cómo está resuelto hoy
- Sitio **estático multi-idioma**: ES (raíz), EN, FR, DE. El alemán
  importa: público clave en Nerja.
- Estructura: `sitio/index.html` (ES) y `sitio/{en,fr,de}/index.html`.
- Estilos compartidos en `sitio/assets/`.
- SEO listo: `robots.txt`, `sitemap.xml`, JSON-LD en el `<head>`.
- Marca: "Julia Moreno · Yoga"; lema "Yoga con ciencia, frente al
  Mediterráneo."
- Tres ubicaciones: Nerja (principal), Maro, Almuñécar (Centro
  Profesional de Danza Juan Pablo García).

## Decisiones tomadas
- Estático en vez de CMS: coste cero de mantenimiento, rápido, seguro,
  fácil de desplegar (Cloudflare Pages gratis). No necesita base de
  datos para servirse.
- Multi-idioma por carpetas (no por parámetros ni cookies): simple,
  indexable, cada idioma con su URL.
- Contenido con marcadores a rellenar (teléfono, dirección, horarios,
  Instagram) — ver README-despliegue.md.

## Relación con el resto
- La oferta (actividades, horarios, tarifas) vive en NocoDB; la idea es
  que la web se **genere** con esos datos (build), no que se edite a
  mano cada cambio. Ver backend.md y actividades-clases-agenda.md.
- El módulo de reservas (en diseño) añadiría a la web una vista de
  disponibilidad y un flujo de "contratar clases". Ver
  reservas-disponibilidad-avisos.md.

## Pendiente / ideas
- Publicar la agenda/horarios reales desde NocoDB en la web pública
  (hoy los horarios son marcadores).
- Fotos reales (clases, espacio, Julia): pesan mucho en conversión.
- Página o sección de tarifas alimentada desde NocoDB (tabla Precios).
- Integrar la vista de disponibilidad cuando exista el módulo de
  reservas.

## Ficheros
- `sitio/index.html`, `sitio/{en,fr,de}/index.html`
- `sitio/assets/`
- `docs/README-despliegue.md` (despliegue y SEO)
- `docs/traduccion-cambiar-motor.md` (notas de traducción)
