"""
backend.handlers.agenda — rutas /admin/api/agenda y sus operaciones.

  GET    /admin/api/agenda                 lista de ocurrencias
  POST   /admin/api/agenda                 crea (puntual, o recurrente->materializa)
  PATCH  /admin/api/agenda                 edita una ocurrencia
  DELETE /admin/api/agenda                 elimina (con reglas de negocio)
  POST   /admin/api/agenda/cancelar        marca cancelada + motivo
  POST   /admin/api/agenda/replicar        clona ocurrencias al mes siguiente
  POST   /admin/api/agenda/proyectar-matriz  despliega la matriz sobre un mes
  POST   /admin/api/agenda/copiar-mes      copia un mes a otro
"""
from .. import agenda as logica
from .. import datos
from ..util import limpio
from ..web import dispara_rebuild

RUTA = "/admin/api/agenda"


def _lista():
    filas = datos.lee("Agenda")
    # mapa actividad_id -> estado de la actividad (para reglas de borrado)
    try:
        act_estado = {a.get("id"): (a.get("estado") or "").strip()
                      for a in datos.lee("Actividades")}
    except Exception:
        act_estado = {}
    out = []
    for r in filas:
        aid = r.get("actividad_id")
        out.append({
            "Id": r.get("Id"), "titulo": r.get("titulo"),
            "actividad_id": aid, "tipo": r.get("tipo"),
            "dias_semana": r.get("dias_semana"), "fecha": r.get("fecha"),
            "hora_inicio": r.get("hora_inicio"), "duracion_min": r.get("duracion_min"),
            "serie_id": r.get("serie_id"),
            "lugar": r.get("lugar"), "color": r.get("color"),
            "visible_web": r.get("visible_web"),
            "estado": r.get("estado") or "programada",
            "motivo": r.get("motivo"), "motivo_texto": r.get("motivo_texto"),
            "actividad_estado": act_estado.get(aid, ""),
        })
    return out


def _crear(body):
    fila = logica.fila_agenda(body, con_id=False)
    if not fila.get("titulo") and not fila.get("actividad_id"):
        return 422, {"error": "falta título o actividad"}
    try:
        if fila.get("tipo") == "recurrente":
            if not fila.get("dias_semana"):
                return 422, {"error": "una clase recurrente necesita días de la semana"}
            ocurrencias = logica.materializa_mes(fila)
            if not ocurrencias:
                return 422, {"error": "no hay días de ese tipo en lo que queda de mes"}
            datos.guarda_varios("Agenda", ocurrencias)
            dispara_rebuild()
            return 200, {"ok": True, "generadas": len(ocurrencias)}
        if not fila.get("fecha"):
            return 422, {"error": "una sesión puntual necesita fecha"}
        datos.guarda("Agenda", fila)
        dispara_rebuild()
        return 200, {"ok": True}
    except Exception as e:
        return 502, {"error": f"no se pudo crear: {e}"}


def _editar(body):
    if not body.get("Id"):
        return 422, {"error": "falta Id"}
    fila = logica.fila_agenda(body, con_id=True)
    try:
        datos.actualiza("Agenda", fila)
        dispara_rebuild()
        return 200, {"ok": True}
    except Exception as e:
        return 502, {"error": f"no se pudo guardar: {e}"}


def _eliminar(body):
    ids = body.get("ids")
    if not (isinstance(ids, list) and ids):
        ids = [body["Id"]] if body.get("Id") else []
    if not ids:
        return 422, {"error": "falta Id"}
    try:
        # Regla: solo se elimina una clase puntual, no visible en web y sin
        # actividad en curso detrás. El resto se cancela o aplaza, no se borra.
        agenda = {r.get("Id"): r for r in datos.lee("Agenda")}
        act_estado = {a.get("id"): (a.get("estado") or "").strip()
                      for a in datos.lee("Actividades")}
        for i in ids:
            r = agenda.get(int(i))
            if not r:
                continue
            en_curso = act_estado.get(r.get("actividad_id")) == "en_curso"
            anunciada = bool(r.get("visible_web"))
            if en_curso or anunciada:
                return 409, {"error": "esa clase no se puede eliminar (pertenece a una actividad en curso o está anunciada en la web). Puedes aplazarla o cancelarla."}
        datos.borra_varios("Agenda", [int(i) for i in ids])
        dispara_rebuild()
        return 200, {"ok": True, "borradas": len(ids)}
    except Exception as e:
        return 502, {"error": f"no se pudo borrar: {e}"}


def _cancelar(body):
    ids = body.get("ids") or ([body["Id"]] if body.get("Id") else [])
    motivo = limpio(body.get("motivo"), 100)
    if not ids:
        return 422, {"error": "falta la clase a cancelar"}
    if not motivo:
        return 422, {"error": "hay que indicar un motivo de cancelación"}
    try:
        filas = [{
            "Id": int(i), "estado": "cancelada", "motivo": motivo,
            "motivo_texto": limpio(body.get("motivo_texto"), 1000),
            "avisar_alumnos": bool(body.get("avisar_alumnos")),
        } for i in ids]
        datos.actualiza_varios("Agenda", filas)
        dispara_rebuild()
        return 200, {"ok": True, "canceladas": len(ids)}
    except Exception as e:
        return 502, {"error": f"no se pudo cancelar: {e}"}


def _replicar(body):
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return 422, {"error": "no se seleccionó ninguna clase"}
    try:
        n = logica.replica_ocurrencias([int(i) for i in ids])
        dispara_rebuild()
        return 200, {"ok": True, "replicadas": n}
    except Exception as e:
        return 502, {"error": f"no se pudo replicar: {e}"}


def _proyectar(body):
    mes = limpio(body.get("mes"), 7)  # YYYY-MM
    if len(mes) != 7:
        return 422, {"error": "falta el mes (YYYY-MM)"}
    try:
        n = logica.proyecta_matriz(mes)
        dispara_rebuild()
        return 200, {"ok": True, "generadas": n}
    except Exception as e:
        return 502, {"error": f"no se pudo proyectar: {e}"}


def _copiar_mes(body):
    desde = limpio(body.get("desde"), 7)
    hasta = limpio(body.get("hasta"), 7)
    if not (len(desde) == 7 and len(hasta) == 7):
        return 422, {"error": "faltan meses origen/destino (YYYY-MM)"}
    try:
        n = logica.copia_mes(desde, hasta)
        dispara_rebuild()
        return 200, {"ok": True, "copiadas": n}
    except Exception as e:
        return 502, {"error": f"no se pudo copiar: {e}"}


# Sub-rutas POST -> función que las resuelve
_SUBRUTAS_POST = {
    RUTA + "/cancelar": _cancelar,
    RUTA + "/replicar": _replicar,
    RUTA + "/proyectar-matriz": _proyectar,
    RUTA + "/copiar-mes": _copiar_mes,
}


def handle(req):
    # Sub-rutas POST (cancelar, replicar, proyectar, copiar-mes)
    if req.metodo == "POST" and req.path in _SUBRUTAS_POST:
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _SUBRUTAS_POST[req.path](req.body)

    if req.path != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}

    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "agenda": _lista()}
        except Exception as e:
            return 502, {"error": f"no se pudo leer: {e}"}
    if req.metodo == "POST":
        return _crear(req.body)
    if req.metodo == "PATCH":
        return _editar(req.body)
    if req.metodo == "DELETE":
        return _eliminar(req.body)
    return None
