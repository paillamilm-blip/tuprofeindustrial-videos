"""Piezas visuales reutilizables para el formato vertical 9:16.

El cuadro de Manim mide 9 unidades de ancho × 16 de alto (1 unidad = 120 px en 1080×1920),
con el origen al centro: arriba y = 8, abajo y = −8.

Zonas del marco "pizarra" (de arriba hacia abajo):
- y ≈ 6.5      cabecera con la marca y la materia
- y ≈ 5.5      título del ejercicio
- 4.7 … −2.4   zona de contenido (enunciado, datos, pasos, resultado)
- y ≈ −3.5     subtítulos estilo CapCut (los quema FFmpeg después)
- y < −4.8     se deja libre: ahí van los botones y textos de TikTok/Reels/Shorts

El marco "hoja" (Hoja de desarrollo) pone todo dentro de una hoja cuadriculada (y de 5.9 a −5.7), con
los subtítulos dentro de la hoja, abajo (y ≈ −4.5).
"""

from __future__ import annotations

import functools
import logging
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    BOLD,
    DL,
    DOWN,
    DR,
    HEAVY,
    LEFT,
    MEDIUM,
    RIGHT,
    SEMIBOLD,
    TAU,
    UL,
    ULTRABOLD,
    UP,
    UR,
    Animation,
    Arrow,
    Circle,
    Create,
    FadeIn,
    GrowFromEdge,
    Group,
    ImageMobject,
    Line,
    MarkupText,
    MathTex,
    Mobject,
    Paragraph,
    Polygon,
    Rectangle,
    RoundedRectangle,
    Text,
    VGroup,
    VMobject,
    Write,
)

from . import tipografia
from .errores import ErrorMotor
from .guion import sin_tildes
from .tex import agrupar_argumentos, corregir_decimales, partes

# ------------------------------------------------------------------------------------------
# Estilo activo (lo fija `usar_estilo` al comenzar cada video). Vive en un ContextVar: cada hilo
# ve el suyo, así dos renders del mismo proceso no se pisan. Sin tema, manda "Pizarra nocturna".
# ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rol:
    familia: str = "Montserrat"
    grosor: str = "conservar"  # "conservar" = usar el grosor que pide cada texto
    escala: float = 1.0


@dataclass(frozen=True)
class _Estilo:
    """Tipografía y diagramación de un tema, ya resueltas (sin volver a leer el YAML)."""

    titulos: Rol = Rol()
    texto: Rol = Rol()
    ancho_util: float = 7.6
    y_cabecera: float = 6.55
    y_titulo: float = 5.55
    y_zona_superior: float = 4.75
    y_zona_inferior: float = -2.4
    banda_subtitulo: float = 0.28
    aire_dibujo: float = 0.28

    @property
    def centro_zona(self) -> float:
        return (self.y_zona_superior + self.y_zona_inferior) / 2

    @property
    def alto_zona(self) -> float:
        return self.y_zona_superior - self.y_zona_inferior


_PESOS_TITULO = {HEAVY, ULTRABOLD, BOLD}

# Nombres de siempre, que siguen leyéndose como atributos del módulo (``c.Y_CABECERA``) y que ahora
# resuelven contra el estilo del contexto en vez de contra una variable global.
_NOMBRES_DE_SIEMPRE = {
    "ANCHO_UTIL": "ancho_util",
    "Y_CABECERA": "y_cabecera",
    "Y_TITULO": "y_titulo",
    "Y_ZONA_SUPERIOR": "y_zona_superior",
    "Y_ZONA_INFERIOR": "y_zona_inferior",
    "CENTRO_ZONA": "centro_zona",
    "ALTO_ZONA": "alto_zona",
    "BANDA_SUBTITULO": "banda_subtitulo",
    "AIRE_DIBUJO": "aire_dibujo",
}

_ESTILO: ContextVar[_Estilo | None] = ContextVar("tpi_estilo", default=None)


def __getattr__(nombre: str) -> Any:
    campo = _NOMBRES_DE_SIEMPRE.get(nombre)
    if campo is None:
        raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
    return getattr(estilo_activo(), campo)


