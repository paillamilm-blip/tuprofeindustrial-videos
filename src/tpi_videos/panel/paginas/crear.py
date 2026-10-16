"""Crear: del enunciado (o un guion) al video, en 3 pasos."""

from __future__ import annotations

import re
from pathlib import Path

from nicegui import events, ui

from ... import ia
from ...config import ajustes_dir, cargar_marca
from ...entorno import PLANTILLAS_DIR, raiz_proyecto
from ...errores import ErrorMotor
from ...guion import cabecera_de, cargar_guion
from ...revision import Revision
from ...temas import listar_temas
from .. import biblioteca
from ..comun import abrir_en_mac, marco, titulo_seccion, url_medio
from ..editor import EditorGuion
from ..tareas import TAREAS, Tarea
from .videos import abrir_kit

TIPOS_SUBIDA = ".jpg,.jpeg,.png,.heic,.heif,.webp,.pdf,.txt"


def _nombre_seguro(nombre: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(nombre).name).strip("._") or "archivo"
    return base[-80:]


def guion_permitido(valor: str | None) -> Path | None:
    """Solo guiones de la carpeta guiones/ (la dirección del panel no puede abrir otros archivos)."""
    if not valor:
        return None
    raiz = raiz_proyecto()
    ruta = Path(valor)
    ruta = (ruta if ruta.is_absolute() else raiz / ruta).resolve()
    dentro = ruta.is_relative_to((raiz / "guiones").resolve())
    return ruta if dentro and ruta.suffix in (".yaml", ".yml") and ruta.is_file() else None


