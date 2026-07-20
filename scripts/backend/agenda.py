"""
backend.agenda — lógica de ocurrencias de la agenda.

El modelo: cada entrada de la Agenda es una *ocurrencia* concreta (fecha +
hora + duración). Las clases "recurrentes" no se guardan como reglas, sino
que se materializan en ocurrencias. Aquí viven las operaciones que generan
o transforman esas ocurrencias:

  materializa_mes        una definición recurrente -> ocurrencias del mes
  proyecta_matriz        la matriz de Clases (semana tipo) -> mes completo
  replica_ocurrencias    clona ocurrencias al mes siguiente (misma posición)
  copia_mes              copia un mes entero a otro (misma posición semanal)
  horas_programadas_mes  suma de horas de clase del mes en curso
  fila_agenda            construye/sanea una fila de Agenda desde una petición
"""
import calendar
import datetime
import json
import uuid

from . import datos
from .util import limpio, DIA_NUM


def _nueva_serie():
    return uuid.uuid4().hex[:12]


def _ocurrencia(base, fecha, serie, visible=None):
    """Construye una fila de ocurrencia puntual a partir de una definición."""
    return {
        "titulo": base.get("titulo", ""),
        "actividad_id": base.get("actividad_id", ""),
        "tipo": "puntual",
        "fecha": fecha.isoformat(),
        "hora_inicio": base.get("hora_inicio", ""),
        "duracion_min": base.get("duracion_min"),
        "lugar_uuid": base.get("lugar_uuid", ""),
        "lugar": base.get("lugar", ""),
        "color": base.get("color", ""),
        "visible_web": base.get("visible_web", False) if visible is None else visible,
        "serie_id": serie,
    }


def _pos_semanal(dia_mes):
    """Posición ordinal del día dentro de su día de semana (0 = primera)."""
    return (dia_mes - 1) // 7


def _fecha_por_posicion(anio, mes, weekday, pos):
    """Fecha del mes con ese weekday en esa posición ordinal, o None."""
    ndias = calendar.monthrange(anio, mes)[1]
    cuenta = -1
    for dia in range(1, ndias + 1):
        fd = datetime.date(anio, mes, dia)
        if fd.weekday() == weekday:
            cuenta += 1
            if cuenta == pos:
                return fd
    return None


def materializa_mes(base, anio=None, mes=None):
    """Convierte una definición recurrente (dias_semana + horas) en ocurrencias
    puntuales concretas, una por cada día correspondiente. Si se pasa anio/mes,
    genera para ese mes completo; si no, desde hoy (o vigencia_desde) hasta fin
    del mes en curso. Todas comparten serie_id."""
    dias = {DIA_NUM.get(x.strip()) for x in (base.get("dias_semana") or "").split(",")}
    dias.discard(None)
    if not dias:
        return []
    hoy = datetime.date.today()
    if anio and mes:
        desde = datetime.date(anio, mes, 1)
    else:
        desde_s = (base.get("vigencia_desde") or "")[:10]
        try:
            desde = datetime.date.fromisoformat(desde_s) if desde_s else hoy
        except Exception:
            desde = hoy
        if desde < hoy:
            desde = hoy
    ndias = calendar.monthrange(desde.year, desde.month)[1]
    fin = datetime.date(desde.year, desde.month, ndias)
    serie = _nueva_serie()
    ocurrencias = []
    d = desde
    while d <= fin:
        if d.weekday() in dias:
            ocurrencias.append(_ocurrencia(base, d, serie))
        d += datetime.timedelta(days=1)
    return ocurrencias


def proyecta_matriz(mes_ym):
    """Proyecta la matriz de Clases (semana tipo) sobre un mes completo: por
    cada celda activa, genera una ocurrencia por cada día del mes que caiga en
    su día de la semana. Cada celda produce una serie. Devuelve cuántas."""
    y, m = map(int, mes_ym.split("-"))
    celdas = datos.lee("Clases")
    ndias = calendar.monthrange(y, m)[1]
    # Título de cada temporada: vive en su Servicio. acts mapea el uuid de la
    # temporada (lo que Clases.actividad_id referencia) al título del servicio.
    try:
        servicios = {s.get("uuid"): s.get("titulo_es") for s in datos.lee("Servicios")}
        acts = {a.get("uuid"): servicios.get(a.get("servicio_uuid"))
                for a in datos.lee("Actividades")}
    except Exception:
        acts = {}
    nuevas = []
    for c in celdas:
        if not c.get("activa"):
            continue
        wd = DIA_NUM.get((c.get("dia_semana") or "").strip())
        if wd is None:
            continue
        serie = _nueva_serie()
        titulo = acts.get(c.get("actividad_id")) or c.get("actividad_id") or "(clase)"
        base = dict(c, titulo=titulo)
        for dia in range(1, ndias + 1):
            fecha = datetime.date(y, m, dia)
            if fecha.weekday() == wd:
                nuevas.append(_ocurrencia(base, fecha, serie, visible=True))
    if nuevas:
        datos.guarda_varios("Agenda", nuevas)
    return len(nuevas)


