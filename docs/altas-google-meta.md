# Altas en Google y Meta — guía operativa

Orden de ejecución. Los textos entre comillas están listos para pegar.
Todas las altas con el MISMO correo del negocio (paso 0) y las
credenciales al gestor de contraseñas compartido.

## 0. Correo del negocio (previo a todo)
Crear `hola@juliamoreno.yoga` en **Zoho Mail Free** (0 €, hasta 5
buzones con dominio propio, webmail y app):
1. zoho.com/mail → plan Forever Free → verificar dominio con el
   registro TXT que indique.
2. Añadir a la zona DNS: MX de Zoho, SPF (`v=spf1 include:zoho.eu ~all`)
   y DKIM (el TXT que genere el panel).
Este correo es la identidad de TODAS las altas siguientes; nada de
cuentas personales mezcladas.

## 1. Cuenta de Google
Crear cuenta Google con `hola@juliamoreno.yoga` ("Usar mi dirección
actual", sin crear Gmail). Activar verificación en dos pasos.

## 2. Google Business Profile (la pieza nº 1)
business.google.com → Añadir empresa:
- Nombre: `Julia Moreno · Yoga` (exactamente igual que en la web;
  nunca añadir palabras clave al nombre: motivo de suspensión).
- Categoría principal: `Estudio de yoga`. Secundarias: `Profesor
  particular`, `Gimnasio` solo si lo ofrece.
- Modelo: empresa de servicios CON dirección si el local de Nerja es
  fijo y atendible; si no, empresa de zona de servicio con áreas:
  `Nerja`, `Maro`, `Almuñécar`, `Frigiliana`, `Torrox`.
- Teléfono: [TELÉFONO]. Web: `https://juliamoreno.yoga`.
  Enlace de citas: `https://reservas.juliamoreno.yoga`.
- Descripción (750 caracteres máx.):
  "Clases de Hatha yoga en Nerja, Maro y Almuñécar impartidas por
  Julia Moreno, graduada universitaria en Ciencias de la Actividad
  Física y el Deporte y experta en Hatha yoga. Una práctica con base
  científica, adaptada a cada cuerpo: grupos reducidos, yoga para
  mayores de 60, programas de espalda sana y yoga para niños y
  familias. Clases en español y en inglés. Método con la precisión
  del maestro Iyengar y el criterio de la formación universitaria en
  ciencias del deporte. Primera clase de prueba: reserva por WhatsApp
  o en la web."
- Servicios: crear uno por clase (Hatha yoga, Yoga +60, Espalda sana,
  Yoga infantil, Clases privadas, Valoración inicial) con precios.
- Verificación: normalmente vídeo del local/actividad. Hacerla con
  calma, con material de clase visible.
- Tras el alta: 3-5 fotos reales, primera publicación, y arrancar la
  campaña de reseñas (enlace corto de reseña: perfil → "Pedir reseñas").

## 3. Google Search Console
search.google.com/search-console → propiedad de DOMINIO
`juliamoreno.yoga` → verificación por registro TXT en DNS.
Enviar `https://juliamoreno.yoga/sitemap.xml`. Repetir como propiedad
URL para el .com si algún día sirve contenido (no hace falta si solo
redirige).
NO dar de alta Google Analytics: la analítica es Umami (sin cookies).

## 4. Instagram (Meta)
- Crear cuenta con el correo del negocio. Nombre: `Julia Moreno · Yoga`.
  Usuario preferido: `@juliamoreno.yoga`; alternativas si está cogido:
  `@juliamorenoyoga`, `@yoga.juliamoreno`.
- Convertir en cuenta profesional → categoría "Instructor(a) de yoga"
  o "Salud/belleza".
- Bio: "Hatha yoga en Nerja · Maro · Almuñécar | Graduada en Ciencias
  del Deporte | Clases ES/EN | ↓ Reserva tu primera clase" +
  enlace `https://juliamoreno.yoga`.
- Geotag en cada publicación (Nerja / Playa Burriana / Almuñécar).

## 5. Página de Facebook
Necesaria aunque Instagram sea el canal fuerte: los grupos de expats
de Nerja/Frigiliana viven en Facebook y la página da acceso al
ecosistema Meta Business.
- Crear página `Julia Moreno · Yoga`, categoría "Instructor de yoga",
  misma foto, misma bio, botón de acción → WhatsApp.
- Vincular Instagram y la página en Meta Business Suite
  (business.facebook.com) bajo un portfolio empresarial a nombre de
  Julia.

## 6. WhatsApp Business (app, gratuita)
Migrar el número actual a WhatsApp Business:
- Perfil de empresa: nombre, dirección, web, horario.
- Mensaje de bienvenida y respuestas rápidas (/horarios, /precios,
  /donde, /prueba, /resena) según el manual.
- Catálogo: bonos y clases con precios.
- No confundir con la API de WhatsApp Business (de pago, vía Meta):
  no la necesitamos; los avisos automatizados salen por correo o
  email, coste cero.

## 7. Conexión con Postiz (cuando se levante el perfil gestion)
Para programar publicaciones en Instagram/Facebook desde Postiz
self-hosted hay que crear una app en developers.facebook.com
(tipo Business, permisos instagram_content_publish y
pages_manage_posts) y cargar sus claves en el .env de Postiz.
Es el único trámite "de desarrollador" de toda la guía; sin él,
Postiz queda limitado y las publicaciones se hacen a mano en
Meta Business Suite, que también vale.

## Registro DNS acumulado tras esta guía
| Tipo | Nombre | Valor | Motivo |
|------|--------|-------|--------|
| MX   | @      | mx.zoho.eu (y secundarios) | correo |
| TXT  | @      | v=spf1 include:zoho.eu ~all | SPF |
| TXT  | zmail._domainkey | (DKIM de Zoho) | DKIM |
| TXT  | @      | google-site-verification=... | Search Console |

## Checklist final
- [ ] Correo del negocio operativo con SPF/DKIM
- [ ] Cuenta Google + 2FA
- [ ] Ficha de Google verificada, con servicios, fotos y 1ª publicación
- [ ] Search Console verificado y sitemap enviado
- [ ] Instagram profesional con bio y enlace
- [ ] Página de Facebook vinculada en Business Suite
- [ ] WhatsApp Business migrado con respuestas rápidas y catálogo
- [ ] Todas las credenciales en el gestor compartido, nada en papel
