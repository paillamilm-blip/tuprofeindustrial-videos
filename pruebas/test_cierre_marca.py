"""El cierre lleva el sticker de la marca (el logo subido) salvo que el guion pida otro."""

import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace

from tpi_videos.config import Cierre, Marca, cargar_marca
from tpi_videos.errores import ErrorMotor

try:
    from tpi_videos import escena
except ModuleNotFoundError:  # Manim no está instalado en este equipo: esa parte se prueba en CI
    escena = None


class CierreDeLaMarcaTest(unittest.TestCase):
    def test_la_marca_puede_guardar_su_sticker_de_cierre(self):
        """El logo se sube a mis_ajustes/stickers/logo.png; la marca tiene que poder nombrarlo."""
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "marca.yaml"
            ruta.write_text("cierre:\n  emoji: logo\n", encoding="utf-8")
            self.assertEqual(cargar_marca(ruta).cierre.emoji, "logo")

    def test_sin_sticker_el_cierre_queda_como_siempre(self):
        # El valor por defecto, no el de mis_ajustes: cada uno tiene su logo en su Mac.
        self.assertEqual(Cierre().emoji, "")

    def test_el_guion_manda_sobre_la_marca(self):
        marca = Marca.model_validate({"cierre": {"emoji": "logo"}})
        self.assertEqual(marca.sticker_del_cierre("🤯"), "🤯")
        self.assertEqual(marca.sticker_del_cierre(None), "logo")

    def test_sin_sticker_en_la_marca_ni_en_el_guion_no_hay_sticker(self):
        """Sin sticker el cierre dibuja el engranaje, que es como estaba antes de subir el logo."""
        self.assertIsNone(Marca().sticker_del_cierre(None))


@unittest.skipUnless(escena is not None, "manim no está instalado")
class StickerAusenteTest(unittest.TestCase):
    def test_si_el_sticker_del_cierre_no_existe_lo_dice(self):
        """Un nombre mal escrito o un PNG borrado no puede terminar en un engranaje sin avisar."""
        falso = SimpleNamespace(
            guion=SimpleNamespace(cierre=None),
            marca=Marca.model_validate({"cierre": {"emoji": "noexiste"}}),
            tema=SimpleNamespace(emojis=True),
        )
        falso._emoji = MethodType(escena.VideoEjercicio._emoji, falso)
        with self.assertRaises(ErrorMotor) as sube:
            escena.VideoEjercicio._cierre(falso)
        texto = str(sube.exception)
        self.assertIn("«noexiste»", texto)
        self.assertIn("mis_ajustes/stickers/noexiste.png", texto)
