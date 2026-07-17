# Rama calcom-centric — exploración

Rama aislada para evaluar, con hechos, si Cal.com puede ser la **base
del calendario y las reservas** (no un simple widget). No toca `main`:
si convence, se fusiona; si no, se descarta sin coste.

La decisión se toma solo con costes/beneficios futuros. Que Cal.com
esté desplegado o que exista el panel de Agenda no cuenta: se evalúa
qué da cada opción y qué trabajo queda.

## Punto crítico a validar

¿Se puede **leer de Cal.com por API** lo que la web pública y el panel
necesitan? Concretamente:
1. Los tipos de evento (las "clases") con sus plazas.
2. La disponibilidad / franjas reservables por rango de fechas
   (esto es lo que alimentaría la vista de disponibilidad de la web).
3. Las reservas (para la lista de alumnos por clase y los avisos).

Si esto funciona, Cal.com-centric es viable. Si no, se queda en
NocoDB-centric (main).

## Lo que hay en esta rama

- `scripts/backend/calcom/cliente.py` — cliente mínimo de la API v2.
- `scripts/backend/calcom/sonda.py` — prueba manual que ejercita los
  tres puntos y reporta OK/FALLO con el motivo.

## Requisito previo: levantar la API v2 de Cal.com

Hallazgo (17 jul): el Cal.com desplegado **solo tiene el webapp**
(contenedor `calcom`, puerto 3000, en reservas.juliamoreno.yoga). La
**API v2 es un contenedor aparte** que no está en el compose. Para
probar la sonda hay que levantarlo. Añadir al docker-compose.yml algo
como:

```yaml
  calcom-api:
    image: calcom/api:latest        # imagen de la API v2 de Cal.com
    container_name: jmy-cal-api
    restart: unless-stopped
    profiles: [todo]
    environment:
      DATABASE_URL: postgresql://julia:${PG_PASSWORD}@pg:5432/calcom
      NEXTAUTH_SECRET: ${CALCOM_SECRET}
      CALENDSO_ENCRYPTION_KEY: ${CALCOM_ENC_KEY}
      # otras vars según la doc de self-host de la API v2
    depends_on: [pg, calcom]
    networks: [internal, traefik_public]
    labels:
      - traefik.enable=true
      - traefik.docker.network=traefik_public
      - traefik.http.routers.jmy-cal-api.rule=Host(`api-reservas.juliamoreno.yoga`)
      - traefik.http.routers.jmy-cal-api.entrypoints=websecure
      - traefik.http.routers.jmy-cal-api.tls.certresolver=letsencrypt
      - traefik.http.services.jmy-cal-api.loadbalancer.server.port=80
```

(Los detalles exactos —imagen, puerto, variables— hay que tomarlos de
la doc de self-host de la API v2 de Cal.com; lo de arriba es la forma,
no la verdad literal.)

## Pasos de la exploración

1. **Levantar la API v2** (arriba) y comprobar que responde.
2. **Generar una API key** en Cal.com (Settings → Developer → API
   keys) para la sonda.
3. **Configurar en Cal.com una franja real** de Julia como evento
   recurrente con plazas: p. ej. "Hatha martes 19:00 · Nerja", 10
   plazas. Es la prueba de que el modelo "clase recurrente con aforo"
   encaja.
4. **Correr la sonda** en el VPS:
   ```
   CALCOM_API_URL=https://api-reservas.juliamoreno.yoga \
   CALCOM_API_KEY=cal_live_xxx \
   python3 -m backend.calcom.sonda
   ```
   Debe dar OK en los tres bloques (tipos, slots, reservas).
5. **Con los datos reales de la sonda**, decidir:
   - Si la disponibilidad se lee bien → probar a pintarla con el estilo
     de la web (mini-página que consuma slots).
   - Ver si la UI de Cal.com basta a Julia para gestionar, o si haría
     falta panel propio contra su API.
