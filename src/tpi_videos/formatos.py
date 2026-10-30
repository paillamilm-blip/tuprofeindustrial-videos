"""Las familias de contenido del canal: molde + estilo + dibujo en una sola elección.

Se leen de ``plantillas/formatos.yaml`` (viaja con el motor) y de ``mis_ajustes/formatos.yaml`` (las del
autor, que ganan porque Git ignora esa carpeta). ``puntuar_idea()`` es un conteo de palabras: sin IA y sin
cuota, y si no reconoce nada no marca ninguna familia.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor

PLANTILLA = PLANTILLAS_DIR / "formatos.yaml"
FORMATO_POR_DEFECTO = "datos"


@dataclass(frozen=True)
class Formato:
    clave: str
    nombre: str
    que_es: str
    moldes: tuple[str, ...]
    tema: str
    dibujos: tuple[str, ...]
    color: str
    cta: str
    gancho_corto: bool = False


def _ruta_usuario() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "formatos.yaml"


def _una(clave: str, datos: dict, origen: Path) -> Formato:
    try:
        return Formato(
            clave=clave,
            nombre=str(datos["nombre"]),
            que_es=" ".join(str(datos["que_es"]).split()),
            moldes=tuple(datos["moldes"]),
            tema=str(datos["tema"]),
            dibujos=tuple(datos["dibujos"]),
            color=str(datos["color"]),
            cta=str(datos["cta"]),
            gancho_corto=bool(datos.get("gancho_corto", False)),
        )
    except KeyError as e:
        raise ErrorMotor(f"La familia {clave} de {origen.name} no tiene el campo {e}.") from e


def _leer(ruta: Path) -> dict[str, Formato]:
    if not ruta.exists():
        return {}
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {clave: _una(clave, valor, ruta) for clave, valor in datos.items() if isinstance(valor, dict)}


def cargar_formatos() -> dict[str, Formato]:
    """Las familias del motor, con las propias encima si repiten clave."""
    salida = _leer(PLANTILLA)
    salida.update(_leer(_ruta_usuario()))
    return salida


def formato(clave: str | None) -> Formato:
    claves = cargar_formatos()
    if clave in claves:
        return claves[clave]
    raise ErrorMotor(
        f"No conozco la familia «{clave}». Opciones: {', '.join(claves)}.",
        ayuda="Cámbialas o agrega las tuyas en mis_ajustes/formatos.yaml; se ven con «tpi formatos».",
    )


def _limpio(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c))


# Palabras que delatan cada familia. Se cuentan apariciones, no ocurrencias: una idea corta no debe
# empatar con otra por casualidad (por eso el margen de puntuar_idea).
_PISTAS: dict[str, tuple[str, ...]] = {
    "trampas": ("trampa", "reto", "desafio", "magia", "sutil", "engana", "encuentra", "truco de magia"),
    "paso_a_paso": ("pov", "calcular", "paso a paso", "cronometro", "tradicional", "procedimiento"),
    "datos": (
        "dato",
        "datos",
        "grafico",
        "porcentaje",
        "escala",
        "paradoja",
        "historia",
        "poblacion",
        "promedio",
        "cultura",
    ),
    "hacks": (
        "truco",
        "hacks",
        "hack",
        "atajo",
        "mental",
        "rapido",
        "sin calculadora",
        "comprobacion",
        "expres",
        "dos segundos",
    ),
}


def puntuar_idea(texto: str) -> str | None:
    """La familia con más palabras clave; None si ninguna destaca o si dos empatan."""
    limpio = _limpio(texto or "")
    if not limpio.strip():
        return None
    puntos = {
        clave: sum(limpio.count(palabra) for palabra in palabras) for clave, palabras in _PISTAS.items()
    }
    mejor = max(puntos, key=lambda clave: puntos[clave])
    if puntos[mejor] < 2:
        return None
    if list(puntos.values()).count(puntos[mejor]) > 1:
        return None
    return mejor


def palabra_que_delata(texto: str, clave: str) -> str | None:
    """La palabra de la frase que hizo caer en esa familia: para que el motivo se pueda revisar."""
    limpio = _limpio(texto or "")
    for palabra in _PISTAS.get(clave, ()):
        if palabra in limpio:
            return palabra
    return None


def formato_de_guion(guion) -> Formato | None:
    """La familia que carga con el molde elegido en el guion, o None si el guion va libre."""
    if not guion.molde:
        return None
    for familia in cargar_formatos().values():
        if guion.molde in familia.moldes:
            return familia
    return None


def tabla_para_ia() -> str:
    """La tabla de familias, en markdown, para el prompt de quien propone las 3 opciones."""
    lineas = ["| clave | familia | moldes | estilo |", "|---|---|---|---|"]
    for f in cargar_formatos().values():
        lineas.append(f"| `{f.clave}` | {f.nombre} | {', '.join(f.moldes)} | {f.tema} |")
    return "\n".join(lineas)
