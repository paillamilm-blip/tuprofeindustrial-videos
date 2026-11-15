"""Regresión: la fuente de los subtítulos debe cargar aunque el video se renderice fuera del repo.

Antes, ``_carpeta_fuentes_relativa`` devolvía una ruta relativa con ``../`` que se salía del repo;
libass no la resolvía y sustituía Montserrat Black por la fuente del sistema (Helvetica) sin avisar.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tpi_videos import entorno, postproduccion

ASS_PRUEBA = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CapCut,Montserrat Black,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,6.0,2.0,5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,CapCut,,0,0,0,,PRUEBA
"""


class TestFuentesSubtitulos(unittest.TestCase):
    def test_fontsdir_fuera_del_repo_no_se_sale_con_puntos(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            fuentes = postproduccion._carpeta_fuentes(carpeta)
            self.assertFalse(fuentes.startswith(".."), f"ruta relativa que se sale del repo: {fuentes}")
            resuelta = (carpeta / fuentes).resolve()
            self.assertTrue(resuelta.is_dir(), f"fontsdir no resuelve a una carpeta: {resuelta}")
            self.assertTrue((resuelta / "Montserrat-Black.ttf").exists(), f"falta la fuente en {resuelta}")

    def test_libass_carga_montserrat_desde_fuera_del_repo(self):
        ffmpeg = entorno.ffmpeg_con_libass()
        if ffmpeg is None:
            self.skipTest("FFmpeg con libass no disponible")
        # /tmp en Mac es symlink a /private/tmp: los "../" de la ruta relativa se resuelven contra la
        # ruta real y caen fuera del repo -> libass no carga la fuente. Ahí se reproduce el bug.
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            carpeta = Path(tmp) / "a" / "b" / "c"
            carpeta.mkdir(parents=True)
            (carpeta / "p.ass").write_text(ASS_PRUEBA, encoding="utf-8")
            fuentes = postproduccion._carpeta_fuentes(carpeta)
            proceso = subprocess.run(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "debug",
                    "-f", "lavfi", "-i", "color=c=black:s=200x200:d=1",
                    "-vf", f"ass=p.ass:fontsdir={fuentes}",
                    "-frames:v", "1", "-y", str(carpeta / "out.png"),
                ],
                cwd=carpeta, capture_output=True, text=True,
            )
            self.assertEqual(proceso.returncode, 0, proceso.stderr[-500:])
            seleccion = [l for l in proceso.stderr.splitlines() if "fontselect" in l]
            self.assertTrue(seleccion, "libass no reportó fontselect")
            self.assertTrue(
                any("Montserrat" in l for l in seleccion),
                f"libass sustituyó la fuente (cayó al sistema): {seleccion}",
            )


class TestFuentesRuidoso(unittest.TestCase):
    def test_registro_fallido_es_error_no_silencio(self):
        from unittest.mock import patch

        from tpi_videos.errores import ErrorMotor

        with patch.object(entorno, "registrar_fuentes", return_value=False):
            with self.assertRaises(ErrorMotor):
                entorno.exigir_fuentes()

    def test_registro_ok_no_falla(self):
        from unittest.mock import patch

        with patch.object(entorno, "registrar_fuentes", return_value=True):
            entorno.exigir_fuentes()  # no debe lanzar


class TestSondaDoctor(unittest.TestCase):
    def test_sonda_confirma_fuente_incluida(self):
        if entorno.ffmpeg_con_libass() is None:
            self.skipTest("FFmpeg con libass no disponible")
        ok, detalle = postproduccion.fuente_subtitulos_ok()
        self.assertTrue(ok, detalle)
        self.assertIn("Montserrat", detalle)


if __name__ == "__main__":
    unittest.main()