def estilo_activo() -> _Estilo:
    """El estilo del tema que se está renderizando, o el de siempre si nadie fijó uno."""
    return _ESTILO.get() or _Estilo()


# Marco "hoja": la hoja cuadriculada ocupa casi todo el cuadro; los subtítulos van dentro, abajo.
HOJA_ANCHO, HOJA_ALTO, HOJA_CENTRO_Y = 7.9, 11.6, 0.1
_ZONAS = {
    "pizarra": {"ANCHO_UTIL": 7.6, "Y_CABECERA": 6.55, "Y_TITULO": 5.55, "Y_ZONA_SUPERIOR": 4.75,
                "Y_ZONA_INFERIOR": -2.4},
    "hoja": {"ANCHO_UTIL": 7.0, "Y_CABECERA": 6.5, "Y_TITULO": 4.78, "Y_ZONA_SUPERIOR": 4.15,
             "Y_ZONA_INFERIOR": -3.55},
}  # fmt: skip


def ancho_util_de(tema) -> float:
    """Lo más ancho que se dibuja en ese marco: una cámara que se acerque más lo recorta."""
    return _ZONAS[tema.marco]["ANCHO_UTIL"]


def _del_tema(tema) -> _Estilo:
    t = tema.tipografia
    z = _ZONAS[tema.marco]
    layout = getattr(tema, "layout", None)

    def zona(campo: str, clave: str) -> float:
        """Lo que pide el tema; si no lo pide, lo del marco (pizarra u hoja)."""
        elegido = getattr(layout, campo, None) if layout is not None else None
        return float(z[clave] if elegido is None else elegido)

    return _Estilo(
        titulos=Rol(t.titulos.familia, t.titulos.grosor, t.titulos.escala),
        texto=Rol(t.texto.familia, t.texto.grosor, t.texto.escala),
        ancho_util=z["ANCHO_UTIL"],
        y_cabecera=zona("y_cabecera", "Y_CABECERA"),
        y_titulo=z["Y_TITULO"],
        y_zona_superior=zona("y_zona_enunciado", "Y_ZONA_SUPERIOR"),
        y_zona_inferior=zona("y_zona_pasos", "Y_ZONA_INFERIOR"),
        banda_subtitulo=float(getattr(layout, "banda_subtitulo", 0.28) if layout is not None else 0.28),
        aire_dibujo=float(getattr(layout, "aire_dibujo", 0.28) if layout is not None else 0.28),
    )


def usar_estilo(tema) -> Token[_Estilo]:
    """Fija tipografía y diagramación del tema en el contexto actual (ver ``temas.Tema``)."""
    return _ESTILO.set(_del_tema(tema))


def restablecer_estilo(token: Token[_Estilo]) -> None:
    """Deshace un ``usar_estilo``: vuelve al estilo que había antes en este contexto."""
    _ESTILO.reset(token)


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


def _letra(peso: str) -> tuple[str, str, float]:
    """(familia, grosor real, escala) para un texto que pide ``peso``.

    Los pesos fuertes (títulos, etiquetas, marca) usan la letra de títulos; el resto, la de texto."""
    est = estilo_activo()
    rol = est.titulos if peso in _PESOS_TITULO else est.texto
    grosor = peso if rol.grosor == "conservar" else rol.grosor
    return rol.familia, tipografia.grosor_disponible(rol.familia, grosor), rol.escala


def ancho_texto(texto: str, tam: float, peso: str) -> float:
    """Ancho aproximado (en unidades de Manim) de una línea de texto (``tam`` ya escalado)."""
    familia, grosor, _ = _letra(peso)
    try:
        pil = tipografia.fuente_pil(familia, grosor)
        return pil.getlength(texto) * tipografia.unidades_por_pixel(familia, grosor) * tam / 100
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


