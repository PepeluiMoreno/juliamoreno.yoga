"""
backend.calcom.cliente — cliente mínimo de la API v2 de Cal.diy.

Exploración de la rama calcom-centric: valida que se puede leer desde
Cal.diy lo que la web pública necesita (tipos de evento, disponibilidad
y franjas reservables), que era el punto crítico para decidir si
Cal.diy puede ser la base del calendario.

La API v2 se autentica con Bearer token y exige la cabecera
'cal-api-version', que NO es global: cada recurso tiene la suya
(verificado el 17 jul 2026 contra la instancia real: con una versión
que el recurso no reconoce, responde 404 "Cannot GET", como si la ruta
no existiera). Versiones que funcionan:
  event-types  2024-06-14
  slots        2024-09-04
  bookings     2024-08-13

Variables de entorno esperadas:
  CALCOM_API_URL   base de la API v2 (p.ej. https://api-reservas.juliamoreno.yoga)
  CALCOM_API_KEY   token (cal_...)

Nada de esto toca NocoDB ni el backend de main: es un módulo aislado.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

VERSIONES = {
    "event-types": "2024-06-14",
    "slots": "2024-09-04",
    "bookings": "2024-08-13",
}


def _cfg():
    url = os.environ.get("CALCOM_API_URL", "").rstrip("/")
    key = os.environ.get("CALCOM_API_KEY", "")
    if not (url and key):
        raise RuntimeError("faltan CALCOM_API_URL / CALCOM_API_KEY en el entorno")
    return url, key


def _get(ruta, version, params=None):
    url, key = _cfg()
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    req = urllib.request.Request(f"{url}{ruta}{q}", method="GET")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("cal-api-version", version)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Cal.diy {e.code} en {ruta}: {cuerpo[:300]}")


def event_types():
    """Lista los tipos de evento (las 'clases' configuradas en Cal.diy)."""
    return _get("/v2/event-types", VERSIONES["event-types"])


def slots(event_type_id, desde, hasta):
    """Franjas reservables de un tipo de evento entre dos fechas ISO
    (YYYY-MM-DD). Es lo que alimentaría la disponibilidad de la web."""
    return _get("/v2/slots", VERSIONES["slots"], {
        "eventTypeId": event_type_id,
        "start": desde,
        "end": hasta,
    })


def bookings(desde=None, hasta=None):
    """Reservas existentes (para la lista de alumnos por clase). Filtros
    opcionales por rango de fechas."""
    params = {}
    if desde:
        params["afterStart"] = desde
    if hasta:
        params["beforeEnd"] = hasta
    return _get("/v2/bookings", VERSIONES["bookings"], params or None)


def aforo_por_hueco(event_type_id, desde, hasta):
    """Devuelve {inicio_utc: {'total': N, 'ocupadas': M, 'libres': L}}
    para cada franja del rango.

    IMPORTANTE: el endpoint de slots reporta seatsRemaining/seatsBooked
    pero NO los actualiza al reservar (verificado 17 jul 2026: una
    reserva aceptada deja el slot en seatsRemaining=total). El motor de
    Cal.diy sí descuenta bien (el booker muestra el aforo correcto), así
    que aquí lo calculamos a mano: total del slot menos asistentes de
    las reservas ACEPTADAS que caen en ese inicio. Este es el número
    fiable para la vista pública.
    """
    dias = slots(event_type_id, desde, hasta).get("data", {})
    reservas = bookings(desde, hasta).get("data", [])
    ocupacion = {}
    for b in reservas:
        if b.get("status") != "accepted":
            continue
        ini = b.get("start")
        ocupacion[ini] = ocupacion.get(ini, 0) + max(1, len(b.get("attendees", [])))
    resultado = {}
    for dia in dias:
        for s in dias[dia]:
            ini = s.get("start")
            total = s.get("seatsTotal")
            ocup = ocupacion.get(ini, 0)
            resultado[ini] = {
                "total": total,
                "ocupadas": ocup,
                "libres": (total - ocup) if isinstance(total, int) else None,
            }
    return resultado


def _post(ruta, version, cuerpo):
    url, key = _cfg()
    datos = json.dumps(cuerpo).encode()
    req = urllib.request.Request(f"{url}{ruta}", data=datos, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("cal-api-version", version)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        cuerpo_err = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Cal.diy {e.code} en {ruta}: {cuerpo_err[:300]}")


def crear_reserva(event_type_id, inicio_utc, nombre, email,
                  zona="Europe/Madrid", idioma="es"):
    """Crea una reserva A TRAVÉS DEL MOTOR de Cal.diy (regla de oro:
    nunca escribir en su base por fuera). inicio_utc en ISO con Z, tal
    como lo devuelve el endpoint de slots."""
    return _post("/v2/bookings", VERSIONES["bookings"], {
        "start": inicio_utc,
        "eventTypeId": event_type_id,
        "attendee": {
            "name": nombre,
            "email": email,
            "timeZone": zona,
            "language": idioma,
        },
    })


def cancelar_reserva(uid, motivo="Cancelación de prueba"):
    """Cancela una reserva por su uid, también a través del motor."""
    return _post(f"/v2/bookings/{uid}/cancel", VERSIONES["bookings"], {
        "cancellationReason": motivo,
    })


# --- Alta de clases en Cal.diy (horario + tipo de evento) -------------
# Se usan al dar de alta las clases reales de Julia desde lo que ya hay
# en NocoDB. La API v2 versiona por recurso, igual que en lectura.
VERSIONES["schedules"] = "2024-06-11"

DIAS_CAL = {"lun": "Monday", "mar": "Tuesday", "mie": "Wednesday",
            "jue": "Thursday", "vie": "Friday", "sab": "Saturday",
            "dom": "Sunday"}


def crear_horario(nombre, dias, inicio, fin, zona="Europe/Madrid"):
    """Crea un horario de disponibilidad con UNA franja semanal.

    dias: lista de claves cortas ('lun', 'mie'...). inicio/fin en HH:MM.
    Es lo que hace que la clase se repita cada semana: la recurrencia la
    pone la disponibilidad, no la función 'recurring' de Cal.com (que es
    excluyente con seats y significa otra cosa; ver docs).
    """
    return _post("/v2/schedules", VERSIONES["schedules"], {
        "name": nombre,
        "timeZone": zona,
        "isDefault": False,
        "availability": [{
            "days": [DIAS_CAL[d] for d in dias],
            "startTime": inicio,
            "endTime": fin,
        }],
    })


def crear_tipo_evento(titulo, slug, minutos, plazas, schedule_id,
                      lugar=None, descripcion=None):
    """Crea la clase como tipo de evento con aforo.

    RGPD: showAttendeeInfo en False (los alumnos no se ven entre sí) y
    showAvailabilityCount en True (el aforo sí es público). OJO con el
    nombre: es showAvailabilityCount, no showAvailableSeatsCount — la API
    descarta el campo desconocido y luego se queja del obligatorio que
    falta, con un 400 que despista.
    """
    cuerpo = {
        "title": titulo,
        "slug": slug,
        "lengthInMinutes": minutos,
        "description": descripcion or titulo,
        "scheduleId": schedule_id,
        "seats": {
            "seatsPerTimeSlot": plazas,
            "showAttendeeInfo": False,
            "showAvailabilityCount": True,
        },
    }
    if lugar:
        cuerpo["locations"] = [{"type": "address", "address": lugar,
                                "public": True}]
    return _post("/v2/event-types", VERSIONES["event-types"], cuerpo)
