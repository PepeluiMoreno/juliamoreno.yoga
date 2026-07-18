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


# Etiqueta del botón de reserva por idioma, por si no está en las
# etiquetas de interfaz de contenido.json.
RESERVAR_ETQ = {"es": "Reservar mi plaza", "en": "Book my place",
                "fr": "Réserver ma place", "de": "Meinen Platz buchen"}
# Etiquetas de estado. Van aquí y no en contenido.json porque las claves
# de allí ('tentativa', 'confirmada') no coincidían con los estados y los
# badges salían VACÍOS: pastillas de color sin texto.
ESTADO_ETQ = {
    "propuesta": {"es": "En preparación", "en": "In preparation",
                  "fr": "En préparation", "de": "In Vorbereitung"},
    "programada": {"es": "Programada", "en": "Scheduled",
                   "fr": "Programmée", "de": "Geplant"},
    "en_curso": {"es": "En curso", "en": "Running",
                 "fr": "En cours", "de": "Laufend"},
}
ESTADO_ETQ["finalizada"] = {"es": "Finalizada", "en": "Finished",
                            "fr": "Terminée", "de": "Beendet"}
# Disponibilidad: se calcula del aforo real, no la mantiene nadie a mano.
# Un badge que hay que actualizar a mano acaba mintiendo; este no puede.
AFORO_ETQ = {
    "abierta": {"es": "Admitiendo alumnos", "en": "Open for enrolment",
                "fr": "Inscriptions ouvertes", "de": "Anmeldung offen"},
    "ultimas": {"es": "Últimas plazas", "en": "Last places",
                "fr": "Dernières places", "de": "Letzte Plätze"},
    "completa": {"es": "No quedan plazas", "en": "Fully booked",
                 "fr": "Complet", "de": "Ausgebucht"},
}
PASADAS_ETQ = {"es": "Ver actividades anteriores",
               "en": "See past activities",
               "fr": "Voir les activités passées",
               "de": "Frühere Aktivitäten ansehen"}
AFORO_CLASE = {"abierta": "badge-abierta", "ultimas": "badge-ultimas",
               "completa": "badge-lleno"}
# A partir de cuántas plazas libres se avisa de que quedan pocas. Solo se
# muestra si es cierto: la urgencia inventada se nota y quema la confianza.
UMBRAL_ULTIMAS = 3
# Salida secundaria: en yoga la objeción no suele ser el precio sino "¿es
# para mí?". Un enlace discreto a contacto recoge esa duda en vez de
# perderla en un abandono silencioso.
PREGUNTA_ETQ = {"es": "¿Te encaja? Pregúntanos",
                "en": "Not sure? Ask us",
                "fr": "Un doute ? Écris-nous",
                "de": "Unsicher? Frag uns"}
CONTACTO_ANCLA = {"es": "#contacto", "en": "#contact",
                  "fr": "#contact", "de": "#kontakt"}


def _archivada(ln):
    """¿La actividad ya pasó? Dos vías: que Julia la marque 'finalizada',
    o que su fecha de vigencia (campo 'hasta') haya quedado atrás. La
    segunda evita que nadie tenga que acordarse de archivar nada."""
    if (ln.get("estado") or "") == "finalizada":
        return True
    hasta = (ln.get("hasta") or "").strip()
    if not hasta:
        return False
    try:
        import datetime
        return datetime.date.fromisoformat(hasta[:10]) < datetime.date.today()
    except Exception:
        return False


def _aforo(cal_id, dias=30):
    """Estado de ocupación de una clase en el próximo mes.

    Devuelve "abierta", "ultimas" o "completa" mirando el hueco con MÁS
    plazas libres (si en alguna hora hay sitio de sobra, la clase no está
    en las últimas). Se usa el aforo real de Cal.diy, calculado cruzando
    huecos y reservas: el seatsRemaining del endpoint de slots no se
    actualiza al reservar.

    Devuelve None si no hay clase enlazada o no se puede consultar —sin
    credenciales, Cal.diy caído—: preferimos no decir nada del aforo a
    decirlo mal y espantar a quien sí tenía plaza.
    """
    if not cal_id:
        return None
    try:
        import datetime
        sys.path.insert(0, str(RAIZ / "scripts"))
        # Las credenciales de Cal.diy salen del .env, igual que las de
        # NocoDB. Sin esto, build-web.py no podía consultar el aforo y las
        # clases reservables se quedaban con el badge de ciclo de vida en
        # vez de "Admitiendo alumnos" / "Últimas plazas".
        import nocolib as _nc
        _nc.carga_env()
        os.environ.setdefault("CALCOM_API_URL",
                              "https://api-reservas.juliamoreno.yoga")
        from backend.calcom import cliente
        hoy = datetime.date.today()
        fin = hoy + datetime.timedelta(days=dias)
        aforo = cliente.aforo_por_hueco(int(cal_id), hoy.isoformat(),
                                        fin.isoformat())
        if not aforo:
            return None
        mejor = max((v.get("libres") or 0) for v in aforo.values())
        if mejor <= 0:
            return "completa"
        return "ultimas" if mejor <= UMBRAL_ULTIMAS else "abierta"
    except Exception:
        return None