def texto(
    contenido: str, tam: float, peso: str = SEMIBOLD, color: str = "#FFFFFF", mayus: bool = False
) -> Text:
    familia, grosor, escala = _letra(peso)
    if mayus:
        contenido = contenido.upper()
    return Text(contenido, font=familia, weight=grosor, font_size=tam * escala, color=color)


def _resaltados_sin_solapamiento(frases: tuple[str, ...]) -> list[str]:
    """Los tramos a resaltar, sin ninguno metido dentro de otro.

    Manim lanza «Ambiguous style» si dos resaltos comparten letras, aunque el color sea
    el mismo (text_mobject.py `_merge_settings`). Gana el trecho más largo: en «6, 8 y 48»
    el «8» suelto queda cubierto por el «48», que también lo pinta.
    """
    largos: list[str] = []
    for frase in sorted(set(frases), key=len, reverse=True):
        if not any(frase in k for k in largos):
            largos.append(frase)
    return largos


def parrafo(
    contenido: str,
    tam: float,
    peso: str = SEMIBOLD,
    color: str = "#FFFFFF",
    ancho_max: float | None = None,
    alineacion: str = "center",
    destacar: list[str] | tuple[str, ...] = (),
    color_destacado: str | None = None,
    interlineado: float = 0.5,
    max_lineas: int | None = None,
    mayus: bool = False,
) -> Paragraph:
    """Párrafo con saltos de línea automáticos. Guarda ``.lineas_texto`` para ubicar frases.

    ``interlineado``: espacio extra entre líneas como fracción del tamaño de letra.
    ``max_lineas``: si el texto ocupa más líneas, la letra se achica (hasta un 30 %).
    ``mayus``: todo en mayúsculas (las frases a destacar también)."""
    ancho_max = estilo_activo().ancho_util if ancho_max is None else ancho_max
    familia, grosor, escala = _letra(peso)
    tam = tam * escala
    if mayus:
        contenido = contenido.upper()
        destacar = [f.upper() for f in destacar]
    destacar = tuple(f for f in destacar if f)
    # Líneas de largo parejo: evita una palabra sola al final (ej. "m/s²." huérfano).
    lineas = envolver_equilibrado(contenido, tam, peso, ancho_max, atomicos=destacar)
    minimo = tam * 0.7
    while max_lineas and len(lineas) > max_lineas and tam * 0.93 >= minimo:
        tam *= 0.93
        lineas = envolver_equilibrado(contenido, tam, peso, ancho_max, atomicos=destacar)
    t2c = {
        f: color_destacado
        for f in (_resaltados_sin_solapamiento(destacar) if color_destacado else ())
        if any(f in linea for linea in lineas)
    }
    p = Paragraph(
        *lineas,
        font=familia,
        weight=grosor,
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
    p.mayus = mayus
    return p


def frase_en_parrafo(p: Paragraph, frase: str) -> VGroup:
    """Las letras de ``frase`` dentro del párrafo (todas sus apariciones)."""
    if getattr(p, "mayus", False):
        frase = frase.upper()
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


_HASTA_VEINTINUEVE = (
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
    "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
    "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco",
    "veintiséis", "veintisiete", "veintiocho", "veintinueve",
)  # fmt: skip
_DECENAS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta",
            80: "ochenta", 90: "noventa"}  # fmt: skip
_CENTENAS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
             6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}  # fmt: skip


def _tres_cifras(n: int) -> str:
    """0..999 dicho en español: del 16 al 29 se escribe junto y de 31 en adelante lleva «y»."""
    if n < 30:
        return _HASTA_VEINTINUEVE[n]
    centena, resto = divmod(n, 100)
    if centena:
        if resto == 0:
            return "cien" if centena == 1 else _CENTENAS[centena]
        return f"{_CENTENAS[centena]} {_tres_cifras(resto)}"
    decena, unidad = divmod(resto, 10)
    if unidad == 0:
        return _DECENAS[decena * 10]
    return f"{_DECENAS[decena * 10]} y {_HASTA_VEINTINUEVE[unidad]}"


