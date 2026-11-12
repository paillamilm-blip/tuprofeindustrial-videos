import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from manim import tempconfig

from tpi_videos import componentes as c, escena
from tpi_videos.config import Marca
from tpi_videos.guion import Guion
from tpi_videos.temas import Tema, cargar_tema, listar_temas


class EscenaGramaticaTest(unittest.TestCase):
    def test_tema_viejo_no_construye_gramatica(self):
        tabs, panel = escena.gramatica_de(Tema(nombre="viejo"), 3)
        self.assertIsNone(tabs)
        self.assertIsNone(panel)

    def test_tema_con_gramatica_construye_tabs_y_panel(self):
        t = Tema(nombre="g", gramatica={"tabs": True, "panel": True})
        tabs, panel = escena.gramatica_de(t, 3)
        self.assertEqual(len(tabs), 3)
        self.assertIsNotNone(panel)

    def test_consola_paso_a_paso_se_lista_y_activa_gramatica(self):
        t = cargar_tema("consola_pasos", Marca())
        self.assertTrue(t.gramatica.tabs)
        self.assertTrue(t.gramatica.panel)
        self.assertFalse(t.resplandor)  # versión sobria: sin brillo neón
        self.assertIn("consola_pasos", [clave for clave, _, _ in listar_temas()])
        # la Consola neón original queda archivada: ya no se ofrece, pero se sigue pudiendo pedir
        self.assertNotIn("consola_neon", [clave for clave, _, _ in listar_temas()])
        self.assertTrue(cargar_tema("consola_neon", Marca()).gramatica.tabs)

    def test_tabs_caben_con_muchos_pasos(self):
        t = Tema(nombre="g", gramatica={"tabs": True})
        tabs, _ = escena.gramatica_de(t, 30)
        self.assertLessEqual(tabs.width, c.ancho_util_de(t) + 1e-6)

    def test_subtitulos_se_levantan_sin_mutar_el_tema(self):
        from tpi_videos.render import subtitulos_de
        t = Tema(nombre="g", subtitulos={"posicion_y": 0.82},
                 gramatica={"panel": True}, layout={"banda_panel": 1.6})
        self.assertAlmostEqual(subtitulos_de(t).posicion_y, 0.72)
        self.assertAlmostEqual(t.subtitulos.posicion_y, 0.82)

    def test_subtitulos_viejos_no_cambian(self):
        from tpi_videos.render import subtitulos_de
        t = Tema(nombre="viejo")
        self.assertIs(subtitulos_de(t), t.subtitulos)

    def test_sin_pasos_no_crea_componentes(self):
        t = Tema(nombre="g", gramatica={"tabs": True, "panel": True})
        self.assertEqual(escena.gramatica_de(t, 0), (None, None))


class PersistenciaEnEscenaTest(unittest.TestCase):
    def setUp(self):
        self.carpeta = TemporaryDirectory()
        self.config = tempconfig({
            "frame_height": 16, "frame_width": 9, "pixel_height": 160,
            "pixel_width": 90, "frame_rate": 10, "skip_animations": True,
            "write_to_movie": False, "media_dir": self.carpeta.name,
        })
        self.config.__enter__()
        self.tema = Tema(nombre="g", gramatica={"tabs": True, "panel": True},
                         layout={"banda_panel": 1.6})
        self.token = c.usar_estilo(self.tema)
        guion = Guion.model_validate({
            "titulo": "Prueba", "materia": "matematica", "gancho": {"texto": "¿Cuánto?"},
            "enunciado": {"texto": "Suma dos números."},
            "pasos": [{"voz": "Primero", "tex": "x=1"}, {"voz": "Ahora piensa"},
                      {"voz": "Termina", "tex": "x=2"}],
            "resultado": {"tex": "x=2", "voz": "Son dos."},
        })
        opciones = escena.OpcionesEscena("silencio", "", "+0%", Path(self.carpeta.name) / "tiempo.json")
        self.video = escena.VideoEjercicio(guion, Marca(), self.tema, opciones)

    def tearDown(self):
        c.restablecer_estilo(self.token)
        self.config.__exit__(None, None, None)
        self.carpeta.cleanup()

    def test_panel_permanece_en_escena_tras_varios_pasos(self):
        self.video._iniciar_gramatica()
        panel = self.video.panel_gram
        for i, paso in enumerate(self.video.guion.pasos, 1):
            self.video._cerrar_paso_gramatica(i, paso)
            self.assertIs(self.video.panel_gram, panel)
            self.assertIn(panel, self.video.mobjects)
        self.assertEqual(self.video.cerrados_gram, ["x=1", "x=2"])
        # en la banda de 1,6 entra la recién cerrada: el panel no crece (antes se achicaba entero)
        self.assertGreaterEqual(len(panel[1][2]), 1)
        self.assertEqual(panel[1][2][-1].tex_string, "x=2")
        self.assertLessEqual(panel.height, 1.6 + 1e-6)
        self.assertTrue(all(getattr(formula, "tex_string", None) for formula in panel[1][2]))
        self.assertAlmostEqual(panel[1][1][0].width, panel[1][1][1].width)

    def test_micro_movimiento_no_desprende_los_tabs(self):
        self.tema.gramatica.micro = True
        self.video._iniciar_gramatica()
        tabs = self.video.tabs_gram
        for i, paso in enumerate(self.video.guion.pasos, 1):
            self.video._cerrar_paso_gramatica(i, paso)
            self.assertIn(tabs, self.video.mobjects)
            self.assertEqual(len(tabs[i - 1]), 3)

    def test_tabs_quedan_fuera_de_la_zona_de_formulas(self):
        self.video._iniciar_gramatica()
        tabs = self.video.tabs_gram
        self.assertGreaterEqual(tabs.get_bottom()[1], 7.5)
        self.assertLessEqual(tabs.get_top()[1], 7.9)

    def test_panel_no_invade_la_banda_del_subtitulo(self):
        self.video._iniciar_gramatica()
        for i, paso in enumerate(self.video.guion.pasos, 1):
            self.video._cerrar_paso_gramatica(i, paso)
        panel = self.video.panel_gram
        self.assertLessEqual(panel.height, 1.6)
        self.assertLessEqual(panel.get_top()[1], -6.15 + 1e-6)

    def test_componentes_siguen_fijos_al_mover_la_camara(self):
        self.video._iniciar_gramatica()
        frame = self.video.camera.frame
        panel = self.video.panel_gram
        antes = (panel.get_center() - frame.get_center()) / frame.width
        ancho = panel.width / frame.width
        frame.scale(0.8).shift(np.array([0.2, -0.4, 0]))
        self.video.update_mobjects(0)
        np.testing.assert_allclose((panel.get_center() - frame.get_center()) / frame.width, antes)
        self.assertAlmostEqual(panel.width / frame.width, ancho)
