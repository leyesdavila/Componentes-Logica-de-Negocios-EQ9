# TechStore — Práctica Guiada Actividad 4 (CLN, Unidad 4)

**Componentes de Lógica de Negocio · FIME · UANL**

Núcleo de negocio de la tienda ficticia **TechStore**: entidades y *value objects*,
reglas de descuento con el patrón *Specification*, máquina de estados con eventos
de dominio, un servicio de aplicación que carga los CSV, API REST con FastAPI y una
suite de **116 pruebas** con pytest.

El repositorio es **en memoria**: al cerrar el programa los cambios se pierden
(la persistencia es una ampliación opcional, no exigida por la práctica).

---

## 1. Instalación

Requisito: **Python 3.11 o superior** (probado con 3.14.7).

```powershell
# 1. Crear el entorno virtual
python -m venv .venv

# 2. Activarlo
#    Windows PowerShell:
.venv\Scripts\Activate.ps1
#    Windows CMD:
.venv\Scripts\activate.bat
#    macOS / Linux:
source .venv/bin/activate

# 3. Instalar dependencias
python -m pip install fastapi uvicorn pytest httpx
#    o, con las versiones exactas con las que se validó la entrega:
python -m pip install -r requirements.txt
```

> Si PowerShell bloquea la activación, ejecuta
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
> También puedes usar el ejecutable del entorno directamente:
> `.venv\Scripts\python.exe -m pytest -q`.

## 2. Ejecución

```powershell
# Cargar los 16 pedidos del CSV (punto de control del paso 7)
python cargar_csv.py

# Ejecutar la bitácora reproducible de los 15 escenarios
python scripts/ejecutar_bitacora.py

# Ejecutar la suite completa de pruebas (116 pruebas)
python -m pytest -q

# Levantar la API
uvicorn app.api:app --reload
```

