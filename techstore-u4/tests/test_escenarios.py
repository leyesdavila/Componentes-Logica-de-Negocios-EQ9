"""Escenarios E01–E15 — sección 10 de la práctica guiada.

Cada prueba ejecuta **un** escenario del archivo `datos/escenarios.csv` usando
objetos recién cargados con `load_fixture()`, y verifica el resultado esperado.

Reglas de ejecución (README.txt del paquete):

* No se modifica ningún CSV ni ningún pedido para forzar que un caso pase.
* Los datos se recargan antes de cada escenario, porque varios escenarios
  modifican el estado del mismo pedido base (O012–O016) y las transiciones no
  se pueden repetir sobre un pedido ya avanzado.
"""

from decimal import Decimal

import pytest

from app.domain import (
    InvalidOrderData,
    InvalidOrderTransition,
    Money,
    OrderItem,
    OrderItemLimitExceeded,
)
from app.specifications import evaluate_discount, resolve_discount
from cargar_csv import load_fixture, rows

#: Precio del catálogo, leído de `datos/productos.csv` (no codificado a mano).
PRECIO_SKU003 = Decimal(
    next(r["precio_mxn"] for r in rows("productos.csv") if r["sku"] == "SKU003")
)


def bitacora(caso, estado_inicial, operacion, resultado, explicacion, evento):
    """Imprime la fila de la bitácora del escenario."""
    print(
        f"{caso} | {estado_inicial} | {operacion} | {resultado} | {explicacion} | {evento}"
    )


# ---------------------------------------------------------------------------
# E01–E05  Descuentos, VIP y promoción activa
# ---------------------------------------------------------------------------


def test_e01_o001_descuento_10_por_ciento():
    """O001: VIP, total > 500, 4 unidades y sin promoción -> 10 %."""
    order = load_fixture()["O001"]
    resultado = evaluate_discount(order)

    assert resultado.percentage == Decimal("10")
    assert resultado.total.amount == Decimal("2100.00")
    assert resultado.discounted_total.amount == Decimal("1890.00")

    bitacora(
        "E01", "DRAFT", "evaluate_discount(O001)", "10% (1890.00 MXN)",
        "VIP + total 2100.00 > 500 + 4 unidades >= 4 + sin promoción",
        "n/a (no es transición de estado)",
    )


def test_e02_o002_sin_descuento():
    """O002: no es VIP y tiene 2 unidades -> 0 %."""
    order = load_fixture()["O002"]
    resultado = evaluate_discount(order)

    assert resultado.percentage == Decimal("0")
    assert resultado.total.amount == Decimal("1050.00")
    assert resultado.discounted_total.amount == Decimal("1050.00")

    bitacora(
        "E02", "DRAFT", "evaluate_discount(O002)", "0% (1050.00 MXN)",
        "No cumple VIP ni unidades >= 4; tampoco supera 5000",
        "n/a (no es transición de estado)",
    )


def test_e03_o003_confirmar_rechazado_cliente_inactivo():
    """O003: el cliente es VIP pero está inactivo -> confirmar se rechaza."""
    order = load_fixture()["O003"]

    with pytest.raises(InvalidOrderData):
        order.confirm()

    assert order.status.value == "DRAFT"
    assert order.events == []

    bitacora(
        "E03", "DRAFT", "confirm()", "RECHAZADO (InvalidOrderData)",
        "El cliente C003 está inactivo: un pedido no puede confirmarse",
        "ninguno (la operación falló)",
    )


def test_e04_o005_promocion_activa_excluye_descuento():
    """O005: cumple VIP, monto y unidades, pero tiene promoción -> 0 %."""
    order = load_fixture()["O005"]
    resultado = evaluate_discount(order)

    assert order.has_promotion is True
    assert resultado.percentage == Decimal("0")
    assert resultado.total.amount == Decimal("2100.00")

    bitacora(
        "E04", "DRAFT", "evaluate_discount(O005)", "0% (2100.00 MXN)",
        "La promoción activa bloquea las dos reglas de descuento",
        "n/a (no es transición de estado)",
    )


