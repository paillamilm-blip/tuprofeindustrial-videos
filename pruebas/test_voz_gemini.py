"""La voz de Gemini: qué se le pide, qué se guarda y cómo se explican sus errores (sin internet)."""

import base64
import unittest
from types import SimpleNamespace

from tpi_videos.errores import ErrorMotor
from tpi_videos.voz_gemini import (
    ESTILO_POR_DEFECTO,
    MODELO_TTS,
    VOZ_POR_DEFECTO,
    es_voz_de_gemini,
    estilo_con_ritmo,
    sintetizar,
    voz_de_gemini,
)

WAV = b"RIFF....WAVEfmt "


class _Interacciones:
    def __init__(self, respuesta=None, error=None):
        self.pedidos, self.respuesta, self.error = [], respuesta, error

    def create(self, **pedido):
        self.pedidos.append(pedido)
        if self.error:
            raise self.error
        return self.respuesta


def _cliente(respuesta=None, error=None):
    return SimpleNamespace(interactions=_Interacciones(respuesta, error))


class VozTest(unittest.TestCase):
    def test_las_voces_de_edge_no_se_le_pasan_a_gemini(self):
        self.assertEqual(voz_de_gemini("es-CL-LorenzoNeural"), VOZ_POR_DEFECTO)
        self.assertEqual(voz_de_gemini(None), VOZ_POR_DEFECTO)
        self.assertEqual(voz_de_gemini("Kore"), "Kore")
        self.assertTrue(es_voz_de_gemini("voice_mi_clon"))  # una voz propia (diseñada o clonada)
        self.assertFalse(es_voz_de_gemini("es-CL-CatalinaNeural"))

    def test_el_ritmo_se_pide_con_palabras(self):
        self.assertEqual(estilo_con_ritmo("", "+5%"), ESTILO_POR_DEFECTO)
        self.assertTrue(estilo_con_ritmo("", "+15%").endswith("Ritmo ágil."))
        self.assertIn("pausado", estilo_con_ritmo("Profe serio.", "-10%"))
        self.assertTrue(estilo_con_ritmo("Profe serio.", None).startswith("Profe serio."))


class SintetizarTest(unittest.TestCase):
    def test_pide_el_texto_la_voz_y_el_estilo_y_devuelve_el_wav(self):
        cliente = _cliente(SimpleNamespace(output_audio=SimpleNamespace(data=base64.b64encode(WAV).decode())))
        self.assertEqual(sintetizar("Hola, curso.", "Kore", "con calma", cliente=cliente), WAV)
        pedido = cliente.interactions.pedidos[0]
        self.assertEqual(pedido["model"], MODELO_TTS)
        contenido = pedido["input"][0]["content"][0]
        self.assertEqual(contenido["text"], "Hola, curso.")
        self.assertEqual(contenido["annotations"][0], {"type": "speech_metadata", "style": "con calma"})
        self.assertEqual(pedido["generation_config"], {"speech_config": [{"voice": "Kore"}]})
        self.assertEqual(pedido["response_format"], {"type": "audio"})

    def test_si_no_viene_output_audio_busca_el_ultimo_bloque_de_audio(self):
        audio = SimpleNamespace(type="audio", data=base64.b64encode(WAV).decode())
        respuesta = SimpleNamespace(output_audio=None, steps=[SimpleNamespace(content=[audio])])
        self.assertEqual(sintetizar("Hola.", cliente=_cliente(respuesta)), WAV)

    def test_sin_audio_avisa_y_se_puede_reintentar(self):
        with self.assertRaises(ErrorMotor) as caso:
            sintetizar("Hola.", cliente=_cliente(SimpleNamespace(output_audio=None, steps=[])))
        self.assertTrue(caso.exception.transitorio)

    def test_un_error_de_red_se_explica_y_ofrece_la_voz_gratis(self):
        with self.assertRaises(ErrorMotor) as caso:
            sintetizar("Hola.", cliente=_cliente(error=ConnectionError("sin internet")))
        self.assertIn("--voz edge", caso.exception.ayuda)


try:
    import manim_voiceover  # noqa: F401

    VOICEOVER = True
except ImportError:  # el panel y las pruebas corren sin Manim
    VOICEOVER = False


@unittest.skipUnless(VOICEOVER, "manim-voiceover no está instalado")
class ServicioTest(unittest.TestCase):
    def test_guarda_el_wav_y_reparte_las_palabras_sobre_la_duracion_real(self):
        import io
        import tempfile
        import wave
        from pathlib import Path

        from tpi_videos.voces import RESOLUCION, GeminiTTSService

        crudo = io.BytesIO()
        with wave.open(crudo, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24_000)
            wav.writeframes(b"\x00\x00" * 24_000 * 2)  # 2 s
        cliente = _cliente(SimpleNamespace(output_audio=SimpleNamespace(data=crudo.getvalue())))
        with tempfile.TemporaryDirectory() as carpeta:
            servicio = GeminiTTSService(voz="Charon", estilo="con calma", cliente=cliente, cache_dir=carpeta)
            datos = servicio.generate_from_text("Dos de largo y dos de ancho.", cache_dir=carpeta)
            self.assertTrue((Path(carpeta) / datos["original_audio"]).is_file())
            self.assertEqual(datos["input_data"]["service"], "gemini-tts")
            self.assertEqual(datos["input_data"]["config"]["voice"], "Charon")
            marcas = datos["word_boundaries"]
            self.assertEqual(len(marcas), 7)  # una marca por palabra
            self.assertLess(marcas[-1]["audio_offset"] / RESOLUCION, 2.0)  # dentro del audio real


if __name__ == "__main__":
    unittest.main()
