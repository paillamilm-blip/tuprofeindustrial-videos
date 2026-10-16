"""Postproducción con FFmpeg: quemar subtítulos, normalizar volumen y dejar el MP4 listo
para TikTok / Reels / Shorts (H.264 + AAC, yuv420p, faststart, −14 LUFS)."""

from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import entorno
from .config import Calidad
from .errores import ErrorMotor

_RUTA_SEGURA = re.compile(r"^[A-Za-z0-9._/-]+$")


@functools.cache
def _codec_video(ffmpeg: str) -> list[str]:
    salida = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if " libx264 " in salida:
        return ["-c:v", "libx264"]
    if " h264_videotoolbox " in salida:  # codificador por hardware de Mac
        return ["-c:v", "h264_videotoolbox", "-b:v", "10M"]
    return ["-c:v", "mpeg4", "-q:v", "2"]


def _codificacion(ffmpeg: str, calidad: Calidad) -> list[str]:
    video = _codec_video(ffmpeg)
    if video[1] == "libx264":
        video += ["-preset", calidad.preset, "-crf", str(calidad.crf)]
    return [
        *video,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",  # volumen estándar de redes sociales
        "-movflags", "+faststart",
    ]  # fmt: skip


def _ejecutar(comando: list[str], cwd: Path, que: str) -> None:
    proceso = subprocess.run(comando, cwd=cwd, capture_output=True, text=True)
    if proceso.returncode != 0:
        detalle = "\n".join(proceso.stderr.strip().splitlines()[-6:])
        raise ErrorMotor(f"FFmpeg falló al {que}:\n{detalle}", ayuda="Revisa ./tpi doctor")


def _carpeta_fuentes_relativa(desde: Path) -> str:
    """Ruta relativa y sin caracteres especiales a las fuentes (para el filtro de FFmpeg)."""
    relativa = Path(os.path.relpath(entorno.FUENTES_DIR, desde)).as_posix()
    if _RUTA_SEGURA.match(relativa):
        return relativa
    copia = desde / ".fuentes"
    if not copia.exists():
        shutil.copytree(entorno.FUENTES_DIR, copia)
    return ".fuentes"


def quemar_subtitulos(video: Path, ass: Path, salida: Path, calidad: Calidad) -> Path:
    ffmpeg = entorno.ffmpeg_con_libass()
    if ffmpeg is None:
        raise ErrorMotor(
            "Tu FFmpeg no puede dibujar subtítulos (le falta libass).",
            ayuda="En Mac instala la versión completa: brew install ffmpeg-full   (luego: ./tpi doctor)",
        )
    carpeta = ass.parent
    fuentes = _carpeta_fuentes_relativa(carpeta)
    _ejecutar(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video.resolve()),
            "-vf", f"ass={ass.name}:fontsdir={fuentes}",
            *_codificacion(ffmpeg, calidad),
            str(salida.resolve()),
        ],
        cwd=carpeta,
        que="quemar los subtítulos",
    )  # fmt: skip
    return salida


def recodificar(video: Path, salida: Path, calidad: Calidad) -> Path:
    """Sin subtítulos: solo normaliza volumen y deja el formato listo para redes."""
    ffmpeg = entorno.ffmpeg_cualquiera()
    if ffmpeg is None:  # sin FFmpeg el video de Manim igual sirve
        shutil.copyfile(video, salida)
        return salida
    _ejecutar(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video.resolve()),
         *_codificacion(ffmpeg, calidad), str(salida.resolve())],
        cwd=salida.parent,
        que="preparar el video final",
    )  # fmt: skip
    return salida


def duracion(video: Path) -> float:
    import av

    with av.open(str(video)) as contenedor:
        return float(contenedor.duration or 0) / 1_000_000


def extraer_cuadro(video: Path, segundos: float, destino: Path, ancho: int | None = None) -> Path:
    """Guarda como imagen (PNG o JPG) el cuadro del video en ``segundos``."""
    import av
    from PIL import Image

    objetivo = max(0.0, segundos)
    try:
        with av.open(str(video)) as contenedor:
            flujo = contenedor.streams.video[0]
            contenedor.seek(int(objetivo / flujo.time_base), stream=flujo, backward=True)
            cuadro = None
            for cuadro in contenedor.decode(flujo):
                if cuadro.time is not None and cuadro.time >= objetivo - 1e-3:
                    break
            if cuadro is None:
                raise ErrorMotor(f"No pude leer un cuadro de {video.name}.")
            imagen = cuadro.to_image()
    except av.error.FFmpegError as e:
        raise ErrorMotor(f"No pude abrir el video {video.name}.") from e
    if ancho and imagen.width != ancho:
        imagen = imagen.resize((ancho, round(imagen.height * ancho / imagen.width)), Image.LANCZOS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.suffix.lower() in (".jpg", ".jpeg"):
        imagen.convert("RGB").save(destino, quality=88)
    else:
        imagen.save(destino)
    return destino


def resolucion(video: Path) -> tuple[int, int]:
    import av

    with av.open(str(video)) as contenedor:
        flujo = contenedor.streams.video[0]
        return int(flujo.width), int(flujo.height)
