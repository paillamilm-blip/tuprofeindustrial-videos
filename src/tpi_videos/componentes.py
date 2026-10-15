"""Piezas visuales reutilizables para el formato vertical 9:16.

El cuadro de Manim mide 9 unidades de ancho × 16 de alto (1 unidad = 120 px en 1080×1920),
con el origen al centro: arriba y = 8, abajo y = −8.

Zonas (de arriba hacia abajo):
- y ≈ 6.5      cabecera con la marca y la materia
- y ≈ 5.5      título del ejercicio
- 4.7 … −2.4   zona de contenido (enunciado, datos, pasos, resultado)
- y ≈ −3.5     subtítulos estilo CapCut (los quema FFmpeg después)
- y < −4.8     se deja libre: ahí van los botones y textos de TikTok/Reels/Shorts
"""

from __future__ import annotations

import functools
import logging
import re

import numpy as np
from manim import (
    DOWN,
    HEAVY,
    LEFT,
    MEDIUM,
    RIGHT,
    SEMIBOLD,
    TAU,
    ULTRABOLD,
    Circle,
    Line,
    MathTex,
    Mobject,
    Paragraph,
    Polygon,
    RoundedRectangle,
    Text,
    VGroup,
    VMobject,
)
from PIL import ImageFont

from .entorno import FUENTES_DIR
from .errores import ErrorMotor
from .tex import corregir_decimales, partes

FUENTE = "Montserrat"
ARCHIVO_POR_PESO = {
    MEDIUM: "Montserrat-Medium.ttf",
    SEMIBOLD: "Montserrat-SemiBold.ttf",
    ULTRABOLD: "Montserrat-ExtraBold.ttf",
    HEAVY: "Montserrat-Black.ttf",
}

ANCHO_UTIL = 7.6
Y_CABECERA = 6.55
Y_TITULO = 5.55
Y_ZONA_SUPERIOR = 4.75
Y_ZONA_INFERIOR = -2.4
CENTRO_ZONA = (Y_ZONA_SUPERIOR + Y_ZONA_INFERIOR) / 2
ALTO_ZONA = Y_ZONA_SUPERIOR - Y_ZONA_INFERIOR

TAM_GANCHO = 60
TAM_TITULO = 28
TAM_CUERPO = 37
TAM_ETIQUETA = 20
TAM_ECUACION = 84
TAM_DATO = 60
TAM_RESULTADO = 96
ALTO_MAX_ECUACION = 2.1  # una raíz con fracción no debe tapar toda la pizarra
ESCALA_HISTORIAL = 0.72  # tamaño de los pasos anteriores


# ------------------------------------------------------------------------------------------
# Texto
# ------------------------------------------------------------------------------------------


@functools.cache
def _fuente_pil(peso: str) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES_DIR / ARCHIVO_POR_PESO[peso]), 100)


@functools.cache
def _unidades_por_pixel(peso: str) -> float:
    """Calibra cuánto mide en Manim (a font_size 100) un píxel medido con PIL."""
    referencia = "Hamburguesa ñandú 123 ¿Qué?"
    ancho_manim = Text(referencia, font=FUENTE, weight=peso, font_size=100).width
    return ancho_manim / _fuente_pil(peso).getlength(referencia)


def ancho_texto(texto: str, tam: float, peso: str) -> float:
    """Ancho aproximado (en unidades de Manim) de una línea de texto."""
    try:
        return _fuente_pil(peso).getlength(texto) * _unidades_por_pixel(peso) * tam / 100
    except (OSError, KeyError):  # sin la fuente: estimación por cantidad de letras
        return len(texto) * 0.0062 * tam


_ESPACIO_FIJO = "\u00a0"

# Lo que nunca debe quedar partido en dos líneas:
# - expresiones con operadores: "x² - 5x + 6 = 0", "P = V²/R"
# - número + unidad o palabra: "20 metros", "9,8 m/s²", "24 Ω"
_EXPRESION = re.compile(r"(?:\S+ [-+=·×÷/<>≤≥≈] )+\S+")
_NUMERO_Y_PALABRA = re.compile(r"\d+(?:[.,]\d+)*\s(\S+)")
_UNIDAD_CORTA = re.compile(r"^[A-Za-zΩµ°%][A-Za-zΩµ°/²³·]{0,4}$")  # m, s, kg, m/s², km/h, Ω, °C, kWh
_UNIDADES_LARGAS = {
    "metro", "metros", "centímetros", "milímetros", "kilómetros", "segundo", "segundos", "minuto",
    "minutos", "hora", "horas", "gramo", "gramos", "kilogramos", "kilos", "litro", "litros", "volt",
    "volts", "voltios", "ampere", "amperes", "amperios", "ohm", "ohms", "ohmios", "watt", "watts",
    "vatios", "joule", "joules", "newton", "newtons", "pascal", "pascales", "grado", "grados", "veces",
}  # fmt: skip
_NO_SON_UNIDADES = {
    "y",
    "o",
    "u",
    "e",
    "a",
    "al",
    "de",
    "del",
    "en",
    "es",
    "la",
    "el",
    "lo",
    "los",
    "las",
    "un",
    "una",
    "que",
    "con",
    "por",
    "se",
    "si",
    "no",
    "ni",
    "su",
    "sus",
    "más",
    "mas",
}


