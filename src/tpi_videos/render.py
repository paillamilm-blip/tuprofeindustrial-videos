"""Pipeline completo: guion → Manim (animación + voz) → subtítulos → MP4 final."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import entorno
from .config import CALIDADES, Marca, cargar_marca
from .errores import ErrorMotor
from .guion import Guion, cargar_guion, sin_tildes


@dataclass
class ResultadoVideo:
    video: Path
    carpeta: Path
    duracion: float
    segundos_proceso: float
    srt: Path | None = None
    fuentes_tiempo: set[str] = field(default_factory=set)


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes(texto.lower())).strip("-") or "video"


def verificar_requisitos(subtitulos: bool) -> None:
    """Falla rápido (antes de renderizar minutos) si falta algo esencial."""
    entorno.preparar()
    latex, dvisvgm = entorno.latex_disponible()
    if not latex or not dvisvgm:
        falta = "LaTeX" if not latex else "dvisvgm (parte de LaTeX)"
        raise ErrorMotor(
            f"Falta {falta}, que se usa para dibujar las fórmulas.",
            ayuda="Ejecuta ./scripts/instalar_mac.sh y luego ./tpi doctor",
        )
    if subtitulos and entorno.ffmpeg_con_libass() is None:
        raise ErrorMotor(
            "Para los subtítulos necesitas FFmpeg con libass.",
            ayuda="En Mac: brew install ffmpeg-full   (o crea el video sin subtítulos: --sin-subtitulos)",
        )


def renderizar_manim(
    guion: Guion, marca: Marca, calidad: str, proveedor: str, voz: str, velocidad: str, carpeta: Path
) -> tuple[Path, dict]:
    entorno.preparar()
    entorno.registrar_fuentes()
    from manim import tempconfig

    from .escena import OpcionesEscena, VideoEjercicio
    from .tex import plantilla_tex

    cal = CALIDADES[calidad]
    linea = carpeta / "linea_de_tiempo.json"
    configuracion = {
        "pixel_width": cal.ancho,
        "pixel_height": cal.alto,
        "frame_rate": cal.fps,
        "frame_width": 9.0,
        "frame_height": 16.0,
        "media_dir": str(carpeta / "manim"),
        "output_file": "animacion",
        "disable_caching": True,  # obligatorio con manim-voiceover
        "background_color": marca.colores.fondo,
        "tex_template": plantilla_tex(),
        "verbosity": "ERROR",
        "progress_bar": "display",
        "video_encoder_options": {"crf": "12"},  # intermedio de alta calidad (se recodifica al final)
    }
    with tempconfig(configuracion):
        escena = VideoEjercicio(
            guion=guion, marca=marca, opciones=OpcionesEscena(proveedor, voz, velocidad, linea)
        )
        escena.render()
        video = Path(escena.renderer.file_writer.final_file_path)
    return video, json.loads(linea.read_text(encoding="utf-8"))


def crear_video(
    ruta_guion: str | Path,
    calidad: str = "final",
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    subtitulos: bool = True,
    sincronizar: str = "auto",
    modelo_whisper: str = "base",
    carpeta_salida: Path | None = None,
) -> ResultadoVideo:
    from .postproduccion import duracion, quemar_subtitulos, recodificar
    from .subtitulos import agrupar, escribir_ass, escribir_srt, palabras_de_bloques

    inicio = time.time()
    if calidad not in CALIDADES:
        raise ErrorMotor(f"Calidad «{calidad}» no existe.", ayuda=f"Opciones: {', '.join(CALIDADES)}")
    guion = cargar_guion(ruta_guion)
    marca = cargar_marca()
    verificar_requisitos(subtitulos)

    proveedor = proveedor or marca.voz.proveedor
    voz = voz or guion.voz or marca.voz.nombre
    velocidad = velocidad or guion.velocidad or marca.voz.velocidad
    nombre = slug(Path(ruta_guion).stem)
    carpeta = (carpeta_salida or entorno.raiz_proyecto() / "salida") / nombre
    carpeta.mkdir(parents=True, exist_ok=True)

    video_manim, linea = renderizar_manim(guion, marca, calidad, proveedor, voz, velocidad, carpeta)
    final = carpeta / (f"{nombre}.mp4" if calidad == "final" else f"{nombre}_{calidad}.mp4")
    resultado = ResultadoVideo(video=final, carpeta=carpeta, duracion=0.0, segundos_proceso=0.0)

    if subtitulos:
        palabras, resultado.fuentes_tiempo = palabras_de_bloques(
            linea["bloques"], sincronizar, modelo_whisper
        )
        estilo = marca.subtitulos
        ass = escribir_ass(
            agrupar(palabras, estilo.max_palabras, estilo.max_caracteres), carpeta / "subtitulos.ass", estilo
        )
        resultado.srt = escribir_srt(palabras, carpeta / f"{nombre}.srt")
        quemar_subtitulos(video_manim, ass, final, CALIDADES[calidad])
    else:
        recodificar(video_manim, final, CALIDADES[calidad])

    resultado.duracion = duracion(final)
    resultado.segundos_proceso = time.time() - inicio
    return resultado


def subtitular_video(
    video: Path, texto: str | None = None, modelo: str = "base", carpeta_salida: Path | None = None
) -> Path:
    """Agrega subtítulos estilo CapCut a cualquier video usando Whisper."""
    from . import whisper_sync
    from .postproduccion import quemar_subtitulos, resolucion
    from .subtitulos import Palabra, agrupar, alinear, escribir_ass, escribir_srt

    entorno.preparar()
    if not video.exists():
        raise ErrorMotor(f"No encuentro el video «{video}».")
    if not whisper_sync.disponible():
        raise ErrorMotor(
            "Para subtitular videos externos se necesita Whisper.",
            ayuda='Instálalo con: .venv/bin/pip install -e ".[whisper]"',
        )
    if entorno.ffmpeg_con_libass() is None:
        raise ErrorMotor(
            "Tu FFmpeg no puede dibujar subtítulos (le falta libass).",
            ayuda="En Mac: brew install ffmpeg-full",
        )

    nombre = slug(video.stem)
    carpeta = (carpeta_salida or entorno.raiz_proyecto() / "salida" / "subtitulados") / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    reconocidas = whisper_sync.transcribir(
        video, modelo=modelo, prompt=texto, cache=carpeta / f"whisper-{modelo}.json"
    )
    if texto:  # texto exacto conocido: se muestra tal cual, Whisper solo pone los tiempos
        palabras_guion = texto.split()
        fin = reconocidas[-1][2] if reconocidas else 0.0
        palabras = [
            Palabra(p, a, b)
            for p, (a, b) in zip(palabras_guion, alinear(palabras_guion, reconocidas, fin), strict=True)
        ]
    else:
        palabras = [Palabra(p, a, b) for p, a, b in reconocidas]
    if not palabras:
        raise ErrorMotor("Whisper no encontró voz en el video.")

    ancho, alto = resolucion(video)
    base = min(ancho, alto)
    estilo = cargar_marca().subtitulos
    ass = escribir_ass(
        agrupar(palabras, estilo.max_palabras, estilo.max_caracteres),
        carpeta / "subtitulos.ass",
        estilo,
        ancho=round(1080 * ancho / base),
        alto=round(1080 * alto / base),
    )
    escribir_srt(palabras, carpeta / f"{nombre}.srt")
    salida = carpeta / f"{nombre}_subtitulado.mp4"
    return quemar_subtitulos(video, ass, salida, CALIDADES["final"])
