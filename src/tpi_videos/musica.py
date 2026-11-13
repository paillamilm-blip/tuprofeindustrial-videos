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


def componer(segundos: float = SEGUNDOS_POR_DEFECTO, estilo: str = "suave") -> np.ndarray:
    """La base musical del bucle (mono, -1..1)."""
    if estilo == "lofi":
        return componer_lofi(segundos)
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


# ------------------------------------------------------------------------------------------
# Lofi jazz hip hop: acordes de jazz en piano eléctrico, bajo, batería con swing y vinilo
# ------------------------------------------------------------------------------------------

PULSO_LOFI = 78  # el tempo típico del lofi: relajado, con cabeceo
# Dm9 → G13 → Cmaj9 → Am7 (ii–V–I–vi): el giro de jazz que suena a «lofi para estudiar»
ACORDES_LOFI = ((50, 53, 57, 60, 64), (43, 53, 59, 64), (48, 52, 55, 59, 62), (45, 52, 55, 60))
CORTE_LOFI = 2800.0  # Hz: el lofi es cálido y apagado, como un casete
ESTILOS = ("suave", "lofi")


def _rhodes(frecuencia: float, segundos: float) -> np.ndarray:
    """Piano eléctrico: tono redondo, un brillo metálico que se apaga rápido y un leve vaivén."""
    t = np.arange(int(segundos * FRECUENCIA)) / FRECUENCIA
    cuerpo = np.sin(2 * np.pi * frecuencia * t) + 0.18 * np.sin(4 * np.pi * frecuencia * t)
    campana = 0.25 * np.sin(2 * np.pi * frecuencia * 3.5 * t) * np.exp(-t / 0.08)
    vaiven = 1.0 + 0.12 * np.sin(2 * np.pi * 4.5 * t)
    envolvente = np.minimum(1.0, t / 0.008) * np.exp(-t / 1.1)
    return (cuerpo + campana) * vaiven * envolvente


def _bombo(segundos: float = 0.45) -> np.ndarray:
    t = np.arange(int(segundos * FRECUENCIA)) / FRECUENCIA
    frecuencia = 50 + 70 * np.exp(-t / 0.04)  # el «pum»: el tono cae rápido
    fase = 2 * np.pi * np.cumsum(frecuencia) / FRECUENCIA
    return np.sin(fase) * np.exp(-t / 0.13) * np.minimum(1.0, t / 0.002)


def _caja(azar: np.random.Generator, segundos: float = 0.25) -> np.ndarray:
    t = np.arange(int(segundos * FRECUENCIA)) / FRECUENCIA
    ruido = azar.standard_normal(len(t))
    ruido = np.convolve(ruido, np.ones(6) / 6, mode="same")  # ruido algo apagado, no un siseo
    return (0.7 * ruido * np.exp(-t / 0.07) + 0.5 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)) * np.minimum(
        1.0, t / 0.001
    )


def _platillo(azar: np.random.Generator, segundos: float = 0.06) -> np.ndarray:
    t = np.arange(int(segundos * FRECUENCIA)) / FRECUENCIA
    ruido = azar.standard_normal(len(t))
    ruido = ruido - np.convolve(ruido, np.ones(4) / 4, mode="same")  # solo lo agudo
    return ruido * np.exp(-t / 0.018)


def _vinilo(n: int, azar: np.random.Generator) -> np.ndarray:
    """El crujido del disco: un soplido muy bajo y chasquidos sueltos."""
    soplido = np.convolve(azar.standard_normal(n), np.ones(40) / 40, mode="same") * 0.15
    chasquidos = np.zeros(n)
    for i in azar.integers(0, n, size=max(1, n // FRECUENCIA * 6)):
        largo = min(60, n - i)
        chasquidos[i : i + largo] += azar.choice((-1, 1)) * np.exp(-np.arange(largo) / 8) * azar.uniform(0.3, 1.0)
    return soplido + chasquidos


def componer_lofi(segundos: float | None = None) -> np.ndarray:
    tiempo = 60 / PULSO_LOFI
    segundos = segundos or 16 * tiempo
    n = int(round(segundos * FRECUENCIA))
    azar = np.random.default_rng(7)  # siempre el mismo bucle: el video se rehace igual
    salida = np.zeros(n)
    t_compas = segundos / len(ACORDES_LOFI)

    def poner(en_segundos: float, sonido: np.ndarray, volumen: float) -> None:
        _sumar_circular(salida, int(round(en_segundos * FRECUENCIA)) % n, sonido * volumen)

    swing = tiempo * (2 / 3)  # la segunda corchea llega tarde: eso es el swing
    for k, acorde in enumerate(ACORDES_LOFI):
        inicio = k * t_compas
        # Piano eléctrico: el acorde en el 1 y un golpe corto en el «y» del 2
        for nota in acorde:
            poner(inicio, _rhodes(_hz(nota), min(t_compas, 2.8)), 0.13)
            poner(inicio + tiempo + swing, _rhodes(_hz(nota + 12 if nota < 52 else nota), 0.9), 0.05)
        # Bajo: la raíz en el 1 y en el «y» del 2
        raiz = _hz(acorde[0] - 12 if acorde[0] >= 48 else acorde[0])
        for cuando in (0.0, tiempo + swing):
            tb = np.arange(int(0.5 * FRECUENCIA)) / FRECUENCIA
            poner(inicio + cuando, np.sin(2 * np.pi * raiz * tb) * np.exp(-tb / 0.18) * np.minimum(1, tb / 0.01), 0.35)
        # Batería: bombo en 1 y 3, caja en 2 y 4, platillo en corcheas con swing
        for golpe in range(4):
            momento = inicio + golpe * tiempo
            if golpe in (0, 2):
                poner(momento, _bombo(), 0.9)
            else:
                poner(momento, _caja(azar), 0.35)
            poner(momento, _platillo(azar), 0.12)
            poner(momento + swing, _platillo(azar), 0.07)
    salida += _vinilo(n, azar) * 0.025
    salida = _sin_agudos(salida, CORTE_LOFI)
    salida /= np.max(np.abs(salida)) or 1.0
    return salida * 0.5


VOLUMEN_PROMEDIO = 0.42  # RMS del bucle: así ``cama.volumen`` significa lo mismo en todos los estilos


def _a_volumen_parejo(x: np.ndarray) -> np.ndarray:
    """Ajusta la música por su volumen PROMEDIO, no por su golpe más fuerte.

    Ajustar por el pico dejaba el lofi casi mudo: el bombo pega mucho más que el resto, así que todo lo
    demás quedaba bajísimo. Un limitador suave (tanh) redondea los golpes en vez de cortarlos.
    """
    rms = float(np.sqrt(np.mean(x**2))) or 1.0
    y = x * (VOLUMEN_PROMEDIO / rms)
    return np.tanh(y * 1.2) / 1.2 * 0.98


def bucle_cama(destino: Path, segundos: float | None = None, estilo: str = "suave") -> Path:
    """Escribe el WAV mono del bucle; empalma consigo mismo para repetirse sin que se note."""
    from .errores import ErrorMotor

    if estilo not in ESTILOS:
        raise ErrorMotor(f"No conozco la música «{estilo}».", ayuda=f"Opciones: {', '.join(ESTILOS)}.")
    destino = Path(destino)
    musica = componer_lofi(segundos) if estilo == "lofi" else componer(segundos or SEGUNDOS_POR_DEFECTO)
    musica = _a_volumen_parejo(musica)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(FRECUENCIA)
        wav.writeframes((musica * 32767).astype(np.int16).tobytes())
    return destino
