# Análisis de los CSV (Paso 5 de la Práctica Guiada)

Análisis manual de `datos/` previo a escribir código, conforme a la sección 5 de
`CLN_U4_Practica_Guiada_Alumnos_TechStore.pdf`.

## 1. Relaciones entre los archivos

```
clientes.csv  ──cliente_id──►  pedidos.csv  ──pedido_id──►  detalle_pedidos.csv
                                     │                              │
                                     │                              └──sku──►  productos.csv
                                     │
                                     └──pedido_id──►  escenarios.csv
```

| Archivo | Llave | Contenido | Conteo |
|---|---|---|---|
| `clientes.csv` | `cliente_id` | nombre, `es_vip`, `activo` (1 = sí, 0 = no) | 12 |
| `productos.csv` | `sku` | nombre, `precio_mxn`, `existencia` | 12 |
| `pedidos.csv` | `pedido_id` | `cliente_id`, `tiene_promocion`, `estado_inicial`, `descripcion` | 16 |
| `detalle_pedidos.csv` | (`pedido_id`, `sku`) | `cantidad` | 21 renglones |
| `escenarios.csv` | `caso_id` | `pedido_id`, `accion`, `objetivo`, `pista` | 15 (E01–E15) |

Notas:

- `existencia` es **solo catálogo**: esta práctica no descuenta inventario.
- Todos los pedidos nacen en `DRAFT` para que la máquina de estados sea ejecutable.
- `escenarios.csv` guarda el *tipo* de resultado esperado (`objetivo`), no el valor numérico:
  hay que calcularlo.

## 2. Actividad corta: O001, O006 y O010

### O001 — 4 unidades, 2100.00 MXN

| Dato | Valor |
|---|---|
| Cliente | `C001` — **Ana Torres** (`es_vip=1`, `activo=1`) |
| Renglones | `SKU001` Mouse inalábrico 600.00 × 2 = 1200.00 |
| | `SKU002` Teclado mecánico 450.00 × 2 = 900.00 |
| Unidades | 2 + 2 = **4** |
| Total | 1200.00 + 900.00 = **2100.00 MXN** |

Es el caso base del **descuento de 10 %**: es VIP (✓), 2100.00 > 500 (✓), 4 ≥ 4 unidades (✓)
y no tiene promoción (✓) → 2100.00 − 210.00 = **1890.00 MXN**.

> El ejemplo del PDF ("SKU001, cantidad 2, precio 600.00 → subtotal 1200.00") corresponde
> exactamente a la primera línea de O001.

### O006 — 1 unidad, 18000.00 MXN

| Dato | Valor |
|---|---|
| Cliente | `C006` — **Pedro Soto** (`es_vip=0`, `activo=1`) |
| Renglones | `SKU008` Laptop empresarial 18000.00 × 1 = 18000.00 |
| Unidades | 1 |
| Total | **18000.00 MXN** |

No es VIP y tiene una sola unidad, así que la regla del 10 % no se cumple; pero
18000.00 > 5000 y no tiene promoción → aplica el **descuento de 5 %** → 17100.00 MXN.

### O010 — 2 unidades, 500.00 MXN

| Dato | Valor |
|---|---|
| Cliente | `C010` — **Jorge Luna** (`es_vip=0`, `activo=1`) |
| Renglones | `SKU003` Cable USB-C 120.00 × 1 = 120.00 |
| | `SKU009` Hub USB 380.00 × 1 = 380.00 |
| Unidades | 1 + 1 = **2** |
| Total | 120.00 + 380.00 = **500.00 MXN** |

El total es **exactamente 500.00**, no lo *supera*: la regla exige `> 500`, no `>= 500`,
por lo que **no hay descuento**. Es el caso frontera que separa `>` de `>=`.

## 3. Mapa completo de los 16 pedidos

Referencia para la bitácora E01–E15 y para las pruebas.

