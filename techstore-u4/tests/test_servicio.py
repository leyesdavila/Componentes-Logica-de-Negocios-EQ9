"""Pruebas del servicio de aplicación y de los endpoints de apoyo.

Verifican que el servicio y el cargador didáctico produzcan el mismo estado,
que los catálogos se lean de los CSV y que `/health` y
`/admin/reload-fixtures` funcionen sin reiniciar el proceso.
"""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.api import app
from app.service import (
    DATA_DIR,
    catalogo_clientes,
    catalogo_productos,
    load_orders,
)
from cargar_csv import load_fixture


def huella(order):
    """Representación comparable de un pedido (sin marcas de tiempo)."""
    return (
        order.id,
        order.status.value,
        order.has_promotion,
        order.customer.id,
        order.customer.is_vip,
        order.customer.active,
        order.units,
        len(order.items),
        order.total.amount,
        tuple(
            (
                item.sku,
                item.quantity,
                item.unit_price.amount,
                item.subtotal.amount,
            )
            for item in order.items
        ),
        tuple(evento.name for evento in order.events),
    )


def test_servicio_y_cargador_producen_el_mismo_estado():
    """Dos rutas de carga distintas no pueden divergir."""
    desde_servicio = load_orders()
    desde_cargador = load_fixture()
    assert list(desde_servicio) == list(desde_cargador)
    assert {
        oid: huella(order) for oid, order in desde_servicio.items()
    } == {
        oid: huella(order) for oid, order in desde_cargador.items()
    }


def test_load_orders_acepta_un_directorio_alternativo():
    """El servicio permite apuntar a otro directorio de fixtures."""
    alternativo = load_orders(DATA_DIR)
    assert len(alternativo) == 16
    assert alternativo["O001"].total.amount == Decimal("2100.00")
    assert alternativo["O006"].total.amount == Decimal("18000.00")


def test_catalogos_coinciden_con_los_csv():
    """Los catálogos exponen los 12 clientes y 12 productos del paquete."""
    productos = catalogo_productos()
    clientes = catalogo_clientes()
    assert len(productos) == 12
    assert len(clientes) == 12
    assert productos["SKU001"] == Decimal("600.00")
    assert clientes["C001"]["nombre"] == "Ana Torres"
    assert clientes["C003"]["activo"] == "0"


def test_health_responde_ok():
    """`GET /health` informa que el proceso está vivo y los fixtures cargados."""
    with TestClient(app) as client:
        respuesta = client.get("/health")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["pedidos_en_memoria"] == 16
    assert cuerpo["version"] == "1.0.0"


def test_reload_fixtures_restaura_el_estado():
    """La recarga descarta los cambios en memoria y vuelve a los 16 pedidos."""
    with TestClient(app) as client:
        confirmado = client.post("/orders/O013/confirm")
        assert confirmado.status_code == 200
        assert confirmado.json()["status"] == "CONFIRMED"

        recarga = client.post("/admin/reload-fixtures")
        assert recarga.status_code == 200
        assert recarga.json()["recargados"] == 16

        detalle = client.get("/orders/O013").json()
        assert detalle["status"] == "DRAFT"
        assert detalle["eventos"] == []
