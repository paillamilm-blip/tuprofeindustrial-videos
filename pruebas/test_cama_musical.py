"""La cama musical: un bucle ambiental libre de derechos que tapa el aire muerto bajo la voz."""

import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from tpi_videos import entorno, musica
from tpi_videos.config import CALIDADES
from tpi_videos.postproduccion import quemar_subtitulos, recodificar

FFMPEG = entorno.ffmpeg_cualquiera()
FFMPEG_ASS = entorno.ffmpeg_con_libass()

_ASS_MINIMO = """[Script Info]
ScriptType: v4.00+
PlayResX: 64
PlayResY: 64

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,10,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,hola
"""


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x * x)))


class BucleTest(unittest.TestCase):
    def test_el_bucle_dura_lo_pedido_y_no_es_silencio(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = musica.bucle_cama(Path(tmp) / "cama.wav", segundos=4.0)
            with wave.open(str(ruta), "rb") as w:
                self.assertAlmostEqual(w.getnframes() / w.getframerate(), 4.0, delta=0.05)
                x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768
            self.assertGreater(_rms(x), 0.01)

    def test_el_bucle_empalma_sin_salto(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = musica.bucle_cama(Path(tmp) / "cama.wav", segundos=4.0)
            with wave.open(str(ruta), "rb") as w:
                x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768
            self.assertLess(abs(float(x[-1]) - float(x[0])), 0.05)

    def test_el_bucle_no_tiene_huecos_silenciosos(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = musica.bucle_cama(Path(tmp) / "cama.wav", segundos=4.0)
            with wave.open(str(ruta), "rb") as w:
                sr = w.getframerate()
                x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768
            ventana = int(0.1 * sr)
            minimos = [_rms(x[i:i + ventana]) for i in range(0, len(x) - ventana, ventana)]
            self.assertGreater(min(minimos), 0.005)


def _video_con_hueco(destino: Path) -> Path:
    """Un MP4 de prueba cuya voz tiene un silencio de 2 s en el medio (el «aire muerto» del autor)."""
    sr = 48000
    t = np.arange(sr) / sr
    tono = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio = np.concatenate([tono, np.zeros(2 * sr), tono])
    wav = destino.parent / "voz_con_hueco.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    subprocess.run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4:r=10",
         "-i", str(wav), "-c:v", "mpeg4", "-q:v", "2", "-c:a", "aac", "-shortest", str(destino)],
        check=True, capture_output=True,
    )
    return destino


def _tiene_silencio_largo(video: Path) -> bool:
    p = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(video), "-af", "silencedetect=n=-35dB:d=0.6", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return "silence_start" in p.stderr


@unittest.skipUnless(FFMPEG, "ffmpeg no esta instalado")
class MezclaTest(unittest.TestCase):
    def test_recodificar_con_cama_no_deja_aire_muerto(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            entrada = _video_con_hueco(tmp / "entrada.mp4")
            self.assertTrue(_tiene_silencio_largo(entrada), "el video de prueba debe traer el hueco")
            cama = musica.bucle_cama(tmp / "cama.wav")
            salida = recodificar(entrada, tmp / "salida.mp4", CALIDADES["borrador"], cama=cama)
            self.assertFalse(_tiene_silencio_largo(salida), "la cama debe tapar el silencio de 2 s")

    def test_sin_cama_el_hueco_sigue_como_antes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            entrada = _video_con_hueco(tmp / "entrada.mp4")
            salida = recodificar(entrada, tmp / "salida.mp4", CALIDADES["borrador"])
            self.assertTrue(_tiene_silencio_largo(salida), "sin cama el comportamiento no cambia")

    def test_recodificar_con_resplandor_y_cama_no_deja_aire_muerto(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            entrada = _video_con_hueco(tmp / "entrada.mp4")
            cama = musica.bucle_cama(tmp / "cama.wav")
            salida = recodificar(entrada, tmp / "salida.mp4", CALIDADES["borrador"], True, cama=cama)
            self.assertFalse(_tiene_silencio_largo(salida))


@unittest.skipUnless(FFMPEG_ASS, "ffmpeg con libass no esta instalado")
class SubtitulosConCamaTest(unittest.TestCase):
    def test_quemar_subtitulos_con_cama_no_deja_aire_muerto(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            entrada = _video_con_hueco(tmp / "entrada.mp4")
            ass = tmp / "subtitulos.ass"
            ass.write_text(_ASS_MINIMO, encoding="utf-8")
            cama = musica.bucle_cama(tmp / "cama.wav")
            salida = quemar_subtitulos(entrada, ass, tmp / "salida.mp4", CALIDADES["borrador"], cama=cama)
            self.assertTrue(salida.exists())
            self.assertFalse(_tiene_silencio_largo(salida), "la cama debe tapar el hueco también con subtítulos")


if __name__ == "__main__":
    unittest.main()