"""
backend.servidor — servidor HTTP y enrutado.

La clase H es un despachador fino: extrae de cada petición un contexto `Req`
(método, ruta, usuario autenticado por Authelia, cuerpo JSON) y lo pasa por
la cadena de handlers registrados. El primero que devuelve algo distinto de
None resuelve la petición.

Los handlers de área viven en backend.handlers.* y no saben nada de HTTP:
reciben `Req` y devuelven (codigo, dict).
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from .handlers import actividades, agenda, clases, resumen, foto, webhooks, reservas, listas

PORT = int(os.environ.get("CAPTADOR_PORT", "8090"))
ORIGIN = os.environ.get("CAPTADOR_ORIGIN", "https://juliamoreno.yoga")

# Orden de la cadena de handlers. Cada uno devuelve (codigo, dict) o None.
_HANDLERS = [
    resumen.handle,
    actividades.handle,
    agenda.handle,
    clases.handle,
    foto.handle,
    webhooks.handle,
    reservas.handle,
    listas.handle,
]


class Req:
    """Contexto de una petición, independiente de HTTP, que reciben los
    handlers. `raw` da acceso al BaseHTTPRequestHandler para casos especiales
    (subida multipart)."""
    __slots__ = ("metodo", "path", "usuario", "_body", "raw")

    def __init__(self, metodo, path, usuario, body, raw):
        self.metodo = metodo
        self.path = path
        self.usuario = usuario
        self._body = body
        self.raw = raw

    @property
    def body(self):
        return self._body if self._body is not None else {}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, PATCH, GET, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def _responder(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def _leer_body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            return None

    def _usuario(self):
        # Authelia inyecta Remote-User tras autenticar. Si no está, no pasa.
        return self.headers.get("Remote-User")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _despachar(self, metodo, leer_cuerpo):
        # /salud responde sin tocar handlers ni leer cuerpo
        if self.path == "/salud" and metodo == "GET":
            return self._responder({"ok": True})
        # La subida de foto es multipart: no se parsea como JSON aquí; el
        # handler de foto lee del request crudo.
        if self.path == foto.RUTA and metodo == "POST":
            body = None
        elif leer_cuerpo:
            body = self._leer_body()
            if body is None:
                return self._responder({"error": "bad json"}, 400)
        else:
            body = {}
        req = Req(metodo, self.path, self._usuario(), body, self)
        for handler in _HANDLERS:
            res = handler(req)
            if res is not None:
                code, payload = res
                return self._responder(payload, code)
        return self._responder({"error": "not found"}, 404)

    def do_GET(self):
        self._despachar("GET", leer_cuerpo=False)

    def do_POST(self):
        self._despachar("POST", leer_cuerpo=True)

    def do_PATCH(self):
        self._despachar("PATCH", leer_cuerpo=True)

    def do_DELETE(self):
        self._despachar("DELETE", leer_cuerpo=True)


def arranca():
    print(f"backend escuchando en :{PORT} (origin {ORIGIN})")
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