Para regenerar evidencias, documentos y manifiesto existe un solo comando:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\generar_evidencias.ps1
```

| Recurso | URL |
|---|---|
| Documentación interactiva (Swagger) | <http://127.0.0.1:8000/docs> |
| Contrato OpenAPI | <http://127.0.0.1:8000/openapi.json> |
| API base | <http://127.0.0.1:8000/> |

```powershell
# Ejemplos rápidos
curl http://127.0.0.1:8000/orders/O001
curl -X POST http://127.0.0.1:8000/orders/O001/confirm
curl -X POST http://127.0.0.1:8000/orders/O012/ship -H "Content-Type: application/json" -d '{"tracking_number":"G-9"}'
```

## 3. Estructura del proyecto

```
techstore-u4/
├── app/
│   ├── __init__.py
│   ├── domain.py           # Entidades, value objects, invariantes, máquina de estados
│   ├── specifications.py   # Patrón Specification (AND/OR/NOT) y reglas de descuento
│   ├── service.py          # Carga de los CSV y catálogos de clientes/productos
│   └── api.py              # API REST FastAPI (controladores sin reglas duplicadas)
├── tests/
│   ├── conftest.py              # Fixtures compartidos (app, cliente HTTP, pedidos)
│   ├── test_domain.py           # 39 pruebas — value objects, invariantes, descuentos
│   ├── test_api.py              # 26 pruebas — 404 / 409 / 422 y ciclo de vida
│   ├── test_escenarios.py       # 15 pruebas — un caso por escenario E01–E15
│   ├── test_maquina_estados.py  # 21 pruebas — transiciones y eventos
│   ├── test_specifications.py   # 10 pruebas — specifications aisladas y compuestas
│   └── test_servicio.py         # 5 pruebas — carga, catálogos, /health y recarga
├── scripts/
│   ├── ejecutar_bitacora.py     # Ejecuta E01–E15 y genera el CSV de resultados
│   ├── generar_evidencias.py    # Evidencias de pytest/API y manifiesto SHA-256
│   ├── generar_documentos.py    # Reporte técnico y bitácora en DOCX
│   ├── exportar_pdf.ps1         # Actualiza el índice y exporta los PDF con Word
│   └── generar_evidencias.ps1   # Cadena completa: pruebas, evidencias y documentos
├── datos/                 # 5 CSV del paquete (clientes, productos, pedidos, detalle, escenarios)
├── docs/
│   ├── ANALISIS_DATOS.md      # Análisis manual del paso 5 (tabla de los 16 pedidos)
│   ├── DIAGRAMA_ESTADOS.md    # Diagrama de estados + explicación de los Domain Events
│   ├── BITACORA_E01_E15.md    # Bitácora resuelta de los 15 escenarios
│   ├── REFLEXION.md           # Tres errores, su solución y lo aprendido
│   ├── PREGUNTAS_REPORTE.md   # Respuestas a las 5 preguntas de la sección 15
│   ├── Reporte_Tecnico_TechStore_Unidad_4.docx / .pdf   # Reporte técnico completo
│   ├── bitacora/              # Bitácora DOCX/PDF y CSV con los resultados reales
│   ├── diagramas/             # Diagramas UML: .mmd, .puml, .png y .svg
│   └── evidencias/            # Capturas de terminal, de Swagger y contrato OpenAPI
├── evidencias/            # Salidas rápidas: carga, bitácora, pytest y respuestas HTTP
├── cargar_csv.py          # Cargador del paquete (no modificado)
├── README.txt             # Reglas del paquete (no modificado)
├── README_material_original.txt # Copia exacta del README.txt entregado
├── MANIFIESTO_ENTREGA.txt # Inventario, conteos y SHA-256 de los CSV
├── pytest.ini             # Configuración de la suite (salida y advertencias)
├── requirements.txt       # Dependencias de la aplicación y las pruebas
├── requirements-docs.txt  # Dependencias para regenerar DOCX/PDF
└── .gitignore             # Excluye .venv, __pycache__ y .pytest_cache
```

## 4. Reglas de negocio implementadas

### 4.1 Valor `Money`

* Es un **value object inmutable** (`frozen=True`): una vez creado, `amount` no cambia.
* `amount` es un `Decimal`; `currency` es `"MXN"`.
* El constructor **rechaza importes negativos** y valores no finitos (`NaN`, `Infinity`).
* `add()` **rechaza monedas distintas** y devuelve **un objeto nuevo** (nunca muta el original).
* `apply_percentage()` redondea a centavos (`ROUND_HALF_UP`).

### 4.2 Pedido y artículos

| Regla | Comportamiento | Excepción |
|---|---|---|
| Límite de unidades | Máximo **20 unidades** (suma de cantidades, no renglones) | `OrderItemLimitExceeded` |
| Artículo inválido | SKU vacío o cantidad `<= 0` | `InvalidOrderData` |
| Solo MXN | No se admiten artículos con moneda distinta | `InvalidOrderData` |
| Artículos en DRAFT | `add_item()` solo funciona en `DRAFT` | `InvalidOrderTransition` |
| Pedido vacío | Un pedido sin artículos no se puede confirmar | `InvalidOrderData` |
| Cliente inactivo | Un cliente con `activo = 0` no puede confirmar | `InvalidOrderData` |
| Guía de envío | `ship()` exige una guía no vacía | `InvalidOrderData` |
| Motivo de cancelación | `cancel()` exige un motivo no vacío | `InvalidOrderData` |

### 4.3 Descuentos (patrón Specification)

Reglas implementadas en `app/specifications.py` como *specifications* componibles:

| Regla | Condiciones | Descuento |
|---|---|---|
| `TEN_PERCENT_RULE` | cliente VIP **y** total `> 500` **y** `>= 4` unidades **y** sin promoción | **10 %** |
| `FIVE_PERCENT_RULE` | total `> 5000` **y** sin promoción | **5 %** |
| `DISCOUNT_RULE` | `TEN_PERCENT_RULE \| FIVE_PERCENT_RULE` | el mayor aplicable |

* Los umbrales son **estrictos**: `500.00` exacto **no** supera el umbral (`>` y no `>=`).
* Si se cumplen ambas reglas, **aplica primero el 10 %** (prioridad).
* El total con descuento se calcula aparte: `order.total` conserva el importe bruto.

### 4.4 Máquina de estados y eventos de dominio

```
DRAFT --confirm--> CONFIRMED --ship--> SHIPPED --deliver--> DELIVERED
  |                    |                 |
  |                    |                 +--return--> RETURNED
  |                    +--cancel--> CANCELLED
  +--confirm (rechazado si no hay artículos o el cliente está inactivo)
