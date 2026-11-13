"""Conclusión en texto y una sola composición del tema en video, subtítulos y gancho."""

import contextvars
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pruebas.datos_didacticos import datos_base, datos_concepto
from tpi_videos.guion import Guion, a_yaml
from tpi_videos.temas import Tema

try:
    from manim import MathTex, Paragraph, tempconfig

    from tpi_videos import componentes as c
    from tpi_videos import escena
    from tpi_videos.config import Marca
    from tpi_videos.escena import componente_resultado
except ModuleNotFoundError:  # sin Manim (Windows): esta parte se prueba en CI
    escena = None


def _parrafos(objeto):
    return [m for m in objeto.get_family() if isinstance(m, Paragraph)]


def _texto_visible(objeto):
    return " ".join(" ".join(p.lineas_texto) for p in _parrafos(objeto))


def _formulas(objeto):
    return [m for m in objeto.get_family() if isinstance(m, MathTex)]


_CONFIG = {
    "frame_height": 16, "frame_width": 9, "pixel_height": 160, "pixel_width": 90, "frame_rate": 10,
    "skip_animations": True, "write_to_movie": False,
}  # fmt: skip


@unittest.skipUnless(escena is not None, "manim no está instalado")
class ResultadoTextualTest(unittest.TestCase):
    def test_conclusion_es_texto_visible_y_cabe(self):
        g = Guion.model_validate(datos_concepto())
        tema = Tema(nombre="Concepto")
        with tempconfig({"frame_width": 9, "frame_height": 16}):
            objeto = componente_resultado(g, tema)
        self.assertGreater(objeto.width, 0)
        self.assertLessEqual(objeto.width, 7.6)
        self.assertEqual(_texto_visible(objeto).count("Longitud"), 1)
        self.assertIn("crecen de distinta manera.", _texto_visible(objeto))
        self.assertFalse(_formulas(objeto))

    def test_formula_principal_y_texto_como_interpretacion(self):
        datos = datos_concepto()
        datos["resultado"]["tex"] = "V_2 = 8 V_1"
        g = Guion.model_validate(datos)
        with tempconfig({"frame_width": 9, "frame_height": 16}):
            objeto = componente_resultado(g, Tema(nombre="Concepto", marco="hoja"))
        formulas = _formulas(objeto)
        self.assertEqual(len(formulas), 1)
        self.assertIn("crecen de distinta manera.", _texto_visible(objeto))
        # la fórmula va arriba (pieza principal) y el texto debajo
        self.assertGreater(formulas[0].get_bottom()[1], _parrafos(objeto)[0].get_top()[1] - 1e-6)
        self.assertLessEqual(objeto.width, 7.0 + 1e-6)

    def test_conclusion_larga_no_se_sale(self):
        datos = datos_concepto()
        datos["resultado"]["texto"] = " ".join(["La longitud crece una vez y el volumen tres veces."] * 4)
        g = Guion.model_validate(datos)
        with tempconfig({"frame_width": 9, "frame_height": 16}):
            objeto = componente_resultado(g, Tema(nombre="Concepto", marco="hoja"))
        self.assertLessEqual(objeto.width, 7.0 + 1e-6)
        self.assertLess(objeto.height, 6.0)

    def test_conclusion_muy_larga_tiene_alto_maximo_fijo(self):
        """No depende de cuánto mida la letra en cada sistema (en el CI de Linux medía más)."""
        datos = datos_concepto()
        datos["resultado"]["tex"] = "V_2 = 8\\,V_1"
        datos["resultado"]["texto"] = " ".join(["La longitud crece una vez y el volumen tres veces."] * 10)
        g = Guion.model_validate(datos)
        with tempconfig({"frame_width": 9, "frame_height": 16}):
            objeto = componente_resultado(g, Tema(nombre="Concepto", marco="hoja"))
        self.assertLessEqual(objeto[2].height, escena.ALTO_MAX_CONCLUSION + 1e-6)
        self.assertLess(objeto.height, 6.0)

    def test_restablece_el_estilo(self):
        antes = c.estilo_activo()
        with tempconfig({"frame_width": 9, "frame_height": 16}):
            componente_resultado(Guion.model_validate(datos_concepto()), Tema(nombre="H", marco="hoja"))
        self.assertEqual(c.estilo_activo(), antes)


@unittest.skipUnless(escena is not None, "manim no está instalado")
class EscenaConclusionTest(unittest.TestCase):
    """La escena completa (sin video): voz de silencio, animaciones saltadas."""

    def _escena(self, datos, tema, carpeta, didactica=None):
        guion = Guion.model_validate(datos)
        linea = Path(carpeta) / "tiempo.json"
        opciones = escena.OpcionesEscena("silencio", "", "+0%", linea, didactica=didactica)
        return escena.VideoEjercicio(guion, Marca(), tema, opciones), linea

    def test_concepto_sin_formula_termina_con_conclusion(self):
        datos = datos_concepto()
        datos["pasos"][1] = {"voz": "Ahora solo piénsalo."}  # paso solo hablado (rama que ya existe)
        with TemporaryDirectory() as carpeta, tempconfig({**_CONFIG, "media_dir": carpeta}):
            video, linea = self._escena(datos, Tema(nombre="T"), carpeta, didactica=[{"clave": "panel"}])
            contextvars.copy_context().run(video.construct)  # el estilo activo no se filtra
            self.assertIn("crecen de distinta manera.", _texto_visible(video.bloque_resultado))
            self.assertFalse(_formulas(video.bloque_resultado))
            datos_tiempo = json.loads(linea.read_text(encoding="utf-8"))
        secciones = [b["seccion"] for b in datos_tiempo["bloques"]]
        self.assertIn("resultado", secciones)
        self.assertIn("paso 2", secciones)
        self.assertEqual(datos_tiempo["contenido"]["intenciones"], ["dato"])
        self.assertEqual(datos_tiempo["recursos_didacticos"], [{"clave": "panel"}])

    def test_heredado_no_agrega_campos_al_registro(self):
        with TemporaryDirectory() as carpeta, tempconfig({**_CONFIG, "media_dir": carpeta}):
            video, linea = self._escena(datos_base(), Tema(nombre="T"), carpeta)
            contextvars.copy_context().run(video.construct)  # el estilo activo no se filtra
            datos_tiempo = json.loads(linea.read_text(encoding="utf-8"))
            self.assertTrue(_formulas(video.bloque_resultado))
        self.assertNotIn("contenido", datos_tiempo)
        self.assertNotIn("recursos_didacticos", datos_tiempo)