def replica_ocurrencias(ids):
    """Clona las ocurrencias indicadas (por Id) al mes siguiente al de cada
    una, en su misma posición semanal (2º martes -> 2º martes)."""
    por_id = {r.get("Id"): r for r in datos.lee("Agenda")}
    serie = _nueva_serie()
    nuevas = []
    for rid in ids:
        r = por_id.get(rid)
        if not r:
            continue
        try:
            d = datetime.date.fromisoformat((r.get("fecha") or "")[:10])
        except Exception:
            continue
        ym, mm = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        destino = _fecha_por_posicion(ym, mm, d.weekday(), _pos_semanal(d.day))
        if destino is None:
            continue
        nuevas.append(_ocurrencia(r, destino, serie))
    if nuevas:
        datos.guarda_varios("Agenda", nuevas)
    return len(nuevas)


def copia_mes(desde_ym, hasta_ym):
    """Copia las ocurrencias del mes origen al destino, preservando el patrón
    semanal (1er lunes -> 1er lunes). Devuelve cuántas."""
    ya, ma = map(int, desde_ym.split("-"))
    yd, md = map(int, hasta_ym.split("-"))
    origen = []
    for f in datos.lee("Agenda"):
        try:
            d = datetime.date.fromisoformat((f.get("fecha") or "")[:10])
        except Exception:
            continue
        if d.year == ya and d.month == ma:
            origen.append((d, f))
    if not origen:
        return 0
    serie = _nueva_serie()
    nuevas = []
    for d, f in origen:
        destino = _fecha_por_posicion(yd, md, d.weekday(), _pos_semanal(d.day))
        if destino is None:
            continue
        nuevas.append(_ocurrencia(f, destino, serie))
    if nuevas:
        datos.guarda_varios("Agenda", nuevas)
    return len(nuevas)


def horas_programadas_mes():
    """Suma las horas de clase del mes en curso a partir de la Agenda.

    Cada fila de Agenda ES una ocurrencia con su fecha —las recurrentes se
    materializan al crearlas o al proyectar la matriz—, así que basta con
    sumar las del mes. Antes, para las de tipo "recurrente" se intentaba
    expandir dias_semana como si la fila fuera la regla y no la ocurrencia:
    como una ocurrencia ya materializada no lleva dias_semana, no sumaban
    nada y el panel daba 2 horas al mes teniendo la agenda llena.

    No cuentan las canceladas: esa clase no se dio. Las aplazadas tampoco
    aquí, porque su hora se cuenta el día al que se movieron.
    """
    try:
        filas = datos.lee("Agenda")
    except Exception:
        return 0.0
    hoy = datetime.date.today()
    total = 0.0
    for f in filas:
        if (f.get("estado") or "") in ("cancelada", "aplazada"):
            continue
        try:
            dur = int(f.get("duracion_min") or 0) / 60.0
        except Exception:
            continue
        if dur <= 0:
            continue
        try:
            d = datetime.date.fromisoformat((f.get("fecha") or "")[:10])
        except Exception:
            continue
        if d.year == hoy.year and d.month == hoy.month:
            total += dur
    return round(total, 1)


