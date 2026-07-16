"""
backend.handlers.foto — ruta /admin/api/foto (POST multipart).

A diferencia del resto, no recibe JSON sino un formulario multipart con el
fichero. Por eso lee del request crudo (req.raw) en vez de req.body.
"""
import cgi

from ..fotos import guarda_foto

RUTA = "/admin/api/foto"
MAX_FOTO = 12 * 1024 * 1024  # 12 MB


def handle(req):
    if req.path != RUTA or req.metodo != "POST":
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}
    raw = req.raw  # el BaseHTTPRequestHandler original
    ctype = raw.headers.get("Content-Type", "")
    if "multipart/form-data" not in ctype:
        return 400, {"error": "se esperaba multipart"}
    n = int(raw.headers.get("Content-Length", 0))
    if n > MAX_FOTO:
        return 413, {"error": "la foto es demasiado grande (máx. 12 MB)"}
    try:
        form = cgi.FieldStorage(
            fp=raw.rfile, headers=raw.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": ctype})
        item = form["foto"] if "foto" in form else None
        if item is None or not getattr(item, "file", None):
            return 422, {"error": "no llegó ninguna foto"}
        contenido = item.file.read()
        url = guarda_foto(contenido, getattr(item, "filename", "foto"))
        return 200, {"ok": True, "url": url}
    except ValueError as e:
        return 422, {"error": str(e)}
    except Exception as e:
        return 502, {"error": f"no se pudo subir: {e}"}
