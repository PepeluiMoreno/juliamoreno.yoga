# Panel de administración (/admin)

## Qué es
La herramienta interna de gestión para Julia. Vive en `/admin`,
servida por el backend. Su corazón hoy es la **Agenda**: un calendario
para gestionar las clases y sus ocurrencias.

## Cómo está resuelto hoy
- Página única `sitio/admin/index.html`, con FullCalendar 6.1.15 (CDN).
- Estética propia: tipografías Marcellus/Mulish, azul mar #1d5975,
  tinta #153f54, crema #fcfbf8.
- Autenticación por sesión (login propio).

### Agenda — interacción
- Tres vistas: Mes / Semana / Día, unificadas.
- **Menú contextual** como mecanismo central (clic derecho, y hover con
  retardo en clases). Se adapta al contexto:
  - Celda/hueco vacío -> "Nueva clase" (con hora en semana/día).
  - Sobre una clase -> Editar / Ocultar-Mostrar en web / Cancelar /
    Reactivar / Eliminar, según estado.
- Clic en un día -> panel lateral con las **clases de ese día**, como
  tarjetas editables (título, hora, duración, lugar, visible en web),
  con guardado por tarjeta.
- **Cancelación** en el panel lateral (no modal): motivo (enfermedad,
  festivo, aforo insuficiente, climatología, fuerza mayor, otro) +
  detalle + avisar alumnos (intención).
- **Advertencia de día pasado**: crear una clase en fecha anterior a
  hoy avisa de que solo queda a efectos de registro histórico; si
  acepta continúa, si no aborta. Centralizado en crearEnFecha().

### Dashboard
- "Actividades ofertadas" + contador de horas/mes.
- Badges por estado de actividad.

## Decisiones tomadas
- Menú contextual en vez de botones sueltos y selección múltiple: se
  eliminó la clonación/selección por UI (endpoints /replicar siguen en
  backend, sin UI). Interacción más limpia.
- Terminología unificada en "clase" (se descartó "sesión"). Excepción:
  "sesión caducada" del login (es autenticación).
- Layout a todo el ancho, editor de agenda siempre visible en 2
  columnas.
- Todo el trabajo del panel está desplegado en `main`.

## Bugs resueltos (referencia)
- Modal de cancelar congelado (regla CSS de [hidden] vs display:flex).
- "undefined NaN de undefined" en el título del panel lateral al picar
  hueco en vista Semana: dateClick usa info.dateStr recortado a 10
  caracteres; _fmtDia y fechaLocalISO blindados contra fechas
  inválidas.

## Relación con el resto
- Lee y escribe la oferta en NocoDB a través del backend.
- La "lista de alumnos por clase" y el envío real de avisos dependen
  del módulo de reservas (hoy avisar_alumnos solo guarda intención).
  Ver reservas-disponibilidad-avisos.md.

## Pendiente / ideas
- UI para editar la matriz de Clases (semana tipo) desde el panel.
- Envío real de avisos (hoy solo se guarda la intención).
- Transición automática de estados por fechas.
- Publicar la agenda como horarios en la web pública.

## Ficheros
- `sitio/admin/index.html`
- Backend que lo sirve y le da datos: ver backend.md
