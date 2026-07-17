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
