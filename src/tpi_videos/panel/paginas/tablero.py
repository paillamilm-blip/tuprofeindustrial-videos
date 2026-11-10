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
from ..comun import abrir_en_mac, cabecera, confirmar, piel_de_la_pagina
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

    def __init__(self, al_aprobar: Callable[[], None]) -> None:
        self.al_aprobar = al_aprobar
        self.elegido: Path | None = None
        self.todos = False

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
            with (
                ui.column()
                .classes(f"tpi-ficha tpi-clic {elegida} w-full p-4 gap-1 cursor-pointer")
                .on("click", lambda r=ruta: self._elegir(r))
            ):
                ui.label(_titulo_de(ruta)).classes("font-semibold leading-snug")
                color = {qc.APROBADO: "tpi-verde", qc.RECHAZADO: "tpi-rojo"}.get(estado, "tpi-celeste")
                ui.label(qc.NOMBRES[estado]).classes(f"{color} text-xs")

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


def _titulo_de(ruta: Path) -> str:
    import yaml

    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        return str(datos.get("titulo") or ruta.stem.replace("_", " "))
    except (OSError, yaml.YAMLError):
        return ruta.stem.replace("_", " ")


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
        qc_vista = AprobacionDeGuiones(refrescar_cola)

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
