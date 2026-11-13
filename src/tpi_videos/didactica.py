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
# Aire mínimo (unidades de pantalla) entre lo escrito, el subtítulo y el resumen.
SEPARACION = 0.3


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


def decisiones_para_registro(guion: Guion, tema: Tema) -> list[dict[str, Any]] | None:
    """Las cuatro decisiones para la línea de tiempo; None si el guion no decide nada propio."""
    if not es_explicito(guion):
        return None
    return [d.a_dict() for d in recursos_del_guion(guion, tema)]


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
        _reservar_resumen(tema, copia)
    return copia


def piso_de_lectura(tema: Tema) -> float:
    """Lo más bajo (en pantalla, de -8 a 8) donde puede terminar lo escrito sin tocar el subtítulo.

    Toma el subtítulo efectivo (el mismo de ``render.subtitulos_de``), de dos líneas, más el aire.
    """
    from .render import subtitulos_de

    estilo = subtitulos_de(tema)
    return 8.0 - estilo.posicion_y * 16.0 + alto_subtitulo(estilo.tamano) / 2 + SEPARACION


def alto_subtitulo(tamano: int, lineas: int = 2) -> float:
    """Alto (unidades del cuadro de 16) de un subtítulo de ``lineas`` líneas con letra ``tamano`` px."""
    return lineas * 1.25 * tamano / 1920 * 16.0


def _reservar_resumen(tema: Tema, copia: Tema) -> None:
    """Resumen recién encendido: banda para él, subtítulo encima con aire y pasos por encima de ambos.

    ``render.subtitulos_de`` sube el subtítulo una banda entera cuando hay resumen (lo necesitan los
    estilos con subtítulo bajo). Acá se sube solo lo justo para dejar ``SEPARACION`` sobre el resumen:
    una hoja con el subtítulo ya alto no pierde zona de trabajo. Solo afecta a esta copia.
    """
    banda = tema.layout.banda_panel or _BANDA_PANEL
    techo_resumen = -8.0 + 0.25 + banda
    medio = alto_subtitulo(tema.subtitulos.tamano) / 2
    centro = max(8.0 - tema.subtitulos.posicion_y * 16.0, techo_resumen + SEPARACION + medio)
    posicion = min(0.9, (8.0 - centro) / 16.0 + banda / 16.0)  # subtitulos_de le restará banda/16
    centro = 8.0 - (posicion - banda / 16.0) * 16.0
    techo_subtitulo = centro + medio + SEPARACION
    y_actual = tema.layout.y_zona_pasos
    if y_actual is None:
        y_actual = _PISO_DEL_MARCO[tema.marco]
    copia.subtitulos = copia.subtitulos.model_copy(update={"posicion_y": round(posicion, 4)})
    copia.layout = copia.layout.model_copy(
        update={
            "banda_panel": banda,
            "y_zona_pasos": max(y_actual, _PISO_CON_PANEL, techo_subtitulo),
            # la cámara deja lo escrito por encima del subtítulo (fracción del alto, desde abajo)
            "banda_subtitulo": max(tema.layout.banda_subtitulo, round((techo_subtitulo + 8.0) / 16.0, 4)),
        }
    )
