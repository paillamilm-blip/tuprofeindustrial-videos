"""Los sólidos de siempre (cubo, cilindro, cono, esfera) con su volumen y su área calculados y dibujados."""

import math
import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_solido

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, solido

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class MatematicaSolidoTest(unittest.TestCase):
    """Las fórmulas del cuaderno: π r² h, un tercio de eso en el cono, y la esfera completa."""

    def test_el_cilindro(self):
        figura = analizar_solido("cilindro", radio="3 cm", altura="5 cm")
        self.assertAlmostEqual(figura.volumen, math.pi * 9 * 5, places=2)
        self.assertAlmostEqual(figura.area, 2 * math.pi * 3 * 8, places=2)
        self.assertEqual(figura.unidad, "cm")

    def test_el_cono_usa_la_generatriz(self):
        figura = analizar_solido("cono", radio="3 cm", altura="4 cm")
        self.assertAlmostEqual(figura.volumen, math.pi * 9 * 4 / 3, places=2)
        self.assertAlmostEqual(figura.area, math.pi * 3 * (3 + 5), places=2)

    def test_la_esfera(self):
        figura = analizar_solido("esfera", radio="3 cm")
        self.assertAlmostEqual(figura.volumen, 4 * math.pi * 27 / 3, places=2)
        self.assertAlmostEqual(figura.area, 4 * math.pi * 9, places=2)

    def test_el_cubo(self):
        figura = analizar_solido("cubo", lado="4 cm")
        self.assertAlmostEqual(figura.volumen, 64, places=6)
        self.assertAlmostEqual(figura.area, 96, places=6)

    def test_al_cilindro_le_falta_la_altura(self):
        with self.assertRaises(ValueError) as error:
            analizar_solido("cilindro", radio="3 cm")
        self.assertIn("altura", str(error.exception))

    def test_una_medida_sin_numero_se_rechaza(self):
        with self.assertRaises(ValueError) as error:
            analizar_solido("esfera", radio="grande")
        self.assertIn("número", str(error.exception))

    def test_un_solido_que_el_motor_no_conoce(self):
        with self.assertRaises(ValueError) as error:
            analizar_solido("piramide", radio="3 cm")
        self.assertIn("piramide", str(error.exception))


class GuionSolidoTest(unittest.TestCase):
    def test_pide_el_solido_con_sus_medidas(self):
        visual = Visual(tipo="solido", figura="cilindro", radio="3 cm", altura="5 cm", anotar=["volumen"])
        self.assertAlmostEqual(visual.solido().volumen, math.pi * 45, places=2)

    def test_sin_radio_el_error_habla_del_solido(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="solido", figura="esfera", altura="5 cm")
        self.assertIn("radio", str(error.exception))

    def test_marca_desconocida_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="solido", figura="cubo", lado="4 cm", anotar=["arista"])
        self.assertIn("arista", str(error.exception))

    def test_el_yaml_guarda_el_solido(self):
        texto = "\n".join(
            _visual_yaml({"tipo": "solido", "figura": "cono", "radio": "3 cm", "altura": "4 cm"})
        )
        self.assertIn("tipo: solido", texto)
        self.assertIn("figura: cono", texto)
        self.assertIn("radio: '3 cm'", texto)

    def test_la_ia_puede_pedir_el_solido(self):
        paso = PasoIA(
            nota="Calculo el volumen",
            tex=r"V = \pi r^2 h",
            voz="Mira el cilindro y su volumen.",
            dibujo="solido",
            figura="cilindro",
            radio="3 cm",
            altura="5 cm",
            anotar=["volumen", "area"],
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "solido")
        self.assertEqual(visual.anotar, ["volumen", "area"])


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoSolidoTest(unittest.TestCase):
    """El dibujo es la lámina del libro: el cuerpo en perspectiva chica y sus medidas al lado."""

    def _dibujar(self, figura="cilindro", anotar=("volumen", "area"), **medidas):
        por_defecto = {"cubo": {"lado": "4 cm"}, "esfera": {"radio": "3 cm"}}.get(
            figura, {"radio": "3 cm", "altura": "5 cm" if figura != "cono" else "4 cm"}
        )
        por_defecto.update(medidas)
        return solido(
            analizar_solido(figura, **por_defecto), list(anotar), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )

    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_los_cuatro_entran_en_la_franja(self):
        for figura in ("cubo", "cilindro", "cono", "esfera"):
            dib = self._dibujar(figura)
            self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6, figura)
            self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6, figura)

    def test_el_cilindro_escribe_sus_numeros_con_coma_chilena(self):
        textos = self._textos(self._dibujar("cilindro"))
        self.assertIn("141,37", textos)
        self.assertIn("150,8", textos)
        self.assertIn("cm³", textos)

    def test_el_cubo_escribe_numeros_enteros(self):
        textos = self._textos(self._dibujar("cubo"))
        self.assertIn("64", textos)
        self.assertIn("96", textos)


if __name__ == "__main__":
    unittest.main()
