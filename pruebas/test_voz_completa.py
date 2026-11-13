"""La voz de un video entero en un solo pedido, cortada por sus silencios en un trozo por frase."""

import io
import unittest
import wave

import numpy as np

from tpi_videos.voz_completa import cortar, wav_de

SR = 24_000


def _tono(segundos, f=180.0):
    t = np.arange(int(segundos * SR)) / SR
    # sílabas: el volumen sube y baja 4 veces por segundo, con micro-silencios cortos (como al hablar)
    envolvente = (np.sin(2 * np.pi * 4 * t) > -0.6).astype(float)
    return 0.4 * np.sin(2 * np.pi * f * t) * envolvente


def _silencio(segundos):
    return np.zeros(int(segundos * SR))


def _wav(muestras):
    datos = (np.clip(muestras, -1, 1) * 32767).astype(np.int16).tobytes()
    salida = io.BytesIO()
    with wave.open(salida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(datos)
    return salida.getvalue()


def _duracion(wav):
    with wave.open(io.BytesIO(wav), "rb") as w:
        return w.getnframes() / w.getframerate()


TEXTOS = ["Hola a todos.", "Hoy vemos por qué el volumen crece ocho veces.", "Sígueme."]


class CortarTest(unittest.TestCase):
    def _audio_de_tres(self, pausas=0.7):
        partes = [_silencio(0.2), _tono(0.9), _silencio(pausas), _tono(3.2), _silencio(pausas), _tono(0.6),
                  _silencio(0.3)]  # fmt: skip
        return _wav(np.concatenate(partes))

    def test_tres_frases_quedan_en_tres_trozos_con_su_duracion(self):
        trozos = cortar(self._audio_de_tres(), TEXTOS)
        self.assertEqual(len(trozos), 3)
        duraciones = [_duracion(t) for t in trozos]
        for real, esperado in zip(duraciones, (0.9, 3.2, 0.6), strict=True):
            self.assertAlmostEqual(real, esperado, delta=0.35)

    def test_los_trozos_suman_el_audio_sin_perder_voz(self):
        audio = self._audio_de_tres()
        trozos = cortar(audio, TEXTOS)
        self.assertLessEqual(sum(_duracion(t) for t in trozos), _duracion(audio) + 1e-6)
        self.assertGreater(sum(_duracion(t) for t in trozos), 4.7 - 0.3)

    def test_sin_silencios_claros_no_corta_a_ciegas(self):
        audio = _wav(_tono(5.0))
        self.assertIsNone(cortar(audio, TEXTOS))

    def test_una_sola_frase_es_el_audio_entero(self):
        audio = _wav(np.concatenate([_tono(1.0), _silencio(0.4)]))
        self.assertEqual(len(cortar(audio, ["Una sola frase."])), 1)

    def test_audio_roto_no_revienta(self):
        self.assertIsNone(cortar(b"no es un wav", TEXTOS))

    def test_wav_de_conserva_formato(self):
        muestras = (_tono(0.5) * 32767).astype(np.int16)
        with wave.open(io.BytesIO(wav_de(muestras, SR)), "rb") as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, SR))


class ClienteContador:
    """Imita al SDK: cuenta pedidos y devuelve un audio con un tono por párrafo pedido."""

    def __init__(self, con_silencios=True):
        self.pedidos = []
        self.con_silencios = con_silencios
        self.interactions = self

    def create(self, **kw):
        import base64

        texto = kw["input"][0]["content"][0]["text"]
        self.pedidos.append(texto)
        parrafos = [p for p in texto.split("\n\n") if p.strip()]
        partes = [_silencio(0.2)]
        for p in parrafos:
            partes += [_tono(0.4 + 0.05 * len(p)), _silencio(0.7 if self.con_silencios else 0.0)]
        datos = base64.b64encode(_wav(np.concatenate(partes))).decode()
        return type("R", (), {"output_audio": type("A", (), {"data": datos})()})()


