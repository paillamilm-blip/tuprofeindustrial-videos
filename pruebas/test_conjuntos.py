"""Conjuntos, recta numérica y probabilidad: los dibujos que pide la PAES de matemática."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_probabilidad, analizar_recta, analizar_venn

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, probabilidad, recta, venn

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class MatematicaConjuntosTest(unittest.TestCase):
    def test_el_venn_suma_sus_cuatro_regiones(self):
        figura = analizar_venn(5, 3, 2, 4)
        self.assertEqual(figura.total, 14)

    def test_el_venn_rechaza_contajes_negativos(self):
        with self.assertRaises(ValueError) as error:
            analizar_venn(5, -3, 2)
        self.assertIn("negativo", str(error.exception))

    def test_la_recta_con_dos_extremos(self):
        figura = analizar_recta(-1, 3)
        self.assertLessEqual(figura.x0, -1)
        self.assertGreaterEqual(figura.x1, 3)
        self.assertFalse(figura.es_rayo)

    def test_la_recta_con_un_extremo_es_un_rayo(self):
        figura = analizar_recta(2)
        self.assertTrue(figura.es_rayo)

    def test_la_recta_rechaza_el_intervalo_al_reves(self):
        with self.assertRaises(ValueError) as error:
            analizar_recta(3, 1)
        self.assertIn("mayor", str(error.exception))

    def test_la_probabilidad_es_el_cociente(self):
        figura = analizar_probabilidad(3, 8)
        self.assertAlmostEqual(figura.p, 0.375, places=6)

    def test_no_puede_haber_mas_favorables_que_casos(self):
        with self.assertRaises(ValueError) as error:
            analizar_probabilidad(9, 8)
        self.assertIn("favorables", str(error.exception))


class GuionConjuntosTest(unittest.TestCase):
    def test_pide_el_venn_con_sus_contajes(self):
        visual = Visual(tipo="venn", solo_a=5, solo_b=3, ambos=2, anotar=["total"])
        self.assertEqual(visual.venn().total, 10)

    def test_al_venn_le_falta_un_contaje(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="venn", solo_a=5, solo_b=3)
        self.assertIn("ambos", str(error.exception))

    def test_la_recta_pide_su_extremo(self):
        visual = Visual(tipo="recta", extremo_a=2, incluye_a=False)
        self.assertTrue(visual.recta().es_rayo)

    def test_la_recta_al_reves_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="recta", extremo_a=3, extremo_b=1)
        self.assertIn("mayor", str(error.exception))

    def test_la_probabilidad_pide_sus_casos(self):
        visual = Visual(tipo="probabilidad", favorables=3, totales=8, anotar=["probabilidad"])
        self.assertAlmostEqual(visual.probabilidad().p, 0.375, places=6)

    def test_el_yaml_guarda_el_venn(self):
        texto = "\n".join(_visual_yaml({"tipo": "venn", "solo_a": 5, "solo_b": 3, "ambos": 2}))
        self.assertIn("tipo: venn", texto)
        self.assertIn("ambos: 2", texto)

    def test_la_ia_puede_pedir_la_recta(self):
        paso = PasoIA(
            nota="Marco la solución",
            tex=r"x \geq 2",
            voz="Mira la recta con la solución.",
            dibujo="recta",
            extremo_a=2.0,
            incluye_a=True,
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "recta")
        self.assertEqual(visual.extremo_a, 2.0)


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoConjuntosTest(unittest.TestCase):
    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_el_venn_escribe_sus_regiones_y_el_total(self):
        dib = venn(analizar_venn(5, 3, 2, 4), ["total"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        textos = self._textos(dib)
        for numero in ("5", "3", "2", "4", "14"):
            self.assertIn(numero, textos)

    def test_la_recta_entra_en_la_franja(self):
        dib = recta(analizar_recta(-1, 3), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertTrue(dib.trazo)

    def test_la_probabilidad_escribe_su_decimal_con_coma(self):
        dib = probabilidad(
            analizar_probabilidad(3, 8), ["probabilidad"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertIn("0,38", self._textos(dib))


if __name__ == "__main__":
    unittest.main()
