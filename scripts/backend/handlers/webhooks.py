"""
backend.handlers.webhooks — captación de formularios de la web pública.

Las rutas originales del servicio: recogen los datos que envían los
formularios del sitio (contacto e interés en una actividad) y los guardan en
NocoDB. Son públicas (no pasan por Authelia), así que validan con cuidado.
"""
import datetime

from .. import datos
from ..util import limpio, valido_texto


def _ahora_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _contacto(body):
    nombre = limpio(body.get("nombre"), 80)
    telefono = limpio(body.get("telefono"), 40)
    asunto = limpio(body.get("asunto"), 500)
    if not (valido_texto(nombre) and telefono and valido_texto(asunto)):
        return 422, {"error": "datos no válidos"}
    try:
        datos.guarda("Contactos", {
            "nombre": nombre, "telefono": telefono, "asunto": asunto,
            "idioma": limpio(body.get("idioma"), 5) or "es",
            "fecha": _ahora_iso(),
            "atendido": False,
        })
        return 200, {"ok": True}
    except Exception:
        return 502, {"error": "no se pudo guardar"}


def _interes(body):
    nombre = limpio(body.get("nombre"), 80)
    contacto = limpio(body.get("contacto"), 80)
    actividad = limpio(body.get("actividad"), 80)
    franjas = body.get("franjas") or []
    if not (valido_texto(nombre) and contacto and actividad):
        return 422, {"error": "datos no válidos"}
    try:
        datos.guarda("Interesados", {
            "actividad": actividad, "nombre": nombre, "contacto": contacto,
            "franjas": ",".join(franjas) if isinstance(franjas, list) else limpio(franjas),
            "idioma": limpio(body.get("idioma"), 5) or "es",
            "fecha": _ahora_iso(),
        })
        return 200, {"ok": True}
    except Exception:
        return 502, {"error": "no se pudo guardar"}


_RUTAS = {
    "/webhook/contacto": _contacto,
    "/webhook/interes": _interes,
}


def handle(req):
    if req.metodo != "POST" or req.path not in _RUTAS:
        return None
    return _RUTAS[req.path](req.body)
