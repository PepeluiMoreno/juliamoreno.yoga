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
import json, os, sys, pathlib, datetime, re, io, uuid, cgi
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nocolib as nc

PORT = int(os.environ.get("CAPTADOR_PORT", "8090"))
ORIGIN = os.environ.get("CAPTADOR_ORIGIN", "https://juliamoreno.yoga")
MAX_FOTO = 12 * 1024 * 1024   # 12 MB de entrada
ANCHO_MAX = 1200              # redimensionar a este ancho máximo

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


def _preparar_mes_desde_plantillas(mes_ym):
    """Estampa todas las plantillas sobre el mes indicado (YYYY-MM),
    generando las ocurrencias concretas de cada una. Devuelve cuántas."""
    y, m = map(int, mes_ym.split("-"))
    filas = lee("Agenda")
    plantillas = [f for f in filas if f.get("es_plantilla")]
    if not plantillas:
        return 0
    total = 0
    for p in plantillas:
        base = {
            "titulo": p.get("titulo", ""),
            "actividad_id": p.get("actividad_id", ""),
            "dias_semana": p.get("dias_semana", ""),
            "hora_inicio": p.get("hora_inicio", ""),
            "duracion_min": p.get("duracion_min"),
            "lugar": p.get("lugar", ""),
            "color": p.get("color", ""),
            "visible_web": p.get("visible_web", False),
        }
        ocs = _materializa_mes(base, anio=y, mes=m)
        if ocs:
            guarda_varios("Agenda", ocs)
            total += len(ocs)
    return total


def _copia_mes(desde_ym, hasta_ym):
    """Copia las ocurrencias del mes origen (YYYY-MM) al mes destino,
    preservando el patrón semanal: cada clase cae en el mismo día de la
    semana y la misma posición dentro del mes (1er lunes -> 1er lunes).
    No duplica: si el destino ya tiene ocurrencias, se añaden igualmente
    (Julia controla; se puede vaciar antes si quiere). Devuelve cuántas."""
    import calendar as _cal
    import uuid as _uuid
    ya, ma = map(int, desde_ym.split("-"))
    yd, md = map(int, hasta_ym.split("-"))
    filas = lee("Agenda")
    # ocurrencias del mes origen
    origen = []
    for f in filas:
        fecha = (f.get("fecha") or "")[:10]
        if not fecha:
            continue
        try:
            d = datetime.date.fromisoformat(fecha)
        except Exception:
            continue
        if d.year == ya and d.month == ma:
            origen.append((d, f))
    if not origen:
        return 0
    ndias_dest = _cal.monthrange(yd, md)[1]
    nuevas = []
    serie = _uuid.uuid4().hex[:12]
    for d, f in origen:
        # posición: cuántos días de ese weekday han pasado en el mes (1er, 2º...)
        semana_pos = (d.day - 1) // 7  # 0=primera aparición del mes
        wd = d.weekday()
        # encontrar la fecha en el mes destino con mismo weekday y misma posición
        cuenta = -1
        destino = None
        for dia in range(1, ndias_dest + 1):
            fd = datetime.date(yd, md, dia)
            if fd.weekday() == wd:
                cuenta += 1
                if cuenta == semana_pos:
                    destino = fd
                    break
        if destino is None:
            continue  # ese mes no tiene esa posición (p.ej. 5º lunes)
        nuevas.append({
            "titulo": f.get("titulo", ""),
            "actividad_id": f.get("actividad_id", ""),
            "tipo": "puntual",
            "fecha": destino.isoformat(),
            "hora_inicio": f.get("hora_inicio", ""),
            "duracion_min": f.get("duracion_min"),
            "lugar": f.get("lugar", ""),
            "color": f.get("color", ""),
            "visible_web": f.get("visible_web", False),
            "serie_id": serie,
        })
    if nuevas:
        guarda_varios("Agenda", nuevas)
    return len(nuevas)


