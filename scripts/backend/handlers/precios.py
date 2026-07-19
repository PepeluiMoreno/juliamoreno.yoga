"""
backend.handlers.precios — /admin/api/precios: las tarifas de la web.

Julia cambia IMPORTES y decide qué se enseña; los conceptos y sus nombres
en los cuatro idiomas los mantiene el soporte técnico en
data/contenido.json. Ese reparto es deliberado: cambiar un precio es
rutina del negocio, pero añadir un concepto obliga a traducirlo a cuatro
idiomas y a colocarlo en la web, que no es una tarea de mostrador.

    GET   /admin/api/precios   lista de líneas con importe y visibilidad
    PATCH /admin/api/precios   {"lineas": [{"id": ..., "valor": ...,
                                            "visible": ...}], "trial": bool}

La fuente de verdad de los IMPORTES es la tabla Precios de NocoDB, la
misma que ya lee build-web.py. Aquí se escribe allí y se dispara la
regeneración de la web, para que no haya dos caminos que puedan
contradecirse.
"""
import json
import os

from .. import datos
from ..web import dispara_rebuild

RUTA = "/admin/api/precios"

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_CONTENIDO = os.path.join(_REPO, "data", "contenido.json")


def _contenido():
    with open(_CONTENIDO, encoding="utf-8") as f:
        return json.load(f)


def _lineas():
    """Conceptos (de contenido.json) cruzados con importes (de NocoDB).

    El nombre y el orden salen del fichero; el importe y la visibilidad,
    de la tabla. Si una línea aún no está en la tabla se muestra con el
    valor del fichero, que es el que la web está enseñando ahora mismo.
    """
    data = _contenido()
    try:
        filas = {f.get("id"): f for f in datos.lee("Precios")}
    except Exception:
        filas = {}

    salida = []
    for ln in data["precios"]["lineas"]:
        fila = filas.get(ln["id"], {})
        salida.append({
            "id": ln["id"],
            "label": ln["label"]["es"],
            "valor": str(fila.get("valor") or ln.get("valor") or ""),
            "visible": (bool(fila.get("visible"))
                        if fila else bool(ln.get("visible", True))),
            "en_tabla": bool(fila),
        })
    trial = data["precios"].get("trial", {})
    return salida, {
        "label": (trial.get("label") or {}).get("es", ""),
        "visible": bool(trial.get("visible")),
    }


def _guarda(body):
    """Escribe importes y visibilidad en NocoDB. La primera clase de prueba
    vive en contenido.json (no tiene importe), así que se toca allí."""
    conocidos = {ln["id"] for ln in _contenido()["precios"]["lineas"]}
    try:
        filas = {f.get("id"): f for f in datos.lee("Precios")}
    except Exception as e:
        return 502, {"error": "no se pudo leer la tabla de precios: %s" % e}

    nuevas, cambios = [], []
    for ln in body.get("lineas") or []:
        lid = (ln.get("id") or "").strip()
        if lid not in conocidos:
            # No se inventan conceptos desde aquí: añadirlos exige
            # traducirlos y colocarlos en la web.
            continue
        campos = {
            "id": lid,
            "valor": str(ln.get("valor") or "").strip(),
            "visible": bool(ln.get("visible")),
        }
        fila = filas.get(lid)
        if fila:
            campos["Id"] = fila["Id"]
            cambios.append(campos)
        else:
            nuevas.append(campos)

    try:
        if cambios:
            datos.actualiza_varios("Precios", cambios)
        for f in nuevas:
            datos.guarda("Precios", f)
    except Exception as e:
        return 502, {"error": "no se pudieron guardar las tarifas: %s" % e}

    if "trial" in body:
        try:
            data = _contenido()
            data["precios"].setdefault("trial", {})["visible"] = bool(body["trial"])
            with open(_CONTENIDO, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
        except Exception as e:
            return 502, {"error": "no se pudo guardar la clase de prueba: %s" % e}

    dispara_rebuild()
    return 200, {"ok": True, "guardadas": len(cambios) + len(nuevas)}


def handle(req):
    ruta = req.path.partition("?")[0]
    if ruta != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}

    if req.metodo == "GET":
        try:
            lineas, trial = _lineas()
            return 200, {"ok": True, "lineas": lineas, "trial": trial}
        except Exception as e:
            return 502, {"error": "no se pudieron leer las tarifas: %s" % e}

    if req.metodo == "PATCH":
        return _guarda(req.body or {})

    return 405, {"error": "método no admitido"}
