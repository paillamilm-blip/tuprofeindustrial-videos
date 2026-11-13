"""Fase 3: marcas nuevas para que cada paso tenga algo que mostrar (frecuencia, perímetro, tiempo de vuelo).

Las marcas solo se dibujan si el guion las pide: sin ellas, el dibujo sale igual que antes.
"""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual
from tpi_videos.visuales import MARCAS_ONDA, MARCAS_POLIGONO, MARCAS_PROYECTIL

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

ONDA = {"tipo": "onda", "amplitud": "0,5 m", "longitud_onda": "2 m", "periodo": 0.4}
HEXAGONO = {"tipo": "poligono_regular", "lados": 6, "lado": "6 cm"}
TIRO = {"tipo": "proyectil", "velocidad": "20 m/s", "angulo": 45}


class MarcasValidanTest(unittest.TestCase):
    def test_las_tres_marcas_estan_en_el_catalogo(self):
        self.assertIn("frecuencia", MARCAS_ONDA)
        self.assertIn("perimetro", MARCAS_POLIGONO)
        self.assertIn("tiempo", MARCAS_PROYECTIL)

    def test_las_marcas_de_siempre_siguen_ahi(self):
        self.assertEqual(MARCAS_ONDA[0], "velocidad")
        self.assertEqual(MARCAS_POLIGONO[:4], ("apotema", "radio", "angulo_central", "angulo_interior"))
        self.assertEqual(MARCAS_PROYECTIL[:3], ("alcance", "altura_maxima", "componentes"))

    def test_un_guion_las_puede_pedir(self):
        Visual.model_validate({**ONDA, "anotar": ["frecuencia"]})
        Visual.model_validate({**HEXAGONO, "anotar": ["perimetro"]})
        Visual.model_validate({**TIRO, "anotar": ["tiempo"]})

    def test_la_frecuencia_sin_periodo_se_explica(self):
        sin_periodo = {k: v for k, v in ONDA.items() if k != "periodo"}
        with self.assertRaises(ValidationError) as error:
            Visual.model_validate({**sin_periodo, "anotar": ["frecuencia"]})
        self.assertIn("periodo", str(error.exception))


@unittest.skipUnless(MANIM, "manim no está instalado")
class MarcasSeDibujanTest(unittest.TestCase):
    def _textos(self, campos):
        from manim import Text

        from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
        from tpi_videos.temas import ColoresTema

        dibujo = dibujar_visual(Visual.model_validate(campos), ColoresTema(), 6.2, ALTO_DIBUJO)
        return [m.original_text for m in dibujo.mobs.get_family() if isinstance(m, Text)]

    def test_la_onda_escribe_su_frecuencia(self):
        textos = self._textos({**ONDA, "anotar": ["frecuencia"]})
        self.assertTrue(any(t.startswith("f = 1/T ≈ 2,5") for t in textos), textos)

    def test_con_solo_la_velocidad_no_aparece_la_frecuencia(self):
        textos = self._textos({**ONDA, "anotar": ["velocidad"]})
        self.assertFalse(any(t.startswith("f =") for t in textos), textos)
        self.assertTrue(any(t.startswith("v = λ/T") for t in textos), textos)

    def test_el_hexagono_escribe_su_perimetro(self):
        self.assertIn("P = 6 · 6 = 36 cm", self._textos({**HEXAGONO, "anotar": ["perimetro"]}))

    def test_sin_la_marca_el_hexagono_no_cambia(self):
        self.assertFalse(any(t.startswith("P =") for t in self._textos(HEXAGONO)))

    def test_el_tiro_escribe_su_tiempo_de_vuelo(self):
        textos = self._textos({**TIRO, "anotar": ["tiempo"]})
        self.assertTrue(any(t.startswith("t ≈ ") and t.endswith(" s") for t in textos), textos)


if __name__ == "__main__":
    unittest.main()
