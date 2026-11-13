"""Voces sintéticas para manim-voiceover.

- ``edge``: voces neurales de Microsoft (gratis, requiere internet). Por defecto usa una voz
  chilena (es-CL-LorenzoNeural / es-CL-CatalinaNeural) y entrega la marca de tiempo exacta de
  cada palabra, lo que permite subtítulos palabra por palabra sin re-transcribir.
- ``gemini``: la voz de Gemini TTS (misma clave que el redactor). Natural y se le pide el tono con
  palabras (``voz.estilo`` de marca.yaml). No trae marcas por palabra: los subtítulos van con Whisper
  o repartidos sobre la duración real del audio.
- ``gtts``: Google Translate TTS (gratis, requiere internet, voz más robótica). Sin marcas de
  tiempo: los subtítulos se sincronizan con Whisper.
- ``silencio``: sin voz y sin internet, con la duración estimada. Para revisar ritmo y diseño.
"""

from __future__ import annotations

import asyncio
import time
import wave
from pathlib import Path
from typing import Any

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService, initialize_speech_service, path_to_string

from .errores import ErrorMotor
from .pausas import tiene_pausas, trozos
from .revision import estimar_segundos

PROVEEDORES = ("edge", "gemini", "gtts", "silencio")
RESOLUCION = 10_000_000  # manim-voiceover mide los tiempos en unidades de 100 ns


def _marcas_estimadas(texto: str, duracion: float) -> list[dict[str, Any]]:
    """Marcas de tiempo aproximadas: reparte la duración según el largo de cada palabra."""
    palabras = []
    cursor = 0
    for palabra in texto.split():
        idx = texto.find(palabra, cursor)
        palabras.append((palabra, idx))
        cursor = idx + len(palabra)
    total = sum(len(p) + 1 for p, _ in palabras) or 1
    util = max(duracion - 0.3, 0.1)
    marcas, acumulado = [], 0.0
    for palabra, idx in palabras:
        inicio = 0.15 + util * acumulado / total
        acumulado += len(palabra) + 1
        marcas.append(
            {
                "audio_offset": int(inicio * RESOLUCION),
                "duration_milliseconds": int(1000 * util * (len(palabra) + 1) / total),
                "text_offset": idx,
                "word_length": len(palabra),
                "text": palabra,
                "boundary_type": "Word",
            }
        )
    return marcas


class EdgeTTSService(SpeechService):
    """Servicio de voz con edge-tts (voces neurales, con marcas de tiempo por palabra)."""

    def __init__(
        self,
        voz: str = "es-CL-LorenzoNeural",
        velocidad: str = "+0%",
        tono: str = "+0Hz",
        reintentos: int = 3,
        **kwargs: Any,
    ) -> None:
        initialize_speech_service(self, kwargs)
        self.voz = voz
        self.velocidad = velocidad
        self.tono = tono
        self.reintentos = reintentos

    def generate_from_text(self, text: str, cache_dir=None, path=None, **kwargs: Any) -> dict[str, Any]:
        cache_dir = cache_dir or self.cache_dir
        texto = remove_bookmarks(text)
        input_data = {
            "input_text": texto,
            "service": "edge-tts",
            "config": {"voice": self.voz, "rate": self.velocidad, "pitch": self.tono},
        }
        en_cache = self.get_cached_result(input_data, cache_dir)
        if en_cache is not None:
            return en_cache

        audio_path = self.get_audio_basename(input_data) + ".mp3" if path is None else path_to_string(path)
        audio, marcas = self._sintetizar(texto)
        (Path(cache_dir) / audio_path).write_bytes(audio)
        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
            "word_boundaries": marcas,
        }

    def _sintetizar(self, texto: str) -> tuple[bytes, list[dict[str, Any]]]:
        import edge_tts

        ultimo_error: Exception | None = None
        for intento in range(1, self.reintentos + 1):
            try:
                comunicador = edge_tts.Communicate(
                    texto, self.voz, rate=self.velocidad, pitch=self.tono, boundary="WordBoundary"
                )
            except ValueError as e:  # nombre de voz o velocidad con formato inválido: no reintentar
                raise ErrorMotor(
                    f"La voz «{self.voz}» o la velocidad «{self.velocidad}» no son válidas ({e}).",
                    ayuda="Mira las voces disponibles con: ./tpi voces",
                ) from e
            try:
                audio = bytearray()
                marcas: list[dict[str, Any]] = []
                cursor, ultimo_idx = 0, -1
                for trozo in comunicador.stream_sync():
                    if trozo["type"] == "audio":
                        audio += trozo["data"]
                    elif trozo["type"] == "WordBoundary":
                        palabra = trozo["text"]
                        idx = texto.find(palabra, cursor)
                        if idx < 0:
                            idx = cursor
                        idx = max(idx, ultimo_idx + 1)  # siempre creciente
                        marcas.append(
                            {
                                "audio_offset": int(round(trozo["offset"])),
                                "duration_milliseconds": int(round(trozo["duration"] / 10_000)),
                                "text_offset": idx,
                                "word_length": len(palabra),
                                "text": palabra,
                                "boundary_type": "Word",
                            }
                        )
                        cursor, ultimo_idx = idx + len(palabra), idx
                if not audio:
                    raise RuntimeError("el servicio no devolvió audio")
                return bytes(audio), marcas
            except Exception as e:  # red inestable, servicio caído, etc.
                ultimo_error = e
                time.sleep(1.5 * intento)
        raise ErrorMotor(
            f"No pude generar la voz con edge-tts tras {self.reintentos} intentos ({ultimo_error}).",
            ayuda="Revisa tu internet y prueba de nuevo. Alternativas: --voz gtts (otra voz gratis) "
            "o --voz silencio (sin voz, para revisar el diseño).",
        )