```

| Transición | Evento emitido | Requisito |
|---|---|---|
| `confirm()` | `OrderConfirmed` | estado `DRAFT`, con artículos y cliente activo |
| `ship(guia)` | `OrderShipped` | estado `CONFIRMED`, guía no vacía |
| `cancel(motivo)` | `OrderCancelled` | estado `CONFIRMED`, motivo no vacío |
| `deliver()` | `OrderDelivered` | estado `SHIPPED` |
| `return_order()` | `OrderReturned` | estado `SHIPPED` |

**Patrón aplicado en los cinco métodos: validar → cambiar `status` → registrar el evento
al final.** Una operación inválida **no cambia el estado ni añade eventos**.

## 5. Endpoints de la API

| Método | Ruta | Descripción | Respuestas |
|---|---|---|---|
| `GET` | `/` | Información de la API | 200 |
| `GET` | `/orders` | Resumen de los 16 pedidos | 200 |
| `GET` | `/orders/{order_id}` | Detalle del pedido (renglones, total, descuento, reglas, eventos) | 200 · 404 |
| `GET` | `/orders/{order_id}/rules` | Evaluación regla por regla de los descuentos | 200 · 404 |
| `POST` | `/orders/{order_id}/confirm` | `DRAFT → CONFIRMED` | 200 · 404 · 409 · 422 |
| `POST` | `/orders/{order_id}/ship` | `CONFIRMED → SHIPPED` (cuerpo: `tracking_number`) | 200 · 404 · 409 · 422 |
| `POST` | `/orders/{order_id}/cancel` | `CONFIRMED → CANCELLED` (cuerpo: `reason`) | 200 · 404 · 409 · 422 |
| `POST` | `/orders/{order_id}/deliver` | `SHIPPED → DELIVERED` | 200 · 404 · 409 |
| `POST` | `/orders/{order_id}/return` | `SHIPPED → RETURNED` | 200 · 404 · 409 |
| `POST` | `/orders/{order_id}/items` | Agrega un renglón (cuerpo: `sku`, `quantity`) | 200 · 404 · 409 · 422 |
| `POST` | `/orders` | Crea un pedido (cuerpo: `cliente_id`, `items[]`) | 201 · 422 |
| `GET` | `/health` | Estado del servicio y número de pedidos cargados | 200 |
| `POST` | `/admin/reload-fixtures` | Vuelve a leer los CSV sin reiniciar el proceso | 200 |

Además, FastAPI publica automáticamente cuatro rutas auxiliares que **no son
endpoints de negocio** y por eso no aparecen en la tabla anterior. Las dos últimas
rutas de esa tabla (`/health` y `/admin/reload-fixtures`) sí son endpoints de
apoyo declarados por el proyecto:

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/docs` | Interfaz de Swagger UI (evidencias `06`, `08`, `09`, `10`) |
| `GET` | `/redoc` | Documentación alternativa en ReDoc |
| `GET` | `/openapi.json` | Esquema OpenAPI 3.1 de la API (evidencia `07`) |
| `GET` | `/docs/oauth2-redirect` | Redirección OAuth2 de Swagger UI |

Estas rutas las genera el framework y **no aparecen en `openapi.json`**, porque
FastAPI solo publica en el esquema las rutas declaradas con decoradores
(`APIRoute`); las de documentación se sirven fuera de ese contrato.

`/health` y `/admin/reload-fixtures` permiten comprobar el estado y repetir una
demostración sin reiniciar el servidor. La recarga vuelve a leer `datos/*.csv`,
descarta los cambios en memoria y **nunca escribe en los archivos**.

Códigos HTTP y su significado:

