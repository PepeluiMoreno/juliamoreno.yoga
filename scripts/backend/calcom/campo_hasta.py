"""
backend.calcom.campo_hasta — añade 'hasta' (vigencia) a Actividades.

Idempotente: si la columna ya existe, no hace nada.

Para qué: distinguir las actividades vigentes de las que ya concluyeron.
Pasada esa fecha, la actividad sale sola del grid principal de la web y
pasa a la vista de anteriores (/pasadas.html), donde quien llegó tarde
puede pedir que se repita. Así nadie tiene que acordarse de archivar nada
a mano — aunque también vale marcar el estado como 'finalizada'.

Dejarla vacía significa "sin fecha de fin": la actividad sigue vigente
indefinidamente, que es lo normal en las clases regulares.

Uso:
    cd /opt/docker/apps/juliamoreno/scripts
    python3 -m backend.calcom.campo_hasta
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import nocolib as nc

TABLA = "Actividades"
COLUMNA = "hasta"


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
        "uidt": "Date",
        "meta": {"date_format": "YYYY-MM-DD"},
    })
    print(f"Columna '{COLUMNA}' añadida a '{TABLA}'.")
    print("Vacía = sin fecha de fin (actividad vigente). Con fecha pasada, "
          "la actividad se archiva sola y pasa a /pasadas.html.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
