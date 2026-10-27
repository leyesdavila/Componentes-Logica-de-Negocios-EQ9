# Reflexión — Práctica Guiada Actividad 4 (TechStore, CLN Unidad 4)

> Tres errores encontrados durante el desarrollo, cómo los solucioné y qué aprendí.
> Los errores están narrados como ocurrieron: lo que falló, por qué falló y cuál fue
> la corrección real (nunca "arreglar" los datos para que la prueba pasara).

---

## Error 1 — `NameError` al definir los modelos de la API

**Qué pasó.** Al escribir `app/api.py` declaré primero `OrderIn` y después `ItemIn`:

```python
class OrderIn(BaseModel):
    cliente_id: str
    items: list[ItemIn] = Field(default_factory=list)   # <- ItemIn aún no existe

class ItemIn(BaseModel):
    sku: str
    quantity: int = Field(gt=0)
```

Al importar el módulo, Python lanzaba:

```
NameError: name 'ItemIn' is not defined
```

**Por qué pasó.** Las anotaciones de un `BaseModel` de Pydantic v2 **se resuelven en el
momento de crear la clase**, no de forma diferida. La anotación `list[ItemIn]` se
evalúa dentro del cuerpo de la clase `OrderIn`, y en ese momento el nombre `ItemIn`
todavía no existe en el módulo. A diferencia de las anotaciones de una función
(`def f(x: ItemIn)`), que sí se guardan como cadenas en `__annotations__`, las
anotaciones de **atributos de clase** se evalúan de inmediato.

**Cómo lo solucioné.** Declaré `ItemIn` **antes** de `OrderIn`, de modo que la
referencia exista cuando se evalúa la anotación. El orden de las clases dentro del
módulo pasó a ser parte del contrato del archivo:

```python
class ItemIn(BaseModel):
    sku: str
    quantity: int = Field(gt=0)

class OrderIn(BaseModel):
    cliente_id: str
    items: list[ItemIn] = Field(default_factory=list)
```

**Qué aprendí.** «Definir una clase que usa otra» no es un detalle de estilo: en
modelos de Pydantic el **orden de declaración es una dependencia real**. Antes de
esto hubiera imaginado que el `NameError` era un problema de *imports*; la causa
resultó ser el **momento de evaluación** de las anotaciones. También aprendí que
conviene leer el error completo (no solo la última línea): el mensaje apuntaba al
símbolo `ItemIn`, que me llevó directo a la clase mal ordenada.

---

## Error 2 — Una prueba que "demostraba" algo falso

**Qué pasó.** Escribí una prueba para justificar el uso de `Decimal(str(x))` en lugar de
`Decimal(x)` al construir un `Money` desde un `float`:

```python
def test_money_convierte_float_a_decimal_sin_deriva_binaria():
    dinero = Money(600.00)
    assert Decimal(600.00) != Decimal(str(600.00))   # <- FALLÓ
```

La prueba falló con:

```
AssertionError: assert Decimal('600') != Decimal('600.0')
```

**Por qué pasó.** Mi premisa era **incorrecta**. Los `float` no siempre arrastran error
binario: `600.0` es un entero y los enteros se representan **exactamente** en binario
(de ahí `Decimal(600.00) == Decimal('600')`). El error binario aparece en valores con
fracción que no es una potencia de dos: `0.1`, `19.99`, `1.15`. Yo estaba usando, sin
saberlo, el único tipo de valor donde la conversión por texto y la conversión directa
**coinciden**. La prueba era verde en la dirección contraria a la que yo creía
demonstrar: no estaba probando nada.

**Cómo lo solucioné.** Cambié el valor de ejemplo a uno que sí tiene representación
binaria inexacta y dejé explícita la comparación que faltaba:

```python
def test_money_convierte_float_a_decimal_sin_deriva_binaria():
    dinero = Money(19.99)
    assert isinstance(dinero.amount, Decimal)
    assert dinero.amount == Decimal("19.99")
    # Un float no representa 19.99 de forma exacta; la conversión por texto sí.
    assert Decimal(19.99) != Decimal(str(19.99))
    assert dinero.amount == Decimal(str(19.99))
```

**Qué aprendí.** Una prueba que falla no siempre señala un bug **del código**: puede
señalar un error **de la prueba**. Lo importante no fue "arreglarlo para que pasara",
sino **verificar la premisa** contra la realidad (`Decimal(19.99)` frente a
`Decimal("19.99")`) antes de tocar nada. Elegir mal el dato de ejemplo hace que una
prueba "verifique" lo contrario de lo que dice, y eso es peor que no tenerla: da
falsa confianza. En el código de producción la misma disciplina llevó a que
`Money.__post_init__` use `Decimal(str(self.amount))`, que es correcto **para
cualquier** entrada, no solo para las que yo probé.

