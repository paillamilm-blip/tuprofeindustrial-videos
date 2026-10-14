"""Whisper (OpenAI) para obtener el tiempo de cada palabra en un audio.

Se usa cuando la voz no trae marcas de tiempo (gTTS, voz grabada) y en ``tpi subtitular``
para videos externos. El audio se decodifica con PyAV (ya viene con Manim), así Whisper no
depende de tener ``ffmpeg`` en el PATH. Los resultados se guardan junto al audio para no
repetir el trabajo.
"""

from __future__ import annotations

import functools
import importlib.util
import json
from pathlib import Path

from .errores import ErrorMotor

FRECUENCIA = 16_000


@functools.cache
def problema() -> str | None:
    """None si Whisper se puede usar; si no, el motivo (no instalado o no carga)."""
    if importlib.util.find_spec("whisper") is None:
        return "no instalado"
    try:  # importarlo de verdad: en algunos Mac Intel PyTorch no es compatible con NumPy 2
        import whisper  # noqa: F401
    except Exception as e:
        return f"no carga ({str(e).splitlines()[0][:80]})"
    return None


def disponible() -> bool:
    return problema() is None


@functools.cache
def _modelo(nombre: str):
    if not disponible():
        raise ErrorMotor(f"Whisper {problema()}.", ayuda="Usa --sincronizar auto (no necesita Whisper).")
    import whisper

    try:
        return whisper.load_model(nombre, device="cpu")
    except Exception as e:  # sin internet la primera vez, nombre inválido, etc.
        raise ErrorMotor(
            f"No pude cargar el modelo de Whisper «{nombre}» ({e}).",
            ayuda="La primera vez se descarga (~140 MB para 'base'); revisa tu internet. "
            "Modelos: tiny, base, small, medium.",
        ) from e


def cargar_audio(ruta: Path):
    """Audio mono a 16 kHz como arreglo float32 (lo que espera Whisper)."""
    import av
    import numpy as np

    trozos = []
    try:
        with av.open(str(ruta)) as contenedor:
            if not contenedor.streams.audio:
                raise ErrorMotor(f"{ruta.name} no tiene pista de audio.")
            remuestreo = av.AudioResampler(format="s16", layout="mono", rate=FRECUENCIA)
            for cuadro in contenedor.decode(contenedor.streams.audio[0]):
                trozos += [f.to_ndarray().reshape(-1) for f in remuestreo.resample(cuadro)]
            trozos += [f.to_ndarray().reshape(-1) for f in remuestreo.resample(None)]
    except ErrorMotor:
        raise
    except Exception as e:
        raise ErrorMotor(f"No pude leer el audio de {ruta.name} ({e}).") from e
    if not trozos:
        return np.zeros(0, dtype=np.float32)
    return (np.concatenate(trozos).astype(np.float32) / 32768.0).copy()


def transcribir(
    ruta: Path,
    modelo: str = "base",
    idioma: str = "es",
    prompt: str | None = None,
    cache: Path | None = None,
) -> list[tuple[str, float, float]]:
    """Lista de (palabra, inicio, fin) en segundos. Guarda el resultado en ``cache``
    (por defecto, junto al audio) para no repetir el trabajo."""
    cache = cache or ruta.with_name(f"{ruta.name}.whisper-{modelo}.json")
    if cache.exists():
        return [tuple(p) for p in json.loads(cache.read_text(encoding="utf-8"))]  # type: ignore[misc]
    if not disponible():
        raise ErrorMotor(
            "Whisper no está instalado.", ayuda='Instálalo con: .venv/bin/pip install -e ".[whisper]"'
        )
    audio = cargar_audio(ruta)
    if audio.size == 0:
        return []
    resultado = _modelo(modelo).transcribe(
        audio,
        language=idioma,
        word_timestamps=True,
        initial_prompt=prompt,  # ayuda a escribir bien términos técnicos
        condition_on_previous_text=False,
        fp16=False,
        verbose=None,
    )
    palabras: list[tuple[str, float, float]] = []
    for segmento in resultado.get("segments", []):
        for w in segmento.get("words", []):
            texto = w["word"].strip()
            if not texto:
                continue
            # Whisper a veces separa decimales: "9" + ",8" → "9,8"
            if palabras and texto[0] in ",." and texto[1:2].isdigit() and palabras[-1][0][-1:].isdigit():
                anterior = palabras.pop()
                palabras.append((anterior[0] + texto, anterior[1], float(w["end"])))
                continue
            palabras.append((texto, float(w["start"]), float(w["end"])))
    cache.write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")
    return palabras
