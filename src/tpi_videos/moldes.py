"""Catálogo de moldes virales: formatos que ya funcionan en TikTok, Reels y Shorts.

Solo metadatos y normalización. No importa ``guion.py`` para que ``guion.py`` pueda leerlo sin ciclo.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

MOLDE_POR_DEFECTO = "libre"


@dataclass(frozen=True)
class Molde:
    clave: str
    nombre: str
    estructura: str  # los beats que pide el prompt
    regla: str  # un_error | tres_errores | reto | verificacion | ""
    pista: str  # la instrucción objetiva que recibe el guionista
    ejemplo: str  # una frase para que el modelo entienda el tono


MOLDES: dict[str, Molde] = {
    "mito_realidad": Molde(
        clave="mito_realidad",
        nombre="Mito vs realidad",
        estructura="Afirmación incorrecta → por qué falla → forma correcta → resultado",
        regla="un_error",
        pista=(
            "El primer paso es el error que casi todos creen correcto (error: true) y el paso "
            "siguiente muestra la forma correcta. No es el último paso."
        ),
        ejemplo="«¿Pitágoras era a + b = c?» → el error → la forma correcta.",
    ),
    "tres_errores": Molde(
        clave="tres_errores",
        nombre="3 errores",
        estructura="Tres equivocaciones típicas seguidas → la forma correcta → resultado",
        regla="tres_errores",
        pista=(
            "Tres pasos seguidos con error: true, cada uno con su fórmula equivocada, y después "
            "al menos un paso correcto. Nunca un error como último paso."
        ),
        ejemplo="«Los 3 errores que arruinan tu cálculo de porcentajes».",
    ),
    "pov": Molde(
        clave="pov",
        nombre="POV",
        estructura="«Estás en…» en segunda persona → resuelve con lo que tienes → resultado",
        regla="",
        pista=(
            "Cuenta la situación en segunda persona («Estás en el taller y…»), con un problema "
            "concreto, y resuélvelo con los datos que tienes. El gancho también va en segunda persona."
        ),
        ejemplo='«POV: tienes que calcular la caída antes de que suene el timbre».',
    ),
    "reto": Molde(
        clave="reto",
        nombre="Reto",
        estructura="Ejercicio resuelto → un desafío parecido para responder",
        regla="reto",
        pista="El guion termina con el bloque «reto:»: un ejercicio parecido, dicho como pregunta abierta. "
        "En la voz nunca se pide comentar ni seguir.",
        ejemplo="«Ahora tú: si la altura fuera el doble, ¿tardaría el doble?»",
    ),
    "nadie_te_enseno": Molde(
        clave="nadie_te_enseno",
        nombre="Nadie te enseñó esto",
        estructura="Dato que contradice la intuición → se demuestra resolviendo → conclusión",
        regla="verificacion",
        pista=(
            "El guion incluye el bloque «verificacion:» con la comprobación o interpretación que "
            "demuestra el dato. El gancho presenta el dato que contradice la intuición."
        ),
        ejemplo='«Nadie te enseñó que una TV de 55" mide 55 pulgadas en diagonal».',
    ),
}

_OTRAS_PALABRAS = {
    "mito_realidad": ("mitorealidad", "mito", "mitos", "mitovsrealidad", "mitoyrealidad"),
    "tres_errores": ("treserrores", "3errores", "3error", "errores"),
    "pov": ("pov", "puntodevista"),
    "reto": ("reto", "desafio", "challenge"),
    "nadie_te_enseno": (
        "nadieteenseno",
        "nadieteensenoesto",
        "nadieloenseno",
        "nadiemeenseno",
        "nadie",
    ),
}


def normalizar_molde(valor: str | None) -> str:
    """La clave del molde, venga con tildes, mayúsculas, guiones o espacios."""
    limpio = "".join(
        c
        for c in unicodedata.normalize("NFKD", (valor or "").casefold())
        if not unicodedata.combining(c) and c.isalnum()
    )
    for clave, otras in _OTRAS_PALABRAS.items():
        if limpio == clave.replace("_", "") or limpio in otras:
            return clave
    return ""


def opciones_de_moldes() -> str:
    return ", ".join(MOLDES)


def nombre_molde(valor: str | None) -> str:
    clave = normalizar_molde(valor)
    return MOLDES[clave].nombre if clave else "Libre"


def moldes_para_ia() -> str:
    """La tabla que entra a la plantilla del productor de ideas."""
    lineas = ["| clave | nombre | estructura | ejemplo |", "|---|---|---|---|"]
    for molde in MOLDES.values():
        lineas.append(f"| `{molde.clave}` | {molde.nombre} | {molde.estructura} | {molde.ejemplo} |")
    return "\n".join(lineas)
