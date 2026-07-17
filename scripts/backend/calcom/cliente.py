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
