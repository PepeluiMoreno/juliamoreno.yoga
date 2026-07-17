"""
backend.calcom.sonda — prueba manual de la exploración Cal.com-centric.

Ejecuta las tres lecturas que deciden la viabilidad y reporta en claro
qué funciona y qué no, sin tocar nada. No escribe en ningún sitio.

Uso (en el VPS, con el entorno cargado):
    CALCOM_API_URL=... CALCOM_API_KEY=... python3 -m backend.calcom.sonda

Salida esperada si Cal.com puede ser la base del calendario:
  - lista de tipos de evento (las clases)
  - franjas reservables de uno de ellos para el próximo mes
  - reservas existentes
Si algo falla, imprime el motivo (auth, versión, endpoint) para saber
qué ajustar.
"""
import datetime
import json
import sys

from . import cliente


def _sep(t):
    print("\n" + "=" * 60)
    print(t)
    print("=" * 60)


def main():
    _sep("1. Tipos de evento (las 'clases' en Cal.com)")
    try:
        et = cliente.event_types()
        datos = et.get("data", et)
        print(f"OK — {len(datos) if isinstance(datos, list) else '?'} tipo(s) de evento")
        primero = None
        if isinstance(datos, list) and datos:
            for e in datos[:10]:
                eid = e.get("id")
                print(f"   · id={eid}  «{e.get('title','?')}»  "
                      f"seats={e.get('seatsPerTimeSlot')}  "
                      f"recurring={bool(e.get('recurringEvent'))}")
            primero = datos[0].get("id")
    except Exception as e:
        print(f"FALLO: {e}")
        print("→ revisar CALCOM_API_URL / CALCOM_API_KEY / versión de API")
        return 1

    _sep("2. Franjas reservables (alimentaría la disponibilidad de la web)")
    if primero:
        hoy = datetime.date.today()
        fin = hoy + datetime.timedelta(days=30)
        try:
            s = cliente.slots(primero, hoy.isoformat(), fin.isoformat())
            datos = s.get("data", s)
            n = len(datos) if hasattr(datos, "__len__") else "?"
            print(f"OK — franjas devueltas para el tipo {primero} "
                  f"({hoy} → {fin}): {n} clave(s)/día(s)")
            print("   muestra:", json.dumps(datos)[:400])
        except Exception as e:
            print(f"FALLO: {e}")
            print("→ el endpoint de slots o sus parámetros difieren en esta versión")
    else:
        print("(sin tipo de evento con el que probar)")

    _sep("3. Reservas existentes (lista de alumnos por clase)")
    try:
        b = cliente.bookings()
        datos = b.get("data", b)
        n = len(datos) if hasattr(datos, "__len__") else "?"
        print(f"OK — {n} reserva(s) accesibles")
    except Exception as e:
        print(f"FALLO: {e}")

    _sep("Conclusión")
    print("Si los 3 bloques dan OK, Cal.com puede alimentar la web y el")
    print("panel: la variante Cal.com-centric es viable de verdad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
