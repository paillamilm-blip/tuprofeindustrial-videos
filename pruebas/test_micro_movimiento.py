import unittest

from manim import Animation, Rectangle

from tpi_videos import componentes as c
from tpi_videos.temas import Tema


class MicroMovimientoTest(unittest.TestCase):
    def test_tipos_devuelven_animacion(self):
        obj = Rectangle()
        for tipo in ("cursor", "tick", "barra", "contador"):
            self.assertIsInstance(c.micro_movimiento(tipo, obj), Animation)

    def test_tick_dibuja_un_visto(self):
        anim = c.micro_movimiento("tick", Rectangle())
        self.assertIsNotNone(anim.mobject)

    def test_tick_cabe_en_su_tab_sin_tapar_el_numero(self):
        for escala in (1.0, 0.4):
            tab = c.tabs_de_pasos(3, 1, ["#FFC72C"])[0].scale(escala)
            marca = c.micro_movimiento("tick", tab).mobject
            self.assertLessEqual(marca.width, tab.width * 0.25)
            self.assertLessEqual(marca.height, tab.height * 0.25)
            self.assertGreaterEqual(marca.get_left()[0], tab[1].get_right()[0])
            self.assertLessEqual(marca.get_right()[0], tab[0].get_right()[0])
            self.assertLessEqual(marca.get_top()[1], tab[0].get_top()[1])
            self.assertGreaterEqual(marca.get_bottom()[1], tab[0].get_bottom()[1])

    def test_gramatica_activa_apagada_por_defecto(self):
        self.assertFalse(c.gramatica_activa(Tema(nombre="prueba")))

    def test_gramatica_activa_con_un_flag(self):
        t = Tema(nombre="prueba", gramatica={"tabs": True})
        self.assertTrue(c.gramatica_activa(t))


if __name__ == "__main__":
    unittest.main()