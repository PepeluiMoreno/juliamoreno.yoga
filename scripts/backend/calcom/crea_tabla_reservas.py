"""
backend.calcom.crea_tabla_reservas — crea la tabla Reservas en NocoDB.

Idempotente: si la tabla ya existe, no hace nada y lo dice. Usa la misma
capa (nocolib) y el mismo .env que el resto del backend, así que se
ejecuta en el VPS sin pasar credenciales por línea de comandos:

    cd /opt/docker/apps/juliamoreno/scripts
    python3 -m backend.calcom.crea_tabla_reservas

La tabla guarda la copia ligera de cada reserva (la reserva de verdad
vive en el motor de Cal.diy); alimenta la lista de alumnos por clase y
los avisos. Campos, con los nombres exactos que escribe
handlers/reservas.py: cal_uid, event_type_id, inicio, nombre, email,
estado, fecha.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import nocolib as nc

TABLA = "Reservas"

# NocoDB v2 meta: uidt = tipo de columna. SingleLineText para textos,
# Number para el id numérico. Una tabla necesita al menos una columna;
# creamos todas de golpe.
COLUMNAS = [
    {"title": "cal_uid", "uidt": "SingleLineText"},
    {"title": "event_type_id", "uidt": "Number"},
    {"title": "inicio", "uidt": "SingleLineText"},
    {"title": "nombre", "uidt": "SingleLineText"},
    {"title": "email", "uidt": "SingleLineText"},
    {"title": "estado", "uidt": "SingleLineText"},
    {"title": "fecha", "uidt": "SingleLineText"},
]


def main():
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if not bid:
        print(f"ERROR: base '{base}' no encontrada en NocoDB")
        return 1

    existentes = nc.tablas(url, tok, bid)
    if TABLA in existentes:
        print(f"La tabla '{TABLA}' ya existe (id {existentes[TABLA]}). "
              f"Nada que hacer.")
        return 0

    r = nc.api(url, tok, "POST", f"/api/v2/meta/bases/{bid}/tables", {
        "title": TABLA,
        "columns": COLUMNAS,
    })
    tid = r.get("id")
    if not tid:
        print(f"ERROR: NocoDB no devolvió id de tabla. Respuesta: {r}")
        return 1
    print(f"Tabla '{TABLA}' creada (id {tid}) con columnas: "
          f"{', '.join(c['title'] for c in COLUMNAS)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
