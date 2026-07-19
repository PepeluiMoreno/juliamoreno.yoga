"""
backend.handlers.resumen — ruta /admin/api/resumen (GET).

Alimenta el panel de control: cuenta actividades por estado, interesados
reales por actividad, horas de clase del mes, y separa las actividades
"ofertadas" (en curso) de las "en preparación" (propuestas).
"""
from .. import agenda as logica
from .. import datos

RUTA = "/admin/api/resumen"


def handle(req):
    if req.path != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}
    if req.metodo != "GET":
        return None
    try:
        acts = datos.lee("Actividades")
        inter = datos.lee("Interesados")
        servicios = datos.servicios_por_uuid()
        # interesados reales por servicio (el interés es por servicio)
        por_serv = {}
        for r in inter:
            a = (r.get("actividad") or "").strip()  # ahora lleva servicio_uuid
            if a:
                por_serv[a] = por_serv.get(a, 0) + 1
        estados = {}
        ofertadas = []
        propuestas = []
        for a in acts:
            est = (a.get("estado") or "propuesta").strip()
            estados[est] = estados.get(est, 0) + 1
            s_uuid = (a.get("servicio_uuid") or "").strip()
            serv = servicios.get(s_uuid, {})
            tarjeta = {
                "id": s_uuid,
                "titulo": serv.get("titulo_es") or "(sin título)",
                "interesados": por_serv.get(s_uuid, 0),
                "umbral": int(a.get("umbral") or 0),
                "lugar": a.get("lugar") or "",
                "duracion": a.get("duracion") or "",
            }
            if est == "en_curso":
                ofertadas.append(tarjeta)
            elif est == "propuesta":
                propuestas.append(tarjeta)
        propuestas.sort(key=lambda x: x["interesados"], reverse=True)
        return 200, {
            "ok": True,
            "totales": {
                "ofertadas": estados.get("en_curso", 0),
                "programadas": estados.get("programada", 0),
                "en_preparacion": estados.get("propuesta", 0),
                "finalizadas": estados.get("finalizada", 0),
                "total_actividades": len(acts),
                "total_interesados": len(inter),
                "horas_mes": logica.horas_programadas_mes(),
            },
            "ofertadas": ofertadas,
            "preparacion": propuestas,
        }
    except Exception as e:
        return 502, {"error": f"no se pudo calcular: {e}"}
