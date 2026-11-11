import unittest

from tpi_videos import componentes as c
from tpi_videos.temas import Tema


class PanelPersistenteTest(unittest.TestCase):
    def setUp(self):
        self.token = c.usar_estilo(Tema(nombre="prueba"))

    def tearDown(self):
        c.restablecer_estilo(self.token)

    def _panel(self, cerrados):
        return c.panel_persistente(4, cerrados, ["#FFC72C"], 6.0, "#141A24", "#2A3444")

    def test_vacio_muestra_paso_1_de_n(self):
        panel = self._panel([])
        self.assertIn("paso 1 de 4", panel[1][0].original_text)

    def test_acumula_sin_resetear(self):
        uno = self._panel(["a"])
        dos = self._panel(["a", "b"])
        self.assertIn("paso 3 de 4", dos[1][0].original_text)
        self.assertGreaterEqual(len(dos[1][2]), len(uno[1][2]))

    def test_mini_formulas_tope_tres(self):
        panel = self._panel(["a", "b", "c", "d"])
        self.assertEqual(len(panel[1][2]), 3)

    def test_paso_hablado_avanza_sin_agregar_formula(self):
        panel = c.panel_persistente(4, ["a"], ["#FFC72C"], 6.0, "#141A24", "#2A3444", completados=2)
        self.assertIn("paso 3 de 4", panel[1][0].original_text)
        self.assertEqual(len(panel[1][2]), 1)
        self.assertAlmostEqual(panel[1][1][1].width / panel[1][1][0].width, 0.5)

    def test_ultimo_paso_conserva_su_color_al_completarse(self):
        panel = c.panel_persistente(
            3, ["a", "b", "c"], ["#FFC72C", "#38BDF8", "#A78BFA", "#22C55E"],
            6.0, "#141A24", "#2A3444",
        )
        self.assertEqual(panel[1][0].get_color().to_hex(), "#A78BFA")
        self.assertEqual(panel[1][1][1].get_fill_color().to_hex(), "#A78BFA")

    def test_barra_crece_con_pasos(self):
        vacio = self._panel([])
        lleno = self._panel(["a", "b"])
        self.assertGreater(lleno[1][1][1].width, vacio[1][1][1].width)


if __name__ == "__main__":
    unittest.main()