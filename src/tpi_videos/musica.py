"""Cama musical: un pad ambiental que el motor sintetiza (libre de derechos, sin assets externos).

Un bucle corto y sin costura que se repite bajo la voz durante todo el video: aunque la voz calle
un instante, el oído nunca queda en silencio (el «aire muerto» que delata a un video sintético).
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

FRECUENCIA = 48_000
ACORDE = (110.0, 165.0, 220.0, 330.0)  # graves suaves: quedan por debajo de la voz


def bucle_cama(destino: Path, segundos: float = 8.0) -> Path:
    """Escribe un WAV mono con un pad que empalma consigo mismo (cada tono cierra ciclos enteros)."""
    destino = Path(destino)
    n = int(round(segundos * FRECUENCIA))
    t = np.arange(n) / FRECUENCIA
    pad = np.zeros(n)
    for objetivo in ACORDE:
        ciclos = max(1, round(objetivo * segundos))  # ciclos enteros en el bucle = costura invisible
        pad += np.sin(2 * np.pi * (ciclos / segundos) * t)
    pad *= 0.6 + 0.4 * np.sin(2 * np.pi * t / segundos)  # respiración lenta, un ciclo por bucle
    pad /= np.max(np.abs(pad)) or 1.0
    pad *= 0.5
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(FRECUENCIA)
        wav.writeframes((pad * 32767).astype(np.int16).tobytes())
    return destino