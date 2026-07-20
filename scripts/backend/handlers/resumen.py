"""
backend.handlers.resumen — ruta /admin/api/resumen (GET).

Alimenta el Panel de control, que es lo primero que Julia ve al entrar. No
es un escaparate de contadores: responde a cuatro preguntas concretas.

  1. ¿Cómo va ESTA SEMANA? Las clases de lunes a domingo con su ocupación,
     para saber de un vistazo qué hay hoy y qué está medio vacío.
  2. ¿Qué estoy ofreciendo? Los servicios de la cartera, y aparte las
     actividades en curso y las que están en preparación.
  3. ¿Cómo va cada actividad? Clases programadas, celebradas y su
     porcentaje, más las reservas y lo facturado.
  4. ¿Cuánto de lo programado se cumple? Cancelaciones del ejercicio,
     repartidas por motivo y separando las de Julia de las del alumno.

De dónde sale cada dato: la agenda, las plazas y las reservas se leen de
NocoDB. Cal.diy es la fuente de verdad de las reservas, pero solo para las
actividades enlazadas (cal_event_type_id); mientras no lo estén, la copia
de la tabla Reservas es lo que hay, y por eso el cálculo va por aquí.
"""
import datetime

from .. import agenda as logica
from .. import datos

RUTA = "/admin/api/resumen"

# Una clase "se celebró" si ya pasó y no se anuló. Aplazada no cuenta: esa
# clase no se dio ese día (se cuenta el día al que se movió).
_NO_CELEBRADAS = ("cancelada", "aplazada")


def _fecha(r):
    try:
        return datetime.date.fromisoformat(str(r.get("fecha") or "")[:10])
    except Exception:
        return None


def _semana(hoy):
    """Lunes y domingo de la semana en curso."""
    lunes = hoy - datetime.timedelta(days=hoy.weekday())
    return lunes, lunes + datetime.timedelta(days=6)


def _reservas_por_dia_hora(reservas):
    """{(fecha, HH:MM): [nombres]} de las reservas aceptadas.

    El `inicio` de la copia en NocoDB llega como ISO ('2026-07-22T19:00:00Z'),
    así que se parte por la T sin convertir zonas: la hora que se guardó es la
    que Julia ve en su agenda.
    """
    idx = {}
    for r in reservas:
        if (r.get("estado") or "") != "accepted":
            continue
        ini = str(r.get("inicio") or "")
        if "T" not in ini:
            continue
        dia, _, hora = ini.partition("T")
        idx.setdefault((dia[:10], hora[:5]), []).append(r.get("nombre") or "")
    return idx


def _bloque_semana(agenda, plazas_de, reservas_idx, hoy):
    """Las clases de la semana en curso, con ocupación por clase."""
    lunes, domingo = _semana(hoy)
    fuera = []
    for r in agenda:
        f = _fecha(r)
        if not f or not (lunes <= f <= domingo):
            continue
        hora = (r.get("hora_inicio") or "")[:5]
        ocupadas = len(reservas_idx.get((f.isoformat(), hora), []))
        plazas = plazas_de.get(r.get("actividad_id") or "")
        fuera.append({
            "fecha": f.isoformat(),
            "dia_semana": f.weekday(),
            "hora": hora,
            "titulo": r.get("titulo") or "(clase)",
            "lugar": r.get("lugar") or "",
            "duracion_min": r.get("duracion_min") or 0,
            "estado": r.get("estado") or "programada",
            "motivo": r.get("motivo") or "",
            "plazas": plazas,
            "ocupadas": ocupadas,
            "libres": (plazas - ocupadas) if isinstance(plazas, int) else None,
            "pasada": f < hoy,
            "hoy": f == hoy,
        })
    fuera.sort(key=lambda s: (s["fecha"], s["hora"]))
    return fuera


def _bloque_actividades(acts, servicios, agenda, reservas_idx, hoy):
    """Por cada actividad: cumplimiento, reservas y facturación estimada."""
    por_act = {}
    for r in agenda:
        aid = r.get("actividad_id") or ""
        if aid:
            por_act.setdefault(aid, []).append(r)

    fuera = []
    for a in acts:
        uuid = a.get("uuid") or ""
        serv = servicios.get(a.get("servicio_uuid") or "", {})
        clases = por_act.get(uuid, [])
        pasadas = [c for c in clases if (_fecha(c) or hoy) < hoy]
        celebradas = [c for c in pasadas
                      if (c.get("estado") or "") not in _NO_CELEBRADAS]
        canceladas = [c for c in clases if (c.get("estado") or "") == "cancelada"]

        # Reservas y facturación: se cuentan sobre las clases que se dieron,
        # a la tarifa por hora del servicio (el precio de la actividad es
        # texto libre —"12 €"— y no sirve para sumar).
        try:
            tarifa = float(a.get("tarifa_hora") or serv.get("tarifa_hora") or 0)
        except Exception:
            tarifa = 0.0
        # Las reservas se cuentan sobre TODAS las clases de la actividad —las
        # dadas y las que vienen—, porque una plaza reservada para el jueves ya
        # es alumnado apuntado. Lo facturado, en cambio, solo cuenta lo que se
        # dio: cobrar por adelantado una clase que aún no ha ocurrido sería
        # inventarse el ingreso.
        def _apuntados(clase):
            f = _fecha(clase)
            if not f:
                return 0
            return len(reservas_idx.get(
                (f.isoformat(), (clase.get("hora_inicio") or "")[:5]), []))

        reservas = sum(_apuntados(c) for c in clases
                       if (c.get("estado") or "") != "cancelada")
        facturado = 0.0
        for c in celebradas:
            horas = (int(c.get("duracion_min") or 0)) / 60.0
            facturado += _apuntados(c) * horas * tarifa

        fuera.append({
            "uuid": uuid,
            "servicio_uuid": a.get("servicio_uuid"),
            "titulo": serv.get("titulo_es") or "(sin título)",
            "periodo": a.get("periodo") or "",
            "estado": (a.get("estado") or "propuesta").strip(),
            "lugar": a.get("lugar") or "",
            "programadas": len(clases),
            "pasadas": len(pasadas),
            "celebradas": len(celebradas),
            "canceladas": len(canceladas),
            "cumplimiento": (round(100 * len(celebradas) / len(pasadas))
                             if pasadas else None),
            "reservas": reservas,
            "facturado": round(facturado, 2),
            "tarifa_hora": tarifa or None,
        })
    fuera.sort(key=lambda x: (x["estado"] != "en_curso", x["titulo"]))
    return fuera


