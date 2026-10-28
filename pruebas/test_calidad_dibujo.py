"""Calidad de dibujo: trazo de marcador (no de lápiz fino) y tarjetas con sombra."""

import unittest

try:
    from manim import Circle, Line, VGroup

    from tpi_videos import componentes as c
    from tpi_videos import dibujos as d
except ModuleNotFoundError:  # pragma: no cover - sin manim instalado
    c = None


@unittest.skipUnless(c is not None, "manim no está instalado")
class TrazoTest(unittest.TestCase):
    def test_una_linea_fina_sube_al_grosor_minimo_de_marcador(self):
        fino = Line([0, 0, 0], [1, 0, 0]).set_stroke(width=1.5)
        d.afinar_trazo(VGroup(fino))
        self.assertEqual(fino.get_stroke_width(), d.GROSOR_MINIMO)

    def test_una_linea_gruesa_se_queda_como_esta(self):
        gruesa = Line([0, 0, 0], [1, 0, 0]).set_stroke(width=9)
        d.afinar_trazo(VGroup(gruesa))
        self.assertEqual(gruesa.get_stroke_width(), 9)

    def test_los_rellenos_sin_borde_no_ganan_borde(self):
        """Un engranaje relleno se dibuja sin borde: el grosor mínimo no le mete una línea."""
        relleno = Circle().set_fill("#FF0000", 1).set_stroke(width=0)
        d.afinar_trazo(VGroup(relleno))
        self.assertEqual(relleno.get_stroke_width(), 0)

    def test_entra_hasta_las_piezas_anidadas(self):
        dentro = Line([0, 0, 0], [1, 0, 0]).set_stroke(width=2)
        grupo = VGroup(VGroup(dentro))
        d.afinar_trazo(grupo)
        self.assertEqual(dentro.get_stroke_width(), d.GROSOR_MINIMO)


@unittest.skipUnless(c is not None, "manim no está instalado")
class TarjetaTest(unittest.TestCase):
    def test_la_tarjeta_lleva_su_sombra_detras_del_panel(self):
        tarjeta = c.tarjeta(VGroup(Circle()), 7.0, "#FFFFFF", "#DDDDDD")
        panel = tarjeta[0]
        self.assertIsInstance(panel, VGroup)
        self.assertEqual(len(panel), 2)  # sombra + caja
        self.assertGreater(panel[0].get_fill_opacity(), 0.0)

    def test_sobre_panel_oscuro_la_sombra_no_se_ve(self):
        tarjeta = c.tarjeta(VGroup(Circle()), 7.0, "#101820", "#334455")
        self.assertEqual(tarjeta[0][0].get_fill_opacity(), 0.0)

    def test_el_contenido_sigue_siendo_el_ultimo_hijo(self):
        contenido = VGroup(Circle())
        tarjeta = c.tarjeta(contenido, 7.0, "#FFFFFF", "#DDDDDD")
        self.assertIs(tarjeta[-1], contenido)
