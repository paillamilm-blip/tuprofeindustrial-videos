"""Lo que se arregló el 13-11-2026 al revisar videos de verdad, cuadro a cuadro.

- El tamaño del dibujo se puede elegir (``tamano``): el motor solo achicaba, nunca agrandaba.
- La torta y las barras repetían color en la familia Consola (el acento era igual a «cuadricula»):
  dos porciones se leían como un solo disco.
- «°» y «·» dentro de una fórmula botaban el video con un LaTeX mínimo (BasicTeX).
- Escribir a medias un guion, el kit o la clave ya no deja el archivo roto.
- Un comando del panel que se cae sin avisar ya no se anuncia como éxito.
- Cambiar el dibujo con la IA no borra lo que el profe editó mientras tanto.
- La voz de Gemini sin clave avisa antes de animar, no a mitad del video.
"""

import asyncio
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos.entorno import escribir_atomico
from tpi_videos.errores import ErrorMotor
from tpi_videos.guion import Guion, Visual, a_yaml, cargar_guion
from tpi_videos.temas import DISTANCIA_MINIMA, _distancia, colores_distintos
from tpi_videos.tex import corregir_decimales

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "guiones" / "caben_ocho_cubos.yaml"
TEMAS = ("consola_pasos", "consola_error", "consola_mito", "consola_dato", "consola_reto")

try:
    import manim  # noqa: F401

    HAY_MANIM = True
except ImportError:
    HAY_MANIM = False


class TamanoDelDibujoTest(unittest.TestCase):
    def test_el_guion_acepta_el_tamano_y_lo_escribe_solo_si_no_es_auto(self) -> None:
        datos = cargar_guion(GUION).model_dump()
        i = next(n for n, p in enumerate(datos["pasos"]) if p.get("visual"))
        self.assertNotIn("tamano:", a_yaml(datos))
        datos["pasos"][i]["visual"]["tamano"] = "grande"
        texto = a_yaml(datos)
        self.assertIn("tamano: grande", texto)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "g.yaml"
            ruta.write_text(texto, encoding="utf-8")
            self.assertEqual(cargar_guion(ruta).pasos[i].visual.tamano, "grande")

    def test_un_tamano_inventado_no_vale(self) -> None:
        with self.assertRaises(ValueError):
            Visual.model_validate({"tipo": "torta", "categorias": ["A 1", "B 2"], "tamano": "enorme"})

    @unittest.skipUnless(HAY_MANIM, "necesita Manim")
    def test_el_encaje_agranda_solo_si_se_pide(self) -> None:
        from tpi_videos.dibujos import _relleno, factor_de_encaje

        self.assertEqual(factor_de_encaje(1.0, 1.0, 4.0, 4.0), 1.0)  # auto: no agranda
        self.assertAlmostEqual(factor_de_encaje(8.0, 2.0, 4.0, 4.0), 0.5)  # auto: achica lo que no cabe
        marca = _relleno.set(1.0)
        try:
            self.assertAlmostEqual(factor_de_encaje(1.0, 1.0, 4.0, 4.0), 4.0)  # grande: llena la tarjeta
        finally:
            _relleno.reset(marca)
        marca = _relleno.set(0.6)
        try:
            self.assertAlmostEqual(factor_de_encaje(8.0, 2.0, 4.0, 4.0), 0.3)
        finally:
            _relleno.reset(marca)

    @unittest.skipUnless(HAY_MANIM, "necesita Manim")
    def test_las_barras_grandes_ocupan_mas_que_las_automaticas(self) -> None:
        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos import dibujar_visual
        from tpi_videos.temas import cargar_tema

        col = cargar_tema("consola_pasos", cargar_marca()).colores
        medidas = {}
        for tam in ("auto", "chico", "grande"):
            v = Visual.model_validate({"tipo": "barras", "categorias": ["A 1", "B 2"], "tamano": tam})
            medidas[tam] = dibujar_visual(v, col, 6.0, 3.0).mobs.height
        self.assertGreater(medidas["grande"], medidas["auto"])
        self.assertLess(medidas["chico"], medidas["grande"])
        self.assertLessEqual(medidas["grande"], 3.0 + 1e-6)  # nunca se sale de su tarjeta