def _proteger(texto_: str, atomicos: tuple[str, ...]) -> str:
    """Une con espacios fijos las frases que no se deben cortar."""
    tramos: list[tuple[int, int]] = []
    for frase in atomicos:
        if frase:
            tramos += [(m.start(), m.end()) for m in re.finditer(re.escape(frase), texto_)]
    tramos += [(m.start(), m.end()) for m in _EXPRESION.finditer(texto_)]
    for m in _NUMERO_Y_PALABRA.finditer(texto_):
        palabra = m.group(1).rstrip(".,;:!?)")
        es_unidad = palabra.lower() in _UNIDADES_LARGAS or (
            bool(_UNIDAD_CORTA.match(palabra)) and palabra.lower() not in _NO_SON_UNIDADES
        )
        if es_unidad:
            tramos.append((m.start(), m.end()))
    if not tramos:
        return texto_
    unidos: list[list[int]] = []
    for ini, fin in sorted(tramos):  # fusionar tramos que se tocan
        if unidos and ini <= unidos[-1][1]:
            unidos[-1][1] = max(unidos[-1][1], fin)
        else:
            unidos.append([ini, fin])
    piezas, cursor = [], 0
    for ini, fin in unidos:
        piezas += [texto_[cursor:ini], texto_[ini:fin].replace(" ", _ESPACIO_FIJO)]
        cursor = fin
    return "".join(piezas) + texto_[cursor:]


def envolver(
    texto: str, tam: float, peso: str, ancho_max: float, atomicos: tuple[str, ...] = ()
) -> list[str]:
    """Corta el texto en líneas que caben en ``ancho_max``. Las frases ``atomicos``, las
    expresiones matemáticas y los números con su unidad no se parten."""
    lineas: list[str] = []
    for parrafo_ in texto.split("\n"):
        protegido = _proteger(" ".join(parrafo_.split()), atomicos)
        actual = ""
        for palabra in protegido.split(" "):
            candidato = f"{actual} {palabra}".strip()
            if actual and ancho_texto(candidato.replace(_ESPACIO_FIJO, " "), tam, peso) > ancho_max:
                lineas.append(actual)
                actual = palabra
            else:
                actual = candidato
        if actual:
            lineas.append(actual)
    return [linea.replace(_ESPACIO_FIJO, " ") for linea in lineas] or [""]


def envolver_equilibrado(
    texto_: str, tam: float, peso: str, ancho_max: float, atomicos: tuple[str, ...] = ()
) -> list[str]:
    """Como ``envolver`` pero con líneas de largo parejo (sin una palabra sola al final).
    Ideal para títulos y textos centrados."""
    voraz = envolver(texto_, tam, peso, ancho_max, atomicos)
    n = len(voraz)
    if n < 2 or "\n" in texto_:
        return voraz
    palabras = _proteger(" ".join(texto_.split()), atomicos).split(" ")
    m = len(palabras)
    if m > 40:
        return voraz

    @functools.cache
    def ancho(i: int, j: int) -> float:
        return ancho_texto(" ".join(palabras[i:j]).replace(_ESPACIO_FIJO, " "), tam, peso)

    # Con la misma cantidad de líneas, el reparto más parejo es el que minimiza la suma de los
    # cuadrados de los anchos (equivale a minimizar la varianza, porque el total es fijo).
    # mejor[k][j]: costo mínimo de repartir las j primeras palabras en k líneas que caben.
    infinito = float("inf")
    mejor = [[infinito] * (m + 1) for _ in range(n + 1)]
    corte = [[0] * (m + 1) for _ in range(n + 1)]
    mejor[0][0] = 0.0
    for k in range(1, n + 1):
        for j in range(k, m + 1):
            for i in range(k - 1, j):
                w = ancho(i, j)
                if w > ancho_max or mejor[k - 1][i] == infinito:
                    continue
                valor = mejor[k - 1][i] + w * w
                if valor < mejor[k][j]:
                    mejor[k][j], corte[k][j] = valor, i
    if mejor[n][m] == infinito:
        return voraz
    lineas, j = [], m
    for k in range(n, 0, -1):
        i = corte[k][j]
        lineas.append(" ".join(palabras[i:j]).replace(_ESPACIO_FIJO, " "))
        j = i
    return lineas[::-1]


