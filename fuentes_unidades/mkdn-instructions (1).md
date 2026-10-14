# Tarea 3

**Observaciones generales:**
 - Empezar a estructurar el diseño del sistema
 - Ya se definió que necesita el negocio
 - No debe haber dependencias
 - Tampoco interfaces demasiado grandes que obliguen a modificar continuamente el codigo.
 - Concentrar la informaci'on en Gitbub
 - Tomar el analisis de la actividad 2 para esta actividad

## Elegir patrones

Para el caso de U2, justifica con tabla comparativa que patron de logica de negocio usaras (Transaction Script, Domain Model, etc.) y por que.

 - Que Users Stories se van a elegir
 - Justificar las tablas comparativas
 - Patron de logica de negocio (Transaction Model, etc) y por que.
 - Elegir el patron que mejor convenga al negocio.
 - Que necesita el negocio
 - Como organizar esas necesidades
 - Organizar entre 5 y 7 casos de uso
 - Seleccionar cinco casos en donde se requieren operaciones normales, donde se tenga una operacion, pueda rechazarse y tomar un camino distinto.
 - Buscar los patrones (Transacion, Domain Model, entre otros), decidir en base a las User Stories
 - Justificar con evidencia porque se seleccionan determinados patrones

## Mapa de dominio

Identifica todos los Aggregates, Entidades, Value Objects y Domain Events. Crea diagrama con relaciones y explica el lenguaje ubicuo.

 - Explicar que representa cada elemento dentro del negocio.
 - Que reglas debe de proteger ese mapa de dominio

## Service layer

Diseña los Application Services: un metodo por caso de usoo. Define que orquesta cada servicio (sin logica, solo coordinacion).

 - Ubicar cada metodo, esos metodos deben de representar cada caso de uso.
 - Va a coordinar el trabajo sin contener todas las reglas
 - Definir los repositorios que necesita el dominio
 - Que operaciones deben realizarse juntas usando the unit of work
 - Sin usar tecnicismo, sino lenguaje de negocio
 - Incluir SQRS basico, separar operaciones que modofiquen la informaciom
 - Llamadas, commands, querys
 - No es necesario hacer bases datos, solo diferenciar las responsabilidades
 - Que este de acuerdo con los principios del SOLID, ir al minimalismo y evitar que una funcion tenga muchas responsabilidades
 - No deben haber reglas demasiado grandes

## Diagramas UML

 - Donde tenga el diagrama de dominio, 2 diagramas de secuencia, al menos tres registros de los ADR.
 - Matriz de trazabilidad actualizada
 - Estructura inicial de carpetas y codigos

## Otros detalles

### Bitcora de la conversacion con la IA

 - Solicitudes echas a la IA, que les respondio
 - Que preguntaron, los prompst
 - Errores o supuestos
 - Decision del equipo


### Github

 - Subir en Github todos los entregables

### NETACAD

 - Resumen de lo que hicieron
 - Usar el reporte fime
 - Screenshots de la salia
 - Incluir la bitacora
 - Incluir link de github
 - Como comprobaron el diseño

### Teams

Documento subido en Microsoft Teams