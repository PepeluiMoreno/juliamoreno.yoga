#!/usr/bin/env python3
"""
captador.py — micro-servicio de captación de formularios.

Expone dos endpoints que la web invoca:
  POST /webhook/contacto  -> guarda en la tabla Contactos
  POST /webhook/interes   -> guarda en la tabla Interesados (con franjas)

Escribe en NocoDB usando su API REST con el token del entorno (que NUNCA
viaja al navegador: por eso hace falta este intermediario y no un fetch
directo desde la web). Descubre las tablas por nombre, igual que el resto
de scripts. Sin dependencias externas: sólo la stdlib.

Config (del .env, cargado por nocolib):
  NOCODB_URL, NOCODB_TOKEN, NOCODB_BASE
  CAPTADOR_PORT (opcional, por defecto 8090)
  CAPTADOR_ORIGIN (opcional, para CORS; por defecto https://juliamoreno.yoga)
"""
import json, os, sys, pathlib, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nocolib as nc

PORT = int(os.environ.get("CAPTADOR_PORT", "8090"))
ORIGIN = os.environ.get("CAPTADOR_ORIGIN", "https://juliamoreno.yoga")

# Resolución de IDs de tabla una vez al arrancar (y cache)
_TABLAS = {}


def resolver_tablas():
    global _TABLAS
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if not bid:
        raise RuntimeError(f"base '{base}' no encontrada en NocoDB")
    _TABLAS = nc.tablas(url, tok, bid)
    return url, tok


def guarda(tabla, fila):
    url, tok, _ = nc.cfg()
    if tabla not in _TABLAS:
        resolver_tablas()
    tid = _TABLAS[tabla]
    nc.api(url, tok, "POST", f"/api/v2/tables/{tid}/records", [fila])


def limpio(v, n=200):
    return str(v or "").strip()[:n]


def valido_texto(s):
    # antispam mínimo: no vacío, sin URLs, longitud razonable
    return s and "http://" not in s.lower() and "https://" not in s.lower()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # sonda de salud
        if self.path == "/salud":
            return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            return self._json({"error": "bad json"}, 400)

        if self.path == "/webhook/contacto":
            nombre = limpio(body.get("nombre"), 80)
            telefono = limpio(body.get("telefono"), 40)
            asunto = limpio(body.get("asunto"), 500)
            if not (valido_texto(nombre) and telefono and valido_texto(asunto)):
                return self._json({"error": "datos no válidos"}, 422)
            try:
                guarda("Contactos", {
                    "nombre": nombre, "telefono": telefono, "asunto": asunto,
                    "idioma": limpio(body.get("idioma"), 5) or "es",
                    "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "atendido": False,
                })
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"error": "no se pudo guardar"}, 502)

        if self.path == "/webhook/interes":
            nombre = limpio(body.get("nombre"), 80)
            contacto = limpio(body.get("contacto"), 80)
            actividad = limpio(body.get("actividad"), 80)
            franjas = body.get("franjas") or []
            if not (valido_texto(nombre) and contacto and actividad):
                return self._json({"error": "datos no válidos"}, 422)
            try:
                guarda("Interesados", {
                    "actividad": actividad, "nombre": nombre, "contacto": contacto,
                    "franjas": ",".join(franjas) if isinstance(franjas, list) else limpio(franjas),
                    "idioma": limpio(body.get("idioma"), 5) or "es",
                    "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"error": "no se pudo guardar"}, 502)

        self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    nc.carga_env()
    try:
        resolver_tablas()
        print(f"captador: tablas resueltas {list(_TABLAS)}")
    except Exception as e:
        print(f"captador: aviso, no pude resolver tablas al arrancar ({e}); "
              f"se reintentará en cada petición")
    print(f"captador escuchando en :{PORT} (origin {ORIGIN})")
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
