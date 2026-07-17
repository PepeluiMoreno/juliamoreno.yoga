# Reservas, disponibilidad, bonos y avisos — diseño unificado

Documento de trabajo que fija la arquitectura antes de construir.
Unifica y sustituye a los anteriores `reservas-y-bonos.md` y
`diseno-reservas-avisos.md`. No es código: es la decisión de qué hace
cada pieza y por qué.

Fecha: 17 jul 2026.

## 1. Qué se quiere resolver

1. Que el alumno vea la **disponibilidad real** de clases y pueda
   **reservar** su plaza.
2. Una **vista de disponibilidad reutilizable** (web pública y donde
   convenga).
3. En admin, por cada clase, la **lista de alumnos apuntados**, como
   grupo destinatario de **avisos** ("traed esterilla", "nos
   retrasamos 10 min"), enviados solo a quien va a esa clase.
4. **Bonos** (4/8 clases) que se descuentan al asistir, con caducidad.

## 2. La decisión: construir sobre NocoDB, no traer Cal.com

Se valoró con el criterio coste/beneficio correcto: **idoneidad
funcional** como beneficio, **coste de integración** como coste.

**Cal.com** (ya desplegado en reservas.juliamoreno.yoga):
- Idoneidad alta: motor de reservas completo (plazas, recordatorios,
  portal de autoservicio, webhooks).
- Coste de integración alto: introduce una **segunda fuente de verdad
  de la semana tipo** (las franjas viven en Cal.com y en la matriz de
  Clases de NocoDB), obliga a sincronizar o vigilar deriva, añade un
  servicio de pegamento por webhooks y una pieza pesada que mantener.

**Construir sobre NocoDB + el backend existente:**
- Idoneidad media: hay que escribir reserva y aforo (poco), pero
  "apuntarse y ver plazas" es sencillo sobre la Agenda que ya existe.
- Coste de integración bajo: **una sola fuente de verdad**. Agenda,
  clases, alumnos y reservas viven todos en NocoDB. Sin sincronizar
  dos calendarios. Encaja con el panel ya construido.

**Decisión (17 jul 2026):** construir sobre **NocoDB + backend**.
Motivos, según lo que se usará de verdad:
- Del motor de reservas solo se usará **apuntarse y ver plazas**; lo
  demás (recordatorios, portal, pagos) lo lleva Julia/el sistema. Es
  decir, de la alta idoneidad de Cal.com se aprovecharía muy poco.
- Pesa más **evitar duplicar la semana tipo**: una sola fuente de
  verdad (NocoDB) que dos calendarios que mantener sincronizados.

Cuando el beneficio aprovechable es pequeño y el coste que importa es
alto, la balanza cae del lado de construirlo en NocoDB.

Cal.com queda desplegado pero **fuera de este flujo**. Puede retirarse
del compose más adelante si no se le da otro uso (revisar antes de
tocar). InvoiceNinja: **solo facturación a demanda** (si un alumno
pide factura); no es registro de alumnos ni motor de reservas.

## 3. Reparto de piezas

- **NocoDB** (base Yoga) — fuente de verdad única: oferta
  (actividades, agenda/ocurrencias, tarifas), **alumnos**, **bonos**,
  **reservas** y **aforo**.
- **backend** (servicio Python del panel) — expone los endpoints de
  reserva (públicos, con aforo) y la consulta de alumnos por clase.
- **Listmonk** — envío de avisos y boletines.
- **InvoiceNinja** — facturación a demanda, opcional, aparte.

## 4. Modelo de datos en NocoDB (a cerrar)

- **Agenda** (ya existe): cada ocurrencia gana `plazas` (aforo) y un
  `plazas_libres` calculado o derivado del recuento de reservas.
  `visible_web` pasa a significar "abierta a reserva".
- **Alumnos** (nueva): nombre, contacto, consentimiento RGPD.
- **Bonos** (nueva): alumno, tipo 4/8, fecha, caducidad (= fecha + 1
  mes, campo calculado), créditos restantes.
- **Reservas** (nueva): alumno + ocurrencia (id de Agenda) + estado
  (reservada/asistida/cancelada) + bono del que se descuenta.

El aforo se controla contando reservas activas de cada ocurrencia.

## 5. Flujo de reserva (apuntarse + ver plazas)

1. El alumno abre "Contratar clases" -> ve la disponibilidad
   (ocurrencias con plazas libres, calculadas desde Reservas).
2. Elige ocurrencia con plazas libres.
3. Se identifica / da datos (consentimiento RGPD explícito).
4. El backend crea la Reserva y, si tiene bono activo, descuenta un
   crédito del más antiguo no caducado; si no, marca "pendiente de
   cobro" y avisa a Julia.
5. Plazas libres de la ocurrencia baja en uno (por recuento).

Sin recordatorios automáticos ni portal de autoservicio en esta fase:
"lo demás lo lleva Julia".

## 6. Flujo de bonos

1. Venta de bono: se registra en NocoDB (tabla Bonos).
2. Al reservar/asistir: descuenta 1 crédito del bono activo más
   antiguo no caducado; si no hay saldo, aviso a Julia ("cobrar suelta
   o vender bono").
3. Cancelación con antelación > X horas: devuelve el crédito.
4. Diario 9:00 (tarea programada del backend): bonos que caducan en 3
   días -> aviso de renovación al alumno.

## 7. Disponibilidad reutilizable

Endpoint público de solo lectura en el backend: dado actividad o
rango, devuelve ocurrencias con fecha, hora, lugar, plazas totales y
libres, estado (abierta/llena/cerrada/cancelada). Solo aforo, **nunca
nombres**. Un componente de front lo pinta con el estilo de la web;
se embebe en la web pública ("Contratar clases") y en admin si hace
falta. Reutiliza la lógica de la Agenda que ya existe.

## 8. Lista de alumnos por clase + avisos (admin)

Lo que motivó la conversación:

- En la ficha de una ocurrencia, admin pide al backend las reservas
  activas de esa ocurrencia -> lista de alumnos (sale directa de
  NocoDB, sin sistemas externos).
- Esa lista es el **grupo destinatario** de un aviso puntual.
- Envío vía **Listmonk** (o correo directo del backend): mensaje corto
  solo a quien tiene reserva en esa clase. Copia oculta / envíos
  individuales: un alumno nunca ve a otro.
- Reutiliza la intención `avisar_alumnos` que ya se guarda en las
  ocurrencias de la Agenda; ahora con destinatarios reales.

## 9. Talleres y retiros

Mismo mecanismo: ocurrencia puntual con plazas. Cobro por
Bizum/transferencia (0% comisión). Pago online (Stripe ~1,5%+0,25€) es
decisión aparte, solo si se quiere.

## 10. Privacidad (RGPD)

- Datos personales de alumnos: NocoDB, autoalojado, bajo control
  propio. Una sola ubicación, más fácil de auditar y de ejercer
  derechos (acceso, borrado).
- La vista pública de disponibilidad solo muestra aforo, nunca quién.
- Avisos con copia oculta / individuales.
- Consentimiento explícito al reservar.
- InvoiceNinja solo si hay factura; ahí van datos fiscales.

## 11. Orden de trabajo propuesto

1. Modelo de datos en NocoDB: tablas Alumnos, Bonos, Reservas; campo
   plazas en Agenda.
2. Endpoint público de disponibilidad (solo aforo) + componente de
   front reutilizable.
3. Flujo de reserva en el backend (crear reserva, recuento de aforo).
4. Lógica de bonos (descuento, caducidad, tarea diaria).
5. Lista de alumnos por clase en admin.
6. Avisos al grupo de una clase vía Listmonk.
7. (Opcional) Facturación con InvoiceNinja a demanda.

Cada paso es entregable por separado. El 1 condiciona el resto.

## 12. Preguntas abiertas

- Aforo: ¿`plazas_libres` como campo calculado en NocoDB, o recuento
  en vivo en el backend al pedir disponibilidad? (rendimiento vs
  simplicidad).
- Reserva sin cuenta: ¿el alumno reserva solo con email/teléfono, o se
  crea algún acceso? (afecta a la fricción y al RGPD).
- Cancelación por el alumno: ¿se permite desde la web, o solo avisando
  a Julia? (si se permite, hace falta algo de "portal", que era justo
  lo que se decidió no construir ahora).
- Avisos: ¿Listmonk o correo directo del backend? ¿remitente?
- ¿Se retira Cal.com del compose, o se deja por si se le da otro uso?
