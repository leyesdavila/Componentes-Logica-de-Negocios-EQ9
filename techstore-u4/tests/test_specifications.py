"""Pruebas del patrón Specification y de las reglas de descuento.

Complementan a `test_domain.py`: aquí cada Specification se prueba de forma
aislada y las combinaciones se verifican como **objetos** (AND/OR/NOT), no como
condicionales. Los pedidos se construyen en memoria para controlar los umbrales
exactos sin alterar los CSV del paquete.
"""

from decimal import Decimal

from app.domain import Customer, Money, Order, OrderItem
from app.specifications import (
    CONFIRMABLE_RULE,
    FIVE_PERCENT_RULE,
    TEN_PERCENT,
    TEN_PERCENT_RULE,
    ActiveCustomerSpec,
    ActivePromotionSpec,
    AndSpec,
    HasItemsSpec,
    MinimumAmountSpec,
    MinimumUnitsSpec,
    NotSpec,
    OrSpec,
    VIPCustomerSpec,
    evaluate_discount,
    evaluate_rules,
    resolve_discount,
)


def pedido(
    *,
    vip: bool = False,
    activo: bool = True,
    promo: bool = False,
    unidades: int = 4,
    precio: str = "600.00",
) -> Order:
    """Pedido de prueba con un solo renglón y los atributos indicados."""
    order = Order(
        customer=Customer("C-TEST", vip, activo),
        id="T001",
        has_promotion=promo,
    )
    order.add_item(
        OrderItem("SKU001", unidades, Money(Decimal(precio)))
    )
    return order


def test_umbral_de_monto_es_estricto():
    """`> 500`: 500.00 exacto no califica; 500.01 sí."""
    spec = MinimumAmountSpec(Decimal("500"))
    assert spec.is_satisfied_by(pedido(unidades=1, precio="500.00")) is False
    assert spec.is_satisfied_by(pedido(unidades=1, precio="500.01")) is True


def test_regla_vip_exige_cuatro_unidades():
    """La regla del 10 % cuenta unidades, no renglones."""
    tres = pedido(vip=True, unidades=3, precio="500.00")
    cuatro = pedido(vip=True, unidades=4, precio="500.00")
    assert TEN_PERCENT_RULE.is_satisfied_by(tres) is False
    assert TEN_PERCENT_RULE.is_satisfied_by(cuatro) is True


def test_promocion_activa_bloquea_ambas_reglas():
    """Una promoción activa excluye las dos reglas de descuento."""
    con_promo = pedido(vip=True, promo=True, unidades=5, precio="1200.00")
    sin_promo = pedido(vip=True, promo=False, unidades=5, precio="1200.00")
    assert TEN_PERCENT_RULE.is_satisfied_by(con_promo) is False
    assert FIVE_PERCENT_RULE.is_satisfied_by(con_promo) is False
    assert TEN_PERCENT_RULE.is_satisfied_by(sin_promo) is True


def test_prioridad_diez_sobre_cinco():
    """Si se cumplen ambas reglas, se aplica el 10 %, no el 5 %."""
    order = pedido(vip=True, unidades=5, precio="1200.00")  # 6000.00 MXN
    assert TEN_PERCENT_RULE.is_satisfied_by(order) is True
    assert FIVE_PERCENT_RULE.is_satisfied_by(order) is True
    resultado = evaluate_discount(order)
    assert resultado.percentage == TEN_PERCENT
    assert resultado.discounted_total.amount == Decimal("5400.00")
    assert resultado.amount_saved.amount == Decimal("600.00")


def test_composicion_and_or_not():
    """Los operadores `&`, `|` y `~` devuelven specifications componibles."""
    vip = pedido(vip=True, unidades=4)
    no_vip = pedido(vip=False, unidades=4)
    promo = pedido(vip=False, promo=True)

    and_spec = VIPCustomerSpec() & MinimumUnitsSpec(4)
    or_spec = VIPCustomerSpec() | MinimumUnitsSpec(4)
    not_spec = ~ActivePromotionSpec()

    assert isinstance(and_spec, AndSpec)
    assert isinstance(or_spec, OrSpec)
    assert isinstance(not_spec, NotSpec)
    assert and_spec.is_satisfied_by(vip) is True
    assert and_spec.is_satisfied_by(no_vip) is False
    assert or_spec.is_satisfied_by(no_vip) is True
    assert not_spec.is_satisfied_by(promo) is False


def test_descripciones_reflejan_los_umbrales():
    """La etiqueta se deriva de la specification, no se escribe aparte."""
    assert MinimumAmountSpec(Decimal("500")).description == "total > 500"
    assert MinimumUnitsSpec(4).description == "unidades >= 4"
    compuesta = VIPCustomerSpec() & MinimumUnitsSpec(4)
    assert compuesta.description == "(cliente VIP AND unidades >= 4)"


def test_evaluate_rules_devuelve_siete_reglas():
    """El diagnóstico regla por regla conserva orden y etiquetas."""
    filas = evaluate_rules(pedido(vip=True, unidades=4))
    assert len(filas) == 7
    assert [fila["regla"] for fila in filas] == [
        "total > 500",
        "cliente VIP",
        "unidades >= 4",
        "NOT promoción activa",
        "total > 5000",
        "cliente activo",
        "pedido con artículos",
    ]
    assert all(isinstance(fila["cumple"], bool) for fila in filas)


def test_el_descuento_no_modifica_el_total_bruto():
    """`order.total` conserva el importe bruto; el descuento va aparte."""
    order = pedido(vip=True, unidades=4, precio="525.00")  # 2100.00 MXN
    antes = order.total.amount
    resultado = evaluate_discount(order)
    assert order.total.amount == antes == Decimal("2100.00")
    assert resultado.discounted_total.amount == Decimal("1890.00")
    assert order.status.value == "DRAFT"
    assert order.events == []


def test_confirmable_rule_detecta_inactivo_y_vacio():
    """`CONFIRMABLE_RULE` reúne las dos precondiciones de confirmación."""
    activo = pedido(activo=True)
    inactivo = pedido(activo=False)
    vacio = Order(customer=Customer("C-TEST", False, True), id="T002")
    assert CONFIRMABLE_RULE.is_satisfied_by(activo) is True
    assert CONFIRMABLE_RULE.is_satisfied_by(inactivo) is False
    assert CONFIRMABLE_RULE.is_satisfied_by(vacio) is False
    assert ActiveCustomerSpec().is_satisfied_by(activo) is True
    assert HasItemsSpec().is_satisfied_by(vacio) is False


def test_resolve_discount_devuelve_cero_sin_reglas():
    """Sin VIP, sin monto alto y sin promoción, el descuento es 0 %."""
    order = pedido(vip=False, unidades=2, precio="500.00")  # 1000.00 MXN
    assert resolve_discount(order) == Decimal("0")
