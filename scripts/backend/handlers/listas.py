"""
backend.handlers.listas — /admin/api/listas: alumnos de UNA clase.

Ruta bajo /admin, así que va protegida por Authelia (y además se exige
req.usuario): son datos personales de los alumnos y no pueden quedar
expuestos como las rutas públicas de reserva.

Se pide siempre acotada: una actividad concreta y un rango de fechas. La
lista se saca desde la AGENDA, sobre la clase seleccionada, y según su
recurrencia se puede pedir esa sesión, la semana o el mes.

    /admin/api/listas?actividad=<id>&desde=YYYY-MM-DD&hasta=YYYY-MM-DD
    ...&hora=HH:MM   (opcional: solo esa sesión del día)

De dónde sale cada dato:
  - Quién está apuntado: de Cal.diy, que es el motor y la fuente de
    verdad de las reservas (incluidas las hechas desde su propio booker).
  - El teléfono: de la copia en NocoDB (tabla Reservas), porque Cal.diy
    no lo pide. Se cruza por uid de reserva y, si no, por email.
"""
import datetime

from .. import datos
from ..calcom import cliente

RUTA = "/admin/api/listas"


def _telefonos():
    """{clave: telefono} desde la tabla Reservas, por uid y por email."""
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


def _clase_de(actividad_id):
    """(cal_event_type_id, titulo, existe). cal_event_type_id es 0 si la
    actividad existe pero aún no tiene clase de reservas asociada."""
    for fila in datos.lee("Actividades"):
        if fila.get("id") == actividad_id:
            return (int(fila.get("cal_event_type_id") or 0),
                    fila.get("titulo_es") or actividad_id, True)
    return 0, actividad_id, False


def _sesiones(cal_id, titulo, desde, hasta, hora=None):
    tel_idx = _telefonos()
    reservas = cliente.bookings(desde, hasta).get("data", [])

    por_sesion = {}
    for b in reservas:
        if b.get("status") != "accepted":
            continue
        eid = b.get("eventTypeId") or (b.get("eventType") or {}).get("id")
        if eid != cal_id:
            continue
        ini = b.get("start") or ""
        s = por_sesion.setdefault(ini, {
            "inicio": ini, "event_type_id": eid,
            "titulo": titulo, "alumnos": [],
        })
        for a in b.get("attendees", []):
            email = (a.get("email") or "").strip().lower()
            uid = b.get("uid") or ""
            s["alumnos"].append({
                "nombre": a.get("name") or "",
                "email": a.get("email") or "",
                "telefono": (tel_idx.get("uid:" + uid)
                             or tel_idx.get("em:" + email)
                             or a.get("phoneNumber") or ""),
            })

    salida = []
    for s in sorted(por_sesion.values(), key=lambda x: x["inicio"]):
        # "Solo esta clase" llega con hora: se compara con la hora local,
        # que es la que Julia ve en la agenda.
        if hora:
            try:
                d = datetime.datetime.fromisoformat(
                    s["inicio"].replace("Z", "+00:00"))
                local = d + datetime.timedelta(hours=2)  # Europe/Madrid
                if local.strftime("%H:%M") != hora:
                    continue
            except Exception:
                pass
        s["alumnos"].sort(key=lambda a: a["nombre"].lower())
        s["total"] = len(s["alumnos"])
        salida.append(s)
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

    actividad = par.get("actividad", "")
    desde = par.get("desde", "")
    hasta = par.get("hasta", "")
    hora = par.get("hora") or None
    if not actividad or not desde or not hasta:
        return 422, {"error": "faltan actividad, desde o hasta"}

    try:
        cal_id, titulo, existe = _clase_de(actividad)
        if not existe:
            return 200, {"ok": True, "sesiones": [],
                         "aviso": "La actividad '%s' no aparece en la tabla "
                                  "de Actividades: puede que se renombrara o "
                                  "se borrara." % actividad}
        if not cal_id:
            return 200, {"ok": True, "sesiones": [],
                         "aviso": "'%s' todavia no tiene clase de reservas en "
                                  "el motor, asi que nadie ha podido "
                                  "apuntarse. Se crea con alta_clases." % titulo}
        return 200, {"ok": True,
                     "sesiones": _sesiones(cal_id, titulo, desde, hasta, hora)}
    except Exception as e:
        return 502, {"error": "no se pudieron leer las listas: %s" % e}
