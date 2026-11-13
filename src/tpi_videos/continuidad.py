"""El dibujo que se queda entre pasos: cuándo sigue y qué piezas cambian (sin Manim ni numpy).

Cuando dos pasos seguidos usan el MISMO dibujo (mismo tipo y mismos números; ver ``acompanar``), la escena no
lo borra para volver a trazarlo: lo deja en pantalla y cambia solo lo que muestra. Lo que es idéntico se queda
quieto, lo que ya no va se desvanece y lo nuevo aparece. Acá se decide eso; ``escena.py`` lo anima.

Las piezas se comparan por una «clave» que calcula la escena (forma, posición y color redondeados). Aquí
solo se emparejan claves, así esto se prueba sin renderizar.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable, Mapping, Sequence
from typing import Any, TypeVar

from .acompanar import _identidad

V = TypeVar("V")
N = TypeVar("N")


def campos_del_visual(visual: Any) -> dict[str, Any] | None:
    """Los campos de un ``Visual`` (pydantic) como dict simple, con su tipo; None si no hay dibujo."""
    if visual is None:
        return None
    if isinstance(visual, Mapping):
        return dict(visual)
    return visual.model_dump(exclude_none=True, exclude_defaults=True) | {"tipo": visual.tipo}


def sigue(previo: Mapping[str, Any] | None, nuevo: Mapping[str, Any] | None) -> bool:
    """True si el dibujo del paso nuevo es el mismo del anterior y puede quedarse en pantalla.

    Mismo tipo, mismos números y mismo tamaño pedido; puede cambiar lo que muestra (anotar, vista, corte…).
    """
    if not previo or not nuevo:
        return False
    if previo.get("tipo") != nuevo.get("tipo"):
        return False
    if (previo.get("tamano") or None) != (nuevo.get("tamano") or None):
        return False  # otro tamaño reencuadra el dibujo entero: ahí no hay piezas que se queden
    return _identidad(previo) == _identidad(nuevo)


def emparejar(
    viejas: Sequence[V],
    nuevas: Sequence[N],
    clave_vieja: Callable[[V], Hashable],
    clave_nueva: Callable[[N], Hashable],
) -> tuple[list[tuple[V, N]], list[V], list[N]]:
    """Reparte las piezas: ``(se_quedan, salen, entran)``.

    ``se_quedan`` son pares (vieja, nueva) idénticos: no se animan. ``salen`` se desvanecen y ``entran``
    aparecen. Una clave repetida (dos letras iguales en el mismo sitio) se empareja de a una, en orden.
    """
    libres: dict[Hashable, list[V]] = defaultdict(list)
    for v in viejas:
        libres[clave_vieja(v)].append(v)
    se_quedan: list[tuple[V, N]] = []
    entran: list[N] = []
    for n in nuevas:
        candidatas = libres.get(clave_nueva(n))
        if candidatas:
            se_quedan.append((candidatas.pop(0), n))
        else:
            entran.append(n)
    usadas = {id(v) for v, _ in se_quedan}
    salen = [v for v in viejas if id(v) not in usadas]
    return se_quedan, salen, entran