def seccion_actividades(data, idioma):
    import json as _json
    a = data.get("actividades")
    if not a:
        return ""
    # Las archivadas salen del grid principal y viven en su propia vista:
    # que la sección enseñe lo que se puede hacer ahora, no un histórico.
    visibles = [ln for ln in a["lineas"]
                if ln.get("visible", False) and not _archivada(ln)]
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
        estado = ln.get("estado", "propuesta")
        umbral = int(ln.get("umbral", 0) or 0)
        interes = int(ln.get("interesados", 0) or 0)
        aid = ln.get("id", "")
        elegible = bool(ln.get("franjas_elegibles", False))
        franjas = ln.get("franjas", []) if elegible else []
        franjas_data = []
        for fr in franjas:
            fid = fr.get("id", "")
            etiq = fr.get("etiqueta", {}).get(idioma) or fr.get("etiqueta", {}).get("es", fid)
            franjas_data.append({"id": fid, "etiqueta": etiq})

        out.append('      <article class="clase">')
        out.append('        <div class="clase-cab">')
        # UN solo badge, el más informativo. Si la clase ya es reservable,
        # lo que le importa al visitante es si queda sitio, no en qué punto
        # del ciclo está; si no lo es, se muestra el ciclo de vida.
        aforo = ln.get("aforo")
        clases_badge = {"propuesta": "badge-tent", "programada": "badge-prog",
                        "en_curso": "badge-conf", "finalizada": "badge-hueco"}
        if aforo:
            out.append(f'          <p class="badge {AFORO_CLASE[aforo]}">'
                       f'{AFORO_ETQ[aforo].get(idioma, AFORO_ETQ[aforo]["es"])}'
                       f'</p>')
        elif estado in clases_badge:
            etq_est = (t(estado) or ESTADO_ETQ[estado].get(idioma)
                       or ESTADO_ETQ[estado]["es"])
            out.append(f'          <p class="badge {clases_badge[estado]}">'
                       f'{etq_est}</p>')
        else:
            out.append('          <p class="badge badge-hueco">&nbsp;</p>')
        out.append('        </div>')
        out.append('        <div class="clase-cuerpo">')
        if ln.get("foto"):
            out.append(f'          <img src="{ln["foto"]}" alt="{titulo}" class="clase-foto">')
        out.append(f'          <h3>{titulo}</h3>')
        if fecha:
            out.append(f'          <p class="clase-fecha">{fecha}</p>')
        out.append(f'          <p class="clase-texto">{texto}</p>')
        # Metadatos: duración y lugar (línea sutil bajo el texto)
        duracion = ln.get("duracion", "").strip()
        lugar = ln.get("lugar", "").strip()
        metas = []
        if duracion:
            metas.append(f'<span class="clase-meta-it">&#9201; {duracion}</span>')
        if lugar:
            metas.append(f'<span class="clase-meta-it">&#128205; {lugar}</span>')
        # Nivel: si se dejó en blanco al proponer la actividad, no se
        # muestra nunca (nada de "todos los niveles" por defecto).
        nivel = (ln.get("nivel") or "").strip()
        if nivel:
            metas.append(f'<span class="clase-meta-it">&#9679; {nivel}</span>')
        if metas:
            out.append(f'          <p class="clase-meta">{" ".join(metas)}</p>')
        precio = (ln.get("precio") or "").strip()
        if precio:
            out.append(f'          <p class="clase-precio">{precio}</p>')
        if estado == "propuesta" and ln.get("mostrar_contador") and umbral > 0 and interes >= umbral * 0.5 and interes < umbral:
            faltan = umbral - interes
            out.append(f'          <p class="contador">{t("faltan").replace("{n}", str(faltan))}</p>')
        out.append('        </div>')
        if estado == "propuesta":
            # Los datos (nombre y contacto) se piden en su propia vista,
            # no dentro de la tarjeta: el grid queda limpio, todas las
            # tarjetas miden lo mismo y cada una tiene UN botón claro.
            out.append('        <div class="clase-form">')
            out.append(f'          <a class="btn" href="/interes.html?actividad={aid}">'
                       f'{t("interesa")}</a>')
            out.append('        </div>')
        else:
            # Actividad ya programada o en curso: si está enlazada con una
            # clase de Cal.diy (cal_event_type_id), se ofrece reservar plaza.
            # El enlace lleva ?clase=<id> para que el alumno vea ESA clase.
            # REGLA DE NEGOCIO: ninguna tarjeta sin acción. Si la clase es
            # reservable, el CTA es reservar; si no lo es todavía, al menos
            # se ofrece preguntar. Una tarjeta muda es la peor casilla:
            # la clase existe, la miran con interés y no hay dónde pulsar.
            cal_id = int(ln.get("cal_event_type_id", 0) or 0)
            out.append('        <div class="clase-form">')
            if cal_id and ln.get("aforo") != "completa":
                out.append(f'          <a class="btn" href="/reservar.html?clase={cal_id}">'
                           f'{t("interesa")}</a>')
            else:
                # En curso pero todavía no reservable (p. ej. sin horario
                # semanal fijo). Se recoge el interés en vez de mandar a un
                # formulario de contacto genérico: así la persona queda
                # anotada y Julia puede avisarla de la próxima sesión.
                out.append(f'          <a class="btn" href="/interes.html?actividad={aid}">'
                           f'{t("interesa")}</a>')
            out.append('        </div>')
        out.append('      </article>')
    out.append('    </div>')
    if any(ln.get("visible", False) and _archivada(ln) for ln in a["lineas"]):
        out.append('    <p class="pasadas-enlace">'
                   f'<a href="/pasadas.html">'
                   f'{PASADAS_ETQ.get(idioma, PASADAS_ETQ["es"])}</a></p>')
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



