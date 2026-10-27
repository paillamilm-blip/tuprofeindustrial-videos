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


def carpeta_vistas(tema: str, sufijo: str = "") -> Path:
    return raiz_proyecto() / "salida" / "_vistas" / f"{id_tema(tema)}{sufijo}"


def huella(tema: str, guion: Path | None = None) -> str:
    """Cambia si cambia el tema, la marca, el guion del autor o la versión del motor."""
    marca = cargar_marca()
    datos = {"tema": cargar_tema(tema, marca).model_dump(mode="json"), "marca": marca.model_dump(mode="json")}
    contenido = (guion or GUION).read_text(encoding="utf-8")
    texto = json.dumps(datos, sort_keys=True, ensure_ascii=False) + __version__ + contenido
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def _carpeta(tema: str, guion: Path | None) -> Path:
    """Con guion del autor, una carpeta propia: así el cache de la plantilla no se confunde."""
    sufijo = f"__{huella(tema, guion)[:8]}" if guion is not None else ""
    return carpeta_vistas(tema, sufijo)


def _cuadros(carpeta: Path) -> list[Path]:
    return [carpeta / f"{i}_{nombre}.png" for i, (_, nombre) in enumerate(SECCIONES, 1)]


def en_cache(tema: str, guion: Path | None = None) -> list[Path] | None:
    """Los 3 cuadros de la última vista previa, si siguen al día."""
    carpeta = _carpeta(tema, guion)
    archivo_huella = carpeta / "huella.txt"
    cuadros = _cuadros(carpeta)
    try:
        al_dia = archivo_huella.read_text(encoding="utf-8").strip() == huella(tema, guion)
    except Exception:  # sin vista previa o tema dañado: se genera de nuevo
        return None
    return cuadros if al_dia and all(c.exists() for c in cuadros) else None


def crear_vista_previa(
    tema: str | None = None,
    progreso: Progreso | None = None,
    forzar: bool = False,
    guion: Path | None = None,
) -> list[Path]:
    from .postproduccion import extraer_cuadro
    from .render import crear_video
    from .subtitulos import momento_con_subtitulo, tiempos_ass

    tema = tema or cargar_marca().tema
    if not forzar and (guardados := en_cache(tema, guion)):
        if progreso:
            progreso("listo", 1.0, "vista previa guardada")
        return guardados
    carpeta = _carpeta(tema, guion)
    resultado = crear_video(
        guion or GUION, calidad="borrador", proveedor="silencio", sincronizar="estimado",
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
    (carpeta / "huella.txt").write_text(huella(tema, guion), encoding="utf-8")
    return cuadros
