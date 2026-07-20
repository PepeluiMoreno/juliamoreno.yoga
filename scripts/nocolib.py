"""
nocolib.py — utilidades comunes para hablar con NocoDB.

Robustez:
- Carga el .env del proyecto por sí mismo (no depende de `source`).
- Descubre la base y las tablas POR NOMBRE vía la API meta: no se
  necesitan IDs de tabla en el entorno.
Config necesaria (en .env o en el entorno):
  NOCODB_URL, NOCODB_TOKEN, NOCODB_BASE (por defecto "Yoga")
"""
import json, os, pathlib, urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"


def carga_env():
    """Vuelca al entorno las variables del .env (sin pisar las ya definidas)."""
    if ENV.exists():
        for linea in ENV.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, _, v = linea.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def cfg():
    """Devuelve (url, token, nombre_base) o lanza RuntimeError si falta algo."""
    carga_env()
    url = os.environ.get("NOCODB_URL", "").rstrip("/")
    tok = os.environ.get("NOCODB_TOKEN", "")
    base = os.environ.get("NOCODB_BASE", "Yoga")
    if not url or not tok:
        raise RuntimeError("Faltan NOCODB_URL/NOCODB_TOKEN (defínalos en el .env)")
    return url, tok, base


def api(url, tok, method, path, body=None):
    req = urllib.request.Request(
        url + path, method=method,
        headers={"xc-token": tok, "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        t = r.read().decode()
        return json.loads(t) if t else {}


def base_id(url, tok, nombre):
    """ID de la base por nombre, o None si no existe."""
    for b in api(url, tok, "GET", "/api/v2/meta/bases").get("list", []):
        if b.get("title") == nombre:
            return b["id"]
    return None


def tablas(url, tok, bid):
    """Dict {titulo: id} de las tablas de la base."""
    ts = api(url, tok, "GET", f"/api/v2/meta/bases/{bid}/tables").get("list", [])
    return {t["title"]: t["id"] for t in ts}


def columnas(url, tok, tid):
    """Set de títulos de columna de una tabla."""
    meta = api(url, tok, "GET", f"/api/v2/meta/tables/{tid}")
    return {c.get("title") for c in meta.get("columns", [])}


def records(url, tok, tid, limit=200, incluir_eliminados=False):
    """Filas de una tabla. Por defecto OCULTA las borradas lógicamente
    (eliminado=true): la papelera es lo único que quiere verlas, y pasa
    incluir_eliminados=True.

    El filtro se aplica aquí, en la primitiva, y no en cada llamante: por
    aquí pasan tanto el backend (via datos.lee) como build-web.py y los
    scripts de calcom, de modo que una fila en la papelera no puede colarse
    en la web publica ni en el alta de clases por haber olvidado un filtro.
    """
    filas = api(url, tok, "GET",
                f"/api/v2/tables/{tid}/records?limit={limit}").get("list", [])
    if incluir_eliminados:
        return filas
    return [f for f in filas if not f.get("eliminado")]
