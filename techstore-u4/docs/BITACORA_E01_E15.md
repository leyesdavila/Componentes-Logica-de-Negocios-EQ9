# Bitácora de los escenarios E01–E15

Ejecución de `datos/escenarios.csv` (sección 10 de la práctica guiada).

* Cada escenario se ejecuta sobre objetos **recién cargados** con `load_fixture()`,
  de modo que ningún caso hereda el estado de otro.
* No se editó ningún CSV ni ningún pedido para forzar que un caso pase.
* La columna **Evento** registra el evento emitido por la transición o, si la
  operación falló, la ausencia de evento.
* Evidencia reproducible: `docs/evidencias/03_escenarios.txt`
  (`python -m pytest tests/test_escenarios.py -s -v`).

## Resultados

| Caso | Estado inicial | Operación | Resultado real | Explicación | Evento |
|---|---|---|---|---|---|
| **E01** | DRAFT | `evaluate_discount(O001)` | **10 %** → 1890.00 MXN | VIP + total 2100.00 > 500 + 4 unidades ≥ 4 + sin promoción | n/a (no es transición) |
| **E02** | DRAFT | `evaluate_discount(O002)` | **0 %** → 1050.00 MXN | No cumple VIP ni unidades ≥ 4; tampoco supera 5000 | n/a (no es transición) |
| **E03** | DRAFT | `confirm()` | **RECHAZADO** (`InvalidOrderData`) | El cliente C003 está inactivo: un pedido no puede confirmarse | ninguno (falló) |
| **E04** | DRAFT | `evaluate_discount(O005)` | **0 %** → 2100.00 MXN | La promoción activa bloquea las dos reglas de descuento | n/a (no es transición) |
| **E05** | DRAFT | `evaluate_discount(O006)` | **5 %** → 17100.00 MXN | Total > 5000 y sin promoción; no es VIP, así que no aplica el 10 % | n/a (no es transición) |
| **E06** | DRAFT | `confirm()` | **RECHAZADO** (`InvalidOrderData`) | El pedido no tiene artículos: se requieren renglones para confirmar | ninguno (falló) |
| **E07** | DRAFT | `confirm()` | **CONFIRMED** | 20 unidades exactas: el límite es 20 y no se excede | `OrderConfirmed` |
| **E08** | DRAFT | `add_item(SKU003 × 2)` | **RECHAZADO** (`OrderItemLimitExceeded`) | 19 + 2 = 21 unidades: el máximo es 20 unidades, no 20 renglones | ninguno (falló) |
| **E09** | DRAFT | `evaluate_discount(O010)` | **0 %** → 500.00 MXN | El total es exactamente 500 y la regla exige `> 500`, no `>= 500` | n/a (no es transición) |
| **E10** | DRAFT | `evaluate_discount(O011)` | **0 %** → 1500.00 MXN | La regla del 10 % exige ≥ 4 unidades y este pedido tiene 3 | n/a (no es transición) |
| **E11** | DRAFT | `confirm()` y `ship("")` | **CONFIRMADO**, envío **RECHAZADO** (`InvalidOrderData`) | La guía de envío es obligatoria: la transición no se ejecuta | `OrderConfirmed` (ninguno por el envío fallido) |
| **E12** | DRAFT | `confirm()` dos veces | 2.ª **RECHAZADA** (`InvalidOrderTransition`) | No se permite confirmar desde CONFIRMED | `OrderConfirmed` (solo uno; el rechazo no registra evento) |
| **E13** | DRAFT | `confirm()`, `ship()` y `cancel()` | Enviado, cancelación **RECHAZADA** (`InvalidOrderTransition`) | Solo se permite cancelar desde CONFIRMED, no desde SHIPPED | `OrderConfirmed`, `OrderShipped` (ninguno por la cancelación fallida) |
| **E14** | DRAFT | `confirm()`, `ship()` y `return_order()` | **RETURNED** | La devolución se permite desde SHIPPED | `OrderConfirmed`, `OrderShipped`, `OrderReturned` |
| **E15** | DRAFT | `confirm()`, `ship()` y `deliver()` | **DELIVERED** | La entrega se permite desde SHIPPED | `OrderConfirmed`, `OrderShipped`, `OrderDelivered` |

## Trazabilidad con `datos/escenarios.csv`

| Caso | Pedido | Acción | Objetivo del paquete | Resultado obtenido | ✔ |
|---|---|---|---|---|:--:|
| E01 | O001 | evaluar_descuento | 10 % | 10 % | ✔ |
| E02 | O002 | evaluar_descuento | 0 % | 0 % | ✔ |
| E03 | O003 | confirmar | rechazo | rechazo (`InvalidOrderData`) | ✔ |
| E04 | O005 | evaluar_descuento | 0 % | 0 % | ✔ |
| E05 | O006 | evaluar_descuento | 5 % | 5 % | ✔ |
| E06 | O007 | confirmar | rechazo | rechazo (`InvalidOrderData`) | ✔ |
| E07 | O008 | confirmar | exito | CONFIRMED | ✔ |
| E08 | O009 | agregar SKU003 × 2 | rechazo | rechazo (`OrderItemLimitExceeded`) | ✔ |
| E09 | O010 | evaluar_descuento | 0 % | 0 % | ✔ |
| E10 | O011 | evaluar_descuento | 0 % | 0 % | ✔ |
| E11 | O012 | confirmar y enviar sin guía | rechazo envio | envío rechazado (`InvalidOrderData`) | ✔ |
| E12 | O013 | confirmar dos veces | rechazo segunda | 2.ª rechazada (`InvalidOrderTransition`) | ✔ |
| E13 | O014 | confirmar, enviar y cancelar | rechazo cancelacion | cancelación rechazada (`InvalidOrderTransition`) | ✔ |
| E14 | O015 | confirmar, enviar y devolver | exito | RETURNED | ✔ |
| E15 | O016 | confirmar, enviar y entregar | exito | DELIVERED | ✔ |

**15 de 15 escenarios coinciden con el objetivo declarado en el paquete.**

## Comprobaciones adicionales sobre los datos

* **E07 / E08 — el límite es de unidades, no de renglones.** O008 tiene **1 renglón con
  20 unidades** (se acepta) y O009 tiene **1 renglón con 19 unidades** (al agregar 2
  unidades más se rechaza). Ninguno de los dos pedidos llega a 20 renglones, así que el
  caso habría pasado igual con un límite por renglones: el límite por renglones es
  justamente el error que este escenariono puede detectar, y el de unidades sí.
* **E08 — el rechazo no muta el pedido.** Tras el `OrderItemLimitExceeded`, O009 conserva
  19 unidades, 1 renglón, estado DRAFT y cero eventos.
* **E11 — la confirmación sí queda registrada.** El envío falla, pero el `OrderConfirmed`
  permanece: son dos operaciones distintas, y solo la segunda falló.
* **E03 y E06 — dos causas distintas de `InvalidOrderData`.** E03 falla por cliente
  inactivo y E06 por pedido sin artículos, aunque el mensaje sea el mismo
  ("Requiere artículos y cliente activo"). Es el aggregate el que decide; la API
  traduce el error a 422 en ambos casos.

## Escenario adicional (no viene en el paquete)

El paquete no incluye un caso donde **apliquen las dos reglas a la vez**, así que la
prioridad "10 % antes que 5 %" no se puede observar con los 16 pedidos: el único pedido
con total > 5000 es O006 y su cliente no es VIP. La prioridad se cubre con una prueba
dedicada que construye el caso en memoria (`tests/test_domain.py`), sin tocar los CSV.
