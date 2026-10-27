"""Pruebas de la API REST — sección 12 de la práctica guiada.

Se verifica que el controlador **no duplica reglas**: la API traduce las
excepciones del dominio a los códigos HTTP correctos.

* **404** el pedido no existe.
* **409** la transición de estado no está permitida.
* **422** los datos violan una invariante (pedido sin artículos, cliente inactivo,
  guía vacía, más de 20 unidades).
"""

import pytest
from fastapi.testclient import TestClient

from app.api import app


@pytest.fixture()
def client():
    """Cliente HTTP con los fixtures recién cargados en cada prueba.

    El contexto de `TestClient` ejecuta el ciclo de vida de la aplicación, que
    recarga los datos: así cada prueba parte de los 16 pedidos en DRAFT y no
    hereda el estado de la prueba anterior.
    """
    with TestClient(app) as cliente:
        yield cliente


# ---------------------------------------------------------------------------
# 404 — el recurso no existe
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("get", "/orders/NOEXISTE", None),
        ("get", "/orders/NOEXISTE/rules", None),
        ("post", "/orders/NOEXISTE/confirm", None),
        ("post", "/orders/NOEXISTE/ship", {"tracking_number": "G-1"}),
        ("post", "/orders/NOEXISTE/cancel", {"reason": "motivo"}),
        ("post", "/orders/NOEXISTE/deliver", None),
        ("post", "/orders/NOEXISTE/return", None),
        ("post", "/orders/NOEXISTE/items", {"sku": "SKU001", "quantity": 1}),
    ],
)
def test_pedido_inexistente_responde_404(client, metodo, ruta, cuerpo):
    respuesta = getattr(client, metodo)(ruta, json=cuerpo) if cuerpo else getattr(
        client, metodo
    )(ruta)
    assert respuesta.status_code == 404
    assert "no existe" in respuesta.json()["detail"]


# ---------------------------------------------------------------------------
# 409 — transición no permitida
# ---------------------------------------------------------------------------


def test_confirmar_dos_veces_responde_409(client):
    """E12: la segunda confirmación entra en conflicto con el estado actual."""
    primera = client.post("/orders/O013/confirm")
    assert primera.status_code == 200
    assert primera.json()["status"] == "CONFIRMED"

    segunda = client.post("/orders/O013/confirm")
    assert segunda.status_code == 409
    assert segunda.json()["detail"]


def test_cancelar_desde_shipped_responde_409(client):
    """E13: cancelar un pedido ya enviado entra en conflicto."""
    assert client.post("/orders/O014/confirm").status_code == 200
    assert client.post("/orders/O014/ship", json={"tracking_number": "G-1"}).status_code == 200

    respuesta = client.post("/orders/O014/cancel", json={"reason": "me arrepentí"})
    assert respuesta.status_code == 409


def test_entregar_sin_enviar_responde_409(client):
    """Entregar exige el estado SHIPPED."""
    assert client.post("/orders/O016/confirm").status_code == 200
    respuesta = client.post("/orders/O016/deliver")
    assert respuesta.status_code == 409


# ---------------------------------------------------------------------------
# 422 — datos inválidos
# ---------------------------------------------------------------------------


def test_confirmar_pedido_vacio_responde_422(client):
    """E06: el pedido O007 no tiene artículos."""
    respuesta = client.post("/orders/O007/confirm")
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]


def test_confirmar_cliente_inactivo_responde_422(client):
    """E03: el cliente C003 está inactivo."""
    respuesta = client.post("/orders/O003/confirm")
    assert respuesta.status_code == 422


def test_enviar_sin_guia_responde_422(client):
    """E11: la guía de envío es obligatoria."""
    assert client.post("/orders/O012/confirm").status_code == 200
    respuesta = client.post("/orders/O012/ship", json={"tracking_number": ""})
    assert respuesta.status_code == 422


def test_agregar_21_unidades_responde_422(client):
    """E08: O009 tiene 19 unidades y el límite es 20."""
    respuesta = client.post("/orders/O009/items", json={"sku": "SKU003", "quantity": 2})
    assert respuesta.status_code == 422


