# Reservas, disponibilidad y avisos (EN DISEÑO)

## Qué es
El módulo que permitiría a los alumnos ver disponibilidad y reservar
plaza en las clases, y a Julia tener por cada clase la lista de
apuntados para avisarles solo a ellos ("traed esterilla", "nos
retrasamos 10 min"). Incluye bonos (4/8 clases con caducidad).

Estado: **EN DISEÑO**. No hay código en producción. La decisión del
motor de reservas NO está cerrada. Este documento resume el análisis
para poder retomarlo.

## Las necesidades
1. El alumno ve disponibilidad real y reserva su plaza.
2. Vista de disponibilidad reutilizable (web pública y donde convenga).
3. En admin, lista de alumnos por clase = grupo destinatario de avisos,
   solo a quien va a esa clase.
4. Bonos (4/8 clases) que se descuentan al asistir, con caducidad.

## Piezas disponibles (ya en el compose del proyecto)
- **NocoDB** — fuente de verdad de oferta, y candidato a alojar también
  alumnos/bonos/reservas.
- **Cal.com / Cal.diy** — motor de reservas (ver más abajo la historia).
- **InvoiceNinja** — facturación. Self-hosted SIN límite de clientes
  (el "5 clientes" es del cloud gratis; lo confirma el fundador). Queda
  para facturar a demanda, NO como registro de alumnos ni motor de
  reservas.
- **Listmonk** — envío de correo (avisos, boletines).
- **backend** Python — el pegamento.

## El eje de decisión
Se decide con **coste/beneficio**: idoneidad funcional = beneficio;
coste de integración = coste. Y con dos reglas que el usuario fijó:
- No dejar que algo "ya hecho/instalado" condicione (evitar la falacia
  del coste hundido).
- Sopesar de verdad lo que se va a USAR, no lo que la herramienta
  podría hacer.

## Historia de la decisión (resumen honesto)
1. Primer diseño: Cal.com reservas + NocoDB alumnos/bonos.
2. Segundo (contradictorio): InvoiceNinja para alumnos. Se descubrió
   la contradicción y se unificó.
3. Se valoró **todo en NocoDB** (una sola fuente de verdad, sin
   duplicar la semana tipo). El usuario, preguntado, dijo que solo
   usaría "apuntarse y ver plazas" y que le pesa más no duplicar la
   semana tipo -> la balanza cayó a NocoDB-centric.
4. El usuario replanteó: y si **Cal.com sustituye** a NocoDB en el
   calendario (no lo duplica) -> desaparece la objeción de duplicar.
   Se decidió explorar en la rama `calcom-centric`.
5. Exploración de Cal.com: la API v2 no venía en la imagen estándar,
   generar API keys parecía requerir Enterprise de pago, y la edición
   libre estaba desaconsejada para producción. Parecía muerto.
6. **Giro clave**: Cal.com se cerró (abril 2026); el open source es
   ahora **Cal.diy** (fork MIT). Cal.diy CONSERVA la API v2 y NO
   requiere licencia. El muro era del Cal.com cerrado. El camino
   revive.
7. El compose de Cal.diy YA trae el servicio de la API v2
   (`calcom-api`), así que no hay que compilar a mano. Diagnóstico del
   VPS: sobrado (23 GB RAM). Todo verde para intentar levantarlo.

## Dónde está la decisión ahora (dos caminos vivos)
- **A. Cal.diy-centric**: Cal.diy como motor de reservas/calendario
  (API v2, recordatorios, portal, plazas). El usuario quiere intentar
  levantar la API v2 de Cal.diy en el VPS y ver que funciona antes de
  comprometerse. Si va, se decide el reparto (qué queda en NocoDB:
  actividades, tarifas, textos web).
  - Riesgo: Cal.diy está desaconsejado para producción por sus
    autores, pero por SOPORTE/SEGURIDAD, no por licencia ni capacidad.
    Riesgo asumible para un negocio pequeño autohospedado con backups.
  - Si se integra: middleware de SOLO LECTURA (leer disponibilidad y
    reservas); Cal.diy crea las reservas con su motor; NUNCA escribir a
    mano en su base de datos (saltaría su lógica y ataría a su esquema).
- **B. NocoDB-centric**: construir reservas sobre NocoDB + backend
  (tablas Alumnos, Bonos, Reservas; aforo en Agenda). Una sola fuente
  de verdad, cero dependencia frágil de terceros. Más construcción.

Recomendación de Claude: si el intento de Cal.diy en el VPS va bien y
su UI le sirve a Julia, A ahorra construir un motor entero. Si no
convence, B es la más limpia y sin sorpresas. Decidir DESPUÉS de probar
Cal.diy.

## Modelo de datos (si NocoDB-centric)
- Agenda: + campo plazas (aforo) y plazas_libres (recuento de reservas).
- Alumnos (nueva): contacto + consentimiento RGPD.
- Bonos (nueva): tipo 4/8, fecha, caducidad, créditos.
- Reservas (nueva): alumno + ocurrencia + estado + bono.

## Avisos y RGPD
- Avisos por Listmonk (o correo del backend), solo a quien tiene
  reserva en esa clase, con copia oculta / envíos individuales.
- Datos personales de alumnos autoalojados (NocoDB y/o Cal.diy), bajo
  control propio. La vista pública de disponibilidad solo muestra
  aforo, nunca nombres. Consentimiento explícito al reservar.

## Próximo paso concreto
Levantar Cal.diy + su API v2 en el VPS (plan detallado en la rama
`calcom-centric`, doc `docs/rama-calcom-centric.md`), generar API key,
correr la sonda (`scripts/backend/calcom/sonda.py`) y comprobar que se
lee disponibilidad. Con ese hecho, decidir A vs B.

## Ficheros
- `docs/reservas-avisos-disponibilidad.md` — diseño detallado (ambas
  arquitecturas).
- Rama `calcom-centric`: `docs/rama-calcom-centric.md` (toda la
  exploración e historia de hallazgos), `scripts/backend/calcom/`
  (cliente y sonda de la API de Cal.diy).
