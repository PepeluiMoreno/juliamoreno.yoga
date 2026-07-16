"""
Punto de entrada del backend de juliamoreno.yoga.

Arranca el servidor HTTP que atiende:
  - la captación de formularios de la web pública (/webhook/*)
  - la API de administración del panel (/admin/api/*), protegida por Authelia

Se ejecuta con:  python3 -m backend   (o  python3 backend/__main__.py)
"""
import pathlib
import sys

# Permite ejecutarlo tanto como módulo (-m backend) como por ruta directa.
if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from backend import datos, servidor
else:
    from . import datos, servidor

import nocolib as nc


def main():
    nc.carga_env()
    try:
        datos.resolver_tablas()
        print(f"backend: tablas resueltas {datos.tablas_resueltas()}")
    except Exception as e:
        print(f"backend: aviso, no pude resolver tablas al arrancar ({e})")
    servidor.arranca()


if __name__ == "__main__":
    main()
