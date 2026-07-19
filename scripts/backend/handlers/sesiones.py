"""
backend.handlers.sesiones — /admin/api/sesiones: ocupación por sesión.

La agenda contesta "¿qué clases hay el jueves?". Esta vista contesta la
otra pregunta, la que se hace Julia cuando prepara la semana: "¿cuánta
gente viene, y a cuál?". Por eso lista TODAS las sesiones del rango,
incluidas las vacías: saber que el jueves no ha venido nadie es tan útil
como saber que están llenos.

    /admin/api/sesiones?desde=YYYY-MM-DD&hasta=YYYY-MM-DD

Devuelve, por sesión: inicio, clase, aforo (total/ocupadas/libres) y los
alumnos con su teléfono. Es una sola respuesta para toda la vista: así
el listado, el contador y la lista de alumnos salen del mismo dato y no
pueden contradecirse.
"""
import datetime

from .. import datos
from ..calcom import cliente

RUTA = "/admin/api/sesiones"


def _telefonos():
    idx = {}
    try:
        for fila in datos.lee("Reservas"):
            tel = (fila.get("telefono") or "").strip()
            if not tel:
                continue
            uid = (fila.get("cal_uid") or "").strip()
            email = (fila.get("email") or "").strip().lower()
            if uid:
                idx["uid:" + uid] = tel
            if email:
                idx["em:" + email] = tel
    except Exception:
        pass
    return idx


def _clases():
    """[(cal_event_type_id, actividad_id, titulo)] de las temporadas que
    tienen clase de reservas asociada. `actividad_id` es el uuid del servicio
    (identidad estable) y `titulo` sale del Servicio."""
    servicios = datos.servicios_por_uuid()
    salida = []
    for fila in datos.lee("Actividades"):
        cal_id = fila.get("cal_event_type_id")
        if not cal_id:
            continue
        s_uuid = fila.get("servicio_uuid") or ""
        serv = servicios.get(s_uuid, {})
        try:
            salida.append((int(cal_id), s_uuid,
                           serv.get("titulo_es") or s_uuid))
        except (TypeError, ValueError):
            continue
    return salida


def _sesiones(desde, hasta, solo_actividad=None):
    tel_idx = _telefonos()
    reservas = cliente.bookings(desde, hasta).get("data", [])

    # alumnos por (clase, inicio), de una sola pasada
    por_clave = {}
    for b in reservas:
        if b.get("status") != "accepted":
            continue
        eid = b.get("eventTypeId") or (b.get("eventType") or {}).get("id")
        uid = b.get("uid") or ""
        clave = (eid, b.get("start") or "")
        for a in b.get("attendees", []):
            email = (a.get("email") or "").strip().lower()
            por_clave.setdefault(clave, []).append({
                "nombre": a.get("name") or "",
                "email": a.get("email") or "",
                "telefono": (tel_idx.get("uid:" + uid)
                             or tel_idx.get("em:" + email)
                             or a.get("phoneNumber") or ""),
            })

    salida = []
    for cal_id, act_id, titulo in _clases():
        if solo_actividad and act_id != solo_actividad:
            continue
        try:
            aforo = cliente.aforo_por_hueco(cal_id, desde, hasta)
        except Exception:
            continue
        for inicio, datos_hueco in aforo.items():
            alumnos = sorted(por_clave.get((cal_id, inicio), []),
                             key=lambda a: a["nombre"].lower())
            salida.append({
                "inicio": inicio,
                "event_type_id": cal_id,
                "actividad_id": act_id,
                "titulo": titulo,
                "total": datos_hueco.get("total"),
                "ocupadas": len(alumnos),
                "libres": (datos_hueco["total"] - len(alumnos)
                           if isinstance(datos_hueco.get("total"), int)
                           else None),
                "alumnos": alumnos,
            })
    salida.sort(key=lambda s: (s["inicio"], s["titulo"]))
    return salida


def handle(req):
    ruta, _, query = req.path.partition("?")
    if ruta != RUTA or req.metodo != "GET":
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}

    par = {}
    for trozo in query.split("&"):
        k, _, v = trozo.partition("=")
        if k:
            par[k] = v

    hoy = datetime.date.today()
    desde = par.get("desde") or hoy.isoformat()
    try:
        dias = int(par.get("dias", 15))
    except ValueError:
        dias = 15
    hasta = par.get("hasta") or (hoy + datetime.timedelta(days=dias)).isoformat()

    try:
        ses = _sesiones(desde, hasta, par.get("actividad") or None)
        return 200, {"ok": True, "desde": desde, "hasta": hasta,
                     "sesiones": ses,
                     "totales": {"sesiones": len(ses),
                                 "alumnos": sum(x["ocupadas"] for x in ses)}}
    except Exception as e:
        return 502, {"error": "no se pudieron leer las sesiones: %s" % e}
