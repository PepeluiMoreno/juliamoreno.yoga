"""
backend.handlers.actividades — rutas de servicios y de su programación.

Modelo (ver docs/funcionalidades/actividades-clases-agenda.md):
  - SERVICIO: lo que Julia ofrece, atemporal ("Hatha yoga"). Nombre,
    descripción, nivel del alumnado, tarifa tipo por hora de sesión, y si
    se sigue ofertando (la cartera).
  - ACTIVIDAD: la PROGRAMACIÓN de un servicio en un tramo de tiempo. Cuelga
    de él por servicio_uuid y lleva lo temporal: el `periodo` —cómo llama
    Julia a ese tramo: "Campaña de verano", "Otoño", "Temporada 2026/27"—,
    la vigencia (`hasta`), estado, franjas, aforo, precio y el enlace a
    Cal.diy.

Dos rutas, cada una con su CRUD:
  /admin/api/servicios     GET/POST/PATCH/DELETE   la cartera
  /admin/api/actividades   GET/POST/PATCH/DELETE   la programación

Los identificadores son UUID (uuid4().hex), no slugs. NocoDB mantiene su
`Id` numérico, que es el que viaja en los PATCH.

Cada handler recibe `req` y devuelve (codigo, dict), o None si no le
corresponde la ruta/método.
"""
import uuid

from .. import agenda as logica
from .. import datos
from ..util import limpio, valido_texto
from ..web import dispara_rebuild

RUTA_SERVICIOS = "/admin/api/servicios"
RUTA_ACTIVIDADES = "/admin/api/actividades"
RUTA_ACCION = "/admin/api/actividades/accion"


def _nuevo_uuid():
    return uuid.uuid4().hex


# --- Servicios (identidad + cartera) ---------------------------------------

def _servicios_lista():
    out = []
    for r in datos.lee("Servicios"):
        out.append({
            "Id": r.get("Id"), "uuid": r.get("uuid"),
            "se_sigue_ofertando": r.get("se_sigue_ofertando"),
            "titulo_es": r.get("titulo_es"), "texto_es": r.get("texto_es"),
            "foto": r.get("foto"), "nivel": r.get("nivel"),
            "tarifa_hora": r.get("tarifa_hora"),
        })
    return out


def _servicios_handle(req):
    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "servicios": _servicios_lista()}
        except Exception as e:
            return 502, {"error": f"no se pudo leer: {e}"}

    if req.metodo == "POST":
        body = req.body
        titulo = limpio(body.get("titulo_es"), 200)
        if not valido_texto(titulo):
            return 422, {"error": "falta el título del servicio"}
        fila = {
            "uuid": _nuevo_uuid(),
            "titulo_es": titulo,
            "texto_es": limpio(body.get("texto_es"), 2000),
            "foto": limpio(body.get("foto"), 500),
            "nivel": limpio(body.get("nivel"), 40),
            "se_sigue_ofertando": bool(body.get("se_sigue_ofertando", True)),
            "es_hash": "",
        }
        if body.get("tarifa_hora") not in (None, ""):
            try:
                fila["tarifa_hora"] = float(body["tarifa_hora"])
            except Exception:
                pass
        try:
            datos.guarda("Servicios", fila)
            dispara_rebuild()
            return 200, {"ok": True, "uuid": fila["uuid"]}
        except Exception as e:
            return 502, {"error": f"no se pudo crear: {e}"}

    if req.metodo == "PATCH":
        body = req.body
        if not body.get("Id"):
            return 422, {"error": "falta Id"}
        fila = {"Id": body["Id"]}
        for c in ("titulo_es", "texto_es", "foto", "nivel"):
            if c in body:
                fila[c] = limpio(body[c], 2000)
        if "se_sigue_ofertando" in body:
            fila["se_sigue_ofertando"] = bool(body["se_sigue_ofertando"])
        if "tarifa_hora" in body:
            try:
                fila["tarifa_hora"] = (float(body["tarifa_hora"])
                                       if body["tarifa_hora"] not in (None, "") else None)
            except Exception:
                pass
        # Al cambiar el texto ES, vaciar es_hash para forzar re-traducción.
        if "titulo_es" in fila or "texto_es" in fila:
            fila["es_hash"] = ""
        try:
            datos.actualiza("Servicios", fila)
            dispara_rebuild()
            return 200, {"ok": True}
        except Exception as e:
            return 502, {"error": f"no se pudo guardar: {e}"}

    if req.metodo == "DELETE":
        return _borrar("Servicios", req.body or {})

    return None