def fila_agenda(body, con_id):
    """Construye la fila de Agenda desde el cuerpo de la petición, saneando."""
    fila = {}
    if con_id:
        fila["Id"] = body["Id"]
    for c in ("titulo", "actividad_id", "tipo", "dias_semana", "lugar", "color",
              "hora_inicio", "serie_id", "estado", "motivo"):
        if c in body:
            fila[c] = limpio(body[c], 200)
    if "motivo_texto" in body:
        fila["motivo_texto"] = limpio(body["motivo_texto"], 1000)
    if "duracion_min" in body and body["duracion_min"] not in (None, ""):
        try:
            fila["duracion_min"] = int(body["duracion_min"])
        except Exception:
            pass
    if "fecha" in body:
        v = limpio(body["fecha"], 20)
        fila["fecha"] = v if v else None
    if "visible_web" in body:
        fila["visible_web"] = bool(body["visible_web"])
    if "avisar_alumnos" in body:
        fila["avisar_alumnos"] = bool(body["avisar_alumnos"])
    return fila


# --- Proyección de una actividad concreta ----------------------------------
#
# Una actividad tiene su propio calendario semanal y una extensión temporal
# (desde/hasta). De ahí salen sus clases: una ocurrencia por cada día que
# encaje, entre las dos fechas. Si el calendario o las fechas cambian, hay que
# rehacer lo que aún no se ha dado, y solo eso: lo ya impartido es historia y
# no se toca.

def horario_de(actividad):
    """Lista de franjas semanales de una actividad, desde su campo `horario`
    (JSON). Devuelve [] si está vacío o mal formado: sin horario no hay nada
    que proyectar, que es distinto de fallar."""
    try:
        franjas = json.loads(actividad.get("horario") or "[]")
    except Exception:
        return []
    if not isinstance(franjas, list):
        return []
    limpias = []
    for f in franjas:
        if not isinstance(f, dict):
            continue
        dia = (f.get("dia") or "").strip()
        hora = (f.get("hora") or "").strip()
        if DIA_NUM.get(dia) is None or not hora:
            continue
        limpias.append({
            "dia": dia, "hora": hora,
            "duracion_min": int(f.get("duracion_min") or 60),
            "lugar_uuid": (f.get("lugar_uuid") or "").strip(),
            "lugar": (f.get("lugar") or "").strip(),
        })
    return limpias


def _rango(actividad, desde_min=None):
    """(inicio, fin) de la actividad como fechas. `desde_min` recorta el
    principio, que es como se reprograma solo lo que queda por delante."""
    def _f(v):
        try:
            return datetime.date.fromisoformat(str(v or "")[:10])
        except Exception:
            return None
    ini = _f(actividad.get("desde")) or datetime.date.today()
    fin = _f(actividad.get("hasta"))
    if desde_min and ini < desde_min:
        ini = desde_min
    return ini, fin


def clases_de(actividad_uuid, agenda=None):
    """Ocurrencias de una actividad, de la agenda."""
    filas = agenda if agenda is not None else datos.lee("Agenda")
    return [r for r in filas
            if (r.get("actividad_id") or "") == actividad_uuid]


def proyecta_actividad(actividad, titulo, desde_min=None):
    """Genera las ocurrencias de una actividad entre sus fechas. Devuelve la
    lista de filas nuevas (no las guarda)."""
    franjas = horario_de(actividad)
    ini, fin = _rango(actividad, desde_min)
    if not franjas or not fin or fin < ini:
        return []
    serie = _nueva_serie()
    nuevas = []
    for f in franjas:
        wd = DIA_NUM.get(f["dia"])
        dia = ini
        while dia <= fin:
            if dia.weekday() == wd:
                nuevas.append(_ocurrencia({
                    "titulo": titulo,
                    "actividad_id": actividad.get("uuid") or "",
                    "hora_inicio": f["hora"],
                    "duracion_min": f["duracion_min"],
                    "lugar_uuid": f.get("lugar_uuid") or actividad.get("lugar_uuid") or "",
                    "lugar": f["lugar"] or actividad.get("lugar") or "",
                    "color": "",
                }, dia, serie, visible=bool(actividad.get("visible"))))
            dia += datetime.timedelta(days=1)
    return nuevas


def reprograma_actividad(actividad, titulo, desde=None):
    """Rehace las clases de una actividad que aún no se han celebrado.

    Borra las ocurrencias futuras y las vuelve a generar con el calendario y
    las fechas actuales. Lo ya pasado no se toca. Devuelve (borradas, creadas).
    """
    hoy = desde or datetime.date.today()
    uuid_act = actividad.get("uuid") or ""
    futuras = [r for r in clases_de(uuid_act)
               if str(r.get("fecha") or "")[:10] >= hoy.isoformat()]
    if futuras:
        datos.borra_varios("Agenda", [r["Id"] for r in futuras if r.get("Id")],
                           definitivo=True)
    nuevas = proyecta_actividad(actividad, titulo, desde_min=hoy)
    for i in range(0, len(nuevas), 50):
        datos.guarda_varios("Agenda", nuevas[i:i + 50])
    return len(futuras), len(nuevas)