def test_agregar_sku_inexistente_responde_422(client):
    respuesta = client.post("/orders/O009/items", json={"sku": "SKU999", "quantity": 1})
    assert respuesta.status_code == 422


# ---------------------------------------------------------------------------
# 200 — operaciones válidas
# ---------------------------------------------------------------------------


def test_confirmar_pedido_valido_responde_200(client):
    """E07: O008 tiene 20 unidades exactas y se confirma."""
    respuesta = client.post("/orders/O008/confirm")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id"] == "O008"
    assert cuerpo["status"] == "CONFIRMED"
    assert cuerpo["eventos"] == ["OrderConfirmed"]


def test_ciclo_completo_confirmar_enviar_entregar(client):
    """E15."""
    assert client.post("/orders/O016/confirm").status_code == 200
    assert (
        client.post("/orders/O016/ship", json={"tracking_number": "GUIA-1"}).status_code
        == 200
    )
    respuesta = client.post("/orders/O016/deliver")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "DELIVERED"
    assert respuesta.json()["eventos"] == [
        "OrderConfirmed",
        "OrderShipped",
        "OrderDelivered",
    ]


def test_ciclo_completo_confirmar_enviar_devolver(client):
    """E14."""
    assert client.post("/orders/O015/confirm").status_code == 200
    assert (
        client.post("/orders/O015/ship", json={"tracking_number": "GUIA-2"}).status_code
        == 200
    )
    respuesta = client.post("/orders/O015/return")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "RETURNED"


def test_consultar_pedido_devuelve_unidades_y_total(client):
    """El PDF: O001 muestra 4 unidades y 2100.00 MXN."""
    respuesta = client.get("/orders/O001")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "DRAFT"
    assert cuerpo["unidades"] == 4
    assert cuerpo["renglones"] == 2
    assert cuerpo["total"] == "2100.00"
    assert cuerpo["descuento_pct"] == "10"
    assert cuerpo["total_con_descuento"] == "1890.00"
    assert cuerpo["eventos"] == []


def test_consultar_pedido_lista_los_renglones(client):
    cuerpo = client.get("/orders/O001").json()
    assert [item["sku"] for item in cuerpo["items"]] == ["SKU001", "SKU002"]
    assert cuerpo["items"][0]["subtotal"] == "1200.00"


def test_listar_pedidos(client):
    respuesta = client.get("/orders")
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 16


def test_evaluar_reglas_devuelve_el_detalle(client):
    """El endpoint de reglas muestra por qué un pedido recibe o no descuento."""
    cuerpo = client.get("/orders/O001/rules").json()
    reglas = {regla["regla"]: regla["cumple"] for regla in cuerpo["reglas"]}
    assert reglas["total > 500"] is True
    assert reglas["cliente VIP"] is True
    assert reglas["unidades >= 4"] is True
    assert reglas["NOT promoción activa"] is True
    assert reglas["total > 5000"] is False
    assert reglas["cliente activo"] is True
    assert reglas["pedido con artículos"] is True


def test_crear_pedido_nuevo(client):
    respuesta = client.post(
        "/orders",
        json={"cliente_id": "C001", "items": [{"sku": "SKU001", "quantity": 2}]},
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "DRAFT"
    assert cuerpo["unidades"] == 2
    assert cuerpo["total"] == "1200.00"


def test_crear_pedido_con_cliente_inexistente_responde_422(client):
    respuesta = client.post("/orders", json={"cliente_id": "C999", "items": []})
    assert respuesta.status_code == 422


def test_la_api_no_reinicia_el_estado_entre_peticiones(client):
    """Cada petición opera sobre el mismo pedido en memoria."""
    assert client.post("/orders/O013/confirm").status_code == 200
    cuerpo = client.get("/orders/O013").json()
    assert cuerpo["status"] == "CONFIRMED"
    assert cuerpo["eventos"] == ["OrderConfirmed"]
    assert client.post("/orders/O013/confirm").status_code == 409
