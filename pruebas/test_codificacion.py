import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tpi_videos.config import CALIDADES
from tpi_videos.postproduccion import _codificacion
from tpi_videos.render import _opciones_del_intermedio


class CodificacionTest(unittest.TestCase):
    def test_resoluciones_y_crf_final(self) -> None:
        self.assertEqual((CALIDADES["final"].ancho, CALIDADES["final"].alto), (1080, 1920))
        self.assertEqual((CALIDADES["borrador"].ancho, CALIDADES["borrador"].alto), (540, 960))
        self.assertEqual(CALIDADES["final"].crf, 18)

    def test_el_intermedio_no_gasta_mas_de_lo_necesario(self) -> None:
        tema = SimpleNamespace(usar_marca=False)
        self.assertEqual(_opciones_del_intermedio("final", tema), {"crf": "16", "preset": "veryfast"})
        self.assertEqual(_opciones_del_intermedio("borrador", tema), {"crf": "20", "preset": "veryfast"})

    def test_el_estilo_de_siempre_conserva_su_codificador(self) -> None:
        tema = SimpleNamespace(usar_marca=True)
        self.assertEqual(_opciones_del_intermedio("final", tema), {"crf": "16"})

    def test_el_final_lleva_crf_18_loudnorm_y_audio_de_redes(self) -> None:
        with patch("tpi_videos.postproduccion._codec_video", return_value=["-c:v", "libx264"]):
            argumentos = _codificacion("ffmpeg", CALIDADES["final"])

        self.assertEqual(argumentos[argumentos.index("-crf") + 1], "18")
        self.assertIn("loudnorm=I=-14:TP=-1.5:LRA=11", argumentos)
        self.assertIn("192k", argumentos)
        self.assertIn("+faststart", argumentos)


if __name__ == "__main__":
    unittest.main()
