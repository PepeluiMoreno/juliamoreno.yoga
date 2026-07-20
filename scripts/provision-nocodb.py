#!/usr/bin/env python3
"""
provision-nocodb.py — crea y puebla el backoffice en NocoDB. IDEMPOTENTE:
- crea la base si no existe;
- crea las tablas que falten;
- añade a las tablas existentes las columnas que falten (no borra nada);
- siembra datos iniciales SOLO en tablas vacías (Precios, Horarios y una
  actividad de ejemplo).

Config: NOCODB_URL, NOCODB_TOKEN, NOCODB_BASE en el .env del proyecto
(el script carga el .env por sí mismo; no hace falta `source`).

Uso:  python3 scripts/provision-nocodb.py
"""
import datetime, json, sys, pathlib, uuid
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nocolib as nc

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((RAIZ / "data" / "contenido.json").read_text(encoding="utf-8"))


def col(title, uidt="SingleLineText"):
    return {"title": title, "column_name": title, "uidt": uidt}

# --- Modelo Servicio -> Actividad(temporada) -> Clases(sesiones) -> Agenda ---
#
# Un SERVICIO es lo que Julia ofrece, atemporal ("Hatha yoga"): su identidad
# (título, texto, foto, nivel) y si se sigue ofertando (la cartera vigente).
# Una ACTIVIDAD es una PROGRAMACIÓN de ese servicio en una extensión temporal
# concreta ("Hatha, sep-dic 2026"): cuelga de un servicio (servicio_uuid) y
# lleva lo temporal (estado, hasta, franjas, aforo, enlace a Cal.diy).
#
# Los identificadores son UUID de texto (uuid.uuid4().hex), no slugs: se
# acabaron las colisiones de título y el casado por nombre. NocoDB mantiene
# además su propio `Id` numérico, que es el que usan los PATCH/DELETE.
TABLAS = {
    "Precios": [col("id"), col("valor"), col("visible", "Checkbox")],
    "Horarios": [col("id"), col("visible", "Checkbox")],
    "Servicios": [
        col("uuid"), col("se_sigue_ofertando", "Checkbox"),
        col("foto", "URL"), col("nivel"),
        col("titulo_es", "LongText"), col("texto_es", "LongText"),
        col("titulo_en", "LongText"), col("texto_en", "LongText"),
        col("titulo_fr", "LongText"), col("texto_fr", "LongText"),
        col("titulo_de", "LongText"), col("texto_de", "LongText"),
        col("revisado"), col("es_hash"),
    ],
    "Actividades": [
        col("uuid"), col("servicio_uuid"),
        col("estado"), col("hasta"),
        col("umbral", "Number"), col("interesados", "Number"),
        col("plazas", "Number"), col("cal_event_type_id", "Number"),
        col("mostrar_contador", "Checkbox"), col("visible", "Checkbox"),
        col("franjas_elegibles", "Checkbox"), col("franjas", "LongText"),
        col("precio"), col("duracion"), col("lugar"),
    ],
    # actividad_id en Clases/Agenda guarda el UUID de la temporada (Actividad)
    # a la que pertenece. Se conserva el nombre `actividad_id` —no `_uuid`—
    # porque es el que ya usan la lógica de agenda y el panel; solo cambia su
    # valor (antes un slug, ahora el uuid de la temporada).
    "Clases": [
        col("uuid"), col("actividad_id"),
        col("dia_semana"), col("hora_inicio"), col("duracion_min", "Number"),
        col("lugar"), col("color"), col("activa", "Checkbox"),
    ],
    "Agenda": [
        col("uuid"), col("actividad_id"), col("serie_id"),
        col("titulo", "LongText"), col("tipo"),
        col("fecha"), col("hora_inicio"), col("duracion_min", "Number"),
        col("dias_semana"), col("lugar"), col("color"),
        col("visible_web", "Checkbox"), col("avisar_alumnos", "Checkbox"),
        col("estado"), col("motivo"), col("motivo_texto", "LongText"),
    ],
    "Reservas": [
        col("cal_uid"), col("event_type_id", "Number"), col("inicio"),
        col("nombre"), col("email"), col("telefono"),
        col("estado"), col("fecha", "DateTime"),
    ],
    "Interesados": [
        col("actividad"), col("nombre"), col("contacto"),
        col("franjas"), col("idioma"), col("fecha", "DateTime"),
    ],
    "Contactos": [
        col("nombre"), col("telefono"), col("asunto", "LongText"),
        col("idioma"), col("fecha", "DateTime"), col("atendido", "Checkbox"),
    ],
}


