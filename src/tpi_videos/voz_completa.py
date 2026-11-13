"""La voz de un video entero en UN solo pedido, cortada en un trozo por frase.

Pedir la voz frase por frase son 12 o más llamadas por video: basta que una se trabe para que se
trabe el video. Acá se pide todo junto (como hace XCris) y el audio se corta en los silencios que la
voz deja entre frase y frase. Cada trozo queda en la caché de la voz con la misma clave que tendría
si se hubiera pedido solo, así la escena no cambia en nada.

Si los silencios no alcanzan para cortar con seguridad, ``cortar`` devuelve None y se vuelve a pedir
frase por frase (lo de siempre): nunca se corta a ciegas a mitad de una palabra.
Solo numpy y la librería estándar: no depende de Manim.
"""

from __future__ import annotations

import io
import wave

import numpy as np

VENTANA = 0.02  # s por medición de volumen
SILENCIO_MINIMO = 0.25  # s: más corto que esto es una pausa dentro de la frase, no entre frases
MARGEN = 0.08  # s de aire que se deja antes y después de cada trozo
TOLERANCIA = 0.25  # fracción del audio: lo más lejos que puede caer un corte de donde se esperaba


def wav_de(muestras: np.ndarray, frecuencia: int) -> bytes:
    salida = io.BytesIO()
    with wave.open(salida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(frecuencia)
        w.writeframes(muestras.astype(np.int16).tobytes())
    return salida.getvalue()


def _leer(audio: bytes) -> tuple[np.ndarray, int] | None:
    try:
        with wave.open(io.BytesIO(audio), "rb") as w:
            if w.getsampwidth() != 2:
                return None
            canales, frecuencia = w.getnchannels(), w.getframerate()
            muestras = np.frombuffer(w.readframes(w.getnframes()), np.int16)
    except (wave.Error, EOFError):
        return None
    if canales > 1:
        muestras = muestras.reshape(-1, canales).mean(axis=1).astype(np.int16)
    return muestras, frecuencia


def _silencios(muestras: np.ndarray, frecuencia: int) -> tuple[list[tuple[float, float]], float, float]:
    """Tramos de silencio largos (inicio, fin) entre la primera y la última voz, en segundos."""
    paso = max(1, int(VENTANA * frecuencia))
    n = len(muestras) // paso
    if n == 0:
        return [], 0.0, 0.0
    bloques = muestras[: n * paso].astype(np.float32).reshape(n, paso) / 32768.0
    volumen = np.sqrt((bloques**2).mean(axis=1))
    umbral = max(0.03 * float(volumen.max()), 1e-4)
    voz = volumen > umbral
    if not voz.any():
        return [], 0.0, 0.0
    primero, ultimo = int(np.argmax(voz)), int(n - 1 - np.argmax(voz[::-1]))
    tramos: list[tuple[float, float]] = []
    i = primero
    while i <= ultimo:
        if voz[i]:
            i += 1
            continue
        j = i
        while j <= ultimo and not voz[j]:
            j += 1
        if (j - i) * VENTANA >= SILENCIO_MINIMO:
            tramos.append((i * VENTANA, j * VENTANA))
        i = j
    return tramos, primero * VENTANA, (ultimo + 1) * VENTANA


def cortar(audio: bytes, textos: list[str]) -> list[bytes] | None:
    """Un WAV por texto, en orden; None si no se puede cortar con seguridad."""
    leido = _leer(audio)
    if leido is None or not textos:
        return None
    muestras, frecuencia = leido
    tramos, inicio, fin = _silencios(muestras, frecuencia)
    if fin <= inicio:
        return None
    if len(textos) == 1:
        return [wav_de(muestras, frecuencia)]
    if len(tramos) < len(textos) - 1:
        return None
    # Dónde debería caer cada corte si la voz habla parejo: proporcional al largo de cada texto.
    largos = np.array([max(1, len(t)) for t in textos], dtype=float)
    esperados = inicio + (fin - inicio) * np.cumsum(largos)[:-1] / largos.sum()
    tolerancia = TOLERANCIA * (fin - inicio)
    elegidos: list[tuple[float, float]] = []
    desde = 0
    for k, esperado in enumerate(esperados):
        # Deja tramos suficientes para los cortes que faltan.
        hasta = len(tramos) - (len(esperados) - 1 - k)
        candidatos = range(desde, hasta)
        if not candidatos:
            return None
        mejor = min(candidatos, key=lambda c: abs(sum(tramos[c]) / 2 - esperado))
        centro = sum(tramos[mejor]) / 2
        if abs(centro - esperado) > tolerancia:
            return None
        elegidos.append(tramos[mejor])
        desde = mejor + 1
    # Cada trozo va de la voz que termina un silencio a la que empieza el siguiente, con un poco de aire.
    bordes = [inicio, *[x for tramo in elegidos for x in tramo], fin]
    trozos = []
    for a, b in zip(bordes[0::2], bordes[1::2], strict=True):
        ia = max(0, int((a - MARGEN) * frecuencia))
        ib = min(len(muestras), int((b + MARGEN) * frecuencia))
        trozos.append(wav_de(muestras[ia:ib], frecuencia))
    return trozos
