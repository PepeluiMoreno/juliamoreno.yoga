# Backend (servicio Python)

## Qué es
El servicio que sirve el panel /admin y le da datos, hablando con
NocoDB. Es la API interna del proyecto. Paquete modular en
`scripts/backend/`.

## Cómo está resuelto hoy
- Paquete `scripts/backend/` (renombrado desde el antiguo "captador").
- Contenedor `jmy-backend`, arranca con:
  `pip install --quiet Pillow && cd scripts && python3 -m backend`
- `scripts/captador.py` queda como lanzador de compatibilidad.

### Módulos
- `datos.py` — acceso a NocoDB.
- `util.py` — utilidades comunes.
- `agenda.py` — lógica de agenda/ocurrencias.
- `fotos.py` — manejo de imágenes (usa Pillow).
- `web.py` — generación/servicio de la parte web.
- `servidor.py` — el servidor HTTP.
- `__main__.py` — punto de entrada.
- `handlers/` — un handler por área: actividades, agenda, clases,
  resumen, foto, webhooks.
- `calcom/` — (rama calcom-centric) exploración de la API de Cal.diy;
  no está en main.

## Decisiones tomadas
- Estructura modular por responsabilidad, en vez de un script único.
- Un handler por área de datos.
- El .env de la librería de NocoDB va en la RAÍZ del repo (la lib
  calcula la raíz como parent.parent desde scripts/).

## Relación con el resto
- Fuente de verdad: NocoDB, base "Yoga" (tablas Actividades, Agenda,
  Clases, Interesados, Contactos, Precios, Horarios).
- Sirve el panel /admin.
- `handlers/webhooks.py` es el punto natural donde entrarían los
  webhooks de un motor de reservas (Cal.diy) si se adopta esa vía.
- La generación de la web pública desde datos de NocoDB vive aquí
  (web.py).

## Pendiente / ideas
- Servicio de webhooks para el módulo de reservas.
- Tarea diaria (bonos que caducan, etc.) cuando exista reservas.
- Limpiar columnas huérfanas en Agenda (hora_fin, vigencia_*,
  es_plantilla).

## Ficheros
- `scripts/backend/` (todo el paquete)
- `scripts/captador.py` (lanzador de compatibilidad)
