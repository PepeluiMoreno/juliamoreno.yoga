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
- `reservas-disponibilidad-avisos.md` — módulo de reservas (EN DISEÑO,
  con análisis de alternativas Cal.com/Cal.diy vs NocoDB)

## Estado general (17 jul 2026)
- Web pública: desplegada, funcional.
- Panel /admin: agenda operativa (calendario, menú contextual,
  edición de clases). Desplegado en main.
- Backend: modular, operativo.
- Reservas: EN DISEÑO. Decisión de motor sin cerrar. Rama
  `calcom-centric` con exploración de Cal.diy.

## Convenciones
- Fuente de verdad de la oferta: NocoDB (base "Yoga").
- Web pública generada; panel servido por el backend.
- Cuadernos de bitácora por servidor, aparte de estos documentos.
