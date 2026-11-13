"""Las herramientas de la explicación (contador de pasos, resumen, colores, énfasis), por guion.

El contenido decide qué herramientas ayudan; el estilo (la variante de Consola u otro tema) decide
cómo se ve. Este módulo solo toma decisiones y devuelve una COPIA del tema con esas decisiones:
no escribe archivos, no cambia preferencias y no importa Manim ni NiceGUI.

Cascada por herramienta: lo elegido en el guion (``recursos:``) > lo sugerido por su contenido
(``contenido:``) > lo que trae el tema. Sin ``contenido`` ni ``recursos``, el tema queda intacto.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .guion import Guion
from .temas import Tema

RECURSOS: tuple[str, ...] = ("tabs", "panel", "mapa_color", "micro")

NOMBRES: dict[str, str] = {
    "tabs": "Contador de pasos",
    "panel": "Resumen de fórmulas",
    "mapa_color": "Relaciones por color",
    "micro": "Énfasis continuo",
}

# Pisos del marco (los mismos de componentes._ZONAS) y el piso que deja aire al resumen fijo.
_PISO_DEL_MARCO = {"pizarra": -2.4, "hoja": -3.55}
_PISO_CON_PANEL = -2.2
_BANDA_PANEL = 1.6


@dataclass(frozen=True)
class RecursoDidactico:
    clave: str
    activo: bool
    sugerido: bool
    razon: str
    origen: str  # "guion" (elegido), "contenido" (sugerido por lo que enseña) o "tema" (heredado)

    @property
    def nombre(self) -> str:
        return NOMBRES[self.clave]

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)


def _formulas_correctas(guion: Guion) -> int:
    return sum(1 for p in guion.pasos if p.tex and not p.error)


def _con_mapa(guion: Guion) -> bool:
    return any(p.mapa for p in guion.pasos)


def _recomendaciones(guion: Guion) -> dict[str, tuple[bool, str]]:
    """Lo que el contenido sugiere, con su motivo: nace de la estructura real del guion."""
    n = len(guion.pasos)
    formulas = _formulas_correctas(guion)
    return {
        "tabs": (n >= 3, f"{n} pasos: permite seguir el avance." if n >= 3 else "Pocos pasos: el contador no aporta."),
        "panel": (
            formulas >= 2,
            "Conserva las fórmulas correctas para comparar."
            if formulas >= 2
            else "No hay suficientes fórmulas que resumir.",
        ),
        "mapa_color": (
            _con_mapa(guion),
            "Relaciona las partes ya indicadas en el guion."
            if _con_mapa(guion)
            else "El guion no trae relaciones por color.",
        ),
        "micro": (False, "El énfasis continuo queda apagado; puedes activarlo."),
    }


def _sin_datos(clave: str, guion: Guion) -> bool:
    """Herramientas que, encendidas, no tendrían qué mostrar en este guion."""
    if clave == "panel":
        return _formulas_correctas(guion) == 0
    if clave == "mapa_color":
        return not _con_mapa(guion)
    return False


def recursos_del_guion(guion: Guion, tema: Tema) -> list[RecursoDidactico]:
    """Las cuatro decisiones, en orden fijo, con su estado, sugerencia, motivo y origen."""
    recomendaciones = _recomendaciones(guion) if guion.contenido else {}
    decisiones: list[RecursoDidactico] = []
    for clave in RECURSOS:
        base = bool(getattr(tema.gramatica, clave))
        if guion.contenido:
            sugerido, razon = recomendaciones[clave]
        else:
            sugerido = base
            razon = (
                f"Lo trae el estilo «{tema.nombre}»." if base else f"El estilo «{tema.nombre}» no lo usa."
            )
        manual = getattr(guion.recursos, clave) if guion.recursos else None
        activo = sugerido if manual is None else manual
        origen = "guion" if manual is not None else ("contenido" if guion.contenido else "tema")
        if activo and _sin_datos(clave, guion):
            razon = f"{razon.rstrip('.')}: encendido, no tendrá contenido."
        decisiones.append(RecursoDidactico(clave, activo, sugerido, razon, origen))
    return decisiones


def es_explicito(guion: Guion) -> bool:
    """¿El guion decide algo propio (contenido o al menos una herramienta elegida)?"""
    if guion.contenido is not None:
        return True
    return guion.recursos is not None and any(getattr(guion.recursos, c) is not None for c in RECURSOS)


def componer_tema(tema: Tema, guion: Guion) -> Tema:
    """Una copia del tema con las herramientas de este guion; la apariencia no cambia."""
    copia = tema.model_copy(deep=True)
    if not es_explicito(guion):
        return copia
    finales = {d.clave: d.activo for d in recursos_del_guion(guion, tema)}
    if all(finales[c] == bool(getattr(tema.gramatica, c)) for c in RECURSOS):
        return copia
    copia.gramatica = copia.gramatica.model_copy(update=finales)
    if finales["panel"] and not tema.gramatica.panel:
        # Resumen recién encendido: se le reserva su banda y la pila de pasos se detiene antes.
        y_actual = tema.layout.y_zona_pasos
        if y_actual is None:
            y_actual = _PISO_DEL_MARCO[tema.marco]
        copia.layout = copia.layout.model_copy(
            update={
                "banda_panel": tema.layout.banda_panel or _BANDA_PANEL,
                "y_zona_pasos": max(y_actual, _PISO_CON_PANEL),
            }
        )
    return copia
