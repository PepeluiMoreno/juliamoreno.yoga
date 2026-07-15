#!/usr/bin/env python3
"""
provision-nocodb.py — crea y puebla el backoffice en NocoDB. IDEMPOTENTE:
- crea la base si no existe;
- crea las tablas que falten;
- añade a las tablas existentes las columnas que falten (no borra nada);
- siembra datos iniciales SOLO en tablas vacías (Precios, Horarios y una
  actividad de ejemplo).

Config: NOCODB_URL, NOCODB_TOKEN, NOCODB_BASE en el .env del proyecto
(el script carga el .env por sí mismo; no hace falta `source`).

Uso:  python3 scripts/provision-nocodb.py
"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nocolib as nc

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((RAIZ / "data" / "contenido.json").read_text(encoding="utf-8"))


def col(title, uidt="SingleLineText"):
    return {"title": title, "column_name": title, "uidt": uidt}

TABLAS = {
    "Precios": [col("id"), col("valor"), col("visible", "Checkbox")],
    "Horarios": [col("id"), col("visible", "Checkbox")],
    "Actividades": [
        col("id"), col("estado"), col("umbral", "Number"),
        col("interesados", "Number"), col("plazas", "Number"),
        col("foto", "URL"), col("mostrar_contador", "Checkbox"),
        col("visible", "Checkbox"),
        col("titulo_es", "LongText"), col("texto_es", "LongText"),
        col("titulo_en", "LongText"), col("texto_en", "LongText"),
        col("titulo_fr", "LongText"), col("texto_fr", "LongText"),
        col("titulo_de", "LongText"), col("texto_de", "LongText"),
        col("franjas", "LongText"), col("revisado"),
    ],
    "Interesados": [
        col("actividad"), col("nombre"), col("contacto"),
        col("franjas"), col("idioma"), col("fecha", "DateTime"),
    ],
}

ACTIVIDAD_EJEMPLO = {
    "id": "taller-respiracion",
    "estado": "tentativa",
    "umbral": 8,
    "interesados": 0,
    "plazas": 12,
    "mostrar_contador": True,
    "visible": True,
    "titulo_es": "Taller de respiración consciente",
    "texto_es": ("Una mañana dedicada a la respiración como herramienta de calma "
                 "y energía. Técnicas de pranayama adaptadas con criterio científico, "
                 "aptas para todos los niveles. Si reunimos grupo, lo montamos: "
                 "dime cuándo te vendría bien."),
    "franjas": json.dumps([
        {"id": "sab_manana", "tipo": "generica",
         "etiqueta": {"es": "Sábados por la mañana", "en": "Saturday mornings",
                      "fr": "Samedis matin", "de": "Samstagvormittags"}},
        {"id": "vie_tarde", "tipo": "generica",
         "etiqueta": {"es": "Viernes por la tarde", "en": "Friday afternoons",
                      "fr": "Vendredis après-midi", "de": "Freitagnachmittags"}},
        {"id": "f_2026_03_21", "tipo": "fecha",
         "etiqueta": {"es": "Sábado 21 de marzo, 10:00", "en": "Saturday 21 March, 10:00",
                      "fr": "Samedi 21 mars, 10h00", "de": "Samstag, 21. März, 10:00"}},
    ], ensure_ascii=False),
}


def main():
    url, tok, base = nc.cfg()
    bid = nc.base_id(url, tok, base)
    if bid:
        print(f"base '{base}': OK")
    else:
        bid = nc.api(url, tok, "POST", "/api/v2/meta/bases", {"title": base})["id"]
        print(f"base '{base}': creada")

    existentes = nc.tablas(url, tok, bid)
    ids = {}
    for nombre, cols in TABLAS.items():
        if nombre not in existentes:
            r = nc.api(url, tok, "POST", f"/api/v2/meta/bases/{bid}/tables",
                       {"table_name": nombre, "title": nombre, "columns": cols})
            ids[nombre] = r["id"]
            print(f"tabla '{nombre}': creada ({len(cols)} columnas)")
        else:
            ids[nombre] = existentes[nombre]
            # idempotencia de columnas: añadir las que falten
            actuales = nc.columnas(url, tok, ids[nombre])
            faltan = [c for c in cols if c["title"] not in actuales]
            for c in faltan:
                nc.api(url, tok, "POST",
                       f"/api/v2/meta/tables/{ids[nombre]}/columns", c)
            print(f"tabla '{nombre}': OK"
                  + (f" (+{len(faltan)} columnas añadidas)" if faltan else ""))

    # Siembra solo en tablas vacías
    if not nc.records(url, tok, ids["Precios"], 1):
        filas = [{"id": l["id"], "valor": l["valor"], "visible": l.get("visible", True)}
                 for l in DATA["precios"]["lineas"]]
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Precios']}/records", filas)
        print(f"Precios: {len(filas)} filas sembradas")
    else:
        print("Precios: ya tiene datos")

    if not nc.records(url, tok, ids["Horarios"], 1):
        filas = [{"id": l["id"], "visible": l.get("visible", True)}
                 for l in DATA["horarios"]["lineas"]]
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Horarios']}/records", filas)
        print(f"Horarios: {len(filas)} filas sembradas")
    else:
        print("Horarios: ya tiene datos")

    if not nc.records(url, tok, ids["Actividades"], 1):
        nc.api(url, tok, "POST", f"/api/v2/tables/{ids['Actividades']}/records",
               [ACTIVIDAD_EJEMPLO])
        print("Actividades: 1 actividad de ejemplo sembrada (taller-respiracion)")
    else:
        print("Actividades: ya tiene datos")

    print("\nPROVISION OK")


if __name__ == "__main__":
    main()
