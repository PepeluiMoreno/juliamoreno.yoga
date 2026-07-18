"""
backend.calcom.campo_telefono — añade 'telefono' a la tabla Reservas.

Idempotente: si la columna ya existe, no hace nada.

Para qué: Cal.diy no pide el teléfono al reservar, y para pasar lista o
avisar de un cambio de última hora Julia necesita un contacto directo. El
formulario de reserva lo pide como OPCIONAL y se guarda en la copia de
NocoDB; la vista "Listas de clase" del panel lo cruza con los alumnos que
vienen del motor.

Uso:
    cd /opt/docker/apps/juliamoreno/scripts
    python3 -m backend.calcom.campo_telefono
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import nocolib as nc

TABLA = "Reservas"
COLUMNA = "telefono"


def main():
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if not bid:
        print(f"ERROR: base '{base}' no encontrada")
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
        "uidt": "PhoneNumber",
    })
    print(f"Columna '{COLUMNA}' añadida a '{TABLA}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