def sincroniza_matriz(actividad):
    """Vuelca el calendario semanal de la actividad a la tabla Clases.

    La matriz sigue siendo la que leen el calendario del panel y el alta de
    clases en Cal.diy, así que las dos representaciones tienen que decir lo
    mismo: se borran las filas de esta actividad y se escriben las de su
    horario. Que el horario viva en la actividad y no suelto en Clases es lo
    que permite reprogramar sabiendo a qué actividad pertenece cada franja.
    """
    uuid_act = actividad.get("uuid") or ""
    try:
        viejas = [c for c in datos.lee("Clases")
                  if (c.get("actividad_id") or "") == uuid_act]
        if viejas:
            datos.borra_varios("Clases", [c["Id"] for c in viejas if c.get("Id")],
                               definitivo=True)
        filas = [{
            "uuid": uuid.uuid4().hex,
            "actividad_id": uuid_act,
            "dia_semana": f["dia"], "hora_inicio": f["hora"],
            "duracion_min": f["duracion_min"],
            "lugar_uuid": f.get("lugar_uuid") or actividad.get("lugar_uuid") or "",
            "lugar": f["lugar"] or actividad.get("lugar") or "",
            "color": "", "activa": True,
        } for f in horario_de(actividad)]
        if filas:
            datos.guarda_varios("Clases", filas)
        return len(filas)
    except Exception:
        return 0


def aplica_a_futuras(actividad_uuid, cambios, desde=None):
    """Aplica un cambio a las clases de una actividad que quedan por celebrar.

    Se usa para suspender, cancelar o trasladar la actividad entera: la orden
    la da Julia sobre la actividad, pero quien la sufre es cada una de sus
    clases. Las ya dadas se quedan como están. Devuelve cuántas se tocaron.
    """
    hoy = (desde or datetime.date.today()).isoformat()
    pendientes = [r for r in clases_de(actividad_uuid)
                  if str(r.get("fecha") or "")[:10] >= hoy
                  and (r.get("estado") or "") != "cancelada"]
    if not pendientes:
        return 0
    filas = [dict(cambios, Id=r["Id"]) for r in pendientes if r.get("Id")]
    for i in range(0, len(filas), 50):
        datos.actualiza_varios("Agenda", filas[i:i + 50])
    return len(filas)


# --- El lugar como límite de la planificación ------------------------------
#
# Un local no es solo una etiqueta: tiene un aforo y unas horas en que se puede
# usar, y las dos cosas acotan lo que se puede programar. Hay que comprobarlo
# en los DOS niveles de planificación, porque son puertas distintas: el
# calendario semanal de una actividad, y la clase suelta que se mete en la
# agenda. Si solo se validara uno, por el otro entraría lo imposible.

def lugares_por_uuid():
    try:
        return {(l.get("uuid") or ""): l for l in datos.lee("Lugares")}
    except Exception:
        return {}


def disponibilidad_de(lugar, temporada=None, tipo=None):
    """Franjas en que se puede usar el local: [(dia, desde_min, hasta_min)].

    El horario tiene dos dimensiones además del día: la TEMPORADA (verano o
    invierno, porque un local de costa no abre igual en agosto que en enero)
    y el TIPO DE DÍA (laborable o festivo). Una franja sin temporada o sin
    tipo vale para todas, que es el caso corriente y evita tener que escribir
    cuatro veces lo mismo.

    Sin datos, [] = el local no impone horario.
    """
    try:
        crudo = json.loads((lugar or {}).get("disponibilidad") or "[]")
    except Exception:
        return []
    if not isinstance(crudo, list):
        return []
    fuera = []
    for f in crudo:
        if not isinstance(f, dict):
            continue
        dia = (f.get("dia") or "").strip()
        if DIA_NUM.get(dia) is None:
            continue
        # Una franja marcada para otra temporada u otro tipo de día no aplica.
        f_temp = (f.get("temporada") or "").strip()
        f_tipo = (f.get("tipo") or "").strip()
        if temporada and f_temp and f_temp != temporada:
            continue
        if tipo and f_tipo and f_tipo != tipo:
            continue
        d, h = _min_hhmm(f.get("desde")), _min_hhmm(f.get("hasta"))
        if d is None or h is None or h <= d:
            continue
        fuera.append((dia, d, h))
    return fuera


