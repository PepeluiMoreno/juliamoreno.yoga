"""
backend.handlers.lugares — /admin/api/lugares (GET/POST/PATCH/DELETE).

Los sitios donde se da clase. Antes eran texto libre repetido en tres tablas
—"Maro", "maro" y "Estudio Maro" podían convivir como si fueran locales
distintos— más una tabla `Horarios` que solo guardaba si se publicaban.

Un lugar no es una etiqueta: condiciona lo que se puede programar.
  - `aforo` acota las plazas de una actividad: doce esterillas no caben en
    un local de diez.
  - `disponibilidad` acota las horas: un local municipal no abre a cualquiera.
Las dos cosas se comprueban en los DOS niveles de planificación —el
calendario semanal de la actividad y la clase suelta de la agenda—, en
backend.agenda (valida_horario_actividad, cabe_en_lugar).

Y es también lo que el alumno necesita para llegar: la dirección y las
coordenadas con las que se pinta el mapa.
"""
import json
import uuid

from .. import datos
from ..util import limpio, valido_texto
from ..web import dispara_rebuild

RUTA = "/admin/api/lugares"


def _lista():
    out = []
    for r in datos.lee("Lugares"):
        out.append({
            "Id": r.get("Id"), "uuid": r.get("uuid"),
            "nombre_es": r.get("nombre_es"), "nombre_en": r.get("nombre_en"),
            "nombre_fr": r.get("nombre_fr"), "nombre_de": r.get("nombre_de"),
            "direccion": r.get("direccion"),
            "lat": r.get("lat"), "lon": r.get("lon"),
            "foto": r.get("foto"),
            "contacto_nombre": r.get("contacto_nombre"),
            "contacto_telefono": r.get("contacto_telefono"),
            "aforo": r.get("aforo"),
            "disponibilidad": r.get("disponibilidad"),
            "visible": r.get("visible"), "notas": r.get("notas"),
        })
    out.sort(key=lambda x: (x["nombre_es"] or "").lower())
    return out


def _coord(v):
    """Latitud/longitud como número, o None si no viene o no es válida."""
    if v in (None, ""):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _valida_disponibilidad(crudo):
    """El horario del local llega como JSON. Se comprueba aquí para no
    guardar algo que luego la planificación no sepa leer."""
    if not crudo:
        return "", None
    try:
        franjas = json.loads(crudo)
    except Exception:
        return None, "el horario del local no es una lista válida"
    if not isinstance(franjas, list):
        return None, "el horario del local no es una lista válida"
    for f in franjas:
        if not isinstance(f, dict) or not f.get("dia"):
            return None, "cada franja necesita día, desde y hasta"
        if not f.get("desde") or not f.get("hasta"):
            return None, "cada franja necesita hora de apertura y de cierre"
    return json.dumps(franjas, ensure_ascii=False), None


def _campos(body, fila):
    for c in ("nombre_es", "nombre_en", "nombre_fr", "nombre_de",
              "direccion", "notas",
              "foto", "contacto_nombre", "contacto_telefono"):
        if c in body:
            fila[c] = limpio(body[c], 500)
    for c in ("lat", "lon"):
        if c in body:
            fila[c] = _coord(body[c])
    if "aforo" in body:
        try:
            fila["aforo"] = int(body["aforo"]) if body["aforo"] not in (None, "") else None
        except Exception:
            pass
    if "visible" in body:
        fila["visible"] = bool(body["visible"])
    if "disponibilidad" in body:
        valor, error = _valida_disponibilidad(body["disponibilidad"])
        if error:
            return error
        fila["disponibilidad"] = valor
    return None


def handle(req):
    if req.path != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}

    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "lugares": _lista()}
        except Exception as e:
            return 502, {"error": f"no se pudieron leer los lugares: {e}"}

    if req.metodo == "POST":
        body = req.body or {}
        nombre = limpio(body.get("nombre_es"), 200)
        if not valido_texto(nombre):
            return 422, {"error": "el lugar necesita un nombre"}
        fila = {"uuid": uuid.uuid4().hex, "nombre_es": nombre}
        error = _campos(body, fila)
        if error:
            return 422, {"error": error}
        fila.setdefault("visible", True)
        try:
            datos.guarda("Lugares", fila)
            dispara_rebuild()
            return 200, {"ok": True, "uuid": fila["uuid"]}
        except Exception as e:
            return 502, {"error": f"no se pudo crear: {e}"}

    if req.metodo == "PATCH":
        body = req.body or {}
        if not body.get("Id"):
            return 422, {"error": "falta Id"}
        fila = {"Id": body["Id"]}
        error = _campos(body, fila)
        if error:
            return 422, {"error": error}
        try:
            datos.actualiza("Lugares", fila)
            dispara_rebuild()
            return 200, {"ok": True}
        except Exception as e:
            return 502, {"error": f"no se pudo guardar: {e}"}

    if req.metodo == "DELETE":
        body = req.body or {}
        if not body.get("Id"):
            return 422, {"error": "falta Id"}
        # Un lugar en uso no se borra a la ligera: las clases que lo
        # referencian se quedarían señalando al vacío.
        try:
            fila = next((l for l in datos.lee("Lugares")
                         if str(l.get("Id")) == str(body["Id"])), None)
            if fila and bool(body.get("definitivo")):
                u = fila.get("uuid") or ""
                en_uso = sum(1 for t in ("Actividades", "Clases", "Agenda")
                             for r in datos.lee(t)
                             if (r.get("lugar_uuid") or "") == u)
                if en_uso:
                    return 409, {"error": "ese lugar lo usan %d clases o "
                                          "actividades: mándalo a la papelera "
                                          "o cámbialas antes." % en_uso}
            datos.borra("Lugares", body["Id"],
                        definitivo=bool(body.get("definitivo")))
            dispara_rebuild()
            return 200, {"ok": True}
        except Exception as e:
            return 502, {"error": f"no se pudo eliminar: {e}"}

    return None