---

## Error 3 — Constante HTTP deprecada en Starlette

**Qué pasó.** Al traducir las excepciones del dominio a respuestas HTTP usaba la
constante de Starlette:

```python
raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
```

Al ejecutar la suite, `pytest`.Reportó una advertencia en cada prueba 422:

```
StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated.
Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
```

**Por qué pasó.** Starlette renombró recientemente la constante (el código 422 pasó de
«Unprocessable **Entity**» a «Unprocessable **Content**» en el estándar HTTP) y mantuvo
el nombre antiguo como alias que emite advertencia. Depender de ese alias ata el
proyecto a una versión concreta de la biblioteca: cuando el alias desapareciera, el
código dejaría de importar.

**Cómo lo solucioné.** Dejé de depender del nombre del símbolo y usé el código
literal, documentado con una constante propia en el módulo:

```python
#: 422 Unprocessable Content (antes "Unprocessable Entity").
#: Se usa el código literal para no depender de la constante de Starlette,
#: que renombró el símbolo y emite una advertencia de deprecación.
HTTP_422 = 422
```

Las cuatro apariciones de `status.HTTP_422_UNPROCESSABLE_ENTITY` se sustituyeron por
`HTTP_422`. Con eso desapareció la advertencia y el código funciona igual en cualquier
versión de Starlette.

**Qué aprendí.** Un *warning* no es ruido: es información sobre la vida útil de una
API. Lo correcto era **eliminar la causa** (la dependencia del alias), no silenciarla
con un filtro de pytest. Y que el código HTTP 422 es un **contrato de la interfaz
HTTP**, no un detalle de la biblioteca: escribirlo explícitamente documenta la
intención mejor que heredar un alias con nombre histórico.

---

## Dos errores adicionales (menores, pero igual de instructivos)

### 4. El orden de validación de FastAPI

Mi prueba `test_pedido_inexistente_responde_404` enviaba `POST /orders/NOEXISTE/items`
**sin cuerpo** y esperaba 404; la API devolvió **422**. La causa no era un bug del
controlador: FastAPI **valida el cuerpo de la petición antes de invocar al
controlador**, así que una petición con cuerpo inválido nunca llega al `404`. La
solución fue enviar un cuerpo válido en el test para poder alcanzar el camino del
404. Aprendí que, en una API, **el orden de las validaciones es parte del
comportamiento observable** y que «no existe el recurso» y «el cuerpo es inválido» son
dos hechos que compiten por el mismo código de respuesta.

### 5. Una aserción que no cuadraba con el CSV

Al escribir las pruebas de la máquina de estados escribí una expectativa sobre los
renglones de **O013** que no coincidía con los datos: O013 tiene **un solo renglón**
(`O013,SKU001,1`), es decir, 1 unidad por 600.00 MXN. El error estaba en mi
expectativa, no en el modelo. Lo corregí **cambiando la aserción**, nunca el CSV:
la regla didáctica del paquete dice explícitamente que no se deben alterar los datos
para que un caso pase. Aprendí que, cuando una prueba discrepa de los datos de
entrada, lo primero es **verificar contra la fuente de verdad** (`datos/*.csv`) y
preguntarse cuál de los dos está equivocado.

---

## Conclusiones

1. **El error de la clase mal ordenada y el del test con `600.00` eran el mismo tipo
   de error**: una suposición mía que nunca verifiqué. Verificar la premisa *antes*
   de escribir la corrección es más rápido que depurar la consecuencia.
2. **Los datos del paquete son la especificación ejecutable.** El enunciado es
   explícito: los CSV no se tocan. Toda la adaptación (por ejemplo, el caso de
   prioridad del 10 % sobre el 5 %, que ningún pedido del paquete cumple) se resolvió
   **construyendo el caso en memoria**, sin alterar los archivos de datos.
3. **Validar antes de mutar** (en el dominio, en el cuerpo de la petición y en las
   pruebas) es el mismo principio a tres escalas: una transición inválida no cambia
   el estado ni añade eventos; un controlador devuelve 404/409/422 sin tocar el
   pedido; una prueba que falla no modifica los datos.
4. **Las pruebas son el contrato.** Los 116 casos pasan, pero lo que más valor dio fue
   el proceso inverso: cada fallo reveló una suposición mía que estaba mal
   — sobre el orden de las clases, sobre la aritmética binaria y sobre el orden de
   las validaciones HTTP.
