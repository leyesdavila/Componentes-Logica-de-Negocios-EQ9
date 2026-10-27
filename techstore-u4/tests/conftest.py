"""Fixtures compartidas por la suite de pruebas.

Se cargan los pedidos con el servicio de aplicación (`app.service`), no con el
cargador didáctico, para que las pruebas ejerciten la misma ruta que la API y
los scripts. Cada prueba recibe objetos nuevos e independientes.
"""

import pytest

from app.service import load_orders


@pytest.fixture()
def orders():
    """Los 16 pedidos del paquete, recién cargados desde `datos/`."""
    return load_orders()
