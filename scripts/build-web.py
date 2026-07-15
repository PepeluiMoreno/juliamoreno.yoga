#!/usr/bin/env python3
"""
build-web.py — regenera las secciones de horarios y precios de la web
en los cuatro idiomas a partir de data/contenido.json.

Fuente de datos:
  - NocoDB es la FUENTE DE VERDAD: si NOCODB_URL + NOCODB_TOKEN están
    definidos, se lee de NocoDB en cada build y se vuelca sobre
    data/contenido.json (que queda como caché / último-conocido y como
    fallback si NocoDB no responde).
  - data/contenido.json ya NO se edita a mano para precios/horarios/
    actividades (eso se hace en NocoDB). Sí conserva las etiquetas
    multiidioma fijas de la interfaz.

Uso:
  python3 scripts/build-web.py             # lee NocoDB (por defecto) y genera
  python3 scripts/build-web.py --solo-json # ignora NocoDB (pruebas/fallback)

Sólo toca el bloque entre <!-- CONTENIDO:INICIO --> y <!-- CONTENIDO:FIN -->
de cada HTML; el resto de la página no se modifica.
"""
import json, os, re, sys, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
JSON = RAIZ / "data" / "contenido.json"
PAGS = {"es": RAIZ/"sitio"/"index.html", "en": RAIZ/"sitio"/"en"/"index.html",
        "fr": RAIZ/"sitio"/"fr"/"index.html", "de": RAIZ/"sitio"/"de"/"index.html"}
INI, FIN = "<!-- CONTENIDO:INICIO", "<!-- CONTENIDO:FIN -->"
INI_ACT, FIN_ACT = "<!-- ACTIVIDADES:INICIO", "<!-- ACTIVIDADES:FIN -->"

MESES = {
    "es": ["", "enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"],
    "en": ["", "January","February","March","April","May","June","July","August","September","October","November","December"],
    "fr": ["", "janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"],
    "de": ["", "Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"],
}


def fecha_legible(iso, idioma):
    """2026-09-20 -> '20 de septiembre de 2026' / '20 September 2026' etc."""
    if not iso:
        return ""
    try:
        a, m, d = iso.split("-")
        mes = MESES[idioma][int(m)]
        dia = int(d)
        if idioma == "es":
            return f"{dia} de {mes} de {a}"
        if idioma == "fr":
            return f"{dia} {mes} {a}"
        if idioma == "de":
            return f"{dia}. {mes} {a}"
        return f"{mes} {dia}, {a}"
    except Exception:
        return iso


