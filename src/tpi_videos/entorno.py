"""Prepara el entorno de ejecución.

- Agrega al PATH las carpetas típicas de LaTeX (MacTeX/BasicTeX/TinyTeX) y de FFmpeg completo
  (``ffmpeg-full`` de Homebrew, que sí trae libass para quemar subtítulos).
- Registra las letras incluidas en el repo (Montserrat, Comic Neue, Bangers…).
- Silencia avisos ruidosos de librerías que no aportan nada al usuario.
"""

from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
import warnings
from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
FUENTES_DIR = PAQUETE / "assets" / "fuentes"
PLANTILLAS_DIR = PAQUETE / "plantillas"

CARPETAS_LATEX = (
    "/Library/TeX/texbin",  # MacTeX y BasicTeX
    "~/Library/TinyTeX/bin/universal-darwin",  # TinyTeX en Mac
    "~/.TinyTeX/bin/x86_64-linux",  # TinyTeX en Linux
)
# ffmpeg-full es "keg-only" en Homebrew: no queda en el PATH, por eso lo buscamos aquí.
CARPETAS_FFMPEG = (
    "/opt/homebrew/opt/ffmpeg-full/bin",  # Mac con chip Apple (M1, M2, M3…)
    "/usr/local/opt/ffmpeg-full/bin",  # Mac con chip Intel
)


def raiz_proyecto() -> Path:
    """Carpeta raíz del repo (donde están marca.yaml, guiones/ y salida/)."""
    env = os.environ.get("TPI_RAIZ")
    if env:
        return Path(env).expanduser().resolve()
    repo = PAQUETE.parents[1]  # .../repo/src/tpi_videos → .../repo
    if (repo / "pyproject.toml").exists():
        return repo
    return Path.cwd()


def _anteponer_al_path(carpetas: list[str]) -> None:
    actuales = os.environ.get("PATH", "").split(os.pathsep)
    nuevas = []
    for carpeta in carpetas:
        ruta = str(Path(carpeta).expanduser())
        if Path(ruta).is_dir() and ruta not in actuales and ruta not in nuevas:
            nuevas.append(ruta)
    if nuevas:
        os.environ["PATH"] = os.pathsep.join([*nuevas, *actuales])


def silenciar_avisos() -> None:
    # pydub trae expresiones regulares antiguas que generan SyntaxWarning en Python 3.12+.
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    # El paquete "sox" (lo importa manim-voiceover) avisa que falta SoX aunque el motor no lo
    # necesita. Reajusta su propio nivel al importarse, por eso se usa un filtro.
    registro_sox = logging.getLogger("sox")
    if not any(getattr(f, "_tpi", False) for f in registro_sox.filters):
        filtro = logging.Filter()
        filtro.filter = lambda registro: False  # type: ignore[method-assign]
        filtro._tpi = True  # type: ignore[attr-defined]
        registro_sox.addFilter(filtro)
        _importar_sox_en_silencio()
    # PyAV avisa de opciones internas de Manim que no usa ("Some options were not used").
    logging.getLogger("av.container.output").setLevel(logging.ERROR)
    # Gemini (google-genai) y su cliente HTTP anuncian cada petición a nivel INFO.
    for nombre in ("google_genai", "httpx", "httpcore"):
        logging.getLogger(nombre).setLevel(logging.WARNING)


def _importar_sox_en_silencio() -> None:
    """Al importarse, "sox" ejecuta `sox -h` y, si no existe, la terminal muestra
    "sox: command not found". Se importa una vez con la salida de errores tapada."""
    import sys

    try:
        fd = sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        return
    copia, nulo = os.dup(fd), os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(nulo, fd)
        import sox  # noqa: F401
    except Exception:
        pass
    finally:
        os.dup2(copia, fd)
        os.close(copia)
        os.close(nulo)


@functools.cache
def preparar() -> None:
    """Deja listo el entorno. Es seguro llamarla varias veces."""
    silenciar_avisos()
    extra_tex = [os.environ["TPI_TEX_BIN"]] if os.environ.get("TPI_TEX_BIN") else []
    _anteponer_al_path([*extra_tex, *CARPETAS_LATEX])
    _anteponer_al_path(list(CARPETAS_FFMPEG))


@functools.cache
def registrar_fuentes() -> bool:
    """Registra las letras incluidas para Manim (Pango). Devuelve False si no se pudo."""
    import manimpango

    ok = True
    for ttf in sorted(FUENTES_DIR.glob("*.ttf")):
        ok = bool(manimpango.register_font(str(ttf))) and ok
    return ok


def _tiene_filtro_ass(ffmpeg: str) -> bool:
    try:
        salida = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    for linea in salida.splitlines():
        partes = linea.split()
        if len(partes) >= 2 and partes[1] == "ass":
            return True
    return False


@functools.cache
def ffmpeg_con_libass() -> str | None:
    """Ruta a un FFmpeg capaz de quemar subtítulos ASS (requiere libass), o None."""
    preparar()
    candidatos = [os.environ.get("TPI_FFMPEG")]
    candidatos += [str(Path(c) / "ffmpeg") for c in CARPETAS_FFMPEG]
    candidatos.append(shutil.which("ffmpeg"))
    vistos: set[str] = set()
    for candidato in candidatos:
        if not candidato or candidato in vistos or not Path(candidato).exists():
            continue
        vistos.add(candidato)
        if _tiene_filtro_ass(candidato):
            return candidato
    return None


@functools.cache
def ffmpeg_cualquiera() -> str | None:
    """Cualquier FFmpeg disponible (aunque no tenga libass)."""
    return ffmpeg_con_libass() or shutil.which("ffmpeg")


def latex_disponible() -> tuple[str | None, str | None]:
    """Rutas de ``latex`` y ``dvisvgm`` (las dos herramientas que usa Manim)."""
    preparar()
    return shutil.which("latex"), shutil.which("dvisvgm")
