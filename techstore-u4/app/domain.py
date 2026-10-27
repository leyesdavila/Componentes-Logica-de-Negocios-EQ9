"""Núcleo de dominio TechStore — Unidad 4 (Componentes de Lógica de Negocio).

Este módulo no depende de FastAPI, de pytest ni de ningún detalle de infraestructura:
contiene las entidades, los value objects, las invariantes y la máquina de estados del
negocio de pedidos. `cargar_csv.py` y `app/api.py` solo dependen de este módulo.

Conceptos del mapa de dominio:

* **Value Objects** (`Money`, `OrderItem`): sin identidad propia, inmutables y comparables
  por valor. Una vez creados, no cambian: sus atributos se derivan.
* **Entidades** (`Customer`, `Order`): con identidad (`id`) y ciclo de vida propio.
* **Aggregate Root** (`Order`): punto único de entrada para modificar un pedido. Las
  invariantes del pedido (límite de unidades, transiciones, eventos) se protegen aquí y
  en ninguna otra parte.
* **Domain Events** (`DomainEvent`): hechos que ya ocurrieron y que quedan registrados
  en el pedido para su auditoría.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum

#: Máximo de **unidades** (suma de cantidades) que admite un pedido.
#: El límite aplica a las unidades, no al número de renglones.
MAX_UNITS_PER_ORDER = 20

#: Única moneda admitida por el catálogo.
SUPPORTED_CURRENCY = "MXN"

#: Redondeo monetario a dos decimales.
CENT = Decimal("0.01")


# ---------------------------------------------------------------------------
# Excepciones del dominio
# ---------------------------------------------------------------------------


class DomainException(Exception):
    """Base de todas las excepciones de negocio.

    Los endpoints de la API traducen estas excepciones a códigos HTTP; ningún
    detalle de la regla de negocio debe filtrarse a la capa de transporte.
    """


class InvalidOrderData(DomainException):
    """Los datos de entrada violan una invariante del dominio.

    Ejemplos: monto negativo, moneda distinta a MXN, cantidad no positiva,
    pedido sin artículos, cliente inactivo, guía de envío vacía.
    """


class InvalidOrderTransition(DomainException):
    """La transición de estado solicitada no está permitida en la máquina de estados."""


class OrderItemLimitExceeded(DomainException):
    """La operación dejaría el pedido con más de `MAX_UNITS_PER_ORDER` unidades."""


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Money:
    """Importe monetario inmutable: `Decimal` (nunca `float`) y moneda.

    Es un *value object*: dos importes con el mismo `amount` y `currency` son
    el mismo valor. Al ser `frozen`, no puede mutar; cada operación devuelve
    una instancia nueva.
    """

    amount: Decimal
    currency: str = SUPPORTED_CURRENCY

    def __post_init__(self) -> None:
        # Se normaliza a Decimal para que la invariante "amount es Decimal" se
        # cumpla siempre. `str()` evita arrastrar el error binario de un float:
        # `Decimal(19.99)` guarda 19.989999999999998436805981327779591083526611328125,
        # mientras que `Decimal(str(19.99))` guarda exactamente 19.99.
        # (Un float cuyo valor es exacto en binario, como 600.0, no sufre deriva.)
        if not isinstance(self.amount, Decimal):
            try:
                object.__setattr__(self, "amount", Decimal(str(self.amount)))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise InvalidOrderData("Monto inválido") from exc
        if not self.amount.is_finite() or self.amount < 0:
            raise InvalidOrderData("Monto inválido")
        # La moneda NO se restringe aquí: `Money` es un value object genérico que
        # sabe rechazar la mezcla de monedas en `add()`. Es el aggregate `Order`
        # quien exige que las órdenes del negocio se manejen en MXN.

    def add(self, other: "Money") -> "Money":
        """Suma dos importes de la misma moneda y devuelve uno nuevo."""
        if self.currency != other.currency:
            raise InvalidOrderData("Monedas distintas")
        return Money(self.amount + other.amount, self.currency)

    def apply_percentage(self, percentage: Decimal) -> "Money":
        """Devuelve un `Money` nuevo con el porcentaje indicado descontado.

        `percentage` es la tasa de descuento (10, 5, ...). El resultado se redondea
        a dos decimales con `ROUND_HALF_UP`; este objeto no se modifica.
        """
        if percentage < 0:
            raise InvalidOrderData("Porcentaje inválido")
        factor = (Decimal("100") - percentage) / Decimal("100")
        amount = (self.amount * factor).quantize(CENT, rounding=ROUND_HALF_UP)
        return Money(amount, self.currency)

    def __str__(self) -> str:  # pragma: no cover - conveniencia de depuración
        return f"{self.amount} {self.currency}"


@dataclass(frozen=True)
class Customer:
    """Cliente del pedido. Entidad con identidad (`id`) y datos de catálogo."""

    id: str
    is_vip: bool = False
    active: bool = True


@dataclass(frozen=True)
class OrderItem:
    """Un producto y su cantidad dentro de un pedido.

    El subtotal **no se captura**: se calcula, de modo que nunca puede
    discrepar del precio unitario por la cantidad.
    """

    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self) -> None:
        if not self.sku or not self.sku.strip():
            raise InvalidOrderData("Artículo inválido")
        if self.quantity <= 0:
            raise InvalidOrderData("Artículo inválido")

    @property
    def subtotal(self) -> Money:
        """Importe del renglón: precio unitario por cantidad."""
        return Money(
            self.unit_price.amount * self.quantity, self.unit_price.currency
        )


# ---------------------------------------------------------------------------
# Entidades y eventos
# ---------------------------------------------------------------------------


class OrderStatus(str, Enum):
    """Estados posibles de un pedido dentro de la máquina de estados."""

    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


@dataclass(frozen=True)
class DomainEvent:
    """Hecho de dominio ya ocurrido.

    `occurred_at` se calcula al crear el evento, por lo que el evento es
    inmutable y su marca de tiempo es fiable.
    """

    name: str
    order_id: str
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Order:
    """Aggregate Root del pedido.

    Concentra todas las reglas: quién puede confirmarlo, cuántos artículos
    admite, cuándo puede cambiar de estado y qué evento deja cada transición.
    """

    customer: Customer
    id: str
    has_promotion: bool = False
    status: OrderStatus = OrderStatus.DRAFT
    items: list[OrderItem] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    tracking_number: str | None = None
    cancel_reason: str | None = None

    # -- consultas -------------------------------------------------------
    @property
    def units(self) -> int:
        """Suma de las cantidades de los renglones (no el número de renglones)."""
        return sum(item.quantity for item in self.items)

    @property
    def total(self) -> Money:
        """Importe del pedido: suma de los subtotales, sin descuentos aplicados."""
        amount = sum((x.subtotal.amount for x in self.items), Decimal("0"))
        return Money(amount.quantize(CENT, rounding=ROUND_HALF_UP), SUPPORTED_CURRENCY)

    @property
    def is_empty(self) -> bool:
        """`True` si el pedido no tiene renglones."""
        return not self.items

    # -- comandos --------------------------------------------------------
    def add_item(self, item: OrderItem) -> None:
        """Agrega un renglón al pedido.

        Solo se admite en `DRAFT` y el resultado no puede superar las 20
        unidades. Si la operación es inválida, el pedido **no** se modifica.
        """
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo DRAFT admite artículos")
        if self.units + item.quantity > MAX_UNITS_PER_ORDER:
            raise OrderItemLimitExceeded(
                f"Máximo {MAX_UNITS_PER_ORDER} unidades por pedido"
            )
        if item.unit_price.currency != SUPPORTED_CURRENCY:
            raise InvalidOrderData("Solo MXN")
        self.items.append(item)

    def confirm(self) -> None:
        """DRAFT -> CONFIRMED.

        Exige renglones y un cliente activo. Si falla, el estado y la lista de
        eventos quedan intactos.
        """
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo DRAFT")
        if not self.items or not self.customer.active:
            raise InvalidOrderData("Requiere artículos y cliente activo")
        self.status = OrderStatus.CONFIRMED
        self.events.append(DomainEvent("OrderConfirmed", self.id))

    def ship(self, tracking_number: str) -> None:
        """CONFIRMED -> SHIPPED. Exige una guía de envío no vacía."""
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo CONFIRMED")
        if not tracking_number or not tracking_number.strip():
            raise InvalidOrderData("Guía de envío obligatoria")
        self.status = OrderStatus.SHIPPED
        self.tracking_number = tracking_number.strip()
        self.events.append(DomainEvent("OrderShipped", self.id))

    def cancel(self, reason: str) -> None:
        """CONFIRMED -> CANCELLED. Exige un motivo no vacío."""
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo CONFIRMED")
        if not reason or not reason.strip():
            raise InvalidOrderData("Motivo de cancelación obligatorio")
        self.status = OrderStatus.CANCELLED
        self.cancel_reason = reason.strip()
        self.events.append(DomainEvent("OrderCancelled", self.id))

    def deliver(self) -> None:
        """SHIPPED -> DELIVERED."""
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo SHIPPED")
        self.status = OrderStatus.DELIVERED
        self.events.append(DomainEvent("OrderDelivered", self.id))

    def return_order(self) -> None:
        """SHIPPED -> RETURNED (devolución)."""
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo SHIPPED")
        self.status = OrderStatus.RETURNED
        self.events.append(DomainEvent("OrderReturned", self.id))
