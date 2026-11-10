"""La malla del canal: qué ramos y temas corresponden a cada nivel, materia y carrera.

Los datos viven en ``plantillas/malla.yaml``; una copia en ``mis_ajustes/malla.yaml`` le gana (así se
ajusta a una universidad concreta sin tocar el motor).
"""

from __future__ import annotations

from typing import Any

import yaml

from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor
from .niveles import CARRERAS, NIVELES, es_universidad, nombre_carrera

MATERIAS_MALLA = ("matematica", "fisica", "ingenieria")


def _archivo():
    propio = raiz_proyecto() / "mis_ajustes" / "malla.yaml"
    return propio if propio.is_file() else PLANTILLAS_DIR / "malla.yaml"


def cargar_malla() -> dict[str, Any]:
    ruta = _archivo()
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ErrorMotor(
            f"No pude leer la malla ({ruta.name}).", ayuda="Revisa la sangría del archivo."
        ) from e
    if not isinstance(datos, dict):
        raise ErrorMotor(f"La malla ({ruta.name}) no tiene niveles.")
    return datos


def carreras_del_nivel(nivel: str) -> tuple[str, ...]:
    """Las carreras con ramos propios de Ingeniería en ese nivel (vacío = plan común)."""
    ingenieria = cargar_malla().get(nivel, {}).get("ingenieria")
    return tuple(c for c in CARRERAS if isinstance(ingenieria, dict) and c in ingenieria)


def ramos(nivel: str, materia: str, carrera: str | None = None) -> list[str]:
    """Los ramos y temas de ese nivel y materia. Sin carrera, en un año con carreras, van todos."""
    if nivel not in NIVELES:
        return []
    valor = cargar_malla().get(nivel, {}).get(materia)
    if isinstance(valor, dict):
        if carrera:
            return [str(r) for r in valor.get(carrera) or []]
        return [str(r) for c in CARRERAS for r in valor.get(c) or []]
    return [str(r) for r in valor or []]


def pista_para_la_ia(nivel: str | None, materia: str | None, carrera: str | None = None) -> str | None:
    """Lo que la IA necesita saber de un nivel universitario (None en enseñanza media)."""
    if not es_universidad(nivel):
        return None
    materias = [materia] if materia in MATERIAS_MALLA else list(MATERIAS_MALLA)
    temas = [r for m in materias for r in ramos(nivel, m, carrera if m == "ingenieria" else None)]
    partes = [f"PÚBLICO UNIVERSITARIO: estudiantes de {nivel}"]
    partes[0] += (
        f" de {nombre_carrera(carrera)}."
        if carrera
        else " (Ing. Civil Industrial, Civil Eléctrica u Obras Civiles)."
    )
    if temas:
        partes.append("Ramos de este año en la malla: " + "; ".join(temas) + ".")
    partes.append(
        "El ejercicio es de uno de esos ramos, con el rigor, la notación y las unidades de la carrera: "
        "nunca un problema de enseñanza media."
    )
    return " ".join(partes)
