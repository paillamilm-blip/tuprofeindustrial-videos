import unittest

from tpi_videos import componentes as c

try:
    from manim import Paragraph  # noqa: F401  # parrafo() necesita Manim
except ModuleNotFoundError:  # Manim no está instalado en este equipo: esto se prueba en CI
    Paragraph = None


@unittest.skipIf(Paragraph is None, "manim no está instalado")
class DestacaresSolapadosTest(unittest.TestCase):
    """«¿El MCM de 6 y 8 es 48?» destaca 6, 8 y 48: el 8 suelto vive dentro del 48.

    Manim rechaza dos resaltos superpuestos (lanza «Ambiguous style for text») aunque
    compartan el color, así que `parrafo` debe quedarse con el trecho más largo.
    """

    def _gancho(self, destacar):
        return c.parrafo(
            "¿El MCM de 6 y 8 es 48?",
            40,
            color="#1B1B1B",
            destacar=destacar,
            color_destacado="#D32F2F",
        )

    def test_destacares_solapados_no_rompen_el_parrafo(self):
        parrafo = self._gancho(["6", "8", "48"])
        self.assertGreaterEqual(len(parrafo), 1)

    def test_el_trecho_largo_queda_completo_en_el_color_de_acento(self):
        parrafo = self._gancho(["6", "8", "48"])
        cuatro, ocho = c.frase_en_parrafo(parrafo, "48")[0]
        self.assertEqual(cuatro.get_color().to_hex().lower(), "#d32f2f")
        self.assertEqual(ocho.get_color().to_hex().lower(), "#d32f2f")

    def test_sin_solapamientos_se_destacan_todos(self):
        parrafo = self._gancho(["6", "48"])
        for frase in ("6", "48"):
            with self.subTest(frase=frase):
                color = c.frase_en_parrafo(parrafo, frase)[0][0].get_color().to_hex().lower()
                self.assertEqual(color, "#d32f2f")


if __name__ == "__main__":
    unittest.main()
