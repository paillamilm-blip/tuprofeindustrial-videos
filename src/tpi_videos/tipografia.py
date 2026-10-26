"""Letras incluidas en el motor (todas gratuitas, con tildes y ñ revisadas).

Los grosores usan los nombres de Manim ("NORMAL", "BOLD", "HEAVY"…). Si una familia no tiene el grosor
pedido, se usa el más cercano, igual para dibujar (Pango) que para medir (PIL), así los saltos de línea
calculados coinciden con lo que se ve.
"""

from __future__ import annotations

import functools
from pathlib import Path

from .entorno import FUENTES_DIR

PESOS = {
    "THIN": 100, "ULTRALIGHT": 200, "LIGHT": 300, "BOOK": 380, "NORMAL": 400, "MEDIUM": 500,
    "SEMIBOLD": 600, "BOLD": 700, "ULTRABOLD": 800, "HEAVY": 900, "ULTRAHEAVY": 1000,
}  # fmt: skip

# familia → {peso numérico: archivo}
FAMILIAS: dict[str, dict[int, str]] = {
    "Montserrat": {
        500: "Montserrat-Medium.ttf",
        600: "Montserrat-SemiBold.ttf",
        800: "Montserrat-ExtraBold.ttf",
        900: "Montserrat-Black.ttf",
    },
    "Comic Neue": {400: "ComicNeue-Regular.ttf", 700: "ComicNeue-Bold.ttf"},
    "Caveat": {400: "Caveat-Regular.ttf", 700: "Caveat-Bold.ttf"},
    "Patrick Hand": {400: "PatrickHand-Regular.ttf"},
    "Shadows Into Light Two": {400: "ShadowsIntoLightTwo-Regular.ttf"},
    "Bangers": {400: "Bangers-Regular.ttf"},
    "Luckiest Guy": {400: "LuckiestGuy-Regular.ttf"},
    "Cinzel": {400: "Cinzel-Regular.ttf"},
}

# Opciones que ofrece el panel para cada uso
PARA_TITULOS = ("Comic Neue", "Montserrat", "Caveat", "Patrick Hand", "Shadows Into Light Two")
PARA_TEXTO = ("Comic Neue", "Montserrat", "Patrick Hand", "Caveat", "Shadows Into Light Two")
# Nombre como lo busca FFmpeg/libass: familia + estilo en el nombre ("Montserrat Black")
PARA_SUBTITULOS = ("Bangers", "Luckiest Guy", "Montserrat Black", "Comic Neue")


def existe(familia: str) -> bool:
    return familia in FAMILIAS


def _peso(grosor: str | int) -> int:
    if isinstance(grosor, int):
        return grosor
    return PESOS.get(str(grosor).upper(), 400)


def grosor_disponible(familia: str, grosor: str) -> str:
    """El grosor más cercano que trae la familia, como nombre de Manim."""
    pesos = FAMILIAS[familia]
    pedido = _peso(grosor)
    if pedido in pesos:
        return str(grosor).upper()
    cercano = min(pesos, key=lambda p: (abs(p - pedido), -p))
    return next(n for n, v in PESOS.items() if v == cercano)


def archivo(familia: str, grosor: str) -> Path:
    pesos = FAMILIAS[familia]
    return FUENTES_DIR / pesos[_peso(grosor_disponible(familia, grosor))]


@functools.cache
def fuente_pil(familia: str, grosor: str):
    from PIL import ImageFont

    return ImageFont.truetype(str(archivo(familia, grosor)), 100)


@functools.cache
def unidades_por_pixel(familia: str, grosor: str) -> float:
    """Calibra cuánto mide en Manim (a font_size 100) un píxel medido con PIL."""
    from manim import Text

    referencia = "Hamburguesa ñandú 123 ¿Qué?"
    ancho_manim = Text(referencia, font=familia, weight=grosor, font_size=100).width
    return ancho_manim / fuente_pil(familia, grosor).getlength(referencia)


def faltantes() -> list[str]:
    """Archivos de letras que no están (para `tpi doctor`)."""
    return sorted(f for pesos in FAMILIAS.values() for f in pesos.values() if not (FUENTES_DIR / f).exists())
