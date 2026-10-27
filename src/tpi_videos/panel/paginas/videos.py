"""Mis videos: verlos, publicarlos (kit), mostrarlos en Finder, rehacerlos con otro estilo o borrarlos."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from nicegui import background_tasks, run, ui

from ...temas import listar_temas
from .. import biblioteca
from ..comun import abrir_en_mac, confirmar, marco, titulo_seccion, url_medio
from ..tareas import TAREAS, Tarea


def _copiar(texto: str) -> None:
    ui.clipboard.write(texto)
    ui.notify("Copiado: pégalo en la app", type="positive")


def _bloque_texto(titulo: str, texto: str) -> None:
    with ui.column().classes("w-full gap-1"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(titulo).classes("font-bold text-sm")
            ui.button("Copiar", icon="content_copy", on_click=lambda: _copiar(texto)).props("flat dense")
        ui.label(texto).classes("w-full whitespace-pre-wrap text-sm bg-[#FAFAF8] rounded p-3 border")


def _mostrar_kit(cuerpo: ui.column, datos: dict[str, Any]) -> None:
    cuerpo.clear()
    portada = Path(datos.get("portada", ""))
    etiquetas = " ".join(datos.get("hashtags", []))
    with cuerpo, ui.row().classes("w-full gap-6 no-wrap items-start"):
        with ui.column().classes("items-center gap-2"):
            if portada.exists():
                ui.image(url_medio(portada)).classes("w-[220px] rounded-lg border")
                ui.button(
                    "Descargar portada", icon="download", on_click=lambda: ui.download.file(portada)
                ).props("outline")
            ui.label("Escrito con IA ✨" if datos.get("con_ia") else "Hecho con plantilla").classes(
                "tpi-ayuda"
            )
        with ui.column().classes("flex-1 gap-4"):
            _bloque_texto("YouTube Shorts · título", datos.get("titulo_youtube", ""))
            _bloque_texto(
                "YouTube Shorts · descripción", f"{datos.get('descripcion_youtube', '')}\n\n{etiquetas}"
            )
            _bloque_texto("TikTok", f"{datos.get('texto_tiktok', '')} {etiquetas}")
            _bloque_texto("Instagram Reels", f"{datos.get('texto_instagram', '')}\n\n{etiquetas}")


async def abrir_kit(carpeta: Path, al_crear: Callable[[], Any] | None = None) -> None:
    """Diálogo con la portada y los textos para publicar (los crea si no existen)."""
    with ui.dialog() as dialogo, ui.card().classes("w-[900px] max-w-[95vw] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("📦 Kit de publicación").classes("tpi-titulo text-xl")
            ui.button(icon="close", on_click=dialogo.close).props("flat round")
        cuerpo = ui.column().classes("w-full gap-3")
        with ui.row().classes("w-full gap-2 items-center"):
            barra = ui.linear_progress(show_value=False).props("indeterminate").classes("flex-1")
            barra.set_visibility(False)
            estado = ui.label("").classes("tpi-ayuda")

            async def crear(con_ia: bool = True) -> None:
                if TAREAS.ocupado():
                    ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
                    return
                barra.set_visibility(True)

                def avance(t: Tarea) -> None:
                    estado.text = t.detalle or t.texto_etapa

                args = ["publicar", str(carpeta)] + ([] if con_ia else ["--sin-ia"])
                tarea = await TAREAS.ejecutar("Kit de publicación", args, al_cambiar=avance)
                barra.set_visibility(False)
                if tarea.ok:
                    estado.text = tarea.resultado.get("aviso") or ""
                    _mostrar_kit(cuerpo, tarea.resultado)
                    if al_crear:
                        al_crear()
                else:
                    estado.text = ""
                    ui.notify((tarea.error or {}).get("mensaje", "No se pudo crear el kit."), type="negative")

            ui.button("Crear de nuevo con IA", icon="auto_awesome", on_click=lambda: crear(True)).props(
                "outline"
            )
            ui.button("Con plantilla (sin IA)", on_click=lambda: crear(False)).props("flat")
    dialogo.open()
    archivo = carpeta / "publicacion.json"
    if archivo.exists():
        _mostrar_kit(cuerpo, json.loads(archivo.read_text(encoding="utf-8")))
    else:
        with cuerpo:
            ui.label(
                "Se crea la portada (el cuadro del gancho) y la IA escribe el título, la descripción y los "
                "hashtags para YouTube Shorts, TikTok e Instagram Reels."
            ).classes("tpi-ayuda")
        await crear(True)


def ver_video(archivo: Path) -> None:
    with ui.dialog() as dialogo, ui.card().classes("p-3 items-center"):
        ui.video(url_medio(archivo), autoplay=True).classes("h-[78vh] aspect-[9/16] rounded-lg bg-black")
        with ui.row().classes("gap-2"):
            ui.button("Abrir en el Mac", icon="open_in_new", on_click=lambda: abrir_en_mac(archivo)).props(
                "flat"
            )
            ui.button("Cerrar", on_click=dialogo.close).props("flat")
    dialogo.open()


def dialogo_rehacer(
    guion: Path, titulo: str, al_terminar: Callable[[], Any] | None = None, por_defecto: str | None = None
) -> None:
    """Rehacer el mismo guion con otro estilo. Lo usan «Mis videos» y la pantalla Video de Crear."""
    temas = {i: t.nombre for i, t, _ in listar_temas()}
    inicial = por_defecto if por_defecto in temas else next(iter(temas))
    with ui.dialog() as dialogo, ui.card().classes("p-6 gap-3 w-[420px]"):
        ui.label("Rehacer con otro estilo").classes("tpi-titulo text-lg")
        eleccion = ui.select(temas, label="Estilo", value=inicial).props("outlined").classes("w-full")
        final = ui.switch("Calidad final (si no, borrador rápido)", value=False)
        barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
        estado = ui.label("").classes("tpi-ayuda")

        async def ir() -> None:
            if TAREAS.ocupado():
                ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
                return
            args = ["crear", str(guion), "--tema", eleccion.value] + ([] if final.value else ["--borrador"])

            def avance(t: Tarea) -> None:
                barra.value = t.avance
                estado.text = t.texto_etapa

            tarea = await TAREAS.ejecutar(f"Rehaciendo «{titulo}»", args, al_cambiar=avance)
            if tarea.ok:
                dialogo.close()
                ui.notify("¡Listo! El video se actualizó.", type="positive")
                if al_terminar:
                    al_terminar()
            elif not tarea.cancelada:
                estado.text = (tarea.error or {}).get("mensaje", "Falló")

        def cancelar() -> None:
            TAREAS.cancelar()
            dialogo.close()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=cancelar).props("flat")
            ui.button("Crear", icon="movie", on_click=ir)
    dialogo.open()


def filtrar(videos: list[biblioteca.Video], busqueda: str, modo: str) -> list[biblioteca.Video]:
    """El muro se recorre: por título, materia o estilo, y por lo que ya se puede publicar."""
    texto = (busqueda or "").strip().casefold()
    mostrados = []
    for video in videos:
        if modo == "borrador" and not video.borrador:
            continue
        if modo == "publicable" and not video.final:
            continue
        if texto and texto not in f"{video.titulo} {video.materia} {video.tema}".casefold():
            continue
        mostrados.append(video)
    return mostrados


def etiqueta_familia(molde: str | None) -> str:
    """La familia que carga con este molde; si el guion va libre, lo dice en vez de inventar una."""
    from ...formatos import cargar_formatos
    from ...moldes import nombre_molde

    if not molde:
        return "Molde libre"
    for familia in cargar_formatos().values():
        if molde in familia.moldes:
            return familia.nombre
    return nombre_molde(molde)


class PaginaVideos:
    """Una por pestaña del navegador: así refrescar la lista nunca toca la página de otra pestaña."""

    def __init__(self) -> None:
        # Los diálogos viven fuera de la lista: refrescarla no los borra mientras se usan
        self.capa = ui.element("div")
        self.busqueda = ""
        self.modo = "todo"
        self.listo = False

    def controles(self) -> None:
        """Buscador y filtro quedan fuera de la lista refrescable: escribir no pierde el foco."""
        with ui.row().classes("w-full items-center gap-3"):
            caja = ui.input("Buscar por título o materia").props("outlined dense clearable").classes("w-72")
            caja.on_value_change(lambda e: self._cambiar(busqueda=e.value or ""))
            selector = (
                ui.select(
                    {"todo": "Todo", "borrador": "Borradores", "publicable": "Publicables"},
                    value="todo",
                    label="Ver",
                )
                .props("outlined dense")
                .classes("w-44")
            )
            selector.on_value_change(lambda e: self._cambiar(modo=e.value or "todo"))
            self.contador = ui.label("").classes("tpi-ayuda")

    def _cambiar(self, busqueda: str | None = None, modo: str | None = None) -> None:
        if busqueda is not None:
            self.busqueda = busqueda
        if modo:
            self.modo = modo
        if self.listo:
            self.lista.refresh()

    def _rehacer(self, video: biblioteca.Video) -> None:
        if video.guion is None:
            ui.notify("No encuentro el guion de este video.", type="warning")
            return
        with self.capa:
            dialogo_rehacer(video.guion, video.titulo, al_terminar=self.lista.refresh)

    def _borrar(self, video: biblioteca.Video) -> None:
        def si() -> None:
            biblioteca.borrar(video)
            ui.notify("Video borrado", type="info")
            self.lista.refresh()

        with self.capa:
            confirmar(f"¿Borrar «{video.titulo}» y sus archivos?", si)

    async def _kit(self, video: biblioteca.Video) -> None:
        with self.capa:
            await abrir_kit(video.carpeta, al_crear=self.lista.refresh)  # así aparece «Kit listo»

    def _ver(self, video: biblioteca.Video) -> None:
        with self.capa:
            ver_video(video.principal)

    def _tarjeta(self, video: biblioteca.Video) -> ui.image:
        with ui.card().classes("tpi-hoja w-full p-0 overflow-hidden gap-0"):
            with (
                ui.element("div")
                .classes("relative w-full aspect-[9/16] max-h-[300px] bg-[#2A2A2C] cursor-pointer")
                .on("click", lambda: self._ver(video))
            ):
                imagen = ui.image("").classes("w-full h-full").props("fit=cover")
                familia = etiqueta_familia(video.molde)
                ui.label(familia).classes("tpi-etiqueta").tooltip(f"Familia: {familia}")
            with ui.column().classes("p-3 gap-1 w-full"):
                ui.label(video.titulo).classes("font-bold leading-tight")
                fecha = dt.datetime.fromtimestamp(video.fecha).strftime("%d-%m %H:%M")
                ui.label(f"{video.tema} · {video.duracion:.0f} s · {fecha}").classes("tpi-ayuda")
                if video.materia:
                    ui.label(video.materia.capitalize()).classes("tpi-ayuda")
                with ui.row().classes("gap-1"):
                    if video.final:
                        ui.chip("Final", color="positive", text_color="white").props("dense square")
                    if video.borrador:
                        ui.chip("Borrador", color="grey-6", text_color="white").props("dense square")
                    if video.kit:
                        ui.chip("Kit listo", color="primary", text_color="white").props("dense square")
                with ui.row().classes("gap-0 w-full justify-between"):
                    for icono, ayuda, accion in (
                        ("play_arrow", "Ver", self._ver),
                        ("inventory_2", "Kit de publicación", self._kit),
                        ("folder_open", "Mostrar en Finder", lambda v: abrir_en_mac(v.principal, True)),
                        ("palette", "Rehacer con otro estilo", self._rehacer),
                        ("delete", "Borrar", self._borrar),
                    ):
                        color = "grey-7" if icono == "delete" else "primary"
                        ui.button(icon=icono, on_click=lambda a=accion: a(video)).props(
                            f"flat round color={color} aria-label='{ayuda}'"
                        ).tooltip(ayuda)
        return imagen

    @ui.refreshable_method
    def lista(self) -> None:
        self._todos = biblioteca.videos()
        if not self._todos:
            with ui.card().classes("tpi-hoja w-full p-10 items-center gap-2"):
                ui.label("🎬").classes("text-5xl")
                ui.label("Todavía no hay videos").classes("tpi-titulo text-lg")
                ui.label("Crea el primero en Fábrica.").classes("tpi-ayuda")
                ui.button("Ir a Crear", on_click=lambda: ui.navigate.to("/crear"))
            self.listo = True
            return
        mostrados = filtrar(self._todos, self.busqueda, self.modo)
        self.contador.text = f"{len(mostrados)} de {len(self._todos)} videos"
        if not mostrados:
            with ui.card().classes("tpi-hoja w-full p-6 items-center gap-1"):
                ui.label("Ningún video coincide").classes("tpi-titulo text-lg")
                ui.label("Prueba con otra palabra, o vuelve a «Todo».").classes("tpi-ayuda")
            self.listo = True
            return
        with (
            ui.element("div")
            .classes("grid gap-3 w-full")
            .style("grid-template-columns: repeat(auto-fill, minmax(190px, 1fr))")
        ):
            imagenes = [(video, self._tarjeta(video)) for video in mostrados]
        background_tasks.create(self._miniaturas(imagenes), name="miniaturas")
        self.listo = True

    @staticmethod
    async def _miniaturas(imagenes: list[tuple[biblioteca.Video, ui.image]]) -> None:
        """Las miniaturas se crean de a una, sin hacer esperar a la página."""
        for video, imagen in imagenes:
            ruta = await run.io_bound(biblioteca.miniatura, video)
            if not imagen.is_deleted:
                imagen.set_source(url_medio(ruta))


def registrar() -> None:
    @ui.page("/videos", title="Mis videos · Tu Profe Industrial")
    def pagina() -> None:
        with marco("/videos"):
            titulo_seccion(
                None, "Mis videos", "Haz clic en un video para verlo. 📦 = portada y textos para publicar."
            )
            pagina_videos = PaginaVideos()
            pagina_videos.controles()
            pagina_videos.lista()
