#!/usr/bin/env python3
"""
build-web.py — regenera las secciones de horarios y precios de la web
en los cuatro idiomas a partir de data/contenido.json.

Fuente de datos:
  - Por defecto lee data/contenido.json (el fichero versionado).
  - Si se define NOCODB_URL + NOCODB_TOKEN, lee de NocoDB (lo que Julia
    edita) y vuelca sobre contenido.json antes de generar, de modo que
    el repo queda siempre como copia de lo que hay en NocoDB.

Uso:
  python3 scripts/build-web.py            # genera desde el JSON
  python3 scripts/build-web.py --from-nocodb   # sincroniza desde NocoDB y genera

Sólo toca el bloque entre <!-- CONTENIDO:INICIO --> y <!-- CONTENIDO:FIN -->
de cada HTML; el resto de la página no se modifica.
"""
import json, os, re, sys, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
JSON = RAIZ / "data" / "contenido.json"
PAGS = {"es": RAIZ/"sitio"/"index.html", "en": RAIZ/"sitio"/"en"/"index.html",
        "fr": RAIZ/"sitio"/"fr"/"index.html", "de": RAIZ/"sitio"/"de"/"index.html"}
INI, FIN = "<!-- CONTENIDO:INICIO", "<!-- CONTENIDO:FIN -->"


def esc(t):
    return t  # las etiquetas ya vienen limpias; permitimos <strong> en intro/nota


def seccion(data, idioma):
    h = data["horarios"]; p = data["precios"]
    th_l, th_c = h["cabecera"][idioma].split("|")
    out = []
    out.append(f'    <p style="margin-bottom:1.4rem">{h["intro"][idioma]}</p>')
    out.append('    <table>')
    out.append(f'      <thead><tr><th>{th_l}</th><th>{th_c}</th></tr></thead>')
    out.append('      <tbody>')
    for ln in h["lineas"]:
        if not ln.get("visible", True):
            continue
        out.append(f'        <tr><td>{ln["lugar"][idioma]}</td><td>{ln["clases"][idioma]}</td></tr>')
    out.append('      </tbody>')
    out.append('    </table>')
    out.append(f'    <p style="margin-top:1.4rem">{h["nota"][idioma]}</p>')
    # Precios
    if p["trial"].get("visible", True):
        out.append(f'    <p style="margin-top:1.8rem"><strong>{p["trial"]["label"][idioma]}.</strong></p>')
    pc_m, pc_p = p["cabecera"][idioma].split("|")
    out.append('    <table>')
    out.append(f'      <thead><tr><th>{pc_m}</th><th>{pc_p}</th></tr></thead>')
    out.append('      <tbody>')
    for ln in p["lineas"]:
        if not ln.get("visible", True):
            continue
        val = ln["valor"].strip()
        # formatea el precio con € (soporta "10 / 35")
        if "/" in val:
            partes = [x.strip() for x in val.split("/")]
            precio = " / ".join(f"{x} €" for x in partes)
        else:
            precio = f"{val} €"
        out.append(f'        <tr><td>{ln["label"][idioma]}</td><td>{precio}</td></tr>')
    out.append('      </tbody>')
    out.append('    </table>')
    out.append(f'    <p style="margin-top:1.2rem;font-size:.92rem;color:#5c6a75">{p["nota"][idioma]}</p>')
    return "\n".join(out)


def aplica(idioma, ruta, data):
    html = ruta.read_text(encoding="utf-8")
    ini = html.index(INI)
    ini_fin = html.index("-->", ini) + 3
    fin = html.index(FIN)
    nuevo = (html[:ini_fin] + "\n" + seccion(data, idioma) + "\n    " + html[fin:])
    ruta.write_text(nuevo, encoding="utf-8")


def desde_nocodb(data):
    """Vuelca a data los valores editables leidos de NocoDB, si esta configurado."""
    import urllib.request
    base = os.environ["NOCODB_URL"].rstrip("/")
    tok = os.environ["NOCODB_TOKEN"]
    def get(tabla):
        req = urllib.request.Request(f"{base}/{tabla}?limit=200",
                                     headers={"xc-token": tok})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r).get("list", [])
    # Precios: filas con id + valor + visible
    for fila in get(os.environ.get("NOCODB_TBL_PRECIOS", "Precios")):
        for ln in data["precios"]["lineas"]:
            if ln["id"] == fila.get("id"):
                ln["valor"] = str(fila.get("valor", ln["valor"]))
                ln["visible"] = bool(fila.get("visible", True))
    # Horarios: filas con id + dia/hora/clases + visible (solo valores, no idiomas)
    for fila in get(os.environ.get("NOCODB_TBL_HORARIOS", "Horarios")):
        for ln in data["horarios"]["lineas"]:
            if ln["id"] == fila.get("id"):
                ln["visible"] = bool(fila.get("visible", True))
    JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    data = json.loads(JSON.read_text(encoding="utf-8"))
    if "--from-nocodb" in sys.argv:
        if "NOCODB_URL" in os.environ and "NOCODB_TOKEN" in os.environ:
            desde_nocodb(data)
        else:
            print("NOCODB_URL/NOCODB_TOKEN no definidos; genero desde el JSON local.")
    for idioma, ruta in PAGS.items():
        aplica(idioma, ruta, data)
        print(f"generado {ruta.relative_to(RAIZ)}")
    print("OK")


if __name__ == "__main__":
    main()
