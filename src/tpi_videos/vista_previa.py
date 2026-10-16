"""Vista previa de un estilo: 3 cuadros (gancho, paso y resultado) en pocos segundos.

Se crea un video borrador muy corto, sin voz (``plantillas/vista_previa.yaml``), con el motor de siempre
(así la vista previa es exactamente lo que saldrá en el video) y se toman 3 cuadros con subtítulo visible.
Si el tema no cambió desde la última vez, se reutilizan los cuadros guardados.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__
from .config import cargar_marca
from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .render import Progreso
from .temas import cargar_tema, id_tema

GUION = PLANTILLAS_DIR / "vista_previa.yaml"
SECCIONES = (("gancho", "gancho"), ("paso 2", "paso"), ("resultado", "resultado"))


def carpeta_vistas(tema: str) -> Path:
    return raiz_proyecto() / "salida" / "_vistas" / id_tema(tema)


def _huella(tema: str) -> str:
    """Cambia si cambia el tema, la marca (nombre, colores…) o la versión del motor."""
    marca = cargar_marca()
    datos = {"tema": cargar_tema(tema, marca).model_dump(mode="json"), "marca": marca.model_dump(mode="json")}
    texto = (
        json.dumps(datos, sort_keys=True, ensure_ascii=False)
        + __version__
        + GUION.read_text(encoding="utf-8")
    )
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def _cuadros(carpeta: Path) -> list[Path]:
    return [carpeta / f"{i}_{nombre}.png" for i, (_, nombre) in enumerate(SECCIONES, 1)]


def en_cache(tema: str) -> list[Path] | None:
    """Los 3 cuadros de la última vista previa, si siguen al día."""
    carpeta = carpeta_vistas(tema)
    huella = carpeta / "huella.txt"
    cuadros = _cuadros(carpeta)
    try:
        al_dia = huella.read_text(encoding="utf-8").strip() == _huella(tema)
    except Exception:  # sin vista previa o tema dañado: se genera de nuevo
        return None
    return cuadros if al_dia and all(c.exists() for c in cuadros) else None


def crear_vista_previa(
    tema: str | None = None, progreso: Progreso | None = None, forzar: bool = False
) -> list[Path]:
    from .postproduccion import extraer_cuadro
    from .render import crear_video
    from .subtitulos import momento_con_subtitulo, tiempos_ass

    tema = tema or cargar_marca().tema
    if not forzar and (guardados := en_cache(tema)):
        if progreso:
            progreso("listo", 1.0, "vista previa guardada")
        return guardados
    carpeta = carpeta_vistas(tema)
    resultado = crear_video(
        GUION, calidad="borrador", proveedor="silencio", sincronizar="estimado",
        carpeta_salida=carpeta, tema=tema, progreso=progreso,
    )  # fmt: skip
    linea = json.loads((resultado.carpeta / "linea_de_tiempo.json").read_text(encoding="utf-8"))
    bloques = {b["seccion"]: b for b in linea["bloques"]}
    tiempos = tiempos_ass(resultado.carpeta / "subtitulos.ass")
    cuadros = _cuadros(carpeta)
    for (seccion, _), destino in zip(SECCIONES, cuadros, strict=True):
        b = bloques[seccion]
        t = momento_con_subtitulo(b["inicio"], b["inicio"] + b["duracion"], tiempos)
        extraer_cuadro(resultado.video, t, destino)
    (carpeta / "huella.txt").write_text(_huella(tema), encoding="utf-8")
    return cuadros
