"""
backend.handlers.papelera — papelera y estudio de impacto del borrado.

En el panel Julia SIEMPRE puede eliminar. Lo que cambia es qué significa:
por defecto el borrado es LÓGICO (la fila queda con eliminado=true, sale de
todas las vistas y de la web, y se puede restaurar); solo si se marca
"borrado definitivo" se saca de NocoDB para siempre.

Tres rutas:
  GET  /admin/api/papelera?tabla=X    lo borrado, listo para restaurar
  POST /admin/api/papelera/restaurar  {tabla, ids:[...]}
  POST /admin/api/papelera/purgar     {tabla, ids:[...]}  (irreversible)

Y una cuarta que no borra nada, solo avisa:
  GET  /admin/api/impacto?tabla=X&uuid=Y   qué se lleva por delante

El impacto importa porque un Servicio es la tabla maestra de todo un
historial: sus temporadas, las clases de esas temporadas, las ocurrencias de
la agenda y las reservas de los alumnos. Antes de confirmar, la modal enseña
esa cuenta; y para retirar algo de la oferta sin tocar el historial está
se_sigue_ofertando, que es lo que casi siempre se quiere de verdad.
"""
from .. import datos

RUTA = "/admin/api/papelera"
RUTA_RESTAURAR = "/admin/api/papelera/restaurar"
RUTA_PURGAR = "/admin/api/papelera/purgar"
RUTA_IMPACTO = "/admin/api/impacto"

# Tablas que la papelera sabe manejar, con el campo que sirve de etiqueta
# legible al listarlas (para que Julia vea QUÉ va a restaurar, no un id).
TABLAS = {
    "Servicios": "titulo_es",
    "Actividades": "hasta",
    "Clases": "dia_semana",
    "Agenda": "titulo",
    "Reservas": "nombre",
    "Interesados": "nombre",
    "Contactos": "nombre",
}


def _query(path):
    _, _, q = path.partition("?")
    par = {}
    for trozo in q.split("&"):
        k, _, v = trozo.partition("=")
        if k:
            par[k] = v
    return par


def _ids_de(body):
    ids = body.get("ids")
    if not (isinstance(ids, list) and ids):
        ids = [body["Id"]] if body.get("Id") else []
    return [int(i) for i in ids]


def _listar(tabla):
    if tabla not in TABLAS:
        return 422, {"error": "esa tabla no tiene papelera"}
    etiqueta = TABLAS[tabla]
    filas = []
    for r in datos.papelera(tabla):
        filas.append({
            "Id": r.get("Id"),
            "uuid": r.get("uuid"),
            "etiqueta": r.get(etiqueta) or "(sin nombre)",
            "eliminado_fecha": r.get("eliminado_fecha"),
        })
    filas.sort(key=lambda f: str(f.get("eliminado_fecha") or ""), reverse=True)
    return 200, {"ok": True, "tabla": tabla, "filas": filas}


def _impacto(tabla, uuid):
    """Cuenta lo que cuelga de una fila, sin borrar nada. Solo Servicios y
    Actividades arrastran historial; el resto son hojas."""
    if not uuid:
        return 422, {"error": "falta el uuid"}
    detalle = []
    try:
        if tabla == "Servicios":
            temporadas = [a for a in datos.lee("Actividades")
                          if (a.get("servicio_uuid") or "") == uuid]
            t_uuids = {a.get("uuid") for a in temporadas}
            clases = [c for c in datos.lee("Clases")
                      if c.get("actividad_id") in t_uuids]
            agenda = [g for g in datos.lee("Agenda")
                      if g.get("actividad_id") in t_uuids]
            cal_ids = {int(a.get("cal_event_type_id") or 0) for a in temporadas}
            cal_ids.discard(0)
            reservas = [r for r in datos.lee("Reservas")
                        if int(r.get("event_type_id") or 0) in cal_ids]
            detalle = [
                ("temporadas", len(temporadas)),
                ("clases de la semana", len(clases)),
                ("clases en la agenda", len(agenda)),
                ("reservas de alumnos", len(reservas)),
            ]
        elif tabla == "Actividades":
            clases = [c for c in datos.lee("Clases")
                      if (c.get("actividad_id") or "") == uuid]
            agenda = [g for g in datos.lee("Agenda")
                      if (g.get("actividad_id") or "") == uuid]
            detalle = [
                ("clases de la semana", len(clases)),
                ("clases en la agenda", len(agenda)),
            ]
    except Exception as e:
        return 502, {"error": f"no se pudo calcular el impacto: {e}"}

    depende = [{"que": q, "cuantos": n} for q, n in detalle if n]
    total = sum(n for _, n in detalle)
    return 200, {
        "ok": True, "tabla": tabla, "uuid": uuid,
        "depende": depende, "total": total,
        # Un servicio con historial no se borra: se retira de la cartera.
        "sugerir_retirar": tabla == "Servicios" and total > 0,
    }


def handle(req):
    ruta, _, _ = req.path.partition("?")

    if ruta == RUTA and req.metodo == "GET":
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _listar(_query(req.path).get("tabla", ""))

    if ruta == RUTA_IMPACTO and req.metodo == "GET":
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        par = _query(req.path)
        return _impacto(par.get("tabla", ""), par.get("uuid", ""))

    if ruta in (RUTA_RESTAURAR, RUTA_PURGAR) and req.metodo == "POST":
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        body = req.body or {}
        tabla = (body.get("tabla") or "").strip()
        if tabla not in TABLAS:
            return 422, {"error": "esa tabla no tiene papelera"}
        ids = _ids_de(body)
        if not ids:
            return 422, {"error": "no se ha indicado qué restaurar"}
        try:
            if ruta == RUTA_RESTAURAR:
                datos.restaura(tabla, ids)
                accion = "restauradas"
            else:
                datos.borra_varios(tabla, ids, definitivo=True)
                accion = "borradas para siempre"
            from ..web import dispara_rebuild
            dispara_rebuild()
            return 200, {"ok": True, "n": len(ids), "accion": accion}
        except Exception as e:
            return 502, {"error": f"no se pudo completar: {e}"}

    return None
