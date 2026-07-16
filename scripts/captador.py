#!/usr/bin/env python3
"""
captador.py — DEPRECADO. Punto de entrada de compatibilidad.

El servicio se renombró a `backend` y se modularizó en el paquete
scripts/backend/. Este fichero se conserva solo para no romper invocaciones
antiguas; delega en el nuevo punto de entrada.

Usa en su lugar:  python3 -m backend
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from backend.__main__ import main

if __name__ == "__main__":
    main()