def test_e05_o006_descuento_5_por_ciento():
    """O006: total 18000.00 > 5000 y sin promoción -> 5 %."""
    order = load_fixture()["O006"]
    resultado = evaluate_discount(order)

    assert resultado.percentage == Decimal("5")
    assert resultado.total.amount == Decimal("18000.00")
    assert resultado.discounted_total.amount == Decimal("17100.00")

    bitacora(
        "E05", "DRAFT", "evaluate_discount(O006)", "5% (17100.00 MXN)",
        "Total > 5000 y sin promoción; no es VIP, así que no aplica el 10 %",
        "n/a (no es transición de estado)",
    )


# ---------------------------------------------------------------------------
# E06–E10  Pedido vacío, límite de 20 y valores frontera
# ---------------------------------------------------------------------------


def test_e06_o007_confirmar_rechazado_pedido_vacio():
    """O007: el pedido no tiene renglones -> confirmar se rechaza."""
    order = load_fixture()["O007"]

    assert order.items == []
    assert order.units == 0

    with pytest.raises(InvalidOrderData):
        order.confirm()

    assert order.status.value == "DRAFT"
    assert order.events == []

    bitacora(
        "E06", "DRAFT", "confirm()", "RECHAZADO (InvalidOrderData)",
        "El pedido no tiene artículos: se requieren renglones para confirmar",
        "ninguno (la operación falló)",
    )


def test_e07_o008_confirmar_exito_con_20_unidades():
    """O008: 20 unidades exactas están permitidas -> confirmar es válido."""
    order = load_fixture()["O008"]

    assert order.units == 20
    order.confirm()

    assert order.status.value == "CONFIRMED"
    assert [e.name for e in order.events] == ["OrderConfirmed"]

    bitacora(
        "E07", "DRAFT", "confirm()", "CONFIRMED",
        "20 unidades exactas: el límite es 20 y no se excede",
        "OrderConfirmed",
    )


def test_e08_o009_agregar_21_unidades_rechazado():
    """O009: 19 unidades + 2 = 21 -> excede el límite y no modifica el pedido."""
    order = load_fixture()["O009"]
    renglones_previos = len(order.items)

    assert order.units == 19

    with pytest.raises(OrderItemLimitExceeded):
        order.add_item(OrderItem("SKU003", 2, Money(PRECIO_SKU003)))

    assert len(order.items) == renglones_previos
    assert order.units == 19
    assert order.status.value == "DRAFT"
    assert order.events == []

    bitacora(
        "E08", "DRAFT", "add_item(SKU003 x2)", "RECHAZADO (OrderItemLimitExceeded)",
        "19 + 2 = 21 unidades: el máximo es 20 unidades, no 20 renglones",
        "ninguno (la operación falló)",
    )


def test_e09_o010_total_500_sin_descuento():
    """O010: total exactamente 500.00 -> no supera el umbral, no hay descuento."""
    order = load_fixture()["O010"]
    resultado = evaluate_discount(order)

    assert order.total.amount == Decimal("500.00")
    assert resultado.percentage == Decimal("0")
    assert resolve_discount(order) == Decimal("0")

    bitacora(
        "E09", "DRAFT", "evaluate_discount(O010)", "0% (500.00 MXN)",
        "El total es exactamente 500 y la regla exige > 500, no >= 500",
        "n/a (no es transición de estado)",
    )


def test_e10_o011_tres_unidades_sin_descuento():
    """O011: VIP y total 1500.00, pero solo 3 unidades -> 0 %."""
    order = load_fixture()["O011"]
    resultado = evaluate_discount(order)

    assert order.units == 3
    assert resultado.percentage == Decimal("0")
    assert resultado.total.amount == Decimal("1500.00")

    bitacora(
        "E10", "DRAFT", "evaluate_discount(O011)", "0% (1500.00 MXN)",
        "La regla del 10 % exige >= 4 unidades y este pedido tiene 3",
        "n/a (no es transición de estado)",
    )


