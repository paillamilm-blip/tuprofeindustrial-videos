import inspect
import unittest

from tpi_videos import render

try:
    from tpi_videos import escena
except ModuleNotFoundError:  # Manim no está instalado en este equipo (Windows): esa parte se prueba en CI
    escena = None


class FirmaTest(unittest.TestCase):
    @unittest.skipUnless(escena is not None, "manim no está instalado")
    def test_opciones_tiene_solo_gancho(self):
        campos = {f.name for f in __import__("dataclasses").fields(escena.OpcionesEscena)}
        self.assertIn("solo_gancho", campos)

    def test_crear_clip_gancho_existe(self):
        self.assertTrue(callable(render.crear_clip_gancho))
        params = inspect.signature(render.crear_clip_gancho).parameters
        self.assertIn("salida", params)
        self.assertIn("voz", params)


if __name__ == "__main__":
    unittest.main()
