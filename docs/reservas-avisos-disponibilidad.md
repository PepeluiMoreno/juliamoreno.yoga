# Reservas, disponibilidad, bonos y avisos — diseño unificado

Documento de trabajo que fija la arquitectura antes de construir.
Unifica y sustituye a los anteriores `reservas-y-bonos.md` y
`diseno-reservas-avisos.md` (que se contradecían en el motor de
reservas). No es código: es la decisión de qué hace cada pieza.

Fecha: 17 jul 2026.

## 1. Qué se quiere resolver

Encadenado, surgió así:

1. Que el alumno vea la **disponibilidad real** de clases y pueda
   **reservar** su plaza.
2. Una **vista de disponibilidad reutilizable** (web pública y donde
   convenga).
3. En admin, por cada clase, la **lista de alumnos apuntados**, como
   grupo destinatario de **avisos** ("traed esterilla", "nos
   retrasamos 10 min"), enviados solo a quien va a esa clase.
4. **Bonos** (4/8 clases) que se descuentan al asistir, con caducidad.

## 2. Reparto de piezas (todas YA desplegadas en el compose)

No hay que instalar nada nuevo. El diseño reparte roles entre lo que
ya existe:

- **Cal.com** (reservas.juliamoreno.yoga) — **motor de reservas y
  disponibilidad**. Es lo que sabe hacer: franjas con plazas (seats),
  calendario público, confirmaciones y recordatorios automáticos,
  webhooks. Aquí vive el "apuntarse" y la vista de disponibilidad.
- **NocoDB** (base Yoga) — fuente de verdad de **oferta** (actividades,
  agenda/ocurrencias, tarifas) y de **alumnos y bonos**.
- **InvoiceNinja** — **facturación/pagos** cuando haga falta factura
  formal o cobro recurrente. NO es el registro de alumnos ni de
  reservas. Se usa solo si se quiere emitir factura.
- **Listmonk** — envío de correo (avisos y boletines).
- **backend** (el servicio Python del panel) — el pegamento: recibe
  webhooks de Cal.com y mantiene NocoDB coherente.

Decisión de fondo: **Cal.com es el motor de reservas** (no
InvoiceNinja, que es facturación; no NocoDB, que no es un motor de
reservas). Esto corrige el documento que se empezó el 17 jul, que
metía InvoiceNinja donde va Cal.com.

## 3. Por qué Cal.com y no InvoiceNinja para reservar

InvoiceNinja es facturación (cliente -> factura -> pago). Modelar
"reservar plaza en la clase del martes, controlar aforo, recordar"
sobre él sería forzarlo. Cal.com hace justo eso de fábrica: eventos
recurrentes con plazas, disponibilidad, recordatorios, webhooks. Se
verificó (17 jul) que la API de InvoiceNinja *podría* soportar un
apaño con custom_values, pero no es su terreno. Cal.com encaja sin
deformar nada.

InvoiceNinja se reserva para lo suyo: si un alumno pide factura, o
para cobros recurrentes formales. Es opcional en el flujo.

## 4. Configuración en Cal.com

Tipos de evento:
1. "Clase de prueba" — 60 min, individual, confirmación automática.
2. "Clase privada" / "Valoración inicial" — 60-75 min, individual.
3. Un evento RECURRENTE por franja de grupo, con PLAZAS (seats):
   "Hatha martes 19:00 · Nerja" 10 plazas, "Maro jueves 10:00" 12,
   "Almuñécar viernes 18:00" 12. El alumno reserva su plaza y recibe
   confirmación y recordatorio automáticos.

Las franjas de Cal.com se corresponden con la matriz de Clases de
NocoDB (la semana tipo). Pendiente decidir si se sincronizan
automáticamente o se mantienen a mano (ver preguntas abiertas).

## 5. Flujo de bonos (sin apunte manual)

1. Venta de bono: Julia lo registra en NocoDB (tabla Bonos: alumno,
   tipo 4/8, fecha; caducidad = fecha + 1 mes, campo calculado).
2. Webhook Cal.com BOOKING_CREATED -> backend:
   - busca al alumno en NocoDB por email/teléfono (lo crea si es nuevo),
   - registra la asistencia prevista,
   - descuenta 1 crédito del bono activo más antiguo no caducado,
   - si no hay bono con saldo: aviso a Julia (Telegram/correo):
     "cobrar clase suelta o vender bono".
3. BOOKING_CANCELLED -> devuelve el crédito si la cancelación llega
   con más de X horas.
4. Diario 9:00: bonos que caducan en 3 días -> aviso de renovación al
   alumno; primera reserva completada -> petición de reseña de Google
   a las 3 horas.

## 6. Disponibilidad reutilizable

La vista de disponibilidad se resuelve con el **calendario público de
Cal.com** embebido, o con un endpoint propio que lea la disponibilidad
de Cal.com y la pinte con el estilo de la web. Solo lectura, solo
aforo: nunca muestra nombres de otros alumnos. Se puede embeber en la
web pública ("Contratar clases") y en el propio admin si conviene.

## 7. Lista de alumnos por clase + avisos (admin)

Lo que motivó la conversación del 17 jul:

- Cal.com sabe quién ha reservado cada ocurrencia (attendees de la
  reserva con seats). El backend consulta esa lista para una fecha/
  franja concreta.
- Alternativamente, si la asistencia se registra en NocoDB al procesar
  el webhook (paso 5.2), la lista sale directa de NocoDB.
- Esa lista es el **grupo destinatario** de un aviso puntual.
- Envío del aviso vía **Listmonk** (o correo directo): mensaje corto
  solo a quien tiene reserva en esa clase. Copia oculta / envíos
  individuales: un alumno nunca ve a otro.
- Reutiliza la intención `avisar_alumnos` que ya se guarda en las
  ocurrencias de la Agenda; ahora con destinatarios reales detrás.

## 8. Talleres y retiros

Mismo mecanismo: evento puntual con plazas en Cal.com. Cobro por
Bizum/transferencia (0% comisión). Pago online (Stripe ~1,5%+0,25€) es
decisión aparte, solo si se quiere.

## 9. Privacidad (RGPD)

- Datos personales de alumnos: NocoDB (alumnos/bonos) y Cal.com
  (reservas). Ambos autoalojados, bajo control propio.
- La vista pública de disponibilidad solo muestra aforo, nunca quién.
- Avisos con copia oculta / individuales; un alumno no ve a otros.
- Consentimiento explícito al reservar (Cal.com) y al registrarse.
- InvoiceNinja solo entra si hay factura; ahí van datos fiscales.

## 10. Orden de trabajo propuesto

1. Definir en Cal.com los eventos con plazas (franjas de grupo) que
   correspondan a la matriz de Clases.
2. Servicio de webhooks en el backend: BOOKING_CREATED / _CANCELLED
   -> alta/baja de alumno en NocoDB, descuento/devolución de bono.
3. Tabla Bonos en NocoDB + su lógica de caducidad.
4. Vista de disponibilidad (embeber Cal.com o endpoint propio).
5. Lista de alumnos por clase en admin (desde NocoDB o Cal.com).
6. Avisos al grupo de una clase vía Listmonk.
7. (Opcional) Facturación con InvoiceNinja para quien pida factura.

Cada paso es entregable por separado. El 2 (webhooks) es el corazón:
sin él, las reservas de Cal.com no se reflejan en NocoDB.

## 11. Preguntas abiertas

- Franjas Cal.com <-> matriz Clases NocoDB: ¿sincronizar automático o
  mantener a mano? (dos fuentes de la semana tipo es riesgo de deriva).
- ¿La lista de alumnos por clase se lee de Cal.com en vivo, o se
  materializa en NocoDB al procesar el webhook? (afecta a RGPD y a la
  rapidez de la consulta).
- Aforo: ¿lo controla Cal.com (seats) como única fuente, o se replica
  contador en NocoDB para la agenda del panel?
- Avisos: ¿Listmonk o correo directo del backend? ¿remitente?
- ¿InvoiceNinja llega a usarse, o el cobro es siempre Bizum y factura
  solo a demanda?
