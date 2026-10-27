"""Física a mano alzada: barra de energía (un total repartido) y onda con sus cotas."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_energia, analizar_onda

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, energia, onda

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class OndaTest(unittest.TestCase):
    def test_la_onda_saca_frecuencia_y_velocidad(self):
        figura = analizar_onda("0,5 m", "2 m", periodo=0.4)
        self.assertAlmostEqual(figura.frecuencia, 2.5, places=6)
        self.assertAlmostEqual(figura.velocidad, 5.0, places=6)

    def test_sin_periodo_no_hay_velocidad(self):
        figura = analizar_onda("0,5 m", "2 m")
        self.assertIsNone(figura.velocidad)

    def test_la_onda_rechaza_una_amplitud_sin_numero(self):
        with self.assertRaises(ValueError) as error:
            analizar_onda("media metro", "2 m")
        self.assertIn("número", str(error.exception))

    def test_la_onda_rechaza_una_longitud_negativa(self):
        with self.assertRaises(ValueError) as error:
            analizar_onda("0,5 m", "-2 m")
        self.assertIn("positiv", str(error.exception))


class EnergiaTest(unittest.TestCase):
    def test_los_tramos_suman_el_total(self):
        figura = analizar_energia(["Cinética 60", "Térmica 40"])
        self.assertAlmostEqual(figura.total, 100.0, places=6)
        self.assertAlmostEqual(figura.tramos[0].fraccion, 0.6, places=6)

    def test_un_tramo_sin_numero_se_rechaza(self):
        with self.assertRaises(ValueError) as error:
            analizar_energia(["Cinética mucha", "Térmica 40"])
        self.assertIn("número", str(error.exception))


class GuionOndaEnergiaTest(unittest.TestCase):
    def test_la_onda_pide_sus_dos_medidas(self):
        visual = Visual(tipo="onda", amplitud="0,5 m", longitud_onda="2 m")
        self.assertAlmostEqual(visual.onda().amplitud, 0.5, places=6)

    def test_pedir_velocidad_sin_periodo_no_se_puede(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="onda", amplitud="0,5 m", longitud_onda="2 m", anotar=["velocidad"])
        self.assertIn("periodo", str(error.exception))

    def test_la_energia_reusa_las_categorias(self):
        visual = Visual(tipo="energia", categorias=["Cinética 60", "Térmica 40"])
        self.assertAlmostEqual(visual.energia().total, 100.0, places=6)

    def test_sin_categorias_no_hay_energia(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="energia")
        self.assertIn("categorias", str(error.exception))

    def test_el_yaml_guarda_la_onda(self):
        texto = "\n".join(
            _visual_yaml({"tipo": "onda", "amplitud": "0,5 m", "longitud_onda": "2 m", "periodo": 0.4})
        )
        self.assertIn("tipo: onda", texto)
        self.assertIn("longitud_onda", texto)

    def test_la_ia_puede_pedir_energia(self):
        paso = PasoIA(
            nota="Reparto la energía",
            tex=r"E_{total} = 100\ \text{J}",
            voz="Mira la barra.",
            dibujo="energia",
            categorias=["Cinética 60", "Térmica 40"],
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "energia")


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoOndaEnergiaTest(unittest.TestCase):
    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_la_onda_anota_amplitud_lambda_y_velocidad(self):
        dib = onda(
            analizar_onda("0,5 m", "2 m", periodo=0.4), ["velocidad"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        textos = self._textos(dib)
        self.assertIn("0,5", textos)
        self.assertIn("λ", textos)
        self.assertIn("5 m/s", textos)

    def test_la_barra_de_energia_escribe_sus_tramos(self):
        dib = energia(analizar_energia(["Cinética 60", "Térmica 40"]), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertTrue(dib.trazo)
        textos = self._textos(dib)
        self.assertIn("60%", textos)
        self.assertIn("Cinética", textos)


if __name__ == "__main__":
    unittest.main()