# Papelera: en el panel Julia siempre puede eliminar, pero el borrado normal
# es LÓGICO (eliminado=true) y se puede deshacer desde la papelera. Solo el
# "borrado definitivo" saca la fila de NocoDB. Se añaden a TODAS las tablas
# para que la papelera funcione igual sea cual sea el objeto.
for _cols in TABLAS.values():
    _cols.append(col("eliminado", "Checkbox"))
    _cols.append(col("eliminado_fecha", "DateTime"))


def _uuid():
    return uuid.uuid4().hex


# --- Dataset de demostración (solo con --seed-demo) --------------------------
#
# Dos servicios, cada uno con una temporada vigente, con clases semanales y
# ocho alumnos apuntados por clase. Sirve para probar el modelo entero de un
# vistazo. Las claves son UUID; los cruces entre tablas usan esos UUID. No es
# realista al detalle (los alumnos son ficticios), es un andamio de prueba.
#
# NOTA: sembrar el demo VACÍA primero las tablas del modelo de oferta
# (Servicios, Actividades, Clases, Agenda, Reservas). Es destructivo a
# propósito y solo corre bajo la bandera --seed-demo; el provisión normal
# (sin bandera) nunca borra nada.
_ALUMNOS_DEMO = [
    ("Lucía Fernández", "lucia.fernandez@example.com", "600100001"),
    ("Marta Ruiz", "marta.ruiz@example.com", "600100002"),
    ("Elena Gómez", "elena.gomez@example.com", "600100003"),
    ("Carmen Díaz", "carmen.diaz@example.com", "600100004"),
    ("Pablo Serrano", "pablo.serrano@example.com", "600100005"),
    ("Javier Moreno", "javier.moreno@example.com", "600100006"),
    ("Ana Torres", "ana.torres@example.com", "600100007"),
    ("Rosa Navarro", "rosa.navarro@example.com", "600100008"),
]


def main():
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if bid:
        print(f"base '{base}': OK")
    else:
        bid = nc.api(url, tok, "POST", "/api/v2/meta/bases", {"title": base})["id"]
        print(f"base '{base}': creada")

    existentes = nc.tablas(url, tok, bid)
    ids = {}
    for nombre, cols in TABLAS.items():
        if nombre not in existentes:
            r = nc.api(url, tok, "POST", f"/api/v2/meta/bases/{bid}/tables",
                       {"table_name": nombre, "title": nombre, "columns": cols})
            ids[nombre] = r["id"]
            print(f"tabla '{nombre}': creada ({len(cols)} columnas)")
        else:
            ids[nombre] = existentes[nombre]
            # idempotencia de columnas: añadir las que falten
            actuales = nc.columnas(url, tok, ids[nombre])
            faltan = [c for c in cols if c["title"] not in actuales]
            for c in faltan:
                nc.api(url, tok, "POST",
                       f"/api/v2/meta/tables/{ids[nombre]}/columns", c)
            print(f"tabla '{nombre}': OK"
                  + (f" (+{len(faltan)} columnas añadidas)" if faltan else ""))

    # Siembra solo en tablas vacías
    if not nc.records(url, tok, ids["Precios"], 1, incluir_eliminados=True):
        filas = [{"id": l["id"], "valor": l["valor"], "visible": l.get("visible", True)}
                 for l in DATA["precios"]["lineas"]]
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Precios']}/records", filas)
        print(f"Precios: {len(filas)} filas sembradas")
    else:
        print("Precios: ya tiene datos")

    if not nc.records(url, tok, ids["Horarios"], 1, incluir_eliminados=True):
        filas = [{"id": l["id"], "visible": l.get("visible", True)}
                 for l in DATA["horarios"]["lineas"]]
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Horarios']}/records", filas)
        print(f"Horarios: {len(filas)} filas sembradas")
    else:
        print("Horarios: ya tiene datos")

    if "--seed-demo" in sys.argv:
        siembra_demo(url, tok, ids)

    print("\nPROVISION OK")


def _vacia(url, tok, tid):
    """Borra todas las filas de una tabla (por su Id de NocoDB). Se usa antes
    de sembrar el demo para partir de cero."""
    ids = [{"Id": r["Id"]} for r in nc.records(url, tok, tid, 1000,
                                               incluir_eliminados=True)
           if r.get("Id")]
    for i in range(0, len(ids), 100):
        nc.api(url, tok, "DELETE", f"/api/v2/tables/{tid}/records", ids[i:i + 100])
    return len(ids)


