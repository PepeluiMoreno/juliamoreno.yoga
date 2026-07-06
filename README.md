# juliamoreno.yoga

Presencia digital y herramientas de negocio de **Julia Moreno · Yoga**
(Hatha yoga en Nerja, Maro y Almuñécar).

## Estructura
- `sitio/` — web estática en 4 idiomas (ES raíz, `/en/`, `/fr/`, `/de/`),
  SEO local, schema LocalBusiness, hreflang y sitemap.
- `docker-compose.yml` — todo el despliegue, con perfiles:
  - `web`: solo el sitio (nginx tras Traefik, TLS automático,
    redirección canónica desde www y juliamorenoyoga.com).
  - `negocio`: Postgres + Umami (analítica sin cookies). El mínimo para medir.
  - `todo`: añade Cal.com (reservas), Listmonk (boletín),
    n8n (automatizaciones) y NocoDB (alumnos/bonos).
- `nginx/sitio.conf` — configuración del sitio (gzip, caché, cabeceras).
- `stack/initdb/` — creación de las BDs del stack.
- `scripts/bootstrap-secrets.sh` — genera .env y secretos (solo en el VPS).
- `docs/` — guía de despliegue y generador del manual de usuario.

## Despliegue
```bash
git clone <repo> /opt/juliamoreno && cd /opt/juliamoreno
./scripts/bootstrap-secrets.sh
docker compose --profile web up -d        # el sitio
docker compose --profile negocio up -d    # + analítica
# más adelante:
docker compose --profile todo up -d
```
Requisitos: Traefik en la red externa `proxy` con entrypoint `websecure`
y certresolver `letsencrypt`; DNS del dominio y subdominios
(stats, reservas, correo, auto, datos) apuntando al VPS.

## Reglas del repo
- Ni `.env` ni `secrets/` se versionan jamás (ver .gitignore).
- Los paneles `auto.` y `datos.` deben protegerse con Authelia u
  otro middleware de autenticación en Traefik: son internos.
- Marcadores pendientes en `sitio/`: [TELÉFONO], [DIRECCIÓN],
  [DÍA]/[HORA], [PRECIO], usuario de Instagram.
