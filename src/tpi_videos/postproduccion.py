"""Postproducción con FFmpeg: quemar subtítulos, normalizar volumen y dejar el MP4 listo
para TikTok / Reels / Shorts (H.264 + AAC, yuv420p, faststart, −14 LUFS)."""

from __future__ import annotations

import functools
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


def _codificacion(ffmpeg: str, calidad: Calidad, con_cama: bool = False) -> list[str]:
    video = _codec_video(ffmpeg)
    if video[1] == "libx264":
        video += ["-preset", calidad.preset, "-crf", str(calidad.crf)]
    audio = [] if con_cama else ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    return [
        *video,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        *audio,  # con cama el loudnorm va dentro del filter_complex (mezcla voz + cama)
        "-movflags", "+faststart",
    ]  # fmt: skip


def _argumentos_cama(cama: Path, volumen: float) -> list[str]:
    """Entrada en bucle + mezcla: la cama suena bajo la voz durante todo el video, sin aire muerto."""
    # La voz «empuja» la música hacia abajo mientras habla (sidechain) y la deja volver en las pausas:
    # se escucha la música sin que tape ni una palabra.
    formato = "aformat=sample_rates=48000:channel_layouts=stereo"
    cadena = (
        f"[0:a]{formato},asplit=2[voz][llave];"
        f"[1:a]{formato},volume={volumen}[cama0];"
        # suave: cuando hablas baja unos pocos dB (antes bajaba tanto que desaparecía)
        "[cama0][llave]sidechaincompress=threshold=0.06:ratio=2:attack=60:release=450:makeup=1[cama];"
        "[voz][cama]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mezcla];"
        "[mezcla]loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
    )
    return [
        "-stream_loop", "-1", "-i", str(cama.resolve()),
        "-filter_complex", cadena,
        "-map", "0:v", "-map", "[aout]",
    ]  # fmt: skip


def _ejecutar(comando: list[str], cwd: Path, que: str) -> None:
    proceso = subprocess.run(comando, cwd=cwd, capture_output=True, text=True)
    if proceso.returncode != 0:
        detalle = "\n".join(proceso.stderr.strip().splitlines()[-6:])
        raise ErrorMotor(f"FFmpeg falló al {que}:\n{detalle}", ayuda="Revisa ./tpi doctor")


def _carpeta_fuentes(desde: Path) -> str:
    """Carpeta de fuentes para el filtro ``ass`` de FFmpeg, usable desde ``desde``.

    Preferimos la ruta absoluta del repo: una relativa con ``../`` que se sale del repo (o que cruza
    un symlink como /tmp → /private/tmp) no la resuelve libass y sustituye la fuente por la del
    sistema en silencio. Si la absoluta trae caracteres que rompen el filtro, copiamos las fuentes
    junto al video y usamos esa copia local.
    """
    absoluta = entorno.FUENTES_DIR.as_posix()
    if _RUTA_SEGURA.match(absoluta):
        return absoluta
    copia = desde / ".fuentes"
    if not copia.exists():
        shutil.copytree(entorno.FUENTES_DIR, copia)
    return ".fuentes"


