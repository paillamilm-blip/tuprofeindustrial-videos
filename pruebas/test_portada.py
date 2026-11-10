"""La portada automática: un fotograma entre 2 y 4 s, guardado como portada.jpg junto al video."""

import tempfile
import unittest
from pathlib import Path

from tpi_videos.render import NOMBRE_PORTADA, crear_miniatura, momento_de_portada


def _linea(inicio: float, duracion: float) -> dict:
    return {"bloques": [{"seccion": "gancho", "inicio": inicio, "duracion": duracion}]}


class MomentoTest(unittest.TestCase):
    def test_final_del_gancho_acotado_entre_2_y_4_s(self):
        self.assertEqual(momento_de_portada(_linea(0.0, 3.15), 40), 3.0)  # dentro: fin del gancho
        self.assertEqual(momento_de_portada(_linea(0.0, 1.0), 40), 2.0)  # gancho corto: no antes de 2 s
        self.assertEqual(momento_de_portada(_linea(0.0, 9.0), 40), 4.0)  # gancho largo: no después de 4 s

    def test_sin_bloques_o_video_corto(self):
        self.assertEqual(momento_de_portada({}, 40), 4.0)
        self.assertEqual(momento_de_portada(_linea(0.0, 3.0), 1.5), 1.4)  # nunca fuera del video


class MiniaturaTest(unittest.TestCase):
    def test_saca_portada_jpg_del_video_sin_subtitulos(self):
        try:
            import av
            import numpy as np
        except ImportError:
            self.skipTest("sin PyAV / numpy")
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            intermedio = carpeta / "animacion.mp4"
            with av.open(str(intermedio), "w") as salida:
                flujo = salida.add_stream("libx264", rate=10)
                flujo.width, flujo.height, flujo.pix_fmt = 90, 160, "yuv420p"
                for i in range(50):  # 5 s: el color cambia cada segundo
                    cuadro = np.full((160, 90, 3), (i // 10) * 50, dtype=np.uint8)
                    for paquete in flujo.encode(av.VideoFrame.from_ndarray(cuadro, format="rgb24")):
                        salida.mux(paquete)
                for paquete in flujo.encode():
                    salida.mux(paquete)
            linea = _linea(0.0, 3.15) | {"intermedio": str(intermedio)}
            portada = crear_miniatura(carpeta, linea, 5.0)
            self.assertEqual(portada, carpeta / NOMBRE_PORTADA)
            from PIL import Image

            with Image.open(portada) as imagen:
                self.assertEqual(imagen.format, "JPEG")
                self.assertEqual(imagen.size, (90, 160))
                gris = imagen.convert("L").getpixel((45, 80))
            self.assertAlmostEqual(gris, 150, delta=12)  # el cuadro del segundo 3 (no el del 0)

    def test_si_no_hay_video_no_rompe_el_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(crear_miniatura(Path(tmp), _linea(0.0, 3.0), 5.0))


if __name__ == "__main__":
    unittest.main()
