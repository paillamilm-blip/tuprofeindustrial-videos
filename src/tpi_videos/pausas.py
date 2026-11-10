"""Pausas dentro de la voz: ``<break time="1.5s"/>`` le da tiempo a la animación para lucirse.

Se escribe con la sintaxis de SSML, pero edge-tts 7 ya no deja pasar SSML propio (escapa el texto y
la etiqueta se leería en voz alta). Por eso la pausa la resuelve el motor: parte la voz en trozos,
los sintetiza por separado y los une con silencio de verdad (``voces.ServicioConPausas``). Así
funciona igual con edge, con gTTS y con la voz de silencio, y los subtítulos nunca muestran la etiqueta.
"""

from __future__ import annotations

import re

PAUSA_MINIMA = 0.2  # s: menos que eso no se distingue de una coma
PAUSA_MAXIMA = 3.0  # s: más que eso se siente como un video trabado
PAUSAS_MAXIMAS_POR_VOZ = 3
SEGUNDOS_MAXIMOS_POR_VOZ = 5.0

_PAUSA = re.compile(r'<break\s+time\s*=\s*"\s*(\d+(?:[.,]\d+)?)\s*(ms|s)\s*"\s*/>', re.IGNORECASE)
_ETIQUETA = re.compile(r"<[^<>]*>")
_MARCADOR = re.compile(r"<bookmark\s+mark\s*=\s*['\"][^'\"]*['\"]\s*/>", re.IGNORECASE)


def _segundos(numero: str, unidad: str) -> float:
    valor = float(numero.replace(",", "."))
    return valor / 1000 if unidad.lower() == "ms" else valor


def trozos(texto: str) -> list[tuple[str, float]]:
    """La voz partida en (texto, pausa que viene después). Sin pausas, un solo trozo con 0."""
    salida: list[tuple[str, float]] = []
    inicio = 0
    for m in _PAUSA.finditer(texto):
        salida.append((" ".join(texto[inicio : m.start()].split()), _segundos(m.group(1), m.group(2))))
        inicio = m.end()
    salida.append((" ".join(texto[inicio:].split()), 0.0))
    # Dos pausas seguidas (o una al principio) suman silencio en el trozo anterior.
    juntos: list[tuple[str, float]] = []
    for parte, pausa in salida:
        if not parte and juntos:
            juntos[-1] = (juntos[-1][0], juntos[-1][1] + pausa)
        else:
            juntos.append((parte, pausa))
    return juntos


def tiene_pausas(texto: str | None) -> bool:
    return bool(texto and _PAUSA.search(texto))


def sin_pausas(texto: str) -> str:
    """La voz como se dice y como se subtitula: sin etiquetas."""
    return " ".join(_PAUSA.sub(" ", texto).split())


def segundos_de_pausa(texto: str) -> float:
    return sum(_segundos(m.group(1), m.group(2)) for m in _PAUSA.finditer(texto or ""))


def validar_pausas(texto: str | None) -> str | None:
    """Rechaza etiquetas inventadas y pausas fuera de rango, con el arreglo en el mensaje."""
    if texto is None:
        return None
    for etiqueta in _ETIQUETA.findall(texto):
        if not (_PAUSA.fullmatch(etiqueta) or _MARCADOR.fullmatch(etiqueta)):
            raise ValueError(
                f"la voz trae la etiqueta «{etiqueta}», que el motor no conoce: la única pausa que entiende "
                'es <break time="1.5s"/> (entre 0,2 y 3 segundos)'
            )
    pausas = [_segundos(m.group(1), m.group(2)) for m in _PAUSA.finditer(texto)]
    for p in pausas:
        if not PAUSA_MINIMA <= p <= PAUSA_MAXIMA:
            raise ValueError(
                f"una pausa de {p:g} s no sirve: va entre {PAUSA_MINIMA:g} y {PAUSA_MAXIMA:g} segundos"
            )
    if len(pausas) > PAUSAS_MAXIMAS_POR_VOZ or sum(pausas) > SEGUNDOS_MAXIMOS_POR_VOZ:
        raise ValueError(
            f"demasiado silencio en una sola voz ({len(pausas)} pausas, {sum(pausas):g} s): "
            f"como mucho {PAUSAS_MAXIMAS_POR_VOZ} pausas y {SEGUNDOS_MAXIMOS_POR_VOZ:g} s"
        )
    if pausas and not sin_pausas(texto):
        raise ValueError("la voz no puede ser solo una pausa: tiene que decir algo")
    return texto
