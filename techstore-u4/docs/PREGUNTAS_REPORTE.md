# Preguntas para el reporte — sección 15 de la Práctica Guiada Actividad 4

**Alumno:** Jonathan Alexander Reyes García · jonathan.reyesg@uanl.edu.mx
**Proyecto:** TechStore — Componentes de Lógica de Negocio, Unidad 4 (FIME · UANL)

Las cinco respuestas están fundamentadas en el código de este repositorio; cada una
remite a los archivos y a los datos que la sostienen.

---

## 1. ¿Por qué se usa `Decimal` en lugar de `float` para precios?

Porque `float` representa los números en **base 2 (binario)**, y muchos importes
decimales —como los precios con centavos— **no se pueden escribir de forma exacta en
binario**. Es el mismo motivo por el que `0.1 + 0.2` da `0.30000000000000004` en Python.
En un sistema de pedidos eso no es un detalle teórico: el error se acumula renglón por
renglón y termina en un total que no cuadra con la factura.

`Decimal` representa números **en base 10**, que es como escribimos los precios. Con
`Decimal("600.00")` el valor es exactamente el que se lee en el catálogo, y las
sumas y multiplicaciones son exactas.

En el proyecto el detalle se cuida en tres lugares:

* **`app/domain.py`** — `Money.amount` es un `Decimal` y `Money.__post_init__` convierte
  cualquier entrada con `Decimal(str(self.amount))`. La conversión **por texto** es
  deliberada: `Decimal(19.99)` (desde `float`) guarda el valor binario exacto
  `19.989999999999998436805981327779591083526611328125`, mientras que
  `Decimal("19.99")` guarda exactamente `19.99`. La diferencia se demuestra en
  `tests/test_domain.py::test_money_convierte_float_a_decimal_sin_deriva_binaria`.
* **Redondeo explícito** — `Money.apply_percentage()` redondea a centavos con
  `ROUND_HALF_UP`, de modo que el 10 % de 2100.00 sea `1890.00` y no una cola de
  decimales.
* **Serialización sin pérdida** — en la API los importes viajan como **cadenas**
  (`"2100.00"`). Al convertir un `Decimal` a `float` para meterlo en un `float` de
  JSON se volvería a perder exactitud; como cadena, el valor viaja intacto y el
  cliente puede volver a interpretarlo como decimal.

**Conclusión:** `float` es rápido pero aproximado; `Decimal` es exacto y predecible.
En dinero, la previsibilidad es el requisito.

---

## 2. ¿Cuál es la diferencia entre contar renglones y sumar unidades?

Son dos medidas distintas y la práctica las usa para cosas distintas:

| Concepto | Definición | Implementación |
|---|---|---|
| **Renglón** | Una línea del detalle: un SKU con su cantidad. | `len(order.items)` |
| **Unidades** | La **suma de las cantidades** de todos los renglones. | `sum(item.quantity for item in self.items)` |

El caso real que lo aclara es **O008**: tiene **1 renglón** (`SKU003` × 20) y
**20 unidades**. Y **O011** tiene **2 renglones** (`SKU001` × 1 y `SKU002` × 2) pero solo
**3 unidades**. Confundir ambas cosas produce dos errores opuestos y graves:

* Si el **límite de 20** se contara por renglones, un pedido de 40 unidades repartidas
  en 2 renglones entraría sin problema. El `README.txt` del paquete lo dice de forma
  explícita: «Máximo 20 unidades por pedido (**no 20 líneas**)». Por eso
  `Order.add_item()` compara `self.units + item.quantity > 20`, es decir, **unidades**.
* Si el **descuento del 10 %** exigiera 4 renglones en lugar de 4 unidades, un pedido
  de 4 unidades de un solo artículo (como O011 con 3 unidades, o un pedido de 4 x
  SKU001) no calificaría aunque el cliente haya comprado 4 piezas.

Las dos medidas se usan así en el código:

* `Order.units` → límite de 20 unidades (`OrderItemLimitExceeded`) y regla del 10 %
  (`>= 4` unidades).
* `len(order.items)` → solo para **mostrar** cuántos artículos distintos tiene el
  pedido (campo `renglones` de la API y de la bitácora).

Además, `Order.total` se calcula a partir de los **subtotales**, que ya multiplican
cantidad × precio; ningún total se obtiene multiplicando el número de renglones por
algo.

**Conclusión:** el renglón describe **la forma** del pedido (qué artículos lo
componen); la unidad describe **la cantidad** que se purchased. Las reglas de negocio
—límite y descuento— hablan de unidades, porque es lo que el cliente lleva.

---

## 3. ¿Qué ventaja tiene encapsular una regla en `Specification`?

Una `Specification` convierte una regla de negocio en un **objeto que se puede
combinar, probar y reutilizar**, en lugar de un `if` suelto dentro de un método.

