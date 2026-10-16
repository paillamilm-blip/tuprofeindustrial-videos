"""Utilidades de LaTeX: plantilla mínima, coma decimal y división de fórmulas en partes.

Dividir una fórmula en partes ("h", "=", "\\frac{1}{2}", "g", "t^2") permite que
``TransformMatchingTex`` mueva cada término de un paso al siguiente: es la animación que
muestra *cómo* cambia la ecuación en vez de solo reemplazarla.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # importar Manim es lento: solo cuando de verdad se renderiza
    from manim import TexTemplate

# Plantilla mínima: solo amsmath/amssymb. La plantilla por defecto de Manim exige ~20 paquetes
# (babel-english, tipa, physics…) que BasicTeX no trae; esta funciona con
# `tlmgr install standalone preview dvisvgm`. (Sin fontenc T1: exigiría las fuentes cm-super.)
PREAMBULO = "\n".join(
    [
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath}",
        r"\usepackage{amssymb}",
        r"\boldmath",  # fórmulas en negrita: se leen mucho mejor en la pantalla de un celular
    ]
)
PREAMBULO_NORMAL = PREAMBULO.replace("\n\\boldmath", "")  # grosor normal (estilo Hoja de desarrollo)


def plantilla_tex(negrita: bool = True) -> TexTemplate:
    from manim import TexTemplate

    return TexTemplate(preamble=PREAMBULO if negrita else PREAMBULO_NORMAL)


_DECIMAL = re.compile(r"(?<=\d),(?=\d)")


def corregir_decimales(tex: str) -> str:
    """En Chile la coma es decimal: ``9,8`` → ``9{,}8`` (sin el espacio que LaTeX agrega)."""
    return _DECIMAL.sub("{,}", tex)


# Comandos que toman un argumento: si el autor escribe "\vec F" o "\frac {1}{2}" con espacio,
# el comando y su argumento deben quedar en la misma parte.
_CON_ARGUMENTO = {
    "frac", "dfrac", "tfrac", "cfrac", "sqrt", "vec", "hat", "bar", "overline", "underline",
    "widehat", "widetilde", "tilde", "dot", "ddot", "check", "breve", "acute", "grave",
    "mathrm", "mathbf", "mathit", "mathcal", "mathbb", "mathsf", "boldsymbol", "pmb",
    "text", "textbf", "textit", "operatorname", "overrightarrow", "binom", "dbinom",
    "stackrel", "overset", "underset", "boxed", "color", "textcolor",
    "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "biggl", "biggr",
}  # fmt: skip
_ESPACIADO = re.compile(r"^(\\[,;:! ]|\\quad|\\qquad|~)+$")
_COMANDO = re.compile(r"\\([a-zA-Z]+|.)")
_COMANDO_FINAL = re.compile(r"\\([a-zA-Z]+)$")


def _tokens_nivel_superior(tex: str) -> list[str]:
    """Corta en los espacios que no están dentro de llaves, \\left…\\right ni entornos."""
    tokens: list[str] = []
    actual = ""
    profundidad = 0
    i = 0
    while i < len(tex):
        c = tex[i]
        if c == "\\":
            m = _COMANDO.match(tex, i)
            comando = m.group(0) if m else c
            nombre = m.group(1) if m else ""
            if nombre in ("left", "begin"):
                profundidad += 1
            elif nombre in ("right", "end"):
                profundidad = max(0, profundidad - 1)
            actual += comando
            i += len(comando)
            continue
        if c == "{":
            profundidad += 1
        elif c == "}":
            profundidad = max(0, profundidad - 1)
        if c.isspace() and profundidad == 0:
            if actual:
                tokens.append(actual)
                actual = ""
        else:
            actual += c
        i += 1
    if actual:
        tokens.append(actual)
    return tokens


def _debe_unirse(anterior: str, siguiente: str) -> bool:
    if siguiente[0] in "^_{[" or anterior[-1] in "^_":
        return True
    m = _COMANDO_FINAL.search(anterior)
    return bool(m and m.group(1) in _CON_ARGUMENTO)


def partes(tex: str) -> list[str]:
    """Divide la fórmula en partes válidas para ``MathTex(*partes)``.

    Si el autor ya usó la notación ``{{ … }}`` de Manim, se respeta tal cual.
    """
    tex = tex.strip()
    if "{{" in tex or not tex:
        return [tex]
    unidos: list[str] = []
    pendiente_espaciado = ""
    for token in _tokens_nivel_superior(tex):
        if _ESPACIADO.match(token):  # "\," solo no dibuja nada: se pega a un vecino
            if unidos:
                unidos[-1] += " " + token
            else:
                pendiente_espaciado += token + " "
            continue
        token = pendiente_espaciado + token
        pendiente_espaciado = ""
        if unidos and _debe_unirse(unidos[-1], token):
            unidos[-1] += " " + token
        else:
            unidos.append(token)
    return unidos or [tex]


def llaves_balanceadas(tex: str) -> bool:
    profundidad = 0
    i = 0
    while i < len(tex):
        if tex[i] == "\\":
            i += 2  # \{ y \} no cuentan
            continue
        if tex[i] == "{":
            profundidad += 1
        elif tex[i] == "}":
            profundidad -= 1
            if profundidad < 0:
                return False
        i += 1
    return profundidad == 0
