"""Cómo se filma cada molde: la receta de rodaje que lee la escena.

Hasta ahora el molde solo cambiaba las palabras del guion y el rodaje era siempre el mismo.
La receta le dice a ``escena.py`` cómo tratar los pasos: si se apilan o dejan una sola ancla, si
un error tachado se queda o sale de pantalla, si lleva contador y si la cámara entra al término
que cambia. También cómo se abre el video (la pregunta en una tarjeta o ocupando todo el cuadro),
si el cuadro se queda quieto o respira como cámara en mano, si el error y su remedio se ven en dos
mitades fijas de la hoja o en una sola columna que avanza, y si la respuesta del ejercicio sale
tapada con una barra hasta que la voz la nombra.

Se leen de ``plantillas/rodaje.yaml`` (viaja con el motor) y de ``mis_ajustes/rodaje.yaml`` (las del
autor, que ganan porque Git ignora esa carpeta).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor

PLANTILLA = PLANTILLAS_DIR / "rodaje.yaml"
RECETA_LIBRE = "libre"  # la de los guiones que no traen molde

PASOS = {"ancla", "pila"}
ERROR = {"sale", "queda"}
CONTADOR = {"errores", "ninguno"}
PRIMER_PLANO = {"destacar", "nada"}
GANCHO = {"tarjeta", "lleno"}
DERIVA = {"fija", "en_mano"}
PARTIDA = {"seguida", "mitades"}
TAPAR = {"visible", "tapada"}

_VALORES = {
    "pasos": PASOS,
    "error": ERROR,
    "contador": CONTADOR,
    "primer_plano": PRIMER_PLANO,
    "gancho": GANCHO,
    "deriva": DERIVA,
    "partida": PARTIDA,
    "tapar_resultado": TAPAR,
}


@dataclass(frozen=True)
class Receta:
    pasos: str
    error: str
    contador: str
    primer_plano: str
    gancho: str
    deriva: str
    partida: str
    tapar_resultado: str


def _ruta_usuario() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "rodaje.yaml"


def _una(clave: str, datos: dict, origen: Path) -> Receta:
    faltan = [campo for campo in _VALORES if campo not in datos]
    if faltan:
        raise ErrorMotor(
            f"La receta «{clave}» de {origen.name} no tiene {', '.join(faltan)}.",
            ayuda=f"Los valores posibles: {_opciones()}.",
        )
    for campo, buenos in _VALORES.items():
        valor = str(datos[campo])
        if valor not in buenos:
            raise ErrorMotor(
                f"«{valor}» no es un valor de {campo} en la receta «{clave}» de {origen.name}.",
                ayuda=f"Los valores posibles: {_opciones()}.",
            )
    return Receta(**{campo: str(datos[campo]) for campo in _VALORES})


def _opciones() -> str:
    return ", ".join(f"{campo}={'|'.join(sorted(valores))}" for campo, valores in _VALORES.items())


def _leer(ruta: Path) -> dict[str, Receta]:
    if not ruta.exists():
        return {}
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {clave: _una(clave, valor, ruta) for clave, valor in datos.items() if isinstance(valor, dict)}


def cargar_recetas() -> dict[str, Receta]:
    """Las recetas del motor, con las propias encima si repiten clave."""
    salida = _leer(PLANTILLA)
    salida.update(_leer(_ruta_usuario()))
    return salida


def rodaje_para(clave: str | None) -> Receta:
    recetas = cargar_recetas()
    if clave in recetas:
        return recetas[clave]
    raise ErrorMotor(
        f"No conozco cómo rodar el molde «{clave}». Opciones: {', '.join(recetas)}.",
        ayuda="Agrega esa receta a mis_ajustes/rodaje.yaml copiando la forma de las demás.",
    )


def rodaje_de_guion(guion) -> Receta:
    """La receta del molde del guion; la libre cuando el guion no trae molde."""
    return rodaje_para(guion.molde or RECETA_LIBRE)
