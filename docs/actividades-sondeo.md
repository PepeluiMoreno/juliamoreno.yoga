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
  condicional y un formulario "Me interesa" que hace POST a n8n
  (https://auto.juliamoreno.yoga/webhook/interes).
- **NocoDB**, dos tablas:
  - `Actividades`: id, estado (tentativa|confirmada|completada), umbral,
    interesados (lo actualiza n8n), plazas (opc), fecha, foto,
    titulo_{es,en,fr,de}, texto_{es,en,fr,de}, mostrar_contador, visible.
    Julia edita SOLO los campos _es; n8n traduce el resto (flujo
    flujo-actividades-traduccion.json).
  - `Interesados`: actividad, nombre, contacto, idioma, fecha.
- **n8n** (flujo-sondeo-interes.json): recibe el "Me interesa", antispam
  básico, guarda en Interesados, cuenta, y si se alcanza el umbral avisa
  a Julia (Telegram/email) y deja el contador al día.

## Ciclo de vida de una actividad
1. Julia crea la actividad en NocoDB en español, estado "tentativa", con
   un umbral (p. ej. 8). n8n la traduce; el rebuild la publica.
2. Los clientes pulsan "Me interesa" en la web. n8n acumula.
3. Al llegar al umbral, n8n avisa a Julia.
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