class ColoresQueSeDistinguenTest(unittest.TestCase):
    def test_ninguna_variante_repite_el_acento_en_el_segundo_color(self) -> None:
        from tpi_videos.config import cargar_marca
        from tpi_videos.temas import cargar_tema

        for clave in TEMAS:
            c = cargar_tema(clave, cargar_marca()).colores
            self.assertGreaterEqual(_distancia(c.acento, c.cuadricula), DISTANCIA_MINIMA, clave)

    @unittest.skipUnless(HAY_MANIM, "necesita Manim")
    def test_la_paleta_de_la_torta_no_repite_colores(self) -> None:
        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos import _paleta
        from tpi_videos.temas import cargar_tema

        for clave in TEMAS:
            paleta = _paleta(cargar_tema(clave, cargar_marca()).colores)
            self.assertGreaterEqual(len(paleta), 4, clave)
            for i, a in enumerate(paleta):
                for b in paleta[i + 1 :]:
                    self.assertGreaterEqual(_distancia(a, b), DISTANCIA_MINIMA, (clave, a, b))

    def test_colores_distintos_completa_con_la_familia(self) -> None:
        salida = colores_distintos(["#7DB894", "#7DB894", "#7DB894"])
        self.assertEqual(len(salida), 3)
        self.assertEqual(salida[0], "#7DB894")
        self.assertEqual(len(set(salida)), 3)


class SignosEnLasFormulasTest(unittest.TestCase):
    def test_los_signos_pegados_pasan_a_su_comando(self) -> None:
        self.assertEqual(corregir_decimales(r"\theta = 30°"), r"\theta = 30\ensuremath{^{\circ}}")
        self.assertIn(r"\ensuremath{\cdot}", corregir_decimales(r"8\ \text{N·s/m}"))
        self.assertEqual(corregir_decimales("9,8"), "9{,}8")  # la coma decimal sigue igual

    @unittest.skipUnless(HAY_MANIM and shutil.which("latex"), "necesita Manim y LaTeX")
    def test_una_formula_con_grados_se_dibuja(self) -> None:
        from tpi_videos import componentes as c

        eq = c.ecuacion(r"\theta = 30°")
        self.assertGreater(eq.width, 0)
        self.assertTrue(c.partes_por_tex(eq, "30°") or c.partes_por_tex(eq, r"\theta"))