def _hasta_el_millon(n: int) -> str:
    """0..999 999: los miles se agrupan de a tres y el «mil» suelto no lleva «uno» delante."""
    if n < 1000:
        return _tres_cifras(n)
    millar, resto = divmod(n, 1000)
    nombre = "mil" if millar == 1 else f"{_tres_cifras(millar)} mil"
    return nombre if resto == 0 else f"{nombre} {_tres_cifras(resto)}"


def numero_en_palabras(frase: str) -> str | None:
    """Cómo se dice una frase que es un número: '12' → 'doce', '9,8' → 'nueve coma ocho'.

    Devuelve ``None`` para lo que la voz no lee como número entero o decimal con coma: un número
    escrito con puntos de miles no se inventa, porque ahí el resaltado tiene más chances de
    equivocarse que de acertar.
    """
    cifra = re.fullmatch(r"(\d{1,6})(?:,(\d+))?°?", frase.strip())
    if not cifra:
        return None
    dicho = _hasta_el_millon(int(cifra.group(1)))
    if cifra.group(2):
        dicho += " coma " + " ".join(_HASTA_VEINTINUEVE[int(d)] for d in cifra.group(2))
    return dicho


def busca_en_la_voz(texto: str, frase: str) -> int:
    """Dónde suena ``frase`` dentro de la transcripción de la voz, o -1 si no se dijo.

    Primero se busca tal cual está escrita. Si no está y la frase es un número, se busca dicho: el
    gancho se escribe «12» pero la voz lo lee «doce», y ahí el resaltado nunca sonaba.
    """
    base = sin_tildes(texto.lower())
    aguja = sin_tildes(frase.lower())
    if aguja and base.find(aguja) >= 0:
        return base.find(aguja)
    dicho = numero_en_palabras(frase)
    if dicho is None:
        return -1
    # «1» se dice «un» cuando acompaña: «avanza un centímetro», no «avanza uno centímetro».
    encontrada = re.search(rf"\b{re.escape(sin_tildes(dicho))}\b", base)
    if encontrada:
        return encontrada.start()
    if dicho != "uno":
        return -1
    # Con más de un «un» no hay forma de saber cuál es el número («Un vector avanza 1 cm» tiene
    # dos), y resaltar el equivocado es peor que no resaltar.
    unos = list(re.finditer(r"\bun\b", base))
    return unos[0].start() if len(unos) == 1 else -1


# ------------------------------------------------------------------------------------------
# Fórmulas
# ------------------------------------------------------------------------------------------


def ecuacion(
    tex: str, tam: float = TAM_ECUACION, color: str = "#FFFFFF", ancho_max: float | None = None,
    *, aislar: list[str] | None = None,
) -> MathTex:
    """Fórmula dividida en partes (para animar cada término). Si la división falla, usa una sola."""
    ancho_max = estilo_activo().ancho_util if ancho_max is None else ancho_max
    tex = corregir_decimales(tex)
    piezas = partes(tex)
    registro = logging.getLogger("manim")
    nivel = registro.level
    try:
        if aislar:
            tex = agrupar_argumentos(tex)
            espacio = r"(?:\\[,;:!]|\\quad|\\qquad|\\ |\s)*"
            patrones = [espacio.join(re.escape(ch) for ch in _ESPACIOS_TEX.sub("", agrupar_argumentos(corregir_decimales(t))))
                        for t in sorted(set(aislar), key=len, reverse=True)]
            patron = re.compile("(?P<termino>" + "|".join(patrones) + r")|\\[a-zA-Z]+")
            segmentos: list[str] = []
            desde = 0
            for match in patron.finditer(tex):
                if match.group("termino") is None:
                    continue
                if match.start() > desde:
                    segmentos.append(tex[desde:match.start()])
                segmentos.append(match.group())
                desde = match.end()
            if desde < len(tex):
                segmentos.append(tex[desde:])
            eq = MathTex(*segmentos, arg_separator="", font_size=tam, color=color)
        elif len(piezas) > 1:
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


