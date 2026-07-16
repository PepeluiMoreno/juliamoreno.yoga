# Actividades con sondeo de demanda

Julia propone actividades tentativas; los clientes manifiestan interés
("Me interesa"); cuando se alcanza un umbral de interesados, Julia monta
el grupo. No hay pago ni compromiso firme en esta fase: es un sondeo.

## Decisiones de diseño (fijadas)
- El "Me interesa" pide SOLO nombre + contacto (mínima fricción).
- El contador en la web se muestra SOLO cuando va bien (>=50% del umbral
  y aún por debajo de él): evita mostrar "1/8" en actividades flojas.
- El "Me interesa" NO es vinculante: es sondeo; la inscripción firme
  vendría después (fase futura, con Cal.com) cuando Julia confirme.
- Formulario integrado en el diseño de la web (no NocoDB Forms).

## Piezas
- **Web**: cada actividad "tentativa" muestra badge de estado, contador
  condicional y un formulario "Me interesa" que hace POST al captador Python
  (https://api.juliamoreno.yoga/webhook/interes).
- **NocoDB**, dos tablas:
  - `Actividades`: id, estado (tentativa|confirmada|completada), umbral,
    interesados (se cuenta de la tabla Interesados), plazas (opc), fecha, foto,
    titulo_{es,en,fr,de}, texto_{es,en,fr,de}, mostrar_contador, visible.
    Julia edita SOLO los campos _es; build-web.py traduce el resto (DeepL,
    flujo-actividades-traduccion.json).
  - `Interesados`: actividad, nombre, contacto, idioma, fecha.
- **captador Python** (scripts/captador.py): recibe el "Me interesa", antispam
  básico, guarda en Interesados, cuenta, y si se alcanza el umbral avisa
  a Julia (Telegram/email) y deja el contador al día.

## Ciclo de vida de una actividad
1. Julia crea la actividad en NocoDB en español, estado "tentativa", con
   un umbral (p. ej. 8). build-web.py la traduce; el rebuild la publica.
2. Los clientes pulsan "Me interesa" en la web. El captador acumula en NocoDB.
3. Al llegar al umbral, Julia lo ve en NocoDB (o se puede añadir aviso por email).
4. Julia decide: si la monta, cambia estado a "confirmada" (y, en su caso,
   fija plazas/fechas). Si no, la deja o la oculta (visible=false).
5. Tras impartirla, estado "completada" (deja de mostrarse).

## Privacidad (RGPD)
El formulario recoge nombre y contacto: lleva la frase de consentimiento
(ya incluida, campo form_consent en 4 idiomas). Los datos de Interesados
son para avisar de esa actividad; conservación mínima. Ver
docs/rgpd-consentimiento.md.

## Inscripción firme (fase futura, NO incluida ahora)
Cuando Julia confirme un grupo y quiera inscripción con plazas y
recordatorios, se reutiliza Cal.com (evento con aforo) enlazado desde la
tarjeta. No requiere backend nuevo. Se abordará si el negocio lo pide.


## Franjas horarias (disponibilidad)
Cada actividad puede definir franjas entre las que el cliente marca las
que le sirven (opción A: Julia define, cliente elige, build-web.py cuenta la
ganadora). Dos tipos, combinables en una misma actividad:
- **genérica**: recurrente, p. ej. "sábados por la mañana" (para grupos
  regulares). Se traduce a los 4 idiomas.
- **fecha**: puntual, p. ej. "sábado 15 de marzo, 10:00" (para talleres
  únicos). La etiqueta suele ser igual en los 4 idiomas.

Modelo:
- `Actividades.franjas`: lista de {id, tipo, etiqueta_{es,en,fr,de}}.
- `Interesados.franjas`: las que marcó cada persona (ids separados por coma).

build-web.py cuenta el interés TOTAL y también POR FRANJA (conteo de la tabla Interesados). Se puede avisar a Julia cuando:
- el total alcanza el umbral (hay demanda), y/o
- una franja concreta alcanza el umbral (hay demanda a una hora viable) —
  este es el aviso más útil: "8 personas pueden el sábado por la mañana".
Así Julia sabe no solo si montar la actividad, sino a qué hora.

Si una actividad no define franjas, el formulario solo pide nombre y
contacto (sondeo simple), como antes.
## Formulario de contacto general
Además del sondeo por actividad, la sección Contacto de la web lleva un
formulario general (nombre, teléfono, asunto) que postea a
https://api.juliamoreno.yoga/webhook/contacto (flujo-contacto.json):
se guarda en la tabla Contactos (con checkbox "atendido" como bandeja
de Julia). Mismo patrón que el sondeo; RGPD con frase de
consentimiento en los 4 idiomas.
