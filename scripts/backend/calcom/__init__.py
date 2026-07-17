"""
backend.calcom — exploración de la variante Cal.com-centric (rama).

Módulo aislado para evaluar si Cal.com puede ser la base del calendario
y las reservas, leyendo su API v2. No toca NocoDB ni el backend de main.

  cliente.py  cliente mínimo de la API v2 (event-types, slots, bookings)
  sonda.py    prueba manual que valida el punto crítico (leer la
              disponibilidad para alimentar la web)
"""
