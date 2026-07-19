# Textos de la pantalla de acceso (Authelia)

Aquí solo hay **textos**. Authelia admite oficialmente logotipo, favicon
y traducciones; de esas tres, aquí se usa la última.

## Por qué no hay logotipo

Julia **no tiene logotipo**. Se llegó a generar uno (el sol del hero
convertido en marca) y se retiró: inventar una identidad visual no es
una decisión técnica, y un logotipo puesto por descarte acaba
apareciendo en sitios donde nadie lo ha aprobado.

Si algún día lo hay, basta dejar `logo.png` y `favicon.ico` en esta
carpeta.

## Por qué no hay colores ni tipografía

Authelia no lo permite. Lo único que ofrece es el tema (`light`, `dark`,
`grey`, `auto`) con la clave `theme` de la configuración.

Cambiarlos de verdad exigiría un plugin de reescritura en Traefik que
inyecte una hoja de estilos, servirla desde el propio dominio, y
**debilitar la Content Security Policy** de la pantalla de acceso. Es la
página que protege todo lo demás, así que no se hace.

Además, esta instancia de Authelia es **infraestructura compartida**
(vive en `/opt/docker/infra`, no en este proyecto): cualquier cosa que se
le ponga sale también en el acceso al resto de servicios del servidor.
Ese es el motivo de fondo para dejarla neutra.

## Qué hay

    locales/es/portal.json   textos en castellano, adaptados

Es un *override* parcial: solo las claves que se quieren cambiar, el
resto los pone Authelia. La clave es el texto en inglés original. Al
actualizar Authelia conviene revisarlo: si una clave cambia de nombre, ese
texto vuelve al de serie (no rompe nada, solo deja de aplicarse).

## Cómo se activa

1. Montar esta carpeta en `/config/assets` del contenedor de Authelia.
2. En su `configuration.yml`, bajo `server:`, `asset_path: '/config/assets'`.
3. Recrear el contenedor (`docker compose up -d authelia`), no solo
   reiniciarlo: hay un montaje nuevo.