def _bloque_cancelaciones(agenda, reservas, hoy):
    """Cancelaciones del ejercicio en curso (año natural), por motivo.

    Se separan las bajas de Julia —una clase entera que no se da— de las de
    los alumnos, que son reservas sueltas: no son lo mismo ni se arreglan
    igual, y sumarlas juntas escondería cuál de las dos cosas está pasando.
    """
    desde = datetime.date(hoy.year, 1, 1).isoformat()

    del_ejercicio = [r for r in agenda
                     if str(r.get("fecha") or "")[:10] >= desde]
    canceladas = [r for r in del_ejercicio
                  if (r.get("estado") or "") == "cancelada"]
    aplazadas = [r for r in del_ejercicio
                 if (r.get("estado") or "") == "aplazada"]

    motivos = {}
    for r in canceladas + aplazadas:
        m = (r.get("motivo") or "sin motivo").strip() or "sin motivo"
        motivos[m] = motivos.get(m, 0) + 1
    total_inc = len(canceladas) + len(aplazadas)
    por_motivo = sorted(
        ({"motivo": m, "n": n,
          "pct": round(100 * n / total_inc) if total_inc else 0}
         for m, n in motivos.items()),
        key=lambda x: -x["n"])

    bajas_alumno = sum(1 for r in reservas
                       if (r.get("estado") or "") == "cancelled")

    programadas = len(del_ejercicio)
    return {
        "desde": desde,
        "programadas": programadas,
        "canceladas": len(canceladas),
        "aplazadas": len(aplazadas),
        "bajas_alumno": bajas_alumno,
        "por_motivo": por_motivo,
        # Cuánto de lo programado se acabó dando.
        "fidelidad": (round(100 * (programadas - len(canceladas)) / programadas)
                      if programadas else None),
    }


def handle(req):
    if req.path != RUTA:
        return None
    if not req.usuario:
        return 401, {"error": "no autenticado"}
    if req.metodo != "GET":
        return None
    try:
        hoy = datetime.date.today()
        acts = datos.lee("Actividades")
        servicios_filas = datos.lee("Servicios")
        servicios = {s.get("uuid"): s for s in servicios_filas}
        agenda = datos.lee("Agenda")
        reservas = datos.lee("Reservas")
        inter = datos.lee("Interesados")

        reservas_idx = _reservas_por_dia_hora(reservas)
        plazas_de = {}
        for a in acts:
            try:
                plazas_de[a.get("uuid") or ""] = int(a.get("plazas") or 0) or None
            except Exception:
                plazas_de[a.get("uuid") or ""] = None

        # Interesados por servicio (el interés es del servicio, no del tramo).
        por_serv = {}
        for r in inter:
            s = (r.get("actividad") or "").strip()
            if s:
                por_serv[s] = por_serv.get(s, 0) + 1

        actividades = _bloque_actividades(acts, servicios, agenda,
                                          reservas_idx, hoy)
        estados = {}
        for a in acts:
            e = (a.get("estado") or "propuesta").strip()
            estados[e] = estados.get(e, 0) + 1

        en_cartera = [s for s in servicios_filas if s.get("se_sigue_ofertando")]
        cartera = sorted(
            ({"uuid": s.get("uuid"),
              "titulo": s.get("titulo_es") or "(sin título)",
              "nivel": s.get("nivel") or "",
              "tarifa_hora": s.get("tarifa_hora"),
              "interesados": por_serv.get(s.get("uuid") or "", 0),
              "programaciones": sum(1 for a in actividades
                                    if a["servicio_uuid"] == s.get("uuid"))}
             for s in en_cartera),
            key=lambda x: x["titulo"])

        return 200, {
            "ok": True,
            "hoy": hoy.isoformat(),
            "totales": {
                "servicios_ofertados": len(en_cartera),
                "ofertadas": estados.get("en_curso", 0),
                "programadas": estados.get("programada", 0),
                "en_preparacion": estados.get("propuesta", 0),
                "finalizadas": estados.get("finalizada", 0),
                "total_actividades": len(acts),
                "total_interesados": len(inter),
                "horas_mes": logica.horas_programadas_mes(),
            },
            "semana": _bloque_semana(agenda, plazas_de, reservas_idx, hoy),
            "cartera": cartera,
            "actividades": actividades,
            "en_curso": [a for a in actividades if a["estado"] == "en_curso"],
            "preparacion": sorted(
                [a for a in actividades if a["estado"] == "propuesta"],
                key=lambda x: -x["reservas"]),
            "cancelaciones": _bloque_cancelaciones(agenda, reservas, hoy),
        }
    except Exception as e:
        return 502, {"error": f"no se pudo calcular: {e}"}