def guarda_varios(tabla, filas):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "POST", f"/api/v2/tables/{_tid(tabla)}/records", filas)


def _materializa_mes(base, anio=None, mes=None):
    """Convierte una definición recurrente (dias_semana + horas) en ocurrencias
    puntuales concretas, una por cada día correspondiente. Si se pasa anio/mes,
    genera para ese mes completo; si no, desde hoy (o vigencia_desde) hasta fin
    del mes en curso. Todas comparten serie_id."""
    import calendar as _cal
    import uuid as _uuid
    dianum = {"lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6}
    dias = {dianum.get(x.strip()) for x in (base.get("dias_semana") or "").split(",")}
    dias.discard(None)
    if not dias:
        return []
    hoy = datetime.date.today()
    if anio and mes:
        desde = datetime.date(anio, mes, 1)
    else:
        desde_s = (base.get("vigencia_desde") or "")[:10]
        try:
            desde = datetime.date.fromisoformat(desde_s) if desde_s else hoy
        except Exception:
            desde = hoy
        if desde < hoy:
            desde = hoy
    ndias = _cal.monthrange(desde.year, desde.month)[1]
    fin = datetime.date(desde.year, desde.month, ndias)
    serie = _uuid.uuid4().hex[:12]
    ocurrencias = []
    d = desde
    while d <= fin:
        if d.weekday() in dias:
            ocurrencias.append({
                "titulo": base.get("titulo", ""),
                "actividad_id": base.get("actividad_id", ""),
                "tipo": "puntual",
                "fecha": d.isoformat(),
                "hora_inicio": base.get("hora_inicio", ""),
                "duracion_min": base.get("duracion_min"),
                "lugar": base.get("lugar", ""),
                "color": base.get("color", ""),
                "visible_web": base.get("visible_web", False),
                "serie_id": serie,
            })
        d += datetime.timedelta(days=1)
    return ocurrencias


def guarda(tabla, fila):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "POST", f"/api/v2/tables/{_tid(tabla)}/records", [fila])


def actualiza(tabla, fila):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "PATCH", f"/api/v2/tables/{_tid(tabla)}/records", [fila])


def lee(tabla):
    url, tok, _ = nc.cfg()
    return nc.records(url, tok, _tid(tabla))


def borra(tabla, rid):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "DELETE", f"/api/v2/tables/{_tid(tabla)}/records", [{"Id": rid}])


def _dur_horas(hi, hf):
    """Horas decimales entre dos 'HH:MM'. 0 si no parsea."""
    try:
        h1, m1 = map(int, (hi or "").split(":"))
        h2, m2 = map(int, (hf or "").split(":"))
        d = (h2 * 60 + m2) - (h1 * 60 + m1)
        return d / 60.0 if d > 0 else 0.0
    except Exception:
        return 0.0


