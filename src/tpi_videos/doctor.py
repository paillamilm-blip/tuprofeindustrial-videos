"""Diagnóstico del entorno (``./tpi doctor``): dice qué falta y cómo arreglarlo."""

from __future__ import annotations

import importlib.metadata
import platform
import sys
import tempfile
from dataclasses import dataclass

from . import entorno


@dataclass
class Chequeo:
    nombre: str
    estado: str  # "ok", "falla" u "opcional"
    detalle: str
    ayuda: str | None = None


def _version(paquete: str) -> str | None:
    try:
        return importlib.metadata.version(paquete)
    except importlib.metadata.PackageNotFoundError:
        return None


def _probar_latex() -> tuple[bool, str]:
    from manim import MathTex, tempconfig

    from .tex import plantilla_tex

    with (
        tempfile.TemporaryDirectory() as tmp,
        tempconfig({"media_dir": tmp, "tex_template": plantilla_tex(), "verbosity": "CRITICAL"}),
    ):
        try:
            MathTex(r"t = \sqrt{\frac{2h}{g}}")
            return True, "fórmula de prueba compilada"
        except Exception as e:  # el mensaje real queda en el log de LaTeX
            return False, str(e).splitlines()[0][:120]


def _probar_voz() -> tuple[bool, str]:
    import edge_tts

    try:
        audio = b"".join(
            t["data"]
            for t in edge_tts.Communicate("Hola", "es-CL-LorenzoNeural").stream_sync()
            if t["type"] == "audio"
        )
        return bool(audio), f"voz chilena respondió ({len(audio) // 1024} KB)"
    except Exception as e:
        return False, str(e)[:120]


def diagnosticar(probar_red: bool = False) -> list[Chequeo]:
    entorno.preparar()
    chequeos: list[Chequeo] = []

    ok_py = sys.version_info >= (3, 11)
    chequeos.append(
        Chequeo(
            "Python",
            "ok" if ok_py else "falla",
            platform.python_version(),
            None if ok_py else "Se necesita Python 3.11 o superior (el instalador usa 3.12).",
        )
    )

    for nombre, paquete in (
        ("Manim", "manim"),
        ("manim-voiceover", "manim-voiceover"),
        ("edge-tts", "edge-tts"),
    ):
        version = _version(paquete)
        chequeos.append(
            Chequeo(
                nombre,
                "ok" if version else "falla",
                version or "no instalado",
                None if version else "Ejecuta ./scripts/instalar_mac.sh",
            )
        )

    latex, dvisvgm = entorno.latex_disponible()
    if latex and dvisvgm:
        ok, detalle = _probar_latex()
        chequeos.append(
            Chequeo(
                "LaTeX (fórmulas)",
                "ok" if ok else "falla",
                detalle if ok else f"error: {detalle}",
                None if ok else "Instala los paquetes: sudo tlmgr install standalone preview dvisvgm",
            )
        )
    else:
        falta = "latex" if not latex else "dvisvgm"
        chequeos.append(
            Chequeo(
                "LaTeX (fórmulas)",
                "falla",
                f"no encuentro «{falta}»",
                "Ejecuta ./scripts/instalar_mac.sh (instala BasicTeX) y abre una terminal nueva.",
            )
        )

    ffmpeg = entorno.ffmpeg_con_libass()
    if ffmpeg:
        chequeos.append(Chequeo("FFmpeg con libass (subtítulos)", "ok", ffmpeg))
    else:
        otro = entorno.ffmpeg_cualquiera()
        chequeos.append(
            Chequeo(
                "FFmpeg con libass (subtítulos)",
                "falla",
                f"{otro} no trae libass" if otro else "no instalado",
                "brew install ffmpeg-full",
            )
        )

    fuentes = sorted(p.name for p in entorno.FUENTES_DIR.glob("*.ttf"))
    try:
        registradas = entorno.registrar_fuentes()
    except Exception:
        registradas = False
    chequeos.append(
        Chequeo(
            "Fuentes Montserrat",
            "ok" if fuentes and registradas else "falla",
            f"{len(fuentes)} estilos" if fuentes else "faltan archivos .ttf",
            None if fuentes and registradas else "Vuelve a descargar el repo (git pull).",
        )
    )

    from . import whisper_sync

    motivo = whisper_sync.problema()
    chequeos.append(
        Chequeo(
            "Whisper (opcional)",
            "ok" if motivo is None else "opcional",
            _version("openai-whisper")
            if motivo is None
            else f"{motivo}: los subtítulos usan las marcas de la voz",
            None
            if motivo is None
            else 'Para gTTS o `tpi subtitular`: uv pip install --python .venv/bin/python -e ".[whisper]"',
        )
    )

    if probar_red:
        ok, detalle = _probar_voz()
        chequeos.append(
            Chequeo(
                "Voz neural (internet)",
                "ok" if ok else "falla",
                detalle,
                None if ok else "Revisa tu conexión. Sin internet usa --voz silencio.",
            )
        )
    return chequeos
