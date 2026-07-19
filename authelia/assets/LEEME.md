# Personalización de la pantalla de acceso (Authelia)

Authelia solo admite **oficialmente** tres cosas: el logotipo, el favicon
y los textos. No admite CSS propio.

La vía que circula por internet para cambiar colores y tipografías
consiste en inyectar una hoja de estilos desde el proxy inverso, y para
que el navegador la acepte hay que **debilitar la Content Security
Policy** de la pantalla de acceso — precisamente la que protege el resto.
No compensa por unos colores, así que aquí no se hace.

## Qué hay en esta carpeta

    logo.png               marca, se muestra sobre el formulario
    favicon.ico            icono de la pestaña
    locales/es/portal.json textos en castellano, adaptados

Los textos son un *override*: solo hay que poner las claves que se
quieran cambiar; el resto los pone Authelia. La clave es el texto en
inglés original. Ojo al actualizar Authelia: las claves pueden cambiar
entre versiones y entonces el texto vuelve al de serie (no rompe nada,
solo deja de aplicarse).

## Cómo se activa

1. Montar esta carpeta dentro del contenedor, en `/config/assets`.
2. En `configuration.yml`, bajo `server:`, dejar `asset_path: /config/assets`.
3. Reiniciar Authelia.

El tema claro u oscuro se elige aparte, con la clave `theme` de la
configuración (`light`, `dark`, `grey` o `auto`).
