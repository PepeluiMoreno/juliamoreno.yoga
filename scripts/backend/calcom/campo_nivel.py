"""
backend.calcom.campo_nivel — añade 'nivel' (dificultad) a Actividades.

Idempotente: si la columna ya existe, no hace nada.

Criterio fijado: el nivel es OPCIONAL y no tiene valor por defecto. Si se
deja en blanco al proponer la actividad, no se muestra en ninguna parte
durante toda la vida de la actividad — ni en la tarjeta de la web, ni en
la ficha de la página de reserva. Nada de rellenar con "todos los
niveles" por si acaso: si Julia no lo ha dicho, no se dice.

Se crea como selector con las opciones habituales, para que en NocoDB no
haya erratas ni variantes ("iniciacion", "Inicial", "principiantes"...).

Uso:
    cd /opt/docker/apps/juliamoreno/scripts
    python3 -m backend.calcom.campo_nivel
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import nocolib as nc

TABLA = "Actividades"
COLUMNA = "nivel"
OPCIONES = ["Iniciación", "Todos los niveles", "Intermedio", "Avanzado"]


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
        "uidt": "SingleSelect",
        "dtxp": ",".join(f"'{o}'" for o in OPCIONES),
        "colOptions": {"options": [{"title": o} for o in OPCIONES]},
    })
    print(f"Columna '{COLUMNA}' añadida a '{TABLA}' "
          f"({', '.join(OPCIONES)}).")
    print("Dejarla vacía significa que esa actividad no mostrará nivel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