class _Simulado:
    """Lo externo (Manim, FFmpeg, subtítulos) se simula; el guion, el tema y el registro son reales."""

    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self.temas = []
        self.estilos_ass = []
        self.didacticas = []

    def renderizar(self, guion, marca, tema, calidad, proveedor, voz, velocidad, carpeta, **kw):
        self.temas.append(tema)
        self.didacticas.append(kw.get("didactica"))
        self.voces = (proveedor, voz, velocidad, kw.get("tono"))
        video = Path(carpeta) / "animacion.mp4"
        video.write_bytes(b"")
        return video, {"bloques": [], "silencio_de_lectura": 0}

    def escribir_ass(self, grupos, ruta, estilo, **kw):
        self.estilos_ass.append(estilo)
        return ruta


class CrearVideoComponeTest(unittest.TestCase):
    def _correr(self, datos, tema="consola_pasos"):
        with TemporaryDirectory() as carpeta, patch.dict(os.environ, {"TPI_RAIZ": carpeta}):
            raiz = Path(carpeta)
            (raiz / "guiones").mkdir()
            ruta = raiz / "guiones" / "concepto.yaml"
            ruta.write_text(a_yaml(datos), encoding="utf-8")
            sim = _Simulado(raiz)
            with (
                patch("tpi_videos.render.renderizar_manim", side_effect=sim.renderizar),
                patch("tpi_videos.render.verificar_requisitos"),
                patch("tpi_videos.render.crear_miniatura", return_value=None),
                patch("tpi_videos.musica.bucle_cama", return_value=None),
                patch("tpi_videos.postproduccion.quemar_subtitulos"),
                patch("tpi_videos.postproduccion.recodificar"),
                patch("tpi_videos.postproduccion.duracion", return_value=1.0),
                patch("tpi_videos.subtitulos.palabras_de_bloques", return_value=([], {})),
                patch("tpi_videos.subtitulos.escribir_ass", side_effect=sim.escribir_ass),
                patch("tpi_videos.subtitulos.escribir_srt", return_value=None),
            ):
                from tpi_videos import render

                render.crear_video(ruta, calidad="borrador", tema=tema, voz="silencio", proveedor="silencio")
            linea = json.loads((raiz / "salida" / "concepto" / "linea_de_tiempo.json").read_text("utf-8"))
            return sim, linea

    def test_video_y_subtitulos_usan_el_mismo_tema_compuesto(self):
        from tpi_videos.config import cargar_marca
        from tpi_videos.render import subtitulos_de
        from tpi_videos.temas import cargar_tema

        datos = datos_concepto()  # panel: false sobre consola_pasos (que lo trae encendido)
        sim, linea = self._correr(datos)
        tema = sim.temas[0]
        self.assertFalse(tema.gramatica.panel)
        self.assertEqual(sim.estilos_ass[0], subtitulos_de(tema))
        base = cargar_tema("consola_pasos", cargar_marca())
        self.assertTrue(base.gramatica.panel)  # el tema cargado no se tocó
        self.assertEqual(linea["tema_clave"], "consola_pasos")
        claves = [d["clave"] for d in sim.didacticas[0]]
        self.assertEqual(claves, ["tabs", "panel", "mapa_color", "micro"])
        panel = sim.didacticas[0][1]
        self.assertEqual((panel["activo"], panel["sugerido"], panel["origen"]), (False, True, "guion"))

    def test_heredado_recibe_el_tema_tal_cual(self):
        from tpi_videos.config import cargar_marca
        from tpi_videos.temas import cargar_tema

        sim, _ = self._correr(datos_base())
        self.assertEqual(sim.temas[0], cargar_tema("consola_pasos", cargar_marca()))
        self.assertIsNone(sim.didacticas[0])

    def test_clip_de_gancho_compone_y_conserva_voz_del_guion(self):
        from tpi_videos import render

        datos = datos_concepto()
        datos["recursos"] = {"panel": True}
        datos["tema"] = "consola_mito"
        datos["voz"] = "es-CL-LorenzoNeural"
        datos["velocidad"] = "+7%"
        g = Guion.model_validate(datos)
        with TemporaryDirectory() as carpeta, patch.dict(os.environ, {"TPI_RAIZ": carpeta}):
            sim = _Simulado(Path(carpeta))
            with (
                patch("tpi_videos.render.renderizar_manim", side_effect=sim.renderizar),
                patch("tpi_videos.render.verificar_requisitos"),
            ):
                render.crear_clip_gancho(g, salida=Path(carpeta) / "g" / "gancho.mp4")
        self.assertTrue(sim.temas[0].gramatica.panel)
        self.assertEqual(sim.temas[0].layout.banda_panel, 1.6)
        self.assertEqual(sim.voces[1:3], ("es-CL-LorenzoNeural", "+7%"))
        self.assertTrue(sim.didacticas[0][1]["activo"])


if __name__ == "__main__":
    unittest.main()