def terminos_nuevos(origen: Mobject | None, destino: MathTex) -> list[Mobject]:
    """Las partes de ``destino`` que no estaban en ``origen``: lo que la transformación trae nuevo.

    Se compara el texto sin espacios de LaTeX y se ignoran los signos sueltos («=», «+»…): que
    aparezca otro «=» no es un cambio que valga la pena iluminar.
    """
    if origen is None:
        return []

    def normal(t: str) -> str:
        return _ESPACIOS_TEX.sub("", t)

    antes = {normal(p.tex_string) for p in origen.submobjects if hasattr(p, "tex_string")}
    return [
        p
        for p in destino.submobjects
        if hasattr(p, "tex_string")
        and normal(p.tex_string)
        and normal(p.tex_string) not in antes
        and normal(p.tex_string) not in _TRIVIALES
    ]


def halo_de(parte: Mobject, color: str) -> VGroup:
    """Un resplandor suave detrás de un término: tres capas redondeadas que se apagan hacia afuera."""
    capas = VGroup()
    for holgura, opacidad in ((0.26, 0.07), (0.16, 0.13), (0.08, 0.24)):
        capa = RoundedRectangle(
            corner_radius=0.12 + holgura / 2,
            width=parte.width + 2 * holgura,
            height=parte.height + 2 * holgura,
        )
        capa.set_fill(color, opacidad).set_stroke(width=0).move_to(parte.get_center())
        capas.add(capa)
    return capas.set_z_index(0)


def tacha_de(parte: Mobject, color: str) -> Line:
    """Una raya en diagonal sobre un término que se cancela o se va al otro lado."""
    return (
        Line(parte.get_corner(DL) + LEFT * 0.04, parte.get_corner(UR) + RIGHT * 0.04)
        .set_stroke(color, 6)
        .set_z_index(3)
    )


def partes_por_tex(eq: MathTex, buscado: str) -> list[Mobject]:
    """Partes de la fórmula que coinciden con ``buscado``: exacta, contenida en una parte o, si no,
    varias partes seguidas (ej. '5x + 5x', que la fórmula divide en '5x', '+', '5x')."""
    buscado = corregir_decimales(buscado).strip()
    exactas = [p for p in eq.submobjects if getattr(p, "tex_string", "").strip() == buscado]
    if exactas:
        return exactas
    agrupado = agrupar_argumentos(buscado)
    exactas = [p for p in eq.submobjects if getattr(p, "tex_string", "").strip() == agrupado]
    if exactas:
        return exactas
    contenidas = [p for p in eq.submobjects if buscado and buscado in getattr(p, "tex_string", "")]
    if contenidas or not buscado:
        return contenidas
    objetivo = _ESPACIOS_TEX.sub("", buscado)
    piezas = [p for p in eq.submobjects if hasattr(p, "tex_string")]
    for i in range(len(piezas)):
        unido = ""
        for j in range(i, len(piezas)):
            unido += _ESPACIOS_TEX.sub("", piezas[j].tex_string)
            if unido == objetivo:
                return piezas[i : j + 1]
            if not objetivo.startswith(unido):
                break
    return []


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
    """Panel redondeado con el contenido alineado a la izquierda y su sombra detrás (``tarjeta[0]``).

    La sombra se ve sobre papeles claros; en un panel oscuro queda transparente, pero el hijo existe
    igual para que todas las tarjetas tengan la misma forma y el contenido siga siendo el último.
    """
    caja = RoundedRectangle(corner_radius=0.28, width=ancho, height=contenido.height + 2 * margen)
    caja.set_fill(relleno, 0.94).set_stroke(borde, 2.5)
    sombra = RoundedRectangle(corner_radius=0.3, width=ancho, height=caja.height)
    sombra.set_fill("#000000", 0.16 if _luminancia(relleno) > 0.45 else 0.0).set_stroke(width=0)
    sombra.shift(DOWN * 0.1 + RIGHT * 0.05)
    contenido.move_to(caja)
    contenido.align_to(caja.get_left() + RIGHT * margen, LEFT)
    return VGroup(VGroup(sombra, caja), contenido)