| Código | Cuándo se devuelve |
|---|---|
| **404** | El pedido no existe |
| **409** | La transición no está permitida desde el estado actual (`InvalidOrderTransition`) |
| **422** | Los datos violan una invariante (`InvalidOrderData`, `OrderItemLimitExceeded`) |

Los controladores **no repiten las reglas de negocio**: localizan el pedido, llaman al
método del agregado `Order` y traducen la excepción del dominio al código HTTP
correspondiente. Los importes viajan como **cadenas** (`"2100.00"`) para no perder
exactitud decimal en la serialización JSON.

## 6. Pruebas

```powershell
python -m pytest -q          # 116 pruebas, todas en verde
```

| Archivo | Pruebas | Cubre |
|---|---|---|
| `tests/test_domain.py` | 39 | `Money`, `OrderItem`, invariantes del pedido, descuentos y composición de specifications |
| `tests/test_api.py` | 26 | 404 / 409 / 422, ciclo de vida completo, creación de pedidos, `/health` y recarga |
| `tests/test_escenarios.py` | 15 | Un caso por escenario E01–E15 |
| `tests/test_maquina_estados.py` | 21 | Transiciones permitidas y prohibidas, eventos emitidos |
| `tests/test_specifications.py` | 10 | Specifications aisladas, compuestas y prioridad del 10 % |
| `tests/test_servicio.py` | 5 | Carga desde `datos/`, fixtures alternativos, catálogos y recarga |
| **Total** | **116** | Suite completa en verde |

Las pruebas de la API usan `with TestClient(app)`, que dispara el ciclo de vida de la
aplicación y **recarga los fixtures en cada prueba**: cada caso parte de los 16 pedidos
en `DRAFT` y no hereda el estado del anterior. Los fixtures compartidos viven en
`tests/conftest.py`.

## 7. Escenarios E01–E15

La bitácora completa (estado inicial, operación, resultado real, explicación y evento
emitido) está en [`docs/BITACORA_E01_E15.md`](docs/BITACORA_E01_E15.md).

| Caso | Situación | Resultado |
|---|---|---|
| E01 | O001: VIP, 2100.00, 4 unidades, sin promoción | 10 % → **1890.00** |
| E02 | O002: no VIP, 3 unidades, total 1050.00 | sin descuento |
| E03 | O003: cliente inactivo | `InvalidOrderData` al confirmar |
| E04 | O005: promoción activa, 2100.00 | excluido del descuento |
| E05 | O006: 18000.00, sin promoción | 5 % → **17100.00** |
| E06 | O007: pedido sin artículos | `InvalidOrderData` al confirmar |
| E07 | O008: 20 unidades exactas | permitido |
| E08 | O009: 19 unidades + 2 | `OrderItemLimitExceeded` (21 > 20) |
| E09 | O010: total exactamente 500.00 | sin descuento (umbral estricto) |
| E10 | O011: 3 unidades | sin descuento (se exigen 4) |
| E11 | O012: envío sin guía | `InvalidOrderData` |
| E12 | O013: confirmar dos veces | 2.ª lanza `InvalidOrderTransition`, sin eventos extra |
| E13 | O014: cancelar desde `SHIPPED` | `InvalidOrderTransition` |
| E14 | O015: devolución | `SHIPPED → RETURNED`, evento `OrderReturned` |
| E15 | O016: entrega | `SHIPPED → DELIVERED`, evento `OrderDelivered` |

## 8. Evidencias

En [`docs/evidencias/`](docs/evidencias):

