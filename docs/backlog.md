# Backlog — lo que queda por hacer

Temas que fueron surgiendo mientras se trabajaba en otra cosa y se aparcaron
para no descarrilar lo que había en marcha. Están en orden de llegada, no de
importancia. Cada uno lleva lo que se averiguó del código al explorarlo, para
no tener que volver a buscarlo.

Los dos que quedan pendientes —Presencia en redes y el bloque de bonos/cobros—
**necesitan decisiones antes de poder empezar**: están anotadas al final de cada
punto.

## Pendientes

### 1. Bonos / tickets con compra y validación presencial
El usuario quiere estudiar cómo los alumnos compran **bonos o tickets** para las clases y
cómo **Julia los lee/valida con su móvil o algún artefacto** (p. ej. escanear un QR al
entrar). Implica: compra (¿pasarela de pago?), emisión del bono/ticket, modelo de saldo o
canjeo, e identidad estable del alumno para asociarle el bono.
**Mapa del repo (explorado 2026-07-19):**
- **Bonos hoy = solo tarifa.** `bono4`/`bono8`/`bonopriv` son líneas de `Precios`
  (`contenido.json:14-93`, `handlers/precios.py`); NO hay saldo, créditos, canjeo ni
  caducidad en el código.
- **Pagos: no hay integración real.** Stripe solo como placeholder para arrancar Cal.diy
  (`docs/rama-calcom-centric.md:389`). InvoiceNinja existe pero es facturación manual
  (`docker-compose.yml:148-178`). Reservar es **gratis** hoy (`reservas.py:_reservar`), sin
  dato de pago en tabla `Reservas`.
- **Identidad de alumno: NO existe** tabla Alumnos/Clientes; solo email+nombre por reserva.
  Es **prerequisito** para asociar bonos. El manual prevé un fichero Alumnos/Bonos/
  Asistencias no creado (`docs/manual/gen.js:149-155`).
- **QR / validación presencial: no existe nada** (ni código ni docs).
- **PERO el modelo de Bonos YA está DISEÑADO en docs** (no implementado):
  `docs/reservas-avisos-disponibilidad.md:94-104` — tabla **Bonos** (`alumno`, `tipo` 4/8,
  `fecha`, `caducidad` +1 mes, `créditos_restantes`); descontar 1 crédito al webhook
  `BOOKING_CREATED` del bono activo más antiguo no caducado; devolver crédito al cancelar
  con antelación; aviso diario de caducidad. "Los bonos viven FUERA de Cal.diy (NocoDB)".
- **Webhook `BOOKING_CREATED/CANCELLED` de Cal.diy: NO existe** (el `webhooks.py` actual es
  de formularios de contacto/interés, no de bookings).
- Regla de oro a respetar: las reservas SIEMPRE las escribe Cal.diy; el bono descuenta, no
  reemplaza la reserva.

**Piezas a construir (desde cero):** (1) identidad estable de alumno (email como clave);
(2) tabla Bonos + lógica saldo/caducidad/canje; (3) webhook de bookings Cal.diy→backend;
(4) cobro online (evaluar activar pago de Cal.diy vs checkout propio: Stripe/Redsys); (5) QR
/ token de un solo uso + validación en puerta (el "artefacto" de Julia).

**COBROS EN METÁLICO (añadido 2026-07-20, va de la mano de los bonos):** muchos alumnos
**pagan en efectivo al llegar a clase**. Hace falta un módulo de gestión de cobros que
permita **"picar un recibí" con el mínimo roce** —desde el móvil, en la puerta, mientras
entra la gente—, y a partir de ahí **generar la factura y enviarla por correo**.
- Encaja con la lista de alumnos de una sesión que ya existe (`handlers/listas.py`): lo
  natural es marcar el cobro ahí mismo, junto a quien ha venido.
- **InvoiceNinja ya está desplegado** (`docker-compose.yml:148-178`) y hoy se usa a mano;
  es el candidato obvio para emitir la factura y el envío por correo, vía su API, en vez
  de montar un facturador propio.
- Enlaza con la facturación del Panel de control (hoy estimada como horas × tarifa): con
  cobros reales registrados, esa cifra dejaría de ser una estimación.
- A decidir: qué se registra (importe, concepto, forma de pago, quién), si el recibí es
  un simple marcado o ya emite documento, y si la factura es siempre o solo a petición.

**Pendiente de decidir con el usuario:** pasarela de pago; si el bono se compra online o se
paga en persona y Julia lo emite; cómo valida Julia (móvil escaneando QR del alumno, lector,
código manual); si se implementa primero la identidad de alumno + tabla Bonos (base) antes
que el pago y el QR.

