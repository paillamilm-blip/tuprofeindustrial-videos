import math
import unittest

from tpi_videos.visuales import analizar_poligono


class PoligonoRegularTest(unittest.TestCase):
    """La matemática de la figura, sin Manim: el dibujo solamente tiene que obedecerla."""

    def test_pentagono_de_lado_12_da_apotema_8_26_y_radio_10_21(self):
        figura = analizar_poligono(5, "12 cm")
        self.assertAlmostEqual(figura.apotema, 8.26, places=2)
        self.assertAlmostEqual(figura.radio, 10.21, places=2)

    def test_cuadrado_apotema_y_radio_coinciden_con_lo_aprendido_a_mano(self):
        figura = analizar_poligono(4, "10 cm")
        self.assertAlmostEqual(figura.apotema, 5.0, places=6)  # la mitad del lado
        self.assertAlmostEqual(figura.radio, 5 * math.sqrt(2), places=6)  # media diagonal

    def test_triangulo_equilatero_apotema_y_radio(self):
        figura = analizar_poligono(3, "1 m")
        self.assertAlmostEqual(figura.apotema, math.sqrt(3) / 6, places=6)
        self.assertAlmostEqual(figura.radio, math.sqrt(3) / 3, places=6)

    def test_angulos_interior_y_central_del_pentagono(self):
        figura = analizar_poligono(5, "12 cm")
        self.assertAlmostEqual(figura.angulo_interior, 108.0, places=6)
        self.assertAlmostEqual(figura.angulo_central, 72.0, places=6)

    def test_angulos_interior_y_central_del_hexagono(self):
        figura = analizar_poligono(6, "4 cm")
        self.assertAlmostEqual(figura.angulo_interior, 120.0, places=6)
        self.assertAlmostEqual(figura.angulo_central, 60.0, places=6)

    def test_los_vertices_estan_todos_a_un_radio_del_centro(self):
        figura = analizar_poligono(5, "12 cm")
        self.assertEqual(len(figura.vertices), 5)
        for x, y in figura.vertices:
            self.assertAlmostEqual(math.hypot(x, y), figura.radio, places=6)

    def test_el_lado_entre_vertices_pesa_lo_que_dice_el_guion(self):
        figura = analizar_poligono(7, "3,5 cm")
        pares = list(zip(figura.vertices, figura.vertices[1:] + figura.vertices[:1], strict=False))
        for (x0, y0), (x1, y1) in pares:
            self.assertAlmostEqual(math.hypot(x1 - x0, y1 - y0), figura.lado, places=6)

    def test_la_base_queda_horizontal_para_que_el_cuadrado_no_apoye_en_una_punta(self):
        for lados in (3, 4, 5, 6, 7, 8):
            with self.subTest(lados=lados):
                mas_bajos = sorted(analizar_poligono(lados, "12 cm").vertices, key=lambda v: v[1])[:2]
                self.assertAlmostEqual(mas_bajos[0][1], mas_bajos[1][1], places=9)

    def test_la_medida_trae_numero_y_se_guarda_su_unidad(self):
        figura = analizar_poligono(5, "1,5 m")
        self.assertAlmostEqual(figura.lado, 1.5, places=9)
        self.assertEqual(figura.unidad, "m")

    def test_sin_numero_en_la_medida_lo_dice_en_espanol(self):
        with self.assertRaises(ValueError) as error:
            analizar_poligono(5, "el lado")
        self.assertIn("número", str(error.exception))

    def test_un_poligono_de_dos_lados_no_existe(self):
        with self.assertRaises(ValueError):
            analizar_poligono(2, "12 cm")


if __name__ == "__main__":
    unittest.main()
