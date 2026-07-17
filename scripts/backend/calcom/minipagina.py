"""
backend.calcom.minipagina — genera la mini-página de disponibilidad.

Valida el último punto de la exploración: que la disponibilidad leída
de Cal.diy se puede pintar con el estilo de la web (Marcellus/Mulish,
azul mar, crema), mostrando solo aforo — nunca nombres.

Lee los tipos de evento y sus franjas de los próximos días por la API
v2 y escribe un HTML estático autocontenido. No toca nada: solo lee y
escribe el fichero de salida.

Uso (en el VPS):
    CALCOM_API_URL=... CALCOM_API_KEY=... \
    python3 -m backend.calcom.minipagina [salida.html] [dias]

Por defecto escribe /tmp/disponibilidad.html con 14 días vista.
"""
import datetime
import html
import sys
from zoneinfo import ZoneInfo

from . import cliente

TZ = ZoneInfo("Europe/Madrid")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes",
        "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre",
         "diciembre"]

PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Disponibilidad · Julia Moreno · Yoga</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=Mulish:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --mar: #1d5975; --tinta: #153f54; --crema: #fcfbf8;
    --linea: #e5e0d8; --lleno: #b9b2a6;
  }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{
    background: var(--crema); color: var(--tinta);
    font-family: 'Mulish', sans-serif; padding: 2rem 1rem 4rem;
  }}
  .marco {{ max-width: 860px; margin: 0 auto; }}
  h1 {{
    font-family: 'Marcellus', serif; font-weight: 400;
    color: var(--mar); font-size: 1.9rem; margin-bottom: .25rem;
  }}
  .lema {{ color: var(--tinta); opacity: .7; margin-bottom: 2rem; }}
  h2 {{
    font-family: 'Marcellus', serif; font-weight: 400;
    color: var(--tinta); font-size: 1.35rem;
    border-bottom: 1px solid var(--linea);
    padding-bottom: .4rem; margin: 2rem 0 1rem;
  }}
  .dia {{ display: flex; gap: 1rem; padding: .55rem 0;
         border-bottom: 1px solid var(--linea); align-items: baseline; }}
  .fecha {{ flex: 0 0 11.5rem; font-weight: 600; }}
  .franjas {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
  .franja {{
    border: 1px solid var(--mar); color: var(--mar);
    border-radius: 999px; padding: .25rem .8rem; font-size: .92rem;
    white-space: nowrap;
  }}
  .franja .plazas {{ opacity: .75; font-size: .85em; }}
  .franja.llena {{
    border-color: var(--lleno); color: var(--lleno);
    text-decoration: line-through;
  }}
  .vacio {{ opacity: .6; font-style: italic; }}
  footer {{ margin-top: 3rem; font-size: .8rem; opacity: .55; }}
  @media (max-width: 560px) {{
    .dia {{ flex-direction: column; gap: .35rem; }}
    .fecha {{ flex: none; }}
  }}
</style>
</head>
<body>
<div class="marco">
  <h1>Julia Moreno · Yoga</h1>
  <p class="lema">Disponibilidad de clases — {rango}</p>
  {cuerpo}
  <footer>Actualizado el {actualizado}. Las plazas se muestran de forma
  anónima; la reserva se completa en la página de reservas.</footer>
</div>
</body>
</html>
"""


def _fecha_larga(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def _hora_local(iso_utc):
    dt = datetime.datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    return dt.astimezone(TZ).strftime("%H:%M")


def _chip(inicio_utc, aforo):
    """aforo: dict {'total','ocupadas','libres'} de cliente.aforo_por_hueco,
    que ya trae el número real (slots reporta seatsRemaining sin
    actualizar; ver cliente.aforo_por_hueco)."""
    hora = _hora_local(inicio_utc)
    total = aforo.get("total")
    libres = aforo.get("libres")
    if total is None:
        return f'<span class="franja">{hora}</span>'
    if not libres:
        return (f'<span class="franja llena">{hora} '
                f'<span class="plazas">completo</span></span>')
    return (f'<span class="franja">{hora} '
            f'<span class="plazas">{libres} de {total} plazas</span></span>')


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "/tmp/disponibilidad.html"
    dias = int(sys.argv[2]) if len(sys.argv) > 2 else 14

    hoy = datetime.date.today()
    fin = hoy + datetime.timedelta(days=dias)

    tipos = cliente.event_types().get("data", [])
    if not isinstance(tipos, list) or not tipos:
        print("Sin tipos de evento en Cal.diy: nada que pintar.")
        return 1

    secciones = []
    for t in tipos:
        titulo = html.escape(t.get("title", "Clase"))
        aforos = cliente.aforo_por_hueco(
            t["id"], hoy.isoformat(), fin.isoformat())
        por_dia = {}
        for ini in sorted(aforos):
            por_dia.setdefault(ini[:10], []).append(ini)
        filas = []
        for dia in sorted(por_dia):
            chips = "".join(_chip(ini, aforos[ini]) for ini in por_dia[dia])
            filas.append(f'<div class="dia"><span class="fecha">'
                         f'{_fecha_larga(dia)}</span>'
                         f'<span class="franjas">{chips}</span></div>')
        cuerpo = ("".join(filas) if filas
                  else '<p class="vacio">Sin huecos en este periodo.</p>')
        secciones.append(f"<h2>{titulo}</h2>{cuerpo}")

    documento = PLANTILLA.format(
        rango=f"del {hoy.day} de {MESES[hoy.month - 1]} "
              f"al {fin.day} de {MESES[fin.month - 1]}",
        cuerpo="".join(secciones),
        actualizado=datetime.datetime.now(TZ).strftime("%d/%m/%Y %H:%M"),
    )
    with open(salida, "w", encoding="utf-8") as f:
        f.write(documento)
    print(f"Escrito {salida} ({len(secciones)} clase(s), {dias} días vista).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
