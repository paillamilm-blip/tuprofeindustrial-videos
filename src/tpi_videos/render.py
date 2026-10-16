"""Pipeline completo: guion → Manim (animación + voz) → subtítulos → MP4 final."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import entorno
from .config import CALIDADES, Marca, cargar_marca
from .errores import ErrorMotor
from .guion import Guion, cargar_guion, sin_tildes
from .temas import Tema, cargar_tema

# progreso(etapa, avance 0–1, detalle): para barras de progreso (panel y --progreso-json)
Progreso = Callable[[str, float, str], None]


@dataclass
class ResultadoVideo:
    video: Path
    carpeta: Path
    duracion: float
    segundos_proceso: float
    srt: Path | None = None
    fuentes_tiempo: set[str] = field(default_factory=set)
    tema: str = ""  # nombre visible del estilo usado


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
    guion: Guion,
    marca: Marca,
    tema: Tema,
    calidad: str,
    proveedor: str,
    voz: str,
    velocidad: str,
    carpeta: Path,
    progreso: Callable[[int, int, str], None] | None = None,
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
        "background_color": tema.colores.fondo,
        "tex_template": plantilla_tex(negrita=tema.formulas_negrita),
        "verbosity": "ERROR",
        "progress_bar": "none" if progreso else "display",
        # Intermedio de alta calidad (se recodifica al final). "veryfast" lo hace ~2× más rápido con fondos
        # con detalle (foto, hoja); el estilo original conserva su configuración y sale idéntico a antes.
        "video_encoder_options": {"crf": "12"} if tema.usar_marca else {"crf": "12", "preset": "veryfast"},
    }
    with tempconfig(configuracion):
        escena = VideoEjercicio(
            guion=guion,
            marca=marca,
            tema=tema,
            opciones=OpcionesEscena(proveedor, voz, velocidad, linea, progreso=progreso),
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
    tema: str | None = None,
    progreso: Progreso | None = None,
) -> ResultadoVideo:
    """Crea el video. Estilo: ``tema`` (si se pide) > ``tema:`` del guion > ``tema:`` de marca.yaml."""
    from .postproduccion import duracion, quemar_subtitulos, recodificar
    from .subtitulos import agrupar, escribir_ass, escribir_srt, palabras_de_bloques

    def avisar(etapa: str, avance: float, detalle: str = "") -> None:
        if progreso:
            progreso(etapa, round(min(max(avance, 0.0), 1.0), 3), detalle)

    inicio = time.time()
    if calidad not in CALIDADES:
        raise ErrorMotor(f"Calidad «{calidad}» no existe.", ayuda=f"Opciones: {', '.join(CALIDADES)}")
    guion = cargar_guion(ruta_guion)
    marca = cargar_marca()
    estilo_video = cargar_tema(tema or guion.tema, marca)
    verificar_requisitos(subtitulos)
    avisar("preparando", 0.02, estilo_video.nombre)

    proveedor = proveedor or marca.voz.proveedor
    voz = voz or guion.voz or marca.voz.nombre
    velocidad = velocidad or guion.velocidad or marca.voz.velocidad
    nombre = slug(Path(ruta_guion).stem)
    carpeta = (carpeta_salida or entorno.raiz_proyecto() / "salida") / nombre
    carpeta.mkdir(parents=True, exist_ok=True)

    def por_bloque(actual: int, total: int, seccion: str) -> None:
        avisar("animacion", 0.04 + 0.8 * (actual - 1) / max(total, 1), seccion)

    video_manim, linea = renderizar_manim(
        guion, marca, estilo_video, calidad, proveedor, voz, velocidad, carpeta,
        progreso=por_bloque if progreso else None,
    )  # fmt: skip
    final = carpeta / (f"{nombre}.mp4" if calidad == "final" else f"{nombre}_{calidad}.mp4")
    resultado = ResultadoVideo(
        video=final, carpeta=carpeta, duracion=0.0, segundos_proceso=0.0, tema=estilo_video.nombre
    )

    if subtitulos:
        avisar("subtitulos", 0.86, "sincronizando palabras")
        palabras, resultado.fuentes_tiempo = palabras_de_bloques(
            linea["bloques"], sincronizar, modelo_whisper
        )
        estilo = estilo_video.subtitulos
        ass = escribir_ass(
            agrupar(palabras, estilo.max_palabras, estilo.max_caracteres), carpeta / "subtitulos.ass", estilo
        )
        resultado.srt = escribir_srt(palabras, carpeta / f"{nombre}.srt")
        avisar("video final", 0.9, "uniendo animación, voz y subtítulos")
        quemar_subtitulos(video_manim, ass, final, CALIDADES[calidad])
    else:
        avisar("video final", 0.9, "uniendo animación y voz")
        recodificar(video_manim, final, CALIDADES[calidad])

    resultado.duracion = duracion(final)
    resultado.segundos_proceso = time.time() - inicio
    avisar("listo", 1.0, str(final))
    return resultado


def subtitular_video(
    video: Path,
    texto: str | None = None,
    modelo: str = "base",
    carpeta_salida: Path | None = None,
    tema: str | None = None,
) -> Path:
    """Agrega subtítulos estilo CapCut a cualquier video usando Whisper (con la letra del tema)."""
    from . import whisper_sync
    from .postproduccion import quemar_subtitulos, resolucion
    from .subtitulos import Palabra, agrupar, alinear, escribir_ass, escribir_srt

    entorno.preparar()
    if not video.exists():
        raise ErrorMotor(f"No encuentro el video «{video}».")
    estilo = cargar_tema(tema, cargar_marca()).subtitulos  # antes de escuchar: si el tema no existe, avisa ya
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