def visto(color: str, escala: float = 0.32) -> VMobject:
    marca = VMobject()
    marca.set_points_as_corners([[-0.5, 0.05, 0], [-0.12, -0.35, 0], [0.55, 0.45, 0]])
    return marca.scale(escala).set_stroke(color, 7)


def tabs_de_pasos(n: int, activo: int, paleta: list[str]) -> VGroup:
    """Una pestaña numerada por paso con el color de la paleta; la activa brilla y el resto se atenúa."""
    tabs = VGroup()
    for k in range(1, n + 1):
        color = paleta[(k - 1) % len(paleta)]
        tabs.add(chip(str(k), color, tam=16))
    tabs.arrange(RIGHT, buff=0.18)
    activar_tab(tabs, activo)
    return tabs


def activar_tab(tabs: VGroup, activo: int) -> None:
    """Deja la pestaña ``activo`` a full y las demás tenues; idempotente (se llama en cada paso)."""
    for k, tab in enumerate(tabs, 1):
        caja, numero = tab[0], tab[1]
        if k == activo:
            caja.set_fill(opacity=0.22).set_stroke(opacity=1.0)
            numero.set_fill(opacity=1.0)
        else:
            caja.set_fill(opacity=0.05).set_stroke(opacity=0.3)
            numero.set_fill(opacity=0.4)


def panel_persistente(
    total: int, cerrados: list[str], paleta: list[str], ancho: float, relleno: str, borde: str,
    *, completados: int | None = None,
) -> VGroup:
    """El segundo panel de XCris: contador de paso, barra de progreso y las últimas fórmulas cerradas.

    Se reconstruye en cada paso con la lista acumulada (no se resetea): el contenido vive en ``panel[1]``
    (``[0]`` contador, ``[1]`` barra, ``[2]`` mini-fórmulas), porque ``tarjeta`` envuelve el contenido.
    """
    k = len(cerrados) if completados is None else completados
    color = paleta[min(k, max(0, total - 1)) % len(paleta)] if paleta else "#FFFFFF"
    contador = texto(f"paso {min(k + 1, total)} de {total}", 16, ULTRABOLD, color)
    pista = Rectangle(width=ancho - 1.2, height=0.12).set_fill(borde, 0.5).set_stroke(width=0)
    lleno = Rectangle(width=max(0.02, pista.width * (k / total if total else 0.0)), height=0.12)
    lleno.set_fill(color, 0.95).set_stroke(width=0)
    lleno.align_to(pista, LEFT).align_to(pista, UP)
    mini = VGroup(*[ecuacion(t, 20, "#FFFFFF", ancho_max=ancho - 1.2) for t in cerrados[-3:]])
    mini.arrange(DOWN, buff=0.12, aligned_edge=LEFT)
    contenido = VGroup(contador, VGroup(pista, lleno), mini).arrange(DOWN, buff=0.16, aligned_edge=LEFT)
    return tarjeta(contenido, ancho, relleno, borde)


def mapa_de_color(eq: MathTex, mapa: list, paleta: list[str]) -> VGroup:
    """Por cada término del mapa, una etiqueta de concepto y una flecha del color que lo une a la fórmula.

    Un término que no está en la fórmula se omite (la validación del guion ya lo impide, pero el
    componente no revienta si llega igual). El color propio del mapa manda sobre la paleta.
    """
    etiquetas = VGroup()
    objetivos: list[Mobject] = []
    colores: list[str] = []
    for j, m in enumerate(mapa):
        color = m.color or paleta[j % len(paleta)]
        termino = agrupar_argumentos(corregir_decimales(m.termino))
        objetivo = eq.get_part_by_tex(termino)
        if objetivo is None:
            partes = partes_por_tex(eq, m.termino)
            if not partes:
                continue
            objetivo = VGroup(*partes)
        objetivo.set_color(color)
        eq.set_color_by_tex(termino, color)
        etiquetas.add(chip(m.concepto, color, tam=15))
        objetivos.append(objetivo)
        colores.append(color)
    if not len(etiquetas):
        return VGroup()
    orden = sorted(range(len(objetivos)), key=lambda i: objetivos[i].get_center()[0])
    etiquetas = VGroup(*[etiquetas[i] for i in orden])
    objetivos = [objetivos[i] for i in orden]
    colores = [colores[i] for i in orden]
    etiquetas.arrange(RIGHT, buff=0.25)
    ancho = min(estilo_activo().ancho_util, max(eq.width, 3.0))
    if etiquetas.width > ancho:
        etiquetas.scale_to_fit_width(ancho)
    etiquetas.next_to(eq, DOWN, buff=0.6)
    grupo = VGroup()
    for etiqueta, objetivo, color in zip(etiquetas, objetivos, colores, strict=True):
        flecha = Arrow(etiqueta.get_top(), objetivo.get_bottom(), buff=0.12, color=color, stroke_width=4)
        grupo.add(VGroup(etiqueta, flecha))
    return grupo


