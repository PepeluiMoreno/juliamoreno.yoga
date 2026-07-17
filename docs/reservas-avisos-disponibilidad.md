# Reservas, disponibilidad, bonos y avisos — diseño (Cal.diy-centric)

Documento de diseño del módulo de reservas. Sustituye a la versión
anterior de este fichero, que recogía la decisión provisional
NocoDB-centric y el análisis de alternativas. La historia completa de
cómo se llegó aquí (hallazgos 1-7, levantamiento y validación) está en
docs/rama-calcom-centric.md; no se repite.

Fecha: 17 jul 2026.
Decisión: **Cal.diy como motor del calendario y las reservas.**
El main anterior (con la vía NocoDB-centric aún abierta) queda en la
rama de salvaguarda main-salvaguarda-20260717.

## 1. Qué se quiere resolver

1. Que el alumno vea la **disponibilidad real** de clases y pueda
   **reservar** su plaza.
2. Una **vista de disponibilidad reutilizable** (web pública y donde
   convenga), con el estilo de la web.
3. En gestión, por cada clase, la **lista de alumnos apuntados**, como
   grupo destinatario de **avisos** solo a quien va a esa clase.
4. **Bonos** (4/8 clases) que se descuentan al asistir, con caducidad.

## 2. Por qué Cal.diy

- La objeción original a Cal.com (duplicar la semana tipo) desaparece
  al plantearlo como sustitución del calendario, no como duplicado.
- Los muros que mataban la vía (API v2 no incluida en la imagen, API
  keys tras Enterprise) eran del Cal.com cerrado. Cal.diy (fork MIT
  tras el cierre de abril 2026) conserva la API v2 y genera keys sin
  licencia.
- Verificado en el VPS (17 jul): stack levantado, API v2 operativa,
  sonda 3/3 OK — tipos de evento, slots con aforo por hueco
  (seatsBooked/seatsRemaining/seatsTotal) y reservas.
- Riesgo asumido conscientemente: Cal.diy es community y sus autores
  lo desaconsejan para producción por SOPORTE/SEGURIDAD (no por
  capacidad ni licencia). Para un negocio pequeño autohospedado con
  backups es asumible; la salvaguarda permite volver atrás.

## 3. Reparto de piezas

- **Cal.diy** — el motor: calendario, disponibilidad, reservas, aforo,
  confirmaciones y cancelaciones. Su UI es la **trastienda** de
  gestión de Julia (separación tienda/trastienda, aceptada como
  ventaja). Corre como stack propio en /opt/docker/apps/cal.diy
  (Postgres y Redis propios), expuesto en reservas. y
  api-reservas.juliamoreno.yoga.
- **NocoDB** (base Yoga) — lo que no es calendario: actividades y su
  ciclo de estados, tarifas, textos de la web multi-idioma, y la
  contabilidad de **bonos**.
- **backend** (Python) — el pegamento: lee la API v2 de Cal.diy
  (disponibilidad, reservas), recibe sus webhooks, aplica la lógica de
  bonos, dispara avisos y genera la web pública.
- **Listmonk** — correo a alumnos. **Telegram** (bot) — avisos a
  Julia ("nuevo alumno apuntado a la clase del jueves").
- **InvoiceNinja** — facturación a demanda, aparte.

## 4. Modelado de la clase en Cal.diy

- Cada clase es un **tipo de evento NO recurrente con seats** (aforo)
  cuya **disponibilidad está restringida a su franja** (p. ej. horario
  "Hatha martes" con un único tramo martes 19:00-20:00).
- La función "recurring" de Cal.com NO se usa: significa que un mismo
  reservante se lleva la serie entera, y además es excluyente con
  seats (verificado en la UI). La repetición semanal la pone la
  disponibilidad.
- Con esto, el endpoint de slots devuelve exactamente las ocurrencias
  de la clase, cada una con su aforo — lo que la web necesita.
- RGPD en cada evento: "Share attendee information between guests"
  DESMARCADO (los alumnos no se ven entre sí); "Show the number of
  available seats" marcado (el aforo sí es público).