# Verano es temporada alta en la costa: el local de la playa solo sirve
# entonces, y los de interior cambian de horario. Se toma por meses porque
# no hay una fecha oficial que valga para todos los años.
MESES_VERANO = (6, 7, 8, 9)


def temporada_de(fecha):
    """"verano" o "invierno" según el mes."""
    try:
        return "verano" if fecha.month in MESES_VERANO else "invierno"
    except Exception:
        return None


def _min_hhmm(hhmm):
    try:
        h, _, m = (hhmm or "").partition(":")
        return int(h) * 60 + int(m[:2])
    except (TypeError, ValueError):
        return None


def cabe_en_lugar(lugar, dia, hora, duracion_min, temporada=None, tipo=None):
    """¿Cabe una clase de `duracion_min` ese día a esa hora en el local?
    Devuelve None si cabe, o el motivo por el que no. `temporada` y `tipo`
    acotan qué franjas del horario aplican.

    Ojo con la diferencia entre "el local no tiene horario" y "el local no
    abre en esta temporada": la primera no impone nada, la segunda lo cierra
    del todo. Se distingue mirando el horario completo antes de filtrar.
    """
    todas = disponibilidad_de(lugar)          # sin filtrar: ¿tiene horario?
    if not todas:
        return None                            # sin horario = sin restricción
    franjas = disponibilidad_de(lugar, temporada, tipo)
    if not franjas:
        # Tiene horario, pero ninguna franja vale para esta temporada o tipo
        # de día: entonces está cerrado, no libre.
        cuando = " ".join(x for x in (("en " + temporada) if temporada else "",
                                      ("los días " + tipo) if tipo else "") if x)
        return "%s no abre %s" % (nombre_lugar(lugar), cuando or "ese día")
    ini = _min_hhmm(hora)
    if ini is None:
        return None
    fin = ini + int(duracion_min or 60)
    del_dia = [(d, h) for (dd, d, h) in franjas if dd == dia]
    if not del_dia:
        return "%s no abre los %s" % (nombre_lugar(lugar), dia)
    for (d, h) in del_dia:
        if ini >= d and fin <= h:
            return None
    abierto = ", ".join("%s-%s" % (_hhmm_de(d), _hhmm_de(h)) for (d, h) in del_dia)
    return "%s los %s solo está disponible de %s" % (
        nombre_lugar(lugar), dia, abierto)


def _hhmm_de(mins):
    return "%02d:%02d" % (mins // 60, mins % 60)


def nombre_lugar(lugar):
    return (lugar or {}).get("nombre_es") or "el local"


def valida_aforo(lugar, plazas):
    """Las plazas de una actividad no pueden pasar del aforo de la sala."""
    if not lugar or not plazas:
        return None
    try:
        aforo = int(lugar.get("aforo") or 0)
        plazas = int(plazas)
    except Exception:
        return None
    if aforo and plazas > aforo:
        return "%s tiene aforo para %d, y se piden %d plazas" % (
            nombre_lugar(lugar), aforo, plazas)
    return None


def valida_horario_actividad(actividad, lugares=None):
    """Comprueba el calendario semanal de una actividad contra su local.

    Este es el primer nivel de planificación: lo que se decide una vez y luego
    se proyecta muchas veces. Un choque aquí se multiplica por todas las clases
    del periodo, así que conviene cazarlo antes de proyectar nada.
    """
    lugares = lugares if lugares is not None else lugares_por_uuid()
    problemas = []
    aforo = valida_aforo(lugares.get(actividad.get("lugar_uuid") or ""),
                         actividad.get("plazas"))
    if aforo:
        problemas.append(aforo)
    for f in horario_de(actividad):
        # Cada franja puede tener su propio local; si no, el de la actividad.
        lug = lugares.get(f.get("lugar_uuid") or actividad.get("lugar_uuid") or "")
        choque = cabe_en_lugar(lug, f["dia"], f["hora"], f["duracion_min"])
        if choque:
            problemas.append(choque)
    return problemas
