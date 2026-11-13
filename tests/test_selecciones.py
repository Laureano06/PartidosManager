import os
import unittest
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from seed import preseleccion_inicial


class SeleccionesTests(unittest.TestCase):
    def test_preseleccion_prioriza_cobertura_y_nivel(self):
        jugadores = []
        for posicion, cantidad in (("POR", 5), ("DEF", 12), ("MED", 12), ("DEL", 7)):
            for indice in range(cantidad):
                jugadores.append(SimpleNamespace(id_jugador=len(jugadores), posicion=posicion,
                                 overall=90 - indice, edad=25, potencial=85))
        lista = preseleccion_inicial(jugadores)
        self.assertEqual(len(lista), 23)
        self.assertEqual(sum(j.posicion == "POR" for j in lista), 3)
        self.assertGreaterEqual(sum(j.posicion == "DEF" for j in lista), 4)
        self.assertGreaterEqual(sum(j.posicion == "MED" for j in lista), 4)
        self.assertGreaterEqual(sum(j.posicion == "DEL" for j in lista), 3)

