"""
backend.calcom.alta_clases — crea en Cal.diy las clases reales de Julia.

Toma lo que ya está en NocoDB (actividades en curso y sus franjas
semanales en la tabla Clases) y crea, por cada actividad, un horario de
disponibilidad y un tipo de evento con aforo en Cal.diy. Después escribe
el cal_event_type_id de vuelta en la actividad, que es lo que hace que la
web pinte su botón "Reservar mi plaza".

Por defecto SIMULA: enseña lo que haría y no toca nada. Para aplicar hay
que pasar --crear explícitamente.

    cd /opt/docker/apps/juliamoreno/scripts
    python3 -m backend.calcom.alta_clases                      # simular todo
    python3 -m backend.calcom.alta_clases --solo hatha-suave   # simular una
    python3 -m backend.calcom.alta_clases --solo hatha-suave --crear
    python3 -m backend.calcom.alta_clases --crear              # el resto

Necesita CALCOM_API_URL y CALCOM_API_KEY en el entorno.

Es idempotente: salta las actividades que ya tengan cal_event_type_id.
Las actividades sin franjas en Clases (p. ej. las de ciclo lunar, sin
horario fijo) se listan aparte y no se tocan: no encajan en el modelo de
clase semanal y hay que decidirlas a mano.
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import nocolib as nc

from . import cliente

ORDEN_DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]


def _slug(texto):
    s = texto.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"),
                 ("ú", "u"), ("ñ", "n"), ("ü", "u")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60]


def _fin(inicio, minutos):
    h, m = (int(x) for x in inicio.split(":")[:2])
    total = h * 60 + m + int(minutos)
    return f"{total // 60 % 24:02d}:{total % 60:02d}"


def _agrupa(filas_clases):
    """{actividad_id: {'dias': [...], 'inicio': 'HH:MM', 'min': N,
    'lugar': str}}. Si una actividad tuviera franjas con horas distintas,
    se avisa y se usa la primera: el modelo de Cal.diy es un horario por
    tipo de evento."""
    por_act = {}
    for f in filas_clases:
        if not f.get("activa"):
            continue
        aid = f.get("actividad_id")
        hora = (f.get("hora_inicio") or "")[:5]
        if not aid or not hora:
            continue
        d = por_act.setdefault(aid, {
            "dias": [], "inicio": hora,
            "min": int(f.get("duracion_min") or 60),
            "lugar": f.get("lugar"), "mezcla": False,
        })
        if hora != d["inicio"]:
            d["mezcla"] = True
        dia = (f.get("dia_semana") or "").lower()[:3]
        if dia and dia not in d["dias"]:
            d["dias"].append(dia)
    for d in por_act.values():
        d["dias"].sort(key=lambda x: ORDEN_DIAS.index(x)
                       if x in ORDEN_DIAS else 9)
    return por_act


def main():
    crear = "--crear" in sys.argv
    solo = None
    if "--solo" in sys.argv:
        i = sys.argv.index("--solo")
        if i + 1 < len(sys.argv):
            solo = sys.argv[i + 1]

    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    ids = nc.tablas(url, tok, bid)
    actividades = nc.records(url, tok, ids["Actividades"])
    servicios = {s.get("uuid"): s for s in nc.records(url, tok, ids["Servicios"])}
    horarios = _agrupa(nc.records(url, tok, ids["Clases"]))

    print("MODO: " + ("CREAR (se escribirá en Cal.diy y NocoDB)"
                      if crear else "SIMULACIÓN (no se toca nada)"))
    print()

    sin_franjas, hechas = [], 0
    for act in actividades:
        aid = act.get("uuid")  # uuid de la temporada; Clases.actividad_id casa con él
        if solo and aid != solo:
            continue
        if act.get("estado") not in ("en_curso", "programada"):
            continue
        if act.get("cal_event_type_id"):
            print(f"= {aid}: ya enlazada (id {act['cal_event_type_id']})")
            continue
        h = horarios.get(aid)
        if not h:
            sin_franjas.append(aid)
            continue

        # El título de cara al alumno es el del SERVICIO al que pertenece.
        serv = servicios.get(act.get("servicio_uuid"), {})
        titulo = serv.get("titulo_es") or aid
        plazas = int(act.get("plazas") or 10)
        fin = _fin(h["inicio"], h["min"])
        aviso = "  (OJO: franjas con horas distintas, uso la primera)" \
            if h["mezcla"] else ""
        print(f"+ {aid}")
        print(f"    «{titulo}»  {'/'.join(h['dias'])} {h['inicio']}-{fin} "
              f"({h['min']} min)  {plazas} plazas  {h['lugar']}{aviso}")

        if not crear:
            continue
        try:
            hor = cliente.crear_horario(
                f"{titulo} — {'/'.join(h['dias'])} {h['inicio']}",
                h["dias"], h["inicio"], fin).get("data", {})
            sid = hor.get("id")
            if not sid:
                print(f"    ERROR: no se pudo crear el horario: {hor}")
                continue
            ev = cliente.crear_tipo_evento(
                titulo, _slug(titulo), h["min"], plazas, sid,
                lugar=h.get("lugar")).get("data", {})
            eid = ev.get("id")
            if not eid:
                print(f"    ERROR: no se pudo crear la clase: {ev}")
                continue
            nc.api(url, tok,
                   "PATCH", f"/api/v2/tables/{ids['Actividades']}/records",
                   {"Id": act.get("Id"), "cal_event_type_id": eid})
            print(f"    creada en Cal.diy (horario {sid}, clase {eid}) "
                  f"y enlazada en NocoDB")
            hechas += 1
        except Exception as e:
            print(f"    ERROR: {e}")

    if sin_franjas:
        print()
        print("Sin franjas semanales en la tabla Clases (no se tocan; "
              "no encajan en el modelo de clase con horario fijo):")
        for a in sin_franjas:
            print(f"  - {a}")

    if crear:
        print(f"\n{hechas} clase(s) creadas. Regenere la web con "
              f"'python3 scripts/build-web.py' para ver los botones.")
    else:
        print("\nSimulación. Repita con --crear para aplicarlo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
