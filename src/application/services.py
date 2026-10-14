class CheckInService:
    def __init__(self, reservaciones, habitaciones, estancias, uow):
        self.reservaciones, self.habitaciones, self.estancias, self.uow = reservaciones, habitaciones, estancias, uow
    def ejecutar(self, reservacion_id: str, identidad_validada: bool):
        if not identidad_validada: raise ValueError("Identidad no validada")
        reservacion = self.reservaciones.obtener(reservacion_id)
        if reservacion is None: raise ValueError("Reservación no encontrada")
        habitacion = self.habitaciones.obtener(reservacion.habitacion_id)
        if habitacion is None: raise ValueError("Habitación no encontrada")
        reservacion.validar_checkin(); habitacion.ocupar()
        try:
            self.reservaciones.guardar(reservacion); self.habitaciones.guardar(habitacion)
            self.uow.confirmar()
        except Exception:
            self.uow.revertir(); raise
        return {"resultado": "check-in registrado", "habitacion": habitacion.numero}
