"""
backend.web — disparo de la regeneración del sitio estático.

Tras un cambio en actividades o agenda, se lanza build-web.py en segundo
plano para regenerar el HTML público. No bloquea la respuesta al panel.
"""
import os
import subprocess
import sys

# Directorio scripts/ (padre del paquete backend/), donde vive build-web.py
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Raíz del repo (padre de scripts/), cwd desde el que corre build-web.py
_REPO_DIR = os.path.dirname(_SCRIPTS_DIR)


def dispara_rebuild():
    """Lanza build-web.py en segundo plano. Si falla, se registra pero no
    rompe la operación (la web se puede regenerar a mano)."""
    try:
        script = os.path.join(_SCRIPTS_DIR, "build-web.py")
        subprocess.Popen(
            [sys.executable, script],
            cwd=_REPO_DIR,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("rebuild de la web disparado")
    except Exception as e:
        print(f"aviso: no se pudo disparar el rebuild: {e}")
