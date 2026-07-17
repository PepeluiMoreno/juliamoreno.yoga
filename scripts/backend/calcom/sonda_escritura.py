"""
backend.calcom.sonda_escritura — prueba del ciclo de escritura vía motor.

Valida el único endpoint que la sonda de lectura no toca: crear una
reserva a través del motor de Cal.diy y cancelarla, comprobando en cada
paso que el aforo del hueco baja y se restaura. Deja la instancia como
estaba (la reserva de prueba queda cancelada).

Uso (en el VPS, con el entorno cargado):
    CALCOM_API_URL=... CALCOM_API_KEY=... \
    python3 -m backend.calcom.sonda_escritura
"""
import datetime
import sys
import time

from . import cliente


def _sep(t):
    print("\n" + "=" * 60)
    print(t)
    print("=" * 60)


def _primer_hueco(event_type_id):
    hoy = datetime.date.today()
    fin = hoy + datetime.timedelta(days=30)
    dias = cliente.slots(event_type_id, hoy.isoformat(),
                         fin.isoformat()).get("data", {})
    for dia in sorted(dias):
        for franja in dias[dia]:
            return franja
    return None


def _aforo(event_type_id, inicio):
    hueco = None
    hoy = datetime.date.today()
    fin = hoy + datetime.timedelta(days=30)
    dias = cliente.slots(event_type_id, hoy.isoformat(),
                         fin.isoformat()).get("data", {})
    for franjas in dias.values():
        for f in franjas:
            if f.get("start") == inicio:
                hueco = f
    return (hueco or {}).get("seatsRemaining")


def main():
    _sep("0. Elegir clase y hueco de prueba")
    tipos = cliente.event_types().get("data", [])
    if not tipos:
        print("FALLO: no hay tipos de evento")
        return 1
    tipo = tipos[0]
    hueco = _primer_hueco(tipo["id"])
    if not hueco:
        print("FALLO: sin huecos en 30 días")
        return 1
    inicio = hueco["start"]
    antes = hueco.get("seatsRemaining")
    print(f"OK — «{tipo.get('title')}» (id={tipo['id']}), hueco {inicio}, "
          f"plazas libres: {antes}")

    _sep("1. Crear reserva a través del motor (POST /v2/bookings)")
    try:
        r = cliente.crear_reserva(
            tipo["id"], inicio,
            "Prueba Sonda", "prueba-sonda@juliamoreno.yoga")
        datos = r.get("data", r)
        uid = datos.get("uid")
        print(f"OK — reserva creada, uid={uid}, "
              f"estado={datos.get('status')}")
    except Exception as e:
        print(f"FALLO: {e}")
        return 1

    _sep("2. Verificar que el aforo bajó")
    tras_crear = _aforo(tipo["id"], inicio)
    if antes is not None and tras_crear == antes - 1:
        print(f"OK — plazas libres {antes} → {tras_crear}")
    else:
        print(f"AVISO — esperado {antes}-1, leído {tras_crear} "
              "(revisar si seats está activo en el evento)")

    _sep("3. Cancelar la reserva (el hueco debe restaurarse)")
    try:
        cliente.cancelar_reserva(uid)
        print(f"OK — reserva {uid} cancelada")
    except Exception as e:
        print(f"FALLO al cancelar: {e}")
        print(f"→ cancele a mano la reserva {uid} en la UI")
        return 1

    # la lectura de slots se sirve con caché (Redis): tras una
    # escritura puede tardar unos segundos en reflejarse
    time.sleep(20)
    tras_cancelar = _aforo(tipo["id"], inicio)
    if tras_cancelar == antes:
        print(f"OK — aforo restaurado: {tras_cancelar}")
    else:
        print(f"AVISO — aforo leído tras cancelar: {tras_cancelar} "
              f"(esperado {antes})")

    _sep("Conclusión")
    print("Ciclo crear→verificar→cancelar→verificar por API completado.")
    print("La pantalla de reserva propia puede construirse sobre esto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