def _borrar(tabla, body):
    """Manda a la papelera (o borra para siempre con definitivo=true).

    Retirar algo de la oferta NO es borrarlo: para eso está
    se_sigue_ofertando en el servicio, que conserva el historial. Aquí se
    borra de verdad, y por eso el panel enseña antes qué arrastra.
    """
    if not body.get("Id"):
        return 422, {"error": "falta Id"}
    definitivo = bool(body.get("definitivo"))
    try:
        datos.borra(tabla, body["Id"], definitivo=definitivo)
        dispara_rebuild()
        return 200, {"ok": True, "definitivo": definitivo}
    except Exception as e:
        return 502, {"error": f"no se pudo eliminar: {e}"}


# --- Actividades / temporadas (programación temporal) ----------------------

def _actividades_lista():
    out = []
    for r in datos.lee("Actividades"):
        out.append({
            "Id": r.get("Id"), "uuid": r.get("uuid"),
            "servicio_uuid": r.get("servicio_uuid"),
            "estado": r.get("estado"), "hasta": r.get("hasta"),
            "desde": r.get("desde"), "horario": r.get("horario"),
            "motivo": r.get("motivo"), "motivo_publico": r.get("motivo_publico"),
            "periodo": r.get("periodo"),
            "umbral": r.get("umbral"), "plazas": r.get("plazas"),
            "franjas": r.get("franjas"), "franjas_elegibles": r.get("franjas_elegibles"),
            "visible": r.get("visible"), "mostrar_contador": r.get("mostrar_contador"),
            "cal_event_type_id": r.get("cal_event_type_id"),
            "precio": r.get("precio"), "duracion": r.get("duracion"),
            "lugar": r.get("lugar"), "interesados": r.get("interesados"),
        })
    return out


def _actividades_handle(req):
    if req.metodo == "GET":
        try:
            return 200, {"ok": True, "actividades": _actividades_lista()}
        except Exception as e:
            return 502, {"error": f"no se pudo leer: {e}"}

    if req.metodo == "POST":
        body = req.body
        servicio_uuid = limpio(body.get("servicio_uuid"), 40)
        if not servicio_uuid:
            return 422, {"error": "una temporada necesita un servicio (servicio_uuid)"}
        fila = {
            "uuid": _nuevo_uuid(),
            "servicio_uuid": servicio_uuid,
            "estado": limpio(body.get("estado"), 20) or "propuesta",
            "periodo": limpio(body.get("periodo"), 80),
            "desde": limpio(body.get("desde"), 10),
            "horario": limpio(body.get("horario"), 4000),
            "franjas": limpio(body.get("franjas"), 500),
            "interesados": 0,
        }
        for c in ("umbral", "plazas"):
            if body.get(c) not in (None, ""):
                try:
                    fila[c] = int(body[c])
                except Exception:
                    pass
        fila["visible"] = bool(body.get("visible", True))
        fila["mostrar_contador"] = bool(body.get("mostrar_contador", True))
        fila["franjas_elegibles"] = bool(body.get("franjas_elegibles", False))
        fila["precio"] = limpio(body.get("precio"), 40)
        fila["duracion"] = limpio(body.get("duracion"), 40)
        fila["lugar"] = limpio(body.get("lugar"), 120)
        # Vigencia: pasada esta fecha la temporada se archiva sola y deja el
        # grid principal (sigue visible en /pasadas.html).
        fila["hasta"] = limpio(body.get("hasta"), 10)
        try:
            datos.guarda("Actividades", fila)
            resultado = {"ok": True, "uuid": fila["uuid"]}
            # Con calendario y fechas ya se pueden echar las clases al
            # calendario: crear la actividad y tener que proyectarla aparte
            # sería dejarla a medias.
            if fila.get("horario"):
                try:
                    logica.sincroniza_matriz(fila)
                    nuevas = logica.proyecta_actividad(fila, _titulo_de(fila))
                    for i in range(0, len(nuevas), 50):
                        datos.guarda_varios("Agenda", nuevas[i:i + 50])
                    resultado["clases_creadas"] = len(nuevas)
                except Exception as e:
                    resultado["aviso"] = f"la actividad se creó, pero no se pudieron proyectar las clases: {e}"
            dispara_rebuild()
            return 200, resultado
        except Exception as e:
            return 502, {"error": f"no se pudo crear: {e}"}

    if req.metodo == "PATCH":
        body = req.body
        if not body.get("Id"):
            return 422, {"error": "falta Id"}
        fila = {"Id": body["Id"]}
        for c in ("servicio_uuid", "estado", "periodo", "franjas", "precio",
                  "duracion", "lugar", "hasta", "desde", "motivo"):
            if c in body:
                fila[c] = limpio(body[c], 500)
        if "horario" in body:
            fila["horario"] = limpio(body["horario"], 4000)
        for c in ("umbral", "plazas"):
            if c in body and body[c] not in (None, ""):
                try:
                    fila[c] = int(body[c])
                except Exception:
                    pass
        for c in ("visible", "mostrar_contador", "franjas_elegibles"):
            if c in body:
                fila[c] = bool(body[c])
        # Tocar el calendario o las fechas obliga a rehacer lo que queda por
        # dar: de nada sirve guardar "los martes a las 19" si la agenda sigue
        # con los lunes. Se reprograma solo lo futuro; lo impartido es historia.
        reprograma = any(c in body for c in ("horario", "desde", "hasta"))
        try:
            datos.actualiza("Actividades", fila)
            resultado = {"ok": True}
            if reprograma:
                resultado.update(_reprograma(body["Id"]))
            dispara_rebuild()
            return 200, resultado
        except Exception as e:
            return 502, {"error": f"no se pudo guardar: {e}"}

    if req.metodo == "DELETE":
        return _borrar("Actividades", req.body or {})

    return None