La implementación (`app/specifications.py`) da cinco ventajas concretas:

1. **Composición con operadores.** `&`, `|` y `~` construyen especificaciones
   compuestas, y las reglas se leen casi como el enunciado:

   ```python
   TEN_PERCENT_RULE = (
       MinimumAmountSpec(Decimal("500"))
       & VIPCustomerSpec()
       & MinimumUnitsSpec(4)
       & ~ActivePromotionSpec()
   )
   DISCOUNT_RULE = TEN_PERCENT_RULE | FIVE_PERCENT_RULE
   ```

   La regla del 10 % **es** el enunciado de la sección 8, sin una sola variable
   intermedia ni un `and` anidado.

2. **Reutilización y una sola fuente de verdad.** `MinimumAmountSpec(500)` no se
   escribe dos veces: la regla del 10 % la usa, y `ActivePromotionSpec` la comparten
   las dos reglas de descuento. Si mañana el umbral cambia, se cambia en un lugar.

3. **Reglas evaluables sin efectos secundarios.** `is_satisfied_by(order)` es un
   **predicado**: solo observa, nunca modifica el pedido. Eso permite evaluarlas en
   cualquier momento (incluido dentro de la API, en `GET /orders/{id}/rules`) sin
   riesgo de efectos secundarios, y lo verifica
   `tests/test_domain.py::test_la_specification_no_modifica_el_pedido`.

4. **Diagnóstico explicable.** Cada especificación sabe describirse
   (`description()`), así que la API puede mostrar **por qué** un pedido recibe o no
   descuento, regla por regla:

   ```json
   "reglas": [
     {"regla": "total > 500", "cumple": true},
     {"regla": "cliente VIP", "cumple": true},
     {"regla": "unidades >= 4", "cumple": true},
     {"regla": "NOT promoción activa", "cumple": true}
   ]
   ```

   Con `if` anidados, esa explicación no sería posible sin duplicar la lógica.

5. **Pruebas aisladas y composables.** Cada especificación se prueba por separado y
   las combinaciones se prueban como un objeto:

   ```python
   assert (vip & monto).is_satisfied_by(o001) is True
   assert (vip | unidades).is_satisfied_by(o002) is False
   assert (~vip).is_satisfied_by(o002) is True
   ```

**Conclusión:** la `Specification` no es una abstracción gratuita: es lo que permite
que las reglas se **comprongan, se compongan, se expliquen y se prueben** como datos y
no como control de flujo disperso.

---

## 4. ¿Por qué los eventos se registran solo después de una transición válida?

Porque **el registro del evento es la confirmación de que la transición ocurrió**. Si
se añadiera el evento antes de validar (o se añadiera aunque la validación fallara),
el historial del pedido mentiría.

El patrón que usan los cinco métodos de `app/domain.py` es siempre el mismo:

```python
def confirm(self) -> None:
    if self.status != OrderStatus.DRAFT:          # 1. validar
        raise InvalidOrderTransition("Solo DRAFT")
    if not self.items or not self.customer.active:
        raise InvalidOrderData("Requiere artículos y cliente activo")
    self.status = OrderStatus.CONFIRMED           # 2. cambiar el estado
    self.events.append(DomainEvent("OrderConfirmed", self.id))   # 3. registrar
```

Las tres razones de fondo:

1. **Integridad del historial.** Los eventos son la memoria de lo que le pasó al
   pedido. Si un evento se escribiera antes de validar, un `confirm()` fallido
   dejaría un `OrderConfirmed` en un pedido que sigue en `DRAFT`: el historial
   afirmaría una transición que nunca ocurrió. El ejercicio de la sección 9 lo pide
   explícitamente: la segunda confirmación de O013 **no debe** añadir otro evento, y
   eso es exactamente lo que comprueba
   `tests/test_maquina_estados.py::test_confirmacion_doble_no_agrega_evento`.

2. **Atomicidad de la operación.** La excepción se lanza **antes** de cualquier
   mutación, así que un fallo no deja el pedido a medio camino: o cambió por completo
   (estado + evento), o no cambió nada. Es la garantía que exige la lista de
   verificación de la sección 14: «Una operación inválida no cambia el estado ni
   añade eventos».

3. **Coherencia entre estado e historial.** El evento y el `status` van juntos: tras
   `confirm()` se cumple simultáneamente `status == CONFIRMED` y
   `"OrderConfirmed" in [e.name for e in order.events]`. Si se pudieran desincronizar,
   cualquier consumidor del historial (un auditor, una proyección, otra interfaz)
   tendría que decidir cuál de los dos manda.

Además, `DomainEvent` es **inmutable** (`frozen=True`) y lleva `occurred_at` con
zona horaria (`datetime.now(timezone.utc)`), de modo que un evento ya registrado no
puede alterarse: el historial es append-only.

