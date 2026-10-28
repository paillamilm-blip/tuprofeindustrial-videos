"""El dibujo de un paso, visto antes de crear el video: un fotograma, sin voz y sin IA.

No pasa por `TAREAS`: la cola es de un trabajo a la vez y una miniatura no puede pelearse con un
video en marcha. Manim se importa adentro de `dibujar_miniatura`, a propósito: el panel arranca
igual de rápido y solo paga ese costo quien pide ver un dibujo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from .. import __version__
from ..config import cargar_marca
from ..entorno import raiz_proyecto
from ..errores import ErrorMotor
from ..guion import Visual, explicar_errores
from ..temas import cargar_tema

RAZON = 16 / 9  # alto / ancho de un cuadro vertical
HOLGURA = 1.15  # aire alrededor del dibujo: lo justo para que ninguna letra toque el borde
LADO = 320  # px del alto del PNG: se muestra a 78-160 px, sobra


def _carpeta() -> Path:
    carpeta = raiz_proyecto() / "salida" / "_miniaturas"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _huella(visual: dict, tema: str) -> str:
    # La versión va en la huella: un arreglo en el modo de dibujar no cambia el visual y, sin esto,
    # el panel seguiría mostrando para siempre el PNG que se dibujó con el código viejo.
    texto = json.dumps(
        {"visual": visual, "tema": tema, "version": __version__}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def ruta_miniatura(visual: dict, tema: str = "hoja_de_desarrollo") -> Path:
    tipo = str(visual.get("tipo") or "sin_tipo").replace("/", "_")
    return _carpeta() / f"{tipo}_{_huella(visual, tema)}.png"


def marco_para(ancho: float, alto: float) -> tuple[float, float]:
    """El marco 9:16 mínimo que contiene un dibujo de ``ancho``×``alto`` (con su holgura)."""
    ancho = max(ancho, 0.5)
    alto = max(alto, 0.5)
    alto_marco = max(alto, ancho * RAZON) * HOLGURA
    return alto_marco / RAZON, alto_marco


def dibujar_miniatura(visual: dict, tema: str = "hoja_de_desarrollo", forzar: bool = False) -> Path:
    """Un PNG con el dibujo centrado y encuadrado. Lanza ErrorMotor si el tipo o los campos no valen."""
    destino = ruta_miniatura(visual, tema)
    if destino.exists() and not forzar:
        return destino
    tipo = str(visual.get("tipo") or "")
    if not tipo:
        raise ErrorMotor("No hay dibujo que mostrar: elige uno en «Qué dibujar».")
    try:
        modelo = Visual.model_validate(visual)
    except Exception as e:
        # `explicar_errores` traduce pydantic: el texto crudo con «input_value» no sirve en pantalla.
        falta = "; ".join(explicar_errores(e)) if isinstance(e, ValidationError) else str(e)
        raise ErrorMotor(f"El dibujo «{tipo}» aún no está completo. {falta.removeprefix('(raíz): ')}") from e

    from manim import ORIGIN, Camera, tempconfig

    from .. import dibujos as _d
    from .. import entorno as _entorno
    from ..componentes import ANCHO_UTIL

    _entorno.preparar()
    _entorno.registrar_fuentes()
    estilo = cargar_tema(tema, cargar_marca())
    dibujo = _d.dibujar_visual(modelo, estilo.colores, ANCHO_UTIL, _d.ALTO_DIBUJO, estilo.hoja.color)
    grupo = dibujo.mobs
    # La cámara encuadra alrededor del origen: un dibujo que se arma con `move_to` aparte
    # (la recta, el péndulo) salía corrido a un lado y con medio cuadro vacío.
    grupo.move_to(ORIGIN)
    ancho, alto = marco_para(grupo.width, grupo.height)
    with tempconfig(
        {
            "pixel_width": round(LADO / RAZON),
            "pixel_height": LADO,
            "frame_width": ancho,
            "frame_height": alto,
            "background_color": estilo.colores.fondo,
            "verbosity": "ERROR",
            "disable_caching": True,
        }
    ):
        camara = Camera()
        camara.capture_mobject(grupo)
        camara.get_image().save(destino)
    return destino
