"""
backend.handlers.clases — ruta /admin/api/clases (GET).

Devuelve la matriz semanal: las celdas tipo+día+hora que definen la semana
tipo. La edición de la matriz se hace por ahora desde NocoDB; aquí solo se
expone la lectura para el calendario y la proyección de meses.
"""
from .. import datos

RUTA = "/admin/api/clases"


def handle(req):
    if req.path != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}
    if req.metodo != "GET":
        return None
    try:
        out = []
        for r in datos.lee("Clases"):
            out.append({
                "Id": r.get("Id"), "actividad_id": r.get("actividad_id"),
                "dia_semana": r.get("dia_semana"), "hora_inicio": r.get("hora_inicio"),
                "duracion_min": r.get("duracion_min"), "lugar": r.get("lugar"),
                "color": r.get("color"), "activa": r.get("activa"),
            })
        return 200, {"ok": True, "clases": out}
    except Exception as e:
        return 502, {"error": f"no se pudo leer: {e}"}
