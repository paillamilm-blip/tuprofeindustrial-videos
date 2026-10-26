"""Piezas comunes del panel: estilo visual, marco de cada página y ayudas."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from nicegui import ui

from ..entorno import raiz_proyecto
from .tareas import TAREAS

AZUL = "#1C3D74"
ROJO = "#D32F2F"
VERDE = "#2E7D32"
GRIS = "#6B6B6B"  # el gris que sí se lee sobre el blanco (4,5:1)

PAGINAS = (
    ("/", "Fábrica", "bolt"),
    ("/crear", "Crear", "movie_creation"),
    ("/videos", "Mis videos", "video_library"),
    ("/estilos", "Estilos", "palette"),
    ("/ajustes", "Ajustes", "tune"),
)

CSS = f"""
@font-face {{ font-family: 'Comic Neue'; src: url('/fuentes/ComicNeue-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'Comic Neue'; src: url('/fuentes/ComicNeue-Bold.ttf'); font-weight: 700; }}
@font-face {{ font-family: 'Bangers'; src: url('/fuentes/Bangers-Regular.ttf'); }}
@font-face {{ font-family: 'Montserrat'; src: url('/fuentes/Montserrat-SemiBold.ttf'); font-weight: 600; }}
body {{
  background-color: #F3F3F0;
  background-image: linear-gradient(#E4E4E0 1px, transparent 1px),
                    linear-gradient(90deg, #E4E4E0 1px, transparent 1px);
  background-size: 24px 24px;
  color: #262626;
}}
.tpi-marca {{ font-family: 'Comic Neue', sans-serif; font-weight: 700; letter-spacing: .03em; }}
.tpi-titulo {{ font-family: 'Comic Neue', sans-serif; font-weight: 700; color: {AZUL}; text-transform: uppercase; }}
.tpi-hoja {{ background: #FFFFFF; border: 1px solid #DCDCD7; border-radius: 14px; }}
.tpi-paso-num {{ font-family: 'Comic Neue', sans-serif; font-weight: 700; color: #fff; background: {AZUL};
  border-radius: 999px; width: 28px; height: 28px; display: inline-flex; align-items: center;
  justify-content: center; flex-shrink: 0; }}
.tpi-error {{ border-left: 4px solid {ROJO}; }}
.tpi-nav a {{ color: #fff; text-decoration: none; padding: 6px 12px; border-radius: 8px; opacity: .85; }}
.tpi-nav a:hover {{ background: rgba(255,255,255,.12); opacity: 1; }}
.tpi-nav a.activa {{ background: rgba(255,255,255,.18); opacity: 1; box-shadow: inset 0 -3px 0 {ROJO}; }}
.tpi-bangers {{ font-family: 'Bangers', cursive; letter-spacing: .04em; }}
.tpi-ayuda {{ color: #6B6B6B; font-size: .85rem; }}
"""


def url_medio(ruta: Path | None) -> str:
    """URL para mostrar un archivo de salida/ o mis_ajustes/ (con la fecha, para no ver una versión vieja)."""
    if ruta is None or not ruta.exists():
        return ""
    raiz = raiz_proyecto()
    ruta = ruta.resolve()
    v = int(ruta.stat().st_mtime)
    for base, prefijo in (
        (raiz / "salida", "/medios/salida"),
        (raiz / "mis_ajustes" / "stickers", "/medios/stickers"),
        (raiz / "mis_ajustes" / "fondos", "/medios/fondos"),
    ):
        try:
            relativa = ruta.relative_to(base.resolve())
        except ValueError:
            continue
        return f"{prefijo}/{relativa.as_posix()}?v={v}"
    return ""


def abrir_en_mac(ruta: Path, mostrar_en_finder: bool = False) -> None:
    if platform.system() == "Darwin":
        comando = ["open", "-R", str(ruta)] if mostrar_en_finder else ["open", str(ruta)]
    else:
        comando = ["xdg-open", str(ruta.parent if mostrar_en_finder else ruta)]
    try:
        subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        ui.notify("No pude abrirlo en este computador.", type="warning")


def _estado_tarea(chip: ui.chip) -> None:
    t = TAREAS.actual
    if t is None or (t.terminada and not t.reciente()):
        chip.set_visibility(False)
        return
    chip.set_visibility(True)
    if t.terminada:
        chip.text = "✅ Listo" if t.ok else ("⏹ Cancelado" if t.cancelada else "❌ Falló")
    else:
        chip.text = f"⏳ {t.nombre} · {round(t.avance * 100)} %"


@contextmanager
def marco(ruta_activa: str) -> Iterator[None]:
    """Encabezado con la marca y el menú; el contenido de la página va dentro del bloque."""
    ui.add_css(CSS)
    ui.colors(primary=AZUL, secondary="#5B6B86", accent=ROJO, positive=VERDE, negative=ROJO)
    with ui.header().classes("items-center justify-between px-6 py-2").style(f"background:{AZUL}"):
        with ui.row().classes("items-center gap-3"):
            ui.image("/marca/panel.png").classes("w-11 h-11").props('alt="" no-spinner no-transition')
            with ui.column().classes("gap-0"):
                ui.label("TU PROFE INDUSTRIAL").classes("tpi-marca text-lg leading-tight")
                ui.label("Motor de video · panel de control").classes("text-xs opacity-80")
        with ui.row().classes("tpi-nav items-center gap-1"):
            for ruta, nombre, icono in PAGINAS:
                clase = "activa" if ruta == ruta_activa else ""
                with ui.link(target=ruta).classes(f"{clase} flex items-center gap-1"):
                    ui.icon(icono).classes("text-lg")
                    ui.label(nombre)
        chip = ui.chip("", color="white", text_color="primary").props("outline").classes("bg-white")
        chip.set_visibility(False)
        ui.timer(0.7, lambda: _estado_tarea(chip))
    with ui.column().classes("w-full max-w-6xl mx-auto px-4 py-6 gap-6"):
        yield


def titulo_seccion(numero: str | None, texto: str, ayuda: str | None = None) -> None:
    with ui.row().classes("items-center gap-3"):
        if numero:
            ui.label(numero).classes("tpi-paso-num")
        ui.label(texto).classes("tpi-titulo text-xl")
    if ayuda:
        ui.label(ayuda).classes("tpi-ayuda -mt-2")


def confirmar(pregunta: str, accion: Callable[[], object], boton: str = "Sí, borrar") -> None:
    with ui.dialog() as dialogo, ui.card().classes("p-6"):
        ui.label(pregunta).classes("text-base")
        with ui.row().classes("justify-end w-full gap-2 mt-4"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")

            async def si() -> None:
                dialogo.close()
                resultado = accion()
                if hasattr(resultado, "__await__"):
                    await resultado

            ui.button(boton, on_click=si, color="negative")
    dialogo.open()
