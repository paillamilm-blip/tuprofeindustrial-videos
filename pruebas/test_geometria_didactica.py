"""Geometría de la conclusión con herramientas compuestas: nada cortado y aire frente a subtítulos y resumen.

Se renderiza la escena completa (animaciones saltadas, voz de silencio) y se mide en coordenadas de
PANTALLA en el momento en que la conclusión ya está escrita: así cuenta el acercamiento de la cámara.
"""

import contextvars
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pruebas.datos_didacticos import datos_concepto
from tpi_videos.config import Marca, cargar_marca
from tpi_videos.didactica import componer_tema
from tpi_videos.guion import Guion
from tpi_videos.render import subtitulos_de
from tpi_videos.temas import Tema, cargar_tema

try:
    from manim import tempconfig

    from tpi_videos import escena
except ModuleNotFoundError:  # sin Manim: se prueba en CI
    escena = None

SEPARACION = 0.3
_CONFIG = {
    "frame_height": 16, "frame_width": 9, "pixel_height": 160, "pixel_width": 90, "frame_rate": 10,
    "skip_animations": True, "write_to_movie": False,
}  # fmt: skip


def _guion(n_pasos: int, camara: str, con_formula: bool) -> Guion:
    datos = datos_concepto()
    datos["camara"] = camara
    datos["recursos"] = {"panel": True, "tabs": True}
    datos["pasos"] = [{"voz": f"Paso número {i}.", "tex": f"a_{{{i}}} = {i}"} for i in range(1, n_pasos + 1)]
    datos["resultado"]["texto"] = "Al duplicar la arista, el volumen no se duplica: se multiplica por ocho."
    if con_formula:
        datos["resultado"]["tex"] = "V_2 = 8\\,V_1"
    return Guion.model_validate(datos)


def _pantalla(mob, frame):
    """Caja (izq, der, abajo, arriba) del objeto en coordenadas de pantalla de 9 × 16."""
    k = 9.0 / frame.width
    cx, cy = frame.get_center()[:2]
    return (
        (mob.get_left()[0] - cx) * k,
        (mob.get_right()[0] - cx) * k,
        (mob.get_bottom()[1] - cy) * k,
        (mob.get_top()[1] - cy) * k,
    )


def _banda_subtitulos(tema: Tema) -> tuple[float, float]:
    """(abajo, arriba) de un subtítulo de DOS líneas, centrado en posicion_y (ASS, alineación 5)."""
    estilo = subtitulos_de(tema)
    centro = 8.0 - estilo.posicion_y * 16.0
    alto = 2 * 1.25 * estilo.tamano / 1920 * 16.0
    return centro - alto / 2, centro + alto / 2


@unittest.skipUnless(escena is not None, "manim no está instalado")
class GeometriaConclusionTest(unittest.TestCase):
    def _medir(self, tema: Tema, guion: Guion):
        compuesto = componer_tema(tema, guion)
        medidas = {}

        class Midiendo(escena.VideoEjercicio):
            def _conclusion(self):
                super()._conclusion()
                self.update_mobjects(0)  # los componentes fijos siguen a la cámara
                frame = self.camera.frame
                medidas["conclusion"] = _pantalla(self.bloque_resultado, frame)
                medidas["panel"] = _pantalla(self.panel_gram, frame)
                medidas["tabs"] = _pantalla(self.tabs_gram, frame)

            def _verificacion(self):  # noqa: D401 - lo de después no se mide
                pass

            def _cierre(self):
                pass

        with TemporaryDirectory() as carpeta, tempconfig({**_CONFIG, "media_dir": carpeta}):
            opciones = escena.OpcionesEscena("silencio", "", "+0%", Path(carpeta) / "t.json")
            # construct() fija el estilo activo (ContextVar): en un contexto aparte no se filtra
            contextvars.copy_context().run(Midiendo(guion, Marca(), compuesto, opciones).construct)
        return compuesto, medidas

    def _revisar(self, tema: Tema, guion: Guion):
        compuesto, m = self._medir(tema, guion)
        izq, der, abajo, arriba = m["conclusion"]
        donde = f"{tema.nombre}, {len(guion.pasos)} pasos, cámara {guion.camara}"
        self.assertGreaterEqual(izq, -4.5, donde)
        self.assertLessEqual(der, 4.5, donde)
        sub_abajo, sub_arriba = _banda_subtitulos(compuesto)
        self.assertGreaterEqual(abajo - sub_arriba, SEPARACION, f"{donde}: la conclusión toca el subtítulo")
        self.assertGreaterEqual(sub_abajo - m["panel"][3], SEPARACION, f"{donde}: el subtítulo toca el resumen")
        self.assertGreaterEqual(m["tabs"][2] - arriba, SEPARACION, f"{donde}: la conclusión toca los pasos")
        self.assertLessEqual(m["panel"][3] - m["panel"][2], (compuesto.layout.banda_panel or 1.6) + 1e-6)
        self.assertGreaterEqual(m["panel"][2], -8.0 - 1e-6, donde)
        self.assertLessEqual(m["tabs"][3], 8.0 + 1e-6, donde)

    def test_hoja_con_resumen_nuevo(self):
        tema = Tema(nombre="Hoja", marco="hoja")
        for n, camara, formula in ((4, "fuerte", True), (4, "quieta", False), (30, "suave", True)):
            with self.subTest(n=n, camara=camara, formula=formula):
                self._revisar(tema, _guion(n, camara, formula))

    def test_consola_mito_con_resumen_por_eleccion(self):
        tema = cargar_tema("consola_mito", cargar_marca())
        for n, camara, formula in ((4, "fuerte", True), (30, "suave", False)):
            with self.subTest(n=n, camara=camara, formula=formula):
                self._revisar(tema, _guion(n, camara, formula))


if __name__ == "__main__":
    unittest.main()
