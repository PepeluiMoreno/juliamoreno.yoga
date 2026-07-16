"""
backend — servidor del sitio juliamoreno.yoga.

Estructura del paquete:

  datos.py        acceso a NocoDB (lee/guarda/actualiza/borra)
  util.py         utilidades puras (saneado, slugs, tiempo)
  agenda.py       lógica de ocurrencias (materializar, proyectar, replicar…)
  fotos.py        subida y optimización de imágenes
  web.py          disparo de la regeneración del sitio estático
  servidor.py     servidor HTTP y enrutado a los handlers
  handlers/       un módulo por área de la API, sin lógica HTTP:
                    actividades, agenda, clases, resumen, foto, webhooks
  __main__.py     punto de entrada (python3 -m backend)

Antes se llamaba "captador" porque solo recogía formularios; hoy es el
backend completo del panel, y la captación es uno de sus handlers.
"""
