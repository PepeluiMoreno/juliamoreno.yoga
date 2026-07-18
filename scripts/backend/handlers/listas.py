"""
backend.handlers.listas — /admin/api/listas: alumnos apuntados por sesión.

Ruta bajo /admin, así que va protegida por Authelia (y además se exige
req.usuario): son datos personales de los alumnos y no pueden quedar
expuestos como las rutas públicas de reserva.

De dónde sale cada dato:
  - Quién está apuntado: de Cal.diy, que es el motor y la fuente de
    verdad de las reservas (incluidas las hechas desde su propio booker).
  - El teléfono: de la copia en NocoDB (tabla Reservas), porque Cal.diy
    no lo pide. Se cruza por uid de reserva y, si no, por email.

Devuelve las sesiones del rango con su lista, pensado para que Julia
pase lista, recoja firmas o imprima consentimientos.
"""
import datetime

from .. import datos
from ..calcom import cliente

RUTA = "/admin/api/listas"


def _copias(desde, hasta):
    """{clave: telefono} desde la tabla Reservas, por uid y por email."""
    idx = {}
    try:
        for fila in datos.lee("Reservas"):
            tel = (fila.get("telefono") or "").strip()
            if not tel:
                continue
            uid = (fila.get("cal_uid") or "").strip()
            email = (fila.get("email") or "").strip().lower()
            ini = str(fila.get("inicio") or "")
            if uid:
                idx[f"uid:{uid}"] = tel
            if email:
                idx[f"em:{email}"] = tel
                if ini:
                    idx[f"em:{email}|{ini}"] = tel
    except Exception:
        pass
    return idx


def _sesiones(dias):
    hoy = datetime.date.today()
    fin = hoy + datetime.timedelta(days=dias)
    tipos = {}
    for t in cliente.event_types().get("data", []):
        tipos[t.get("id")] = t.get("title")

    tel_idx = _copias(hoy.isoformat(), fin.isoformat())
    reservas = cliente.bookings(hoy.isoformat(), fin.isoformat()).get("data", [])

    por_sesion = {}
    for b in reservas:
        if b.get("status") != "accepted":
            continue
        ini = b.get("start")
        eid = b.get("eventTypeId") or b.get("eventType", {}).get("id")
        clave = f"{eid}|{ini}"
        s = por_sesion.setdefault(clave, {
            "inicio": ini,
            "event_type_id": eid,
            "titulo": tipos.get(eid) or "Clase",
            "alumnos": [],
        })
        for a in b.get("attendees", []):
            email = (a.get("email") or "").strip().lower()
            uid = b.get("uid") or ""
            tel = (tel_idx.get(f"uid:{uid}")
                   or tel_idx.get(f"em:{email}|{ini}")
                   or tel_idx.get(f"em:{email}")
                   or a.get("phoneNumber") or "")
            s["alumnos"].append({
                "nombre": a.get("name") or "",
                "email": a.get("email") or "",
                "telefono": tel,
            })

    salida = sorted(por_sesion.values(), key=lambda x: x["inicio"] or "")
    for s in salida:
        s["alumnos"].sort(key=lambda a: a["nombre"].lower())
        s["total"] = len(s["alumnos"])
    return salida


def handle(req):
    ruta, _, query = req.path.partition("?")
    if ruta != RUTA or req.metodo != "GET":
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}

    dias = 30
    for par in query.split("&"):
        if par.startswith("dias="):
            try:
                dias = max(1, min(int(par[5:]), 120))
            except ValueError:
                pass
    try:
        return 200, {"ok": True, "sesiones": _sesiones(dias)}
    except Exception as e:
        return 502, {"error": f"no se pudieron leer las listas: {e}"}
