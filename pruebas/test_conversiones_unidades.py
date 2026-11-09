"""La escalera métrica completa: km también es longitud y mg también es masa.

Antes «1 km» se trataba como 1 m y «500 mg» como 500 kg: la física salía mal por un factor
de mil o un millón sin que nada avisara. Acá se fija la conversión correcta en las dos direcciones.
"""

import unittest

from tpi_videos.visuales import _a_kilos, _a_metros, _desde_metros


class AMetrosTest(unittest.TestCase):
    def test_un_kilometro_son_mil_metros(self):
        self.assertEqual(_a_metros(1, "km"), 1000.0)

    def test_las_unidades_de_siempre_no_cambian(self):
        self.assertEqual(_a_metros(1, "m"), 1.0)
        self.assertEqual(_a_metros(1, "cm"), 0.01)
        self.assertEqual(_a_metros(1, "mm"), 0.001)


class AKilosTest(unittest.TestCase):
    def test_quinientos_miligramos_son_medio_gramo_en_kilos(self):
        self.assertAlmostEqual(_a_kilos(500, "mg"), 0.0005)

    def test_gramos_y_kilos_no_cambian(self):
        self.assertEqual(_a_kilos(500, "g"), 0.5)
        self.assertEqual(_a_kilos(2, "kg"), 2.0)


class DesdeMetrosTest(unittest.TestCase):
    def test_la_vuelta_al_kilometro_es_consistente(self):
        # _desde_metros dice cuántas unidades del guion hay en un metro: en km, 0,001.
        self.assertEqual(_desde_metros("km"), 0.001)
        self.assertEqual(_a_metros(1, "km") * _desde_metros("km"), 1.0)

    def test_las_unidades_de_siempre_no_cambian(self):
        self.assertEqual(_desde_metros("m"), 1.0)
        self.assertEqual(_desde_metros("cm"), 100.0)
        self.assertEqual(_desde_metros("mm"), 1000.0)


if __name__ == "__main__":
    unittest.main()