def micro_movimiento(tipo: str, objetivo: Mobject) -> Animation:
    if tipo == "tick":
        marca = visto("#22C55E").scale_to_fit_width(objetivo.width * 0.22)
        if marca.height > objetivo.height * 0.24:
            marca.scale_to_fit_height(objetivo.height * 0.24)
        marca.set_stroke(width=2.5).align_to(objetivo, UR)
        marca.shift(LEFT * objetivo.width * 0.06 + DOWN * objetivo.height * 0.06)
        return Create(marca)
    if tipo == "barra":
        return GrowFromEdge(objetivo, LEFT)
    if tipo == "contador":
        return FadeIn(objetivo, shift=UP * 0.2)
    return Write(objetivo)


def gramatica_activa(tema) -> bool:
    g = tema.gramatica
    return bool(g.tabs or g.panel or g.mapa_color or g.micro)


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


# ------------------------------------------------------------------------------------------
# Fondos y marcos por tema
# ------------------------------------------------------------------------------------------


def _capa_fondo(tema) -> Mobject | None:
    """Imagen, degradado o cuadrícula de fondo (lo que hay detrás de todo)."""
    from .temas import ruta_fondo

    fondo = tema.fondo
    if fondo.tipo == "imagen":
        return ImageMobject(str(ruta_fondo(fondo.imagen))).scale_to_fit_height(16).set_z_index(-3)
    if fondo.tipo == "degradado":
        capa = Rectangle(width=9.2, height=16.2).set_stroke(width=0)
        return capa.set_fill(fondo.degradado, 1).set_sheen_direction(DOWN).set_z_index(-3)
    if fondo.tipo == "cuadricula":
        return fondo_cuadricula(tema.colores.cuadricula).set_z_index(-1)
    return None  # "color": basta el color de fondo del video


def fondo_tema(tema) -> Mobject:
    """Todo lo fijo del fondo según el tema. En "pizarra" con cuadrícula es idéntico al original."""
    capa = _capa_fondo(tema)
    if tema.marco == "hoja":
        return marco_hoja(tema, capa)
    return capa if capa is not None else VGroup()