class GeminiTTSService(SpeechService):
    """La voz de Gemini (ver ``voz_gemini``): natural, con el tono que pide el estilo."""

    def __init__(
        self, voz: str, estilo: str, modelo: str | None = None, cliente: Any = None, **kwargs: Any
    ) -> None:
        from .voz_gemini import MODELO_TTS

        initialize_speech_service(self, kwargs)
        self.voz = voz
        self.estilo = estilo
        self.modelo = modelo or MODELO_TTS
        self._cliente = cliente  # se crea recién al primer audio que no está en caché

    def generate_from_text(self, text: str, cache_dir=None, path=None, **kwargs: Any) -> dict[str, Any]:
        from .voz_gemini import cliente_tts, sintetizar

        cache_dir = cache_dir or self.cache_dir
        texto = remove_bookmarks(text)
        input_data = {
            "input_text": texto,
            "service": "gemini-tts",
            "config": {"voice": self.voz, "style": self.estilo, "model": self.modelo},
        }
        en_cache = self.get_cached_result(input_data, cache_dir)
        if en_cache is not None:
            return en_cache

        if self._cliente is None:
            self._cliente = cliente_tts()  # guardar la referencia: si se libera, cierra su conexión
        audio = sintetizar(texto, self.voz, self.estilo, self.modelo, cliente=self._cliente)
        audio_path = self.get_audio_basename(input_data) + ".wav" if path is None else path_to_string(path)
        destino = Path(cache_dir) / audio_path
        destino.write_bytes(audio)
        try:
            with wave.open(str(destino), "rb") as wav:
                duracion = wav.getnframes() / float(wav.getframerate())
        except (wave.Error, EOFError):
            duracion = estimar_segundos(texto)
        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
            # Gemini no da el tiempo de cada palabra: se reparten sobre la duración REAL del audio
            # (si Whisper está instalado, el subtítulo usa Whisper en su lugar).
            "word_boundaries": _marcas_estimadas(texto, duracion),
        }


