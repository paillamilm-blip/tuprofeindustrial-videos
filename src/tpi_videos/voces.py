"""Voces sintéticas para manim-voiceover.

- ``edge``: voces neurales de Microsoft (gratis, requiere internet). Por defecto usa una voz
  chilena (es-CL-LorenzoNeural / es-CL-CatalinaNeural) y entrega la marca de tiempo exacta de
  cada palabra, lo que permite subtítulos palabra por palabra sin re-transcribir.
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
from .revision import estimar_segundos

PROVEEDORES = ("edge", "gtts", "silencio")
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


def crear_servicio(proveedor: str, voz: str, velocidad: str) -> SpeechService:
    if proveedor == "edge":
        return EdgeTTSService(voz=voz, velocidad=velocidad)
    if proveedor == "gtts":
        from manim_voiceover.services.gtts import GTTSService

        return GTTSService(lang="es", tld="com.mx")  # acento latinoamericano
    if proveedor == "silencio":
        return SilencioService()
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
