"""
backend.handlers.reservas — reserva pública de plaza en una clase.

Ruta pública (no pasa por Authelia, como los webhooks): la usa un alumno
anónimo desde la web. Valida con cuidado y crea la reserva SIEMPRE a
través del motor de Cal.diy (regla de oro: nunca escribir la reserva por
fuera del motor), no directamente en NocoDB. Tras reservar, deja una
copia ligera en NocoDB para la lista de alumnos por clase y los avisos.

Dos rutas:
  GET  /disponibilidad?dias=N[&clase=ID]  → aforo por hueco; con clase,
       solo esa (enlace 'Reservar' de una actividad concreta)
  POST /reservar                  → {event_type_id, inicio, nombre, email}

El aforo se calcula por cruce (cliente.aforo_por_hueco): el endpoint de
slots de Cal.diy reporta seatsRemaining sin actualizar, pero el motor
descuenta bien; ver cliente.py.

La API key vive en el entorno del backend (CALCOM_API_KEY), nunca viaja
al navegador: por eso el POST pasa por aquí y no se llama a Cal.diy desde
el cliente web.
"""
import datetime
import re
import urllib.parse

from .. import datos
from ..calcom import cliente
from ..util import limpio, valido_texto

RUTA_DISPONIBILIDAD = "/disponibilidad"
RUTA_RESERVAR = "/reservar"
RUTA_ACTIVIDAD = "/actividad"

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valido_email(s):
    return bool(s) and len(s) <= 120 and _EMAIL.match(s) is not None


def _ahora_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _actividad_de(cal_id):
    """Ficha de la actividad de NocoDB enlazada con esa clase de Cal.diy.

    El alumno que llega desde una actividad tiene que ver QUÉ está
    reservando (texto, duración, lugar, precio, foto), no solo horas
    sueltas. Cal.diy solo guarda título y duración; lo demás vive en
    NocoDB, y el cruce lo hace cal_event_type_id.
    Si algo falla, se devuelve None: la cabecera es un extra, nunca debe
    tumbar la disponibilidad.
    """
    try:
        for fila in datos.lee("Actividades"):
            if int(fila.get("cal_event_type_id") or 0) != int(cal_id):
                continue
            return {
                "titulo": fila.get("titulo_es"),
                "texto": fila.get("texto_es"),
                "duracion": fila.get("duracion"),
                "lugar": fila.get("lugar"),
                "nivel": fila.get("nivel"),
                "precio": fila.get("precio"),
                "foto": fila.get("foto"),
            }
    except Exception:
        pass
    return None


def _ficha(fila):
    return {
        "id": fila.get("id"),
        "titulo": fila.get("titulo_es"),
        "texto": fila.get("texto_es"),
        "duracion": fila.get("duracion"),
        "lugar": fila.get("lugar"),
        "nivel": fila.get("nivel"),
        "precio": fila.get("precio"),
        "foto": fila.get("foto"),
        "estado": fila.get("estado"),
        "franjas": fila.get("franjas"),
        "franjas_elegibles": bool(fila.get("franjas_elegibles")),
        "cal_event_type_id": int(fila.get("cal_event_type_id") or 0),
        "completa": _sin_plazas(int(fila.get("cal_event_type_id") or 0)),
    }


def _sin_plazas(cal_id, dias=30):
    """¿Sin plazas a ninguna hora del próximo mes? Ante cualquier duda
    (error, sin clase enlazada) se responde False: mejor no avisar que
    avisar en falso."""
    if not cal_id:
        return False
    try:
        hoy = datetime.date.today()
        fin = hoy + datetime.timedelta(days=dias)
        aforo = cliente.aforo_por_hueco(cal_id, hoy.isoformat(), fin.isoformat())
        return bool(aforo) and all((v.get("libres") or 0) <= 0
                                   for v in aforo.values())
    except Exception:
        return False


def _actividad(aid):
    """Ficha de una actividad por su id, para la vista de interés.

    Pública: la usa interes.html para pintar la cabecera de qué está
    apuntándose el visitante antes de dejar sus datos.
    """
    if not aid:
        return 422, {"error": "falta el id de actividad"}
    try:
        for fila in datos.lee("Actividades"):
            if fila.get("id") == aid:
                if not fila.get("visible", True):
                    return 404, {"error": "actividad no disponible"}
                return 200, {"ok": True, "actividad": _ficha(fila)}
        return 404, {"error": "actividad no encontrada"}
    except Exception as e:
        return 502, {"error": f"no se pudo leer la actividad: {e}"}


