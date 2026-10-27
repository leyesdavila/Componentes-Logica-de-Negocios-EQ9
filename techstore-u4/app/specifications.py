"""Reglas de negocio expresadas como Specifications — Unidad 4 (CLN).

Una *Specification* es un predicado sobre un pedido existente: responde
verdadero o falso y **nunca modifica** el pedido. Al combinarse con `&` (AND),
`|` (OR) y `~` (NOT) se pueden componer reglas sin duplicar código ni reglas.

Este módulo depende de `app.domain` (para `Money` y `Order`), nunca al revés:
el dominio no conoce las reglas de composición.

Reglas de descuento del negocio:

* **10 %**: cliente VIP, total > 500 MXN, >= 4 unidades y sin promoción.
* **5 %**: total > 5000 MXN y sin promoción.
* Si ambas se cumplen, se aplica primero el **10 %**.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from app.domain import Money, Order

#: Tasas de descuento soportadas.
TEN_PERCENT = Decimal("10")
FIVE_PERCENT = Decimal("5")
NO_DISCOUNT = Decimal("0")

#: Umbrales monetarios del negocio.
VIP_MINIMUM_AMOUNT = Decimal("500")
LARGE_ORDER_AMOUNT = Decimal("5000")

#: Mínimo de unidades para la regla del 10 %.
VIP_MINIMUM_UNITS = 4


# ---------------------------------------------------------------------------
# Patrón Specification
# ---------------------------------------------------------------------------


class Specification:
    """Predicado combinable sobre un pedido.

    Las subclases implementan `is_satisfied_by`; la combinación se hereda de
    aquí mediante los operadores de Python.
    """

    def is_satisfied_by(self, order: Order) -> bool:
        """`True` si el pedido cumple la regla."""
        raise NotImplementedError

    def __and__(self, other: "Specification") -> "AndSpec":
        """AND: ambas reglas deben cumplirse."""
        return AndSpec(self, other)

    def __or__(self, other: "Specification") -> "OrSpec":
        """OR: basta con que se cumpla una de las dos reglas."""
        return OrSpec(self, other)

    def __invert__(self) -> "NotSpec":
        """NOT: la regla debe ser incumplida."""
        return NotSpec(self)

    @property
    def description(self) -> str:
        """Descripción legible de la regla (para evidencia y respuestas de la API)."""
        return type(self).__name__


class AndSpec(Specification):
    """Conjunción: `left AND right`."""

    def __init__(self, left: Specification, right: Specification) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, order: Order) -> bool:
        return (
            self.left.is_satisfied_by(order)
            and self.right.is_satisfied_by(order)
        )

    @property
    def description(self) -> str:
        return f"({self.left.description} AND {self.right.description})"


class OrSpec(Specification):
    """Disyunción: `left OR right`."""

    def __init__(self, left: Specification, right: Specification) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, order: Order) -> bool:
        return (
            self.left.is_satisfied_by(order)
            or self.right.is_satisfied_by(order)
        )

    @property
    def description(self) -> str:
        return f"({self.left.description} OR {self.right.description})"


class NotSpec(Specification):
    """Negación: `NOT spec`."""

    def __init__(self, spec: Specification) -> None:
        self.spec = spec

    def is_satisfied_by(self, order: Order) -> bool:
        return not self.spec.is_satisfied_by(order)

    @property
    def description(self) -> str:
        return f"NOT {self.spec.description}"


# ---------------------------------------------------------------------------
# Reglas concretas del negocio
# ---------------------------------------------------------------------------


class MinimumAmountSpec(Specification):
    """El total del pedido debe **superar** el monto indicado.

    Usa `>` y no `>=`: un total exactamente igual al umbral no califica
    (caso O010: total 500.00 MXN).
    """

    def __init__(self, amount: Decimal) -> None:
        self.amount = Decimal(str(amount))

    def is_satisfied_by(self, order: Order) -> bool:
        return order.total.amount > self.amount

    @property
    def description(self) -> str:
        return f"total > {self.amount}"


class VIPCustomerSpec(Specification):
    """El cliente del pedido es VIP."""

    def is_satisfied_by(self, order: Order) -> bool:
        return order.customer.is_vip

    @property
    def description(self) -> str:
        return "cliente VIP"


class MinimumUnitsSpec(Specification):
    """El pedido debe tener **al menos** el mínimo de unidades indicado.

    Suma unidades, no renglones (caso O011: 3 unidades no califican).
    """

    def __init__(self, min_units: int = VIP_MINIMUM_UNITS) -> None:
        self.min_units = min_units

    def is_satisfied_by(self, order: Order) -> bool:
        return order.units >= self.min_units

    @property
    def description(self) -> str:
        return f"unidades >= {self.min_units}"


class ActivePromotionSpec(Specification):
    """El pedido tiene una promoción activa.

    Se usa siempre negada (`~ActivePromotionSpec()`) para expresar
    "sin promoción".
    """

    def is_satisfied_by(self, order: Order) -> bool:
        return order.has_promotion

    @property
    def description(self) -> str:
        return "promoción activa"


class ActiveCustomerSpec(Specification):
    """El cliente del pedido está activo (puede confirmar pedidos)."""

    def is_satisfied_by(self, order: Order) -> bool:
        return order.customer.active

    @property
    def description(self) -> str:
        return "cliente activo"


class HasItemsSpec(Specification):
    """El pedido tiene al menos un renglón."""

    def is_satisfied_by(self, order: Order) -> bool:
        return bool(order.items)

    @property
    def description(self) -> str:
        return "pedido con artículos"


# ---------------------------------------------------------------------------
# Reglas compuestas del negocio
# ---------------------------------------------------------------------------

#: Regla del 10 %: VIP + total > 500 + >= 4 unidades + sin promoción.
TEN_PERCENT_RULE = (
    MinimumAmountSpec(VIP_MINIMUM_AMOUNT)
    & VIPCustomerSpec()
    & MinimumUnitsSpec(VIP_MINIMUM_UNITS)
    & ~ActivePromotionSpec()
)

#: Regla del 5 %: total > 5000 y sin promoción.
FIVE_PERCENT_RULE = (
    MinimumAmountSpec(LARGE_ORDER_AMOUNT)
    & ~ActivePromotionSpec()
)

#: Combinación OR de ambas reglas: el pedido recibe descuento si cumple alguna.
DISCOUNT_RULE = TEN_PERCENT_RULE | FIVE_PERCENT_RULE

#: Precondiciones de confirmación, expresadas como especificación (diagnóstico).
CONFIRMABLE_RULE = ActiveCustomerSpec() & HasItemsSpec()


# ---------------------------------------------------------------------------
# Resolución del descuento
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscountResult:
    """Resultado de evaluar las reglas de descuento sobre un pedido."""

    percentage: Decimal
    rule: str
    total: Money
    discounted_total: Money

    @property
    def amount_saved(self) -> Money:
        """Importe ahorrado por el descuento."""
        return Money(self.total.amount - self.discounted_total.amount, self.total.currency)


def resolve_discount(order: Order) -> Decimal:
    """Porcentaje de descuento aplicable al pedido.

    La regla del 10 % tiene prioridad: si se cumplen ambas, se aplica primero
    el 10 %. `order.total` no se modifica; el descuento se calcula aparte.
    """
    if not DISCOUNT_RULE.is_satisfied_by(order):
        return NO_DISCOUNT
    if TEN_PERCENT_RULE.is_satisfied_by(order):
        return TEN_PERCENT
    return FIVE_PERCENT


def evaluate_discount(order: Order) -> DiscountResult:
    """Evalúa las reglas y devuelve el total con y sin descuento."""
    percentage = resolve_discount(order)
    total = order.total
    if percentage == TEN_PERCENT:
        rule = "10%"
    elif percentage == FIVE_PERCENT:
        rule = "5%"
    else:
        rule = "0%"
    return DiscountResult(
        percentage=percentage,
        rule=rule,
        total=total,
        discounted_total=total.apply_percentage(percentage),
    )


def evaluate_rules(order: Order) -> list[dict]:
    """Evalúa cada regla atómica y devuelve el detalle, regla por regla.

    Sirve como evidencia: muestra **por qué** un pedido recibe o no el
    descuento, en lugar de devolver solo el resultado.

    La etiqueta de cada fila es la `description` de la propia especificación:
    así el texto mostrado y el umbral realmente evaluado no pueden divergir
    si cambia una constante del negocio.
    """
    min_amount = MinimumAmountSpec(VIP_MINIMUM_AMOUNT)
    min_units = MinimumUnitsSpec(VIP_MINIMUM_UNITS)
    large_amount = MinimumAmountSpec(LARGE_ORDER_AMOUNT)
    checks: Iterable[Specification] = (
        min_amount,
        VIPCustomerSpec(),
        min_units,
        ~ActivePromotionSpec(),
        large_amount,
        ActiveCustomerSpec(),
        HasItemsSpec(),
    )
    return [
        {"regla": spec.description, "cumple": spec.is_satisfied_by(order)}
        for spec in checks
    ]
