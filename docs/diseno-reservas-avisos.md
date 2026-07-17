# Diseño — Reservas, disponibilidad y avisos por clase

Documento de trabajo. Fija la arquitectura antes de construir. No es
código; es la decisión de dónde vive cada cosa y cómo se conectan las
piezas, para no reconstruir sobre malas decisiones.

Fecha: 17 jul 2026.

## 1. Problema

Tres necesidades que han surgido, encadenadas:

1. El checkbox actual "mostrar en la web" solo decide si una clase
   figura en el listado público. Se quiere que sirva para algo más:
   que el alumno vea la **disponibilidad real** y pueda **reservar**.
2. Hace falta una **vista de disponibilidad reutilizable**, usable
   tanto en la web pública (para reservar) como donde convenga dentro
   del flujo de contratación.
3. En admin, por cada clase, la **lista de alumnos apuntados**, para
   poder **avisar solo a ese grupo** ("traed esterilla", "nos
   retrasamos 10 min"), sin molestar a quien no va a esa clase.

## 2. Decisión de fondo (ya tomada, se mantiene)

Los **alumnos y las inscripciones son datos personales de clientes**,
ligados a pagos. Por RGPD y por no reconstruir gestión de clientes
desde cero, **viven en InvoiceNinja**, no en NocoDB. El panel de admin
los **consulta** desde InvoiceNinja; no los duplica.

Consecuencia: NocoDB sigue siendo la fuente de verdad de la **oferta**
(actividades, clases/ocurrencias, tarifas). InvoiceNinja es la fuente
de verdad de **quién ha reservado/pagado qué**. La reserva es el puente
entre ambos mundos.

## 3. Reparto de responsabilidades

### NocoDB (oferta — lo que ya existe)
- Actividades: qué enseña Julia.
- Clases/Agenda: ocurrencias concretas (fecha, hora, lugar, aforo).
- Tarifas: precios (clase suelta, bonos, mensualidad).
- Campo nuevo por ocurrencia: **plazas** (aforo) y **plazas_libres**
  calculado. `visible_web` deja de ser "mostrar en lista" y pasa a
  significar "abierta a reserva".

### InvoiceNinja (clientes y dinero)
- Cliente = alumno (nombre, contacto, consentimiento RGPD).
- Producto = actividad o bono.
- Factura / suscripción = lo que el alumno ha contratado.
- **Reserva** = la relación alumno ↔ ocurrencia concreta. Ver 3.1.

### 3.1 El punto delicado: dónde se guarda la reserva

Una "reserva" enlaza un alumno (InvoiceNinja) con una ocurrencia
(NocoDB). Tres opciones, con su coste:

- **A. Reserva en InvoiceNinja.** Un campo personalizado o una línea de
  factura que referencia el id de la ocurrencia de NocoDB. Ventaja: el
  dato personal (quién) vive con el resto de datos del cliente, RGPD
  limpio. Inconveniente: consultar "quién va a la clase X" obliga a
  filtrar en InvoiceNinja por ese id.
- **B. Reserva en NocoDB.** Una tabla Reservas con id_ocurrencia +
  id_cliente_invoiceninja. Ventaja: consulta directa de aforo y lista.
  Inconveniente: mete un identificador de cliente en NocoDB; hay que
  cuidar que ahí no se copien nombre/contacto (solo el id opaco).
- **C. Híbrido.** La reserva vive en InvoiceNinja (fuente de verdad,
  RGPD), y NocoDB guarda solo un **contador de aforo** por ocurrencia,
  actualizado al reservar/cancelar. La lista de alumnos siempre se pide
  a InvoiceNinja en el momento.

Recomendación inicial: **C**. Mantiene los datos personales en
InvoiceNinja, da aforo rápido en NocoDB para pintar disponibilidad, y
la lista nominal solo se materializa cuando admin la pide (y se puede
no cachear, mejor para RGPD). A validar cuando veamos la API de
InvoiceNinja.

## 4. Componente reutilizable de disponibilidad

Una sola vista que, dada una actividad o un rango de fechas, pinta las
ocurrencias con su aforo:

- Entrada: actividad_id o rango; salida: lista de ocurrencias con
  fecha, hora, lugar, plazas totales y libres, estado (abierta / llena
  / cerrada / cancelada).
- Se alimenta de un endpoint público de solo lectura (no expone datos
  personales, solo números de aforo).
- Se pinta en dos sitios: la web pública (dentro de "Contratar
  clases") y, si hace falta, el propio admin.
- Es de solo lectura; reservar es una acción aparte (ver 5).

Regla: este componente **nunca** ve nombres de alumnos. Solo aforo.

## 5. Flujo de contratación (alto nivel)

1. El alumno abre "Contratar clases" → ve el componente de
   disponibilidad (4).
2. Elige ocurrencia(s) con plazas libres.
3. Se identifica / da sus datos (consentimiento RGPD explícito).
4. Paga o queda pendiente de pago (InvoiceNinja gestiona esto).
5. Al confirmarse: se crea la reserva (3.1, opción C) y el contador de
   aforo de la ocurrencia en NocoDB baja en uno.

Este flujo es un proyecto en sí. No se aborda hasta que el modelo de
datos (3) esté cerrado.

## 6. Lista de alumnos por clase + avisos (admin)

Lo que motivó esta conversación. Una vez existan las reservas:

- En la ficha de una ocurrencia, admin pide a InvoiceNinja la lista de
  alumnos con reserva confirmada en ella.
- Esa lista es el **grupo destinatario** de un aviso puntual.
- Aviso = mensaje corto (email, y si se quiere en el futuro SMS/
  WhatsApp) enviado solo a ese grupo. Reutiliza la intención
  `avisar_alumnos` que ya guardamos en las ocurrencias, pero ahora con
  destinatarios reales.
- El canal de envío se decide aparte (email es lo natural para
  empezar; encaja con lo que ya hay).

Nota: hoy `avisar_alumnos` solo guarda la intención. El envío real
depende de que exista este grupo, así que este bloque va **después**
del modelo de reservas.

## 7. Privacidad (RGPD) — no negociable

- Datos personales de alumnos: solo en InvoiceNinja.
- NocoDB, como mucho, ids opacos de cliente; nunca nombre/contacto.
- El componente público de disponibilidad solo ve aforo, jamás quién.
- Los avisos: el admin ve la lista para decidir, pero el envío no
  expone unos alumnos a otros (copia oculta / envíos individuales).
- Consentimiento explícito en el paso de contratación.

## 8. Orden de trabajo propuesto

1. Cerrar el modelo de datos de la reserva (3.1) — requiere mirar la
   API real de InvoiceNinja (campos personalizados, cómo referenciar
   una ocurrencia, cómo listar por ese campo).
2. Añadir aforo a las ocurrencias en NocoDB (plazas + contador libre).
3. Endpoint público de disponibilidad (solo aforo) + componente
   reutilizable de solo lectura.
4. Flujo de contratación / reserva (el grande).
5. Lista de alumnos por clase en admin (consulta a InvoiceNinja).
6. Envío real de avisos al grupo de una clase.

Cada paso es entregable y probable por separado. El 1 es el que
condiciona todo; conviene no avanzar al 2 sin haberlo validado contra
la API de InvoiceNinja.

## 9. Preguntas abiertas (a resolver antes de construir)

- ¿InvoiceNinja permite un campo personalizado por línea/factura para
  referenciar la ocurrencia, y filtrar clientes por él vía API?
- ¿La reserva es por ocurrencia concreta, o por "bono de N clases" que
  el alumno va gastando? (cambia el modelo de aforo).
- ¿Se reserva y se paga a la vez, o se puede reservar y pagar luego?
- ¿El aforo se controla de verdad (plazas limitadas) o es informativo?
- Avisos: ¿solo email de momento? ¿quién es el remitente?
