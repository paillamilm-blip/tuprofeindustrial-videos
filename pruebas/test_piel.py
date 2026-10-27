import unittest

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

from tpi_videos.componentes import marco_hoja
from tpi_videos.config import cargar_marca
from tpi_videos.temas import cargar_tema


@unittest.skipUnless(MANIM, "manim no esta instalado")
class HojaTest(unittest.TestCase):
    def _etiqueta(self, tema):
        marco = marco_hoja(tema)
        buscado = tema.hoja.etiqueta.strip()
        self.assertTrue(buscado, "el tema no pone etiqueta: nada que probar")
        return next(m for m in marco.get_family() if getattr(m, "text", "") == buscado)

    def test_sobre_fondo_oscuro_la_etiqueta_clarea(self):
        """El fondo de «hoja_de_desarrollo» es casi negro: la etiqueta va en el color del papel."""
        tema = cargar_tema("hoja_de_desarrollo", cargar_marca())
        self.assertEqual(str(self._etiqueta(tema).color).upper(), tema.hoja.color.upper())

    def test_sobre_fondo_claro_la_etiqueta_usa_el_tenue(self):
        """En papel claro el blanco desaparecía: «rotulador» tiene fondo #E9E7DF."""
        tema = cargar_tema("rotulador", cargar_marca())
        claro = tema.model_copy(update={"hoja": tema.hoja.model_copy(update={"etiqueta": "Clase"})})
        self.assertNotEqual(str(self._etiqueta(claro).color).upper(), "#FFFFFF")
        self.assertEqual(str(self._etiqueta(claro).color).upper(), tema.colores.tenue.upper())


if __name__ == "__main__":
    unittest.main()