def texto(contenido: str, tam: float, peso: str = SEMIBOLD, color: str = "#FFFFFF") -> Text:
    return Text(contenido, font=FUENTE, weight=peso, font_size=tam, color=color)


def parrafo(
    contenido: str,
    tam: float,
    peso: str = SEMIBOLD,
    color: str = "#FFFFFF",
    ancho_max: float = ANCHO_UTIL,
    alineacion: str = "center",
    destacar: list[str] | tuple[str, ...] = (),
    color_destacado: str | None = None,
    interlineado: float = 0.5,
    max_lineas: int | None = None,
) -> Paragraph:
    """Párrafo con saltos de línea automáticos. Guarda ``.lineas_texto`` para ubicar frases.

    ``interlineado``: espacio extra entre líneas como fracción del tamaño de letra.
    ``max_lineas``: si el texto ocupa más líneas, la letra se achica (hasta un 30 %)."""
    destacar = tuple(f for f in destacar if f)
    # Líneas de largo parejo: evita una palabra sola al final (ej. "m/s²." huérfano).
    lineas = envolver_equilibrado(contenido, tam, peso, ancho_max, atomicos=destacar)
    minimo = tam * 0.7
    while max_lineas and len(lineas) > max_lineas and tam * 0.93 >= minimo:
        tam *= 0.93
        lineas = envolver_equilibrado(contenido, tam, peso, ancho_max, atomicos=destacar)
    t2c = {f: color_destacado for f in destacar if color_destacado and any(f in linea for linea in lineas)}
    p = Paragraph(
        *lineas,
        font=FUENTE,
        weight=peso,
        font_size=tam,
        color=color,
        alignment=alineacion,
        t2c=t2c,
        line_spacing=interlineado,
        disable_ligatures=True,  # así cada letra es un objeto y se puede ubicar cada frase
    )
    if p.width > ancho_max:
        p.scale_to_fit_width(ancho_max)
    p.lineas_texto = lineas
    return p


def frase_en_parrafo(p: Paragraph, frase: str) -> VGroup:
    """Las letras de ``frase`` dentro del párrafo (todas sus apariciones)."""
    grupo = VGroup()
    for linea_mob, linea_txt in zip(p, getattr(p, "lineas_texto", []), strict=False):
        desde = 0
        while (idx := linea_txt.find(frase, desde)) >= 0:
            grupo.add(VGroup(*linea_mob[idx : idx + len(frase)]))
            desde = idx + len(frase)
    return grupo


def numeros_en(contenido: str) -> list[str]:
    """Palabras con números (para destacarlas en el gancho), ej. '20', '9,8', '45°'."""
    return [m.strip("¿?¡!.,;:") for m in re.findall(r"\S*\d\S*", contenido)]


# ------------------------------------------------------------------------------------------
# Fórmulas
# ------------------------------------------------------------------------------------------


def ecuacion(
    tex: str, tam: float = TAM_ECUACION, color: str = "#FFFFFF", ancho_max: float = ANCHO_UTIL
) -> MathTex:
    """Fórmula dividida en partes (para animar cada término). Si la división falla, usa una sola."""
    tex = corregir_decimales(tex)
    piezas = partes(tex)
    registro = logging.getLogger("manim")
    nivel = registro.level
    try:
        if len(piezas) > 1:
            registro.setLevel(logging.CRITICAL)  # el primer intento puede fallar sin asustar a nadie
            try:
                eq = MathTex(*piezas, font_size=tam, color=color)
            except Exception:
                eq = None
            finally:
                registro.setLevel(nivel)
        else:
            eq = None
        if eq is None:
            eq = MathTex(tex, font_size=tam, color=color)
    except Exception as e:
        raise ErrorMotor(
            f"No pude dibujar la fórmula: {tex}",
            ayuda="Revisa el LaTeX (llaves { }, comandos con \\). Puedes probarla en https://www.overleaf.com",
        ) from e
    if eq.width > ancho_max:
        eq.scale_to_fit_width(ancho_max)
    return eq


_ESPACIOS_TEX = re.compile(r"\\[,;:!]|\\quad|\\qquad|\\ |\s+")
_TRIVIALES = {"=", "+", "-", "(", ")", r"\cdot", r"\times"}


