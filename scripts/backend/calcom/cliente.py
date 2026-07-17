"""
backend.calcom.cliente — cliente mínimo de la API v2 de Cal.com.

Exploración de la rama calcom-centric: valida que se puede leer desde
Cal.com lo que la web pública necesita (tipos de evento, disponibilidad
y franjas reservables), que era el punto crítico para decidir si
Cal.com puede ser la base del calendario.

La API v2 se autentica con Bearer token y exige la cabecera de versión
'cal-api-version'. En self-hosted, la base es la URL de la instancia de
API (un contenedor aparte del webapp), no la del webapp de reservas.

Variables de entorno esperadas:
  CALCOM_API_URL      base de la API v2 (p.ej. https://api-reservas.juliamoreno.yoga)
  CALCOM_API_KEY      token (cal_live_... o el que genere la instancia)
  CALCOM_API_VERSION  versión de la API (por defecto 2024-08-13)

Nada de esto toca NocoDB ni el backend de main: es un módulo aislado.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = os.environ.get("CALCOM_API_VERSION", "2024-08-13")


def _cfg():
    url = os.environ.get("CALCOM_API_URL", "").rstrip("/")
    key = os.environ.get("CALCOM_API_KEY", "")
    if not (url and key):
        raise RuntimeError("faltan CALCOM_API_URL / CALCOM_API_KEY en el entorno")
    return url, key


def _get(ruta, params=None):
    url, key = _cfg()
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    req = urllib.request.Request(f"{url}{ruta}{q}", method="GET")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("cal-api-version", API_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Cal.com {e.code} en {ruta}: {cuerpo[:300]}")


def event_types():
    """Lista los tipos de evento (las 'clases' configuradas en Cal.com)."""
    return _get("/v2/event-types")


def slots(event_type_id, desde, hasta):
    """Franjas reservables de un tipo de evento entre dos fechas ISO
    (YYYY-MM-DD). Es lo que alimentaría la disponibilidad de la web."""
    return _get("/v2/slots", {
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
    return _get("/v2/bookings", params or None)
