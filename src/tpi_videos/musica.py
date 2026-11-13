"""Cama musical: una base suave que el motor compone y sintetiza (libre de derechos, sin assets externos).

Antes era un acorde fijo que respiraba: sonaba a zumbido. Ahora es música de verdad, tranquila, para
explicar: cuatro acordes que avanzan (La menor, Fa, Do, Sol), un arpegio de notas suaves que
marca el pulso y un bajo. Todo va por debajo de los 1500 Hz para no tapar la claridad de la voz.

Es un bucle sin costura: las notas que suenan al final continúan al principio y el filtro se aplica
en forma circular, así que al repetirse bajo la voz no se nota dónde empieza.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

FRECUENCIA = 48_000
PULSO_BPM = 90  # tranquilo: acompaña la explicación sin apurarla
# La menor, Fa, Do, Sol (vi–IV–I–V): la progresión más reconocible y amable del pop
ACORDES = ((57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62))  # notas MIDI
SEGUNDOS_POR_DEFECTO = 4 * 4 * 60 / PULSO_BPM  # 4 compases de 4 tiempos ≈ 10,7 s
CORTE_AGUDOS = 1500.0  # Hz: por encima vive la claridad de la voz


def _hz(nota: int) -> float:
    return 440.0 * 2 ** ((nota - 69) / 12)


def _tono(frecuencia: float, t: np.ndarray, brillo: float = 0.25) -> np.ndarray:
    """Seno con un poco de armónicos: más cálido que un seno puro, sin sonar a chicharra."""
    return np.sin(2 * np.pi * frecuencia * t) + brillo * np.sin(4 * np.pi * frecuencia * t) * 0.5


def _sumar_circular(destino: np.ndarray, inicio: int, sonido: np.ndarray) -> None:
    """Suma ``sonido`` desde ``inicio``; lo que se pasa del final entra por el principio (bucle)."""
    n = len(destino)
    indices = (inicio + np.arange(len(sonido))) % n
    np.add.at(destino, indices, sonido)


def _sin_agudos(x: np.ndarray, corte: float) -> np.ndarray:
    """Filtro de agudos circular (FFT): suave, y el bucle sigue empalmando perfecto."""
    espectro = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / FRECUENCIA)
    espectro *= 1.0 / (1.0 + (f / corte) ** 4)
    return np.fft.irfft(espectro, n=len(x))


def componer(segundos: float = SEGUNDOS_POR_DEFECTO) -> np.ndarray:
    """La base musical del bucle (mono, -1..1)."""
    n = int(round(segundos * FRECUENCIA))
    salida = np.zeros(n)
    compas = n / len(ACORDES)
    tiempo = compas / 4
    for k, acorde in enumerate(ACORDES):
        inicio = int(round(k * compas))
        largo = int(round(compas))
        t = np.arange(largo + int(0.6 * FRECUENCIA)) / FRECUENCIA  # el acorde se funde con el siguiente
        # Pad: el acorde sostenido, con entrada y salida suaves
        envolvente = np.minimum(1.0, t / 0.35) * np.clip((t[-1] - t) / 0.6, 0.0, 1.0)
        pad = sum(_tono(_hz(nota), t, 0.15) for nota in acorde) * envolvente * 0.16
        _sumar_circular(salida, inicio, pad)
        # Bajo: la nota base una octava abajo, en el primer y el tercer tiempo
        for golpe in (0, 2):
            tb = np.arange(int(tiempo * 1.8)) / FRECUENCIA
            bajo = _tono(_hz(acorde[0] - 12), tb, 0.3) * np.exp(-tb / 0.45) * np.minimum(1.0, tb / 0.01) * 0.35
            _sumar_circular(salida, inicio + int(round(golpe * tiempo)), bajo)
        # Arpeggio: corcheas que suben y bajan por el acorde, una octava arriba
        orden = (0, 1, 2, 1, 0, 1, 2, 1)
        for j, cual in enumerate(orden):
            ta = np.arange(int(0.9 * FRECUENCIA)) / FRECUENCIA
            nota = acorde[cual] + 12
            golpe = np.minimum(1.0, ta / 0.006) * np.exp(-ta / 0.28)
            volumen = 0.22 if j % 2 == 0 else 0.16  # el pulso se siente sin marcar fuerte
            _sumar_circular(salida, inicio + int(round(j * tiempo / 2)), _tono(_hz(nota), ta, 0.35) * golpe * volumen)
    salida = _sin_agudos(salida, CORTE_AGUDOS)
    salida /= np.max(np.abs(salida)) or 1.0
    return salida * 0.5


def bucle_cama(destino: Path, segundos: float = SEGUNDOS_POR_DEFECTO) -> Path:
    """Escribe el WAV mono del bucle; empalma consigo mismo para repetirse sin que se note."""
    destino = Path(destino)
    musica = componer(segundos)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(FRECUENCIA)
        wav.writeframes((musica * 32767).astype(np.int16).tobytes())
    return destino
