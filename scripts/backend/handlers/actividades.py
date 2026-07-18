"""
backend.handlers.actividades — rutas /admin/api/actividades (GET/POST/PATCH).

Cada handler recibe `req` (contexto de la petición) y devuelve (codigo, dict).
Devuelve None si la ruta/método no le corresponde, para que el enrutador
siga probando otros handlers.
"""
from .. import datos
from ..util import limpio, slug, valido_texto
from ..web import dispara_rebuild

RUTA = "/admin/api/actividades"


def _lista():
    filas = datos.lee("Actividades")
    out = []
    for r in filas:
        out.append({
            "Id": r.get("Id"), "id": r.get("id"),
            "titulo_es": r.get("titulo_es"), "texto_es": r.get("texto_es"),
            "estado": r.get("estado"), "umbral": r.get("umbral"),
            "plazas": r.get("plazas"), "franjas": r.get("franjas"),
            "visible": r.get("visible"), "mostrar_contador": r.get("mostrar_contador"),
            "franjas_elegibles": r.get("franjas_elegibles"),
            "foto": r.get("foto"),
            "precio": r.get("precio"), "duracion": r.get("duracion"), "lugar": r.get("lugar"),
            "nivel": r.get("nivel"),
            "hasta": r.get("hasta"),
            "interesados": r.get("interesados"),
        })
    return out


def handle(req):
    if req.path != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}

    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "actividades": _lista()}
        except Exception as e:
            return 502, {"error": f"no se pudo leer: {e}"}

    if req.metodo == "POST":
        body = req.body
        titulo = limpio(body.get("titulo_es"), 200)
        if not valido_texto(titulo):
            return 422, {"error": "falta el título"}
        fila = {
            "id": slug(titulo),
            "titulo_es": titulo,
            "texto_es": limpio(body.get("texto_es"), 2000),
            "estado": limpio(body.get("estado"), 20) or "propuesta",
            "franjas": limpio(body.get("franjas"), 500),
            "es_hash": "",
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
        fila["foto"] = limpio(body.get("foto"), 500)
        fila["precio"] = limpio(body.get("precio"), 40)
        fila["duracion"] = limpio(body.get("duracion"), 40)
        fila["lugar"] = limpio(body.get("lugar"), 120)
        # Nivel de dificultad. En blanco = no se muestra nunca (no hay
        # valor por defecto: si Julia no lo especifica, no se inventa).
        fila["nivel"] = limpio(body.get("nivel"), 40)
        # Vigencia: pasada esta fecha la actividad se archiva sola y
        # deja el grid principal (sigue visible en /pasadas.html).
        fila["hasta"] = limpio(body.get("hasta"), 10)
        try:
            datos.guarda("Actividades", fila)
            dispara_rebuild()
            return 200, {"ok": True, "id": fila["id"]}
        except Exception as e:
            return 502, {"error": f"no se pudo crear: {e}"}

    if req.metodo == "PATCH":
        body = req.body
        if not body.get("Id"):
            return 422, {"error": "falta Id"}
        fila = {"Id": body["Id"]}
        for c in ("titulo_es", "texto_es", "estado", "franjas", "foto",
                  "precio", "duracion", "lugar", "nivel", "hasta"):
            if c in body:
                fila[c] = limpio(body[c], 2000)
        for c in ("umbral", "plazas"):
            if c in body and body[c] not in (None, ""):
                try:
                    fila[c] = int(body[c])
                except Exception:
                    pass
        for c in ("visible", "mostrar_contador", "franjas_elegibles"):
            if c in body:
                fila[c] = bool(body[c])
        # Al cambiar el texto ES, vaciar es_hash para forzar re-traducción
        if "titulo_es" in fila or "texto_es" in fila:
            fila["es_hash"] = ""
        try:
            datos.actualiza("Actividades", fila)
            dispara_rebuild()
            return 200, {"ok": True}
        except Exception as e:
            return 502, {"error": f"no se pudo guardar: {e}"}

    return None