class PaginaCrear:
    def __init__(self) -> None:
        self.editor: EditorGuion | None = None
        self.subida: Path | None = None

    # --------------------------------------------------------------------------------------
    # 1 · El ejercicio
    # --------------------------------------------------------------------------------------

    def seccion_ejercicio(self) -> None:
        titulo_seccion("1", "El ejercicio", "Escríbelo, sube una foto o PDF, o abre un guion que ya tienes.")
        with ui.card().classes("tpi-hoja w-full p-0"):
            with ui.tabs().classes("w-full text-primary") as pestanas:
                ia_tab = ui.tab("Escribir con IA", icon="auto_awesome")
                abrir_tab = ui.tab("Abrir un guion", icon="folder_open")
                blanco_tab = ui.tab("Empezar en blanco", icon="note_add")
            with ui.tab_panels(pestanas, value=ia_tab).classes("w-full"):
                with ui.tab_panel(ia_tab).classes("gap-3"):
                    self._panel_ia()
                with ui.tab_panel(abrir_tab).classes("gap-3"):
                    self._panel_abrir()
                with ui.tab_panel(blanco_tab).classes("gap-3"):
                    self._panel_blanco()

    def _panel_ia(self) -> None:
        if ia.obtener_clave() is None:
            with ui.row().classes("w-full items-center gap-2 bg-[#FFF4E5] rounded p-3"):
                ui.icon("key").classes("text-xl text-orange-8")
                ui.label("Para escribir con IA falta tu clave de Gemini (gratis).")
                ui.link("Configurarla en Ajustes", "/ajustes").classes("font-bold")
        self.enunciado = (
            ui.textarea(
                "Enunciado",
                placeholder="Un bus viaja a 72 km/h constantes. ¿Cuántos minutos tarda en recorrer 18 km?",
            )  # fmt: skip
            .props("outlined autogrow")
            .classes("w-full")
        )
        with ui.row().classes("w-full items-center gap-4"):
            with ui.column().classes("gap-1"):
                ui.upload(
                    label="…o sube una foto o PDF del ejercicio", auto_upload=True, max_files=1,
                    on_upload=self._al_subir, max_file_size=18 * 1024 * 1024,
                    on_rejected=lambda: ui.notify(
                        "Ese archivo pesa más de 18 MB o no es una foto, PDF o .txt: envía una captura de pantalla.",
                        type="warning", multi_line=True,
                    ),
                ).props(f'accept="{TIPOS_SUBIDA}" flat bordered').classes("w-[340px]")  # fmt: skip
                with ui.row().classes("items-center gap-1") as self.fila_archivo:
                    self.texto_archivo = ui.label("").classes("text-sm")
                    ui.button(icon="close", on_click=self._quitar_archivo).props(
                        "flat round dense size=sm aria-label='Quitar archivo'"
                    ).tooltip("Quitar archivo")
                self.fila_archivo.set_visibility(False)
            with ui.column().classes("gap-2 flex-1"):
                self.materia_ia = ui.select(
                    {"": "La IA la deduce", "matematica": "Matemática", "fisica": "Física", "ingenieria": "Ingeniería"},
                    value="", label="Materia",
                ).props("outlined dense").classes("w-60")  # fmt: skip
                self.nivel_ia = ui.input("Nivel (opcional)", placeholder="Ej. 1° medio").props(
                    "outlined dense"
                )
        with ui.row().classes("items-center gap-3"):
            self.boton_ia = ui.button(
                "Escribir el guion con IA", icon="auto_awesome", on_click=self._escribir_con_ia
            )
            self.estado_ia = ui.label("").classes("tpi-ayuda")
        self.barra_ia = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
        self.barra_ia.set_visibility(False)
        self.notas_ia = ui.column().classes("w-full gap-1")

    async def _al_subir(self, e: events.UploadEventArguments) -> None:
        carpeta = ajustes_dir() / "subidas"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / _nombre_seguro(e.file.name)
        await e.file.save(destino)
        self.subida = destino
        e.sender.reset()  # el cuadro queda libre por si quieres cambiar el archivo
        self.texto_archivo.text = f"📎 {destino.name}: la IA leerá este archivo"
        self.fila_archivo.set_visibility(True)

    def _quitar_archivo(self) -> None:
        self.subida = None
        self.fila_archivo.set_visibility(False)

    async def _escribir_con_ia(self) -> None:
        texto = (self.enunciado.value or "").strip()
        if not texto and self.subida is None:
            ui.notify("Escribe el enunciado o sube una foto.", type="warning")
            return
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        args = ["redactar"]
        if self.materia_ia.value:
            args += ["--materia", self.materia_ia.value]
        if (self.nivel_ia.value or "").strip():
            args += ["--nivel", self.nivel_ia.value.strip()]
        args += ["--", str(self.subida) if self.subida else texto]  # la foto o el PDF, si hay
        self.boton_ia.disable()
        self.barra_ia.set_visibility(True)
        self.notas_ia.clear()

        def avance(t: Tarea) -> None:
            self.estado_ia.text = t.detalle or t.texto_etapa

        tarea = await TAREAS.ejecutar("Escribiendo el guion con IA", args, al_cambiar=avance)
        self.boton_ia.enable()
        self.barra_ia.set_visibility(False)
        self.estado_ia.text = ""
        if not tarea.ok:
            self._error(tarea)
            return
        ruta = Path(tarea.resultado["guion"])
        with self.notas_ia:
            ui.label(f"✅ Guion listo: {ruta.name}. Revísalo abajo: la IA puede equivocarse.").classes(
                "font-bold"
            )
            for s in tarea.resultado.get("supuestos") or []:
                ui.label(f"ℹ️ Supuesto de la IA: {s}").classes("text-sm")
            for p in tarea.resultado.get("pendientes") or []:
                ui.label(f"⚠️ Por revisar: {p}").classes("text-sm").style("color:#B26A00")
        self.abrir(ruta)

    def _panel_abrir(self) -> None:
        guardados = biblioteca.guiones()
        opciones = {str(g.ruta): g.nombre for g in guardados}
        with ui.row().classes("w-full items-center gap-3"):
            eleccion = ui.select(opciones, label="Guion", with_input=True).props("outlined").classes("flex-1")
            ui.button(
                "Abrir",
                icon="folder_open",
                on_click=lambda: eleccion.value and self.abrir(Path(eleccion.value)),
            )
        ui.label(
            "Los ejemplos se guardan como copia (con «_mio» al final): los originales no se tocan."
        ).classes("tpi-ayuda")

    def _panel_blanco(self) -> None:
        with ui.row().classes("items-center gap-3"):
            materia = ui.select(
                {"matematica": "Matemática", "fisica": "Física", "ingenieria": "Ingeniería"}, value="fisica",
                label="Materia",
            ).props("outlined dense").classes("w-60")  # fmt: skip
            ui.button(
                "Crear guion desde la plantilla",
                icon="note_add",
                on_click=lambda: self._en_blanco(materia.value),
            )

    def _en_blanco(self, materia: str) -> None:
        guion = cargar_guion(PLANTILLAS_DIR / "guion_base.yaml").model_copy(update={"materia": materia})
        self.cargar_editor(EditorGuion(guion, None))

    def abrir(self, ruta: Path) -> None:
        try:
            guion = cargar_guion(ruta)
        except ErrorMotor as e:
            ui.notify(e.mensaje, type="negative", multi_line=True)
            return
        self.cargar_editor(EditorGuion(guion, ruta, cabecera_de(ruta)))

    # --------------------------------------------------------------------------------------
    # 2 · El guion
    # --------------------------------------------------------------------------------------

    def cargar_editor(self, editor: EditorGuion) -> None:
        self.editor = editor
        editor.al_cambiar_revision = self._mostrar_revision
        self.zona_guion.clear()
        with self.zona_guion:
            titulo_seccion(
                "2", "El guion", "Lo que se ve y lo que se escucha. Los cambios se guardan al crear el video."
            )
            with ui.card().classes("tpi-hoja w-full p-4"), ui.row().classes("w-full items-center gap-3"):
                ui.input("Nombre del archivo").props("outlined dense suffix=.yaml").classes(
                    "w-72"
                ).bind_value(editor.nombre, "valor")
                ui.button("Guardar", icon="save", on_click=self._guardar).props("outline")
                ui.button("Revisar", icon="fact_check", on_click=lambda: editor.revisar()).props("flat")
                self.resumen = ui.label("").classes("tpi-ayuda")
            self.avisos = ui.column().classes("w-full gap-1")
            editor.render()
        self.zona_video.set_visibility(True)
        editor.revisar()
        destino = self.zona_guion.id
        with self.zona_guion:  # cuando el navegador ya mostró el editor, bajar hasta él
            ui.timer(0.4, lambda: ui.run_javascript(
                f'getHtmlElement({destino}).scrollIntoView({{behavior: "smooth", block: "start"}})'
            ), once=True)  # fmt: skip

    def _guardar(self) -> Path | None:
        if self.editor is None:
            return None
        ruta = self.editor.guardar()
        if ruta:
            ui.notify(f"Guardado en guiones/{ruta.name}", type="positive")
        return ruta

    def _mostrar_revision(self, rev: Revision | None, errores: list[str]) -> None:
        self.avisos.clear()
        with self.avisos:
            if errores:
                with ui.card().classes("w-full p-4 bg-[#FDECEC] gap-1").props("flat"):
                    ui.label("Falta completar:").classes("font-bold").style("color:#B71C1C")
                    for linea in errores:
                        ui.label(f"• {linea}").classes("text-sm")
                self.resumen.text = ""
                return
            if rev is None:
                return
            self.resumen.text = f"⏱ ~{rev.segundos:.0f} s · {rev.palabras} palabras"
            if not rev.avisos:
                ui.label("✅ Sin observaciones. ¡Buen guion!").classes("text-sm").style("color:#2E7D32")
            for aviso in rev.avisos:
                icono = "⚠️" if aviso.nivel == "advertencia" else "💡"
                ui.label(f"{icono} {aviso.donde}: {aviso.mensaje}").classes("text-sm")

    # --------------------------------------------------------------------------------------
    # 3 · El video
    # --------------------------------------------------------------------------------------

    def seccion_video(self) -> None:
        with ui.column().classes("w-full gap-4") as self.zona_video:
            titulo_seccion(
                "3", "El video", "Primero un borrador (rápido) para revisar; luego el video final."
            )
            with ui.card().classes("tpi-hoja w-full p-5 gap-4"):
                temas = {i: t.nombre for i, t, _ in listar_temas()}
                por_defecto = cargar_marca().tema
                with ui.row().classes("w-full items-center gap-3"):
                    self.tema = ui.select(
                        temas, label="Estilo", value=por_defecto if por_defecto in temas else None
                    )
                    self.tema.props("outlined dense").classes("w-64")
                    ui.button("Crear borrador", icon="bolt", on_click=lambda: self._crear(True)).props(
                        "outline"
                    )
                    ui.button("Crear video final", icon="movie", on_click=lambda: self._crear(False))
                    self.boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                        "flat color=negative"
                    )
                    self.boton_cancelar.set_visibility(False)
                self.barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
                self.barra.set_visibility(False)
                self.estado = ui.label("").classes("tpi-ayuda")
                self.resultado = ui.row().classes("w-full gap-6 items-start no-wrap")
        self.zona_video.set_visibility(False)

    async def _crear(self, borrador: bool) -> None:
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        ruta = self._guardar()
        if ruta is None:
            return
        args = (
            ["crear", str(ruta)]
            + (["--borrador"] if borrador else [])
            + (["--tema", self.tema.value] if self.tema.value else [])
        )
        self.barra.set_visibility(True)
        self.barra.value = 0
        self.boton_cancelar.set_visibility(True)
        self.resultado.clear()

        def avance(t: Tarea) -> None:
            self.barra.value = t.avance
            self.estado.text = t.texto_etapa

        nombre = "Creando borrador" if borrador else "Creando video final"
        tarea = await TAREAS.ejecutar(nombre, args, al_cambiar=avance)
        self.boton_cancelar.set_visibility(False)
        if not tarea.ok:
            self.barra.set_visibility(False)
            self.estado.text = ""
            if tarea.cancelada:
                ui.notify("Cancelado.", type="info")
            else:
                self._error(tarea)
            return
        video = Path(tarea.resultado["video"])
        self.estado.text = f"✅ Listo en {tarea.resultado.get('segundos', 0)} s · {tarea.resultado.get('duracion', 0)} s de video"
        with self.resultado:
            ui.video(url_medio(video)).classes("h-[70vh] aspect-[9/16] rounded-lg bg-black").props(
                'preload="metadata"'
            )
            with ui.column().classes("gap-2"):
                ui.label("¿Te gusta?").classes("tpi-titulo text-lg")
                ui.label("Si algo no te gusta, cambia el guion arriba y crea de nuevo.").classes("tpi-ayuda")
                ui.button("Abrir en el Mac", icon="open_in_new", on_click=lambda: abrir_en_mac(video)).props(
                    "outline"
                )
                ui.button(
                    "Mostrar en Finder", icon="folder_open", on_click=lambda: abrir_en_mac(video, True)
                ).props("outline")
                if borrador:
                    ui.button("Crear video final", icon="movie", on_click=lambda: self._crear(False))
                ui.button("Kit de publicación", icon="inventory_2", on_click=lambda: abrir_kit(video.parent))

    def _error(self, tarea: Tarea) -> None:
        error = tarea.error or {}
        with ui.dialog() as dialogo, ui.card().classes("p-6 gap-3 w-[640px] max-w-[95vw]"):
            ui.label("Algo no salió").classes("tpi-titulo text-lg").style("color:#D32F2F")
            ui.label(error.get("mensaje", "Error")).classes("whitespace-pre-wrap")
            if error.get("ayuda"):
                ui.label(f"→ {error['ayuda']}").classes("whitespace-pre-wrap text-sm").style("color:#8A5A00")
            with ui.expansion("Detalle técnico (para Kiro)").classes("w-full"):
                ui.code("\n".join(tarea.registro[-40:]) or "(sin detalle)").classes("w-full text-xs")
            ui.button("Cerrar", on_click=dialogo.close).classes("self-end")
        dialogo.open()


def registrar() -> None:
    @ui.page("/", title="Crear · Tu Profe Industrial")
    def pagina(guion: str | None = None) -> None:
        estado = PaginaCrear()
        with marco("/"):
            estado.seccion_ejercicio()
            estado.zona_guion = ui.column().classes("w-full gap-4")
            estado.seccion_video()
            if ruta := guion_permitido(guion):
                estado.abrir(ruta)
