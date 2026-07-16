# Backoffice de precios y horarios (NocoDB → web)

Permite a Julia cambiar precios, y activar/desactivar franjas de horario,
sin editar la web. Ella solo toca VALORES; los idiomas los mantiene el
soporte técnico en data/contenido.json.

## Piezas
- `data/contenido.json` — fuente de verdad. Etiquetas en 4 idiomas (fijas)
  + valores editables (precio, visible).
- `scripts/build-web.py` — regenera las secciones de horarios y precios
  de los 4 HTML, solo entre `<!-- CONTENIDO:INICIO -->` y `<!-- CONTENIDO:FIN -->`.
- NocoDB (perfil negocio) — dos tablas que edita Julia.
- El rebuild se lanza con deploy.sh (o un disparo a configurar).

## Qué edita Julia en NocoDB
Tabla **Precios**: columnas `id` (fijo: suelta, bono4, bono8, infantil,
privada, bonopriv), `valor` (lo que cambia: "15", "72", "10 / 35"),
`visible` (sí/no). No hay columnas de idioma: el nombre de cada concepto
lo pone el generador en los 4 idiomas.

Tabla **Horarios**: `id` (fijo: nerja, maro, almunecar), `visible` (sí/no).
Para cambiar los textos de clases por ubicación (multiidioma) se edita
data/contenido.json (soporte técnico), no NocoDB.

## Flujo de actualización
1. Julia cambia un precio en NocoDB y guarda.
2. El rebuild se ejecuta con deploy.sh (o un futuro disparo por cron/webhook a Python).
3. deploy.sh ejecuta:
   `python3 /srv/scripts/build-web.py`
   (lee NocoDB, actualiza contenido.json y regenera los HTML).
4. La web (servida por nginx desde ./sitio) refleja el cambio en segundos.

## Puesta en marcha
1. Crear en NocoDB las tablas Precios y Horarios con las columnas de arriba
   e importar los `id` iniciales (ver data/contenido.json).
2. Generar un token de API en NocoDB.
3. Definir en el .env del VPS:
   NOCODB_URL=https://datos.juliamoreno.yoga/api/v2/tables/<id>/records
   NOCODB_TOKEN=<token>
   (o las variables NOCODB_TBL_PRECIOS / NOCODB_TBL_HORARIOS si se usan
   nombres en lugar de IDs de tabla)
4. (El disparo automático del rebuild queda pendiente de implementar en Python.)
5. Configurar en NocoDB un webhook "After Insert/Update" de ambas tablas
   apuntando al captador Python (api.juliamoreno.yoga).

## Ejecución manual (sin esperar al webhook)
```
cd /opt/docker/apps/juliamoreno
python3 scripts/build-web.py              # desde el JSON
python3 scripts/build-web.py  # sincroniza desde NocoDB
```
