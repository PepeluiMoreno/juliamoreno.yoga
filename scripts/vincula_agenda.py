"""
vincula_agenda — rellena el actividad_id que falta en la tabla Agenda.

Las entradas creadas a mano en el panel se guardaban sin vínculo con su
actividad, porque el formulario no ofrecía ese campo. Sin él, una clase
de la agenda no sabe a qué reservas corresponde: no hay lista de alumnos
ni aforo.

Empareja por TÍTULO contra la tabla Actividades, en tres pasadas de menos
a más permisiva, y solo aplica las seguras:

  1. exacto        "Hatha suave"  ->  "Hatha suave"
  2. sin acentos, mayúsculas ni espacios de más
  3. por prefijo   "Hatha suave para todas las edades" -> "Hatha suave"

Las de la tercera pasada NO se aplican solas: se listan aparte para que
las revise una persona, porque un prefijo puede acertar por casualidad.

    cd /opt/docker/apps/juliamoreno/scripts
    python3 vincula_agenda.py              # simular
    python3 vincula_agenda.py --aplicar    # escribir
    python3 vincula_agenda.py --aplicar --dudosas   # incluir las de prefijo
"""
import sys
import unicodedata

import nocolib as nc


def normaliza(t):
    t = (t or "").strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(t.split())


def main():
    aplicar = "--aplicar" in sys.argv
    con_dudosas = "--dudosas" in sys.argv

    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    ids = nc.tablas(url, tok, bid)

    actividades = nc.records(url, tok, ids["Actividades"], limit=500)
    por_titulo = {}
    for a in actividades:
        aid = (a.get("id") or "").strip()
        if not aid:
            continue
        for campo in ("titulo_es", "id"):
            clave = normaliza(a.get(campo))
            if clave:
                por_titulo.setdefault(clave, aid)

    agenda = nc.records(url, tok, ids["Agenda"], limit=1000)
    exactas, dudosas, huerfanas = [], [], []

    for fila in agenda:
        if (fila.get("actividad_id") or "").strip():
            continue
        titulo = fila.get("titulo") or ""
        clave = normaliza(titulo)
        if clave in por_titulo:
            exactas.append((fila, por_titulo[clave], titulo))
            continue
        # prefijo: el título de la agenda empieza por el de una actividad
        cand = [aid for t, aid in por_titulo.items()
                if clave.startswith(t) and len(t) >= 6]
        if len(set(cand)) == 1:
            dudosas.append((fila, cand[0], titulo))
        else:
            huerfanas.append((fila, titulo))

    print("MODO: " + ("APLICAR (se escribe en NocoDB)" if aplicar
                      else "SIMULACIÓN (no se toca nada)"))
    print(f"\n{len(exactas)} por título exacto:")
    for _, aid, tit in exactas[:8]:
        print(f"    {tit}  ->  {aid}")
    if len(exactas) > 8:
        print(f"    ... y {len(exactas)-8} más")

    if dudosas:
        print(f"\n{len(dudosas)} por prefijo (revíselas):")
        for _, aid, tit in dudosas:
            print(f"    {tit}  ->  {aid}")
        if not con_dudosas:
            print("    (no se aplican; use --dudosas si está de acuerdo)")

    if huerfanas:
        print(f"\n{len(huerfanas)} sin actividad que encaje:")
        for _, tit in huerfanas:
            print(f"    {tit}")

    if not aplicar:
        print("\nSimulación. Repita con --aplicar para escribir.")
        return 0

    a_escribir = exactas + (dudosas if con_dudosas else [])
    n = 0
    for fila, aid, _ in a_escribir:
        try:
            nc.api(url, tok, "PATCH", f"/api/v2/tables/{ids['Agenda']}/records",
                   {"Id": fila["Id"], "actividad_id": aid})
            n += 1
        except Exception as e:
            print(f"  fallo en Id={fila.get('Id')}: {e}")
    print(f"\n{n} entrada(s) vinculadas.")
    if huerfanas or (dudosas and not con_dudosas):
        print("Las que quedan se arreglan a mano en Agenda → Editar → Actividad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
