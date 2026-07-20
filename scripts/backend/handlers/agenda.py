"""
backend.handlers.agenda — rutas /admin/api/agenda y sus operaciones.

  GET    /admin/api/agenda                 lista de ocurrencias
  POST   /admin/api/agenda                 crea (puntual, o recurrente->materializa)
  PATCH  /admin/api/agenda                 edita una ocurrencia
  DELETE /admin/api/agenda                 elimina (con reglas de negocio)
  POST   /admin/api/agenda/cancelar        marca cancelada + motivo
  POST   /admin/api/agenda/replicar        clona ocurrencias al mes siguiente
  POST   /admin/api/agenda/proyectar-matriz  despliega la matriz sobre un mes
  POST   /admin/api/agenda/copiar-mes      copia un mes a otro
"""
from .. import agenda as logica
from .. import datos
from ..util import limpio
from ..web import dispara_rebuild

RUTA = "/admin/api/agenda"


def _lista():
    filas = datos.lee("Agenda")
    # mapa actividad_id (uuid de temporada) -> estado (para reglas de borrado)
    try:
        act_estado = {a.get("uuid"): (a.get("estado") or "").strip()
                      for a in datos.lee("Actividades")}
    except Exception:
        act_estado = {}
    out = []
    for r in filas:
        aid = r.get("actividad_id")
        out.append({
            "Id": r.get("Id"), "titulo": r.get("titulo"),
            "actividad_id": aid, "tipo": r.get("tipo"),
            "dias_semana": r.get("dias_semana"), "fecha": r.get("fecha"),
            "hora_inicio": r.get("hora_inicio"), "duracion_min": r.get("duracion_min"),
            "serie_id": r.get("serie_id"),
            "lugar": r.get("lugar"), "color": r.get("color"),
            "visible_web": r.get("visible_web"),
            "estado": r.get("estado") or "programada",
            "motivo": r.get("motivo"), "motivo_texto": r.get("motivo_texto"),
            "actividad_estado": act_estado.get(aid, ""),
        })
    return out



# Separación mínima entre dos clases del mismo día, en minutos. No es un
# capricho de agenda: entre una clase y la siguiente hay que despedir a
# unos, ventilar, recoger esterillas y recibir a los otros.
HOLGURA_MIN = 30


def _minutos(hhmm):
    try:
        h, _, m = (hhmm or "").partition(":")
        return int(h) * 60 + int(m[:2])
    except (TypeError, ValueError):
        return None


