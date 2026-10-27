"""Pruebas del núcleo de dominio — sección 12 de la práctica guiada.

Organizadas en tres partes, como pide el PDF: **preparar** los datos, **ejecutar**
la acción y **comprobar** el resultado.

Cobertura exigida por la sección 12: Money negativo, 21 unidades, cliente
inactivo, pedido vacío, descuento VIP, promoción activa, envío sin guía,
confirmación doble y cancelación desde SHIPPED. Además se cubren los
comparadores de frontera (`>` 500, `>= 4` unidades, 20 unidades) y la
composición de Specifications con AND, OR y NOT.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.domain import (
    Customer,
    InvalidOrderData,
    InvalidOrderTransition,
    Money,
    Order,
    OrderItem,
    OrderItemLimitExceeded,
    OrderStatus,
)
from app.specifications import (
    ActivePromotionSpec,
    AndSpec,
    CONFIRMABLE_RULE,
    DISCOUNT_RULE,
    FIVE_PERCENT_RULE,
    MinimumAmountSpec,
    MinimumUnitsSpec,
    NotSpec,
    OrSpec,
    Specification,
    TEN_PERCENT_RULE,
    VIPCustomerSpec,
    evaluate_discount,
    resolve_discount,
)
from cargar_csv import load_fixture


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


def test_money_negativo():
    """El PDF: `Money(Decimal("-1"))` debe lanzar `InvalidOrderData`."""
    with pytest.raises(InvalidOrderData):
        Money(Decimal("-1"))


def test_money_no_finito():
    for valor in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(InvalidOrderData):
            Money(valor)


def test_money_rechaza_monedas_distintas_al_sumar():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("10.00")).add(Money(Decimal("10.00"), "USD"))


def test_money_add_devuelve_un_objeto_nuevo():
    original = Money(Decimal("600.00"))
    suma = original.add(Money(Decimal("450.00")))
    assert suma.amount == Decimal("1050.00")
    assert original.amount == Decimal("600.00")  # el original no cambió
    assert suma is not original


def test_money_es_inmutable():
    dinero = Money(Decimal("600.00"))
    with pytest.raises(FrozenInstanceError):
        dinero.amount = Decimal("1.00")


def test_money_convierte_float_a_decimal_sin_deriva_binaria():
    """`Decimal(str(19.99))` evita el error binario de construir desde float."""
    dinero = Money(19.99)
    assert isinstance(dinero.amount, Decimal)
    assert dinero.amount == Decimal("19.99")
    # Un float no representa 19.99 de forma exacta; la conversión por texto sí.
    assert Decimal(19.99) != Decimal(str(19.99))
    assert dinero.amount == Decimal(str(19.99))


def test_money_apply_percentage_redondea_a_centavos():
    assert Money(Decimal("2100.00")).apply_percentage(Decimal("10")).amount == Decimal(
        "1890.00"
    )
    assert Money(Decimal("18000.00")).apply_percentage(Decimal("5")).amount == Decimal(
        "17100.00"
    )
    assert Money(Decimal("0.00")).apply_percentage(Decimal("10")).amount == Decimal("0.00")


# ---------------------------------------------------------------------------
# OrderItem
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sku", "cantidad"),
    [("", 1), ("   ", 1), ("SKU001", 0), ("SKU001", -3)],
)
def test_order_item_invalido(sku, cantidad):
    with pytest.raises(InvalidOrderData):
        OrderItem(sku, cantidad, Money(Decimal("600.00")))


def test_order_item_subtotal_se_calcula():
    item = OrderItem("SKU001", 2, Money(Decimal("600.00")))
    assert item.subtotal.amount == Decimal("1200.00")


# ---------------------------------------------------------------------------
# Order: unidades, total y renglones
# ---------------------------------------------------------------------------


def test_pedido_o001_inicia_draft():
    """El PDF: O001 tiene 4 unidades y 2100.00 MXN."""
    orders = load_fixture()
    assert orders["O001"].status.value == "DRAFT"
    assert orders["O001"].units == 4
    assert orders["O001"].total.amount == Decimal("2100.00")


def test_unidades_suman_cantidades_y_no_renglones():
    """O008 tiene 1 renglón pero 20 unidades; O007 no tiene ninguno."""
    orders = load_fixture()
    assert len(orders["O008"].items) == 1
    assert orders["O008"].units == 20
    assert len(orders["O007"].items) == 0
    assert orders["O007"].units == 0


def test_total_suma_los_subtotales():
    orders = load_fixture()
    total = orders["O001"].total
    assert total.amount == Decimal("1200.00") + Decimal("900.00")
    assert total.currency == "MXN"


def test_add_item_rechaza_mas_de_20_unidades():
    """E08: 19 unidades + 2 = 21 -> `OrderItemLimitExceeded` sin mutar el pedido."""
    order = load_fixture()["O009"]
    with pytest.raises(OrderItemLimitExceeded):
        order.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))
    assert order.units == 19
    assert len(order.items) == 1


def test_add_item_acepta_exactamente_20_unidades():
    """E07: 20 unidades en un solo renglón están permitidas."""
    order = load_fixture()["O008"]
    assert order.units == 20
    with pytest.raises(OrderItemLimitExceeded):
        order.add_item(OrderItem("SKU003", 1, Money(Decimal("120.00"))))
    assert order.units == 20


def test_add_item_rechaza_monedas_distintas():
    order = load_fixture()["O013"]
    with pytest.raises(InvalidOrderData):
        order.add_item(OrderItem("SKU001", 1, Money(Decimal("600.00"), "USD")))


def test_add_item_solo_en_draft():
    order = load_fixture()["O013"]
    order.confirm()
    with pytest.raises(InvalidOrderTransition):
        order.add_item(OrderItem("SKU001", 1, Money(Decimal("600.00"))))


def test_is_empty_refleja_si_el_pedido_tiene_renglones():
    """`is_empty` es la consulta que usa la especificación de confirmación."""
    vacio = load_fixture()["O007"]
    lleno = load_fixture()["O001"]
    assert vacio.is_empty is True
    assert lleno.is_empty is False


# ---------------------------------------------------------------------------
# Reglas de confirmación
# ---------------------------------------------------------------------------


def test_confirmable_rule_exige_cliente_activo_y_articulos():
    """La especificación de confirmación resume las dos precondiciones."""
    # E03: cliente inactivo -> no confirmable
    assert CONFIRMABLE_RULE.is_satisfied_by(load_fixture()["O003"]) is False
    # E06: pedido sin artículos -> no confirmable
    assert CONFIRMABLE_RULE.is_satisfied_by(load_fixture()["O007"]) is False
    # E07: cliente activo y con artículos -> confirmable
    assert CONFIRMABLE_RULE.is_satisfied_by(load_fixture()["O008"]) is True


def test_cliente_inactivo_no_puede_confirmar():
    """E03: el cliente C003 está inactivo."""
    order = load_fixture()["O003"]
    with pytest.raises(InvalidOrderData):
        order.confirm()
    assert order.status is OrderStatus.DRAFT
    assert order.events == []


def test_pedido_vacio_no_puede_confirmar():
    """E06: el pedido O007 no tiene artículos."""
    order = load_fixture()["O007"]
    with pytest.raises(InvalidOrderData):
        order.confirm()
    assert order.status is OrderStatus.DRAFT
    assert order.events == []


def test_confirmacion_doble_es_rechazada_y_no_agrega_eventos():
    """E12: la segunda confirmación lanza `InvalidOrderTransition`."""
    order = load_fixture()["O013"]
    order.confirm()
    with pytest.raises(InvalidOrderTransition):
        order.confirm()
    assert order.status is OrderStatus.CONFIRMED
    assert len(order.events) == 1


def test_envio_sin_guia_es_rechazado():
    """E11: la guía de envío es obligatoria."""
    order = load_fixture()["O012"]
    order.confirm()
    with pytest.raises(InvalidOrderData):
        order.ship("")
    assert order.status is OrderStatus.CONFIRMED
    assert order.tracking_number is None
    assert [e.name for e in order.events] == ["OrderConfirmed"]


def test_cancelacion_desde_shipped_es_rechazada():
    """E13: cancelar solo se permite desde CONFIRMED."""
    order = load_fixture()["O014"]
    order.confirm()
    order.ship("GUIA-TEST-01")
    with pytest.raises(InvalidOrderTransition):
        order.cancel("motivo")
    assert order.status is OrderStatus.SHIPPED
    assert order.cancel_reason is None
    assert [e.name for e in order.events] == ["OrderConfirmed", "OrderShipped"]


def test_transicion_valida_emite_el_evento_correspondiente():
    order = load_fixture()["O016"]
    order.confirm()
    order.ship("GUIA-TEST-02")
    order.deliver()
    assert order.status is OrderStatus.DELIVERED
    assert [e.name for e in order.events] == [
        "OrderConfirmed",
        "OrderShipped",
        "OrderDelivered",
    ]


# ---------------------------------------------------------------------------
# Descuentos
# ---------------------------------------------------------------------------


def test_descuento_vip_de_10_por_ciento():
    """E01: O001 es VIP, 2100.00 > 500, 4 unidades y sin promoción."""
    order = load_fixture()["O001"]
    resultado = evaluate_discount(order)
    assert resultado.percentage == Decimal("10")
    assert resultado.discounted_total.amount == Decimal("1890.00")


def test_amount_saved_es_la_diferencia_entre_el_total_y_el_total_con_descuento():
    """El ahorro es el importe efectivamente restado al cliente."""
    resultado = evaluate_discount(load_fixture()["O001"])
    assert resultado.amount_saved.amount == Decimal("210.00")
    assert resultado.amount_saved.currency == "MXN"
    assert (
        resultado.total.amount - resultado.amount_saved.amount
        == resultado.discounted_total.amount
    )


def test_promocion_activa_excluye_el_descuento():
    """E04: O005 cumple todas las condiciones salvo la promoción."""
    order = load_fixture()["O005"]
    assert order.has_promotion is True
    assert resolve_discount(order) == Decimal("0")


def test_descuento_de_5_por_ciento_para_totales_mayores_a_5000():
    """E05: O006 suma 18000.00 y no tiene promoción."""
    order = load_fixture()["O006"]
    resultado = evaluate_discount(order)
    assert resultado.percentage == Decimal("5")
    assert resultado.discounted_total.amount == Decimal("17100.00")


def test_umbral_estricto_de_500():
    """E09: un total de exactamente 500.00 no supera el umbral."""
    order = load_fixture()["O010"]
    assert order.total.amount == Decimal("500.00")
    assert resolve_discount(order) == Decimal("0")


def test_se_requieren_cuatro_unidades():
    """E10: O011 tiene 3 unidades y no califica."""
    order = load_fixture()["O011"]
    assert order.units == 3
    assert resolve_discount(order) == Decimal("0")


def test_prioridad_del_10_por_ciento_sobre_el_5_por_ciento():
    """Si se cumplen ambas reglas, aplica el 10 %.

    Ningún pedido del paquete cumple las dos condiciones a la vez (el único con
    total > 5000 es O006 y su cliente no es VIP), así que el caso se construye
    en memoria. No se modifica ningún CSV.
    """
    pedido = Order(customer=Customer("C999", is_vip=True, active=True), id="T001")
    pedido.add_item(OrderItem("SKU005", 3, Money(Decimal("3200.00"))))  # 9600.00
    pedido.add_item(OrderItem("SKU003", 1, Money(Decimal("120.00"))))  # 120.00

    assert pedido.units == 4
    assert pedido.total.amount == Decimal("9720.00")
    assert TEN_PERCENT_RULE.is_satisfied_by(pedido)
    assert FIVE_PERCENT_RULE.is_satisfied_by(pedido)
    assert DISCOUNT_RULE.is_satisfied_by(pedido)

    assert resolve_discount(pedido) == Decimal("10")
    assert evaluate_discount(pedido).discounted_total.amount == Decimal("8748.00")


def test_el_mismo_pedido_sin_vip_recibe_5_por_ciento():
    """Control del caso anterior: sin VIP solo aplica la regla del 5 %."""
    pedido = Order(customer=Customer("C998", is_vip=False, active=True), id="T002")
    pedido.add_item(OrderItem("SKU005", 3, Money(Decimal("3200.00"))))
    pedido.add_item(OrderItem("SKU003", 1, Money(Decimal("120.00"))))

    assert not TEN_PERCENT_RULE.is_satisfied_by(pedido)
    assert FIVE_PERCENT_RULE.is_satisfied_by(pedido)
    assert resolve_discount(pedido) == Decimal("5")


# ---------------------------------------------------------------------------
# Composición de Specifications
# ---------------------------------------------------------------------------


def test_specification_base_no_se_puede_evaluar():
    with pytest.raises(NotImplementedError):
        Specification().is_satisfied_by(load_fixture()["O001"])


def test_composicion_and_or_not():
    orders = load_fixture()
    o001 = orders["O001"]
    o002 = orders["O002"]

    vip = VIPCustomerSpec()
    monto = MinimumAmountSpec(Decimal("500"))
    unidades = MinimumUnitsSpec(4)

    assert (vip & monto).is_satisfied_by(o001) is True
    assert (vip & unidades).is_satisfied_by(o002) is False
    assert (vip | unidades).is_satisfied_by(o001) is True
    assert (vip | unidades).is_satisfied_by(o002) is False
    assert (~vip).is_satisfied_by(o002) is True
    assert (~vip).is_satisfied_by(o001) is False

    assert isinstance(vip & monto, AndSpec)
    assert isinstance(vip | monto, OrSpec)
    assert isinstance(~vip, NotSpec)


def test_active_promotion_spec_se_usa_negada():
    orders = load_fixture()
    assert ActivePromotionSpec().is_satisfied_by(orders["O005"]) is True
    assert (~ActivePromotionSpec()).is_satisfied_by(orders["O005"]) is False
    assert (~ActivePromotionSpec()).is_satisfied_by(orders["O001"]) is True


def test_la_specification_no_modifica_el_pedido():
    """Una Specification es un predicado: solo observa."""
    order = load_fixture()["O001"]
    estado_previo = order.status
    items_previos = list(order.items)
    eventos_previos = list(order.events)

    DISCOUNT_RULE.is_satisfied_by(order)
    TEN_PERCENT_RULE.is_satisfied_by(order)
    evaluate_discount(order)

    assert order.status is estado_previo
    assert order.items == items_previos
    assert order.events == eventos_previos
    assert order.total.amount == Decimal("2100.00")
