"""Vista previa de fórmulas en el panel, compiladas con el MISMO LaTeX del video (sin internet).

Cada fórmula se convierte en un SVG (en ``salida/_panel/Tex/``); si tiene un error, se explica en
español (ej. «Undefined control sequence: \\sqrtt»). Se compila una a la vez.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from nicegui import run

from ..entorno import raiz_proyecto

_candado = asyncio.Lock()


def _compilar(tex: str, negrita: bool) -> tuple[Path | None, str | None]:
    from .. import entorno
    from ..guion import _validar_tex
    from ..redactor import _error_latex
    from ..tex import corregir_decimales, plantilla_tex

    try:
        _validar_tex(tex)
    except ValueError as e:
        return None, str(e)
    entorno.preparar()
    if not all(entorno.latex_disponible()):
        return None, "falta LaTeX para dibujar fórmulas (ejecuta ./scripts/instalar_mac.sh)"
    from manim import config
    from manim.utils.tex_file_writing import tex_to_svg_file

    config.media_dir = str(raiz_proyecto() / "salida" / "_panel")
    registro = logging.getLogger("manim")
    nivel = registro.level
    registro.setLevel(logging.CRITICAL)  # el error se muestra en el panel, no en la Terminal
    try:
        return tex_to_svg_file(corregir_decimales(tex), "align*", plantilla_tex(negrita)), None
    except Exception as e:
        return None, _error_latex(e)
    finally:
        registro.setLevel(nivel)


def tamano_en_pantalla(svg: Path, escala: float = 2.4, alto_max: float = 120) -> tuple[float, float]:
    """(ancho, alto) en píxeles para mostrar el SVG de LaTeX a un tamaño cómodo de leer."""
    import re

    cabecera = svg.read_text(encoding="utf-8", errors="replace")[:600]
    medidas = [re.search(rf"{k}=['\"]([\d.]+)pt['\"]", cabecera) for k in ("width", "height")]
    if not all(medidas):
        return 0.0, 40.0
    ancho, alto = (float(m.group(1)) * escala for m in medidas)  # type: ignore[union-attr]
    if alto > alto_max:  # fracciones muy altas: se achican un poco
        ancho, alto = ancho * alto_max / alto, alto_max
    return round(ancho, 1), round(alto, 1)


async def dibujar(tex: str, negrita: bool = False) -> tuple[Path | None, str | None]:
    """(svg, None) si compila; (None, motivo) si no."""
    tex = (tex or "").strip()
    if not tex:
        return None, None
    async with _candado:
        resultado = await run.io_bound(_compilar, tex, negrita)
    return resultado or (None, None)  # None solo si el panel se está cerrando