6. **Comparar** contra NocoDB-centric (main) con hechos y decidir el
   reparto. Solo entonces se toca `main`.

## Qué NO se hace todavía

No se migra nada de main, no se jubila el panel de Agenda, no se toca
la web pública. Esta rama solo prueba lecturas. La migración, si se
decide, es un paso posterior y consciente.

## Resultado (rellenar tras la exploración)

- [ ] API v2 levantada y respondiendo
- [ ] Franja recurrente con plazas creada en Cal.com
- [ ] Sonda: tipos de evento → OK / FALLO: ____
- [ ] Sonda: slots/disponibilidad → OK / FALLO: ____
- [ ] Sonda: reservas → OK / FALLO: ____
- [ ] Disponibilidad pintable con estilo web → sí / no
- [ ] UI de Cal.com suficiente para gestión → sí / no
- [ ] Decisión: Cal.com-centric / NocoDB-centric

## HALLAZGO (17 jul) — la API v2 self-hosted es costosa de levantar

Investigada la doc oficial y casos reales antes de tocar el VPS.
Resultado que pesa en la decisión:

- La **imagen Docker estándar de Cal.com NO arranca la API v2**. El
  servidor de la API (puerto 5555) no viene en la imagen; los
  workspaces @calcom/api-v2 / @calcom/api no están presentes en ella
  (issue #23911, discusión #17098).
- Para tener la API v2 hay que **compilar una imagen propia** desde
  `apps/api/v2` del monorepo, y hay gente atascada en el build
  (`yarn install` falla, exit 1 — discusión #19313).
- Cal.com **no da soporte oficial a Docker** ("use at your own risk").

Implicación: el camino Cal.com-centric no es "añadir un contenedor de
API", sino **mantener una imagen compilada a mano de un componente que
el propio Cal.com no soporta en Docker**. Eso es coste de integración
recurrente (cada actualización de Cal.com puede romper el build), no
de una sola vez.

### Efecto en el eje coste/beneficio
El beneficio de Cal.com (reservas/recordatorios/portal ya hechos)
sigue ahí, pero el **coste de integración sube bastante**: depender de
una API que hay que compilar y mantener uno mismo, sin soporte. Esto
acerca la balanza al camino NocoDB-centric, donde no hay esa
dependencia frágil.

### Alternativas dentro de Cal.com-centric (si aun así se quiere)
- **Embeber el booker de Cal.com** (iframe / atoms) en la web SIN usar
  la API v2: el alumno reserva en la UI de Cal.com. Se pierde el
  control fino de pintar la disponibilidad con estilo propio, pero se
  evita la API v2. Los webhooks (que sí funcionan en el webapp) llevan
  las reservas al backend.
- **Leer la base de datos de Cal.com directamente** (Postgres
  compartido) en vez de por API. Frágil (acopla a su esquema interno)
  pero evita la API v2. No recomendado.

### Estado
La sonda y el cliente de esta rama asumen la API v2. Si no se levanta,
esa vía queda bloqueada; habría que pivotar a "embeber booker +
webhooks" (sin API v2 de lectura) o descartar Cal.com-centric.

## HALLAZGO 2 (17 jul) — API keys self-hosted y muro Enterprise

Investigado más a fondo. Dos cosas nuevas, ambas pesan:

### A. Generar API keys en self-hosted parece requerir Enterprise (pago)
- Caso real (issue #23911): al intentar crear una API key en la UI de
  un self-hosted, salió "creación de API keys solo disponible en
  Enterprise". El usuario compró licencia Enterprise y entonces sí
  pudo crearla. Con imagen oficial estándar, v5.6.19.
- La doc oficial confirma que hay funciones self-hosted tras licencia
  comercial de pago (cal.com/docs/self-hosting/license-key).
- Contradicción: el FAQ oficial dice que la API y los webhooks están
  en el plan gratuito ("90% de las funciones"). Y otra fuente dice que
  en self-hosted "añades tu propia API key".
- Lectura probable: **generar API keys desde la UI está tras Enterprise
  en self-hosted; los webhooks sí funcionan gratis.** O sea: la vía
  "leer por API v2" (nuestra sonda) probablemente choca con Enterprise;
  la vía "webhooks + embeber booker" probablemente no. A confirmar en
  la instancia real.

### B. Cal.diy — la edición que de verdad corresponde
- Cal.com ha escindido la parte open source en **Cal.diy**. Cal.com,
  Inc. dice literalmente: Cal.diy es "community maintained y
  ESTRICTAMENTE recomendada para uso personal, NO de producción... use
  at your own risk". Para uso comercial/producción remiten a Cal.com
  (cloud) o a su on-prem Enterprise (ventas).
- Traducción sin adornos: la versión libre self-hosted que podríamos
  usar es la que ELLOS MISMOS desaconsejan para producción. El negocio
  de Julia es producción.

### Efecto en la decisión (importante)
Junta los tres hallazgos:
1. La API v2 no viene en la imagen estándar (hay que compilarla, con
   builds que fallan).
2. Generar API keys parece requerir Enterprise de pago en self-hosted.
3. La edición libre (Cal.diy) está oficialmente desaconsejada para
   producción.

El camino "Cal.com-centric por API v2" acumula: componente frágil a
compilar + probable muro de pago para la key + edición no recomendada
para producción. **El coste/riesgo de integración es alto y en parte
fuera de nuestro control** (depende de decisiones de licencia de un
tercero).

Queda viva una variante MÁS BARATA dentro de Cal.com:
- **Embeber el booker + webhooks** (sin API v2, sin API key de
  lectura). El alumno reserva en la UI de Cal.com; el webhook
  BOOKING_CREATED avisa al backend, que registra en NocoDB. Esto no
  necesita Enterprise (webhooks son gratis) ni compilar la API v2.
  Pierde: pintar disponibilidad con estilo propio (se usa el widget de
  Cal.com tal cual). Gana: coste bajo y sin dependencias frágiles.

### Recomendación de Claude (honesta)
Si se quiere Cal.com, ir por **embeber booker + webhooks**, NO por la
API v2. Pero visto lo visto (edición libre desaconsejada para
producción, muros de pago móviles), la opción **NocoDB-centric** —
construir reservas sobre lo que ya controlas al 100%— evita todo este
terreno movedizo. La exploración en rama ha cumplido su función:
destapar estos costes antes de invertir tiempo en el VPS.

## HALLAZGO 3 (17 jul) — middleware sí, pero solo de LECTURA

Explorada la idea de un middleware que aísle la UI y hable con Cal.com
por su base de datos PostgreSQL directamente (evitando la API y su muro
Enterprise). La base de Cal.com ya está en el mismo Postgres del
proyecto (DATABASE_URL ...@pg:5432/calcom), así que el backend la
alcanza sin abrir nada nuevo.

### Lo verificado del esquema (Prisma sobre Postgres)
- Tablas claras: EventType (clases; seatsPerTimeSlot = plazas,
  recurringEvent = recurrencia), Booking (reservas), Attendee.
- Existe precedente de leer y hasta escribir reservas por SQL (wrapper
  FDW de Cal.com). Técnicamente se puede.

### El riesgo de ESCRIBIR en su base (decisivo)
- El esquema lleva lógica de negocio dentro: bookingUid como string
  plano para auditoría, anonimización al borrar, etc.
- Crear una reserva en Cal.com dispara efectos: evento de calendario
  (EventManager), recordatorios obligatorios, validación de aforo,
  estado PENDING/ACCEPTED según requiresConfirmation.
- Insertar filas a mano SALTA todo eso: sin recordatorios, sin evento,
  sin validar plazas, y atado al esquema interno -> una actualización
  de Cal.com rompe el middleware en silencio.

### Recomendación de Claude (firme)
Middleware **solo de LECTURA**:
- Cal.com crea las reservas (booker/webhooks), con su lógica completa.
- El middleware LEE de su base: disponibilidad (plazas libres) y lista
  de reservas por clase. Leer es estable; no dispara efectos.
- La UI la controla la web propia (pinta disponibilidad leyendo del
  middleware; para reservar, booker embebido o redirección).
- Avisos y lista de alumnos salen de lo leído.

NO escribir en la base de Cal.com. Si se necesita crear reservas
programáticamente, es señal de que Cal.com no está aportando su valor
(su motor) y conviene NocoDB-centric.

### Conclusión del análisis (las dos opciones netas)
1. **Cal.com de solo lectura + UI propia** — usa el motor de Cal.com
   para crear/validar/recordar; el middleware solo lee. Menos frágil
   que escribir. Pero arrastra que la edición libre (Cal.diy) está
   desaconsejada para producción por la propia Cal.com.
2. **NocoDB-centric** — reservas sobre lo que ya se controla al 100%,
   sin terceros con licencias movedizas. Más construcción, cero
   dependencia frágil.

Recomendación global: si Cal.com, opción 1 (leer, no escribir). Pero la
más limpia y sin sorpresas de terceros es NocoDB-centric. Decisión del
usuario pendiente; el análisis está cerrado.

## PLAN — intentar el build de la API v2 en el VPS (17 jul)

Decisión: intentarlo y leer los errores reales antes de descartar. Va
en esta rama, no toca main. Coste acotado (una tarde).

### Datos del VPS a confirmar antes (rellenar):
- arch: ____   RAM: ____   disco libre: ____
- redis corriendo: sí/no
- versión imagen calcom actual: ____

Importante: el build de la API v2 necesita ~4GB RAM. Si el VPS tiene
menos, el `yarn install` puede morir por OOM (esa es una causa real del
"exit code 1" que se ve en los foros, no siempre es un bug del código).

### Estrategia para evitar el error "Workspace @calcom/api-v2 not found"
Ese error sale al intentar arrancar la API con la imagen del WEBAPP
(que no contiene ese workspace). La vía correcta es BUILDAR la imagen
de la API desde el Dockerfile propio del monorepo:
  apps/api/v2/  (tiene su Dockerfile)

### Pasos
1. Clonar el monorepo EN LA MISMA VERSIÓN que corre el webapp (para que
   el esquema de la base coincida):
     cd /opt/docker/apps/juliamoreno    # o donde se prefiera
     git clone --depth 1 --branch <VERSION> https://github.com/calcom/cal.com.git calcom-src
   (VERSION = la que devuelva el inspect del contenedor, p.ej. v5.6.x)

2. Redis: si no hay, añadir un contenedor redis al stack (la API v2 lo
   exige por REDIS_URL).

3. Build de la API v2 con su Dockerfile:
     cd calcom-src
     docker build -f apps/api/v2/Dockerfile -t jmy-cal-api:local .
   —> AQUÍ es donde saldrán los errores reveladores. Guardar el log
      completo: docker build ... 2>&1 | tee /tmp/calapi-build.log

4. Según el error:
   - "yarn install exit 1" + OOM en dmesg -> falta RAM: añadir swap
     temporal (fallocate 4G) y reintentar.
   - "Workspace not found" -> se está buildando desde el contexto/
     Dockerfile equivocado; usar el de apps/api/v2.
   - fallo de prisma/DATABASE_URL en build -> pasar las vars de build.
   - fallo de versión de node/yarn -> el Dockerfile del monorepo fija
     la suya; no forzar otra.

5. Si la imagen se construye, levantarla apuntando al Postgres de
   calcom (mismo DATABASE_URL que el webapp) + Redis, exponer por
   Traefik en api-reservas.juliamoreno.yoga, y correr la sonda
   (backend/calcom/sonda.py).

### Regla
Cada error que salga, pegarlo tal cual y diagnosticarlo. Muchos "exit
1" son entorno (RAM, contexto de build), no bugs irresolubles. El log
completo es lo que dice la verdad.
