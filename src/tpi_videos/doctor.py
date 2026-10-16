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


def _chequear_estilos() -> Chequeo:
    """El tema por defecto se puede cargar y están los emojis 3D."""
    from .config import cargar_marca
    from .emojis import EMOJIS, EMOJIS_DIR
    from .errores import ErrorMotor
    from .temas import cargar_tema, listar_temas

    nombre = "Estilos y emojis"
    try:
        tema = cargar_tema(None, cargar_marca())
    except ErrorMotor as e:
        return Chequeo(
            nombre, "falla", e.mensaje, e.ayuda or "Revisa «tema:» en marca.yaml (ver ./tpi temas)."
        )
    faltan = [n for n in EMOJIS.values() if not (EMOJIS_DIR / f"{n}.png").exists()]
    if faltan:
        return Chequeo(
            nombre, "falla", f"faltan {len(faltan)} emojis", "Vuelve a descargar el repo (git pull)."
        )
    return Chequeo(
        nombre, "ok", f"estilo «{tema.nombre}» · {len(listar_temas())} temas · {len(EMOJIS)} emojis 3D"
    )


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

    from . import tipografia

    faltan = tipografia.faltantes()
    try:
        registradas = entorno.registrar_fuentes()
    except Exception:
        registradas = False
    ok_letras = not faltan and registradas
    if ok_letras:
        detalle = f"{len(tipografia.FAMILIAS)} familias ({', '.join(tipografia.FAMILIAS)})"
    else:
        detalle = f"faltan: {', '.join(faltan)}" if faltan else "no se pudieron registrar"
    chequeos.append(
        Chequeo(
            "Letras",
            "ok" if ok_letras else "falla",
            detalle,
            None if ok_letras else "Vuelve a descargar el repo (git pull).",
        )
    )
    chequeos.append(_chequear_estilos())
    version_panel = _version("nicegui")
    chequeos.append(
        Chequeo(
            "Panel de control",
            "ok" if version_panel else "falla",
            f"NiceGUI {version_panel} · ábrelo con ./tpi panel" if version_panel else "no instalado",
            None if version_panel else "Ejecuta ./scripts/instalar_mac.sh (instala lo nuevo)",
        )
    )
    from .icono import NOMBRE, escritorio

    icono = escritorio() / NOMBRE
    donde = "en tu Escritorio" if icono.parent.name == "Desktop" else str(icono)
    chequeos.append(
        Chequeo(
            "Ícono del panel (opcional)",
            "ok" if icono.exists() else "opcional",
            donde if icono.exists() else "no está en tu Escritorio",
            None if icono.exists() else "Créalo con: ./tpi icono (te lo muestra en Finder)",
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

    from . import ia

    clave = ia.obtener_clave()
    if clave and probar_red:
        try:
            ia.probar_clave(clave)
            chequeos.append(
                Chequeo("IA para redactar (opcional)", "ok", f"clave válida · {ia.MODELO_POR_DEFECTO}")
            )
        except Exception as e:  # ErrorMotor con el motivo
            chequeos.append(Chequeo("IA para redactar (opcional)", "falla", getattr(e, "mensaje", str(e)),
                                    getattr(e, "ayuda", None)))  # fmt: skip
    else:
        chequeos.append(
            Chequeo(
                "IA para redactar (opcional)",
                "ok" if clave else "opcional",
                "clave de Gemini configurada" if clave else "sin clave: ./tpi redactar no funcionará",
                None if clave else ia.AYUDA_CLAVE,
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