# ---------------------------------------------------------------------------
# E11–E13  Guía obligatoria y transiciones prohibidas
# ---------------------------------------------------------------------------


def test_e11_o012_enviar_sin_guia_rechazado():
    """O012: confirmar es válido, pero enviar sin guía se rechaza."""
    order = load_fixture()["O012"]

    order.confirm()
    assert order.status.value == "CONFIRMED"

    with pytest.raises(InvalidOrderData):
        order.ship("")

    assert order.status.value == "CONFIRMED"
    assert [e.name for e in order.events] == ["OrderConfirmed"]
    assert order.tracking_number is None

    bitacora(
        "E11", "DRAFT", "confirm() y ship('')", "CONFIRMADO, envío RECHAZADO",
        "La guía de envío es obligatoria: la transición no se ejecuta",
        "OrderConfirmed (ninguno por el envío fallido)",
    )


def test_e12_o013_confirmar_dos_veces_rechazada_la_segunda():
    """O013: la segunda confirmación se rechaza y no agrega otro evento."""
    order = load_fixture()["O013"]

    order.confirm()
    assert order.status.value == "CONFIRMED"
    assert len(order.events) == 1

    with pytest.raises(InvalidOrderTransition):
        order.confirm()

    assert order.status.value == "CONFIRMED"
    assert len(order.events) == 1
    assert [e.name for e in order.events] == ["OrderConfirmed"]

    bitacora(
        "E12", "DRAFT", "confirm() dos veces", "2.a RECHAZADA (InvalidOrderTransition)",
        "No se permite confirmar desde CONFIRMED",
        "OrderConfirmed (solo uno; el rechazo no registra evento)",
    )


def test_e13_o014_cancelar_desde_shipped_rechazado():
    """O014: confirmar y enviar son válidos; cancelar desde SHIPPED no lo es."""
    order = load_fixture()["O014"]

    order.confirm()
    order.ship("GUIA-E13-01")
    assert order.status.value == "SHIPPED"

    with pytest.raises(InvalidOrderTransition):
        order.cancel("El cliente se arrepintió")

    assert order.status.value == "SHIPPED"
    assert [e.name for e in order.events] == ["OrderConfirmed", "OrderShipped"]
    assert order.cancel_reason is None

    bitacora(
        "E13", "DRAFT", "confirm(), ship() y cancel()", "enviado, cancelación RECHAZADA",
        "Solo se permite cancelar desde CONFIRMED, no desde SHIPPED",
        "OrderConfirmed, OrderShipped (ninguno por la cancelación fallida)",
    )


# ---------------------------------------------------------------------------
# E14–E15  Devolución y entrega válidas
# ---------------------------------------------------------------------------


def test_e14_o015_devolucion_desde_shipped():
    """O015: confirmar, enviar y devolver -> RETURNED."""
    order = load_fixture()["O015"]

    order.confirm()
    order.ship("GUIA-E14-01")
    order.return_order()

    assert order.status.value == "RETURNED"
    assert [e.name for e in order.events] == [
        "OrderConfirmed",
        "OrderShipped",
        "OrderReturned",
    ]

    bitacora(
        "E14", "DRAFT", "confirm(), ship() y return_order()", "RETURNED",
        "La devolución se permite desde SHIPPED",
        "OrderConfirmed, OrderShipped, OrderReturned",
    )


def test_e15_o016_entrega_desde_shipped():
    """O016: confirmar, enviar y entregar -> DELIVERED."""
    order = load_fixture()["O016"]

    order.confirm()
    order.ship("GUIA-E15-01")
    order.deliver()

    assert order.status.value == "DELIVERED"
    assert [e.name for e in order.events] == [
        "OrderConfirmed",
        "OrderShipped",
        "OrderDelivered",
    ]

    bitacora(
        "E15", "DRAFT", "confirm(), ship() y deliver()", "DELIVERED",
        "La entrega se permite desde SHIPPED",
        "OrderConfirmed, OrderShipped, OrderDelivered",
    )
