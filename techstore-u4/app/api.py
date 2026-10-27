"""API REST de TechStore — Unidad 4 (Componentes de Lógica de Negocio).

Los controladores **no repiten reglas de negocio**: localizan el pedido, llaman al
método del aggregate `Order` y traducen el resultado a una respuesta HTTP.

| Situación | Código |
|---|---|
| El pedido no existe | **404** |
| La transición de estado no está permitida | **409** |
| Los datos violan una invariante (sin artículos, cliente inactivo, guía vacía, más de 20 unidades) | **422** |

Documentación interactiva: `http://127.0.0.1:8000/docs` · contrato OpenAPI:
`http://127.0.0.1:8000/openapi.json`
"""

from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app.domain import (
    Customer,
    DomainException,
    InvalidOrderTransition,
    Money,
    Order,
    OrderItem,
)
from app.service import catalogo_clientes, catalogo_productos, load_orders
from app.specifications import evaluate_discount, evaluate_rules

#: 422 Unprocessable Content (antes "Unprocessable Entity").
#: Se usa el código literal para no depender de la constante de Starlette,
#: que renombró el símbolo y emite una advertencia de deprecación.
HTTP_422 = 422


# ---------------------------------------------------------------------------
# Modelos de respuesta
# ---------------------------------------------------------------------------


class ItemOut(BaseModel):
    """Renglón de un pedido."""

    sku: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class EventOut(BaseModel):
    """Evento de dominio registrado en el pedido."""

    name: str
    occurred_at: datetime


class OrderSummary(BaseModel):
    """Vista resumida de un pedido."""

    id: str
    cliente_id: str
    cliente: str
    es_vip: bool
    status: str
    unidades: int
    renglones: int
    total: Decimal
    descuento_pct: Decimal
    total_con_descuento: Decimal
    eventos: list[str]


class OrderDetail(OrderSummary):
    """Vista completa de un pedido."""

    items: list[ItemOut]
    tracking_number: str | None = None
    cancel_reason: str | None = None
    reglas: list[dict[str, Any]] = Field(default_factory=list)
    historial: list[EventOut] = Field(default_factory=list)


class TransitionOut(BaseModel):
    """Respuesta de una operación que cambia el estado del pedido."""

    id: str
    status: str
    total: Decimal
    eventos: list[str]


class ItemIn(BaseModel):
    """Datos de un renglón al crear o ampliar un pedido."""

    sku: str
    quantity: int = Field(gt=0)


class OrderIn(BaseModel):
    """Datos para crear un pedido."""

    cliente_id: str
    items: list[ItemIn] = Field(default_factory=list)


class ShipIn(BaseModel):
    """Datos para enviar un pedido."""

    tracking_number: str = ""


class CancelIn(BaseModel):
    """Datos para cancelar un pedido."""

    reason: str = ""


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------


