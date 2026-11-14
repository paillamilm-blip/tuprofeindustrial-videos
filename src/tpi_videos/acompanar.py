"""¿El dibujo acompaña la explicación? Revisa la cadena de pasos de un ejercicio (sin Manim ni pydantic).

El motor traza el dibujo de un paso mientras suena su voz: un paso con fórmula y sin dibujo, en un guion que
sí dibuja, es una fórmula sola en pantalla. Acá se avisa de eso y de cambiarle los números al dibujo entre
pasos. Que el mismo dibujo se repita NO es un problema: es lo que se busca. Un ejercicio también puede
cambiar de tipo de dibujo (una caja 3D y después barras): cada tipo lleva sus propios números.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Lo que un paso puede cambiar de su dibujo sin dejar de ser «el mismo»: qué muestra, no qué es.
CAMPOS_DE_LO_QUE_SE_MUESTRA = frozenset(
    {
        "anotar",
        "vista",
        "corte",
        "despiece",
        "movimiento",
        "desde",
        "hasta",
        "marcar",
        "descomponer",
        "tamano",
    }
)


@dataclass(frozen=True)
class PasoParaRevisar:
    tex: str  # vacío = paso solo hablado
    error: bool  # un error típico se tacha: no necesita dibujo propio
    visual: Mapping[str, Any] | None  # los campos del dibujo, o None


@dataclass(frozen=True)
class Falta:
    nivel: str  # "advertencia" o "sugerencia"
    donde: str
    mensaje: str


def _identidad(visual: Mapping[str, Any]) -> dict[str, Any]:
    """El dibujo sin lo que cambia de un paso a otro: su tipo y sus números."""
    return {
        k: v for k, v in visual.items() if k not in CAMPOS_DE_LO_QUE_SE_MUESTRA and v not in (None, "", [])
    }


def faltas_de_acompanamiento(pasos: Sequence[PasoParaRevisar], ejercicio: bool) -> list[Falta]:
    """Avisos para que el dibujo acompañe cada paso que se puede ver (solo en ejercicios con dibujo)."""
    con_dibujo = [p for p in pasos if p.visual]
    if not ejercicio or not con_dibujo:
        return []  # sin dibujo no hay nada que acompañar; un dato o mito puede mezclar ejemplos
    faltas: list[Falta] = []
    vistos: dict[str, dict[str, Any]] = {}  # el último paso de cada tipo: sus números son la referencia
    for i, p in enumerate(pasos, 1):
        if p.visual:
            identidad = _identidad(p.visual)
            tipo = str(p.visual.get("tipo") or "")
            base = vistos.get(tipo)
            vistos[tipo] = identidad
            if base is not None and identidad != base:
                distintos = sorted(k for k in set(base) | set(identidad) if base.get(k) != identidad.get(k))
                faltas.append(
                    Falta(
                        "sugerencia",
                        f"paso {i} (visual)",
                        f"el dibujo cambia de datos ({', '.join(distintos)}): mantén los números del enunciado "
                        "para que se vea que es el mismo problema.",
                    )
                )
        elif p.tex.strip() and not p.error:
            faltas.append(
                Falta(
                    "sugerencia",
                    f"paso {i}",
                    "este paso tiene fórmula pero no dibujo: si se puede ver, repite el dibujo de los otros pasos "
                    "para que acompañe la explicación (si es solo álgebra, déjalo así).",
                )
            )
    return faltas
