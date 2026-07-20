"""
backend.handlers.actividades — rutas de servicios y sus temporadas.

Modelo (ver docs/funcionalidades/actividades-clases-agenda.md):
  - SERVICIO: lo que Julia ofrece, atemporal ("Hatha yoga"). Identidad
    (título, texto, foto, nivel) y si se sigue ofertando (la cartera).
  - ACTIVIDAD (temporada): una programación del servicio en una extensión
    temporal ("Hatha, sep-dic 2026"). Cuelga de un servicio (servicio_uuid)
    y lleva lo temporal (estado, hasta, franjas, aforo, enlace a Cal.diy).

Dos rutas, cada una con su CRUD:
  /admin/api/servicios     GET/POST/PATCH   identidad + cartera
  /admin/api/actividades   GET/POST/PATCH   programación temporal

Los identificadores son UUID (uuid4().hex), no slugs. NocoDB mantiene su
`Id` numérico, que es el que viaja en los PATCH.

Cada handler recibe `req` y devuelve (codigo, dict), o None si no le
corresponde la ruta/método.
"""
import uuid

from .. import datos
from ..util import limpio, valido_texto
from ..web import dispara_rebuild

RUTA_SERVICIOS = "/admin/api/servicios"
RUTA_ACTIVIDADES = "/admin/api/actividades"


def _nuevo_uuid():
    return uuid.uuid4().hex


# --- Servicios (identidad + cartera) ---------------------------------------

def _servicios_lista():
    out = []
    for r in datos.lee("Servicios"):
        out.append({
            "Id": r.get("Id"), "uuid": r.get("uuid"),
            "se_sigue_ofertando": r.get("se_sigue_ofertando"),
            "titulo_es": r.get("titulo_es"), "texto_es": r.get("texto_es"),
            "foto": r.get("foto"), "nivel": r.get("nivel"),
        })
    return out


def _servicios_handle(req):
    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "servicios": _servicios_lista()}
        except Exception as e:
            return 502, {"error": f"no se pudo leer: {e}"}

    if req.metodo == "POST":
        body = req.body
        titulo = limpio(body.get("titulo_es"), 200)
        if not valido_texto(titulo):
            return 422, {"error": "falta el título del servicio"}
        fila = {
            "uuid": _nuevo_uuid(),
            "titulo_es": titulo,
            "texto_es": limpio(body.get("texto_es"), 2000),
            "foto": limpio(body.get("foto"), 500),
            "nivel": limpio(body.get("nivel"), 40),
            "se_sigue_ofertando": bool(body.get("se_sigue_ofertando", True)),
            "es_hash": "",
        }
        try:
            datos.guarda("Servicios", fila)
            dispara_rebuild()
            return 200, {"ok": True, "uuid": fila["uuid"]}
        except Exception as e:
            return 502, {"error": f"no se pudo crear: {e}"}

    if req.metodo == "PATCH":
        body = req.body
        if not body.get("Id"):
            return 422, {"error": "falta Id"}
        fila = {"Id": body["Id"]}
        for c in ("titulo_es", "texto_es", "foto", "nivel"):
            if c in body:
                fila[c] = limpio(body[c], 2000)
        if "se_sigue_ofertando" in body:
            fila["se_sigue_ofertando"] = bool(body["se_sigue_ofertando"])
        # Al cambiar el texto ES, vaciar es_hash para forzar re-traducción.
        if "titulo_es" in fila or "texto_es" in fila:
            fila["es_hash"] = ""
        try:
            datos.actualiza("Servicios", fila)
            dispara_rebuild()
            return 200, {"ok": True}
        except Exception as e:
            return 502, {"error": f"no se pudo guardar: {e}"}

    if req.metodo == "DELETE":
        return _borrar("Servicios", req.body or {})

    return None


