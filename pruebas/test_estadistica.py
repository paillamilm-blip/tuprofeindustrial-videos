"""Estadística a mano alzada: torta de porcentajes y barras de datos."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_barras, analizar_torta

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, barras, torta

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)

CURSO = ["Fútbol 12", "Básquetbol 8", "Vóley 5", "Otros 5"]  # 30 en total


class MatematicaDatosTest(unittest.TestCase):
    def test_la_torta_saca_el_total_y_las_fracciones(self):
        figura = analizar_torta(CURSO)
        self.assertAlmostEqual(figura.total, 30.0, places=6)
        self.assertAlmostEqual(figura.categorias[0].fraccion, 0.4, places=6)

    def test_la_torta_rechaza_una_sola_categoria(self):
        with self.assertRaises(ValueError) as error:
            analizar_torta(["Fútbol 12"])
        self.assertIn("categor", str(error.exception))

    def test_cada_categoria_necesita_su_numero(self):
        with self.assertRaises(ValueError) as error:
            analizar_torta(["Fútbol doce", "Básquetbol 8"])
        self.assertIn("número", str(error.exception))

    def test_la_torta_rechaza_demasiadas_categorias(self):
        con_siete = [f"C{i} {i + 1}" for i in range(7)]
        with self.assertRaises(ValueError) as error:
            analizar_torta(con_siete)
        self.assertIn("seis", str(error.exception))

    def test_las_barras_conocen_su_maximo(self):
        figura = analizar_barras(CURSO)
        self.assertAlmostEqual(figura.maximo, 12.0, places=6)

    def test_las_barras_rechazan_un_valor_negativo(self):
        with self.assertRaises(ValueError) as error:
            analizar_barras(["Fútbol -12", "Básquetbol 8"])
        self.assertIn("positiv", str(error.exception))


class GuionDatosTest(unittest.TestCase):
    def test_la_torta_pide_sus_categorias(self):
        visual = Visual(tipo="torta", categorias=CURSO)
        self.assertAlmostEqual(visual.torta().total, 30.0, places=6)

    def test_sin_categorias_no_hay_torta(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="torta")
        self.assertIn("categorias", str(error.exception))

    def test_las_barras_tambien_las_pide(self):
        visual = Visual(tipo="barras", categorias=CURSO)
        self.assertAlmostEqual(visual.barras().maximo, 12.0, places=6)

    def test_el_yaml_guarda_las_categorias(self):
        texto = "\n".join(_visual_yaml({"tipo": "torta", "categorias": CURSO}))
        self.assertIn("tipo: torta", texto)
        self.assertIn("Fútbol 12", texto)

    def test_la_ia_puede_pedir_las_barras(self):
        paso = PasoIA(
            nota="Comparo los deportes",
            tex=r"12 > 8 > 5",
            voz="Mira las barras.",
            dibujo="barras",
            categorias=CURSO,
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "barras")
        self.assertEqual(len(visual.categorias), 4)


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoDatosTest(unittest.TestCase):
    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_la_torta_escribe_porcentaje_y_nombre(self):
        dib = torta(analizar_torta(CURSO), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        textos = self._textos(dib)
        self.assertIn("40%", textos)
        self.assertIn("Fútbol", textos)

    def test_las_barras_entran_en_la_franja(self):
        dib = barras(analizar_barras(CURSO), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertTrue(dib.trazo)
        self.assertIn("12", self._textos(dib))


if __name__ == "__main__":
    unittest.main()
