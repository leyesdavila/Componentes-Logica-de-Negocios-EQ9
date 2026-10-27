"""Ejecuta los escenarios E01–E15 y exporta la bitácora reproducible.

Cada caso se ejecuta sobre pedidos **recién cargados** con `load_orders()`, de
modo que ningún escenario hereda el estado de otro. El objetivo esperado se lee
de `datos/escenarios.csv`; el resultado observado se obtiene ejecutando el
dominio, nunca escribiéndolo a mano.

Uso:
    python scripts/ejecutar_bitacora.py

Salidas:
    docs/bitacora/bitacora_escenarios.csv
    (y la misma información por consola)
"""

from __future__ import annotations

import csv
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.domain import DomainException, Money, OrderItem  # noqa: E402
from app.service import catalogo_productos, load_orders, read_rows  # noqa: E402
from app.specifications import evaluate_discount  # noqa: E402

DESTINO = ROOT / "docs" / "bitacora" / "bitacora_escenarios.csv"
PRECIO_SKU003 = catalogo_productos()["SKU003"]

COLUMNAS = [
    "caso",
    "pedido",
    "estado_inicial",
    "operacion",
    "resultado_esperado",
    "resultado_observado",
    "estado_final",
    "evento_emitido",
    "veredicto",
    "detalle",
]


# ---------------------------------------------------------------------------
# Acciones de cada escenario
# ---------------------------------------------------------------------------


def evaluar_descuento(order, orders):
    return f"{evaluate_discount(order).percentage}%"


def confirmar(order, orders):
    order.confirm()
    return order.status.value


def agregar_sku003_x2(order, orders):
    order.add_item(OrderItem("SKU003", 2, Money(PRECIO_SKU003)))
    return f"{order.units} unidades"


def confirmar_y_enviar_sin_guia(order, orders):
    order.confirm()
    order.ship("")
    return order.status.value


def confirmar_dos_veces(order, orders):
    order.confirm()
    order.confirm()
    return order.status.value


def confirmar_enviar_cancelar(order, orders):
    order.confirm()
    order.ship("GUIA-E13")
    order.cancel("Cancelación solicitada")
    return order.status.value


def confirmar_enviar_devolver(order, orders):
    order.confirm()
    order.ship("GUIA-E14")
    order.return_order()
    return order.status.value


def confirmar_enviar_entregar(order, orders):
    order.confirm()
    order.ship("GUIA-E15")
    order.deliver()
    return order.status.value


ACCIONES = {
    "E01": evaluar_descuento,
    "E02": evaluar_descuento,
    "E03": confirmar,
    "E04": evaluar_descuento,
    "E05": evaluar_descuento,
    "E06": confirmar,
    "E07": confirmar,
    "E08": agregar_sku003_x2,
    "E09": evaluar_descuento,
    "E10": evaluar_descuento,
    "E11": confirmar_y_enviar_sin_guia,
    "E12": confirmar_dos_veces,
    "E13": confirmar_enviar_cancelar,
    "E14": confirmar_enviar_devolver,
    "E15": confirmar_enviar_entregar,
}

ESTADOS_EXITO = {"CONFIRMED", "RETURNED", "DELIVERED"}


def veredicto(esperado: str, observado: str, rechazo: bool, estado: str) -> str:
    """Compara el objetivo del CSV con el resultado realmente observado."""
    if esperado.startswith("rechazo"):
        coincide = rechazo
    elif esperado == "exito":
        coincide = not rechazo and estado in ESTADOS_EXITO
    else:
        coincide = not rechazo and observado == esperado
    return "COINCIDE" if coincide else "NO COINCIDE"


def main() -> int:
    objetivos = {
        fila["caso_id"]: fila for fila in read_rows("escenarios.csv")
    }
    filas: list[dict[str, str]] = []

    for caso in sorted(objetivos):
        meta = objetivos[caso]
        pedido_id = meta["pedido_id"]
        orders = load_orders()
        order = orders[pedido_id]
        estado_inicial = order.status.value
        eventos_antes = len(order.events)

        rechazo = False
        detalle = ""
        try:
            observado = ACCIONES[caso](order, orders)
        except DomainException as exc:
            rechazo = True
            observado = f"RECHAZADO ({type(exc).__name__})"
            detalle = f"{type(exc).__name__}: {exc}"

        eventos = [evento.name for evento in order.events[eventos_antes:]]
        filas.append(
            {
                "caso": caso,
                "pedido": pedido_id,
                "estado_inicial": estado_inicial,
                "operacion": meta["accion"],
                "resultado_esperado": meta["objetivo"],
                "resultado_observado": observado,
                "estado_final": order.status.value,
                "evento_emitido": ", ".join(eventos) if eventos else "ninguno",
                "veredicto": veredicto(
                    meta["objetivo"], observado, rechazo, order.status.value
                ),
                "detalle": detalle,
            }
        )

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.DictWriter(
            archivo, fieldnames=COLUMNAS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(filas)

    print(f"Escenarios registrados: {len(filas)}")
    for fila in filas:
        print(
            f"{fila['caso']} | {fila['pedido']} | "
            f"{fila['resultado_observado']} | {fila['estado_final']} | "
            f"{fila['evento_emitido']} | {fila['veredicto']}"
        )
    coincidencias = sum(fila["veredicto"] == "COINCIDE" for fila in filas)
    print(f"Coincidencias: {coincidencias}/{len(filas)}")
    print(f"Bitácora: {DESTINO.relative_to(ROOT)}")
    return 0 if coincidencias == len(filas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
