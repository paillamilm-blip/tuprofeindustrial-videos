"""La revisión y el chequeo de LaTeX entienden una conclusión en texto (sin fórmula)."""

import unittest
from unittest.mock import patch

from pruebas.datos_didacticos import datos_base, datos_concepto
from tpi_videos.guion import Guion
from tpi_videos.revision import revisar


def _concepto_fisica(**resultado):
    datos = datos_concepto()
    datos["materia"] = "fisica"
    datos["resultado"].update(resultado)
    return Guion.model_validate(datos)


class RevisionConclusionTest(unittest.TestCase):
    def _avisos(self, guion, seccion):
        return [a.mensaje for a in revisar(guion, "Sígueme").avisos if a.donde == seccion]

    def test_conclusion_textual_no_pide_unidades(self):
        self.assertFalse([m for m in self._avisos(_concepto_fisica(), "resultado") if "unidades" in m])

    def test_ejercicio_heredado_sigue_pidiendo_unidades(self):
        datos = datos_base()
        datos["materia"] = "fisica"
        avisos = self._avisos(Guion.model_validate(datos), "resultado")
        self.assertTrue([m for m in avisos if "unidades" in m])

    def test_formula_de_fisica_sin_unidades_en_un_concepto_si_avisa(self):
        avisos = self._avisos(_concepto_fisica(tex="v = 8"), "resultado")
        self.assertTrue([m for m in avisos if "unidades" in m])

    def test_emoji_dentro_de_la_conclusion_avisa(self):
        avisos = self._avisos(_concepto_fisica(texto="Crecen distinto 🤯"), "resultado")
        self.assertTrue([m for m in avisos if "emoji" in m])

    def test_conclusion_larga_sugiere_acortar(self):
        avisos = self._avisos(_concepto_fisica(texto="Una conclusión muy larga para leer. " * 6), "resultado")
        self.assertTrue([m for m in avisos if "larga" in m])


class LatexConclusionTest(unittest.TestCase):
    def test_no_compila_un_resultado_sin_formula(self):
        try:
            import manim  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("manim no está instalado")
        from tpi_videos import redactor

        compiladas = []
        with (
            patch("tpi_videos.entorno.latex_disponible", return_value=("latex", "dvisvgm")),
            patch("manim.MathTex", side_effect=lambda tex, *a, **k: compiladas.append(tex)),
        ):
            self.assertEqual(redactor.errores_latex(Guion.model_validate(datos_concepto())), [])
        self.assertNotIn("", compiladas)
        self.assertEqual(compiladas, ["a = 1", "a = 2"])


if __name__ == "__main__":
    unittest.main()
