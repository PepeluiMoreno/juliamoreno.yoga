# Funcionalidades de juliamoreno.yoga

Un documento por funcionalidad desarrollada o discutida. Cada uno
describe qué es, cómo está resuelto hoy, qué decisiones se tomaron y
qué queda pendiente. Pensados para retomar el trabajo sin depender del
historial de chat.

## Índice
- `web-publica.md` — sitio estático multi-idioma (ES/EN/FR/DE)
- `panel-admin.md` — panel de gestión en /admin (agenda, clases)
- `backend.md` — servicio Python modular (API interna del panel)
- `actividades-clases-agenda.md` — modelo de oferta y ocurrencias
- `reservas-disponibilidad-avisos.md` — módulo de reservas (motor
  decidido: Cal.diy)

## Estado general (17 jul 2026)
- Web pública: desplegada, funcional.
- Panel /admin: agenda operativa. La parte de calendario pasará a la
  UI de Cal.diy cuando se complete la integración de reservas; el
  resto se conserva.
- Backend: modular, operativo.
- Reservas: motor DECIDIDO (Cal.diy, validado en el VPS el 17 jul).
  Integración en construcción; diseño en
  docs/reservas-avisos-disponibilidad.md.

## Convenciones
- Fuentes de verdad: Cal.diy (calendario/reservas/aforo) y NocoDB
  (actividades, tarifas, textos, bonos).
- Web pública generada; panel servido por el backend.
- Cuadernos de bitácora por servidor, aparte de estos documentos.
