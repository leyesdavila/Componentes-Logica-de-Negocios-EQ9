"""Modelo de dominio inicial; reglas derivadas del caso U2 y pendientes de validación."""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime

class EstadoHabitacion(str, Enum):
    DISPONIBLE = "disponible"
    OCUPADA = "ocupada"
    SUCIA = "sucia / pendiente de limpieza"
    EN_LIMPIEZA = "en limpieza"
    FUERA_SERVICIO = "fuera de servicio"

class EstadoReservacion(str, Enum):
    PENDIENTE_GARANTIA = "pendiente de garantía"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    NO_SHOW = "no-show"

@dataclass(frozen=True)
class Dinero:
    cantidad: Decimal
    moneda: str = "MXN"
    def __post_init__(self):
        if self.cantidad < 0: raise ValueError("El monto no puede ser negativo")

@dataclass(frozen=True)
class RangoFechas:
    entrada: datetime
    salida: datetime
    def __post_init__(self):
        if self.salida <= self.entrada: raise ValueError("La salida debe ser posterior a la entrada")

@dataclass
class Habitacion:
    id: str
    numero: int
    estado: EstadoHabitacion
    def validar_para_checkin(self):
        if self.estado != EstadoHabitacion.DISPONIBLE:
            raise ValueError("La habitación no está disponible; verifique limpieza y estado operativo")
    def ocupar(self):
        self.validar_para_checkin(); self.estado = EstadoHabitacion.OCUPADA
    def enviar_a_limpieza(self):
        if self.estado != EstadoHabitacion.OCUPADA: raise ValueError("Solo una habitación ocupada puede liberarse mediante check-out")
        self.estado = EstadoHabitacion.SUCIA
    def marcar_disponible(self):
        if self.estado not in (EstadoHabitacion.SUCIA, EstadoHabitacion.EN_LIMPIEZA): raise ValueError("La habitación debe estar en limpieza para marcarse disponible")
        self.estado = EstadoHabitacion.DISPONIBLE

@dataclass
class Reservacion:
    id: str
    estado: EstadoReservacion
    habitacion_id: str
    garantia_valida: bool = False
    def validar_checkin(self):
        if self.estado != EstadoReservacion.CONFIRMADA or not self.garantia_valida:
            raise ValueError("La reservación debe estar confirmada y contar con garantía válida")