def _actividad_por_id(rid):
    for a in datos.lee("Actividades"):
        if str(a.get("Id")) == str(rid):
            return a
    return None


def _titulo_de(actividad):
    """El nombre que se ve en la agenda es el del servicio."""
    serv = datos.servicios_por_uuid().get(actividad.get("servicio_uuid") or "", {})
    return serv.get("titulo_es") or "(clase)"


def _reprograma(rid):
    """Rehace la matriz y las clases futuras de una actividad."""
    act = _actividad_por_id(rid)
    if not act:
        return {}
    try:
        logica.sincroniza_matriz(act)
        borradas, creadas = logica.reprograma_actividad(act, _titulo_de(act))
        return {"reprogramado": {"borradas": borradas, "creadas": creadas}}
    except Exception as e:
        return {"aviso_reprogramacion": f"no se pudieron rehacer las clases: {e}"}


# --- Acciones sobre una actividad entera -----------------------------------
#
# Suspender, reanudar, cancelar o trasladar se deciden sobre la actividad,
# pero quien lo acusa es cada una de sus clases pendientes. El motivo se
# guarda en las dos partes: en la actividad, para saber por qué está así; y
# en cada clase, para que aparezca en la agenda y en la estadística.

_ACCIONES = ("suspender", "reanudar", "cancelar", "trasladar")


def _accion(body):
    accion = (body.get("accion") or "").strip()
    if accion not in _ACCIONES:
        return 422, {"error": "acción no reconocida"}
    if not body.get("Id"):
        return 422, {"error": "falta Id"}
    motivo = limpio(body.get("motivo"), 100)
    motivo_texto = limpio(body.get("motivo_texto"), 1000)
    # Julia decide si el motivo se cuenta en la web o se queda en el panel.
    publico = bool(body.get("motivo_publico"))
    if accion in ("suspender", "cancelar", "trasladar") and not motivo:
        return 422, {"error": "hay que indicar el motivo"}

    act = _actividad_por_id(body["Id"])
    if not act:
        return 404, {"error": "actividad no encontrada"}

    try:
        if accion == "reanudar":
            # Vuelve a estar en marcha y se rehacen las clases que quedaban.
            datos.actualiza("Actividades", {"Id": body["Id"],
                                            "estado": "en_curso", "motivo": ""})
            act["estado"] = "en_curso"
            borradas, creadas = logica.reprograma_actividad(act, _titulo_de(act))
            dispara_rebuild()
            return 200, {"ok": True, "accion": accion,
                         "reprogramado": {"borradas": borradas, "creadas": creadas}}

        if accion == "trasladar":
            # Trasladar es cambiar el calendario: lo hace el PATCH normal con
            # el horario nuevo. Aquí solo se deja constancia del porqué en las
            # clases que se van a rehacer.
            n = logica.aplica_a_futuras(act.get("uuid") or "", {
                "motivo": motivo, "motivo_texto": motivo_texto,
                "motivo_publico": publico})
            dispara_rebuild()
            return 200, {"ok": True, "accion": accion, "clases": n}

        estado_act = "suspendida" if accion == "suspender" else "finalizada"
        estado_clase = "aplazada" if accion == "suspender" else "cancelada"
        datos.actualiza("Actividades", {
            "Id": body["Id"], "estado": estado_act,
            "motivo": (motivo + (" · " + motivo_texto if motivo_texto else "")),
            "motivo_publico": publico,
        })
        n = logica.aplica_a_futuras(act.get("uuid") or "", {
            "estado": estado_clase, "motivo": motivo,
            "motivo_texto": motivo_texto, "motivo_publico": publico,
            "avisar_alumnos": bool(body.get("avisar_alumnos")),
        })
        dispara_rebuild()
        return 200, {"ok": True, "accion": accion, "clases": n}
    except Exception as e:
        return 502, {"error": f"no se pudo completar la acción: {e}"}


def handle(req):
    if req.path == RUTA_ACCION and req.metodo == "POST":
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _accion(req.body or {})
    if req.path == RUTA_SERVICIOS:
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _servicios_handle(req)
    if req.path == RUTA_ACTIVIDADES:
        if not req.usuario:
            return 401, {"error": "no autenticado"}
        return _actividades_handle(req)
    return None
