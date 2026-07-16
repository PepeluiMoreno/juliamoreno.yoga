"""
backend.fotos — subida y optimización de imágenes de actividades.

Recibe los bytes de una imagen, valida que lo sea, corrige la orientación
EXIF, la redimensiona a ANCHO_MAX y la guarda como JPEG optimizado en el
directorio de uploads que sirve nginx. Requiere Pillow.
"""
import io
import os
import pathlib
import uuid

from .util import slug

ANCHO_MAX = 1200  # ancho máximo al que se redimensiona


def guarda_foto(datos_bytes, nombre_orig):
    """Redimensiona con Pillow a ANCHO_MAX y guarda como JPEG optimizado.
    Devuelve la URL pública. Lanza ValueError si no es una imagen válida."""
    from PIL import Image
    uploads_dir = os.environ.get("UPLOADS_DIR", "/app/sitio/uploads")
    uploads_url = os.environ.get("UPLOADS_URL", "https://juliamoreno.yoga/uploads")
    try:
        img = Image.open(io.BytesIO(datos_bytes))
        img.verify()  # valida que es imagen real
        img = Image.open(io.BytesIO(datos_bytes))  # reabrir tras verify
    except Exception:
        raise ValueError("el fichero no es una imagen válida")
    # Corregir orientación EXIF (fotos de móvil)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert("RGB")
    if img.width > ANCHO_MAX:
        alto = int(img.height * ANCHO_MAX / img.width)
        img = img.resize((ANCHO_MAX, alto), Image.LANCZOS)
    pathlib.Path(uploads_dir).mkdir(parents=True, exist_ok=True)
    base = slug(pathlib.Path(nombre_orig or "foto").stem)
    fichero = f"{base}-{uuid.uuid4().hex[:8]}.jpg"
    destino = os.path.join(uploads_dir, fichero)
    img.save(destino, "JPEG", quality=82, optimize=True)
    return f"{uploads_url}/{fichero}"
