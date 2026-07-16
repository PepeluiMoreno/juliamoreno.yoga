#!/usr/bin/env python3
"""
captador.py — micro-servicio de captación de formularios y backoffice.

Endpoints públicos (los invoca la web):
  POST /webhook/contacto  -> guarda en la tabla Contactos
  POST /webhook/interes   -> guarda en la tabla Interesados (con franjas)

Endpoints de administración (bajo /admin/api/*, protegidos por Authelia en
Traefik; el captador confía en la cabecera Remote-User que Authelia inyecta):
  GET  /admin/api/actividades       -> lista actividades (campos _es y gestión)
  POST /admin/api/actividades       -> crea una actividad
  PATCH /admin/api/actividades      -> edita una actividad (por Id)

Escribe en NocoDB con el token del entorno (que NUNCA viaja al navegador).
Sin dependencias externas: sólo la stdlib.
"""
import json, os, sys, pathlib, datetime, re
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nocolib as nc

PORT = int(os.environ.get("CAPTADOR_PORT", "8090"))
ORIGIN = os.environ.get("CAPTADOR_ORIGIN", "https://juliamoreno.yoga")

_TABLAS = {}


def resolver_tablas():
    global _TABLAS
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if not bid:
        raise RuntimeError(f"base '{base}' no encontrada en NocoDB")
    _TABLAS = nc.tablas(url, tok, bid)
    return url, tok


def _tid(tabla):
    if tabla not in _TABLAS:
        resolver_tablas()
    return _TABLAS[tabla]


def guarda(tabla, fila):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "POST", f"/api/v2/tables/{_tid(tabla)}/records", [fila])


def actualiza(tabla, fila):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "PATCH", f"/api/v2/tables/{_tid(tabla)}/records", [fila])


def lee(tabla):
    url, tok, _ = nc.cfg()
    return nc.records(url, tok, _tid(tabla))


def limpio(v, n=200):
    return str(v or "").strip()[:n]


def valido_texto(s):
    return s and "http://" not in s.lower() and "https://" not in s.lower()


def slug(s):
    s = (s or "").lower().strip()
    s = re.sub(r"[áàä]", "a", s); s = re.sub(r"[éèë]", "e", s)
    s = re.sub(r"[íìï]", "i", s); s = re.sub(r"[óòö]", "o", s)
    s = re.sub(r"[úùü]", "u", s); s = re.sub(r"ñ", "n", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "actividad"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, PATCH, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            return None

    def _admin_user(self):
        # Authelia inyecta Remote-User tras autenticar. Si no está, no pasa.
        return self.headers.get("Remote-User")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/salud":
            return self._json({"ok": True})
        if self.path == "/admin/api/actividades":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            try:
                filas = lee("Actividades")
                out = []
                for r in filas:
                    out.append({
                        "Id": r.get("Id"), "id": r.get("id"),
                        "titulo_es": r.get("titulo_es"), "texto_es": r.get("texto_es"),
                        "estado": r.get("estado"), "umbral": r.get("umbral"),
                        "plazas": r.get("plazas"), "franjas": r.get("franjas"),
                        "visible": r.get("visible"), "mostrar_contador": r.get("mostrar_contador"),
                        "interesados": r.get("interesados"),
                    })
                return self._json({"ok": True, "actividades": out})
            except Exception as e:
                return self._json({"error": f"no se pudo leer: {e}"}, 502)
        self._json({"error": "not found"}, 404)

    def do_PATCH(self):
        if self.path == "/admin/api/actividades":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            body = self._body()
            if body is None:
                return self._json({"error": "bad json"}, 400)
            if not body.get("Id"):
                return self._json({"error": "falta Id"}, 422)
            fila = {"Id": body["Id"]}
            for c in ("titulo_es", "texto_es", "estado", "franjas"):
                if c in body:
                    fila[c] = limpio(body[c], 2000)
            for c in ("umbral", "plazas"):
                if c in body and body[c] not in (None, ""):
                    try: fila[c] = int(body[c])
                    except: pass
            for c in ("visible", "mostrar_contador"):
                if c in body:
                    fila[c] = bool(body[c])
            # Al cambiar el texto ES, vaciar es_hash para forzar re-traducción
            if "titulo_es" in fila or "texto_es" in fila:
                fila["es_hash"] = ""
            try:
                actualiza("Actividades", fila)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"error": f"no se pudo guardar: {e}"}, 502)
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        body = self._body()
        if body is None:
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
            except Exception:
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
            except Exception:
                return self._json({"error": "no se pudo guardar"}, 502)

        if self.path == "/admin/api/actividades":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            titulo = limpio(body.get("titulo_es"), 200)
            if not valido_texto(titulo):
                return self._json({"error": "falta el título"}, 422)
            fila = {
                "id": slug(titulo),
                "titulo_es": titulo,
                "texto_es": limpio(body.get("texto_es"), 2000),
                "estado": limpio(body.get("estado"), 20) or "tentativa",
                "franjas": limpio(body.get("franjas"), 500),
                "es_hash": "",
                "interesados": 0,
            }
            for c in ("umbral", "plazas"):
                if body.get(c) not in (None, ""):
                    try: fila[c] = int(body[c])
                    except: pass
            fila["visible"] = bool(body.get("visible", True))
            fila["mostrar_contador"] = bool(body.get("mostrar_contador", True))
            try:
                guarda("Actividades", fila)
                return self._json({"ok": True, "id": fila["id"]})
            except Exception as e:
                return self._json({"error": f"no se pudo crear: {e}"}, 502)

        self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    nc.carga_env()
    try:
        resolver_tablas()
        print(f"captador: tablas resueltas {list(_TABLAS)}")
    except Exception as e:
        print(f"captador: aviso, no pude resolver tablas al arrancar ({e})")
    print(f"captador escuchando en :{PORT} (origin {ORIGIN})")
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
