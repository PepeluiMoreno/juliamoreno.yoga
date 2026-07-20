# Levantar el proyecto en otra máquina (WSL)

Clonar el repositorio **no basta**: hay cosas que a propósito no están en git.
Esto es lo que hay que llevarse aparte y en qué orden montarlo.

## Lo que no viaja en el clon

| Qué | Dónde está en el VPS | Por qué no está en git |
|---|---|---|
| `.env` | raíz del proyecto | credenciales de NocoDB, Cal.diy y DeepL |
| `backups/*.json` | `backups/` | llevan nombres, correos y teléfonos de alumnos |
| `sitio/uploads/` | fotos subidas desde el panel | datos de producción |
| Los datos de NocoDB | volumen del contenedor `jmy-pg` | no son ficheros del repo |

Cópialos con `scp` desde el VPS antes de parar nada:

```bash
scp usuario@juliamoreno.yoga:/opt/docker/apps/juliamoreno/.env .
scp -r usuario@juliamoreno.yoga:/opt/docker/apps/juliamoreno/backups .
scp -r usuario@juliamoreno.yoga:/opt/docker/apps/juliamoreno/sitio/uploads sitio/
```

## Los datos: dos caminos

**El fácil** — repoblar desde cero con el sembrado de prueba. Sirve para
desarrollar, no conserva nada de lo que hubiera:

```bash
python3 scripts/provision-nocodb.py --seed-demo
```

**El fiel** — restaurar el volcado de `backups/`. Es un JSON con todas las
tablas, incluidas las filas en papelera. No hay script de restauración escrito
todavía: habría que recorrerlo y reinsertar por la API de NocoDB, tabla por
tabla, respetando que los `uuid` son los que enlazan unas con otras.

## Orden de arranque

1. **NocoDB** en marcha y accesible en la URL que diga el `.env`.
2. `python3 scripts/provision-nocodb.py` — crea las tablas y columnas que
   falten. Es idempotente y no borra nada.
3. Poblar (una de las dos vías de arriba).
4. **Backend**: `python3 -m backend` desde `scripts/`, o el contenedor
   `jmy-backend` con el compose.
5. `python3 scripts/build-web.py` para regenerar la web con lo que haya.

## Cuidado con esto

- **`--seed-demo` es destructivo**: vacía Servicios, Actividades, Clases, Agenda
  y Reservas antes de sembrar. En una base con datos buenos, se pierden.
- **El backend cachea el código en memoria**: tras tocar un `.py` hay que
  reiniciarlo (`docker restart jmy-backend`) o los cambios no se ven.
- **El panel no tiene runtime de JS propio**. Para validarlo se usa el node del
  contenedor de Cal.diy; si en WSL tienes node instalado, mejor:
  `node --check` sobre el JS extraído de `sitio/admin/index.html`.
- **Authelia protege `/admin`**. Sin él delante, el backend rechaza las
  peticiones porque exige la cabecera `Remote-User`.

## Parar el stack en el VPS

Los contenedores de Julia son estos cinco:

```bash
docker stop jmy-web jmy-backend jmy-nocodb jmy-umami jmy-pg
```

Parar `jmy-web` tira la web pública; `jmy-nocodb` y `jmy-pg`, el acceso a los
datos. Se revierte con `docker start` en orden inverso (`jmy-pg` primero, que
los demás dependen de él). Los datos siguen en los volúmenes: parar no borra.

El VPS lo comparten pepelui.es y juliamoreno.yoga —misma IP, mismo servidor—,
así que **el resto de contenedores no son de este proyecto** y conviene no
tocarlos: traefik, authelia, grafana, prometheus, ckan, portainer y el stack de
Cal.diy (`caldiy-calcom-1`, `calcom-api`, `database`, `redis`).
