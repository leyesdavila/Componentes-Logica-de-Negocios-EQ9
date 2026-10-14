# Architecture Decision Records — Hotel Costa Azul

## ADR-01: Domain Model como patrón principal
- **Estado:** Propuesto; requiere aceptación del equipo.
- **Contexto:** Reglas relacionadas entre reservación, habitación, garantía, estancia y cuenta; evidencia US-08, US-12, US-13, US-15 y N1–N6.
- **Alternativas:** Transaction Script (simple, riesgo de duplicación); Table Module (organiza por tabla); Domain Model (reglas e invariantes cerca del dominio, mayor costo de diseño inicial).
- **Decisión:** Domain Model para reglas centrales; Service Layer coordina.
- **Consecuencias:** Facilita coherencia y pruebas, exige definir límites e invariantes.
- **Trazabilidad:** N1, N2, N3, N4, N6; US-08, US-12, US-13, US-15.

## ADR-02: Estado explícito de habitación
- **Estado:** Propuesto; requiere aceptación del equipo.
- **Contexto:** US-15 y US-16 separan check-out de habitación disponible; limpieza toma 30–45 min.
- **Alternativas:** libre/ocupada; estados explícitos.
- **Decisión:** disponible, ocupada, sucia/pendiente, en limpieza y fuera de servicio. Solo Limpieza confirma disponible tras completar.
- **Consecuencias:** Reduce asignaciones incorrectas; exige actualizar estado en tiempo real.
- **Trazabilidad:** N1, N2, N8; US-08, US-09, US-10, US-15, US-16.

## ADR-03: Unit of Work para operaciones coordinadas
- **Estado:** Propuesto; requiere aceptación del equipo.
- **Contexto:** Check-in, check-out y cambio de habitación modifican objetos relacionados.
- **Alternativas:** guardar individualmente; transacción coordinada; compensación manual.
- **Decisión:** definir un límite transaccional por caso de uso y revertir ante error.
- **Consecuencias:** Consistencia mejorada; la implementación concreta depende de persistencia.
- **Trazabilidad:** N2, N3, N4; US-08, US-13, US-15, US-18.
