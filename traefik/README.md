# Traefik del VPS

Puesta en marcha (una sola vez):
```bash
cd traefik
docker network create proxy
touch acme.json && chmod 600 acme.json
sudo apt install -y apache2-utils && htpasswd -nb admin 'CONTRASEÑA' > usersfile
cp .env.example .env   # y poner el correo real para Let's Encrypt
docker compose up -d
```

## DNS necesario (zona juliamoreno.yoga, todo a la IP del VPS)
| Registro | Nombre    | Destino            | Uso                    |
|----------|-----------|--------------------|------------------------|
| A        | @         | IP del VPS         | web                    |
| CNAME    | www       | juliamoreno.yoga.  | redirección canónica   |
| CNAME    | stats     | juliamoreno.yoga.  | Umami (analítica)      |
| CNAME    | reservas  | juliamoreno.yoga.  | Cal.com                |
| CNAME    | correo    | juliamoreno.yoga.  | Listmonk               |
| CNAME    | auto      | juliamoreno.yoga.  | n8n (proteger)         |
| CNAME    | datos     | juliamoreno.yoga.  | NocoDB (proteger)      |
| CNAME    | panel     | juliamoreno.yoga.  | dashboard Traefik      |

Y en juliamorenoyoga.com: `A @ -> IP del VPS` y `CNAME www` (la 301 al
.yoga la hace el router del sitio).

Los certificados TLS se emiten solos en el primer acceso a cada host.
