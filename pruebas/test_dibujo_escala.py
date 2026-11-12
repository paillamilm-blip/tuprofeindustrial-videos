"""El dibujo que demuestra: al agrandar el lado, las piezas del original entran de a una y se cuentan."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_escala

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from tpi_videos.dibujos import escala


class AnalisisTest(unittest.TestCase):
    def test_duplicar_el_lado_son_8_cubos_o_4_cuadrados(self):
        self.assertEqual(analizar_escala("4 cm", 2, 3).piezas, 8)
        self.assertEqual(analizar_escala("4 cm", 2, 2).piezas, 4)
        self.assertEqual(analizar_escala("4 cm", 3, 3).piezas, 27)
        e = analizar_escala("4 cm", 2, 3)
        self.assertEqual((e.lado_grande, e.unidad), (8.0, "cm"))

    def test_fuera_de_rango_se_explica_en_espanol(self):
        for factor, dimension in ((4, 3), (2, 1), (1.5, 3)):
            with self.assertRaisesRegex(ValueError, "escala"):
                analizar_escala("4 cm", factor, dimension)

    def test_el_guion_lo_valida_y_pide_el_lado(self):
        Visual.model_validate({"tipo": "escala", "lado": "4 cm", "factor": 2, "dimension": 3})
        with self.assertRaisesRegex(ValidationError, "lado original"):
            Visual.model_validate({"tipo": "escala", "factor": 2, "dimension": 3})
        with self.assertRaisesRegex(ValidationError, "marca de la escala"):
            Visual.model_validate({"tipo": "escala", "lado": "4 cm", "anotar": ["volumen"]})


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoTest(unittest.TestCase):
    def _dibujo(self, dimension=3, factor=2, marcas=("contador", "razon")):
        figura = analizar_escala("4 cm", factor, dimension)
        return escala(figura, list(marcas), ColoresTema(), 7.0, 3.3, "#141A24")

    def _encendidas(self, dibujo, n):
        # las piezas son los primeros n grupos después del contorno punteado
        piezas = list(dibujo.mobs)[len(dibujo.trazo) : len(dibujo.trazo) + n]
        return sum(1 for p in piezas if p[0].get_fill_opacity() > 0.5)

    def test_es_un_recorrido_que_dura_toda_la_voz(self):
        d = self._dibujo()
        self.assertIsNotNone(d.vivo)
        self.assertFalse(d.fisico)
        self.assertLessEqual(d.mobs.height, 3.3 + 1e-6)
        self.assertLessEqual(d.mobs.width, 7.0 + 1e-6)

    def test_parte_con_el_original_y_termina_lleno(self):
        for dimension, n in ((3, 8), (2, 4)):
            with self.subTest(dimension=dimension):
                d = self._dibujo(dimension)
                d.vivo(0.0)
                self.assertEqual(self._encendidas(d, n), 1)
                d.vivo(0.5)
                self.assertTrue(1 < self._encendidas(d, n) < n)
                d.vivo(1.0)
                self.assertEqual(self._encendidas(d, n), n)

    def test_tres_veces_el_lado_son_27_cubos(self):
        d = self._dibujo(factor=3)
        d.vivo(1.0)
        self.assertEqual(self._encendidas(d, 27), 27)


if __name__ == "__main__":
    unittest.main()
