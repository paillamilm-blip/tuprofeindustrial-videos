import unittest

from tpi_videos import componentes as c
from tpi_videos.temas import Tema


class TabsPasosTest(unittest.TestCase):
    def setUp(self):
        self.token = c.usar_estilo(Tema(nombre="prueba"))

    def tearDown(self):
        c.restablecer_estilo(self.token)

    def test_un_tab_por_paso(self):
        tabs = c.tabs_de_pasos(4, 1, ["#FFC72C", "#38BDF8"])
        self.assertEqual(len(tabs), 4)

    def test_activo_brilla_mas_que_el_resto(self):
        tabs = c.tabs_de_pasos(3, 2, ["#FFC72C"])
        self.assertGreater(tabs[1][0].get_fill_opacity(), tabs[0][0].get_fill_opacity())
        self.assertGreater(tabs[1][0].get_fill_opacity(), tabs[2][0].get_fill_opacity())

    def test_activar_tab_cambia_el_brillo(self):
        tabs = c.tabs_de_pasos(3, 1, ["#FFC72C"])
        c.activar_tab(tabs, 3)
        self.assertGreater(tabs[2][0].get_fill_opacity(), tabs[0][0].get_fill_opacity())

    def test_paleta_cicla(self):
        tabs = c.tabs_de_pasos(5, 1, ["#FF0000", "#00FF00"])
        self.assertEqual(len(tabs), 5)  # no revienta con mas pasos que colores


if __name__ == "__main__":
    unittest.main()