class SilencioService(SpeechService):
    """Sin voz: genera silencio con la duración estimada del texto (no necesita internet)."""

    def __init__(self, **kwargs: Any) -> None:
        initialize_speech_service(self, kwargs)

    def generate_from_text(self, text: str, cache_dir=None, path=None, **kwargs: Any) -> dict[str, Any]:
        cache_dir = cache_dir or self.cache_dir
        texto = remove_bookmarks(text)
        input_data = {"input_text": texto, "service": "silencio"}
        en_cache = self.get_cached_result(input_data, cache_dir)
        if en_cache is not None:
            return en_cache

        audio_path = self.get_audio_basename(input_data) + ".wav" if path is None else path_to_string(path)
        duracion = estimar_segundos(texto)
        frecuencia = 24_000
        with wave.open(str(Path(cache_dir) / audio_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(frecuencia)
            wav.writeframes(b"\x00\x00" * int(duracion * frecuencia))
        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
            "word_boundaries": _marcas_estimadas(texto, duracion),
        }


class ServicioConPausas(SpeechService):
    """Envuelve a cualquier voz y resuelve las pausas ``<break time="1.5s"/>`` con silencio de verdad.

    Cada trozo entre pausas se sintetiza (y se guarda en caché) con la voz de siempre; después se
    unen con el silencio pedido en un WAV y las marcas de cada palabra se corren lo que corresponde.
    Una voz sin pausas pasa directo a la voz de siempre: el audio y la caché quedan como antes.
    """

    def __init__(self, base: SpeechService, nombre: str, **kwargs: Any) -> None:
        initialize_speech_service(self, kwargs)
        self.base = base
        self.nombre = nombre  # "edge-tts", "gtts" o "silencio": así sigue llamándose en la línea de tiempo

    def generate_from_text(self, text: str, cache_dir=None, path=None, **kwargs: Any) -> dict[str, Any]:
        cache_dir = cache_dir or self.cache_dir
        if not tiene_pausas(text):
            return self.base.generate_from_text(text, cache_dir=cache_dir, path=path, **kwargs)
        from pydub import AudioSegment

        partes = trozos(remove_bookmarks(text))
        limpio = " ".join(t for t, _ in partes if t)
        claves = ("voz", "velocidad", "tono", "estilo", "modelo")
        config = {k: getattr(self.base, k) for k in claves if hasattr(self.base, k)}
        input_data = {"input_text": text, "service": self.nombre, "config": config, "pausas": True}
        en_cache = self.get_cached_result(input_data, cache_dir)
        if en_cache is not None:
            return en_cache

        audio = AudioSegment.silent(duration=0, frame_rate=24_000)
        marcas: list[dict[str, Any]] = []
        cursor_texto = 0
        for texto, pausa in partes:
            if texto:
                trozo = self.base.generate_from_text(texto, cache_dir=cache_dir, **kwargs)
                sonido = AudioSegment.from_file(str(Path(cache_dir) / trozo["original_audio"]))
                desplazamiento = int(len(audio) * RESOLUCION / 1000)  # ms → unidades de 100 ns
                for m in trozo.get("word_boundaries") or []:
                    marcas.append(
                        {
                            **m,
                            "audio_offset": m["audio_offset"] + desplazamiento,
                            "text_offset": m.get("text_offset", 0) + cursor_texto,
                        }
                    )
                audio += sonido.set_frame_rate(audio.frame_rate).set_channels(1)
                cursor_texto += len(texto) + 1
            if pausa:
                audio += AudioSegment.silent(duration=int(round(pausa * 1000)), frame_rate=audio.frame_rate)
        audio_path = self.get_audio_basename(input_data) + ".wav" if path is None else path_to_string(path)
        audio.export(str(Path(cache_dir) / audio_path), format="wav")
        return {
            "input_text": limpio,
            "input_data": input_data,
            "original_audio": audio_path,
            "word_boundaries": marcas,
        }


def crear_servicio(proveedor: str, voz: str, velocidad: str, tono: str = "+0Hz") -> SpeechService:
    if proveedor == "edge":
        from .config import Voz
        from .voz_gemini import es_voz_de_gemini

        # «--voz edge» con la marca en Gemini trae el nombre «Charon»: edge no lo conoce. Va la de siempre.
        if es_voz_de_gemini(voz):
            voz = Voz.model_fields["nombre"].default
        return ServicioConPausas(EdgeTTSService(voz=voz, velocidad=velocidad, tono=tono), "edge-tts")
    if proveedor == "gemini":
        from .config import cargar_marca
        from .voz_gemini import estilo_con_ritmo, voz_de_gemini

        estilo = estilo_con_ritmo(cargar_marca().voz.estilo, velocidad)
        return ServicioConPausas(GeminiTTSService(voz=voz_de_gemini(voz), estilo=estilo), "gemini-tts")
    if proveedor == "gtts":
        from manim_voiceover.services.gtts import GTTSService

        return ServicioConPausas(GTTSService(lang="es", tld="com.mx"), "gtts")  # acento latinoamericano
    if proveedor == "silencio":
        return ServicioConPausas(SilencioService(), "silencio")
    raise ErrorMotor(
        f"No conozco el proveedor de voz «{proveedor}».", ayuda=f"Opciones: {', '.join(PROVEEDORES)}"
    )


def listar_voces_es() -> list[dict[str, Any]]:
    """Voces en español disponibles en edge-tts (requiere internet)."""
    import edge_tts

    try:
        voces = asyncio.run(edge_tts.list_voices())
    except Exception as e:
        raise ErrorMotor(
            f"No pude obtener la lista de voces ({e}).", ayuda="Revisa tu conexión a internet."
        ) from e
    return sorted((v for v in voces if v["Locale"].startswith("es-")), key=lambda v: v["ShortName"])
