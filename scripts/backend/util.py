"""
backend.util — utilidades puras, sin dependencias de red ni estado.

Saneado de entrada, generación de slugs y pequeños cálculos de tiempo.
"""
import re


def limpio(v, n=200):
    """Texto saneado: str, sin espacios en los bordes, cortado a n caracteres."""
    return str(v or "").strip()[:n]


def valido_texto(s):
    """Rechaza texto vacío o que contenga URLs (anti-spam en formularios)."""
    return s and "http://" not in s.lower() and "https://" not in s.lower()


def slug(s):
    """Convierte un texto en un identificador url-safe (sin acentos ni ñ)."""
    s = (s or "").lower().strip()
    s = re.sub(r"[áàä]", "a", s); s = re.sub(r"[éèë]", "e", s)
    s = re.sub(r"[íìï]", "i", s); s = re.sub(r"[óòö]", "o", s)
    s = re.sub(r"[úùü]", "u", s); s = re.sub(r"ñ", "n", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "actividad"


def dur_horas(hi, hf):
    """Horas decimales entre dos 'HH:MM'. 0 si no parsea o el rango es inválido."""
    try:
        h1, m1 = map(int, (hi or "").split(":"))
        h2, m2 = map(int, (hf or "").split(":"))
        d = (h2 * 60 + m2) - (h1 * 60 + m1)
        return d / 60.0 if d > 0 else 0.0
    except Exception:
        return 0.0


# Mapa día-de-semana (abreviatura española) -> número weekday() de Python.
DIA_NUM = {"lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6}
