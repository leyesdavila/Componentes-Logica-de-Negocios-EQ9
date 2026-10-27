"""Máquina de estados y Domain Events — sección 9 de la práctica guiada.

Demuestra el recorrido completo del pedido y comprueba la regla central:
*una operación inválida no cambia el estado ni agrega eventos*.
"""

from decimal import Decimal

import pytest

from app.domain import (
    InvalidOrderData,
    InvalidOrderTransition,
    Money,
    OrderItem,
    OrderItemLimitExceeded,
    OrderStatus,
)
from cargar_csv import load_fixture


def eventos(order) -> list[str]:
    """Nombres de los eventos registrados en el pedido."""
    return [e.name for e in order.events]


# ---------------------------------------------------------------------------
# Recorrido válido
# ---------------------------------------------------------------------------


def test_todos_los_pedidos_inician_en_draft():
    orders = load_fixture()
    assert len(orders) == 16
    assert all(o.status is OrderStatus.DRAFT for o in orders.values())
    assert all(o.events == [] for o in orders.values())


def test_confirm_emite_order_confirmed():
    order = load_fixture()["O013"]
    order.confirm()
    assert order.status is OrderStatus.CONFIRMED
    assert eventos(order) == ["OrderConfirmed"]
    assert order.events[0].order_id == "O013"
    assert order.events[0].occurred_at.tzinfo is not None


def test_ciclo_completo_confirmar_enviar_entregar():
    order = load_fixture()["O016"]
    order.confirm()
    order.ship("GUIA-ENTREGA-01")
    order.deliver()
    assert order.status is OrderStatus.DELIVERED
    assert eventos(order) == ["OrderConfirmed", "OrderShipped", "OrderDelivered"]
    assert order.tracking_number == "GUIA-ENTREGA-01"


def test_ciclo_completo_confirmar_enviar_devolver():
    order = load_fixture()["O015"]
    order.confirm()
    order.ship("GUIA-DEVOLUCION-01")
    order.return_order()
    assert order.status is OrderStatus.RETURNED
    assert eventos(order) == ["OrderConfirmed", "OrderShipped", "OrderReturned"]


def test_cancelacion_desde_confirmed():
    order = load_fixture()["O014"]
    order.confirm()
    order.cancel("El cliente cambió de opinión")
    assert order.status is OrderStatus.CANCELLED
    assert order.cancel_reason == "El cliente cambió de opinión"
    assert eventos(order) == ["OrderConfirmed", "OrderCancelled"]


# ---------------------------------------------------------------------------
# Transiciones prohibidas: el estado y los eventos quedan intactos
# ---------------------------------------------------------------------------


def _nada(order):
    """Precondición: el pedido sigue en DRAFT."""


def _confirmado(order):
    order.confirm()


def _enviado(order):
    order.confirm()
    order.ship("GUIA-ORIGEN")


def _entregado(order):
    order.confirm()
    order.ship("GUIA-ORIGEN")
    order.deliver()


@pytest.mark.parametrize(
    ("preparacion", "accion", "excepcion"),
    [
        # Transiciones que la máquina de estados no permite.
        (_confirmado, lambda o: o.confirm(), InvalidOrderTransition),
        (_nada, lambda o: o.ship("GUIA-X"), InvalidOrderTransition),
        (_nada, lambda o: o.cancel("motivo"), InvalidOrderTransition),
        (_confirmado, lambda o: o.deliver(), InvalidOrderTransition),
        (_confirmado, lambda o: o.return_order(), InvalidOrderTransition),
        (_enviado, lambda o: o.cancel("motivo"), InvalidOrderTransition),
        (_entregado, lambda o: o.deliver(), InvalidOrderTransition),
        (_entregado, lambda o: o.return_order(), InvalidOrderTransition),
        # Datos obligatorios que faltan.
        (_confirmado, lambda o: o.ship(""), InvalidOrderData),
        (_confirmado, lambda o: o.ship("   "), InvalidOrderData),
        (_confirmado, lambda o: o.cancel(""), InvalidOrderData),
        (_confirmado, lambda o: o.cancel("   "), InvalidOrderData),
    ],
)
def test_operaciones_invalidas_no_cambian_estado_ni_eventos(preparacion, accion, excepcion):
    """Ninguna operación inválida deja rastro en el pedido."""
    order = load_fixture()["O014"]
    preparacion(order)
    estado_previo = order.status
    eventos_previos = eventos(order)

    with pytest.raises(excepcion):
        accion(order)

    assert order.status is estado_previo
    assert eventos(order) == eventos_previos


def test_confirmacion_doble_no_agrega_evento():
    """Ejercicio de la sección 9: con O013, la segunda confirmación se rechaza."""
    order = load_fixture()["O013"]
    order.confirm()
    assert order.status is OrderStatus.CONFIRMED
    assert len(order.events) == 1

    with pytest.raises(InvalidOrderTransition):
        order.confirm()

    assert order.status is OrderStatus.CONFIRMED
    assert len(order.events) == 1
    assert eventos(order) == ["OrderConfirmed"]


def test_no_se_pueden_agregar_articulos_a_un_pedido_confirmado():
    order = load_fixture()["O013"]
    order.confirm()
    renglones_previos = list(order.items)

    with pytest.raises(InvalidOrderTransition):
        order.add_item(OrderItem("SKU001", 1, Money(Decimal("600.00"))))

    assert order.items == renglones_previos
    assert order.units == 1
    assert eventos(order) == ["OrderConfirmed"]


def test_limite_de_unidades_no_modifica_el_pedido():
    """O009 tiene 19 unidades; agregar 2 dejaría 21 y debe rechazarse."""
    order = load_fixture()["O009"]
    renglones_previos = len(order.items)

    with pytest.raises(OrderItemLimitExceeded):
        order.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))

    assert len(order.items) == renglones_previos
    assert order.units == 19


# ---------------------------------------------------------------------------
# Demostración para la evidencia del reporte
# ---------------------------------------------------------------------------


def test_demostracion_maquina_de_estados():
    """Recorre los caminos de la máquina de estados y los imprime como evidencia."""
    print("\n=== MAQUINA DE ESTADOS Y DOMAIN EVENTS ===")

    pedido = load_fixture()["O015"]
    print(f"{'DRAFT (inicial)':<34}{pedido.status.value} | eventos: {eventos(pedido)}")

    pedido.confirm()
    print(f"{'-> confirm()':<34}{pedido.status.value} | eventos: {eventos(pedido)}")

    pedido.ship("GUIA-DEMO-01")
    print(f"{'-> ship(GUIA-DEMO-01)':<34}{pedido.status.value} | eventos: {eventos(pedido)}")

    pedido.return_order()
    print(f"{'-> return_order()':<34}{pedido.status.value} | eventos: {eventos(pedido)}")

    otro = load_fixture()["O013"]
    otro.confirm()
    try:
        otro.confirm()
    except InvalidOrderTransition as exc:
        print(f"{'-> confirm() (2a vez)':<34}RECHAZADO: {exc} | eventos: {eventos(otro)}")

    tercero = load_fixture()["O014"]
    tercero.confirm()
    tercero.ship("GUIA-DEMO-02")
    try:
        tercero.cancel("intento fallido")
    except InvalidOrderTransition as exc:
        print(
            f"{'-> cancel() desde SHIPPED':<34}RECHAZADO: {exc} | estado: {tercero.status.value} "
            f"| eventos: {eventos(tercero)}"
        )