### 2. Menú lateral del panel: responsive en móvil (icono hamburguesa)
El menú lateral del panel de administración (`sitio/admin/index.html`, `.menu-item` con
`data-vista`, sección de navegación sobre la línea ~310) debe **adaptarse en versión móvil
y mostrar el icono de menú**, igual que ya hace la UI de la web pública.
- A mirar: cómo resuelve la web pública ese patrón (`sitio/index.html` y su CSS) para
  reutilizar el mismo comportamiento y estilo en vez de inventar otro.
- Es cambio de UI/CSS del panel, independiente del modelo de datos.

### 5. "Presencia en redes": sustituir la entrada Estado del sidebar
La última entrada del menú lateral, **Estado**, pasa a llamarse **Presencia en redes**, y
se construye un **módulo que repase la situación del SEO y demás**.
- Hoy `#vista-estados` ("Estado de las actividades") es un placeholder vacío: *"Sección en
  preparación"* (`sitio/admin/index.html`). El menú usa `data-vista="estados"` → renombrar
  a `presencia` y reescribir la sección.
- Punto de partida en el repo: `docs/altas-google-meta.md` (altas en Google/Meta, y la
  noción de "un servicio por clase") y las menciones a QR en carteles para analítica y
  reseñas (`docs/manual/gen.js:164`, `docs/README-despliegue.md:32`).
- A decidir con el usuario qué debe repasar el módulo: ficha de Google Business, presencia
  en Meta/Instagram, metadatos y `sitemap` de la web generada, reseñas, palabras clave…
  y **de dónde saldría cada dato** (comprobaciones automáticas sobre la web propia vs.
  APIs externas vs. lista de verificación manual). Sin eso, el módulo corre el riesgo de
  ser otro placeholder.

### 6. Lugares como tabla propia en NocoDB (hoy son texto libre)
Los sitios donde se dan las clases deberían ser una **tabla `Lugares`**, no texto suelto.
- Hoy `lugar` es un `SingleLineText` repetido en **tres** tablas (`Actividades`, `Clases`,
  `Agenda`), escrito a mano cada vez: "Nerja", "Maro", "Playa de Burriana". Nada impide que
  convivan "Maro", "maro" y "Estudio Maro" como si fueran sitios distintos.
- **Ya está modelado a medias**: existe la tabla `Horarios` con ids `nerja` / `maro` /
  `almunecar` (`provision-nocodb.py`, `contenido.json:110-142`), pero solo sirve para
  decidir qué horarios se publican en la web — no es una entidad de lugar con sus datos.
- Propuesta: tabla `Lugares` (uuid, nombre, dirección, aforo, notas, visible) y sustituir
  el texto por `lugar_uuid` en Actividades/Clases/Agenda. Decidir qué hacer con `Horarios`:
  probablemente absorberla o dejarla como la vista pública de los lugares.
- Beneficio inmediato: aforo por sala (hoy las plazas están en la temporada, no en el
  sitio), filtros por lugar fiables, y direcciones para la web y para Google.

## Hecho / promovido al plan

### ✅ Tarjetas a mano de la web (2026-07-20)
Era el punto 7. Las 4 tarjetas escritas a mano fuera de los marcadores tenían textos
buenos, así que en vez de borrarlos se **dieron de alta como servicios**: "Espalda sana" y
"Yoga para niños y familias" son nuevos, y "Hatha yoga"/"Yoga para mayores de 60" heredaron
la descripción de la web. Quitadas las tarjetas del HTML en los 4 idiomas. Resultado: 7
tarjetas, ninguna duplicada, todo el catálogo desde NocoDB.

### ✅ Interesados huérfanos arreglados (2026-07-20)
Era el punto 8. Los 4 interesados apuntaban a `taller-respiracion`, slug del modelo viejo.
Se sustituyen por 11 interesados sembrados por el seed, repartidos entre servicios reales
por su uuid. Queda pendiente de verificar que la web genera `/interes.html?actividad=…`
con el uuid del servicio (parte del punto 7, tarjetas a mano de la web).

### ✅ Panel de control rediseñado (commit 60d2a30, 2026-07-20)
Era el punto 3+4 del backlog. Hecho: **semana en curso** con siete columnas y barra
de aforo por clase (verde llena / ámbar a medias / azul con sitio; canceladas y
aplazadas visibles con su motivo, hoy resaltado); **cartera de servicios** separada de
**actividades en curso**; **métricas por actividad** (clases dadas/las que tocaban,
cumplimiento %, reservas, facturado = horas impartidas × tarifa del servicio, solo lo
ya dado); y **cumplimiento del ejercicio** con % impartido y reparto por motivo,
separando bajas de Julia (clases) de bajas de alumno (reservas).
Datos desde NocoDB; Cal.diy queda preparado para cuando las actividades se enlacen.
La vista **Sesiones** del menú sigue existiendo aparte (detalle de quién viene a cada
clase); lo que se pidió —el resumen semanal gráfico— vive ya en el Panel de control.
