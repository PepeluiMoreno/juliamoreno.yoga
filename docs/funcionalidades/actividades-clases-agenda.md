# Actividades, Clases y Agenda (modelo de oferta)

## Qué es
El modelo de datos que describe QUÉ enseña Julia y CUÁNDO. Tres
conceptos en NocoDB (base "Yoga") que el panel gestiona y la web
mostrará.

## Los tres conceptos
- **Actividades** — el catálogo de lo que se ofrece (Hatha, Vinyasa,
  Yoga para mayores...). Ciclo de 4 estados:
  propuesta | programada | en_curso | finalizada.
  Campos: precio, duración, lugar.
- **Clases** — la MATRIZ de la semana tipo (plantilla recurrente):
  actividad, día de la semana, hora de inicio, duración, lugar, color,
  activa. Es "los martes a las 19:00 hay Hatha en Nerja".
- **Agenda** — cada fila es una OCURRENCIA puntual (una fecha
  concreta). Campos: estado (programada | aplazada | cancelada),
  motivo, motivo_texto, avisar_alumnos, serie_id, visible_web,
  duracion_min.

## Cómo se relacionan
Actividad (qué) -> Clase (cuándo, en abstracto: "los martes") ->
Agenda (cuándo, en concreto: "el martes 22 de julio"). La agenda es lo
que se ve y gestiona en el calendario del panel.

## Decisiones tomadas
- Separar la semana tipo (Clases) de las ocurrencias (Agenda): permite
  cancelar/mover un día sin tocar la plantilla.
- `visible_web` marca si una ocurrencia se muestra en la web. En el
  módulo de reservas pasaría a significar "abierta a reserva".
- `avisar_alumnos` hoy solo guarda la intención de avisar; el envío
  real depende del módulo de reservas.

## Tensión conocida (importante para reservas)
Si se adopta un motor de reservas externo (Cal.diy), la "semana tipo"
podría acabar viviendo en dos sitios (Clases en NocoDB y eventos en
Cal.diy). Evitar esa duplicación es uno de los ejes de la decisión del
módulo de reservas. Ver reservas-disponibilidad-avisos.md.

## Pendiente / ideas
- Aforo por ocurrencia (campo plazas) — requisito para reservas.
- Transición automática de estados por fechas.
- Limpiar columnas huérfanas en Agenda.

## Ficheros / ubicación
- Tablas NocoDB base "Yoga".
- Gestión: panel /admin (ver panel-admin.md) vía backend
  (handlers/actividades.py, agenda.py, clases.py).