def _disponibilidad(body_dias, solo_clase=None):
    """Aforo por hueco de las clases para los próximos N días. Pensado
    para que la web pinte la disponibilidad con su estilo.

    solo_clase: si viene un event_type_id, devuelve solo esa clase (es
    lo que usa el enlace "Reservar" de cada actividad, para que el
    alumno vea la clase que eligió y no el listado entero)."""
    try:
        dias = int(body_dias) if body_dias else 14
    except (TypeError, ValueError):
        dias = 14
    dias = max(1, min(dias, 60))
    hoy = datetime.date.today()
    fin = hoy + datetime.timedelta(days=dias)
    try:
        tipos = cliente.event_types().get("data", [])
        if solo_clase is not None:
            tipos = [t for t in tipos if t.get("id") == solo_clase]
            if not tipos:
                return 404, {"error": "clase no encontrada"}
        salida = []
        for t in tipos:
            aforo = cliente.aforo_por_hueco(
                t["id"], hoy.isoformat(), fin.isoformat())
            huecos = [
                {"inicio": ini, "total": a["total"],
                 "libres": a["libres"], "ocupadas": a["ocupadas"]}
                for ini, a in sorted(aforo.items())
            ]
            entrada = {
                "event_type_id": t["id"],
                "titulo": t.get("title"),
                "huecos": huecos,
            }
            # Solo al pedir una clase concreta: la ficha para la cabecera.
            if solo_clase is not None:
                entrada["actividad"] = _actividad_de(t["id"])
            salida.append(entrada)
        return 200, {"ok": True, "clases": salida}
    except Exception as e:
        return 502, {"error": f"no se pudo leer disponibilidad: {e}"}


def _reservar(body):
    nombre = limpio(body.get("nombre"), 80)
    email = limpio(body.get("email"), 120)
    inicio = limpio(body.get("inicio"), 40)
    event_type_id = body.get("event_type_id")

    if not valido_texto(nombre):
        return 422, {"error": "nombre no válido"}
    if not _valido_email(email):
        return 422, {"error": "email no válido"}
    if not inicio or not isinstance(event_type_id, int):
        return 422, {"error": "hueco no válido"}

    # Comprobar aforo ANTES de reservar: si el hueco está lleno, no
    # llamamos al motor. (El motor también valida, pero así damos un
    # error claro y evitamos una llamada de escritura inútil.)
    try:
        hoy = datetime.date.today()
        fin = hoy + datetime.timedelta(days=60)
        aforo = cliente.aforo_por_hueco(
            event_type_id, hoy.isoformat(), fin.isoformat())
        estado = aforo.get(inicio)
        if estado is None:
            return 422, {"error": "el hueco ya no existe"}
        if estado["libres"] is not None and estado["libres"] <= 0:
            return 409, {"error": "clase completa"}
    except Exception as e:
        return 502, {"error": f"no se pudo comprobar aforo: {e}"}

    # Reservar en el motor de Cal.diy (única vía de escritura de reservas)
    try:
        r = cliente.crear_reserva(event_type_id, inicio, nombre, email)
        data = r.get("data", r)
        uid = data.get("uid")
        if not uid or data.get("status") not in ("accepted", "pending"):
            return 502, {"error": "el motor no aceptó la reserva"}
    except Exception as e:
        return 502, {"error": f"no se pudo reservar: {e}"}

    # Copia ligera en NocoDB para lista de alumnos y avisos. Si falla,
    # la reserva en el motor YA es válida: no la deshacemos, solo
    # avisamos de que el registro auxiliar no se guardó.
    registro_ok = True
    try:
        datos.guarda("Reservas", {
            "cal_uid": uid,
            "event_type_id": event_type_id,
            "inicio": inicio,
            "nombre": nombre,
            "email": email,
            "estado": data.get("status"),
            "fecha": _ahora_iso(),
        })
    except Exception:
        registro_ok = False

    # Si esa reserva ha dejado la clase sin plazas, la web debe reflejarlo:
    # el badge "No quedan plazas" se calcula al generar el sitio.
    try:
        from ..web import dispara_rebuild
        dispara_rebuild()
    except Exception:
        pass

    return 200, {"ok": True, "uid": uid, "registro_auxiliar": registro_ok}


def handle(req):
    # El servidor no separa la query string: req.path puede llegar como
    # "/disponibilidad?dias=20". Partimos aquí (opción A: no tocar el
    # servidor central, que ya funciona para el resto de handlers).
    ruta, _, query = req.path.partition("?")
    if req.metodo == "GET" and ruta == RUTA_DISPONIBILIDAD:
        dias = None
        clase = None
        for par in query.split("&"):
            if par.startswith("dias="):
                dias = par[5:]
            elif par.startswith("clase="):
                try:
                    clase = int(par[6:])
                except ValueError:
                    return 422, {"error": "clase no válida"}
        return _disponibilidad(dias, clase)
    if req.metodo == "GET" and ruta == RUTA_ACTIVIDAD:
        aid = None
        for par in query.split("&"):
            if par.startswith("id="):
                aid = limpio(urllib.parse.unquote(par[3:]), 80)
        return _actividad(aid)
    if req.metodo == "POST" and ruta == RUTA_RESERVAR:
        return _reservar(req.body)
    return None
