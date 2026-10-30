"""Cómo se filma cada molde: la receta de rodaje que lee la escena.

Hasta ahora el molde solo cambiaba las palabras del guion y el rodaje era siempre el mismo.
La receta le dice a ``escena.py`` cómo tratar los pasos: si se apilan o dejan una sola ancla, si
un error tachado se queda o sale de pantalla, si lleva contador y si la cámara entra al término
que cambia. También cómo se abre el video (la pregunta en una tarjeta o ocupando todo el cuadro),
si el cuadro se queda quieto o respira como cámara en mano, si el error y su remedio se ven en dos
mitades fijas de la hoja o en una sola columna que avanza, y si la respuesta del ejercicio sale
tapada con una barra hasta que la voz la nombra.

Se leen de ``plantillas/rodaje.yaml`` (viaja con el motor) y de ``mis_ajustes/rodaje.yaml`` (las del
autor, que ganan porque Git ignora esa carpeta). El panel las escribe con ``guardar_receta``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
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

# Lo que el panel muestra en lugar del nombre técnico del archivo.
NOMBRE_MANDO = {
    "pasos": "Los pasos",
    "error": "El error tachado",
    "contador": "Contador",
    "primer_plano": "La cámara",
    "gancho": "La apertura",
    "deriva": "El cuadro",
    "partida": "El tablero",
    "tapar_resultado": "El resultado",
}

# El orden en que se ofrecen las opciones, y qué hace cada una en la pantalla.
QUE_HACE = {
    "pasos": {"ancla": "una sola línea: la anterior se va", "pila": "se apilan, todos a la vista"},
    "error": {"sale": "desaparece al pasar a la forma buena", "queda": "se queda visible, para comparar"},
    "contador": {"errores": "chip «✗ 2 de 3» arriba", "ninguno": "sin contador"},
    "primer_plano": {"destacar": "entra al término que cambia", "nada": "sin acercamientos"},
    "gancho": {"tarjeta": "la pregunta en una tarjeta", "lleno": "la pregunta ocupa todo el cuadro"},
    "deriva": {"fija": "quieto", "en_mano": "respira y se desliza, como en mano"},
    "partida": {"seguida": "una columna que avanza", "mitades": "partido: MITO arriba, REALIDAD abajo"},
    "tapar_resultado": {
        "visible": "se ve al aparecer",
        "tapada": "tapado con una nota hasta que la voz lo dice",
    },
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


def campos_de_receta(clave: str) -> dict[str, str]:
    """La receta que se filmaría hoy, campo por campo, tal como la ve el panel."""
    return {campo: str(getattr(rodaje_para(clave), campo)) for campo in _VALORES}


def guardar_receta(clave: str, valores: dict[str, str]) -> Path:
    """Escribe la receta de un molde en ``mis_ajustes/rodaje.yaml`` sin tocar la del motor.

    Valida antes de escribir: una receta a medias o un valor mal dejan el archivo como estaba,
    porque el cargador exige las ocho líneas y el autor se quedaría sin recetas."""
    conocidas = list(_leer(PLANTILLA))
    if clave not in conocidas:
        raise ErrorMotor(
            f"No sé rodar el molde «{clave}». Opciones: {', '.join(conocidas)}.",
            ayuda="Elige uno de la lista del panel.",
        )
    receta = _una(clave, valores, _ruta_usuario())
    destino = _ruta_usuario()
    actuales = yaml.safe_load(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    if actuales is None:
        actuales = {}
    if not isinstance(actuales, dict):
        raise ErrorMotor(f"{destino.name} no tiene el formato esperado (molde: campos).")
    actuales[clave] = asdict(receta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(yaml.safe_dump(actuales, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destino