_ASS_SONDA = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CapCut,Montserrat Black,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,6.0,2.0,5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,CapCut,,0,0,0,,PRUEBA
"""


def fuente_subtitulos_ok() -> tuple[bool, str]:
    """Sonda: quema un fotograma desde fuera del repo y confirma que libass usa la fuente incluida
    (y no la del sistema). Detecta la sustitución silenciosa antes de renderizar minutos."""
    import tempfile

    ffmpeg = entorno.ffmpeg_con_libass()
    if ffmpeg is None:
        return False, "FFmpeg con libass no disponible"
    with tempfile.TemporaryDirectory() as tmp:
        carpeta = Path(tmp)
        (carpeta / "sonda.ass").write_text(_ASS_SONDA, encoding="utf-8")
        fuentes = _carpeta_fuentes(carpeta)
        proceso = subprocess.run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "debug",
                "-f", "lavfi", "-i", "color=c=black:s=200x200:d=1",
                "-vf", f"ass=sonda.ass:fontsdir={fuentes}",
                "-frames:v", "1", "-y", str(carpeta / "sonda.png"),
            ],
            cwd=carpeta, capture_output=True, text=True,
        )
        seleccion = [l for l in proceso.stderr.splitlines() if "fontselect" in l]
        if any("Montserrat" in l for l in seleccion):
            return True, "Montserrat Black (libass la carga)"
        sustituta = seleccion[0].split("->")[-1].strip() if seleccion else "sin respuesta"
        return False, f"libass sustituyó la fuente por: {sustituta}"


def _cadena_resplandor(ancho: int, alto: int) -> str:
    """El halo de los temas neón: recorta lo brillante, lo desenfoca y lo devuelve sumado.

    Se hace en RGB porque ``screen`` sobre los planos de color de YUV tiñe todo el fondo.
    El desenfoque va a un tercio del tamaño: el halo no se beneficia del detalle fino
    y así el paso entero cuesta segundos, no minutos.
    """
    recorte = "if(gt(clipval,150),clipval,0)"
    return (
        "format=gbrp,split=2[base][brillo];"
        f"[brillo]scale={ancho // 3}:{alto // 3},"
        f"lutrgb=r='{recorte}':g='{recorte}':b='{recorte}',"
        f"gblur=sigma=9,scale={ancho}:{alto}[halo];"
        "[base][halo]blend=all_mode=screen:all_opacity=0.75"
    )  # fmt: skip


def quemar_subtitulos(
    video: Path, ass: Path, salida: Path, calidad: Calidad, resplandor: bool = False,
    cama: Path | None = None, volumen_cama: float = 0.18,
) -> Path:
    ffmpeg = entorno.ffmpeg_con_libass()
    if ffmpeg is None:
        raise ErrorMotor(
            "Tu FFmpeg no puede dibujar subtítulos (le falta libass).",
            ayuda="En Mac instala la versión completa: brew install ffmpeg-full   (luego: ./tpi doctor)",
        )
    carpeta = ass.parent
    fuentes = _carpeta_fuentes(carpeta)
    filtro = f"ass={ass.name}:fontsdir={fuentes}"
    if resplandor:
        ancho, alto = resolucion(video)
        # el resplandor va antes: los subtítulos se dibujan encima y quedan nítidos
        filtro = f"{_cadena_resplandor(ancho, alto)},{filtro}"
    extra = _argumentos_cama(cama, volumen_cama) if cama else []
    _ejecutar(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video.resolve()),
            *extra,  # la entrada de la cama va antes de cualquier filtro de salida (-vf)
            "-vf", filtro,
            *_codificacion(ffmpeg, calidad, con_cama=cama is not None),
            str(salida.resolve()),
        ],
        cwd=carpeta,
        que="quemar los subtítulos",
    )  # fmt: skip
    return salida


def recodificar(
    video: Path, salida: Path, calidad: Calidad, resplandor: bool = False,
    cama: Path | None = None, volumen_cama: float = 0.18,
) -> Path:
    """Sin subtítulos: solo normaliza volumen y deja el formato listo para redes."""
    ffmpeg = entorno.ffmpeg_cualquiera()
    if ffmpeg is None:  # sin FFmpeg el video de Manim igual sirve
        shutil.copyfile(video, salida)
        return salida
    argumentos = ["-hide_banner", "-loglevel", "error", "-y", "-i", str(video.resolve())]
    if cama:  # la entrada de la cama va antes de cualquier filtro de salida (-vf)
        argumentos += _argumentos_cama(cama, volumen_cama)
    if resplandor:
        ancho, alto = resolucion(video)
        argumentos += ["-vf", _cadena_resplandor(ancho, alto)]
    _ejecutar(
        [ffmpeg, *argumentos, *_codificacion(ffmpeg, calidad, con_cama=cama is not None), str(salida.resolve())],
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
