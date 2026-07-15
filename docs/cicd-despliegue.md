# CI/CD — despliegue automático del código

Cuando se hace `git push` a main (cambios en la web, datos, generador o
compose), el VPS se actualiza solo. Dos vías; elegir una.

## Vía A — GitHub Actions
(El fichero de workflow no se versiona en este repo porque requiere que el
token de push tenga scope `workflow`. Si se quiere usar, crear a mano
.github/workflows/deploy.yml desde un cliente con permisos, con el
contenido de ejemplo de docs/ejemplo-github-actions.txt.)
1. En el VPS, crear un par de claves SSH para el deploy:
   `ssh-keygen -t ed25519 -f ~/.ssh/deploy_jmy -C deploy-jmy`
   y añadir la pública a ~/.ssh/authorized_keys del usuario que despliega.
2. En GitHub → repo → Settings → Secrets and variables → Actions, crear:
   - VPS_HOST = 167.86.123.88
   - VPS_USER = jose
   - VPS_SSH_KEY = (contenido de la clave privada deploy_jmy)
3. Listo: cada push a main que toque sitio/, data/, scripts/ o el compose
   dispara el pull + rebuild en el VPS. Sin git pull manual.

## Vía B — script + webhook en el VPS (RECOMENDADA, sin dar acceso a GitHub)
Fichero: scripts/deploy.sh
- Uso manual inmediato: `./scripts/deploy.sh`
- Como webhook automático: instalar un listener ligero (p. ej. el paquete
  `webhook` de adnanh) que ejecute deploy.sh al recibir el webhook de
  GitHub (repo → Settings → Webhooks → payload URL del listener).
  Proteger con un secreto compartido. Enrutarlo por Traefik en un
  subdominio tipo deploy.juliamoreno.yoga si se quiere HTTPS.

## Relación con el flujo de contenido
- CI/CD (esto) despliega CÓDIGO: lo que cambian Jose/soporte con push.
- El workflow n8n de contenido despliega CONTENIDO: lo que cambia Julia
  en NocoDB (precios, horarios, actividades). Ese llama a build-web.py
  leyendo NocoDB por defecto, y no pasa por git.
Ambos acaban ejecutando build-web.py; son disparadores distintos para
editores distintos.