def _borrar(tabla, body):
    """Manda a la papelera (o borra para siempre con definitivo=true).

    Retirar algo de la oferta NO es borrarlo: para eso está
    se_sigue_ofertando en el servicio, que conserva el historial. Aquí se
    borra de verdad, y por eso el panel enseña antes qué arrastra.
    """
    if not body.get("Id"):
        return 422, {"error": "falta Id"}
    definitivo = bool(body.get("definitivo"))
    try:
        datos.borra(tabla, body["Id"], definitivo=definitivo)
        dispara_rebuild()
        return 200, {"ok": True, "definitivo": definitivo}
    except Exception as e:
        return 502, {"error": f"no se pudo eliminar: {e}"}


# --- Actividades / temporadas (programación temporal) ----------------------

def _actividades_lista():
    out = []
    for r in datos.lee("Actividades"):
        out.append({
            "Id": r.get("Id"), "uuid": r.get("uuid"),
            "servicio_uuid": r.get("servicio_uuid"),
            "estado": r.get("estado"), "hasta": r.get("hasta"),
            "umbral": r.get("umbral"), "plazas": r.get("plazas"),
            "franjas": r.get("franjas"), "franjas_elegibles": r.get("franjas_elegibles"),
            "visible": r.get("visible"), "mostrar_contador": r.get("mostrar_contador"),
            "cal_event_type_id": r.get("cal_event_type_id"),
            "precio": r.get("precio"), "duracion": r.get("duracion"),
            "lugar": r.get("lugar"), "interesados": r.get("interesados"),
        })
    return out


def _actividades_handle(req):
    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "actividades": _actividades_lista()}
        except Exception as e:
            return 502, {"error": f"no se pudo leer: {e}"}

    if req.metodo == "POST":
        body = req.body
        servicio_uuid = limpio(body.get("servicio_uuid"), 40)
        if not servicio_uuid:
            return 422, {"error": "una temporada necesita un servicio (servicio_uuid)"}
        fila = {
            "uuid": _nuevo_uuid(),
            "servicio_uuid": servicio_uuid,
            "estado": limpio(body.get("estado"), 20) or "propuesta",
            "franjas": limpio(body.get("franjas"), 500),
            "interesados": 0,
        }
        for c in ("umbral", "plazas"):
            if body.get(c) not in (None, ""):
                try:
                    fila[c] = int(body[c])
                except Exception:
                    pass
        fila["visible"] = bool(body.get("visible", True))
        fila["mostrar_contador"] = bool(body.get("mostrar_contador", True))
        fila["franjas_elegibles"] = bool(body.get("franjas_elegibles", False))
        fila["precio"] = limpio(body.get("precio"), 40)
        fila["duracion"] = limpio(body.get("duracion"), 40)
        fila["lugar"] = limpio(body.get("lugar"), 120)
        # Vigencia: pasada esta fecha la temporada se archiva sola y deja el
        # grid principal (sigue visible en /pasadas.html).
        fila["hasta"] = limpio(body.get("hasta"), 10)
        try:
            datos.guarda("Actividades", fila)
            dispara_rebuild()
            return 200, {"ok": True, "uuid": fila["uuid"]}
        except Exception as e:
            return 502, {"error": f"no se pudo crear: {e}"}

    if req.metodo == "PATCH":
        body = req.body
        if not body.get("Id"):
            return 422, {"error": "falta Id"}
        fila = {"Id": body["Id"]}
        for c in ("servicio_uuid", "estado", "franjas", "precio", "duracion",
                  "lugar", "hasta"):
            if c in body:
                fila[c] = limpio(body[c], 500)
        for c in ("umbral", "plazas"):
            if c in body and body[c] not in (None, ""):
                try:
                    fila[c] = int(body[c])
                except Exception:
                    pass
        for c in ("visible", "mostrar_contador", "franjas_elegibles"):
            if c in body:
                fila[c] = bool(body[c])
        try:
            datos.actualiza("Actividades", fila)
            dispara_rebuild()
            return 200, {"ok": True}
        except Exception as e:
            return 502, {"error": f"no se pudo guardar: {e}"}

    if req.metodo == "DELETE":
        return _borrar("Actividades", req.body or {})

    return None


def handle(req):
    if req.path == RUTA_SERVICIOS:
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _servicios_handle(req)
    if req.path == RUTA_ACTIVIDADES:
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _actividades_handle(req)
    return None
