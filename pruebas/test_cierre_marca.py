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


@unittest.skipUnless(escena is not None, "manim no está instalado")
class StickerEnTemasSobriosTest(unittest.TestCase):
    def test_el_logo_de_la_marca_va_tambien_en_los_sobrios(self):
        """`plano_azul`, `vineta_cine` y compañía apagan emojis, pero tu logo es identidad."""
        self.assertTrue(escena.dibuja_el_sticker("logo", de_la_marca=True, tema_emojis=False))

    def test_los_stickers_comicos_siguen_apagados_en_los_sobrios(self):
        self.assertFalse(escena.dibuja_el_sticker("explota", de_la_marca=False, tema_emojis=False))

    def test_en_un_tema_con_emojis_se_dibuja_igual(self):
        self.assertTrue(escena.dibuja_el_sticker("explota", de_la_marca=False, tema_emojis=True))

    def test_sin_sticker_no_hay_nada_que_dibujar(self):
        self.assertFalse(escena.dibuja_el_sticker(None, de_la_marca=True, tema_emojis=True))


@unittest.skipUnless(escena is not None, "manim no está instalado")
class LogoEnCabeceraTest(unittest.TestCase):
    """La franja de arriba lleva tu logo, no el engranaje dibujado, cuando la marca tiene uno.

    El defecto que cierra: la cabecera llamaba siempre a ``engranaje`` con el color de acento del
    estilo, así que el logo subido en Ajustes sólo aparecía al cierre.
    """

    class _Trampa(escena.VideoEjercicio):
        """Lo mínimo que pide ``_cabecera``: marca, tema, colores y materia, sin armar la escena."""

        def __init__(self, emoji_marca: str, marco: str = "pizarra") -> None:
            self.marca = Marca.model_validate({"cierre": {"emoji": emoji_marca}})
            self.tema = SimpleNamespace(marco=marco, emojis=False)
            self.col = SimpleNamespace(acento="#FB923C", fondo="#0B1220", titulos="#F8FAFC")
            self.color_materia = "#FB923C"
            self.guion = SimpleNamespace(etiqueta_materia="FÍSICA")

    def _icono(self, emoji_marca: str):
        return self._Trampa(emoji_marca)._cabecera()[0][0]

    def test_con_logo_de_la_marca_va_la_imagen(self):
        """«💡» es un PNG real del catálogo: prueba que la cabecera mira el sticker de la marca."""
        from manim import ImageMobject

        self.assertIsInstance(self._icono("💡"), ImageMobject)

    def test_sin_logo_de_la_marca_sigue_el_engranaje_dibujado(self):
        from manim import ImageMobject

        self.assertNotIsInstance(self._icono(""), ImageMobject)

    def test_el_logo_se_apaga_junto_con_la_cabecera(self):
        """Al acercarse la cámara la cabecera se disuelve; el logo no puede quedarse solo flotando."""
        trampa = self._Trampa("💡")
        trampa.fondo = SimpleNamespace()
        trampa.cabecera = trampa._cabecera()
        trampa._cabecera_opacidades, trampa._cabecera_imagenes = [], []
        trampa._fijar_cabecera()
        self.assertIn(trampa.cabecera[0][0], trampa._cabecera_imagenes)

    def test_en_la_hoja_el_logo_va_arriba_y_se_apaga_con_la_cinta(self):
        """En la hoja la cabecera propia está vacía: el logo tiene que sumarse a «Notas»/«Fecha:»."""
        from manim import ImageMobject, Text, VGroup

        from tpi_videos import componentes as c

        trampa = self._Trampa("💡", marco="hoja")
        # la cinta de `marco_hoja` vive a la altura 6,5, fuera de la hoja
        trampa.fondo = SimpleNamespace(cinta=VGroup(Text("Notas").move_to([0, 6.5, 0])))
        trampa.cabecera = trampa._cabecera()
        trampa._cabecera_opacidades, trampa._cabecera_imagenes = [], []
        trampa._fijar_cabecera()
        logo = trampa.cabecera[0]
        self.assertIsInstance(logo, ImageMobject)
        self.assertIn(logo, trampa._cabecera_imagenes)  # viaja con la cinta al disolverse
        self.assertAlmostEqual(logo.get_center()[1], 6.5, delta=0.15)  # a la altura de la cinta
        self.assertGreater(logo.get_center()[1], c.HOJA_CENTRO_Y)  # arriba, no dentro de la hoja

    def test_sin_logo_la_hoja_queda_como_estaba(self):
        trampa = self._Trampa("", marco="hoja")
        self.assertEqual(len(trampa._cabecera()), 0)


class StickersDelPanelTest(unittest.TestCase):
    def test_el_panel_ofrece_los_png_subidos_por_su_nombre(self):
        """Lo que se sube en Ajustes aparece en la lista del selector del cierre."""
        from tpi_videos.emojis import stickers_disponibles

        with tempfile.TemporaryDirectory() as carpeta:
            (Path(carpeta) / "logo.png").write_bytes(b"x")
            (Path(carpeta) / "mascota.png").write_bytes(b"x")
            (Path(carpeta) / "notas.txt").write_text("no es un sticker", encoding="utf-8")
            self.assertEqual(stickers_disponibles(Path(carpeta)), ["logo", "mascota"])

    def test_sin_carpeta_de_stickers_no_hay_lista(self):
        from tpi_videos.emojis import stickers_disponibles

        with tempfile.TemporaryDirectory() as carpeta:
            self.assertEqual(stickers_disponibles(Path(carpeta) / "no_existe"), [])
