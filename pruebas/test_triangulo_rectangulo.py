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

    def test_partes_del_dibujo(self):
        from tpi_videos.config import cargar_marca
        from tpi_videos.temas import cargar_tema
        from tpi_videos.dibujos import triangulo_rectangulo

        marca = cargar_marca()
        tema = cargar_tema("pizarra_acrilica", marca)
        fig = analizar_triangulo_rectangulo(cateto_a="a = 6 m", hipotenusa="c = 10 m", cateto_b="b = ¿?")
        dibujo = triangulo_rectangulo(fig, ["angulo_recto"], tema.colores, 5.0, 5.0)

        self.assertIn("hipotenusa", dibujo.partes)
        self.assertIn("c", dibujo.partes)
        self.assertIn("cateto a", dibujo.partes)
        self.assertIn("cateto b", dibujo.partes)
        self.assertIn("angulo_recto", dibujo.partes)
        self.assertIn("diez", dibujo.partes)
        self.assertIn("seis", dibujo.partes)
        self.assertIn("incognita", dibujo.partes)

if __name__ == "__main__":
    unittest.main()
