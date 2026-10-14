# Matriz de trazabilidad — Hotel Costa Azul

| Necesidad | Historias/casos | Componentes | Prueba sugerida |
|---|---|---|---|
| N1 estado de habitación | US-08, US-09, US-15, US-16 | Habitacion, CheckInService, limpieza | Rechazar habitación sucia; disponible solo tras limpieza |
| N2 disponibilidad consistente | US-01, US-02, US-03 | HabitacionRepository, pre-reserva | Excluir sucia/en limpieza/fuera de servicio; expirar a 24 h |
| N3 trazabilidad | US-13, US-18 | CambiarHabitacionService, HistorialCambioRepository | Validar fecha, anterior, nueva y responsable |
| N4 cargos centralizados | US-11, US-15 | CuentaHuesped, Consumo | Total coincide con cargos |
| N5 cancelación/no-show | US-05, US-06, US-07 | Política de reservación | Validar 48 h, excepción y cargo primera noche |
| N6 tope crédito | US-12 | CuentaHuesped, autorización | Superar $3,000 exige pago parcial o autorización |
| N7 reportes | US-17 | Query y ReporteOcupacionDTO | Desglose por estado y porcentaje |
| N8 excepciones | US-09, US-10, US-13, US-14 | Application Services | Validar habitación fuera de servicio, early check-in y extensión |

## Hallazgos por validar
- Contradicción aparente entre US-06 y respuesta de entrevista sobre cancelación fuera de 48 h.
- Precisar si el tope se activa al alcanzar o superar $3,000 MXN.
- Precisar regla de salida anticipada y su trazabilidad a una historia aprobada.
