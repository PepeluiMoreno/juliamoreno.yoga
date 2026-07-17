# Reservas, disponibilidad y avisos (MOTOR DECIDIDO: Cal.diy)

## Qué es
El módulo que permite a los alumnos ver disponibilidad y reservar
plaza, a Julia avisar solo a los apuntados de cada clase, y llevar
bonos (4/8 clases con caducidad).

Estado (17 jul 2026): **decisión tomada — Cal.diy-centric**. El
levantamiento en el VPS validó el punto crítico (API v2 self-hosted
sin licencia, slots con aforo por hueco, sonda 3/3 OK). La rama
calcom-centric se promocionó a main; el main anterior quedó en
main-salvaguarda-20260717.

## Cómo queda resuelto
- **Cal.diy** (stack propio en el VPS, reservas. y
  api-reservas.juliamoreno.yoga): motor de calendario, reservas y
  aforo. Su UI es la trastienda de gestión (separación
  tienda/trastienda, asumida como ventaja).
- Cada clase = tipo de evento con seats + disponibilidad restringida a
  su franja (NO la función recurring, que es excluyente con seats y
  significa otra cosa: un mismo reservante se lleva la serie).
- **NocoDB**: actividades, tarifas, textos web y bonos.
- **backend**: lee la API (versiones por recurso), recibe webhooks
  BOOKING_CREATED/CANCELLED, aplica bonos, avisa (Listmonk a alumnos,
  Telegram a Julia).
- Regla de oro: el motor de Cal.diy escribe; el resto solo lee.

## Decisiones tomadas
- Cal.diy sustituye (no duplica) la semana tipo: desaparece la
  objeción original a Cal.com.
- Riesgo community asumido: sin soporte, con backups y salvaguarda.
- El panel /admin propio conserva lo que no es calendario.
- RGPD: aforo público, nombres nunca; "share attendee info" apagado.

## Pendiente
- Mini-página de disponibilidad con estilo web (consume slots).
- Valorar la UI de Cal.diy con ojos de Julia.
- Webhooks + Telegram; bonos en NocoDB; avisos Listmonk.
- Clases reales en Cal.diy y conexión de la web.
- Infra: retirar calcom viejo del compose, SMTP de Cal.diy, backups de
  su Postgres, endurecer credenciales, revocar API key de exploración,
  2FA.

## Ficheros
- docs/reservas-avisos-disponibilidad.md — diseño detallado vigente.
- docs/rama-calcom-centric.md — historia de la exploración (hallazgos
  1-7, levantamiento, promoción).
- scripts/backend/calcom/ — cliente API v2 y sonda.