## 5. Regla de oro: el motor escribe, el resto lee

- Las reservas las crea SIEMPRE el motor de Cal.diy (booker embebido o
  enlazado desde la web). Nunca se escribe a mano en su base de datos
  ni se crean reservas por fuera: saltaría su lógica (validación de
  aforo, confirmaciones) y ataría al esquema interno.
- El backend solo LEE su API (slots, bookings) y RECIBE sus webhooks.
  Versiones de cabecera cal-api-version por recurso: event-types
  2024-06-14, slots 2024-09-04, bookings 2024-08-13 (ver cliente.py).

## 6. Flujo de reserva

1. La web pública pinta la disponibilidad con su estilo (el backend
   lee slots y expone un endpoint propio de solo aforo).
2. El alumno reserva en el booker de Cal.diy (embebido o enlazado),
   con consentimiento RGPD explícito.
3. Webhook BOOKING_CREATED (firmado HMAC) llega al backend
   (handlers/webhooks.py): registra, descuenta bono si lo hay (o marca
   pendiente de cobro), avisa a Julia por Telegram.
4. BOOKING_CANCELLED: devuelve crédito si procede y avisa.

## 7. Bonos

Viven FUERA de Cal.diy (NocoDB + backend), como estaba diseñado:
- Bonos (tabla): alumno, tipo 4/8, fecha, caducidad (fecha + 1 mes),
  créditos restantes.
- Al llegar BOOKING_CREATED se descuenta 1 crédito del bono activo más
  antiguo no caducado; sin saldo, aviso a Julia ("cobrar suelta o
  vender bono").
- Cancelación con antelación > X horas: devuelve el crédito.
- Tarea diaria del backend: bonos que caducan en 3 días -> aviso de
  renovación al alumno. Venta de bono -> aviso a Julia por Telegram.

## 8. Lista de alumnos por clase + avisos

- La lista sale de la API de bookings de Cal.diy filtrada por la
  ocurrencia (o del registro que el backend mantiene vía webhooks).
- Aviso puntual solo a ese grupo, vía Listmonk o correo del backend;
  copia oculta / envíos individuales: un alumno nunca ve a otro.

## 9. RGPD

- Datos personales en servicios autohospedados (Cal.diy y NocoDB),
  bajo control propio.
- La vista pública de disponibilidad muestra solo aforo, nunca nombres.
- Consentimiento explícito al reservar. InvoiceNinja solo si hay
  factura.

## 10. Orden de trabajo

1. Mini-página de disponibilidad con estilo web consumiendo slots
   (valida el punto que queda de la exploración).
2. Valorar la UI de Cal.diy como trastienda con ojos de Julia.
3. Endpoint de webhooks en el backend (BOOKING_CREATED/CANCELLED,
   verificación HMAC) + aviso Telegram a Julia.
4. Modelo de bonos en NocoDB y su lógica en el backend.
5. Avisos por clase vía Listmonk.
6. Configurar las clases reales de Julia en Cal.diy y conectar la web.
7. Limpieza e integración de infraestructura: retirar el servicio
   calcom viejo del compose del proyecto, decidir si el stack cal.diy
   se integra en el compose o sigue aparte, endurecer credenciales de
   su Postgres, backups (restic) de su base, SMTP (EMAIL_FROM /
   EMAIL_SERVER_*, hoy sin configurar: las confirmaciones por correo
   no salen), revocar la API key de la exploración y 2FA de la cuenta
   admin.

## 11. Preguntas abiertas

- ¿Stack cal.diy dentro del compose del proyecto o aparte? (backups y
  operación hablan de integrarlo; el aislamiento, de dejarlo aparte).
- Identificación del alumno al reservar: solo email/teléfono en el
  booker, ¿basta?
- Ventana de cancelación X horas para devolver crédito (definir X).
- Remitente y SMTP definitivos de Cal.diy y de los avisos.
- Qué se retira del panel /admin propio y qué se conserva (todo lo que
  no es calendario se conserva).
