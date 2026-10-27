"""El muro de las cuatro familias y su detalle al costado.

La lógica (qué familia está activa, qué trae decidido y con qué se cambia) va separada del widget: las
pantallas de NiceGUI no tienen pruebas en este repo y ésta es la pantalla que él va a usar todos los días.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from ..formatos import FORMATO_POR_DEFECTO, Formato, cargar_formatos, formato, puntuar_idea
from ..moldes import MOLDES
from ..temas import listar_temas
from ..visuales import VISUALES, opciones_select
from . import miniaturas
from .comun import PIEL, url_medio


@dataclass(frozen=True)
class Eleccion:
    activo: str
    la_puso_el_autor: bool


def sugerido(texto: str) -> str | None:
    """La familia que delata la idea escrita; None si la frase todavía no dice nada."""
    return puntuar_idea(texto)


def elegir(autor: str | None, sugerida: str | None = None) -> Eleccion:
    """Lo que el autor tocó gana a la sugerencia. Nada de esto bloquea el paso siguiente."""
    familias = cargar_formatos()
    if autor in familias:
        return Eleccion(autor, True)
    if sugerida in familias:
        return Eleccion(sugerida, False)
    return Eleccion(FORMATO_POR_DEFECTO, False)


def opciones_de(pieza: str) -> dict[str, str]:
    """Las opciones reales de cada pieza: las mismas listas que usa el motor, no una copia."""
    if pieza == "Molde":
        return {clave: molde.nombre for clave, molde in MOLDES.items()}
    if pieza == "Estilo":
        return {ident: tema.nombre for ident, tema, _propio in listar_temas()}
    return opciones_select()


def piezas(clave: str) -> list[tuple[str, str, dict[str, str]]]:
    """(nombre, valor elegido por la familia, opciones) — el valor se muestra siempre con su «cambiar»."""
    f = formato(clave)
    moldes, estilos, dibujos = opciones_de("Molde"), opciones_de("Estilo"), opciones_de("Dibujos")
    return [
        ("Molde", " o ".join(moldes.get(m, m) for m in f.moldes), moldes),
        ("Estilo", estilos.get(f.tema, f.tema), estilos),
        ("Dibujos", ", ".join(dibujos.get(d, d).split(" · ")[-1] for d in f.dibujos), dibujos),
    ]


def texto_del_pie(clave: str) -> str:
    """El llamado a comentar se muestra como pie de post: en el video no se pide nada."""
    return f"Lo que va en el pie del post (nunca en la voz del video): «{formato(clave).cta}»"


def visual_de_portada(clave: str) -> dict[str, Any]:
    """El dibujo típico de la familia, con los datos de ejemplo del catálogo.

    Sin esos datos el motor no dibuja nada («aún no está completo») y la tarjeta quedaría vacía: la portada
    tiene que mostrarse aunque el autor todavía no haya escrito el ejercicio.
    """
    f = formato(clave)
    return {"tipo": f.dibujos[0], **VISUALES[f.dibujos[0]].ejemplo}


# ----------------------------------------------------------------------------------------------
# Los widgets
# ----------------------------------------------------------------------------------------------


def motivo_de(eleccion: Eleccion, idea: str) -> str:
    """De dónde sale la familia marcada. La dice siempre: él tiene que saber quién la puso."""
    if eleccion.la_puso_el_autor:
        return "Elegida por ti."
    if sugerido(idea) == eleccion.activo:
        return "Sugerida por lo que escribiste — toca otra tarjeta y manda tu elección."
    return "La frase todavía no delata ninguna familia: ésta viene por defecto. Toca la que quieras."


def muro_y_costado(
    activa: str | None,
    idea: str,
    al_elegir: Callable[[str], Any],
    al_cambiar_pieza: Callable[[str, str], Any],
) -> None:
    """Cuatro tarjetas al ancho y, al costado, la familia activa con sus piezas y su «cambiar»."""
    eleccion = elegir(activa, sugerido(idea))
    familias = cargar_formatos()
    with ui.row().classes("tpi-columnas w-full items-start"):
        with ui.column().classes("gap-3 w-full"):
            with ui.element("div").classes("grid grid-cols-2 md:grid-cols-4 gap-3 w-full"):
                for f in familias.values():
                    _tarjeta(f, f.clave == eleccion.activo, al_elegir)
        with ui.column().classes("tpi-costado gap-3 w-full"):
            _costado(familias[eleccion.activo], motivo_de(eleccion, idea), al_cambiar_pieza)


def pantalla_formato(
    eleccion: Eleccion,
    idea: str,
    al_elegir: Callable[[str], Any],
    al_cambiar_pieza: Callable[[str, str], Any],
) -> None:
    """La familia elegida, en grande, con un «cambiar» en cada pieza; las otras tres, en una línea discreta."""
    familias = cargar_formatos()
    with ui.row().classes("tpi-columnas w-full items-start"):
        with ui.column().classes("gap-1 w-full"):
            ui.label("Las otras tres — toca para cambiarte sin perder lo que escribiste.").classes(
                "tpi-ayuda"
            )
            for otra in familias.values():
                if otra.clave == eleccion.activo:
                    continue
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.button(otra.nombre, on_click=lambda c=otra.clave: al_elegir(c)).props(
                        "flat dense no-caps size=sm"
                    )
                    ui.label(otra.que_es).classes("tpi-ayuda")
        with ui.column().classes("tpi-costado gap-3 w-full"):
            _costado(familias[eleccion.activo], motivo_de(eleccion, idea), al_cambiar_pieza, ancho=150)


def _tarjeta(f: Formato, activa: bool, al_elegir: Callable[[str], Any]) -> None:
    con = "tpi-tarjetaactiva" if activa else ""
    with (
        ui.card()
        .classes(f"{con} tpi-tarjeta w-full p-0 overflow-hidden gap-0")
        .props("clickable")
        .on("click", lambda _e, clave=f.clave: al_elegir(clave))
    ):
        with ui.element("div").classes("w-full aspect-[9/16] relative"):
            _portada(f)
            ui.label(f.nombre).classes(
                "absolute left-2 top-2 text-[10px] font-bold uppercase tracking-wide leading-tight"
            ).style(f"background:{f.color}; color:{PIEL['muro']}; padding:2px 6px; border-radius:6px")


def _portada(f: Formato) -> None:
    """La viñeta del dibujo típico de la familia, sobre el fondo del tema que sugiere."""
    try:
        png = miniaturas.dibujar_miniatura(visual_de_portada(f.clave), tema=f.tema)
        ui.image(url_medio(png)).classes("w-full h-full").props("fit=cover")
    except Exception as e:  # una portada que falla no puede tapar la familia elegida
        with ui.element("div").classes("w-full h-full flex items-center justify-center p-3"):
            ui.label(f.nombre).classes("text-sm text-center").style(f"color:{PIEL['texto_muro']}")
            ui.tooltip(str(e))


def _costado(
    f: Formato,
    motivo: str,
    al_cambiar_pieza: Callable[[str, str], Any],
    ancho: int = 78,
) -> None:
    """La familia con sus tres piezas ya puestas y un «cambiar» en cada una."""
    alto = round(ancho * 16 / 9)
    with ui.card().classes("tpi-tarjeta w-full p-4 gap-3"):
        with ui.row().classes("items-start gap-3 no-wrap w-full"):
            try:
                png = miniaturas.dibujar_miniatura(visual_de_portada(f.clave), tema=f.tema)
                ui.image(url_medio(png)).classes("shrink-0 rounded-md").style(f"width:{ancho}px")
            except Exception:
                ui.element("div").classes("shrink-0 rounded-md").style(
                    f"width:{ancho}px; height:{alto}px; background:{PIEL['tarjeta']}"
                )
            with ui.column().classes("gap-1 min-w-0"):
                ui.label(f.nombre).classes("tpi-titulo text-lg leading-tight").style(
                    f"color:{PIEL['texto_muro']}"
                )
                ui.label(f.que_es).classes("text-sm").style(f"color:{PIEL['texto_muro']}")
                ui.label(motivo).classes("tpi-tenue text-xs")
        for pieza, valor, _opciones in piezas(f.clave):
            with ui.row().classes("items-center justify-between gap-2 w-full"):
                ui.label(f"{pieza}: {valor}").classes("text-sm").style(f"color:{PIEL['texto_muro']}")
                ui.button("cambiar", on_click=lambda p=pieza, c=f.clave: al_cambiar_pieza(c, p)).props(
                    "flat dense size=sm"
                )
        ui.label(texto_del_pie(f.clave)).classes("tpi-tenue text-xs")