| Pedido | Cliente | VIP | Activo | Promo | Renglones | Unidades | Total | Descuento | Resultado |
|---|---|:--:|:--:|:--:|:--:|:--:|---:|:--:|---|
| O001 | C001 Ana Torres | ✔ | ✔ | – | 2 | 4 | 2100.00 | 10 % | 1890.00 |
| O002 | C002 Luis Medina | – | ✔ | – | 2 | 2 | 1050.00 | 0 % | 1050.00 |
| O003 | C003 Carla Ruiz | ✔ | ✘ | – | 2 | 4 | 2100.00 | (10 %) | confirmar rechazado: cliente inactivo |
| O004 | C004 Diego Peña | – | ✘ | – | 1 | 1 | 850.00 | 0 % | confirmar rechazado: cliente inactivo |
| O005 | C005 Sofía Lara | ✔ | ✔ | ✔ | 2 | 4 | 2100.00 | 0 % | promoción bloquea el descuento |
| O006 | C006 Pedro Soto | – | ✔ | – | 1 | 1 | 18000.00 | 5 % | 17100.00 |
| O007 | C007 Mariana Gil | ✔ | ✔ | – | **0** | 0 | 0.00 | 0 % | confirmar rechazado: sin artículos |
| O008 | C008 Raúl Vega | – | ✔ | – | 1 | **20** | 2400.00 | 0 % | confirmar permitido (límite exacto) |
| O009 | C009 Elena Mora | ✔ | ✔ | – | 1 | 19 | 2280.00 | 10 % | al agregar 2 más → 21 → excede |
| O010 | C010 Jorge Luna | – | ✔ | – | 2 | 2 | 500.00 | 0 % | umbral estricto `> 500` |
| O011 | C011 Valeria Ríos | ✔ | ✔ | – | 2 | 3 | 1500.00 | 0 % | requiere ≥ 4 unidades |
| O012 | C012 Oscar Nieto | – | ✔ | – | 1 | 1 | 850.00 | 0 % | envío sin guía → rechazado |
| O013 | C001 Ana Torres | ✔ | ✔ | – | 1 | 1 | 600.00 | 0 % | confirmar dos veces → 2.ª rechazada |
| O014 | C002 Luis Medina | – | ✔ | – | 1 | 1 | 600.00 | 0 % | cancelar desde SHIPPED → rechazado |
| O015 | C005 Sofía Lara | ✔ | ✔ | – | 1 | 1 | 450.00 | 0 % | devolución → RETURNED |
| O016 | C007 Mariana Gil | ✔ | ✔ | – | 1 | 1 | 2100.00 | 0 % | entrega → DELIVERED |

Comprobación de conteos: 12 clientes, 12 productos, 16 pedidos, 21 renglones, 15 escenarios.

## 4. Conclusiones que condicionan el diseño

1. **Unidades ≠ renglones.** O001 tiene 2 renglones y 4 unidades; O008 tiene **1 renglón y
   20 unidades**; O007 tiene 0 renglones y 0 unidades. El límite de 20 aplica a la **suma de
   cantidades**, no al número de filas.
2. **El catálogo no restringe el pedido.** O008 pide 20 unidades de `SKU003` y su `existencia`
   es 70; O009 pide 19 y el mismo producto tiene 70. El `existencia` nunca invalida un renglón.
3. **Tres escenarios de frontera** dependen de comparadores exactos:
   - `O010` → total 500.00 exacto prueba `>` vs `>=` en el monto;
   - `O011` → 3 unidades prueba `>= 4` en unidades;
   - `O008` → 20 unidades exactas prueba `> 20` vs `>= 20` en el límite.
4. **O003 y O005 repiten el detalle de O001** (2 renglones, 2100.00) y solo cambian de cliente
   o de promoción: el dataset aísla una variable por escenario, así que un fallo en la regla de
   descuento se detecta de inmediato.
5. **O009 es el caso de sobrecarga**: 19 unidades en DRAFT; añadir `SKU003 × 2` deja 21 y debe
   lanzar `OrderItemLimitExceeded` **sin** modificar `items`.
6. **Cada escenario se apoya en un pedido con precondiciones distintas**, de modo que recargar
   los fixtures entre casos no es opcional en E11–E15 (mismo orden base, distintas transiciones).