def _horas_programadas_mes():
    """Suma las horas de clase del mes en curso a partir de la Agenda:
    expande recurrentes en sus ocurrencias del mes y suma las puntuales."""
    import calendar as _cal
    try:
        filas = lee("Agenda")
    except Exception:
        return 0.0
    hoy = datetime.date.today()
    ndias = _cal.monthrange(hoy.year, hoy.month)[1]
    dianum = {"lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6}
    total = 0.0
    for f in filas:
        try:
            dur = int(f.get("duracion_min") or 0) / 60.0
        except Exception:
            dur = 0.0
        if dur <= 0:
            continue
        tipo = (f.get("tipo") or "").strip()
        if tipo == "puntual":
            fecha = (f.get("fecha") or "")[:10]
            try:
                d = datetime.date.fromisoformat(fecha)
                if d.year == hoy.year and d.month == hoy.month:
                    total += dur
            except Exception:
                pass
        elif tipo == "recurrente":
            dias = {dianum.get(x.strip()) for x in (f.get("dias_semana") or "").split(",")}
            dias.discard(None)
            desde = (f.get("vigencia_desde") or "")[:10]
            hasta = (f.get("vigencia_hasta") or "")[:10]
            d0 = datetime.date.fromisoformat(desde) if desde else None
            d1 = datetime.date.fromisoformat(hasta) if hasta else None
            for dia in range(1, ndias + 1):
                fecha = datetime.date(hoy.year, hoy.month, dia)
                if fecha.weekday() in dias:
                    if d0 and fecha < d0:
                        continue
                    if d1 and fecha > d1:
                        continue
                    total += dur
    return round(total, 1)


def _fila_agenda(body, con_id):
    """Construye la fila de Agenda desde el cuerpo de la petición, saneando."""
    fila = {}
    if con_id:
        fila["Id"] = body["Id"]
    for c in ("titulo", "actividad_id", "tipo", "dias_semana", "lugar", "color",
              "hora_inicio", "serie_id"):
        if c in body:
            fila[c] = limpio(body[c], 200)
    if "duracion_min" in body and body["duracion_min"] not in (None, ""):
        try: fila["duracion_min"] = int(body["duracion_min"])
        except: pass
    for c in ("fecha", "vigencia_desde", "vigencia_hasta"):
        if c in body:
            v = limpio(body[c], 20)
            fila[c] = v if v else None
    if "visible_web" in body:
        fila["visible_web"] = bool(body["visible_web"])
    if "es_plantilla" in body:
        fila["es_plantilla"] = bool(body["es_plantilla"])
    return fila


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


def guarda_foto(datos, nombre_orig):
    """Redimensiona con Pillow a ANCHO_MAX y guarda como JPEG optimizado.
    Devuelve la URL pública. Lanza ValueError si no es una imagen válida."""
    from PIL import Image
    uploads_dir = os.environ.get("UPLOADS_DIR", "/app/sitio/uploads")
    uploads_url = os.environ.get("UPLOADS_URL", "https://juliamoreno.yoga/uploads")
    try:
        img = Image.open(io.BytesIO(datos))
        img.verify()  # valida que es imagen real
        img = Image.open(io.BytesIO(datos))  # reabrir tras verify
    except Exception:
        raise ValueError("el fichero no es una imagen válida")
    # Corregir orientación EXIF (fotos de móvil)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert("RGB")
    if img.width > ANCHO_MAX:
        alto = int(img.height * ANCHO_MAX / img.width)
        img = img.resize((ANCHO_MAX, alto), Image.LANCZOS)
    pathlib.Path(uploads_dir).mkdir(parents=True, exist_ok=True)
    base = slug(pathlib.Path(nombre_orig or "foto").stem)
    fichero = f"{base}-{uuid.uuid4().hex[:8]}.jpg"
    destino = os.path.join(uploads_dir, fichero)
    img.save(destino, "JPEG", quality=82, optimize=True)
    return f"{uploads_url}/{fichero}"


def dispara_rebuild():
    """Lanza build-web.py en segundo plano para regenerar la web tras un
    cambio en actividades. No bloquea la respuesta al panel; si falla, se
    registra pero no rompe la operación (la web se puede regenerar a mano)."""
    import subprocess
    try:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build-web.py")
        subprocess.Popen(
            [sys.executable, script],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("rebuild de la web disparado")
    except Exception as e:
        print(f"aviso: no se pudo disparar el rebuild: {e}")


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
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/salud":
            return self._json({"ok": True})
        if self.path == "/admin/api/resumen":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            try:
                acts = lee("Actividades")
                inter = lee("Interesados")
                # Contar interesados reales por actividad (id de actividad)
                por_act = {}
                for r in inter:
                    a = (r.get("actividad") or "").strip()
                    if a:
                        por_act[a] = por_act.get(a, 0) + 1
                estados = {}
                ofertadas = []
                propuestas = []
                for a in acts:
                    est = (a.get("estado") or "propuesta").strip()
                    estados[est] = estados.get(est, 0) + 1
                    aid = (a.get("id") or "").strip()
                    tarjeta = {
                        "id": aid,
                        "titulo": a.get("titulo_es") or "(sin título)",
                        "interesados": por_act.get(aid, 0),
                        "umbral": int(a.get("umbral") or 0),
                        "lugar": a.get("lugar") or "",
                        "duracion": a.get("duracion") or "",
                    }
                    if est == "en_curso":
                        ofertadas.append(tarjeta)
                    elif est == "propuesta":
                        propuestas.append(tarjeta)
                propuestas.sort(key=lambda x: x["interesados"], reverse=True)
                # Horas programadas del mes en curso (a partir de la agenda)
                horas_mes = _horas_programadas_mes()
                return self._json({
                    "ok": True,
                    "totales": {
                        "ofertadas": estados.get("en_curso", 0),
                        "programadas": estados.get("programada", 0),
                        "en_preparacion": estados.get("propuesta", 0),
                        "finalizadas": estados.get("finalizada", 0),
                        "total_actividades": len(acts),
                        "total_interesados": len(inter),
                        "horas_mes": horas_mes,
                    },
                    "ofertadas": ofertadas,
                    "preparacion": propuestas,
                })
            except Exception as e:
                return self._json({"error": f"no se pudo calcular: {e}"}, 502)
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
                        "franjas_elegibles": r.get("franjas_elegibles"),
                        "foto": r.get("foto"),
                        "precio": r.get("precio"), "duracion": r.get("duracion"), "lugar": r.get("lugar"),
                        "interesados": r.get("interesados"),
                    })
                return self._json({"ok": True, "actividades": out})
            except Exception as e:
                return self._json({"error": f"no se pudo leer: {e}"}, 502)

        if self.path == "/admin/api/agenda":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            try:
                filas = lee("Agenda")
                out = []
                for r in filas:
                    out.append({
                        "Id": r.get("Id"), "titulo": r.get("titulo"),
                        "actividad_id": r.get("actividad_id"), "tipo": r.get("tipo"),
                        "dias_semana": r.get("dias_semana"), "fecha": r.get("fecha"),
                        "vigencia_desde": r.get("vigencia_desde"), "vigencia_hasta": r.get("vigencia_hasta"),
                        "hora_inicio": r.get("hora_inicio"), "duracion_min": r.get("duracion_min"),
                        "serie_id": r.get("serie_id"), "es_plantilla": r.get("es_plantilla"),
                        "lugar": r.get("lugar"), "color": r.get("color"),
                        "visible_web": r.get("visible_web"),
                    })
                return self._json({"ok": True, "agenda": out})
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
            for c in ("titulo_es", "texto_es", "estado", "franjas", "foto", "precio", "duracion", "lugar"):
                if c in body:
                    fila[c] = limpio(body[c], 2000)
            for c in ("umbral", "plazas"):
                if c in body and body[c] not in (None, ""):
                    try: fila[c] = int(body[c])
                    except: pass
            for c in ("visible", "mostrar_contador", "franjas_elegibles"):
                if c in body:
                    fila[c] = bool(body[c])
            # Al cambiar el texto ES, vaciar es_hash para forzar re-traducción
            if "titulo_es" in fila or "texto_es" in fila:
                fila["es_hash"] = ""
            try:
                actualiza("Actividades", fila)
                dispara_rebuild()
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"error": f"no se pudo guardar: {e}"}, 502)

        if self.path == "/admin/api/agenda":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            body = self._body()
            if body is None:
                return self._json({"error": "bad json"}, 400)
            if not body.get("Id"):
                return self._json({"error": "falta Id"}, 422)
            fila = _fila_agenda(body, con_id=True)
            try:
                actualiza("Agenda", fila)
                dispara_rebuild()
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"error": f"no se pudo guardar: {e}"}, 502)

        self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        if self.path == "/admin/api/agenda":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            body = self._body()
            if body is None or not body.get("Id"):
                return self._json({"error": "falta Id"}, 422)
            try:
                borra("Agenda", body["Id"])
                dispara_rebuild()
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"error": f"no se pudo borrar: {e}"}, 502)
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        # Subida de foto: multipart, no JSON. Se maneja aparte.
        if self.path == "/admin/api/foto":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                return self._json({"error": "se esperaba multipart"}, 400)
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_FOTO:
                return self._json({"error": "la foto es demasiado grande (máx. 12 MB)"}, 413)
            try:
                form = cgi.FieldStorage(
                    fp=self.rfile, headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": ctype})
                item = form["foto"] if "foto" in form else None
                if item is None or not getattr(item, "file", None):
                    return self._json({"error": "no llegó ninguna foto"}, 422)
                datos = item.file.read()
                url = guarda_foto(datos, getattr(item, "filename", "foto"))
                return self._json({"ok": True, "url": url})
            except ValueError as e:
                return self._json({"error": str(e)}, 422)
            except Exception as e:
                return self._json({"error": f"no se pudo subir: {e}"}, 502)

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
                "estado": limpio(body.get("estado"), 20) or "propuesta",
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
            fila["franjas_elegibles"] = bool(body.get("franjas_elegibles", False))
            fila["foto"] = limpio(body.get("foto"), 500)
            fila["precio"] = limpio(body.get("precio"), 40)
            fila["duracion"] = limpio(body.get("duracion"), 40)
            fila["lugar"] = limpio(body.get("lugar"), 120)
            try:
                guarda("Actividades", fila)
                dispara_rebuild()
                return self._json({"ok": True, "id": fila["id"]})
            except Exception as e:
                return self._json({"error": f"no se pudo crear: {e}"}, 502)

        if self.path == "/admin/api/agenda/preparar-mes":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            mes = limpio(body.get("mes"), 7)  # YYYY-MM
            if len(mes) != 7:
                return self._json({"error": "falta el mes (YYYY-MM)"}, 422)
            try:
                n = _preparar_mes_desde_plantillas(mes)
                dispara_rebuild()
                return self._json({"ok": True, "generadas": n})
            except Exception as e:
                return self._json({"error": f"no se pudo preparar: {e}"}, 502)

        if self.path == "/admin/api/agenda/copiar-mes":
            if not self._admin_user():
                return self._json({"error": "no autenticado"}, 401)
            # body: {"desde":"2026-07", "hasta":"2026-08"}
            desde = limpio(body.get("desde"), 7)   # YYYY-MM
            hasta = limpio(body.get("hasta"), 7)
            if not (len(desde) == 7 and len(hasta) == 7):
                return self._json({"error": "faltan meses origen/destino (YYYY-MM)"}, 422)
            try:
                n = _copia_mes(desde, hasta)
                dispara_rebuild()
                return self._json({"ok": True, "copiadas": n})
            except Exception as e:
                return self._json({"error": f"no se pudo copiar: {e}"}, 502)

        if self.path == "/admin/api/agenda":
            tipo = fila.get("tipo")
            try:
                if tipo == "recurrente":
                    if not fila.get("dias_semana"):
                        return self._json({"error": "una clase recurrente necesita días de la semana"}, 422)
                    ocurrencias = _materializa_mes(fila)
                    if not ocurrencias:
                        return self._json({"error": "no hay días de ese tipo en lo que queda de mes"}, 422)
                    guarda_varios("Agenda", ocurrencias)
                    dispara_rebuild()
                    return self._json({"ok": True, "generadas": len(ocurrencias)})
                else:
                    if not fila.get("fecha"):
                        return self._json({"error": "una sesión puntual necesita fecha"}, 422)
                    guarda("Agenda", fila)
                    dispara_rebuild()
                    return self._json({"ok": True})
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
