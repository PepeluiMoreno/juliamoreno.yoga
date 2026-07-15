#!/usr/bin/env python3
"""
provision-nocodb.py — crea y puebla las tablas del backoffice en NocoDB
vía su API REST (v2). Idempotente: si una tabla ya existe, no la duplica;
si una fila (por 'id') ya existe, la respeta.

Requiere en el entorno (.env del VPS o export):
  NOCODB_URL    p.ej. https://datos.juliamoreno.yoga
  NOCODB_TOKEN  token de API generado en NocoDB (Account Settings -> Tokens)
  NOCODB_BASE   nombre de la base a usar/crear (por defecto: Yoga)

Uso:
  python3 scripts/provision-nocodb.py

Crea las tablas: Precios, Horarios, Actividades, Interesados
y siembra Precios y Horarios desde data/contenido.json.
Las traducciones (titulo_en/fr/de, etc.) las rellena luego n8n+DeepL;
aquí solo se crean las columnas.
"""
import json, os, sys, urllib.request, urllib.error, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
JSON = RAIZ / "data" / "contenido.json"
URL = os.environ.get("NOCODB_URL", "").rstrip("/")
TOKEN = os.environ.get("NOCODB_TOKEN", "")
BASE_NAME = os.environ.get("NOCODB_BASE", "Yoga")

if not URL or not TOKEN:
    sys.exit("Faltan NOCODB_URL y/o NOCODB_TOKEN en el entorno.")

H = {"xc-token": TOKEN, "Content-Type": "application/json"}


def api(method, path, body=None):
    req = urllib.request.Request(URL + path, method=method, headers=H,
                                 data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            t = r.read().decode()
            return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        print(f"  ! {method} {path} -> {e.code}: {e.read().decode()[:200]}")
        raise


# ---- Definición de columnas por tabla ----
def col(title, uidt="SingleLineText", **extra):
    c = {"title": title, "uidt": uidt}
    c.update(extra)
    return c

TABLAS = {
    "Precios": [
        col("id"), col("valor"), col("visible", "Checkbox"),
    ],
    "Horarios": [
        col("id"), col("visible", "Checkbox"),
    ],
    "Actividades": [
        col("id"), col("estado"), col("umbral", "Number"),
        col("interesados", "Number"), col("plazas", "Number"),
        col("foto", "URL"), col("mostrar_contador", "Checkbox"),
        col("visible", "Checkbox"),
        col("titulo_es", "LongText"), col("texto_es", "LongText"),
        col("titulo_en", "LongText"), col("texto_en", "LongText"),
        col("titulo_fr", "LongText"), col("texto_fr", "LongText"),
        col("titulo_de", "LongText"), col("texto_de", "LongText"),
        col("franjas", "LongText"),   # JSON de franjas (id,tipo,etiquetas)
        col("revisado", "SingleLineText"),  # idiomas revisados a mano
    ],
    "Interesados": [
        col("actividad"), col("nombre"), col("contacto"),
        col("franjas"), col("idioma"), col("fecha", "DateTime"),
    ],
}


def base_id():
    bases = api("GET", "/api/v2/meta/bases").get("list", [])
    for b in bases:
        if b.get("title") == BASE_NAME:
            print(f"base '{BASE_NAME}' encontrada")
            return b["id"]
    r = api("POST", "/api/v2/meta/bases", {"title": BASE_NAME})
    print(f"base '{BASE_NAME}' creada")
    return r["id"]


def tablas_existentes(bid):
    ts = api("GET", f"/api/v2/meta/bases/{bid}/tables").get("list", [])
    return {t["title"]: t["id"] for t in ts}


def crea_tabla(bid, nombre, columnas):
    body = {"table_name": nombre, "title": nombre,
            "columns": [dict(c, column_name=c["title"]) for c in columnas]}
    r = api("POST", f"/api/v2/meta/bases/{bid}/tables", body)
    print(f"  tabla '{nombre}' creada ({len(columnas)} columnas)")
    return r["id"]


def siembra_precios(tid, data):
    filas = [{"id": ln["id"], "valor": ln["valor"], "visible": ln.get("visible", True)}
             for ln in data["precios"]["lineas"]]
    api("POST", f"/api/v2/tables/{tid}/records", filas)
    print(f"  Precios: {len(filas)} filas sembradas")


def siembra_horarios(tid, data):
    filas = [{"id": ln["id"], "visible": ln.get("visible", True)}
             for ln in data["horarios"]["lineas"]]
    api("POST", f"/api/v2/tables/{tid}/records", filas)
    print(f"  Horarios: {len(filas)} filas sembradas")


def siembra_actividades(tid):
    """Una actividad de ejemplo, tentativa, con franjas (genérica + fecha)."""
    franjas = [
        {"id": "sab_manana", "tipo": "generica",
         "etiqueta": {"es": "Sábados por la mañana", "en": "Saturday mornings",
                      "fr": "Samedis matin", "de": "Samstagvormittags"}},
        {"id": "vie_tarde", "tipo": "generica",
         "etiqueta": {"es": "Viernes por la tarde", "en": "Friday afternoons",
                      "fr": "Vendredis après-midi", "de": "Freitagnachmittags"}},
        {"id": "f_2026_03_21", "tipo": "fecha",
         "etiqueta": {"es": "Sábado 21 de marzo, 10:00", "en": "Saturday 21 March, 10:00",
                      "fr": "Samedi 21 mars, 10h00", "de": "Samstag, 21. März, 10:00"}},
    ]
    fila = {
        "id": "taller-respiracion",
        "estado": "tentativa",
        "umbral": 8,
        "interesados": 0,
        "plazas": 12,
        "mostrar_contador": True,
        "visible": True,
        "titulo_es": "Taller de respiración consciente",
        "texto_es": ("Una mañana dedicada a la respiración como herramienta de calma y energía. "
                     "Técnicas de pranayama adaptadas con criterio científico, aptas para todos los niveles. "
                     "Si reunimos grupo, lo montamos: dime cuándo te vendría bien."),
        "franjas": json.dumps(franjas, ensure_ascii=False),
    }
    api("POST", f"/api/v2/tables/{tid}/records", [fila])
    print("  Actividades: 1 actividad de ejemplo sembrada (taller-respiracion)")


def main():
    data = json.loads(JSON.read_text(encoding="utf-8"))
    bid = base_id()
    existentes = tablas_existentes(bid)
    ids = {}
    for nombre, cols in TABLAS.items():
        if nombre in existentes:
            print(f"  tabla '{nombre}' ya existe, no se recrea")
            ids[nombre] = existentes[nombre]
        else:
            ids[nombre] = crea_tabla(bid, nombre, cols)
    # Sembrar solo si están recién creadas y vacías
    def vacia(tid):
        r = api("GET", f"/api/v2/tables/{tid}/records?limit=1")
        return not r.get("list")
    if vacia(ids["Precios"]):
        siembra_precios(ids["Precios"], data)
    if vacia(ids["Horarios"]):
        siembra_horarios(ids["Horarios"], data)
    if vacia(ids["Actividades"]):
        siembra_actividades(ids["Actividades"])
    print("\nOK. IDs de tabla (guardar para el .env de build-web / n8n):")
    for n, i in ids.items():
        print(f"  {n} = {i}")


if __name__ == "__main__":
    main()
