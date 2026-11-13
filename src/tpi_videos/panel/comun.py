"""Piezas comunes del panel: estilo visual, marco de cada página y ayudas."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from nicegui import ui

from ..entorno import PAQUETE, raiz_proyecto
from .tareas import TAREAS

# La piel del panel, en un solo lugar. Las páginas leen de acá; no reciben colores nuevos.
# MODO Operate (impeccable): la expresión vive en el muro y en la hoja, no en los controles.
PIEL = {
    "muro": "#080A0D",  # la pantalla del muro de portadas
    "tarjeta": "#11161C",
    "borde_muro": "#223041",
    "texto_muro": "#EAF2FF",
    "tenue_muro": "#8A97A8",
    "hoja": "#FBF7EC",  # el papel crema donde se escribe
    "borde_hoja": "#DCDCD7",
    "tinta": "#1B2430",
    "papel_panel": "#F3F3F0",  # el fondo con renglones de las páginas
    "renglon_panel": "#E4E4E0",
    "marca": "#1C3D74",
    "secundario": "#5B6B86",
    "error": "#D32F2F",
    "aviso": "#B26A00",  # lo que conviene mirar, sin ser un error
    "exito": "#2E7D32",
    "gris": "#6B6B6B",  # el gris que sí se lee sobre blanco (4,5:1)
    "blanco": "#FFFFFF",
    "caja": "#FAFAF8",  # la superficie clara dentro de la hoja: un bloque de texto, una fila
    "banda_aviso": "#FFF4E5",  # el fondo del aviso que hay que resolver (falta la clave)
    "banda_error": "#FDECEC",  # el fondo de la tarjeta «falta completar»
    "error_fuerte": "#B71C1C",  # el rojo de un título sobre banda_error (el error de siempre baja de 4,5:1)
    "aviso_fuerte": "#8A5A00",  # el ámbar de un texto de ayuda sobre blanco o crema
    "aviso_muro": "#F0B664",  # el ámbar que se lee sobre la tarjeta oscura (el de siempre baja de 4,5:1)
    "costado_px": "392",  # el ancho del panel de detalle aprobado en el mockup
    # El tablero de supervisión: una sala de control oscura, un solo acento ámbar de seguridad.
    "sala": "#0D1117",  # el fondo de toda la pantalla
    "consola": "#151B23",  # las tarjetas
    "consola_alta": "#1C2430",  # lo que va encima de una tarjeta (una ficha, el código)
    "linea_sala": "#26303C",  # separadores y bordes, apenas visibles
    "texto_sala": "#E6EDF3",
    "tenue_sala": "#8D99A6",  # se lee sobre la consola (4,8:1)
    "ambar": "#F2A93B",  # la acción principal y lo que está trabajando
    "tinta_ambar": "#1A1205",  # el texto sobre el botón ámbar
    "verde_sala": "#3FB950",
    "rojo_sala": "#F85149",
    "celeste_sala": "#58A6FF",  # lo que está en espera
    # La insignia de categoría de cada guion: azul Matemáticas, turquesa Física, naranja Ingeniería.
    "insignia_matematicas": "#2F6FEB",
    "insignia_fisica": "#1ABC9C",
    "insignia_ingenieria": "#E8833A",
    "tinta_insignia": "#0D1117",  # el texto sobre la insignia clara (turquesa y naranja)
}

# Tres pestañas: supervisar, aprobar y, solo si hace falta, meter las manos. («/» es el Estudio.)
PAGINAS = (
    ("/cola", "Cola de Producción", "dashboard"),
    ("/qc", "Aprobación de Guiones (QC)", "fact_check"),
    ("/avanzado", "Avanzado", "tune"),
)

CSS = f"""
@font-face {{ font-family: 'Comic Neue'; src: url('/fuentes/ComicNeue-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'Comic Neue'; src: url('/fuentes/ComicNeue-Bold.ttf'); font-weight: 700; }}
@font-face {{ font-family: 'Bangers'; src: url('/fuentes/Bangers-Regular.ttf'); }}
@font-face {{ font-family: 'Montserrat'; src: url('/fuentes/Montserrat-SemiBold.ttf'); font-weight: 600; }}
body {{ background-color: {PIEL["sala"]}; color: {PIEL["texto_sala"]}; }}
.tpi-legado {{
  background-color: {PIEL["papel_panel"]};
  background-image: linear-gradient({PIEL["renglon_panel"]} 1px, transparent 1px),
                    linear-gradient(90deg, {PIEL["renglon_panel"]} 1px, transparent 1px);
  background-size: 24px 24px;
  color: {PIEL["tinta"]}; border-radius: 16px; padding: 24px;
}}
.tpi-cabecera {{ background: {PIEL["sala"]}; border-bottom: 1px solid {PIEL["linea_sala"]}; }}
.tpi-pestanas .q-tab {{ color: {PIEL["tenue_sala"]}; text-transform: none; font-size: .95rem; padding: 0 20px; }}
.tpi-pestanas .q-tab--active {{ color: {PIEL["texto_sala"]}; }}
.tpi-pestanas .q-tab__indicator {{ background: {PIEL["ambar"]}; height: 3px; }}
.tpi-consola {{ background: {PIEL["consola"]}; border-radius: 16px; box-shadow: none; color: {PIEL["texto_sala"]}; }}
.tpi-ficha {{ background: {PIEL["consola_alta"]}; border-radius: 12px; color: {PIEL["texto_sala"]}; }}
.tpi-ficha-activa {{ box-shadow: inset 3px 0 0 {PIEL["ambar"]}; }}
.tpi-ficha-fallo {{ box-shadow: inset 3px 0 0 {PIEL["rojo_sala"]}; }}
.tpi-ficha-elegida {{ box-shadow: 0 0 0 1px {PIEL["ambar"]}; }}
.tpi-sobrio {{ color: {PIEL["tenue_sala"]}; }}
.tpi-cifra {{ font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 2rem; line-height: 1; }}
.tpi-rotulo {{ color: {PIEL["tenue_sala"]}; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; }}
.tpi-ambar {{ color: {PIEL["ambar"]}; }}
.tpi-verde {{ color: {PIEL["verde_sala"]}; }}
.tpi-rojo {{ color: {PIEL["rojo_sala"]}; }}
.tpi-celeste {{ color: {PIEL["celeste_sala"]}; }}
.tpi-boton-principal {{ background: {PIEL["ambar"]} !important; color: {PIEL["tinta_ambar"]} !important;
  font-weight: 700; border-radius: 12px; padding: 14px 28px; font-size: 1rem; text-transform: none; }}
.tpi-aprobar {{ background: {PIEL["verde_sala"]} !important; color: {PIEL["sala"]} !important;
  font-weight: 700; border-radius: 12px; padding: 14px 28px; font-size: 1rem; text-transform: none; }}
.tpi-rechazar {{ background: transparent !important; color: {PIEL["rojo_sala"]} !important;
  box-shadow: inset 0 0 0 1px {PIEL["rojo_sala"]}; font-weight: 700; border-radius: 12px; padding: 14px 28px;
  font-size: 1rem; text-transform: none; }}
.tpi-voz {{ font-size: 1.05rem; line-height: 1.65; color: {PIEL["texto_sala"]}; }}
.tpi-pausa {{ display: inline-block; margin: 0 6px; padding: 0 8px; border-radius: 999px; font-size: .75rem;
  color: {PIEL["ambar"]}; box-shadow: inset 0 0 0 1px {PIEL["ambar"]}; vertical-align: middle; }}
.tpi-hashtag {{ color: {PIEL["celeste_sala"]}; font-size: .9rem; }}
.tpi-plegable {{ background: {PIEL["consola"]}; border-radius: 16px; overflow: hidden; }}
.tpi-plegable + .tpi-plegable {{ margin-top: 12px; }}
.tpi-plegable > .q-expansion-item__container > .q-item {{ min-height: 64px; color: {PIEL["texto_sala"]}; }}
.tpi-plegable > .q-expansion-item__container > .q-item .q-item__label--caption {{ color: {PIEL["tenue_sala"]}; }}
.tpi-tablero .q-linear-progress {{ color: {PIEL["ambar"]}; }}
.tpi-tablero .q-toggle__inner--truthy {{ color: {PIEL["ambar"]}; }}
.tpi-tablero .q-btn {{ text-transform: none; }}
.tpi-insignia {{ align-self: flex-start; padding: 2px 10px; border-radius: 999px; font-size: .7rem;
  font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }}
.tpi-insignia-matematicas {{ background: {PIEL["insignia_matematicas"]}; color: {PIEL["texto_sala"]}; }}
.tpi-insignia-fisica {{ background: {PIEL["insignia_fisica"]}; color: {PIEL["tinta_insignia"]}; }}
.tpi-insignia-ingenieria {{ background: {PIEL["insignia_ingenieria"]}; color: {PIEL["tinta_insignia"]}; }}
.tpi-clic {{ transition: background-color .15s ease, box-shadow .15s ease; }}
.tpi-clic:hover {{ background-color: {PIEL["linea_sala"]}; }}
.tpi-ficha.tpi-clic:hover {{ box-shadow: 0 0 0 1px {PIEL["ambar"]}; background-color: {PIEL["consola_alta"]}; }}
.tpi-consola.tpi-clic:hover {{ box-shadow: 0 0 0 1px {PIEL["linea_sala"]}; background-color: {PIEL["consola"]}; }}
.tpi-codigo {{ background: {PIEL["consola_alta"]} !important; border-radius: 12px; }}
.tpi-hoja {{ color: {PIEL["tinta"]}; }}
.tpi-marca {{ font-family: 'Comic Neue', sans-serif; font-weight: 700; letter-spacing: .03em; }}
.tpi-titulo {{ font-family: 'Comic Neue', sans-serif; font-weight: 700; color: {PIEL["marca"]}; text-transform: uppercase; }}
.tpi-hoja {{ background: {PIEL["hoja"]}; border: 1px solid {PIEL["borde_hoja"]}; border-radius: 14px; }}
.tpi-paso-num {{ font-family: 'Comic Neue', sans-serif; font-weight: 700; color: {PIEL["blanco"]};
  background: {PIEL["marca"]};
  border-radius: 999px; width: 28px; height: 28px; display: inline-flex; align-items: center;
  justify-content: center; flex-shrink: 0; }}
.tpi-error {{ border-left: 4px solid {PIEL["error"]}; }}
.tpi-nav a {{ color: {PIEL["blanco"]}; text-decoration: none; padding: 6px 12px; border-radius: 8px; opacity: .85; }}
.tpi-nav a:hover {{ background: rgba(255,255,255,.12); opacity: 1; }}
.tpi-nav a.activa {{ background: rgba(255,255,255,.18); opacity: 1; box-shadow: inset 0 -3px 0 {PIEL["error"]}; }}
.tpi-bangers {{ font-family: 'Bangers', cursive; letter-spacing: .04em; }}
.tpi-ayuda {{ color: {PIEL["gris"]}; font-size: .85rem; }}
.tpi-muro {{ background: {PIEL["muro"]}; color: {PIEL["texto_muro"]}; }}
.tpi-tarjeta {{ background: {PIEL["tarjeta"]}; border: 1px solid {PIEL["borde_muro"]}; border-radius: 12px; }}
.tpi-tarjetaactiva {{ border-color: {PIEL["texto_muro"]}; box-shadow: 0 0 0 2px {PIEL["texto_muro"]}; }}
.tpi-tenue {{ color: {PIEL["tenue_muro"]}; }}
.tpi-etiqueta {{ position: absolute; top: 6px; left: 6px; max-width: 88%; padding: 2px 8px;
  border-radius: 999px; font-size: .68rem; font-weight: 700; line-height: 1.5; overflow: hidden;
  white-space: nowrap; text-overflow: ellipsis; background: {PIEL["marca"]}; color: {PIEL["blanco"]}; }}
.tpi-columnas {{ display: grid; grid-template-columns: minmax(0, 1fr) {PIEL["costado_px"]}px;
  gap: 16px; align-items: start; }}
@media (max-width: 900px) {{ .tpi-columnas {{ grid-template-columns: minmax(0, 1fr); }} }}
.tpi-costado {{ position: sticky; top: 12px; }}
/* El Estudio: una sola pantalla. Mismo mundo que la sala (oscuro, un acento ámbar). */
.tpi-enlace-cabecera {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 10px;
  color: {PIEL["tenue_sala"]}; text-decoration: none; transition: background-color .15s ease, color .15s ease; }}
.tpi-enlace-cabecera:hover {{ background-color: {PIEL["consola"]}; color: {PIEL["texto_sala"]}; }}
.tpi-estudio .q-field__native, .tpi-estudio .q-field__input {{ color: {PIEL["texto_sala"]}; }}
.tpi-estudio .q-field__label, .tpi-estudio .q-field__bottom {{ color: {PIEL["tenue_sala"]}; }}
.tpi-estudio .q-field--outlined .q-field__control:before {{ border-color: {PIEL["linea_sala"]}; }}
.tpi-estudio .q-field--outlined.q-field--focused .q-field__control:after {{ border-color: {PIEL["ambar"]}; }}
.tpi-estudio .q-btn {{ text-transform: none; }}
.tpi-estudio .q-linear-progress {{ color: {PIEL["ambar"]}; }}
.tpi-idea textarea {{ font-size: 1.1rem; line-height: 1.55; }}
.tpi-zona {{ display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px;
  border-radius: 999px; font-size: .8rem; font-weight: 700; color: {PIEL["ambar"]};
  box-shadow: inset 0 0 0 1.5px {PIEL["ambar"]}; flex-shrink: 0; }}
.tpi-zona-apagada {{ color: {PIEL["tenue_sala"]}; box-shadow: inset 0 0 0 1.5px {PIEL["linea_sala"]}; }}
.tpi-chip-tipo {{ min-height: 44px; padding: 0 18px; border-radius: 999px; background: {PIEL["consola_alta"]};
  color: {PIEL["texto_sala"]}; box-shadow: inset 0 0 0 1px {PIEL["linea_sala"]}; font-weight: 600;
  transition: background-color .15s ease, box-shadow .15s ease; }}
.tpi-chip-tipo.activo {{ background: {PIEL["ambar"]}; color: {PIEL["tinta_ambar"]}; box-shadow: none; }}
.tpi-atajo {{ min-height: 36px; padding: 0 12px; border-radius: 10px; color: {PIEL["tenue_sala"]};
  box-shadow: inset 0 0 0 1px {PIEL["linea_sala"]}; font-size: .85rem; }}
.tpi-opcion {{ width: 100%; text-align: left; padding: 12px 14px; border-radius: 12px; background: {PIEL["consola_alta"]};
  color: {PIEL["texto_sala"]}; box-shadow: inset 0 0 0 1px transparent; cursor: pointer;
  transition: box-shadow .15s ease, background-color .15s ease; }}
.tpi-opcion.elegida {{ box-shadow: inset 3px 0 0 {PIEL["ambar"]}, inset 0 0 0 1px {PIEL["ambar"]}; cursor: default; }}
.tpi-sugerencia {{ min-height: 36px; padding: 0 12px; border-radius: 999px; font-size: .85rem;
  color: {PIEL["texto_sala"]}; background: {PIEL["consola_alta"]}; box-shadow: inset 0 0 0 1px {PIEL["linea_sala"]}; }}
.tpi-sugerencia.elegida {{ box-shadow: inset 0 0 0 1px {PIEL["ambar"]}; color: {PIEL["ambar"]}; }}
.tpi-paso {{ display: grid; grid-template-columns: 28px minmax(0, 1fr) 92px; gap: 14px; align-items: start;
  padding: 14px; border-radius: 12px; background: {PIEL["consola_alta"]}; }}
@media (max-width: 600px) {{ .tpi-paso {{ grid-template-columns: 28px minmax(0, 1fr); }}
  .tpi-paso .tpi-cuadro-paso {{ grid-column: 2; }} .tpi-paso .tpi-cuadro-paso.vacio {{ display: none; }} }}
.tpi-paso-error {{ box-shadow: inset 3px 0 0 {PIEL["rojo_sala"]}; }}
.tpi-num-paso {{ width: 28px; height: 28px; border-radius: 999px; display: inline-flex; align-items: center;
  justify-content: center; font-size: .8rem; font-weight: 700; background: {PIEL["sala"]}; color: {PIEL["texto_sala"]}; }}
.tpi-cuadro-paso {{ width: 92px; aspect-ratio: 9 / 16; border-radius: 10px; overflow: hidden; background: {PIEL["sala"]};
  box-shadow: inset 0 0 0 1px {PIEL["linea_sala"]}; display: flex; align-items: center; justify-content: center; }}
.tpi-cuadro-paso.vacio {{ aspect-ratio: auto; height: 56px; background: transparent;
  box-shadow: inset 0 0 0 1px {PIEL["linea_sala"]}; }}
.tpi-cuadro-video {{ width: 72px; aspect-ratio: 9 / 16; border-radius: 8px; overflow: hidden; background: {PIEL["sala"]};
  flex-shrink: 0; }}
.tpi-cuadro-paso img, .tpi-cuadro-video img {{ width: 100%; height: 100%; object-fit: cover; }}
.tpi-esqueleto {{ background: {PIEL["linea_sala"]}; border-radius: 8px; animation: tpi-latido 1.4s ease-in-out infinite; }}
@keyframes tpi-latido {{ 0%, 100% {{ opacity: .55; }} 50% {{ opacity: 1; }} }}
.tpi-aviso-error {{ border-radius: 12px; padding: 14px 16px; background: {PIEL["consola_alta"]};
  box-shadow: inset 3px 0 0 {PIEL["rojo_sala"]}; }}
.tpi-entra {{ animation: tpi-entra .22s cubic-bezier(0.23, 1, 0.32, 1); }}
@keyframes tpi-entra {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
@media (hover: hover) and (pointer: fine) {{
  .tpi-chip-tipo:not(.activo):hover, .tpi-opcion:not(.elegida):hover, .tpi-sugerencia:hover, .tpi-atajo:hover {{
    box-shadow: inset 0 0 0 1px {PIEL["ambar"]}; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .tpi-entra {{ animation: none; }}
  .tpi-esqueleto {{ animation: none; }}
}}
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
        (PAQUETE / "assets" / "fondos", "/medios/fondos_paquete"),
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


def piel_de_la_pagina() -> None:
    ui.add_css(CSS)
    ui.colors(
        primary=PIEL["marca"],
        secondary=PIEL["secundario"],
        accent=PIEL["ambar"],
        positive=PIEL["exito"],
        negative=PIEL["error"],
        warning=PIEL["aviso"],
    )


def cabecera(con_menu: bool = True, estudio: bool = False, al_estudio: bool = False) -> None:
    """La barra de arriba, oscura y sin ruido: la marca, el estado del motor y (si toca) volver.

    En el Estudio (``estudio=True``) lleva además la salida a la sala de producción y a los ajustes; en
    la sala (``al_estudio=True``), el camino de vuelta al Estudio.
    """
    with ui.header().classes("tpi-cabecera items-center justify-between px-8 py-3"):
        with ui.row().classes("items-center gap-3 cursor-pointer").on("click", lambda: ui.navigate.to("/")):
            ui.image("/marca/panel.png").classes("w-9 h-9").props('alt="" no-spinner no-transition')
            with ui.column().classes("gap-0"):
                ui.label("TU PROFE INDUSTRIAL").classes("tpi-marca text-base leading-tight")
                ui.label("Estudio" if estudio else "Sala de producción").classes("tpi-sobrio text-xs")
        with ui.row().classes("items-center gap-4"):
            chip = (
                ui.chip("", color=None, on_click=lambda: ui.navigate.to("/"))
                .props("outline clickable")
                .classes("tpi-ambar")
            )
            chip.set_visibility(False)
            ui.timer(0.7, lambda: _estado_tarea(chip))
            if estudio:
                with (
                    ui.link(target="/cola")
                    .classes("tpi-enlace-cabecera")
                    .props('aria-label="Sala de producción"')
                ):
                    ui.icon("dashboard").classes("text-xl")
                    ui.label("Sala de producción").classes("gt-xs")
                with ui.link(target="/ajustes").classes("tpi-enlace-cabecera").props('aria-label="Ajustes"'):
                    ui.icon("settings").classes("text-xl")
                    ui.label("Ajustes").classes("gt-xs")
            elif al_estudio:
                with (
                    ui.link(target="/").classes("tpi-enlace-cabecera").props('aria-label="Volver al Estudio"')
                ):
                    ui.icon("edit_note").classes("text-xl")
                    ui.label("Estudio")
            elif con_menu:
                ui.link("← Volver a la sala", "/cola").classes("tpi-sobrio no-underline")


@contextmanager
def marco(ruta_activa: str) -> Iterator[None]:
    """Las páginas sueltas de siempre (el editor de un estilo): cabecera oscura y su hoja clara.

    El contenido va dentro de ``tpi-legado``: conserva el papel con renglones y la tinta oscura con
    que se diseñaron, así nada queda claro sobre claro ni oscuro sobre oscuro.
    """
    del ruta_activa  # se conserva la firma: las páginas antiguas la siguen llamando igual
    piel_de_la_pagina()
    cabecera(con_menu=True)
    with ui.column().classes("w-full max-w-6xl mx-auto px-4 py-8"):
        with ui.column().classes("tpi-legado w-full gap-6"):
            yield


def titulo_seccion(numero: str | None, texto: str, ayuda: str | None = None) -> None:
    with ui.row().classes("items-center gap-3"):
        if numero:
            ui.label(numero).classes("tpi-paso-num")
        ui.label(texto).classes("tpi-titulo text-xl")
    if ayuda:
        ui.label(ayuda).classes("tpi-ayuda -mt-2")


def confirmar(pregunta: str, accion: Callable[[], object], boton: str = "Sí, borrar") -> None:
    with ui.dialog() as dialogo, ui.card().classes("tpi-hoja p-6"):
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
