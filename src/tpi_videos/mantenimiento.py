"""Poda de cachés temporales: dibujos 3D, audios de la voz, borradores de la vista previa y los trozos
que Manim ya unió.

Todo lo que se borra acá se puede volver a generar (el PNG con la misma cámara, el audio con el mismo
texto), así que la poda nunca toca videos, guiones ni kits. Se borra sólo dentro de las carpetas de
caché y se respeta la fecha de modificación: lo que se está usando tiene mtime de hoy.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .entorno import raiz_proyecto

SUFIJOS_3D = {".png", ".json"}
SUFIJOS_AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


@dataclass
class Poda:
    archivos: list[Path] = field(default_factory=list)
    bytes: int = 0


def _tamano(ruta: Path) -> int:
    try:
        return ruta.stat().st_size
    except OSError:
        return 0


def _es_archivo(ruta: Path) -> bool:
    return ruta.is_file() and not ruta.is_symlink()


def _viejos(carpeta: Path, limite: float, sufijos: set[str]) -> list[Path]:
    if not carpeta.is_dir():
        return []
    return sorted(
        (
            ruta
            for ruta in carpeta.iterdir()
            if ruta.suffix.lower() in sufijos and _es_archivo(ruta) and ruta.stat().st_mtime < limite
        ),
        key=lambda ruta: ruta.stat().st_mtime,
    )


def _referencias_audio(carpeta: Path) -> set[str] | None:
    """Los audios que el manifiesto de manim-voiceover da por buenos; None si no se puede leer."""
    manifiesto = carpeta / "cache.json"
    if not manifiesto.is_file():
        return None
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(datos, list):
        return None
    referencias: set[str] = set()
    for entrada in datos:
        if isinstance(entrada, dict):
            for clave in ("original_audio", "final_audio"):
                nombre = entrada.get(clave)
                if isinstance(nombre, str) and nombre:
                    referencias.add(Path(nombre).name)
    return referencias


def _par(ruta: Path) -> list[Path]:
    """El PNG y su JSON de recorte se van juntos, aunque a uno le falte la fecha del otro."""
    if ruta.suffix.lower() not in SUFIJOS_3D:
        return [ruta]
    return [ruta, ruta.with_suffix(".json" if ruta.suffix.lower() == ".png" else ".png")]


def _podar_3d(carpeta: Path, limite: float, cuota: int) -> list[Path]:
    """Borra por antigüedad y, si igual se pasa de la cuota, va sacando lo más viejo primero."""
    if not carpeta.is_dir():
        return []
    candidatos = _viejos(carpeta, limite, SUFIJOS_3D)
    restantes = [
        ruta
        for ruta in carpeta.iterdir()
        if ruta.suffix.lower() in SUFIJOS_3D and _es_archivo(ruta) and ruta not in candidatos
    ]
    total = sum(_tamano(ruta) for ruta in restantes)
    if total > cuota:
        for ruta in sorted(restantes, key=lambda r: r.stat().st_mtime):
            if total <= cuota:
                break
            for lado in _par(ruta):
                if lado in restantes and lado not in candidatos:
                    candidatos.append(lado)
                    total -= _tamano(lado)
    con_pares: list[Path] = []
    for ruta in candidatos:
        for lado in _par(ruta):
            if lado not in con_pares and _es_archivo(lado):
                con_pares.append(lado)
    return con_pares


def _podar_voz(raiz: Path, limite: float) -> list[Path]:
    candidatos: list[Path] = []
    for carpeta in raiz.glob("salida/**/manim/voiceovers"):
        if not carpeta.is_dir():
            continue
        referencias = _referencias_audio(carpeta)
        if referencias is None:  # sin manifiesto legible no se toca nada de esa carpeta
            continue
        for ruta in _viejos(carpeta, limite, SUFIJOS_AUDIO):
            if ruta.name not in referencias:
                candidatos.append(ruta)
    return candidatos


def _sin_enlaces(ruta: Path, base: Path) -> bool:
    """Ni la ruta ni ninguna carpeta entre ella y ``base`` es un enlace simbólico: nunca se sigue uno."""
    try:
        relativa = ruta.relative_to(base)
    except ValueError:
        return False
    actual = base
    for parte in relativa.parts:
        actual = actual / parte
        if actual.is_symlink():
            return False
    return True


def _archivos_si_todo_es_viejo(carpeta: Path, limite: float) -> list[Path] | None:
    """Todos los archivos de la carpeta si todos son viejos; None si hay algo reciente o un enlace."""
    archivos: list[Path] = []
    for raiz, carpetas, nombres in os.walk(carpeta, followlinks=False):
        for nombre in carpetas + nombres:
            if (Path(raiz) / nombre).is_symlink():
                return None
        for nombre in nombres:
            ruta = Path(raiz) / nombre
            if ruta.stat().st_mtime >= limite:
                return None
            archivos.append(ruta)
    return archivos


def _podar_vistas(base: Path, limite: float) -> list[Path]:
    """El video borrador de cada vista previa (``salida/_vistas/<estilo>/<video>/``).

    Se conservan los 3 PNG y ``huella.txt`` de cada estilo: es todo lo que necesita
    ``vista_previa.en_cache``, así que la vista previa guardada sigue apareciendo en el panel.
    """
    vistas = base / "salida" / "_vistas"
    if not vistas.is_dir() or not _sin_enlaces(vistas, base):
        return []
    candidatos: list[Path] = []
    for estilo in sorted(vistas.iterdir()):
        if not estilo.is_dir() or estilo.is_symlink():
            continue
        for video in sorted(estilo.iterdir()):
            if video.is_dir() and not video.is_symlink():
                candidatos += _archivos_si_todo_es_viejo(video, limite) or []
    return candidatos


def _podar_trozos(base: Path, limite: float) -> list[Path]:
    """Los trozos que Manim ya unió en ``animacion.mp4`` (``.../manim/videos/*/partial_movie_files/``).

    ``animacion.mp4`` no se toca: ``linea_de_tiempo.json`` lo usa para la miniatura y la portada.
    """
    candidatos: list[Path] = []
    for trozos in sorted(base.glob("salida/**/manim/videos/*/partial_movie_files")):
        if not trozos.is_dir() or not _sin_enlaces(trozos, base):
            continue
        for raiz, _carpetas, nombres in os.walk(trozos, followlinks=False):
            for nombre in nombres:
                ruta = Path(raiz) / nombre
                if _es_archivo(ruta) and ruta.stat().st_mtime < limite:
                    candidatos.append(ruta)
    return candidatos


def _tope(ruta: Path, base: Path) -> Path | None:
    """Hasta dónde se pueden quitar carpetas vacías: ``_vistas/<estilo>`` (se queda con sus PNG) o
    la carpeta que contiene ``partial_movie_files``. None para todo lo demás (3D, voz): ahí no se toca."""
    vistas = base / "salida" / "_vistas"
    if vistas in ruta.parents:
        return vistas / ruta.relative_to(vistas).parts[0]
    partes = ruta.parts
    if "partial_movie_files" in partes:
        return Path(*partes[: partes.index("partial_movie_files")])
    return None


def _quitar_carpetas_vacias(borrados: list[Path], base: Path) -> None:
    carpetas: set[Path] = set()
    for ruta in borrados:
        tope = _tope(ruta, base)
        if tope is None:
            continue
        for padre in ruta.parents:
            if padre == tope or tope not in padre.parents:
                break
            carpetas.add(padre)
    for carpeta in sorted(carpetas, key=lambda c: len(c.parts), reverse=True):
        try:
            if carpeta.is_dir() and not carpeta.is_symlink() and not any(carpeta.iterdir()):
                carpeta.rmdir()
        except OSError:
            continue


def podar_temporales(
    dias: int = 7,
    max_tamano_mb: int = 500,
    *,
    raiz: Path | None = None,
    aplicar: bool = True,
    ahora: float | None = None,
) -> Poda:
    """Limpia `salida/_3d`, los audios de voz no referenciados, los borradores de la vista previa
    (`salida/_vistas/<estilo>/<video>/`, si todo lo de adentro es viejo) y los trozos que Manim ya unió.
    Nunca toca videos finales ni borradores, subtítulos, kits, portadas ni `linea_de_tiempo.json`.

    ``dias`` es la edad mínima para borrar; ``max_tamano_mb`` es la cuota de `salida/_3d` (si se pasa,
    se borran los PNG/JSON más viejos primero). Con ``aplicar=False`` sólo devuelve lo que borraría.
    """
    base = Path(raiz) if raiz is not None else raiz_proyecto()
    limite = (time.time() if ahora is None else ahora) - max(0, dias) * 86400
    cuota = max(0, max_tamano_mb) * 1024 * 1024

    candidatos = _podar_3d(base / "salida" / "_3d", limite, cuota)
    candidatos += _podar_voz(base, limite)
    candidatos += _podar_vistas(base, limite)
    candidatos += _podar_trozos(base, limite)

    vistos: list[Path] = []
    for ruta in candidatos:
        if ruta not in vistos:
            vistos.append(ruta)
    if not aplicar:
        return Poda(archivos=vistos, bytes=sum(_tamano(ruta) for ruta in vistos))

    borrados: list[Path] = []
    liberados = 0
    for ruta in vistos:
        tamano = _tamano(ruta)
        try:
            ruta.unlink()
        except OSError:
            continue
        borrados.append(ruta)
        liberados += tamano
    _quitar_carpetas_vacias(borrados, base)
    return Poda(archivos=borrados, bytes=liberados)