def coincidencias(origen: MathTex, destino: MathTex) -> dict[str, str] | None:
    """``key_map`` para ``TransformMatchingTex`` si las fórmulas comparten algún término real
    (no basta con el "="). Ignora espacios de LaTeX como ``\\,``. None = no conviene transformar."""

    def normal(t: str) -> str:
        return _ESPACIOS_TEX.sub("", t)

    claves_origen = {
        p.tex_string: normal(p.tex_string) for p in origen.submobjects if hasattr(p, "tex_string")
    }
    claves_destino = {
        normal(p.tex_string): p.tex_string for p in destino.submobjects if hasattr(p, "tex_string")
    }
    comunes = {n for n in claves_origen.values() if n in claves_destino and n not in _TRIVIALES}
    if not comunes:
        return None
    return {
        crudo: claves_destino[n]
        for crudo, n in claves_origen.items()
        if n in claves_destino and crudo != claves_destino[n]
    }


def partes_por_tex(eq: MathTex, buscado: str) -> list[Mobject]:
    """Partes de la fórmula que coinciden con ``buscado`` (exacto o contenido)."""
    buscado = corregir_decimales(buscado).strip()
    exactas = [p for p in eq.submobjects if getattr(p, "tex_string", "").strip() == buscado]
    if exactas:
        return exactas
    return [p for p in eq.submobjects if buscado and buscado in getattr(p, "tex_string", "")]


# ------------------------------------------------------------------------------------------
# Formas
# ------------------------------------------------------------------------------------------


def engranaje(radio: float, color: str, color_agujero: str, dientes: int = 10) -> VGroup:
    """Engranaje simple (ícono de marca 'industrial')."""
    externo, interno = radio, radio * 0.78
    puntos = []
    for k in range(dientes):
        a0 = TAU * k / dientes
        paso = TAU / dientes
        for fraccion, r in ((0.0, interno), (0.14, externo), (0.46, externo), (0.6, interno)):
            a = a0 + paso * fraccion
            puntos.append([r * np.cos(a), r * np.sin(a), 0])
    cuerpo = Polygon(*puntos).set_fill(color, 1).set_stroke(width=0)
    agujero = Circle(radius=radio * 0.34).set_fill(color_agujero, 1).set_stroke(width=0)
    return VGroup(cuerpo, agujero)


def chip(contenido: str, color: str, tam: float = 19) -> VGroup:
    etiqueta = texto(contenido, tam, ULTRABOLD, color)
    caja = RoundedRectangle(corner_radius=0.18, width=etiqueta.width + 0.42, height=etiqueta.height + 0.26)
    caja.set_fill(color, 0.14).set_stroke(color, 2, 0.9)
    etiqueta.move_to(caja)
    return VGroup(caja, etiqueta)


def tarjeta(contenido: Mobject, ancho: float, relleno: str, borde: str, margen: float = 0.4) -> VGroup:
    """Panel redondeado con el contenido alineado a la izquierda."""
    caja = RoundedRectangle(corner_radius=0.28, width=ancho, height=contenido.height + 2 * margen)
    caja.set_fill(relleno, 0.94).set_stroke(borde, 2.5)
    contenido.move_to(caja)
    contenido.align_to(caja.get_left() + RIGHT * margen, LEFT)
    return VGroup(caja, contenido)


def visto(color: str, escala: float = 0.32) -> VMobject:
    marca = VMobject()
    marca.set_points_as_corners([[-0.5, 0.05, 0], [-0.12, -0.35, 0], [0.55, 0.45, 0]])
    return marca.scale(escala).set_stroke(color, 7)


def subrayado(objetivo: Mobject, color: str, grosor: float = 6, separacion: float = 0.1) -> Line:
    inicio = objetivo.get_corner(DOWN + LEFT) + DOWN * separacion
    fin = objetivo.get_corner(DOWN + RIGHT) + DOWN * separacion
    return Line(inicio, fin).set_stroke(color, grosor)


def fondo_cuadricula(color: str, paso: float = 0.6) -> VGroup:
    """Cuadrícula tenue tipo plano técnico."""
    lineas = VGroup()
    for x in np.arange(-4.5, 4.5 + 1e-6, paso):
        lineas.add(Line([x, -8, 0], [x, 8, 0]))
    for y in np.arange(-8, 8 + 1e-6, paso):
        lineas.add(Line([-4.5, y, 0], [4.5, y, 0]))
    return lineas.set_stroke(color, width=1, opacity=0.07)
