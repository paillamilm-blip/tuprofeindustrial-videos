import unittest
from tpi_videos.visuales import analizar_triangulo_rectangulo
from tpi_videos.guion import Guion

class TrianguloRectanguloTest(unittest.TestCase):
    def test_pitagoras_cateto_faltante(self):
        fig = analizar_triangulo_rectangulo(cateto_a="6", hipotenusa="10", cateto_b="b = ¿?")
        self.assertEqual(fig.cateto_a, 6.0)
        self.assertEqual(fig.hipotenusa, 10.0)
        self.assertEqual(fig.cateto_b, 8.0)
        self.assertEqual(fig.rotulo_a, "6")
        self.assertEqual(fig.rotulo_b, "b = ¿?")
        self.assertEqual(fig.rotulo_c, "10")

    def test_pitagoras_hipotenusa_faltante(self):
        fig = analizar_triangulo_rectangulo(cateto_a="3 m", cateto_b="4 m")
        self.assertEqual(fig.cateto_a, 3.0)
        self.assertEqual(fig.cateto_b, 4.0)
        self.assertEqual(fig.hipotenusa, 5.0)
        self.assertEqual(fig.unidad, "m")

    def test_hipotenusa_menor_que_cateto_falla(self):
        with self.assertRaises(ValueError):
            analizar_triangulo_rectangulo(cateto_a="10", hipotenusa="6")

if __name__ == "__main__":
    unittest.main()
