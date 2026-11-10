"""El tiempo de lectura no es contenido de más: no puede hacer que el video «se pasó» de lo prometido.

El piso de lectura suma silencio al final del render, en el bloque de la fórmula. Si la promesa se
compara contra la duración bruta, un video correcto sale con ⚠️ y el panel le echa la culpa a la IA.
Estas pruebas fijan que lo que el motor esperó para que se pueda leer no se le cobra a nadie.
"""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tpi_videos.panel.sugerencia import clause_lectura
from tpi_videos.redactor import problemas_de_formato, promesa_incumplida

from .test_ritmo import _guion


class PromesaConLecturaTest(unittest.TestCase):
    def test_sin_lectura_se_compara_como_antes(self):
        self.assertTrue(promesa_incumplida(39.0, 30))
        self.assertFalse(promesa_incumplida(38.0, 30))

    def test_el_silencio_de_lectura_no_cuenta_como_exceso(self):
        self.assertTrue(promesa_incumplida(42.1, 30), "sin perdonar la lectura, el alerta es falso")
        self.assertFalse(promesa_incumplida(42.1, 30, lectura=9.6))

    def test_un_video_que_de_verdad_se_paso_si_se_avisa(self):
        self.assertTrue(promesa_incumplida(70.0, 30, lectura=9.6))

    def test_sin_promesa_no_hay_comparacion(self):
        self.assertFalse(promesa_incumplida(99.0, None, lectura=9.6))


class FraseDeLecturaTest(unittest.TestCase):
    def test_la_clause_dice_cuanto_fue_de_lectura(self):
        self.assertEqual(clause_lectura(9.6), " · 9,6 s fueron de lectura")

    def test_sin_espera_no_hay_clause_que_mostrar(self):
        self.assertEqual(clause_lectura(0.0), "")
        self.assertEqual(clause_lectura(0.04), "", "las centésimas del corte de cuadro no se muestran")


def _problema_de_duracion(guion, prometido):
    return [p for p in problemas_de_formato(guion, prometido) if p.startswith("duración:")]


class AchicaloSinLecturaTest(unittest.TestCase):
    """La orden de achicar que recibe Gemini antes del render tampoco puede cobrarle el silencio.

    La estimación ``rev.segundos`` es solo voz: el piso de lectura se suma después, en el render. Si la
    orden dice «achicalo a 30 s» sin decirlo, la IA recorta pasos para compensar segundos que todavía
    no existen, y el video pierde explicación para ganar un número que igual se supera.
    """

    paso = {"voz": "Factorizo la equis.", "tex": "x (x - 5) = 0"}

    def test_un_guion_cuya_voz_cabe_en_la_promesa_no_recibe_orden(self):
        self.assertEqual(
            _problema_de_duracion(_guion([self.paso] * 12), 30), [], "la voz cabe; la lectura se suma aparte"
        )

    def test_un_guion_demasiado_largo_de_voz_si_recibe_la_orden(self):
        self.assertEqual(len(_problema_de_duracion(_guion([self.paso] * 4), 10)), 1)

    def test_la_orden_dice_que_el_tiempo_de_lectura_no_se_achica(self):
        orden = _problema_de_duracion(_guion([self.paso] * 4), 10)[0]
        self.assertIn("cuentan aparte", orden, "la IA debe saber que esos segundos no son su culpa")
        self.assertIn("10,0 s", orden, "dice cuántos segundos de lectura se suman")


class CmdCrearLecturaTest(unittest.TestCase):
    """«rehacer con otro estilo» del panel corre ``tpi crear``: su JSON también lleva la lectura.

    Sin este número el panel muestra la duración sola y quien mira no puede saber si el video se pasó
    de lo prometido o si fueron los segundos que la fórmula necesitaba para leerse.
    """

    def test_el_json_de_crear_lleva_los_segundos_de_lectura(self) -> None:
        from tpi_videos.cli import cmd_crear, construir_parser
        from tpi_videos.render import ResultadoVideo

        args = construir_parser().parse_args(["crear", "guiones/demo.yaml", "--progreso-json"])
        carpeta = Path("guiones")
        salida = ResultadoVideo(
            video=carpeta / "demo.mp4",
            carpeta=carpeta,
            duracion=42.1,
            lectura=12.8,
            segundos_proceso=1.0,
            tema="Hoja de desarrollo",
        )
        consola = io.StringIO()
        with (
            patch("tpi_videos.render.crear_video", return_value=salida),
            patch("tpi_videos.cli._mostrar_revision"),
            redirect_stdout(consola),
        ):
            cmd_crear(args)

        eventos = [json.loads(linea) for linea in consola.getvalue().splitlines() if linea.startswith("{")]
        resultado = next(e for e in eventos if e.get("etapa") == "resultado")
        self.assertEqual(resultado["lectura"], 12.8, "el rehacer del panel también dice la lectura")


class TechoDelPerdonTest(unittest.TestCase):
    """Perdonar toda la lectura sin límite dejaría una tarjeta de «≈15 s» convertido en 60 s.

    Con doce fórmulas el piso pide ~27 s de silencio: si todos cuentan, el ⚠️ nunca sale y quien mira
    recibe el triple de lo que le prometieron. El perdón se corta en TECHO_DE_LECTURA.
    """

    def test_el_perdon_de_lectura_tiene_techo(self):
        self.assertTrue(
            promesa_incumplida(51.0, 30, lectura=27.0),
            "27 s de lectura no compran 27 s de permiso: el techo es 12 s",
        )

    def test_el_video_real_de_42_s_sigue_estando_cumplido(self):
        self.assertFalse(promesa_incumplida(42.1, 30, lectura=12.8), "el caso medido en el render no se avisa")

    def test_bajo_el_techo_la_lectura_se_perdona_toda(self):
        self.assertFalse(promesa_incumplida(47.0, 30, lectura=10.0))
        self.assertTrue(promesa_incumplida(49.0, 30, lectura=10.0))


if __name__ == "__main__":
    unittest.main()
