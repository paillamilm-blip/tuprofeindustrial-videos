"""El tablero de supervisión: Cola de Producción, Aprobación de Guiones (QC) y Avanzado.

El motor ya escribe los guiones y produce los videos solo; la persona supervisa. La pantalla
principal muestra solo el estado de la fábrica y un botón para producir; la aprobación es una lectura
limpia con dos decisiones; todo lo manual (crear a mano, estilos, ajustes, diagnóstico) queda
plegado en «Avanzado» y se construye recién cuando se abre.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from nicegui import background_tasks, ui

from ... import cola
from ...errores import ErrorMotor
from .. import qc
from ..comun import abrir_en_mac, cabecera, confirmar, piel_de_la_pagina, url_medio
from ..supervision import (
    COLUMNAS,
    COMPLETADOS,
    EN_RENDER,
    LANZAMIENTO,
    PENDIENTES,
    args_de_lote,
    columnas,
    lotes_por_producir,
)
from ..tareas import TAREAS

PESTANAS = {
    "cola": ("Cola de Producción", "dashboard"),
    "qc": ("Aprobación de Guiones (QC)", "fact_check"),
    "avanzado": ("Avanzado", "tune"),
}
ICONOS_COLUMNA = {PENDIENTES: "schedule", EN_RENDER: "motion_photos_on", COMPLETADOS: "task_alt"}
CLASE_COLUMNA = {PENDIENTES: "tpi-celeste", EN_RENDER: "tpi-ambar", COMPLETADOS: "tpi-verde"}


# ------------------------------------------------------------------------------------------
# El lanzamiento en lote vive en la app, no en la pestaña del navegador
# ------------------------------------------------------------------------------------------

_vigilante: dict[str, Any] = {"tarea": None}


async def _seguir_el_lote() -> None:
    """Mientras el usuario pidió producir en lote, cuando la fila queda libre va el lote siguiente."""
    import asyncio

    while LANZAMIENTO.activo:
        args = LANZAMIENTO.siguiente(cola.cargar(), TAREAS.ocupado())
        if args is not None:
            try:
                TAREAS.lanzar(f"Lote {LANZAMIENTO.lanzados}", args)
            except ErrorMotor:
                pass  # otra pestaña lanzó algo en el mismo instante: se reintenta en la vuelta siguiente
        await asyncio.sleep(2.0)
    _vigilante["tarea"] = None


def lanzar_en_lote() -> bool:
    """Pone en marcha la producción de todo lo pendiente. False si no había nada que producir."""
    if not lotes_por_producir(cola.cargar()):
        return False
    LANZAMIENTO.empezar()
    if _vigilante["tarea"] is None:
        _vigilante["tarea"] = background_tasks.create(_seguir_el_lote(), name="lanzamiento en lote")
    return True


def _en_vivo() -> dict[str, dict[str, Any]]:
    """El avance que informa la tarea en curso, con el id de video de la cola."""
    t = TAREAS.actual
    if t is None or t.terminada or "--cola-id" not in t.args:
        return {}
    lote_id = t.args[t.args.index("--cola-id") + 1]
    return {
        f"{lote_id}-{n}": {
            "avance": datos.get("video_avance", datos.get("avance")),
            "estado": datos.get("estado"),
            "detalle": datos.get("detalle"),
        }
        for n, datos in t.videos.items()
    }


# ------------------------------------------------------------------------------------------
# Piezas visuales
# ------------------------------------------------------------------------------------------


def _consola(clases: str = "") -> ui.card:
    return ui.card().props("flat").classes(f"tpi-consola w-full p-6 gap-4 {clases}")


def _rotulo(texto: str) -> None:
    ui.label(texto).classes("tpi-rotulo")


def _clic(elemento: Any, accion: Callable[[], Any], ayuda: str) -> Any:
    """Todo lo que se ve en el tablero responde: puntero, resalte al pasar y qué va a pasar."""
    elemento.classes("tpi-clic cursor-pointer").on("click", lambda _e=None: accion())
    elemento.tooltip(ayuda)
    return elemento


def _copiar(texto: str, que: str) -> None:
    ui.clipboard.write(texto)
    ui.notify(f"{que} copiado.", type="positive")


def _abrir_editor(ruta: Path) -> None:
    ui.navigate.to(f"/crear?guion={quote(str(ruta))}")


# ------------------------------------------------------------------------------------------
# 1 · Cola de Producción
# ------------------------------------------------------------------------------------------


class ColaDeProduccion:
    """El estado de la fábrica de un vistazo, y una sola acción: producir lo pendiente."""

    def __init__(self, ir_a: Callable[[str], None]) -> None:
        self.ir_a = ir_a
        self.firma: tuple = ()

    def render(self) -> None:
        self.firma = self._firma()  # lo recién pintado no se repinta: un clic no cae sobre algo que se va
        self.resumen()
        self.columnas()
        ui.timer(1.5, self._mirar)

    def _mirar(self) -> None:
        # Se repinta solo si algo cambió: un tablero que parpadea cansa la vista.
        firma = self._firma()
        if firma != self.firma:
            self.firma = firma
            self.resumen.refresh()
            self.columnas.refresh()

    def _firma(self) -> tuple:
        datos = cola.cargar()
        vivo = _en_vivo()
        return (
            tuple(
                (v.get("id"), v.get("estado"), round(float(v.get("avance") or 0), 2))
                for lote in datos.get("lotes", [])
                for v in lote.get("videos", [])
            ),
            tuple(
                sorted((k, round(float(d.get("avance") or 0), 2), d.get("estado")) for k, d in vivo.items())
            ),
            TAREAS.ocupado(),
            LANZAMIENTO.activo,
            len(qc.guiones()),
        )

    @ui.refreshable_method
    def resumen(self) -> None:
        datos = cola.cargar()
        fichas = columnas(datos, _en_vivo())
        por_producir = len(lotes_por_producir(datos))
        por_revisar = len(qc.guiones())
        with _consola():
            with ui.row().classes("w-full items-center justify-between gap-8 flex-wrap"):
                with ui.row().classes("gap-6 items-end"):
                    for clave, nombre in COLUMNAS.items():
                        cifra = _clic(
                            ui.column().classes("gap-1 px-3 py-2 rounded-xl"),
                            lambda c=clave, n=nombre, fs=fichas[clave]: self._lista_de(n, fs),
                            f"Ver los {nombre.lower()}",
                        )
                        with cifra:
                            ui.label(str(len(fichas[clave]))).classes(f"tpi-cifra {CLASE_COLUMNA[clave]}")
                            _rotulo(nombre)
                    with _clic(
                        ui.column().classes("gap-1 px-3 py-2 rounded-xl"),
                        lambda: self.ir_a("qc"),
                        "Ir a aprobar guiones",
                    ):
                        ui.label(str(por_revisar)).classes("tpi-cifra")
                        _rotulo("Guiones por aprobar")
                with ui.row().classes("items-center gap-3"):
                    if por_revisar:
                        ui.button(
                            color=None,
                            text="Revisar guiones",
                            icon="fact_check",
                            on_click=lambda: self.ir_a("qc"),
                        ).props("flat no-caps").classes("tpi-sobrio")
                    if TAREAS.ocupado():
                        ui.button(color=None, text="Detener", icon="stop", on_click=self._detener).props(
                            "flat no-caps"
                        ).classes("tpi-rojo")
                    boton = ui.button(
                        color=None,
                        text="Lanzar Renderización en Lote",
                        icon="play_arrow",
                        on_click=self._lanzar,
                    ).classes("tpi-boton-principal")
                    if LANZAMIENTO.activo or TAREAS.ocupado():
                        boton.text = "Produciendo…"
                        boton.disable()
                    elif not por_producir:
                        boton.disable()
                        boton.tooltip("No hay videos esperando. Aprueba un guion en la pestaña QC.")
            t = TAREAS.actual
            if t is not None and not t.terminada:
                with _clic(
                    ui.column().classes("w-full gap-1 px-3 py-2 rounded-xl"),
                    _dialogo_tarea,
                    "Ver qué está haciendo el motor",
                ):
                    ui.linear_progress(value=t.avance, show_value=False, color=None).props(
                        "rounded size=6px"
                    ).classes("w-full")
                    ui.label(t.detalle or t.texto_etapa).classes("tpi-sobrio text-sm")

    def _lista_de(self, nombre: str, fichas: list[Any]) -> None:
        with (
            ui.dialog() as dialogo,
            ui.card().props("flat").classes("tpi-consola p-8 gap-4 w-[560px] max-w-[95vw]"),
        ):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(nombre).classes("text-lg font-semibold")
                ui.button(color=None, icon="close", on_click=dialogo.close).props("flat round").classes(
                    "tpi-sobrio"
                )
            if not fichas:
                ui.label("No hay videos acá.").classes("tpi-sobrio")
            for f in fichas:
                with _clic(
                    ui.column().classes("tpi-ficha w-full p-4 gap-1"),
                    lambda f=f: (dialogo.close(), self._detalle(f)),
                    "Ver el detalle",
                ):
                    ui.label(f.titulo).classes("font-semibold")
                    ui.label(f"{f.texto_estado} · {f.tema}").classes("tpi-sobrio text-xs")
        dialogo.open()

    def _detalle(self, f: Any) -> None:
        """Todo lo que se puede hacer con un video de la cola, en un solo lugar."""
        activo = f.estado in cola.ESTADOS_ACTIVOS
        with (
            ui.dialog() as dialogo,
            ui.card().props("flat").classes("tpi-consola p-8 gap-4 w-[560px] max-w-[95vw]"),
        ):
            with ui.row().classes("w-full items-start justify-between no-wrap"):
                with ui.column().classes("gap-1"):
                    _rotulo(f.tema)
                    ui.label(f.titulo).classes("text-xl font-semibold leading-tight")
                ui.button(color=None, icon="close", on_click=dialogo.close).props("flat round").classes(
                    "tpi-sobrio"
                )
            color = "tpi-rojo" if f.fallo else ("tpi-ambar" if activo else "tpi-sobrio")
            ui.label(f.texto_estado + (f" · {round(f.avance * 100)} %" if activo else "")).classes(color)
            if activo:
                ui.linear_progress(value=f.avance, show_value=False, color=None).props("rounded size=6px")
            if activo and f.detalle and f.detalle != f.texto_estado:
                ui.label(f.detalle).classes("tpi-sobrio text-sm")
            if f.error:
                ui.label(str(f.error)).classes("tpi-rojo text-sm")

            def cerrar_y(accion: Callable[[], Any]) -> Callable[[], None]:
                def hacer() -> None:
                    dialogo.close()
                    accion()

                return hacer

            with ui.row().classes("w-full gap-3 pt-4 flex-wrap"):
                if f.video is not None:
                    ui.button(
                        color=None,
                        text="Ver el video",
                        icon="play_circle",
                        on_click=cerrar_y(lambda: _ver(f.video)),
                    ).classes("tpi-aprobar")
                    ui.button(
                        color=None,
                        text="Kit para publicar",
                        icon="content_copy",
                        on_click=lambda: _kit(f.video, dialogo),
                    ).props("flat no-caps").classes("tpi-sobrio")
                    ui.button(
                        color=None,
                        text="Carpeta",
                        icon="folder_open",
                        on_click=lambda: abrir_en_mac(f.video, True),
                    ).props("flat no-caps").classes("tpi-sobrio")
                if not activo and f.estado != "listo":
                    ui.button(
                        color=None,
                        text="Producir este ahora",
                        icon="play_arrow",
                        on_click=cerrar_y(lambda: self._producir(f)),
                    ).classes("tpi-boton-principal")
                if f.guion is not None:
                    ui.button(
                        color=None,
                        text="Abrir el guion",
                        icon="edit",
                        on_click=cerrar_y(lambda: _abrir_editor(f.guion)),
                    ).props("flat no-caps").classes("tpi-sobrio")
                if activo:
                    ui.button(
                        color=None, text="Detener", icon="stop", on_click=cerrar_y(self._detener)
                    ).props("flat no-caps").classes("tpi-rojo")
                else:
                    ui.button(
                        color=None,
                        text="Quitar de la cola",
                        icon="delete",
                        on_click=cerrar_y(lambda: self._quitar(f)),
                    ).props("flat no-caps").classes("tpi-rojo")
        dialogo.open()

    def _producir(self, f: Any) -> None:
        if TAREAS.ocupado():
            ui.notify("Ya hay un trabajo en curso: espera a que termine.", type="warning")
            return
        TAREAS.lanzar(f.titulo, args_de_lote(f.lote_id))
        ui.notify(f"Produciendo «{f.titulo}».", type="positive")
        self.firma = ()

    def _quitar(self, f: Any) -> None:
        def si() -> None:
            try:
                cola.descartar_lote(f.lote_id)
            except ErrorMotor as e:
                ui.notify(e.mensaje, type="warning")
                return
            ui.notify("Quitado de la cola. Los archivos que ya salieron no se borran.", type="info")
            self.firma = ()

        confirmar(f"¿Quitar «{f.titulo}» (y su lote, «{f.tema}») de la cola?", si, "Sí, quitar")

    def _lanzar(self) -> None:
        if TAREAS.ocupado():
            ui.notify("Ya hay un trabajo en curso: el lote sigue cuando termine.", type="warning")
            return
        if lanzar_en_lote():
            ui.notify("Producción en marcha: los videos pasan solos de columna.", type="positive")
        else:
            ui.notify("No hay videos esperando en la cola.", type="info")
        self.firma = ()

    def _detener(self) -> None:
        def si() -> None:
            LANZAMIENTO.detener()
            TAREAS.cancelar()
            ui.notify("Producción detenida. Lo que quedó a medias se retoma después.", type="info")

        confirmar(
            "¿Detener la producción? El video en curso queda para retomarlo después.", si, "Sí, detener"
        )

    @ui.refreshable_method
    def columnas(self) -> None:
        fichas = columnas(cola.cargar(), _en_vivo())
        with (
            ui.element("div")
            .classes("w-full grid gap-6")
            .style("grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))")
        ):
            for clave, nombre in COLUMNAS.items():
                with _consola("min-h-[320px]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(ICONOS_COLUMNA[clave]).classes(f"{CLASE_COLUMNA[clave]} text-xl")
                            ui.label(nombre).classes("text-base font-semibold")
                        ui.label(str(len(fichas[clave]))).classes("tpi-sobrio")
                    if not fichas[clave]:
                        texto, accion, ayuda = self._vacio(clave)
                        _clic(
                            ui.label(texto).classes("tpi-sobrio text-sm py-6 px-3 rounded-xl"), accion, ayuda
                        )
                    for ficha in fichas[clave]:
                        self._ficha(ficha)

    def _vacio(self, clave: str) -> tuple[str, Callable[[], Any], str]:
        return {
            PENDIENTES: (
                "Nada esperando. Lo que apruebes en QC llega acá.",
                lambda: self.ir_a("qc"),
                "Ir a QC",
            ),
            EN_RENDER: ("El motor está libre.", self._lanzar, "Producir lo pendiente"),
            COMPLETADOS: (
                "Todavía no sale ningún video.",
                lambda: ui.navigate.to("/videos"),
                "Abrir la biblioteca de videos",
            ),
        }[clave]

    def _ficha(self, f: Any) -> None:
        clase = (
            "tpi-ficha-activa" if f.estado in cola.ESTADOS_ACTIVOS else ("tpi-ficha-fallo" if f.fallo else "")
        )
        with _clic(
            ui.column().classes(f"tpi-ficha {clase} w-full p-4 gap-2"),
            lambda: self._detalle(f),
            "Ver el detalle y qué hacer",
        ):
            ui.label(f.titulo).classes("font-semibold leading-snug")
            with ui.row().classes("w-full items-center justify-between gap-2"):
                color = (
                    "tpi-rojo"
                    if f.fallo
                    else ("tpi-ambar" if f.estado in cola.ESTADOS_ACTIVOS else "tpi-sobrio")
                )
                ui.label(f.texto_estado).classes(f"{color} text-xs")
                if f.estado in cola.ESTADOS_ACTIVOS:
                    ui.label(f"{round(f.avance * 100)} %").classes("tpi-ambar text-xs")
            if f.estado in cola.ESTADOS_ACTIVOS:
                ui.linear_progress(value=f.avance, show_value=False, color=None).props(
                    "rounded size=4px"
                ).classes("w-full")
            if f.fallo and f.error:
                ui.label(str(f.error)).classes("tpi-sobrio text-xs")
            if f.video is not None:
                with ui.row().classes("gap-1 -ml-2"):
                    ui.button(color=None, text="Ver", icon="play_circle").props("flat dense no-caps").classes(
                        "tpi-verde"
                    ).on("click.stop", lambda _e, v=f.video: _ver(v))
                    ui.button(color=None, text="Carpeta", icon="folder_open").props(
                        "flat dense no-caps"
                    ).classes("tpi-sobrio").on("click.stop", lambda _e, v=f.video: abrir_en_mac(v, True))


def _ver(video: Path) -> None:
    from .videos import ver_video

    ver_video(video)


async def _kit(video: Path, dialogo: Any = None) -> None:
    from .videos import abrir_kit

    if dialogo is not None:
        dialogo.close()
    await abrir_kit(video.parent)  # dentro del clic: el diálogo del kit necesita su pestaña


def _dialogo_tarea() -> None:
    """Lo que el motor está haciendo ahora mismo, con su registro y el botón para detenerlo."""
    t = TAREAS.actual
    if t is None:
        return
    with (
        ui.dialog() as dialogo,
        ui.card().props("flat").classes("tpi-consola p-8 gap-4 w-[720px] max-w-[95vw]"),
    ):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(t.nombre).classes("text-lg font-semibold")
            ui.button(color=None, icon="close", on_click=dialogo.close).props("flat round").classes(
                "tpi-sobrio"
            )
        ui.label(f"{t.texto_etapa} · {round(t.avance * 100)} %").classes("tpi-ambar")
        if t.detalle:
            ui.label(t.detalle).classes("tpi-sobrio text-sm")
        ui.code("\n".join(t.registro[-40:]) or "Todavía no hay mensajes.", language="text").classes(
            "tpi-codigo w-full text-xs"
        )
        if not t.terminada:

            def detener() -> None:
                LANZAMIENTO.detener()
                TAREAS.cancelar()
                dialogo.close()
                ui.notify("Producción detenida.", type="info")

            ui.button(color=None, text="Detener", icon="stop", on_click=detener).props(
                "flat no-caps"
            ).classes("tpi-rojo")
    dialogo.open()


# ------------------------------------------------------------------------------------------
# 2 · Aprobación de Guiones (QC)
# ------------------------------------------------------------------------------------------


class AprobacionDeGuiones:
    """Una lista corta a la izquierda y la lectura limpia del guion elegido a la derecha."""

    def __init__(self, al_aprobar: Callable[[], None], abrir: str | None = None) -> None:
        self.al_aprobar = al_aprobar
        self.elegido: Path | None = None
        self.todos = False
        # /qc?guion=…: otra pantalla («Mis videos», el editor) manda a elegir el estilo de un guion.
        if abrir and qc.guion_revisable(Path(abrir)):
            self.elegido = Path(abrir).resolve()
            self.todos = qc.estado(self.elegido) != qc.POR_REVISAR

    def render(self) -> None:
        with (
            ui.element("div")
            .classes("w-full grid gap-6")
            .style("grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); align-items: start")
        ):
            with ui.column().classes("w-full gap-3"):
                self.lista()
            with ui.column().classes("w-full gap-6"):
                self.lectura()

    @ui.refreshable_method
    def lista(self) -> None:
        rutas = qc.guiones(incluir_decididos=self.todos)
        rutas = [r.resolve() for r in rutas]
        if self.elegido is None or self.elegido not in rutas:
            self.elegido = rutas[0] if rutas else None
        with ui.row().classes("w-full items-center justify-between"):
            _rotulo(f"{len(rutas)} {'guiones' if self.todos else 'por revisar'}")
            ui.switch("Ver todos", value=self.todos, on_change=self._cambiar_filtro).props(
                "dense color=amber"
            )
        if not rutas:
            with _clic(_consola(), lambda: ui.navigate.to("/crear"), "Escribir un guion a mano"):
                ui.label("No hay guiones esperando aprobación.").classes("font-semibold")
                ui.label("Los que escribe ./tpi redactar aparecen acá solos.").classes("tpi-sobrio text-sm")
        for ruta in rutas[:40]:
            estado = qc.estado(ruta)
            elegida = "tpi-ficha-elegida" if ruta == self.elegido else ""
            titulo, categoria = _resumen_de(ruta)
            with (
                ui.column()
                .classes(f"tpi-ficha tpi-clic {elegida} w-full p-4 gap-2 cursor-pointer")
                .on("click", lambda r=ruta: self._elegir(r))
            ):
                if categoria:
                    ui.label(NOMBRES_CATEGORIA[categoria]).classes(f"tpi-insignia tpi-insignia-{categoria}")
                ui.label(titulo).classes("font-semibold leading-snug")
                color = {qc.APROBADO: "tpi-verde", qc.RECHAZADO: "tpi-rojo"}.get(estado, "tpi-celeste")
                ui.label(qc.NOMBRES[estado]).classes(f"{color} text-xs")
                if estado == qc.POR_REVISAR:
                    VistaPrevia(ruta).render()

    def _cambiar_filtro(self, e: Any) -> None:
        self.todos = bool(e.value)
        self.lista.refresh()
        self.lectura.refresh()

    def _elegir(self, ruta: Path) -> None:
        self.elegido = ruta
        self.lista.refresh()
        self.lectura.refresh()

    @ui.refreshable_method
    def lectura(self) -> None:
        if self.elegido is None:
            return
        f = qc.ficha(self.elegido)
        with _clic(_consola(), lambda: _abrir_editor(f.ruta), "Abrir este guion en el editor"):
            _rotulo(" · ".join(x for x in (f.materia, f.nivel, qc.NOMBRES[f.estado]) if x))
            ui.label(f.titulo).classes("text-2xl font-semibold leading-tight")
            if f.error:
                ui.label(f"Este guion no pasa la validación: {f.error}").classes("tpi-rojo text-sm")
            for nota in f.observaciones:
                ui.label(f"⚠ {nota}").classes("tpi-ambar text-sm")
        if f.estilo is not None:
            self._estilo(f)
        with _consola():
            _rotulo("Para redes · toca para copiar")
            if f.metadatos:
                m = f.metadatos
                _clic(
                    ui.label(m["titulo"]).classes("text-lg font-semibold rounded-lg px-2 -mx-2"),
                    lambda: _copiar(m["titulo"], "Título"),
                    "Copiar el título",
                )
                _clic(
                    ui.label(m["descripcion"]).classes("tpi-voz rounded-lg px-2 -mx-2"),
                    lambda: _copiar(m["descripcion"], "Descripción"),
                    "Copiar la descripción",
                )
                with ui.row().classes("gap-2"):
                    for etiqueta in m["hashtags"]:
                        _clic(
                            ui.label(etiqueta).classes("tpi-hashtag rounded-lg px-2"),
                            lambda e=etiqueta: _copiar(e, "Hashtag"),
                            "Copiar este hashtag",
                        )
                    _clic(
                        ui.label("copiar todos").classes("tpi-sobrio text-xs rounded-lg px-2"),
                        lambda: _copiar(" ".join(m["hashtags"]), "Hashtags"),
                        "Copiar los hashtags juntos",
                    )
            else:
                _clic(
                    ui.label(
                        "Este guion no trae título ni hashtags: el kit los escribirá al publicar."
                    ).classes("tpi-sobrio text-sm rounded-lg px-2 -mx-2"),
                    lambda: _abrir_editor(f.ruta),
                    "Abrir el guion para agregarlos",
                )
        with _consola():
            _rotulo("Lo que dice la voz")
            for voz in f.voces:
                with _clic(
                    ui.row().classes("w-full gap-6 no-wrap items-start rounded-lg px-2 py-1 -mx-2"),
                    lambda v=voz: _copiar(v.texto, "Texto de la voz"),
                    "Copiar lo que dice esta voz",
                ):
                    ui.label(voz.seccion.capitalize()).classes("tpi-sobrio text-xs w-24 shrink-0 pt-1")
                    with ui.row().classes("gap-1 items-center"):
                        ui.label(voz.texto).classes("tpi-voz")
                        for pausa in voz.pausas:
                            ui.label(f"pausa {pausa:g} s".replace(".", ",")).classes("tpi-pausa")
        with ui.expansion("Detalles técnicos", icon="code").classes("w-full tpi-plegable").props("dense"):
            with ui.column().classes("w-full gap-2 p-2"):
                for linea in f.tecnico:
                    _clic(
                        ui.label(linea).classes("tpi-sobrio text-sm font-mono rounded-lg px-2"),
                        lambda x=linea: _copiar(x, "Línea"),
                        "Copiar",
                    )
                ui.code(f.yaml, language="yaml").classes("tpi-codigo w-full text-xs")
        with ui.row().classes("w-full justify-end gap-4 pt-2"):
            ui.button(
                color=None, text="Rechazar / Editar", icon="close", on_click=lambda: self._rechazar(f)
            ).classes("tpi-rechazar")
            aprobar = ui.button(
                color=None, text="Aprobar y Enviar a Cola", icon="check", on_click=lambda: self._aprobar(f)
            ).classes("tpi-aprobar")
            if not f.aprobable or f.estado == qc.APROBADO:
                aprobar.disable()

    # ── El estilo del video: el único lugar del panel donde se elige ───────────────────────

    def _estilo(self, f: qc.Ficha) -> None:
        estilo, sugerido = f.estilo, f.sugerido
        temas = _temas()
        elegido = estilo.origen == "guion"
        with _clic(_consola(), lambda: self._dialogo_estilo(f), "Elegir otro estilo para este video"):
            with ui.row().classes("w-full items-center justify-between"):
                _rotulo("Estilo del video · toca para cambiarlo")
                ui.label("elegido por ti" if elegido else "★ sugerido").classes(
                    "tpi-ambar text-xs" if elegido else "tpi-verde text-xs"
                )
            with ui.row().classes("w-full items-center gap-5 no-wrap"):
                _muestra(estilo.clave, temas, ancho=72)
                with ui.column().classes("gap-1 min-w-0"):
                    ui.label(_nombre_estilo(estilo.clave, temas)).classes("text-xl font-semibold")
                    ui.label(estilo.razon).classes("tpi-sobrio text-sm")
                    if elegido and sugerido is not None and sugerido.clave != estilo.clave:
                        ui.label(
                            f"El sugerido sería {_nombre_estilo(sugerido.clave, temas)}: {sugerido.razon}"
                        ).classes("tpi-sobrio text-xs")
                    if estilo.clave not in temas:
                        ui.label("Ese estilo no está en este equipo: el video no se podrá crear.").classes(
                            "tpi-rojo text-xs"
                        )

    def _dialogo_estilo(self, f: qc.Ficha) -> None:
        temas = _temas()
        actual, sugerido = f.estilo.clave, f.sugerido.clave
        orden = [sugerido, *(c for c in temas if c != sugerido)]
        with (
            ui.dialog() as dialogo,
            ui.card().props("flat").classes("tpi-consola p-8 gap-4 w-[880px] max-w-[95vw]"),
        ):
            ui.label(f"Estilo de «{f.titulo}»").classes("text-lg font-semibold")
            ui.label(f"★ Sugerido: {_nombre_estilo(sugerido, temas)}. {f.sugerido.razon}").classes(
                "tpi-sobrio text-sm"
            )

            def elegir(clave: str) -> None:
                try:
                    nuevo = qc.cambiar_estilo(f.ruta, clave)
                except ErrorMotor as e:
                    ui.notify(f"No pude cambiar el estilo: {e.mensaje}", type="negative")
                    return
                dialogo.close()
                ui.notify(
                    f"Estilo: {_nombre_estilo(nuevo.clave, temas)}. Toca «Vista Previa Rápida» para verlo.",
                    type="positive",
                )
                self.lista.refresh()
                self.lectura.refresh()

            with (
                ui.element("div")
                .classes("w-full grid gap-3")
                .style("grid-template-columns: repeat(auto-fill, minmax(250px, 1fr))")
            ):
                for clave in orden:
                    if clave not in temas:
                        continue
                    tema = temas[clave]
                    marcas = ("★ sugerido " if clave == sugerido else "") + (
                        "✓ actual" if clave == actual else ""
                    )
                    with _clic(
                        ui.row().classes(
                            "tpi-ficha w-full p-3 gap-3 no-wrap items-start"
                            + (" tpi-ficha-elegida" if clave == actual else "")
                        ),
                        lambda c=clave: elegir(c),
                        "Usar este estilo",
                    ):
                        _muestra(clave, temas, ancho=54)
                        with ui.column().classes("gap-0 min-w-0"):
                            if marcas:
                                ui.label(marcas.strip()).classes("tpi-ambar text-xs")
                            ui.label(tema.nombre).classes("font-semibold leading-snug")
                            ui.label(_primera_frase(tema.descripcion)).classes(
                                "tpi-sobrio text-xs leading-snug"
                            )
            with ui.row().classes("w-full justify-end pt-2"):
                ui.button(color=None, text="Cerrar", on_click=dialogo.close).props("flat no-caps").classes(
                    "tpi-sobrio"
                )
        dialogo.open()

    def _aprobar(self, f: qc.Ficha) -> None:
        from ...cli import encolar_guion

        try:
            lote_id = encolar_guion(f.ruta)
            qc.aprobar(f.ruta, lote_id)
        except ErrorMotor as e:
            ui.notify(f"No pude enviarlo a la cola: {e.mensaje}", type="negative")
            return
        ui.notify(f"«{f.titulo}» quedó en la cola de producción.", type="positive")
        self.elegido = None
        self.lista.refresh()
        self.lectura.refresh()
        self.al_aprobar()

    def _rechazar(self, f: qc.Ficha) -> None:
        with ui.dialog() as dialogo, ui.card().props("flat").classes("tpi-consola p-8 gap-4 w-[520px]"):
            ui.label("¿Qué hacemos con este guion?").classes("text-lg font-semibold")
            nota = (
                ui.textarea("Qué hay que corregir (opcional)")
                .props("outlined dark autogrow")
                .classes("w-full")
            )

            def solo_rechazar() -> None:
                qc.rechazar(f.ruta, nota.value or "")
                dialogo.close()
                ui.notify("Rechazado: no se va a producir.", type="info")
                self.elegido = None
                self.lista.refresh()
                self.lectura.refresh()

            def editar() -> None:
                qc.rechazar(f.ruta, nota.value or "")
                dialogo.close()
                ui.navigate.to(f"/crear?guion={quote(str(f.ruta))}")

            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                ui.button(color=None, text="Cancelar", on_click=dialogo.close).props("flat no-caps").classes(
                    "tpi-sobrio"
                )
                ui.button(color=None, text="Solo rechazar", on_click=solo_rechazar).classes("tpi-rechazar")
                ui.button(color=None, text="Abrir en el editor", icon="edit", on_click=editar).classes(
                    "tpi-boton-principal"
                )
        dialogo.open()


NOMBRES_CATEGORIA = {"matematicas": "Matemáticas", "fisica": "Física", "ingenieria": "Ingeniería"}


def _temas() -> dict[str, Any]:
    from ...temas import listar_temas

    return {clave: tema for clave, tema, _propio in listar_temas()}


def _nombre_estilo(clave: str, temas: dict[str, Any]) -> str:
    return temas[clave].nombre if clave in temas else clave


def _primera_frase(texto: str) -> str:
    frase = (texto or "").split(":")[0].split(".")[0].strip()
    return frase[:90] + ("…" if len(frase) > 90 else "")


def _muestra(clave: str, temas: dict[str, Any], ancho: int) -> None:
    """Cómo se ve un estilo: el cuadro de su vista previa si ya existe; si no, sus colores de verdad."""
    from ...vista_previa import en_cache

    cuadros = en_cache(clave) if clave in temas else None
    caja = f"width:{ancho}px; aspect-ratio:9/16; flex-shrink:0; border-radius:8px; overflow:hidden"
    if cuadros:
        ui.image(url_medio(cuadros[0])).style(caja)
        return
    if clave not in temas:
        ui.element("div").classes("tpi-ficha").style(caja)
        return
    c = temas[clave].colores
    with ui.column().classes("items-center justify-center gap-1").style(f"{caja}; background:{c.fondo}"):
        ui.label("Aa").classes("font-bold").style(f"color:{c.titulos}; font-size:{ancho // 3}px")
        ui.element("div").style(f"width:60%; height:3px; border-radius:2px; background:{c.acento}")
        ui.element("div").style(f"width:40%; height:3px; border-radius:2px; background:{c.formulas}")


def _resumen_de(ruta: Path) -> tuple[str, str | None]:
    """El título y la categoría de un guion, leídos rápido (sin validar el guion entero)."""
    import yaml

    from ...guion import CATEGORIA_DE_MATERIA, sin_tildes

    respaldo = ruta.stem.replace("_", " ")
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return respaldo, None
    materia = sin_tildes(str(datos.get("materia") or "")).strip().lower()
    materia = materia[:-1] if materia.endswith("s") else materia  # «matemáticas» → «matematica»
    return str(datos.get("titulo") or respaldo), CATEGORIA_DE_MATERIA.get(materia)


class VistaPrevia:
    """«Vista Previa Rápida»: el borrador del guion, renderizado y reproducido dentro de su tarjeta.

    Usa la misma fila de trabajos que todo lo demás (uno a la vez): si el motor está ocupado, avisa.
    El borrador queda en salida/ y se vuelve a mostrar mientras el guion no cambie.
    """

    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta
        self.args = ["crear", str(ruta), "--borrador"]
        self.vigilando = False
        self.marca: tuple = ()

    def borrador(self) -> Path | None:
        """El borrador ya hecho de este guion, si es más nuevo que el guion."""
        from ...entorno import raiz_proyecto
        from ...render import slug

        nombre = slug(self.ruta.stem)
        video = raiz_proyecto() / "salida" / nombre / f"{nombre}_borrador.mp4"
        if video.exists() and video.stat().st_mtime >= self.ruta.stat().st_mtime:
            return video
        return None

    def _mia(self) -> Any:
        t = TAREAS.actual
        return t if t is not None and t.args == self.args else None

    def render(self) -> None:
        self.ancla = ui.element("div").classes("hidden")  # el reloj vive acá: la zona se repinta, esto no
        self.zona()
        if self._mia() is not None and not self._mia().terminada:
            self._vigilar()

    @ui.refreshable_method
    def zona(self) -> None:
        t = self._mia()
        video = self.borrador()
        with ui.column().classes("w-full gap-2").on("click.stop", lambda _e: None):
            if t is not None and not t.terminada:
                ui.linear_progress(value=t.avance, show_value=False, color=None).props("rounded size=4px")
                ui.label(f"Borrador · {round(t.avance * 100)} % · {t.detalle or t.texto_etapa}").classes(
                    "tpi-ambar text-xs"
                )
                return
            if t is not None and t.terminada and t.error:
                ui.label(f"El borrador falló: {t.error.get('mensaje', '')}").classes("tpi-rojo text-xs")
            if video is not None:
                ui.video(url_medio(video), autoplay=False, controls=True).classes(
                    "w-full aspect-[9/16] rounded-lg bg-black"
                )
            boton = (
                ui.button(
                    color=None,
                    text="Vista Previa Rápida" if video is None else "Rehacer la vista previa",
                    icon="slow_motion_video",
                )
                .props("flat dense no-caps")
                .classes("tpi-ambar -ml-2")
            )
            boton.on("click.stop", lambda _e: self._lanzar())
            boton.tooltip("Un borrador rápido y en baja resolución, para mirarlo antes de mandarlo a la cola")

    def _lanzar(self) -> None:
        if TAREAS.ocupado():
            ui.notify("El motor está ocupado: la vista previa espera a que termine.", type="warning")
            return
        TAREAS.lanzar(f"Vista previa · {_resumen_de(self.ruta)[0]}", self.args)
        ui.notify("Armando el borrador: aparece acá mismo en un par de minutos.", type="info")
        self.zona.refresh()
        self._vigilar()

    def _vigilar(self) -> None:
        if self.vigilando:
            return
        self.vigilando = True

        def mirar() -> None:
            t = self._mia()
            marca = (round(t.avance, 2), t.terminada) if t is not None else ("sin tarea",)
            if marca != self.marca:
                self.marca = marca
                self.zona.refresh()
            if t is None or t.terminada:
                reloj.deactivate()
                self.vigilando = False

        with self.ancla:
            reloj = ui.timer(1.0, mirar)


# ------------------------------------------------------------------------------------------
# 3 · Avanzado: todo lo manual, plegado y construido solo al abrirlo
# ------------------------------------------------------------------------------------------


def _plegable(
    titulo: str, icono: str, subtitulo: str, construir: Callable[[], None], abierto: bool = False
) -> None:
    caja = ui.expansion(titulo, icon=icono, caption=subtitulo, value=abierto).classes("tpi-plegable w-full")
    hecho = {"listo": False}

    def armar() -> None:
        if hecho["listo"]:
            return
        hecho["listo"] = True
        with caja:
            with ui.column().classes("tpi-legado w-full gap-6 m-4").style("width: auto"):
                construir()

    caja.on_value_change(lambda e: armar() if e.value else None)
    if abierto:
        armar()


def _fabrica_manual(modo: str, guion: str | None) -> None:
    from .crear import PaginaCrear, guion_permitido
    from .fabrica import PaginaFabrica
    from .un_video import PaginaUnVideo

    pestanas = ui.tabs(value=modo)
    with pestanas:
        ui.tab("uno", label="Un video (con laboratorio de ganchos)", icon="movie_creation")
        ui.tab("lote", label="Lote de 3", icon="bolt")
        ui.tab("paso", label="Paso a paso (editor)", icon="edit_note")
    zona = ui.column().classes("w-full gap-6")

    def productor(valor: str) -> None:
        if valor == "lote":
            PaginaFabrica().render()
        elif valor == "paso":
            estado = PaginaCrear()
            estado.arrancar()
            if ruta := guion_permitido(guion):
                estado.abrir(ruta)
        else:
            PaginaUnVideo().render()

    def al_cambiar(e: Any) -> None:
        zona.clear()
        with zona:
            productor(e.value)

    pestanas.on_value_change(al_cambiar)
    with zona:
        productor(modo)


def _cola_detallada() -> None:
    from .fabrica import ColaLotes

    def lanzar(args: list[str], nombre: str) -> None:
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        TAREAS.lanzar(nombre, args)
        ui.notify("Puesto en marcha.", type="positive")

    ColaLotes(lanzar).dibujar()


def _biblioteca() -> None:
    from .videos import PaginaVideos

    biblioteca = PaginaVideos()
    biblioteca.controles()
    biblioteca.lista()


def _estilos() -> None:
    from .estilos import lista_de_temas

    lista_de_temas()


def _ajustes() -> None:
    from . import ajustes

    ajustes.cuerpo()


def avanzado(abrir: str | None = None, modo: str = "uno", guion: str | None = None) -> None:
    _rotulo("Herramientas manuales · todo queda plegado hasta que lo necesites")
    _plegable(
        "Crear a mano",
        "edit_note",
        "Un video, lote de 3 o el editor paso a paso; incluye el laboratorio de ganchos",
        lambda: _fabrica_manual(modo, guion),
        abierto=abrir == "crear",
    )
    _plegable(
        "Cola detallada por lote",
        "view_list",
        "Reanudar, reintentar o descartar un lote a mano",
        _cola_detallada,
        abierto=abrir == "cola",
    )
    _plegable(
        "Biblioteca de videos",
        "video_library",
        "Todo lo que ya salió, con su kit",
        _biblioteca,
        abrir == "videos",
    )
    _plegable(
        "Estilos visuales", "palette", "Plantillas de color, letra y fondo", _estilos, abrir == "estilos"
    )
    _plegable(
        "Ajustes y diagnóstico",
        "settings",
        "Clave de Gemini, voz, marca, stickers y el chequeo del entorno (tpi doctor)",
        _ajustes,
        abrir == "ajustes",
    )


# ------------------------------------------------------------------------------------------
# La página
# ------------------------------------------------------------------------------------------


def tablero(
    pestana: str = "cola", abrir: str | None = None, modo: str = "uno", guion: str | None = None
) -> None:
    piel_de_la_pagina()
    cabecera(con_menu=False)
    with ui.column().classes("tpi-tablero w-full max-w-7xl mx-auto px-8 py-10 gap-8"):
        pestanas = ui.tabs(value=pestana).props("align=left no-caps inline-label").classes("tpi-pestanas")
        with pestanas:
            for clave, (nombre, icono) in PESTANAS.items():
                ui.tab(clave, label=nombre, icon=icono)
        paneles = (
            ui.tab_panels(pestanas, value=pestana)
            .props("animated keep-alive")
            .classes("w-full bg-transparent")
        )
        construidos: set[str] = set()
        cajas: dict[str, ui.column] = {}

        def ir_a(clave: str) -> None:
            pestanas.set_value(clave)

        def refrescar_cola() -> None:
            if "cola" in construidos:
                cola_vista.firma = ()

        cola_vista = ColaDeProduccion(ir_a)
        qc_vista = AprobacionDeGuiones(refrescar_cola, abrir=guion if pestana == "qc" else None)

        def construir(clave: str) -> None:
            if clave in construidos:
                if clave == "qc":
                    qc_vista.lista.refresh()
                    qc_vista.lectura.refresh()
                return
            construidos.add(clave)
            with cajas[clave]:
                if clave == "cola":
                    cola_vista.render()
                elif clave == "qc":
                    qc_vista.render()
                else:
                    avanzado(abrir, modo, guion)

        with paneles:
            for clave in PESTANAS:
                with ui.tab_panel(clave).classes("p-0 pt-2"):
                    cajas[clave] = ui.column().classes("w-full gap-8")
        pestanas.on_value_change(lambda e: construir(e.value))
        construir(pestana)
