"""
backend.datos — capa de acceso a NocoDB.

Resuelve los ids de las tablas de la base "Yoga" y ofrece las operaciones
CRUD básicas (lee/guarda/actualiza/borra, y sus variantes en lote). Todo el
resto del backend habla con NocoDB a través de aquí; nadie más llama a
nocolib directamente para escribir.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import nocolib as nc

_TABLAS = {}


def resolver_tablas():
    """Carga el mapa nombre->id de todas las tablas de la base. Se llama al
    arrancar y, perezosamente, la primera vez que se pide una tabla."""
    global _TABLAS
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if not bid:
        raise RuntimeError(f"base '{base}' no encontrada en NocoDB")
    _TABLAS = nc.tablas(url, tok, bid)
    return url, tok


def tablas_resueltas():
    """Nombres de tablas ya resueltos (para el log de arranque)."""
    return list(_TABLAS)


def _tid(tabla):
    if tabla not in _TABLAS:
        resolver_tablas()
    return _TABLAS[tabla]


def lee(tabla):
    url, tok, _ = nc.cfg()
    return nc.records(url, tok, _tid(tabla))


def guarda(tabla, fila):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "POST", f"/api/v2/tables/{_tid(tabla)}/records", [fila])


def guarda_varios(tabla, filas):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "POST", f"/api/v2/tables/{_tid(tabla)}/records", filas)


def actualiza(tabla, fila):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "PATCH", f"/api/v2/tables/{_tid(tabla)}/records", [fila])


def actualiza_varios(tabla, filas):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "PATCH", f"/api/v2/tables/{_tid(tabla)}/records", filas)


def borra(tabla, rid):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "DELETE", f"/api/v2/tables/{_tid(tabla)}/records", [{"Id": rid}])


def borra_varios(tabla, ids):
    url, tok, _ = nc.cfg()
    nc.api(url, tok, "DELETE", f"/api/v2/tables/{_tid(tabla)}/records",
           [{"Id": i} for i in ids])


def servicios_por_uuid():
    """Índice {uuid: fila} de Servicios. Los datos de identidad (título,
    texto, foto, nivel) viven en el Servicio; una Actividad/temporada solo
    guarda su servicio_uuid. Este índice evita releer Servicios en cada
    handler que necesita la identidad detrás de una temporada."""
    try:
        return {(s.get("uuid") or ""): s for s in lee("Servicios")}
    except Exception:
        return {}
