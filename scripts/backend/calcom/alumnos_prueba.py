"""
backend.calcom.alumnos_prueba — siembra reservas de prueba en varias clases.

Sirve para probar de verdad las listas de asistentes, los documentos
imprimibles y los avisos de aforo, que con la agenda vacía no se pueden
mirar.

Reserva a través del MISMO camino que un alumno real (POST /reservar del
backend), no por debajo: así se ejercita el circuito entero —motor de
Cal.diy, copia en NocoDB, teléfono— y lo que se ve luego en el panel es
lo que se verá en producción.

Los correos usan el dominio reservado .invalid, que por norma no existe
ni puede existir: ninguna confirmación llegará a una persona real.

    cd /opt/docker/apps/juliamoreno/scripts
    python3 -m backend.calcom.alumnos_prueba                 # simular
    python3 -m backend.calcom.alumnos_prueba --crear         # sembrar
    python3 -m backend.calcom.alumnos_prueba --limpiar       # borrar
    ...--sesiones 3 --min 2 --max 6   (cuántas sesiones y cuánta gente)

--limpiar cancela SOLO lo sembrado aquí, reconocido por el dominio del
correo: las reservas reales no se tocan.
"""
import os
import random
import sys
import json
import urllib.request
import urllib.error

from . import cliente

DOMINIO = "alumno-prueba.invalid"
API_PUBLICA = os.environ.get("API_PUBLICA", "https://api.juliamoreno.yoga")

NOMBRES = [
    "Ana Belén Ruiz", "Carmen Pérez Soto", "Lucía Ortega", "Marta Gil Navarro",
    "Rocío Cabrera", "Elena Vidal", "Pilar Márquez", "Inés Domínguez",
    "Javier Molina", "Antonio Reyes", "Miguel Ángel Serrano", "David Cortés",
    "Paula Herrera", "Sofía Bermúdez", "Teresa Aguilar", "Nuria Castaño",
    "Beatriz Lozano", "Clara Espejo", "Manuel Fuentes", "Rafael Ibáñez",
]


def _telefono(i):
    # Rango 600-699 pero con final fijo y previsible, para que se note a
    # simple vista que son inventados.
    return f"6{random.randint(10, 99)} {random.randint(100, 999)} 0{i:02d}"


def _correo(nombre, i):
    base = (nombre.lower()
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
            .replace(" ", "."))
    return f"{base}.{i}@{DOMINIO}"


def _post(ruta, cuerpo):
    req = urllib.request.Request(
        f"{API_PUBLICA.rstrip('/')}{ruta}",
        data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _clases():
    """Clases con aforo, tal como las ve el público."""
    salida = []
    for t in cliente.event_types().get("data", []):
        salida.append((t.get("id"), t.get("title")))
    return salida


def sembrar(crear, n_sesiones, minimo, maximo):
    random.seed(20260718)  # reproducible: dos pasadas dan lo mismo
    total = 0
    for cal_id, titulo in _clases():
        try:
            import datetime
            hoy = datetime.date.today()
            fin = hoy + datetime.timedelta(days=21)
            aforo = cliente.aforo_por_hueco(cal_id, hoy.isoformat(),
                                            fin.isoformat())
        except Exception as e:
            print(f"  {titulo}: no se pudo leer el aforo ({e})")
            continue
        if not aforo:
            print(f"  {titulo}: sin huecos en las próximas 3 semanas")
            continue

        huecos = sorted(aforo.items())[:n_sesiones]
        print(f"\n{titulo} (clase {cal_id})")
        for inicio, datos_hueco in huecos:
            libres = datos_hueco.get("libres") or 0
            cuantos = min(random.randint(minimo, maximo), libres)
            if cuantos <= 0:
                print(f"  {inicio}: sin plazas libres, se salta")
                continue
            elegidos = random.sample(NOMBRES, cuantos)
            print(f"  {inicio}: {cuantos} alumno(s)")
            for i, nombre in enumerate(elegidos):
                if not crear:
                    continue
                try:
                    r = _post("/reservar", {
                        "event_type_id": cal_id,
                        "inicio": inicio,
                        "nombre": nombre,
                        "email": _correo(nombre, i),
                        "telefono": _telefono(i),
                    })
                    if r.get("ok"):
                        total += 1
                    else:
                        print(f"      {nombre}: {r.get('error')}")
                except urllib.error.HTTPError as e:
                    detalle = e.read().decode()[:120]
                    print(f"      {nombre}: HTTP {e.code} {detalle}")
                except Exception as e:
                    print(f"      {nombre}: {e}")
    return total


def limpiar():
    """Cancela solo las reservas sembradas (por el dominio del correo)."""
    n = 0
    for b in cliente.bookings().get("data", []):
        if b.get("status") != "accepted":
            continue
        correos = [(a.get("email") or "") for a in b.get("attendees", [])]
        if not any(c.endswith("@" + DOMINIO) for c in correos):
            continue
        try:
            cliente.cancelar_reserva(b["uid"])
            n += 1
        except Exception as e:
            print(f"  no se pudo cancelar {b.get('uid')}: {e}")
    return n


def main():
    if "--limpiar" in sys.argv:
        n = limpiar()
        print(f"{n} reserva(s) de prueba canceladas. "
              f"Las filas de la tabla Reservas de NocoDB se borran a mano.")
        return 0

    crear = "--crear" in sys.argv
    def _num(bandera, defecto):
        if bandera in sys.argv:
            i = sys.argv.index(bandera)
            if i + 1 < len(sys.argv):
                try:
                    return int(sys.argv[i + 1])
                except ValueError:
                    pass
        return defecto

    n_ses = _num("--sesiones", 3)
    mini = _num("--min", 2)
    maxi = _num("--max", 6)

    print("MODO: " + ("SEMBRAR (se crearán reservas reales en el motor)"
                      if crear else "SIMULACIÓN (no se toca nada)"))
    total = sembrar(crear, n_ses, mini, maxi)
    if crear:
        print(f"\n{total} reserva(s) creadas. Mírelas en el panel → Agenda → "
              f"clic derecho en una clase → Sacar lista de alumnos.")
        print(f"Para deshacerlo: python3 -m backend.calcom.alumnos_prueba "
              f"--limpiar")
    else:
        print("\nSimulación. Repita con --crear para sembrarlas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