**Conclusión:** validar → cambiar → registrar no es una convención de estilo, es la
regla que hace que el historial de eventos sea una fuente de verdad. Si el evento se
registrara antes de validar, estaríamos guardando la intención en lugar del hecho.

---

## 5. ¿Qué parte del código podrías reutilizar si reemplazas FastAPI por otra interfaz?

Prácticamente **todo el dominio**: `app/domain.py` y `app/specifications.py` no
importan FastAPI (ni Starlette, ni Pydantic, ni nada de la capa web). Son código
Python puro, con la única dependencia de la biblioteca estándar (`dataclasses`,
`decimal`, `enum`, `datetime`).

| Pieza | ¿Se reutiliza? | Por qué |
|---|---|---|
| `app/domain.py` (entidades, value objects, invariantes, máquina de estados, eventos) | **Sí, al 100 %** | No tiene ninguna dependencia de FastAPI; contiene las reglas. |
| `app/specifications.py` (patrón Specification y reglas de descuento) | **Sí, al 100 %** | Son funciones y clases puras sobre `Order`. |
| `tests/test_domain.py`, `tests/test_escenarios.py`, `tests/test_maquina_estados.py` (75 pruebas) | **Sí, al 100 %** | No usan `TestClient`; son la red de seguridad que garantiza que la lógica no se rompió al cambiar de interfaz. |
| `cargar_csv.py` y `datos/*.csv` | **Sí, al 100 %** | La fuente de datos es independiente de la presentación. |
| `app/api.py` | **Solo la capa delgada** | Aquí vive lo específico de HTTP: rutas, modelos Pydantic de entrada/salida y la traducción de excepciones a códigos HTTP. |

La clave está en **dónde está el límite**:

* **Las reglas viven en el agregado `Order`.** El controlador solo hace tres cosas:
  buscar el pedido, llamar al método del dominio y traducir la excepción. Como el PDF
  lo pide —«No copies las validaciones de negocio al endpoint»—, el endpoint
  `confirm_order` no sabe qué es un pedido vacío ni qué es un cliente inactivo:

  ```python
  order = orders.get(order_id)
  if order is None:
      raise HTTPException(status_code=404, detail="No existe")
  try:
      order.confirm()
  except InvalidOrderTransition as exc:
      raise HTTPException(status_code=409, detail=str(exc))
  except InvalidOrderData as exc:
      raise HTTPException(status_code=422, detail=str(exc))
  ```

  El `if order is None` y el `try/except` **son** la lógica de la interfaz; todo lo
  demás es negocio y vive en otro lado.

* **La traducción de excepciones es un diccionario pequeño y explícito.** Cambiar de
  interfaz es reescribir ese diccionario, no las reglas:

  | Excepción del dominio | REST (FastAPI) | CLI | GUI / otro |
  |---|---|---|---|
  | `InvalidOrderTransition` | 409 Conflict | mensaje + código de salida 2 | diálogo «operación no permitida» |
  | `InvalidOrderData` | 422 Unprocessable Content | mensaje + código de salida 1 | formulario con error en campo |
  | `OrderItemLimitExceeded` | 422 Unprocessable Content | mensaje + código de salida 1 | aviso de límite |
  | *(recurso inexistente)* | 404 Not Found | «no existe» | pantalla de vacío |

  Las cuatro excepciones (`DomainException`, `InvalidOrderData`,
  `InvalidOrderTransition`, `OrderItemLimitExceeded`) ya viven en el dominio: cualquier
  interfaz nueva las puede distinguir sin tocar el dominio.

* **Ejemplo concreto.** Una interfaz de línea de comandos sería:

  ```python
  # cli.py — nueva interfaz, mismo dominio
  from app.domain import DomainException, InvalidOrderTransition, InvalidOrderData
  from cargar_csv import load_fixture

  def confirmar(order_id: str) -> int:
      orders = load_fixture()
      order = orders.get(order_id)
      if order is None:
          print(f"No existe el pedido {order_id}")
          return 1
      try:
          order.confirm()
      except InvalidOrderTransition as exc:
          print(f"No se puede confirmar: {exc}")
          return 2
      except InvalidOrderData as exc:
          print(f"Datos inválidos: {exc}")
          return 1
      print(f"{order.id} confirmado: {order.total.amount} MXN")
      return 0
  ```

  Ni una línea de `app/domain.py` ni de `app/specifications.py` cambiaría, y las 72
  pruebas del dominio seguirían pasando sin modificación. Esa es la prueba de que
  **el núcleo de negocio está realmente separado de la interfaz**.

**Conclusión:** lo reutilizable es el **núcleo** (dominio + specifications + datos +
sus pruebas); lo que habría que reescribir es solo el **adaptador** (rutas, modelos de
entrada/salida y el mapeo de excepciones). Separar esa frontera desde el principio es
lo que hace barato el cambio de interfaz.