| Archivo | Contenido |
|---|---|
| `01_carga_csv.txt` | Carga exitosa de los 16 pedidos en `DRAFT` |
| `11_carga_16_pedidos.png` | **Captura de terminal** de `python cargar_csv.py` con los 16 pedidos |
| `02_maquina_estados.txt` | Ejecución de las transiciones y eventos |
| `03_escenarios.txt` | Salida de los 15 escenarios E01–E15 |
| `04_pytest.txt` | Salida completa de `pytest -v` (116 pruebas) |
| `12_pytest_resultados.png` | **Captura de terminal** de `python -m pytest -q` (116 passed) |
| `05_respuestas_http.txt` | Respuestas 200 / 404 / 409 / 422 contra la API en vivo |
| `06_swagger_docs.png` | Vista general de `/docs` |
| `07_openapi.json` | Contrato OpenAPI generado |
| `08_swagger_exito_200.png` | Swagger: `POST /orders/O001/confirm` → **HTTP 200** |
| `09_swagger_rechazo_404.png` | Swagger: `POST /orders/NOEXISTE/confirm` → **HTTP 404** |
| `10_swagger_rechazo_422.png` | Swagger: `POST /orders/O007/confirm` → **HTTP 422** |

Las capturas de Swagger son ejecuciones reales de la petición desde la interfaz
`/docs` (botón *Try it out* → *Execute*), no imágenes simuladas.

La carpeta raíz [`evidencias/`](evidencias/) contiene, además, las salidas
reproducibles que produce `scripts/generar_evidencias.py`:
`carga_csv.txt`, `bitacora_consola.txt`, `resultado_pytest.txt` y
`respuestas_api.json`.

### 8.1 Diagramas

Los diagramas UML están en [`docs/diagramas/`](docs/diagramas/), separados de las
capturas. Cada uno incluye fuente Mermaid (`.mmd`), fuente PlantUML (`.puml`),
render `.png` y render vectorial `.svg`:

| Diagrama | Render | Contenido |
|---|---|---|
| Estados | [`estados.png`](docs/diagramas/estados.png) · [`.svg`](docs/diagramas/estados.svg) | Máquina de estados de `Order` y Domain Events |
| Clases | [`clases.png`](docs/diagramas/clases.png) · [`.svg`](docs/diagramas/clases.svg) | Entidades, value objects y excepciones |
| Specifications | [`especificaciones.png`](docs/diagramas/especificaciones.png) · [`.svg`](docs/diagramas/especificaciones.svg) | Patrón Specification y reglas de descuento |
| Secuencia | [`secuencia-confirmar.png`](docs/diagramas/secuencia-confirmar.png) · [`.svg`](docs/diagramas/secuencia-confirmar.svg) | `POST /orders/{id}/confirm`: 404 / 409 / 422 / 200 |
| Flujo | [`flujo-confirmacion.png`](docs/diagramas/flujo-confirmacion.png) · [`.svg`](docs/diagramas/flujo-confirmacion.svg) | Decisión de la confirmación paso a paso |

Índice completo con todos los renders y las fuentes:
[`docs/diagramas/README.md`](docs/diagramas/README.md).

### 8.2 Documentos

| Documento | Contenido |
|---|---|
| [`docs/Reporte_Tecnico_TechStore_Unidad_4.pdf`](docs/Reporte_Tecnico_TechStore_Unidad_4.pdf) | Reporte técnico completo (20 páginas, portada con campos en blanco) |
| [`docs/Reporte_Tecnico_TechStore_Unidad_4.docx`](docs/Reporte_Tecnico_TechStore_Unidad_4.docx) | Fuente editable, con índice automático de Word |
| [`docs/bitacora/Bitacora_TechStore.pdf`](docs/bitacora/Bitacora_TechStore.pdf) | Bitácora con las 15 fichas de escenario (10 páginas) |
| [`docs/bitacora/Bitacora_TechStore.docx`](docs/bitacora/Bitacora_TechStore.docx) | Fuente editable de la bitácora |
| [`docs/bitacora/bitacora_escenarios.csv`](docs/bitacora/bitacora_escenarios.csv) | Resultados reales de E01–E15 (15/15 coinciden) |
| [`MANIFIESTO_ENTREGA.txt`](MANIFIESTO_ENTREGA.txt) | Inventario, conteos y SHA-256 de los cinco CSV |

Los documentos se regeneran con el Python del sistema (que tenga `python-docx`) y
Microsoft Word:

```powershell
C:\Python314\python.exe scripts\generar_documentos.py
powershell -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1
```

## 9. Lista de verificación (sección 14 de la práctica)