def siembra_demo(url, tok, ids):
    """Vacía y repuebla el modelo de oferta con un dataset de demostración:
    dos servicios, una temporada vigente cada uno, clases semanales y ocho
    alumnos apuntados por clase. DESTRUCTIVO: solo bajo --seed-demo."""
    for t in ("Servicios", "Actividades", "Clases", "Agenda", "Reservas"):
        n = _vacia(url, tok, ids[t])
        print(f"demo: {t} vaciada ({n} filas)")

    hoy = datetime.date.today()
    fin = (hoy.replace(day=1) + datetime.timedelta(days=120)).isoformat()

    # Dos servicios con su temporada vigente. (titulo, texto, nivel, dias,
    # hora, dur, lugar, precio, duracion_txt)
    demo = [
        {"titulo": "Hatha yoga", "nivel": "Todos los niveles",
         "texto": "Práctica pausada de posturas y respiración, apta para empezar "
                  "y para mantener el hábito.",
         "dias": ["lun", "mie"], "hora": "19:00", "dur": 75,
         "lugar": "Nerja", "precio": "12 €", "duracion": "75 min"},
        {"titulo": "Yoga +60", "nivel": "Suave",
         "texto": "Movimiento amable pensado para mayores: articulaciones, "
                  "equilibrio y respiración, sin exigencias.",
         "dias": ["mar", "jue"], "hora": "11:00", "dur": 60,
         "lugar": "Maro", "precio": "10 €", "duracion": "60 min"},
    ]

    for d in demo:
        s_uuid = _uuid()
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Servicios']}/records", [{
            "uuid": s_uuid, "se_sigue_ofertando": True,
            "nivel": d["nivel"], "es_hash": "", "revisado": "",
            "titulo_es": d["titulo"], "texto_es": d["texto"],
        }])
        a_uuid = _uuid()
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Actividades']}/records", [{
            "uuid": a_uuid, "servicio_uuid": s_uuid,
            "estado": "en_curso", "hasta": fin,
            "umbral": 4, "interesados": 0, "plazas": 12,
            "cal_event_type_id": 0, "mostrar_contador": True, "visible": True,
            "franjas_elegibles": False, "franjas": "[]",
            "precio": d["precio"], "duracion": d["duracion"], "lugar": d["lugar"],
        }])
        # Clases semanales de la temporada + sus ocurrencias en Agenda, con
        # ocho alumnos apuntados por sesión (copia ligera en Reservas).
        for dia in d["dias"]:
            c_uuid = _uuid()
            nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Clases']}/records", [{
                "uuid": c_uuid, "actividad_id": a_uuid,
                "dia_semana": dia, "hora_inicio": d["hora"],
                "duracion_min": d["dur"], "lugar": d["lugar"],
                "color": "", "activa": True,
            }])
        # Una ocurrencia de agenda de ejemplo (la próxima aparición del primer día)
        ocur_uuid = _uuid()
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Agenda']}/records", [{
            "uuid": ocur_uuid, "actividad_id": a_uuid, "serie_id": _uuid()[:12],
            "titulo": d["titulo"], "tipo": "recurrente",
            "fecha": (hoy + datetime.timedelta(days=7)).isoformat(),
            "hora_inicio": d["hora"], "duracion_min": d["dur"],
            "dias_semana": ",".join(d["dias"]), "lugar": d["lugar"], "color": "",
            "visible_web": True, "avisar_alumnos": False,
            "estado": "programada", "motivo": "", "motivo_texto": "",
        }])
        # Ocho alumnos apuntados (Reservas). Sin cal_uid real: es demo.
        filas = [{
            "cal_uid": _uuid()[:16], "event_type_id": 0,
            "inicio": (hoy + datetime.timedelta(days=7)).isoformat() + "T" + d["hora"] + ":00Z",
            "nombre": n, "email": e, "telefono": t,
            "estado": "accepted", "fecha": datetime.datetime.now().isoformat(),
        } for (n, e, t) in _ALUMNOS_DEMO]
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Reservas']}/records", filas)
        print(f"demo: servicio «{d['titulo']}» + temporada + "
              f"{len(d['dias'])} clases + {len(filas)} alumnos")


if __name__ == "__main__":
    main()