class PrecargaGeminiTest(unittest.TestCase):
    def setUp(self):
        try:
            from tpi_videos import voces
        except ModuleNotFoundError:
            self.skipTest("manim no está instalado")
        import tempfile

        self.voces = voces
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _servicio(self, cliente):
        base = self.voces.GeminiTTSService(voz="Charon", estilo="Profe", cliente=cliente, cache_dir=self.tmp.name)
        return self.voces.ServicioConPausas(base, "gemini-tts", cache_dir=self.tmp.name)

    def test_un_solo_pedido_para_todo_el_guion(self):
        cliente = ClienteContador()
        servicio = self._servicio(cliente)
        voces = ["¿Cuánto vale?", 'Primero llenamos el cubo. <break time="1s"/> Caben ocho.', "Sígueme."]
        self.assertTrue(self.voces.precargar_voz(servicio, voces))
        self.assertEqual(len(cliente.pedidos), 1)
        for v in voces:  # lo que pide la escena después: todo sale de la caché, sin otro pedido
            datos = servicio._wrap_generate_from_text(v)
            self.assertTrue((Path(self.tmp.name) / datos["original_audio"]).exists())
        self.assertEqual(len(cliente.pedidos), 1)
        self.assertIn("Caben ocho.", cliente.pedidos[0])

    def test_sin_silencios_vuelve_a_frase_por_frase(self):
        cliente = ClienteContador(con_silencios=False)
        servicio = self._servicio(cliente)
        voces = ["¿Cuánto vale?", "Primero llenamos el cubo.", "Sígueme."]
        self.assertFalse(self.voces.precargar_voz(servicio, voces))
        for v in voces:
            servicio._wrap_generate_from_text(v)
        self.assertEqual(len(cliente.pedidos), 1 + len(voces))  # el intento completo + una por frase

    def test_si_el_pedido_completo_falla_sigue_frase_por_frase(self):
        from tpi_videos.errores import ErrorMotor

        class Falla(ClienteContador):
            def create(self, **kw):
                if not self.pedidos:
                    self.pedidos.append("falló")
                    raise ErrorMotor("Gemini no respondió.", transitorio=True)
                return super().create(**kw)

        cliente = Falla()
        servicio = self._servicio(cliente)
        self.assertFalse(self.voces.precargar_voz(servicio, ["Hola.", "Chao."]))
        servicio._wrap_generate_from_text("Hola.")
        self.assertEqual(len(cliente.pedidos), 2)

    def test_otras_voces_no_cambian(self):
        servicio = self.voces.crear_servicio("silencio", "", "+0%")
        self.assertFalse(self.voces.precargar_voz(servicio, ["Hola."]))

    def test_lo_que_ya_estaba_en_cache_no_se_vuelve_a_pedir(self):
        cliente = ClienteContador()
        servicio = self._servicio(cliente)
        voces = ["Hola a todos.", "Esto es un dato."]
        self.voces.precargar_voz(servicio, voces)
        self.assertFalse(self.voces.precargar_voz(servicio, voces))  # nada nuevo que pedir
        self.assertEqual(len(cliente.pedidos), 1)


from pathlib import Path  # noqa: E402


class EscenaPrecargaTest(unittest.TestCase):
    """La escena pide la voz de TODO el video antes del primer bloque (y solo el gancho en el clip)."""

    def _correr(self, solo_gancho):
        try:
            from manim import tempconfig

            from tpi_videos import escena
            from tpi_videos.entorno import latex_disponible
        except ModuleNotFoundError:
            self.skipTest("manim no está instalado")
        if not all(latex_disponible()):
            self.skipTest("LaTeX no está instalado")
        import contextvars
        import tempfile
        from unittest.mock import patch

        from pruebas.datos_didacticos import datos_base
        from tpi_videos.config import Marca
        from tpi_videos.guion import Guion
        from tpi_videos.temas import Tema

        guion = Guion.model_validate(datos_base())
        llamadas = []
        config = {"frame_height": 16, "frame_width": 9, "pixel_height": 160, "pixel_width": 90,
                  "frame_rate": 10, "skip_animations": True, "write_to_movie": False}  # fmt: skip
        with tempfile.TemporaryDirectory() as carpeta, tempconfig({**config, "media_dir": carpeta}):
            opciones = escena.OpcionesEscena(
                "silencio", "", "+0%", Path(carpeta) / "t.json", solo_gancho=solo_gancho
            )
            video = escena.VideoEjercicio(guion, Marca(), Tema(nombre="T"), opciones)
            with patch.object(escena, "precargar_voz", side_effect=lambda s, v: llamadas.append(v)):
                contextvars.copy_context().run(video.construct)
        return guion, llamadas

    def test_video_entero(self):
        from tpi_videos.config import Marca

        guion, llamadas = self._correr(False)
        self.assertEqual(llamadas, [[v for _, v in guion.textos_de_voz(Marca().cierre.voz)]])

    def test_solo_el_gancho(self):
        guion, llamadas = self._correr(True)
        self.assertEqual(llamadas, [[guion.gancho.voz_final]])
