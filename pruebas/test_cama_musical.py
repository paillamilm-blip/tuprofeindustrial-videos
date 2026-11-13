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


class MusicaNoZumbidoTest(unittest.TestCase):
    """La cama es música (acordes que cambian y notas que suenan), no un zumbido fijo."""

    def _muestras(self, segundos=16.0):
        import tempfile
        import wave

        import numpy as np

        from tpi_videos import musica

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = musica.bucle_cama(Path(carpeta) / "cama.wav", segundos)
            with wave.open(str(ruta)) as w:
                fr = w.getframerate()
                x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        return x, fr

    def _espectro(self, trozo, fr):
        import numpy as np

        e = np.abs(np.fft.rfft(trozo * np.hanning(len(trozo))))
        f = np.fft.rfftfreq(len(trozo), 1 / fr)
        banda = (f > 60) & (f < 1200)
        e = e[banda]
        return e / (np.linalg.norm(e) or 1)

    def test_los_acordes_cambian_en_el_bucle(self):
        import numpy as np

        x, fr = self._muestras()
        cuartos = np.array_split(x, 4)
        espectros = [self._espectro(c, fr) for c in cuartos]
        parecidos = [float(espectros[i] @ espectros[i + 1]) for i in range(3)]
        self.assertLess(max(parecidos), 0.9, f"los 4 tramos suenan casi igual: {parecidos}")

    def test_hay_notas_que_empiezan(self):
        """Un arpegio: el volumen sube de golpe varias veces por segundo (ataques de nota)."""
        import numpy as np

        x, fr = self._muestras()
        paso = int(0.02 * fr)
        rms = np.sqrt(np.add.reduceat(x**2, np.arange(0, len(x), paso)) / paso)
        ataques = int(np.sum(np.diff(rms) > 0.15 * rms.max()))
        self.assertGreater(ataques, 16)

    def test_la_musica_no_pasa_por_encima_de_la_voz(self):
        """Lo grave y lo medio-bajo: casi nada de energía donde vive la claridad de la voz (2–4 kHz)."""
        import numpy as np

        x, fr = self._muestras()
        e = np.abs(np.fft.rfft(x)) ** 2
        f = np.fft.rfftfreq(len(x), 1 / fr)
        self.assertLess(e[(f > 2000) & (f < 4000)].sum() / e.sum(), 0.02)


class MezclaQueSeApartaTest(unittest.TestCase):
    """Mientras habla la voz la música baja; en las pausas vuelve a su volumen."""

    def test_la_cama_baja_bajo_la_voz(self):
        from tpi_videos import postproduccion

        cadena = postproduccion._argumentos_cama(Path("/tmp/c.wav"), 0.18)
        filtro = cadena[cadena.index("-filter_complex") + 1]
        self.assertIn("sidechaincompress", filtro)
        self.assertIn("asplit", filtro)


class MusicaLofiTest(unittest.TestCase):
    """Lofi jazz hip hop: acordes de jazz, batería con swing y el crujido del vinilo."""

    def _lofi(self, segundos=None):
        from tpi_videos import musica

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = musica.bucle_cama(Path(carpeta) / "lofi.wav", segundos, estilo="lofi")
            with wave.open(str(ruta)) as w:
                fr = w.getframerate()
                x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        return x, fr

    def test_bucle_de_cuatro_compases_a_tempo_lofi(self):
        from tpi_videos import musica

        x, fr = self._lofi()
        self.assertAlmostEqual(len(x) / fr, 16 * 60 / musica.PULSO_LOFI, delta=0.05)
        self.assertGreater(_rms(x), 0.02)

    def test_empalma_sin_salto(self):
        x, _ = self._lofi()
        self.assertLess(abs(x[-1] - x[0]), 0.05)

    def test_hay_bombo_y_caja(self):
        """Graves fuertes en los tiempos 1 y 3 (bombo) y golpes de ruido en 2 y 4 (caja)."""
        from tpi_videos import musica

        x, fr = self._lofi()
        tiempo = 60 / musica.PULSO_LOFI
        graves = np.fft.irfft(np.fft.rfft(x) * (np.fft.rfftfreq(len(x), 1 / fr) < 120), n=len(x))

        def energia(t):
            i = int(t * fr)
            return float(np.sqrt(np.mean(graves[i : i + int(0.08 * fr)] ** 2)))

        en_bombo = np.mean([energia(c * 4 * tiempo) for c in range(4)])
        entre = np.mean([energia(c * 4 * tiempo + 0.5 * tiempo) for c in range(4)])
        self.assertGreater(en_bombo, 2 * entre)

    def test_suena_distinto_de_la_musica_suave(self):
        from tpi_videos import musica

        suave = musica.componer(4.0)
        lofi = musica.componer(4.0, estilo="lofi")
        self.assertFalse(np.allclose(suave[: len(lofi)], lofi[: len(suave)]))

    def test_estilo_desconocido_avisa(self):
        from tpi_videos import musica
        from tpi_videos.errores import ErrorMotor

        with tempfile.TemporaryDirectory() as carpeta, self.assertRaises(ErrorMotor):
            musica.bucle_cama(Path(carpeta) / "x.wav", estilo="reggaeton")


class MusicaEnLaTerminalTest(unittest.TestCase):
    def test_crear_acepta_musica(self):
        from tpi_videos import cli

        args = cli.construir_parser().parse_args(["crear", "g.yaml", "--musica", "lofi"])
        self.assertEqual(args.musica, "lofi")
        args = cli.construir_parser().parse_args(["crear", "g.yaml"])
        self.assertIsNone(args.musica)

    def test_marca_trae_estilo_suave_por_defecto(self):
        from tpi_videos.config import Cama

        self.assertEqual(Cama().estilo, "suave")
        self.assertEqual(Cama(estilo="lofi").estilo, "lofi")
