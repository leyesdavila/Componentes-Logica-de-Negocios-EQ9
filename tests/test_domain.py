import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from src.domain.model import Habitacion, EstadoHabitacion, Reservacion, EstadoReservacion, Dinero, RangoFechas

class TestDomain(unittest.TestCase):
    def test_habitacion_no_disponible_rechaza_checkin(self):
        h = Habitacion("H-101", 101, EstadoHabitacion.SUCIA)
        with self.assertRaises(ValueError): h.ocupar()
    def test_habitacion_disponible_pasa_a_ocupada(self):
        h = Habitacion("H-102", 102, EstadoHabitacion.DISPONIBLE); h.ocupar()
        self.assertEqual(h.estado, EstadoHabitacion.OCUPADA)
    def test_reservacion_sin_garantia_rechaza_checkin(self):
        r = Reservacion("R-1", EstadoReservacion.PENDIENTE_GARANTIA, "H-101", False)
        with self.assertRaises(ValueError): r.validar_checkin()
    def test_dinero_no_admite_negativos(self):
        with self.assertRaises(ValueError): Dinero(Decimal("-1"))
    def test_rango_fechas_valido(self):
        now = datetime(2026,1,1); RangoFechas(now, now + timedelta(days=1))

if __name__ == "__main__": unittest.main()