def traduce_actividades_pendientes(nc, url, tok, ids):
    """Traduce con DeepL las actividades cuyo texto ES cambió (sello es_hash).
    Convivencia: respeta idiomas en 'revisado'. Sin bucles: solo actúa si el
    hash del ES difiere del es_hash guardado. Best-effort: si DeepL falla,
    deja la actividad como está y sigue."""
    import hashlib, urllib.request, os
    deepl = os.environ.get("DEEPL_API_KEY")
    if not deepl or "Actividades" not in ids:
        return
    LANGS = {"en": "EN-GB", "fr": "FR", "de": "DE"}
    def dl(texto, target):
        if not texto:
            return ""
        body = json.dumps({"text": [texto], "source_lang": "ES",
                           "target_lang": target}).encode()
        req = urllib.request.Request(
            "https://api-free.deepl.com/v2/translate", data=body,
            headers={"Authorization": f"DeepL-Auth-Key {deepl}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)["translations"][0]["text"]
    for fila in nc.records(url, tok, ids["Actividades"]):
        tit = (fila.get("titulo_es") or "").strip()
        txt = (fila.get("texto_es") or "").strip()
        if not tit and not txt:
            continue
        h = hashlib.md5((tit + "|" + txt).encode()).hexdigest()
        if fila.get("es_hash") == h:
            continue  # sin cambios: no re-traducir (anti-bucle)
        revisado = (fila.get("revisado") or "").lower()
        parche = {"Id": fila["Id"], "es_hash": h}
        try:
            for idi, tgt in LANGS.items():
                if idi in revisado:
                    continue
                if tit:
                    parche[f"titulo_{idi}"] = dl(tit, tgt)
                if txt:
                    parche[f"texto_{idi}"] = dl(txt, tgt)
            nc.api(url, tok, "PATCH",
                   f"/api/v2/tables/{ids['Actividades']}/records", [parche])
            print(f"  traducida actividad {fila.get('id') or fila['Id']}")
        except Exception as e:
            print(f"  AVISO: no se pudo traducir {fila.get('id')}: {e}")


def desde_nocodb(data):
    """Lee precios/horarios/actividades de NocoDB (fuente de verdad) y los
    vuelca en data. Descubre las tablas por nombre; no requiere IDs."""
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
    import nocolib as nc
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if not bid:
        raise RuntimeError(f"la base '{base}' no existe en NocoDB")
    ids = nc.tablas(url, tok, bid)
    for t in ("Precios", "Horarios", "Actividades"):
        if t not in ids:
            raise RuntimeError(f"falta la tabla '{t}' (ejecute provision-nocodb.py)")
    # Traducir (DeepL) lo que haya cambiado, antes de leer para generar
    traduce_actividades_pendientes(nc, url, tok, ids)
    # Precios
    for fila in nc.records(url, tok, ids["Precios"]):
        for ln in data["precios"]["lineas"]:
            if ln["id"] == fila.get("id"):
                ln["valor"] = str(fila.get("valor") or ln["valor"])
                ln["visible"] = bool(fila.get("visible"))
    # Horarios
    for fila in nc.records(url, tok, ids["Horarios"]):
        for ln in data["horarios"]["lineas"]:
            if ln["id"] == fila.get("id"):
                ln["visible"] = bool(fila.get("visible"))
    # Actividades: la lista entera viene de NocoDB.
    # INTEGRIDAD: el nº de interesados NO se lee del campo almacenado en
    # Actividades (redundante y desincronizable); se CUENTA de las filas
    # reales de la tabla Interesados por actividad.
    conteo = {}
    conteo_franjas = {}
    if "Interesados" in ids:
        for fila in nc.records(url, tok, ids["Interesados"], limit=1000):
            a = (fila.get("actividad") or "").strip()
            if a:
                conteo[a] = conteo.get(a, 0) + 1
                for fid in (fila.get("franjas") or "").split(","):
                    fid = fid.strip()
                    if fid:
                        conteo_franjas.setdefault(a, {})
                        conteo_franjas[a][fid] = conteo_franjas[a].get(fid, 0) + 1
    nuevas = []
    for fila in nc.records(url, tok, ids["Actividades"]):
        try:
            franjas = json.loads(fila.get("franjas") or "[]")
        except Exception:
            franjas = []
        idi = lambda b: {i: (fila.get(f"{b}_{i}") or fila.get(f"{b}_es") or "")
                         for i in ("es", "en", "fr", "de")}
        nuevas.append({
            "id": fila.get("id"), "estado": fila.get("estado") or "propuesta",
            "umbral": fila.get("umbral") or 0,
            "interesados": conteo.get((fila.get("id") or "").strip(), 0),
            "conteo_franjas": conteo_franjas.get((fila.get("id") or "").strip(), {}),
            "plazas": fila.get("plazas") or 0, "foto": fila.get("foto") or "",
            "precio": fila.get("precio") or "", "duracion": fila.get("duracion") or "",
            "lugar": fila.get("lugar") or "",
            "mostrar_contador": bool(fila.get("mostrar_contador")),
            "franjas_elegibles": bool(fila.get("franjas_elegibles")),
            "cal_event_type_id": fila.get("cal_event_type_id") or 0,
            "nivel": fila.get("nivel") or "",
            "hasta": str(fila.get("hasta") or "")[:10],
            "aforo": _aforo(fila.get("cal_event_type_id")),
            "visible": bool(fila.get("visible")),
            "titulo": idi("titulo"), "texto": idi("texto"), "franjas": franjas,
        })
    data["actividades"]["lineas"] = nuevas
    JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def versiona_css():
    """Cache-busting: enlaza el CSS con ?v=<hash> de su contenido en los 4 HTML."""
    import hashlib
    css = (RAIZ / "sitio" / "assets" / "style.css").read_bytes()
    h = hashlib.md5(css).hexdigest()[:8]
    for ruta in PAGS.values():
        html = ruta.read_text(encoding="utf-8")
        html = re.sub(r'href="/assets/style\.css[^"]*"',
                      f'href="/assets/style.css?v={h}"', html)
        ruta.write_text(html, encoding="utf-8")
    print(f"css versionado: style.css?v={h}")


def main():
    data = json.loads(JSON.read_text(encoding="utf-8"))
    # NocoDB es la fuente de verdad; el .env lo carga nocolib por sí mismo.
    # --solo-json fuerza a ignorar NocoDB (pruebas o si NocoDB está caído).
    if "--solo-json" in sys.argv:
        print("--solo-json: uso data/contenido.json.")
    else:
        try:
            desde_nocodb(data)
            print("datos leídos de NocoDB")
        except Exception as e:
            print(f"AVISO: no se pudo leer NocoDB ({e}); uso el último JSON conocido.")
    for idioma, ruta in PAGS.items():
        aplica(idioma, ruta, data)
        print(f"generado {ruta.relative_to(RAIZ)}")
    versiona_css()
    print("OK")


if __name__ == "__main__":
    main()