class EscrituraAtomicaTest(unittest.TestCase):
    def test_si_falla_a_mitad_el_archivo_queda_como_estaba(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "guion.yaml"
            ruta.write_text("lo de antes", encoding="utf-8")
            with patch("os.replace", side_effect=OSError("disco lleno")), self.assertRaises(OSError):
                escribir_atomico(ruta, "lo nuevo")
            self.assertEqual(ruta.read_text(encoding="utf-8"), "lo de antes")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["guion.yaml"])  # sin temporales

    @unittest.skipIf(os.name == "nt", "los permisos de Unix no aplican en Windows")
    def test_la_clave_nace_privada(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = escribir_atomico(Path(tmp) / ".env", "GEMINI_API_KEY=x\n", permisos=0o600)
            self.assertEqual(stat.S_IMODE(ruta.stat().st_mode), 0o600)
            otro = escribir_atomico(Path(tmp) / "g.yaml", "x")
            self.assertEqual(stat.S_IMODE(otro.stat().st_mode), 0o644)


class ComandoQueSeCaeTest(unittest.TestCase):
    def test_un_comando_que_termina_mal_no_se_anuncia_como_exito(self) -> None:
        from tpi_videos.panel.tareas import consultar

        with self.assertRaises(ErrorMotor):  # argparse sale con código 2 y sin evento de error
            asyncio.run(consultar(["redibujar", "--opcion-que-no-existe"], segundos=60))


class RedibujarSinPerderCambiosTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        (raiz / "guiones").mkdir()
        self.ruta = raiz / "guiones" / "cubos.yaml"
        shutil.copy(GUION, self.ruta)
        # El guion del repo ya dibuja en todos sus pasos; acá se necesita uno sin dibujo para probar el aviso.
        guion = cargar_guion(self.ruta)
        guion.pasos[-1].visual = None
        escribir_atomico(self.ruta, a_yaml(guion.model_dump()))
        entorno = patch.dict(os.environ, {"TPI_RAIZ": str(raiz)})
        entorno.start()
        self.addCleanup(entorno.stop)

    def test_lo_editado_mientras_la_ia_trabaja_se_conserva_y_el_tamano_tambien(self) -> None:
        from tpi_videos.panel import estudio
        from tpi_videos.redactor import PasoIA, redibujar_paso

        g = cargar_guion(self.ruta)
        n = next(k for k, p in enumerate(g.pasos, 1) if p.visual is not None)
        estudio.cambiar_tamano(self.ruta, n, "grande")

        def la_ia(*_a, **_k):
            estudio.cambiar_cierre(self.ruta, "Ahora lo sabes")  # el profe edita mientras tanto
            return PasoIA(nota="x", tex="x", voz="x", dibujo="grafico", funcion="x^3", rango=[0, 3])

        with (
            patch("tpi_videos.redactor.ia.cliente", return_value=object()),
            patch("tpi_videos.redactor.pedir_json", side_effect=la_ia),
        ):
            redibujar_paso(self.ruta, n, "grafico")
        final = cargar_guion(self.ruta)
        self.assertEqual(final.cierre.texto, "Ahora lo sabes")
        self.assertEqual(final.pasos[n - 1].visual.tipo, "grafico_funcion")
        self.assertEqual(final.pasos[n - 1].visual.tamano, "grande")

    def test_el_tamano_se_cambia_desde_el_estudio(self) -> None:
        from tpi_videos.panel import estudio

        g = cargar_guion(self.ruta)
        con = next(k for k, p in enumerate(g.pasos, 1) if p.visual is not None)
        sin = next(k for k, p in enumerate(g.pasos, 1) if p.visual is None)
        self.assertEqual(
            estudio.cambiar_tamano(self.ruta, con, "chico").pasos[con - 1].visual.tamano, "chico"
        )
        with self.assertRaises(ErrorMotor):
            estudio.cambiar_tamano(self.ruta, sin, "chico")
        with self.assertRaises(ErrorMotor):
            estudio.cambiar_tamano(self.ruta, con, "gigante")


class VozSinClaveTest(unittest.TestCase):
    def test_gemini_sin_clave_avisa_antes_de_animar(self) -> None:
        from tpi_videos.render import verificar_voz

        with patch("tpi_videos.ia.obtener_clave", return_value=None):
            with self.assertRaises(ErrorMotor) as caso:
                verificar_voz("gemini", "Charon")
            self.assertIn("--voz edge", caso.exception.ayuda)
            verificar_voz("edge", "es-CL-LorenzoNeural")  # las otras voces no piden clave
            verificar_voz("gemini", "silencio")


class TikTokConAvisoTest(unittest.TestCase):
    def test_el_texto_con_el_aviso_no_pasa_de_150_y_el_llamado_no_se_repite(self) -> None:
        from tpi_videos.publicar import _limpiar, aplicar_llamado, textos_de_plantilla

        g = cargar_guion(GUION)
        llamado = "¿Tú también lo creías? Cuéntame 👇"
        largo = textos_de_plantilla(g).model_copy(update={"texto_tiktok": f"{'palabra ' * 30}{llamado}"})
        t = _limpiar(aplicar_llamado(largo, llamado))
        self.assertLessEqual(len(t.texto_tiktok), 150)
        self.assertEqual(t.texto_tiktok.count(llamado), 1)
        self.assertIn("Creado con IA.", t.texto_tiktok)


class GuionValidoTest(unittest.TestCase):
    def test_el_guion_de_ejemplo_sigue_valido(self) -> None:
        Guion.model_validate(cargar_guion(GUION).model_dump())


if __name__ == "__main__":
    unittest.main()