def _luminancia(color: str) -> float:
    """Cuánto pesa un color (0 = negro, 1 = blanco), para decidir claro u oscuro encima."""
    r, g, b = (int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _legible_sobre(fondo: str, claro: str, oscuro: str) -> str:
    """Claro u oscuro según cuánto peso tenga el fondo (luminancia percibida).

    La etiqueta de la hoja vive fuera del papel, sobre ``colores.fondo``; medir ahí evita el blanco fijo
    que desaparecía en los temas de papel claro y el gris que desaparecía sobre el fondo oscuro.
    """
    return oscuro if _luminancia(fondo) > 0.45 else claro


def marco_hoja(tema, capa: Mobject | None = None) -> Group:
    """Fondo + "Notas" + "Fecha:" + hoja cuadriculada con encabezado, como en tus videos."""
    h = tema.hoja
    piezas: list[Mobject] = [capa] if capa is not None else []
    hoja = RoundedRectangle(corner_radius=0.42, width=HOJA_ANCHO, height=HOJA_ALTO)
    hoja.set_fill(h.color, 1).set_stroke(width=0).move_to([0, HOJA_CENTRO_Y, 0]).set_z_index(-2)
    piezas.append(hoja)
    if h.cuadricula:
        izq, der = hoja.get_left()[0] + 0.2, hoja.get_right()[0] - 0.2
        arr, aba = hoja.get_top()[1] - 0.2, hoja.get_bottom()[1] + 0.2
        lineas = VGroup()
        for x in np.arange(izq, der + 1e-6, 0.26):
            lineas.add(Line([x, aba, 0], [x, arr, 0]))
        for y in np.arange(aba, arr + 1e-6, 0.26):
            lineas.add(Line([izq, y, 0], [der, y, 0]))
        piezas.append(lineas.set_stroke(h.lineas, width=1.3).set_z_index(-1))
    if h.encabezado.strip():
        encabezado = MarkupText(
            f'<span letter_spacing="1600">{_escapar_markup(h.encabezado.strip())}</span>',
            font="Cinzel", font_size=26, color="#4A4A4A",
        )  # fmt: skip
        if encabezado.width > HOJA_ANCHO - 1.0:
            encabezado.scale_to_fit_width(HOJA_ANCHO - 1.0)
        piezas.append(encabezado.move_to([0, hoja.get_top()[1] - 0.42, 0]))
    # VGroup (no Group): la escena la disuelve al acercar la cámara, y la opacidad solo baja a los hijos.
    cinta = VGroup()
    if h.etiqueta.strip():
        etiqueta = Text(
            h.etiqueta.strip(),
            font="Montserrat",
            weight=MEDIUM,
            font_size=34,
            color=_legible_sobre(tema.colores.fondo, h.color, tema.colores.tenue),
        )
        cinta.add(etiqueta.move_to([0, 6.5, 0]).to_edge(LEFT, buff=0.6))
    if h.fecha.strip():
        pastilla = RoundedRectangle(corner_radius=0.25, width=2.3, height=0.5)
        pastilla.set_fill("#FFFFFF", 0.93).set_stroke(width=0).move_to([0, 6.5, 0]).to_edge(RIGHT, buff=0.6)
        fecha = Text(h.fecha.strip(), font="Montserrat", weight=MEDIUM, font_size=20, color="#555555")
        if fecha.width > 1.9:
            fecha.scale_to_fit_width(1.9)
        fecha.move_to(pastilla).align_to(pastilla, LEFT).shift(RIGHT * 0.22)
        cinta.add(pastilla, fecha)
    if len(cinta):
        piezas.append(cinta)
    fondo = Group(*piezas)
    fondo.cinta = cinta
    return fondo


def _escapar_markup(texto_: str) -> str:
    return texto_.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------------------------------
# Emojis, stickers y error típico
# ------------------------------------------------------------------------------------------


def imagen_emoji(valor: str | None, alto: float) -> ImageMobject | None:
    """El emoji 3D (o sticker propio) como imagen de ``alto`` unidades, o None."""
    from .emojis import resolver

    ruta: Path | None = resolver(valor)
    if ruta is None:
        return None
    return ImageMobject(str(ruta)).scale_to_fit_height(alto).set_z_index(3)


def tachado(objetivo: Mobject, color: str, grosor: float = 11, margen: float = 0.18) -> VGroup:
    """Una ✗ roja dibujada sobre ``objetivo`` (para el paso "error típico")."""
    sup_izq = objetivo.get_corner(UL) + (LEFT + UP) * margen
    inf_der = objetivo.get_corner(DR) + (RIGHT + DOWN) * margen
    sup_der = objetivo.get_corner(UR) + (RIGHT + UP) * margen
    inf_izq = objetivo.get_corner(DL) + (LEFT + DOWN) * margen
    cruz = VGroup(Line(sup_izq, inf_der), Line(sup_der, inf_izq)).set_stroke(color, grosor, 0.92)
    return cruz.set_z_index(2)
