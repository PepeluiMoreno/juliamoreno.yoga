# Reservas y bonos — esquema 100% autoalojado (coste cero)

## Principio
Nada de SaaS. Cal.com (self-hosted) gestiona TODAS las reservas;
NocoDB es la fuente de verdad de alumnos y bonos. La integración con Cal.com (abajo) está pendiente de implementar en Python (un pequeño servicio como el captador).

## Configuración en Cal.com (reservas.juliamoreno.yoga)
Tipos de evento:
1. "Clase de prueba" — 60 min, individual, confirmación automática.
2. "Clase privada" / "Valoración inicial" — 60-75 min, individual.
3. Un evento RECURRENTE por franja de grupo, con PLAZAS (seats):
   p. ej. "Hatha martes 19:00 · Nerja" con 10 plazas, "Maro jueves 10:00"
   con 12, "Almuñécar viernes 18:00" con 12. El alumno reserva su plaza
   y recibe confirmación y recordatorio automáticos.

## Flujo de bonos (sin apunte manual)
1. Venta de bono: Julia lo registra en NocoDB (tabla Bonos: alumno,
   tipo 4/8, fecha; caducidad = fecha + 1 mes, campo calculado).
2. Webhook de Cal.com (BOOKING_CREATED) -> servicio Python (a implementar):
   - busca al alumno en NocoDB por email/teléfono (lo crea si es nuevo),
   - registra la asistencia prevista,
   - descuenta 1 crédito del bono activo más antiguo no caducado,
   - si no hay bono con saldo: aviso a Julia por Telegram/correo
     ("cobrar clase suelta o vender bono").
3. BOOKING_CANCELLED -> el servicio devuelve el crédito si la cancelación
   llega con más de X horas.
4. Diario a las 9:00: bonos que caducan en 3 días -> mensaje de
   renovación al alumno; primera reserva completada -> petición de
   reseña de Google a las 3 horas.

Diseño de referencia (a implementar en Python cuando se aborde Cal.com):
(
credenciales de NocoDB y el canal de aviso).

## Talleres y retiros
Mismo mecanismo: evento puntual con plazas en Cal.com. El cobro se
gestiona por Bizum/transferencia (0% comisión); si algún día se quiere
pago online, Stripe cobra ~1,5%+0,25€ por transacción — decisión aparte.
