import unittest

from tpi_videos import componentes as c
from tpi_videos.entorno import latex_disponible
from tpi_videos.guion import MapaColor
from tpi_videos.temas import Tema

LATEX = all(latex_disponible())  # macOS/Windows en CI no traen TeX: lo que dibuja fórmulas se salta


@unittest.skipUnless(LATEX, "LaTeX no está instalado")
class MapaColorTest(unittest.TestCase):
    def setUp(self):
        self.token = c.usar_estilo(Tema(nombre="prueba"))

    def tearDown(self):
        c.restablecer_estilo(self.token)

    def test_una_flecha_por_termino_presente(self):
        eq = c.ecuacion("x = 150 + 780 t")
        mapa = [MapaColor(termino="780", concepto="velocidad")]
        grupo = c.mapa_de_color(eq, mapa, ["#38BDF8"])
        self.assertEqual(len(grupo), 1)

    def test_termino_ausente_se_omite(self):
        eq = c.ecuacion("x = 150")
        mapa = [MapaColor(termino="999", concepto="nada")]
        self.assertEqual(len(c.mapa_de_color(eq, mapa, ["#38BDF8"])), 0)

    def test_formula_compacta_colorea_solo_los_terminos_mapeados(self):
        eq = c.ecuacion("x=150+780t", aislar=["150", "780"])
        mapa = [MapaColor(termino="150", concepto="posición inicial", color="#FF0000"),
                MapaColor(termino="780", concepto="velocidad", color="#38BDF8")]
        c.mapa_de_color(eq, mapa, ["#FFC72C"])
        self.assertEqual(eq.get_part_by_tex("150").get_color().to_hex(), "#FF0000")
        self.assertEqual(eq.get_part_by_tex("780").get_color().to_hex(), "#38BDF8")
        self.assertLess(eq.get_part_by_tex("150").width, eq.width)
        colores = {m.get_color().to_hex() for m in eq.family_members_with_points()}
        self.assertIn("#FFFFFF", colores)

    def test_etiquetas_de_formula_compacta_no_se_superponen(self):
        eq = c.ecuacion("x=150+780t", aislar=["150", "780"])
        mapa = [MapaColor(termino="150", concepto="posición inicial"),
                MapaColor(termino="780", concepto="velocidad")]
        grupo = c.mapa_de_color(eq, mapa, ["#FFC72C", "#38BDF8"])
        self.assertLess(grupo[0][0].get_right()[0], grupo[1][0].get_left()[0])
        self.assertLess(grupo[0][1].get_end()[0], grupo[1][1].get_end()[0])
        self.assertLessEqual(grupo.width, 7.6)

    def test_termino_dentro_de_fraccion_conserva_la_formula(self):
        eq = c.ecuacion(r"v=\frac{d}{t}", aislar=["d", "t"])
        mapa = [MapaColor(termino="d", concepto="distancia"),
                MapaColor(termino="t", concepto="tiempo")]
        self.assertEqual(len(c.mapa_de_color(eq, mapa, ["#FFC72C", "#38BDF8"])), 2)
        self.assertLess(eq.get_part_by_tex("d").height, eq.height)

    def test_variable_no_divide_el_comando_de_unidades(self):
        eq = c.ecuacion(r"x=780t\ \text{m}", aislar=["t"])
        mapa = [MapaColor(termino="t", concepto="tiempo", color="#38BDF8")]
        self.assertEqual(len(c.mapa_de_color(eq, mapa, ["#FFC72C"])), 1)
        self.assertEqual(eq.get_part_by_tex("t").get_color().to_hex(), "#38BDF8")

    def test_mapa_tolera_espacios_de_latex_en_el_termino(self):
        eq = c.ecuacion(r"x = 780\,t", aislar=["780t"])
        mapa = [MapaColor(termino="780t", concepto="desplazamiento", color="#38BDF8")]
        grupo = c.mapa_de_color(eq, mapa, ["#FFC72C"])
        self.assertEqual(len(grupo), 1)
        objetivo = c.partes_por_tex(eq, "780t")
        self.assertEqual(len(objetivo), 1)
        self.assertEqual(objetivo[0].get_color().to_hex(), "#38BDF8")

    def test_exponente_sin_llaves_puede_aislarse(self):
        eq = c.ecuacion("t^2", aislar=["2"])
        self.assertIsNotNone(eq.get_part_by_tex("2"))

    def test_argumento_sin_llaves_de_vector_puede_aislarse(self):
        eq = c.ecuacion(r"\vec F", aislar=["F"])
        self.assertIsNotNone(eq.get_part_by_tex("F"))

    def test_argumentos_anidados_conservan_su_notacion(self):
        for tex, termino in [(r"t^\alpha", r"\alpha"),
                             (r"\frac a b", "a"),
                             (r"t^\sqrt[3]{x}", "x")]:
            with self.subTest(tex=tex):
                self.assertIsNotNone(c.ecuacion(tex, aislar=[termino]).get_part_by_tex(termino))

    def test_flechas_siguen_el_orden_visual_no_el_del_mapa(self):
        eq = c.ecuacion("x=150+780t", aislar=["150", "780"])
        mapa = [MapaColor(termino="780", concepto="velocidad"),
                MapaColor(termino="150", concepto="posición inicial")]
        grupo = c.mapa_de_color(eq, mapa, ["#38BDF8", "#FFC72C"])
        self.assertLess(grupo[0][1].get_end()[0], grupo[1][1].get_end()[0])
        self.assertEqual(grupo[0][0][0].get_stroke_color().to_hex(), "#FFC72C")

    def test_mapa_conserva_el_resaltado_del_exponente_original(self):
        eq = c.ecuacion("V=4^3=64", aislar=["4^3"])
        self.assertEqual(len(c.partes_por_tex(eq, "4^3")), 1)

    def test_color_propio_manda(self):
        eq = c.ecuacion("x = 150 + 780 t")
        mapa = [MapaColor(termino="780", concepto="velocidad", color="#FF0000")]
        grupo = c.mapa_de_color(eq, mapa, ["#38BDF8"])
        self.assertEqual(len(grupo), 1)


if __name__ == "__main__":
    unittest.main()