def _hhmm(mins):
    return "%02d:%02d" % (mins // 60 % 24, mins % 60)


def _valida_holgura(candidatas, id_excluido=None):
    """Comprueba que ninguna candidata pise a otra clase del mismo día ni
    se le pegue a menos de HOLGURA_MIN. Devuelve un mensaje o None.

    `candidatas` son filas con fecha, hora_inicio y duracion_min: al crear
    una recurrente son todas sus ocurrencias, no solo la primera.
    """
    try:
        agenda = datos.lee("Agenda")
    except Exception:
        return None  # si no se puede leer, no se bloquea el guardado

    por_fecha = {}
    for r in agenda:
        if (r.get("estado") or "") == "cancelada":
            continue
        if id_excluido and str(r.get("Id")) == str(id_excluido):
            continue
        f = (r.get("fecha") or "")[:10]
        if f:
            por_fecha.setdefault(f, []).append(r)

    for c in candidatas:
        f = (c.get("fecha") or "")[:10]
        ini = _minutos(c.get("hora_inicio"))
        if not f or ini is None:
            continue
        dur = int(c.get("duracion_min") or 60)
        fin = ini + dur
        for otra in por_fecha.get(f, []):
            o_ini = _minutos(otra.get("hora_inicio"))
            if o_ini is None:
                continue
            o_fin = o_ini + int(otra.get("duracion_min") or 60)
            # Vale si una acaba y la otra empieza HOLGURA_MIN después.
            if ini >= o_fin + HOLGURA_MIN or o_ini >= fin + HOLGURA_MIN:
                continue
            nombre = otra.get("titulo") or "otra clase"
            return ("El %s choca con «%s» (%s-%s). Entre una clase y la "
                    "siguiente deben pasar al menos %d minutos: la más "
                    "temprana posible sería a las %s." % (
                        f, nombre, _hhmm(o_ini), _hhmm(o_fin),
                        HOLGURA_MIN, _hhmm(o_fin + HOLGURA_MIN)))
    return None


# Hora por defecto cuando el día está vacío: una mañana razonable para
# empezar. No es una regla de negocio, solo un punto de partida sensato
# para que la agenda proponga algo en vez de dejar el campo en blanco.
HORA_POR_DEFECTO = "09:00"


def _primer_hueco(fecha, duracion_min=60):
    """Primer inicio (HH:MM) del día `fecha` en el que caben `duracion_min`
    minutos sin pisar otra clase ni pegarse a menos de HOLGURA_MIN. Si el
    día está libre, devuelve HORA_POR_DEFECTO.

    Recorre las clases ya ocupadas de ese día ordenadas por hora y prueba,
    en orden: justo antes de la primera, en los huecos entre clases, y tras
    la última. Devuelve el más temprano que quepa.
    """
    dur = int(duracion_min or 60)
    try:
        agenda = datos.lee("Agenda")
    except Exception:
        return HORA_POR_DEFECTO

    f0 = (fecha or "")[:10]
    ocupadas = []
    for r in agenda:
        if (r.get("estado") or "") == "cancelada":
            continue
        if (r.get("fecha") or "")[:10] != f0:
            continue
        ini = _minutos(r.get("hora_inicio"))
        if ini is None:
            continue
        ocupadas.append((ini, ini + int(r.get("duracion_min") or 60)))
    ocupadas.sort()

    if not ocupadas:
        return HORA_POR_DEFECTO

    # Candidato inicial: HORA_POR_DEFECTO si cabe antes de la primera clase.
    cand = _minutos(HORA_POR_DEFECTO)
    for o_ini, o_fin in ocupadas:
        # ¿Cabe [cand, cand+dur] antes de que empiece esta clase, con holgura?
        if cand + dur + HOLGURA_MIN <= o_ini:
            return _hhmm(cand)
        # No cabe: el siguiente hueco posible es tras el fin de esta, con holgura.
        cand = max(cand, o_fin + HOLGURA_MIN)
    return _hhmm(cand)


def _crear(body):
    fila = logica.fila_agenda(body, con_id=False)
    if not fila.get("titulo") and not fila.get("actividad_id"):
        return 422, {"error": "falta título o actividad"}
    try:
        if fila.get("tipo") == "recurrente":
            if not fila.get("dias_semana"):
                return 422, {"error": "una clase recurrente necesita días de la semana"}
            ocurrencias = logica.materializa_mes(fila)
            if not ocurrencias:
                return 422, {"error": "no hay días de ese tipo en lo que queda de mes"}
            choque = _valida_holgura(ocurrencias)
            if choque:
                return 409, {"error": choque}
            datos.guarda_varios("Agenda", ocurrencias)
            dispara_rebuild()
            return 200, {"ok": True, "generadas": len(ocurrencias)}
        if not fila.get("fecha"):
            return 422, {"error": "una sesión puntual necesita fecha"}
        # Sin hora no se guarda: antes se colaba una fila con hora_inicio
        # vacía que además se saltaba el control de solape (una candidata
        # sin hora no se compara con nada). Se propone el primer hueco libre
        # para que el panel lo ofrezca en vez de dejar el campo en blanco.
        if not fila.get("hora_inicio"):
            return 422, {"error": "una sesión puntual necesita hora de inicio",
                         "sugerencia_hora": _primer_hueco(
                             fila.get("fecha"), fila.get("duracion_min"))}
        choque = _valida_holgura([fila])
        if choque:
            return 409, {"error": choque,
                         "sugerencia_hora": _primer_hueco(
                             fila.get("fecha"), fila.get("duracion_min"))}
        datos.guarda("Agenda", fila)
        dispara_rebuild()
        return 200, {"ok": True}
    except Exception as e:
        return 502, {"error": f"no se pudo crear: {e}"}


def _editar(body):
    if not body.get("Id"):
        return 422, {"error": "falta Id"}
    fila = logica.fila_agenda(body, con_id=True)
    try:
        # Aplazar cambia fecha y hora, así que hay que revalidar. Se
        # comprueba sobre la fila RESULTANTE: el cuerpo trae solo lo que
        # cambia, y una hora nueva puede chocar usando la fecha vieja.
        if any(k in fila for k in ("fecha", "hora_inicio", "duracion_min")):
            actual = next((r for r in datos.lee("Agenda")
                           if str(r.get("Id")) == str(fila["Id"])), {})
            futura = {
                "fecha": fila.get("fecha", actual.get("fecha")),
                "hora_inicio": fila.get("hora_inicio", actual.get("hora_inicio")),
                "duracion_min": fila.get("duracion_min", actual.get("duracion_min")),
            }
            choque = _valida_holgura([futura], id_excluido=fila["Id"])
            if choque:
                return 409, {"error": choque}
        datos.actualiza("Agenda", fila)
        dispara_rebuild()
        return 200, {"ok": True}
    except Exception as e:
        return 502, {"error": f"no se pudo guardar: {e}"}


def _eliminar(body):
    ids = body.get("ids")
    if not (isinstance(ids, list) and ids):
        ids = [body["Id"]] if body.get("Id") else []
    if not ids:
        return 422, {"error": "falta Id"}
    definitivo = bool(body.get("definitivo"))
    try:
        # El borrado normal manda la clase a la papelera y se puede deshacer,
        # así que se permite siempre. El DEFINITIVO no tiene vuelta atrás: ahí
        # sigue valiendo la regla de siempre —una clase en curso o anunciada en
        # la web se cancela o se aplaza, no se hace desaparecer— porque hay
        # alumnos que cuentan con ella.
        if definitivo:
            agenda = {r.get("Id"): r for r in datos.lee("Agenda")}
            act_estado = {a.get("uuid"): (a.get("estado") or "").strip()
                          for a in datos.lee("Actividades")}
            for i in ids:
                r = agenda.get(int(i))
                if not r:
                    continue
                en_curso = act_estado.get(r.get("actividad_id")) == "en_curso"
                anunciada = bool(r.get("visible_web"))
                if en_curso or anunciada:
                    return 409, {"error": "esa clase no se puede borrar para siempre (pertenece a una actividad en curso o está anunciada en la web). Puedes cancelarla, aplazarla, o mandarla a la papelera."}
        datos.borra_varios("Agenda", [int(i) for i in ids], definitivo=definitivo)
        dispara_rebuild()
        return 200, {"ok": True, "borradas": len(ids), "definitivo": definitivo}
    except Exception as e:
        return 502, {"error": f"no se pudo borrar: {e}"}


def _cancelar(body):
    ids = body.get("ids") or ([body["Id"]] if body.get("Id") else [])
    motivo = limpio(body.get("motivo"), 100)
    if not ids:
        return 422, {"error": "falta la clase a cancelar"}
    if not motivo:
        return 422, {"error": "hay que indicar un motivo de cancelación"}
    try:
        filas = [{
            "Id": int(i), "estado": "cancelada", "motivo": motivo,
            "motivo_texto": limpio(body.get("motivo_texto"), 1000),
            "avisar_alumnos": bool(body.get("avisar_alumnos")),
        } for i in ids]
        datos.actualiza_varios("Agenda", filas)
        dispara_rebuild()
        return 200, {"ok": True, "canceladas": len(ids)}
    except Exception as e:
        return 502, {"error": f"no se pudo cancelar: {e}"}


def _replicar(body):
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return 422, {"error": "no se seleccionó ninguna clase"}
    try:
        n = logica.replica_ocurrencias([int(i) for i in ids])
        dispara_rebuild()
        return 200, {"ok": True, "replicadas": n}
    except Exception as e:
        return 502, {"error": f"no se pudo replicar: {e}"}


def _proyectar(body):
    mes = limpio(body.get("mes"), 7)  # YYYY-MM
    if len(mes) != 7:
        return 422, {"error": "falta el mes (YYYY-MM)"}
    try:
        n = logica.proyecta_matriz(mes)
        dispara_rebuild()
        return 200, {"ok": True, "generadas": n}
    except Exception as e:
        return 502, {"error": f"no se pudo proyectar: {e}"}


def _copiar_mes(body):
    desde = limpio(body.get("desde"), 7)
    hasta = limpio(body.get("hasta"), 7)
    if not (len(desde) == 7 and len(hasta) == 7):
        return 422, {"error": "faltan meses origen/destino (YYYY-MM)"}
    try:
        n = logica.copia_mes(desde, hasta)
        dispara_rebuild()
        return 200, {"ok": True, "copiadas": n}
    except Exception as e:
        return 502, {"error": f"no se pudo copiar: {e}"}


# Sub-rutas POST -> función que las resuelve
_SUBRUTAS_POST = {
    RUTA + "/cancelar": _cancelar,
    RUTA + "/replicar": _replicar,
    RUTA + "/proyectar-matriz": _proyectar,
    RUTA + "/copiar-mes": _copiar_mes,
}


def handle(req):
    # Sub-rutas POST (cancelar, replicar, proyectar, copiar-mes)
    if req.metodo == "POST" and req.path in _SUBRUTAS_POST:
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _SUBRUTAS_POST[req.path](req.body)

    if req.path != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}

    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "agenda": _lista()}
        except Exception as e:
            return 502, {"error": f"no se pudo leer: {e}"}
    if req.metodo == "POST":
        return _crear(req.body)
    if req.metodo == "PATCH":
        return _editar(req.body)
    if req.metodo == "DELETE":
        return _eliminar(req.body)
    return None