def _refrescar(application: FastAPI) -> None:
    """Recarga pedidos y catálogos desde los CSV del paquete.

    Se ejecuta al arrancar la aplicación y desde `POST /admin/reload-fixtures`.
    Recarga también los catálogos para que un cambio en `productos.csv` o
    `clientes.csv` se refleje sin reiniciar el proceso.
    """
    application.state.orders = load_orders()
    application.state.productos = catalogo_productos()
    application.state.clientes = catalogo_clientes()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Carga los fixtures en memoria al arrancar la aplicación."""
    _refrescar(application)
    yield


app = FastAPI(
    title="TechStore U4",
    version="1.0.0",
    summary="API de pedidos del dominio TechStore (Unidad 4)",
    description=(
        "Núcleo de negocio de pedidos: value objects, invariantes, "
        "máquina de estados, eventos de dominio y reglas de descuento."
    ),
    lifespan=lifespan,
)
# Disponible también sin arrancar el ciclo de vida (import directo en pruebas).
_refrescar(app)


# ---------------------------------------------------------------------------
# Utilidades del controlador
# ---------------------------------------------------------------------------


def _orders() -> dict[str, Order]:
    """Pedidos en memoria de la aplicación."""
    return app.state.orders


def _productos() -> dict[str, Decimal]:
    """Precio unitario por SKU, cargado del catálogo."""
    return app.state.productos


def _clientes() -> dict[str, dict[str, Any]]:
    """Datos de catálogo por cliente, cargados del CSV."""
    return app.state.clientes


def _buscar(order_id: str) -> Order:
    """Localiza un pedido o responde 404."""
    order = _orders().get(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El pedido {order_id} no existe",
        )
    return order


def _traducir(exc: DomainException) -> HTTPException:
    """Traduce una excepción del dominio a una respuesta HTTP.

    * `InvalidOrderTransition` -> 409 (conflicto con el estado actual).
    * `InvalidOrderData` y `OrderItemLimitExceeded` -> 422 (datos inválidos).
    """
    if isinstance(exc, InvalidOrderTransition):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=HTTP_422, detail=str(exc)
    )


def _resumen(order: Order) -> OrderSummary:
    """Proyecta el pedido a la vista resumida."""
    descuento = evaluate_discount(order)
    return OrderSummary(
        id=order.id,
        cliente_id=order.customer.id,
        cliente=_clientes().get(order.customer.id, {}).get(
            "nombre", order.customer.id
        ),
        es_vip=order.customer.is_vip,
        status=order.status.value,
        unidades=order.units,
        renglones=len(order.items),
        total=descuento.total.amount,
        descuento_pct=descuento.percentage,
        total_con_descuento=descuento.discounted_total.amount,
        eventos=[e.name for e in order.events],
    )


def _detalle(order: Order) -> OrderDetail:
    """Proyecta el pedido a la vista completa."""
    resumen = _resumen(order)
    return OrderDetail(
        **resumen.model_dump(),
        items=[
            ItemOut(
                sku=item.sku,
                quantity=item.quantity,
                unit_price=item.unit_price.amount,
                subtotal=item.subtotal.amount,
            )
            for item in order.items
        ],
        tracking_number=order.tracking_number,
        cancel_reason=order.cancel_reason,
        reglas=evaluate_rules(order),
        historial=[
            EventOut(name=e.name, occurred_at=e.occurred_at) for e in order.events
        ],
    )


def _transicion(order: Order) -> TransitionOut:
    """Proyecta el resultado de una transición."""
    descuento = evaluate_discount(order)
    return TransitionOut(
        id=order.id,
        status=order.status.value,
        total=descuento.total.amount,
        eventos=[e.name for e in order.events],
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/", summary="Información de la API")
def raiz() -> dict[str, Any]:
    """Descripcion de la API y conteo de pedidos en memoria."""
    return {
        "api": "TechStore U4",
        "descripcion": "API de pedidos con lógica de negocio de la Unidad 4",
        "pedidos_en_memoria": len(_orders()),
        "documentacion": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health", summary="Estado del servicio")
def health() -> dict[str, Any]:
    """Comprobación de salud: proceso vivo y fixtures cargados."""
    return {
        "status": "ok",
        "pedidos_en_memoria": len(_orders()),
        "version": app.version,
    }


@app.post("/admin/reload-fixtures", summary="Recargar los fixtures")
def recargar_fixtures() -> dict[str, Any]:
    """Descarta los cambios en memoria y vuelve a leer los CSV del paquete.

    Es una operación de apoyo académico: permite repetir una demostración sin
    reiniciar `uvicorn`. No es un endpoint de negocio y no altera los CSV.
    """
    _refrescar(app)
    return {
        "status": "ok",
        "recargados": len(_orders()),
        "pedidos": list(_orders()),
    }


@app.get("/orders", response_model=list[OrderSummary], summary="Listar pedidos")
def listar_pedidos() -> list[OrderSummary]:
    """Devuelve el resumen de todos los pedidos cargados en memoria."""
    return [_resumen(order) for order in _orders().values()]


@app.get(
    "/orders/{order_id}",
    response_model=OrderDetail,
    summary="Consultar un pedido",
    responses={404: {"description": "El pedido no existe"}},
)
def consultar_pedido(order_id: str) -> OrderDetail:
    """Detalle de un pedido: renglones, total, descuento, reglas y eventos."""
    return _detalle(_buscar(order_id))


@app.get(
    "/orders/{order_id}/rules",
    response_model=OrderDetail,
    summary="Evaluar reglas de descuento",
    responses={404: {"description": "El pedido no existe"}},
)
def evaluar_reglas(order_id: str) -> OrderDetail:
    """Muestra el resultado de aplicar las reglas de descuento al pedido."""
    return _detalle(_buscar(order_id))


@app.post(
    "/orders/{order_id}/confirm",
    response_model=TransitionOut,
    summary="Confirmar un pedido",
    responses={
        404: {"description": "El pedido no existe"},
        409: {"description": "Transición no permitida desde el estado actual"},
        422: {"description": "Pedido sin artículos o cliente inactivo"},
    },
)
def confirmar_pedido(order_id: str) -> TransitionOut:
    """DRAFT -> CONFIRMED. Requiere artículos y cliente activo."""
    order = _buscar(order_id)
    try:
        order.confirm()
    except DomainException as exc:
        raise _traducir(exc) from exc
    return _transicion(order)


@app.post(
    "/orders/{order_id}/ship",
    response_model=TransitionOut,
    summary="Enviar un pedido",
    responses={
        404: {"description": "El pedido no existe"},
        409: {"description": "Transición no permitida desde el estado actual"},
        422: {"description": "Falta la guía de envío"},
    },
)
def enviar_pedido(order_id: str, datos: ShipIn | None = None) -> TransitionOut:
    """CONFIRMED -> SHIPPED. Requiere una guía de envío no vacía."""
    order = _buscar(order_id)
    guia = datos.tracking_number if datos else ""
    try:
        order.ship(guia)
    except DomainException as exc:
        raise _traducir(exc) from exc
    return _transicion(order)


@app.post(
    "/orders/{order_id}/cancel",
    response_model=TransitionOut,
    summary="Cancelar un pedido",
    responses={
        404: {"description": "El pedido no existe"},
        409: {"description": "Transición no permitida desde el estado actual"},
        422: {"description": "Falta el motivo de cancelación"},
    },
)
def cancelar_pedido(order_id: str, datos: CancelIn | None = None) -> TransitionOut:
    """CONFIRMED -> CANCELLED. Requiere un motivo no vacío."""
    order = _buscar(order_id)
    motivo = datos.reason if datos else ""
    try:
        order.cancel(motivo)
    except DomainException as exc:
        raise _traducir(exc) from exc
    return _transicion(order)


@app.post(
    "/orders/{order_id}/deliver",
    response_model=TransitionOut,
    summary="Entregar un pedido",
    responses={
        404: {"description": "El pedido no existe"},
        409: {"description": "Transición no permitida desde el estado actual"},
    },
)
def entregar_pedido(order_id: str) -> TransitionOut:
    """SHIPPED -> DELIVERED."""
    order = _buscar(order_id)
    try:
        order.deliver()
    except DomainException as exc:
        raise _traducir(exc) from exc
    return _transicion(order)


@app.post(
    "/orders/{order_id}/return",
    response_model=TransitionOut,
    summary="Registrar la devolución de un pedido",
    responses={
        404: {"description": "El pedido no existe"},
        409: {"description": "Transición no permitida desde el estado actual"},
    },
)
def devolver_pedido(order_id: str) -> TransitionOut:
    """SHIPPED -> RETURNED."""
    order = _buscar(order_id)
    try:
        order.return_order()
    except DomainException as exc:
        raise _traducir(exc) from exc
    return _transicion(order)


@app.post(
    "/orders/{order_id}/items",
    response_model=OrderDetail,
    summary="Agregar un renglón a un pedido",
    responses={
        404: {"description": "El pedido no existe"},
        409: {"description": "El pedido ya no admite artículos"},
        422: {"description": "SKU desconocido o límite de unidades excedido"},
    },
)
def agregar_renglon(order_id: str, datos: ItemIn) -> OrderDetail:
    """Agrega un renglón a un pedido en DRAFT, respetando el límite de 20 unidades."""
    order = _buscar(order_id)
    if datos.sku not in _productos():
        raise HTTPException(
            status_code=HTTP_422,
            detail=f"El SKU {datos.sku} no existe en el catálogo",
        )
    try:
        order.add_item(
            OrderItem(datos.sku, datos.quantity, Money(_productos()[datos.sku]))
        )
    except DomainException as exc:
        raise _traducir(exc) from exc
    return _detalle(order)


@app.post(
    "/orders",
    response_model=OrderDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un pedido",
    responses={422: {"description": "Cliente o SKU desconocidos"}},
)
def crear_pedido(datos: OrderIn) -> OrderDetail:
    """Crea un pedido nuevo en DRAFT para un cliente del catálogo."""
    cliente = _clientes().get(datos.cliente_id)
    if cliente is None:
        raise HTTPException(
            status_code=HTTP_422,
            detail=f"El cliente {datos.cliente_id} no existe",
        )
    nuevo = Order(
        customer=Customer(
            cliente["cliente_id"],
            bool(int(cliente["es_vip"])),
            bool(int(cliente["activo"])),
        ),
        id=f"N{len(_orders()) + 1:03d}",
    )
    for item in datos.items:
        if item.sku not in _productos():
            raise HTTPException(
                status_code=HTTP_422,
                detail=f"El SKU {item.sku} no existe en el catálogo",
            )
        try:
            nuevo.add_item(
                OrderItem(item.sku, item.quantity, Money(_productos()[item.sku]))
            )
        except DomainException as exc:
            raise _traducir(exc) from exc
    _orders()[nuevo.id] = nuevo
    return _detalle(nuevo)