def seccion_actividades(data, idioma):
    a = data.get("actividades")
    if not a:
        return ""
    visibles = [ln for ln in a["lineas"] if ln.get("visible", False)]
    out = [f'    <p class="eyebrow">{a["titulo_seccion"][idioma]}</p>',
           f'    <h2>{a["titulo_seccion"][idioma]}</h2>']
    if not visibles:
        out.append(f'    <p>{a["vacio"][idioma]}</p>')
        return "\n".join(out)
    ui = a.get("ui", {})
    def t(clave):
        return ui.get(clave, {}).get(idioma, ui.get(clave, {}).get("es", ""))
    out.append('    <div class="clases-grid">')
    for ln in visibles:
        titulo = ln["titulo"].get(idioma) or ln["titulo"]["es"]
        texto = ln["texto"].get(idioma) or ln["texto"]["es"]
        fecha = fecha_legible(ln.get("fecha", ""), idioma)
        precio = ln.get("precio", "").strip()
        estado = ln.get("estado", "tentativa")
        umbral = int(ln.get("umbral", 0) or 0)
        interes = int(ln.get("interesados", 0) or 0)
        aid = ln.get("id", "")
        out.append('      <article class="clase">')
        if ln.get("foto"):
            out.append(f'        <img src="{ln["foto"]}" alt="{titulo}" style="border-radius:10px;margin-bottom:.8rem">')
        # Badge de estado
        if estado == "tentativa":
            out.append(f'        <p class="badge badge-tent">{t("tentativa")}</p>')
        elif estado == "confirmada":
            out.append(f'        <p class="badge badge-conf">{t("confirmada")}</p>')
        out.append(f'        <h3>{titulo}</h3>')
        if fecha:
            out.append(f'        <p style="color:var(--mar);font-weight:700;margin-bottom:.4rem">{fecha}</p>')
        out.append(f'        <p>{texto}</p>')
        if precio:
            out.append(f'        <p style="font-weight:700;margin-bottom:.6rem">{precio} €</p>')
        # Sondeo: contador (solo si va bien) + formulario "Me interesa"
        if estado == "tentativa":
            # "solo cuando va bien": mostrar si mostrar_contador y ya hay >=50% del umbral
            if ln.get("mostrar_contador") and umbral > 0 and interes >= umbral * 0.5 and interes < umbral:
                faltan = umbral - interes
                out.append(f'        <p class="contador">{t("faltan").replace("{n}", str(faltan))}</p>')
            out.append(f'        <form class="interes" data-actividad="{aid}" onsubmit="return enviarInteres(this)">')
            out.append(f'          <input type="text" name="nombre" placeholder="{t("form_nombre")}" required>')
            out.append(f'          <input type="text" name="contacto" placeholder="{t("form_contacto")}" required>')
            # Franjas horarias (si la actividad las define)
            franjas = ln.get("franjas", [])
            if franjas:
                out.append(f'          <fieldset class="franjas"><legend>{t("elige_franja")}</legend>')
                for fr in franjas:
                    fid = fr.get("id", "")
                    etiq = fr.get("etiqueta", {}).get(idioma) or fr.get("etiqueta", {}).get("es", fid)
                    out.append(f'            <label><input type="checkbox" name="franja" value="{fid}"> {etiq}</label>')
                out.append('          </fieldset>')
            out.append(f'          <button type="submit" class="btn">{t("interesa")}</button>')
            out.append(f'          <p class="consent">{t("form_consent")}</p>')
            out.append(f'          <p class="ok" hidden>{t("form_ok")}</p>')
            out.append('        </form>')
        out.append('      </article>')
    out.append('    </div>')
    # Script de envío (una sola vez por página; idempotente al regenerar)
    out.append('''    <script>
    async function enviarInteres(f){
      const fr=[...f.querySelectorAll('input[name=franja]:checked')].map(x=>x.value);
      const d={actividad:f.dataset.actividad,nombre:f.nombre.value,contacto:f.contacto.value,franjas:fr,idioma:document.documentElement.lang};
      try{
        await fetch('https://auto.juliamoreno.yoga/webhook/interes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
        f.querySelector('.ok').hidden=false;
        f.nombre.disabled=f.contacto.disabled=f.querySelector('button').disabled=true;
      }catch(e){alert('No se pudo enviar, inténtalo más tarde.');}
      return false;
    }
    </script>''')
    return "\n".join(out)


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
    # Bloque precios/horarios
    ini = html.index(INI)
    ini_fin = html.index("-->", ini) + 3
    fin = html.index(FIN)
    html = (html[:ini_fin] + "\n" + seccion(data, idioma) + "\n    " + html[fin:])
    # Bloque actividades
    if INI_ACT in html:
        ai = html.index(INI_ACT)
        ai_fin = html.index("-->", ai) + 3
        af = html.index(FIN_ACT)
        html = (html[:ai_fin] + "\n" + seccion_actividades(data, idioma) + "\n    " + html[af:])
    ruta.write_text(html, encoding="utf-8")


def desde_nocodb(data):
    """Vuelca a data los valores editables leidos de NocoDB, si esta configurado."""
    import urllib.request
    base = os.environ["NOCODB_URL"].rstrip("/")
    tok = os.environ["NOCODB_TOKEN"]
    def get(tabla):
        req = urllib.request.Request(f"{base}/api/v2/tables/{tabla}/records?limit=200",
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
    # Actividades: se reconstruye la lista entera desde NocoDB
    tbl_act = os.environ.get("NOCODB_TBL_ACTIVIDADES")
    if tbl_act:
        nuevas = []
        for fila in get(tbl_act):
            try:
                franjas = json.loads(fila.get("franjas") or "[]")
            except Exception:
                franjas = []
            def campo_idiomas(base):
                return {i: (fila.get(f"{base}_{i}") or fila.get(f"{base}_es") or "")
                        for i in ("es", "en", "fr", "de")}
            nuevas.append({
                "id": fila.get("id"),
                "estado": fila.get("estado", "tentativa"),
                "umbral": fila.get("umbral", 0),
                "interesados": fila.get("interesados", 0),
                "plazas": fila.get("plazas", 0),
                "foto": fila.get("foto", ""),
                "mostrar_contador": bool(fila.get("mostrar_contador", False)),
                "visible": bool(fila.get("visible", True)),
                "titulo": campo_idiomas("titulo"),
                "texto": campo_idiomas("texto"),
                "franjas": franjas,
            })
        if nuevas:
            data["actividades"]["lineas"] = nuevas
    JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    data = json.loads(JSON.read_text(encoding="utf-8"))
    # NocoDB es la fuente de verdad. Se lee siempre que esté configurado.
    # --solo-json fuerza a ignorar NocoDB (para pruebas o si NocoDB está caído).
    usa_nocodb = ("--solo-json" not in sys.argv
                  and os.environ.get("NOCODB_URL") and os.environ.get("NOCODB_TOKEN"))
    if usa_nocodb:
        try:
            desde_nocodb(data)
            print("datos leídos de NocoDB")
        except Exception as e:
            print(f"AVISO: no se pudo leer NocoDB ({e}); uso el último JSON conocido.")
    else:
        print("NocoDB no configurado o --solo-json: uso data/contenido.json.")
    for idioma, ruta in PAGS.items():
        aplica(idioma, ruta, data)
        print(f"generado {ruta.relative_to(RAIZ)}")
    print("OK")


if __name__ == "__main__":
    main()
