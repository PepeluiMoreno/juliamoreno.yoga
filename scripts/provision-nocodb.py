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
        # Tarifa tipo por hora de sesión: el precio de referencia del
        # servicio. Cada programación puede fijar luego su precio concreto
        # (Actividades.precio); esta sirve de base y para calcular lo
        # facturado a partir de las horas impartidas.
        col("tarifa_hora", "Number"),
        col("titulo_es", "LongText"), col("texto_es", "LongText"),
        col("titulo_en", "LongText"), col("texto_en", "LongText"),
        col("titulo_fr", "LongText"), col("texto_fr", "LongText"),
        col("titulo_de", "LongText"), col("texto_de", "LongText"),
        col("revisado"), col("es_hash"),
    ],
    "Actividades": [
        col("uuid"), col("servicio_uuid"),
        col("estado"), col("hasta"),
        # Cómo llama Julia al tramo de tiempo en que se da esta actividad.
        # Texto libre a propósito: unas veces es "Temporada 2026/27", otras
        # "Campaña de verano" o simplemente "Otoño". La fecha de vigencia
        # sigue siendo `hasta`; esto es la etiqueta legible.
        col("periodo"),
        # Extensión temporal de la actividad. `hasta` ya existía como fecha de
        # vigencia; `desde` es cuándo arranca. Entre las dos se proyectan las
        # clases, así que cambiarlas reprograma lo que quede por celebrar.
        col("desde"),
        # Calendario semanal propio, en JSON: [{"dia":"lun","hora":"19:00",
        # "duracion_min":75,"lugar":"Nerja"}, ...]. Es la semana tipo de ESTA
        # actividad; la tabla Clases guarda lo mismo desglosado en filas para
        # que la agenda y Cal.diy sigan leyéndolo como hasta ahora.
        col("horario", "LongText"),
        # Suspender no es cancelar: la actividad para un tiempo y se puede
        # reanudar. Se guarda el motivo porque hay que poder explicarlo.
        col("motivo", "LongText"),
        # Si el motivo se publica en la web o se queda en el panel. Lo decide
        # Julia en cada caso: "se traslada al jueves" conviene contarlo, "baja
        # por enfermedad" es asunto suyo.
        col("motivo_publico", "Checkbox"),
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
        # Si este motivo puede contarse en la web o se queda en el panel.
        col("motivo_publico", "Checkbox"),
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
# El alumnado de una academia en la costa de Nerja es justo esta mezcla, y por
# eso la web está en cuatro idiomas: vecinas del pueblo, residentes extranjeros
# y gente que pasa temporadas. Los nombres van variados a propósito para que las
# listas de clase se parezcan a las de verdad.
_ALUMNOS_DEMO = [
    # España
    ("Lucía Fernández", "lucia.fernandez@example.com", "600100001"),
    ("Carmen Díaz Soto", "carmen.diaz@example.com", "600100002"),
    ("Javier Moreno", "javier.moreno@example.com", "600100003"),
    ("Nuria Cabrera", "nuria.cabrera@example.com", "600100004"),
    # Alemania
    ("Ingrid Baumgartner", "ingrid.baumgartner@example.com", "600100005"),
    ("Klaus Hoffmann", "klaus.hoffmann@example.com", "600100006"),
    ("Annelie Schröder", "annelie.schroeder@example.com", "600100007"),
    # Reino Unido
    ("Emily Whitaker", "emily.whitaker@example.com", "600100008"),
    ("Graham Ellis", "graham.ellis@example.com", "600100009"),
    # Suecia
    ("Astrid Lindqvist", "astrid.lindqvist@example.com", "600100010"),
    ("Erik Sjöberg", "erik.sjoberg@example.com", "600100011"),
    # Países Bajos
    ("Femke van Dijk", "femke.vandijk@example.com", "600100012"),
    ("Bram de Vries", "bram.devries@example.com", "600100013"),
    # Francia
    ("Sophie Laurent", "sophie.laurent@example.com", "600100014"),
    ("Mathieu Rousseau", "mathieu.rousseau@example.com", "600100015"),
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
    """Vacía y repuebla el modelo de oferta con un dataset de prueba.

    Busca dos cosas a la vez. Que LUZCA: una academia con su cartera variada,
    la semana llena de clases, alumnos con nombre y apellidos y precios que
    cuadran, de modo que al abrir el panel o la web haya algo que enseñar y no
    dos filas de relleno. Y que PRUEBE: colados entre lo demás van los casos
    que suelen romperse —un servicio con DOS temporadas (la web no debe
    duplicar su tarjeta y ha de quedarse con la vigente), un servicio retirado
    de la cartera, una temporada caducada, clases canceladas y aplazadas, una
    clase suelta y filas en la papelera—, que es donde se ve si el modelo
    aguanta.

    DESTRUCTIVO: vacía las cinco tablas del modelo de oferta. Solo --seed-demo.
    """
    for t in ("Servicios", "Actividades", "Clases", "Agenda", "Reservas"):
        n = _vacia(url, tok, ids[t])
        print(f"demo: {t} vaciada ({n} filas)")

    hoy = datetime.date.today()
    ayer = hoy - datetime.timedelta(days=1)
    def en(dias):
        return (hoy + datetime.timedelta(days=dias)).isoformat()

    post = lambda tabla, filas: nc.api(
        url, tok, "POST", f"/api/v2/tables/{ids[tabla]}/records", filas)

    # --- Servicios: la cartera. Tres vivos y uno retirado. ---
    servicios = [
        {"k": "hatha", "titulo": "Hatha yoga", "nivel": "Todos los niveles", "tarifa": 12,
         "texto": "Práctica pausada de posturas y respiración. Sirve para empezar "
                  "de cero y para sostener el hábito sin castigarse.",
         "oferta": True},
        {"k": "mayores", "titulo": "Yoga para mayores", "nivel": "Suave", "tarifa": 10,
         "texto": "Movimiento amable para articulaciones, equilibrio y respiración. "
                  "Se puede hacer entero desde una silla.",
         "oferta": True},
        {"k": "mar", "titulo": "Yoga junto al mar", "nivel": "Todos los niveles", "tarifa": 14,
         "texto": "Sesión de verano al aire libre, a primera hora, cuando la playa "
                  "todavía está tranquila y el sol no aprieta.",
         "oferta": True},
        {"k": "vinyasa", "titulo": "Vinyasa dinámico", "nivel": "Intermedio", "tarifa": 14,
         "texto": "Secuencias enlazadas con la respiración, a buen ritmo. Para quien "
                  "ya se maneja con las posturas y busca movimiento continuo.",
         "oferta": True},
        {"k": "yin", "titulo": "Yin yoga y descanso", "nivel": "Todos los niveles", "tarifa": 12,
         "texto": "Posturas largas y sostenidas, con apoyos, para soltar tensión "
                  "profunda. La clase de final de semana.",
         "oferta": True},
        # Retirado de la cartera: NO debe salir en la web, pero conserva su
        # historial (temporada pasada, clases y reservas siguen ahí).
        {"k": "embarazo", "titulo": "Yoga para el embarazo", "nivel": "Suave", "tarifa": 15,
         "texto": "Acompañamiento durante el embarazo, por trimestres.",
         "oferta": False},
    ]
    s_uuid = {}
    for s in servicios:
        s_uuid[s["k"]] = _uuid()
        post("Servicios", [{
            "uuid": s_uuid[s["k"]], "se_sigue_ofertando": s["oferta"],
            "nivel": s["nivel"], "tarifa_hora": s["tarifa"],
            "es_hash": "", "revisado": "",
            "titulo_es": s["titulo"], "texto_es": s["texto"],
        }])
    print(f"demo: {len(servicios)} servicios (1 retirado de la cartera)")

    # --- Temporadas. Hatha tiene DOS: una caducada y otra vigente. ---
    # El `periodo` es texto libre a propósito: así llama Julia a cada tramo.
    temporadas = [
        # (clave, servicio, periodo, estado, hasta, visible, plazas, lugar, precio, dur)
        ("hatha_vieja", "hatha", "Temporada 2025/26", "finalizada", en(-40), True, 12, "Nerja", "12 €", "75 min"),
        ("hatha_actual", "hatha", "Temporada 2026/27", "en_curso", en(90), True, 12, "Nerja", "12 €", "75 min"),
        ("mayores_actual", "mayores", "Curso 2026/27", "en_curso", en(120), True, 10, "Maro", "10 €", "60 min"),
        ("vinyasa_actual", "vinyasa", "Otoño", "en_curso", en(90), True, 14, "Nerja", "14 €", "60 min"),
        ("yin_actual", "yin", "Otoño", "en_curso", en(90), True, 12, "Maro", "12 €", "75 min"),
        # Propuesta: aún sondeando interés, no debería contar como ofertada.
        ("mar_verano", "mar", "Campaña de verano", "propuesta", en(60), True, 15, "Playa de Burriana", "14 €", "60 min"),
        # Del servicio retirado: caducada, para comprobar que el historial queda.
        ("embarazo_2025", "embarazo", "Ciclo 2025", "finalizada", en(-200), True, 8, "Nerja", "15 €", "60 min"),
    ]
    a_uuid = {}
    for (k, serv, periodo, estado, hasta, visible, plazas, lugar, precio, dur) in temporadas:
        a_uuid[k] = _uuid()
        post("Actividades", [{
            "uuid": a_uuid[k], "servicio_uuid": s_uuid[serv],
            "periodo": periodo, "estado": estado, "hasta": hasta,
            "umbral": 4, "interesados": 0, "plazas": plazas,
            "cal_event_type_id": 0, "mostrar_contador": True, "visible": visible,
            "franjas_elegibles": False, "franjas": "[]",
            "precio": precio, "duracion": dur, "lugar": lugar,
        }])
    print(f"demo: {len(temporadas)} temporadas (Hatha con 2: una caducada y una vigente)")

    # --- Matriz semanal (Clases) de las temporadas vivas ---
    clases = [
        ("hatha_actual", "lun", "19:00", 75, "Nerja"),
        ("hatha_actual", "mie", "19:00", 75, "Nerja"),
        ("mayores_actual", "mar", "11:00", 60, "Maro"),
        ("mayores_actual", "jue", "11:00", 60, "Maro"),
        ("vinyasa_actual", "mar", "19:30", 60, "Nerja"),
        ("vinyasa_actual", "jue", "19:30", 60, "Nerja"),
        ("yin_actual", "vie", "18:00", 75, "Maro"),
        ("mar_verano", "sab", "09:00", 60, "Playa de Burriana"),
    ]
    for (tk, dia, hora, dmin, lugar) in clases:
        post("Clases", [{
            "uuid": _uuid(), "actividad_id": a_uuid[tk],
            "dia_semana": dia, "hora_inicio": hora, "duracion_min": dmin,
            "lugar": lugar, "color": "", "activa": True,
        }])
    print(f"demo: {len(clases)} clases en la semana tipo")

    # --- Agenda: ocurrencias con estados variados ---
    # Incluye dos el MISMO día a horas compatibles (para ver la holgura de 30
    # min funcionando) y una clase suelta, que es el caso que se colaba sin hora.
    # La agenda se materializa desde la matriz, cuatro semanas atrás y cuatro
    # adelante: así el calendario tiene cuerpo y hay pasado del que sacar
    # cuántas clases se han celebrado.
    DIA_WD = {"lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6}
    titulo_de = {t[0]: next(s["titulo"] for s in servicios if s["k"] == t[1])
                 for t in temporadas}
    serie = {tk: _uuid()[:12] for tk in a_uuid}
    filas_agenda = []
    for (tk, dia, hora, dmin, lugar) in clases:
        wd = DIA_WD[dia]
        for delta in range(-28, 29):
            f = hoy + datetime.timedelta(days=delta)
            if f.weekday() != wd:
                continue
            filas_agenda.append({
                "uuid": _uuid(), "actividad_id": a_uuid[tk], "serie_id": serie[tk],
                "titulo": titulo_de[tk], "tipo": "recurrente",
                "fecha": f.isoformat(), "hora_inicio": hora, "duracion_min": dmin,
                "dias_semana": "", "lugar": lugar, "color": "",
                "visible_web": True, "avisar_alumnos": False,
                "estado": "programada", "motivo": "", "motivo_texto": "",
            })

    # INCIDENCIAS. No son adorno: son la materia prima de la estadística de
    # fidelidad —cuánto de lo programado se acabó dando— y del reparto de
    # motivos. Se siembran repartidas por el pasado, con una proporción
    # verosímil: la mayoría de las clases salen adelante, pero no todas.
    #
    # El motivo distingue de quién fue la baja, que es lo que luego hay que
    # poder contar por separado: no es lo mismo que Julia cancele por enfermedad
    # que que se caiga por falta de alumnos.
    INCIDENCIAS = [
        # (estado, motivo, texto)
        ("cancelada", "enfermedad", "Julia con gripe, avisado por WhatsApp"),
        ("cancelada", "festivo", "Festivo local"),
        ("cancelada", "sin_alumnos", "Nadie se apuntó, se anula"),
        ("cancelada", "temporal", "Levante fuerte, no se puede en la playa"),
        ("cancelada", "aforo_insuficiente", "Solo una alumna, se pasa a particular"),
        ("aplazada", "festivo", "Puente, se recupera la semana siguiente"),
        ("aplazada", "obras", "Obras en el local, se mueve al jueves"),
        ("aplazada", "viaje", "Julia fuera en formación"),
        ("cancelada", "enfermedad", "Baja de Julia"),
        ("aplazada", "temporal", "Aviso por lluvia, se traslada a cubierto"),
    ]
    pasadas = [f for f in filas_agenda if f["fecha"] < hoy.isoformat()]
    # Repartidas a lo largo del pasado, no amontonadas, y sin pasarse: se
    # siembran como mucho en un cuarto de las clases ya dadas, para que la
    # fidelidad quede en cifras de academia que funciona (en torno al 80-85%)
    # y no de negocio a la deriva.
    if pasadas:
        cupo = max(1, len(pasadas) // 4)
        incidencias = INCIDENCIAS[:cupo]
        paso = max(1, len(pasadas) // (len(incidencias) + 1))
        for i, (estado, motivo, texto) in enumerate(incidencias):
            pos = (i + 1) * paso
            if pos < len(pasadas):
                pasadas[pos].update({"estado": estado, "motivo": motivo,
                                     "motivo_texto": texto})
    # Alguna incidencia también en lo que viene: una clase ya cancelada por
    # adelantado y otra aplazada, que es como se ve en la agenda de verdad.
    futuras = [f for f in filas_agenda if f["fecha"] > hoy.isoformat()]
    if len(futuras) > 6:
        futuras[3].update({"estado": "cancelada", "motivo": "festivo",
                           "motivo_texto": "Festivo, avisadas las alumnas"})
        futuras[6].update({"estado": "aplazada", "motivo": "viaje",
                           "motivo_texto": "Julia en un retiro, se recupera"})

    # Clases SUELTAS (puntuales, sin temporada detrás), que es el caso que se
    # colaba sin hora. La de las 16:00 cae el mismo día que Hatha (19:00) y
    # respeta de sobra la holgura de 30 min.
    for (titulo, dias, hora, dmin, lugar) in [
        ("Clase particular · Ana Torres", 2, "16:00", 60, "Nerja"),
        ("Sesión privada · pareja", 6, "10:00", 60, "Nerja"),
        ("Taller de respiración (puntual)", 12, "17:30", 90, "Nerja"),
    ]:
        filas_agenda.append({
            "uuid": _uuid(), "actividad_id": "", "serie_id": "",
            "titulo": titulo, "tipo": "puntual", "fecha": en(dias),
            "hora_inicio": hora, "duracion_min": dmin,
            "dias_semana": "", "lugar": lugar, "color": "",
            "visible_web": False, "avisar_alumnos": False,
            "estado": "programada", "motivo": "", "motivo_texto": "",
        })

    for i in range(0, len(filas_agenda), 50):
        post("Agenda", filas_agenda[i:i + 50])
    n_pas = sum(1 for f in filas_agenda if f["fecha"] < hoy.isoformat())
    n_can = sum(1 for f in filas_agenda if f["estado"] == "cancelada")
    n_apl = sum(1 for f in filas_agenda if f["estado"] == "aplazada")
    n_cel = sum(1 for f in filas_agenda
                if f["fecha"] < hoy.isoformat() and f["estado"] == "programada")
    fidelidad = (100 * n_cel / n_pas) if n_pas else 0
    print(f"demo: {len(filas_agenda)} clases en la agenda "
          f"({n_pas} pasadas, {n_cel} celebradas, {n_can} canceladas, "
          f"{n_apl} aplazadas, 3 sueltas)")
    print(f"demo: fidelidad a lo programado en el pasado: {fidelidad:.0f}%")

    # --- Reservas: alumnado repartido por las clases de las próximas semanas ---
    # Cada clase tiene su grupo, con solapes (hay quien va a dos cosas) y con
    # bajas: unas cuantas canceladas POR EL ALUMNO, que en la estadística de
    # fidelidad cuentan distinto de las que cancela Julia.
    ahora = datetime.datetime.now().isoformat()
    reservas = []

    def apunta(alumnos, dias, hora, estado="accepted"):
        for (n, e, t) in alumnos:
            reservas.append({
                "cal_uid": _uuid()[:16], "event_type_id": 0,
                "inicio": en(dias) + "T" + hora + ":00Z",
                "nombre": n, "email": e, "telefono": t,
                "estado": estado, "fecha": ahora,
            })

    A = _ALUMNOS_DEMO
    apunta(A[0:9], 2, "19:00")     # Hatha del lunes: grupo grande
    apunta(A[9:15], 4, "19:00")    # Hatha del miércoles: otro grupo
    apunta(A[2:8], 3, "11:00")     # Yoga para mayores
    apunta(A[0:5], 5, "19:30")     # Vinyasa
    apunta(A[6:12], 6, "18:00")    # Yin
    # Bajas por parte del alumno.
    apunta(A[1:3], 2, "19:00", estado="cancelled")
    apunta(A[10:11], 3, "11:00", estado="cancelled")

    # Alumnado en clases YA DADAS: sin esto no habría nada facturado que
    # enseñar, porque solo se factura lo impartido. Se recorren las clases
    # pasadas REALES de la agenda —no fechas calculadas a ojo, que caerían en
    # días donde no hay clase— y se les apunta un grupo, rotando la lista para
    # que no vaya siempre la misma gente.
    dadas = sorted([f for f in filas_agenda
                    if f["fecha"] < hoy.isoformat()
                    and f["estado"] == "programada"],
                   key=lambda f: f["fecha"])
    for i, c in enumerate(dadas):
        corte = 4 + (i % 5)                    # entre 4 y 8 alumnos
        grupo = (A * 2)[i % len(A): i % len(A) + corte]
        for (n, e, t) in grupo:
            reservas.append({
                "cal_uid": _uuid()[:16], "event_type_id": 0,
                "inicio": c["fecha"] + "T" + c["hora_inicio"] + ":00Z",
                "nombre": n, "email": e, "telefono": t,
                "estado": "accepted", "fecha": ahora,
            })

    # En lotes: NocoDB rechaza sin más una inserción de cientos de filas de
    # una tacada, y lo hace en silencio (no da error, simplemente no guarda).
    for i in range(0, len(reservas), 50):
        post("Reservas", reservas[i:i + 50])
    n_baja = sum(1 for r in reservas if r["estado"] == "cancelled")
    print(f"demo: {len(reservas)} reservas de {len(A)} alumnos "
          f"({n_baja} canceladas por el alumno)")

    # --- Interesados: gente apuntada a la lista de espera de un servicio ---
    # Se cuentan contra el `umbral` de las actividades en propuesta: cuando lo
    # alcanzan, la actividad pasa sola a programada. Sin esto no hay forma de
    # ver funcionar ese salto. Van al SERVICIO (su uuid), que es a lo que se
    # apunta uno, no a un tramo concreto de calendario.
    _vacia(url, tok, ids["Interesados"])
    FRANJAS_INT = ["lun_tarde", "mar_manana", "mie_tarde", "jue_manana", "sab_manana"]
    interesados = []
    for k, cuantos in (("mar", 6), ("vinyasa", 3), ("yin", 2)):
        for j in range(cuantos):
            n, e, t = _ALUMNOS_DEMO[(j * 3 + cuantos) % len(_ALUMNOS_DEMO)]
            interesados.append({
                "actividad": s_uuid[k], "nombre": n, "contacto": e,
                "franjas": FRANJAS_INT[j % len(FRANJAS_INT)],
                "idioma": ["es", "en", "de", "fr", "nl", "sv"][j % 6],
                "fecha": ahora,
            })
    post("Interesados", interesados)
    print(f"demo: {len(interesados)} interesados "
          f"(6 en «Yoga junto al mar», que está en propuesta con umbral 4)")

    # --- Papelera: dos filas borradas lógicamente ---
    # Para comprobar de un vistazo que lo eliminado NO sale en las vistas ni en
    # la web, pero sigue estando y se puede restaurar.
    post("Agenda", [{
        "uuid": _uuid(), "actividad_id": "", "serie_id": "",
        "titulo": "Clase borrada por error", "tipo": "puntual",
        "fecha": en(8), "hora_inicio": "18:00", "duracion_min": 60,
        "dias_semana": "", "lugar": "Nerja", "color": "",
        "visible_web": False, "avisar_alumnos": False,
        "estado": "programada", "motivo": "", "motivo_texto": "",
        "eliminado": True, "eliminado_fecha": ahora,
    }])
    post("Servicios", [{
        "uuid": _uuid(), "se_sigue_ofertando": False,
        "nivel": "", "es_hash": "", "revisado": "",
        "titulo_es": "Servicio de prueba descartado",
        "texto_es": "Estaba en la papelera cuando se sembró el demo.",
        "eliminado": True, "eliminado_fecha": ahora,
    }])
    print("demo: 2 filas en la papelera (1 clase, 1 servicio)")


if __name__ == "__main__":
    main()