| # | Verificación | Estado |
|---|---|---|
| 1 | `python cargar_csv.py` se ejecuta sin errores | ✅ |
| 2 | O001 muestra 4 unidades y 2100.00 MXN | ✅ |
| 3 | La regla del 10 % exige VIP, `>500`, `>=4` unidades y ausencia de promoción | ✅ |
| 4 | La regla del 5 % exige `>5000` y ausencia de promoción | ✅ |
| 5 | Una operación inválida no cambia el estado ni añade eventos | ✅ |
| 6 | La API responde 404, 409 y 422 en los casos indicados | ✅ |
| 7 | `pytest` termina sin fallos | ✅ (116 passed) |
| 8 | El repositorio contiene README y evidencias | ✅ |
| 9 | La bitácora E01–E15 coincide con el objetivo del paquete | ✅ (15/15) |
| 10 | El reporte técnico y la bitácora están en DOCX y PDF | ✅ (20 y 10 páginas) |

## 10. Notas y decisiones de diseño

* **No se modificó ningún CSV ni `cargar_csv.py`**: los escenarios se ejecutan tal como
  vienen en el paquete, como exige la regla didáctica del `README.txt`.
* La **carga de datos vive en `app/service.py`**: la API, los scripts y las pruebas
  comparten `load_orders()`, y `catalogo_productos()`/`catalogo_clientes()` evitan
  duplicar precios o atributos en el controlador.
* El **descuento se calcula aparte** del total bruto: `order.total` conserva el importe
  sin descuento (como pide el enunciado: `O001.total.amount == Decimal("2100.00")`) y
  `evaluate_discount(order)` devuelve el porcentaje aplicado y el total final.
* `Money` no restringe la moneda en el constructor (la regla «monedas distintas» se
  valida en `add()`); es el agregado `Order` quien exige MXN al agregar artículos.
* El repositorio Git es **local** (`main`); no se configuró remoto ni se hizo `push`.
  Se puede publicar en GitHub con `git remote add origin <url>` y `git push -u origin main`.
* La única advertencia de `pytest` proviene de Starlette/httpx (no del código del
  proyecto): `StarletteDeprecationWarning` sobre el `TestClient`.
* Los documentos DOCX usan **índice automático de Word**, tablas con encabezado
  repetido y filas indivisibles; los PDF se exportan con Word para actualizar los
  campos antes de guardarlos.

## 11. Documentación complementaria

* [`docs/ANALISIS_DATOS.md`](docs/ANALISIS_DATOS.md) — análisis manual de los CSV (paso 5).
* [`docs/DIAGRAMA_ESTADOS.md`](docs/DIAGRAMA_ESTADOS.md) — diagrama de estados y
  explicación de los eventos de dominio.
* [`docs/diagramas/`](docs/diagramas/README.md) — diagramas UML de estados, clases,
  specifications, secuencia y flujo (fuentes `.mmd`/`.puml` y renders `.png`/`.svg`).
* [`docs/BITACORA_E01_E15.md`](docs/BITACORA_E01_E15.md) — bitácora de los 15 escenarios.
* [`docs/bitacora/`](docs/bitacora/) — bitácora DOCX/PDF y CSV con los resultados reales.
* [`docs/Reporte_Tecnico_TechStore_Unidad_4.pdf`](docs/Reporte_Tecnico_TechStore_Unidad_4.pdf)
  — reporte técnico completo (20 páginas) con anexos de preguntas, glosario y comandos.
* [`docs/REFLEXION.md`](docs/REFLEXION.md) — tres errores encontrados, su solución y lo aprendido.
* [`docs/PREGUNTAS_REPORTE.md`](docs/PREGUNTAS_REPORTE.md) — respuestas a las 5 preguntas del reporte.
* [`MANIFIESTO_ENTREGA.txt`](MANIFIESTO_ENTREGA.txt) — inventario y huellas SHA-256 de los CSV.

---

**Autor:** Jonathan Alexander Reyes García — `jonathan.reyesg@uanl.edu.mx`
**Curso:** Componentes de Lógica de Negocio (CLN), Unidad 4 — FIME, UANL
