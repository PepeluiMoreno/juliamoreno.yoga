"""
backend.calcom.enlaza_actividades — añade cal_event_type_id a Actividades.

Idempotente: si la columna ya existe, no hace nada.

Para qué: una actividad de NocoDB (la oferta que se ve en la web) y una
clase de Cal.diy (el tipo de evento con aforo y disponibilidad) son la
misma cosa vista desde cada lado, pero hasta ahora nada las relacionaba.
Este campo guarda, en cada actividad, el id del tipo de evento de Cal.diy
que la hace reservable.

Con el campo relleno, build-web.py pinta en esa actividad un botón
"Reservar plaza" que lleva a /reservar.html?clase=<id>, de modo que el
alumno ve exactamente esa clase y no el listado entero. Las actividades
sin el campo siguen igual que hasta ahora (formulario de interés si están
en propuesta, nada si ya están programadas).

Uso:
    cd /opt/docker/apps/juliamoreno/scripts
    python3 -m backend.calcom.enlaza_actividades          # añade la columna
    python3 -m backend.calcom.enlaza_actividades --listar # ver actividades
                                                          # y clases de Cal.diy
El --listar ayuda a saber qué id poner en cada actividad.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import nocolib as nc

TABLA = "Actividades"
COLUMNA = "cal_event_type_id"


def _añade_columna():
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if not bid:
        print(f"ERROR: base '{base}' no encontrada en NocoDB")
        return 1
    ids = nc.tablas(url, tok, bid)
    if TABLA not in ids:
        print(f"ERROR: no existe la tabla '{TABLA}'")
        return 1
    tid = ids[TABLA]
    if COLUMNA in nc.columnas(url, tok, tid):
        print(f"La columna '{COLUMNA}' ya existe en '{TABLA}'. Nada que hacer.")
        return 0
    nc.api(url, tok, "POST", f"/api/v2/meta/tables/{tid}/columns", {
        "title": COLUMNA,
        "uidt": "Number",
    })
    print(f"Columna '{COLUMNA}' añadida a '{TABLA}'.")
    print("Rellénela en NocoDB con el id de la clase de Cal.diy "
          "correspondiente (vea --listar).")
    return 0


def _listar():
    """Muestra las actividades y las clases de Cal.diy, para emparejarlas."""
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    ids = nc.tablas(url, tok, bid)
    print("== Actividades en NocoDB ==")
    for fila in nc.records(url, tok, ids[TABLA]):
        print(f"  id={fila.get('id'):<20} "
              f"estado={str(fila.get('estado')):<12} "
              f"{COLUMNA}={fila.get(COLUMNA) or '-':<6} "
              f"{fila.get('titulo_es') or ''}")
    print("\n== Clases (tipos de evento) en Cal.diy ==")
    try:
        from . import cliente
        for t in cliente.event_types().get("data", []):
            print(f"  id={t.get('id'):<4} {t.get('title')}")
    except Exception as e:
        print(f"  (no se pudo consultar Cal.diy: {e})")
        print("  Defina CALCOM_API_URL y CALCOM_API_KEY en el entorno.")
    return 0


def main():
    if "--listar" in sys.argv:
        return _listar()
    return _añade_columna()


if __name__ == "__main__":
    sys.exit(main())
