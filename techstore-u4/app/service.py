"""Servicio de aplicación de TechStore: fixtures, catálogos y recarga.

Este módulo es la frontera entre los archivos CSV y el dominio. Concentra la
lectura de `datos/*.csv`, la construcción de los agregados `Order` y los
catálogos de solo lectura que necesita la API. Ni `app/domain.py` ni
`app/specifications.py` dependen de él: las reglas siguen viviendo en el
dominio y este servicio solo las alimenta.

Ventajas de tenerlo separado de la API:

* la API y los scripts cargan los pedidos con la **misma** función;
* `load_orders()` admite un directorio alternativo, lo que permite probar con
  fixtures temporales sin tocar `datos/`;
* recargar los fixtures (`POST /admin/reload-fixtures`) es una operación del
  servicio, no un detalle del controlador.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain import Customer, Money, Order, OrderItem, OrderStatus

#: Raíz del proyecto (la carpeta que contiene `app/` y `datos/`).
ROOT = Path(__file__).resolve().parents[1]

#: Directorio de datos del paquete original.
DATA_DIR = ROOT / "datos"


def _base(data_dir: str | Path | None = None) -> Path:
    """Directorio de datos efectivo (el del paquete si no se indica otro)."""
    return Path(data_dir) if data_dir is not None else DATA_DIR


def read_rows(
    filename: str, data_dir: str | Path | None = None
) -> list[dict[str, str]]:
    """Lee un CSV del paquete respetando el BOM de los archivos originales."""
    with (_base(data_dir) / filename).open(
        encoding="utf-8-sig", newline=""
    ) as archivo:
        return list(csv.DictReader(archivo))


def load_orders(data_dir: str | Path | None = None) -> dict[str, Order]:
    """Construye los pedidos del paquete a partir de los cuatro CSV de datos.

    El orden de lectura importa: primero clientes y productos (catálogos),
    después pedidos (cabeceras) y por último el detalle. Así ninguna llave
    foránea se resuelve antes de existir. Los pedidos se devuelven indexados
    por `pedido_id`.
    """
    clientes = {
        fila["cliente_id"]: fila
        for fila in read_rows("clientes.csv", data_dir)
    }
    productos = {
        fila["sku"]: fila for fila in read_rows("productos.csv", data_dir)
    }

    pedidos: dict[str, Order] = {}
    for fila in read_rows("pedidos.csv", data_dir):
        cliente = clientes[fila["cliente_id"]]
        pedidos[fila["pedido_id"]] = Order(
            customer=Customer(
                cliente["cliente_id"],
                bool(int(cliente["es_vip"])),
                bool(int(cliente["activo"])),
            ),
            id=fila["pedido_id"],
            has_promotion=bool(int(fila["tiene_promocion"])),
            status=OrderStatus(fila["estado_inicial"]),
        )

    for fila in read_rows("detalle_pedidos.csv", data_dir):
        producto = productos[fila["sku"]]
        pedidos[fila["pedido_id"]].add_item(
            OrderItem(
                fila["sku"],
                int(fila["cantidad"]),
                Money(Decimal(producto["precio_mxn"])),
            )
        )
    return pedidos


def load_fixture(data_dir: str | Path | None = None) -> dict[str, Order]:
    """Alias didáctico de `load_orders` (mismo contrato que el cargador original)."""
    return load_orders(data_dir)


def catalogo_productos(
    data_dir: str | Path | None = None,
) -> dict[str, Decimal]:
    """Precio unitario por SKU, leído del catálogo (no codificado a mano)."""
    return {
        fila["sku"]: Decimal(fila["precio_mxn"])
        for fila in read_rows("productos.csv", data_dir)
    }


def catalogo_clientes(
    data_dir: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Datos de catálogo por cliente, indexados por `cliente_id`."""
    return {
        fila["cliente_id"]: fila
        for fila in read_rows("clientes.csv", data_dir)
    }
