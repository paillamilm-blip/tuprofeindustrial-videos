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
from ...ideas import ANGULOS
from ...revision import Revision
from ...temas import listar_temas
from .. import biblioteca
from ..comun import abrir_en_mac, marco, titulo_seccion, url_medio
from ..editor import EditorGuion
from ..tareas import TAREAS, Tarea
from .videos import abrir_kit

TIPOS_SUBIDA = ".jpg,.jpeg,.png,.heic,.heif,.webp,.pdf,.txt"

# Temas que más piden en el canal: un atajo para no tener que escribir
TEMAS_SUGERIDOS = (
    "Ley de Ohm",
    "Caída libre",
    "Porcentajes",
    "Teorema de Pitágoras",
    "MRU",
    "Potencia eléctrica",
)
ANGULOS_ICONO = {
    "error_tipico": "report_problem",
    "aplicacion_real": "construction",
    "dato_curioso": "emoji_objects",
    "paso_a_paso": "school",
    "reto": "sports_score",
}
NOMBRES_MATERIA = {"matematica": "Matemática", "fisica": "Física", "ingenieria": "Ingeniería"}
# La etapa del comando dice en qué paso del video completo vamos
PASOS = ("El guion", "El video", "El kit")
ETAPA_PASO = {
    "redactando": 0,
    "guion": 0,
    "preparando": 1,
    "animacion": 1,
    "subtitulos": 1,
    "video final": 1,
    "listo": 2,
    "publicando": 2,
}


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
        self.ideas_vistas: list[str] = []

    # --------------------------------------------------------------------------------------
    # 1 · El ejercicio
    # --------------------------------------------------------------------------------------

    def seccion_ejercicio(self) -> None:
        titulo_seccion(
            "1",
            "El ejercicio",
            "Busca ideas con la IA, escribe el enunciado, sube una foto o PDF, o abre un guion que ya tienes.",
        )
        with ui.card().classes("tpi-hoja w-full p-0"):
            with ui.tabs().classes("w-full text-primary") as pestanas:
                ideas_tab = ui.tab("Ideas", icon="lightbulb")
                ia_tab = ui.tab("Escribir con IA", icon="auto_awesome")
                abrir_tab = ui.tab("Abrir un guion", icon="folder_open")
                blanco_tab = ui.tab("Empezar en blanco", icon="note_add")
            with ui.tab_panels(pestanas, value=ideas_tab).classes("w-full"):
                with ui.tab_panel(ideas_tab).classes("gap-3"):
                    self._panel_ideas()
                with ui.tab_panel(ia_tab).classes("gap-3"):
                    self._panel_ia()
                with ui.tab_panel(abrir_tab).classes("gap-3"):
                    self._panel_abrir()
                with ui.tab_panel(blanco_tab).classes("gap-3"):
                    self._panel_blanco()

    # --------------------------------------------------------------------------------------
    # Ideas: la IA propone 3, la persona elige y el motor hace el video completo
    # --------------------------------------------------------------------------------------

    def _panel_ideas(self) -> None:
        if ia.obtener_clave() is None:
            with ui.row().classes("w-full items-center gap-2 bg-[#FFF4E5] rounded p-3"):
                ui.icon("key").classes("text-xl text-orange-8")
                ui.label("Para buscar ideas falta tu clave de Gemini (gratis).")
                ui.link("Configurarla en Ajustes", "/ajustes").classes("font-bold")
        self.tema_idea = ui.input(
            "¿De qué tema quieres un video?", placeholder="Ej. Teorema de Pitágoras"
        ).props("outlined").classes("w-full")  # fmt: skip
        with ui.row().classes("w-full items-center flex-wrap gap-2"):
            ui.label("O toca un tema sugerido:").classes("tpi-ayuda")
            for sugerido in TEMAS_SUGERIDOS:
                ui.button(sugerido, on_click=lambda t=sugerido: self._buscar_ideas(t)).props(
                    "outline dense no-caps size=sm"
                )
        with ui.row().classes("w-full items-end gap-4"):
            self.materia_idea = ui.select(
                {"": "La IA la deduce", "matematica": "Matemática", "fisica": "Física", "ingenieria": "Ingeniería"},
                value="", label="Materia",
            ).props("outlined dense").classes("w-60")  # fmt: skip
            self.nivel_idea = ui.input("Nivel (opcional)", placeholder="Ej. 2° medio").props("outlined dense")
            self.boton_ideas = ui.button("Buscar 3 ideas", icon="lightbulb", on_click=self._buscar_ideas)
            self.estado_ideas = ui.label("").classes("tpi-ayuda")
        self.barra_ideas = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
        self.barra_ideas.set_visibility(False)
        self.tarjetas_ideas = ui.column().classes("w-full gap-3")
        with self.tarjetas_ideas:
            ui.label("Las 3 ideas aparecen aquí. En la que te guste, toca «Hacer este video».").classes(
                "tpi-ayuda"
            )
        self.zona_idea_video = ui.column().classes("w-full gap-3")

    async def _buscar_ideas(self, tema: str | None = None) -> None:
        texto = (tema or self.tema_idea.value or "").strip()
        if not texto:
            ui.notify("Escribe un tema (ej. «Porcentajes») o toca uno de los sugeridos.", type="warning")
            return
        if tema:
            self.tema_idea.value = tema
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        args = ["ideas"]
        if self.materia_idea.value:
            args += ["--materia", self.materia_idea.value]
        if (self.nivel_idea.value or "").strip():
            args += ["--nivel", self.nivel_idea.value.strip()]
        if self.ideas_vistas:
            args += ["--evitar", *self.ideas_vistas]
        args += ["--", texto]

        self.boton_ideas.disable()
        self.barra_ideas.set_visibility(True)
        self.estado_ideas.text = "La IA está pensando 3 ideas…"
        tarea = await TAREAS.ejecutar("Buscando ideas", args)
        self.boton_ideas.enable()
        self.barra_ideas.set_visibility(False)
        self.estado_ideas.text = ""
        if not tarea.ok:
            if tarea.cancelada:
                ui.notify("Cancelado.", type="info")
            else:
                self._error(tarea)
            return
        ideas = list(tarea.resultado.get("ideas") or [])
        if len(ideas) < 3:
            ui.notify("La IA trajo pocas ideas: prueba con un tema más concreto.", type="warning")
            return
        self.ideas_vistas = (self.ideas_vistas + [str(i.get("titulo", "")) for i in ideas])[-9:]
        self._mostrar_tarjetas(ideas, texto)

    def _mostrar_tarjetas(self, ideas: list[dict], tema: str) -> None:
        self.tarjetas_ideas.clear()
        self.zona_idea_video.clear()
        with self.tarjetas_ideas:
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(f"3 ideas para «{tema}»").classes("tpi-titulo text-lg")
                ui.button("Otras 3 ideas", icon="refresh", on_click=lambda: self._buscar_ideas()).props(
                    "outline"
                )
            for idea in ideas:
                angulo = str(idea.get("angulo", ""))
                clave_materia = str(idea.get("materia", ""))
                materia = NOMBRES_MATERIA.get(clave_materia, clave_materia.capitalize())
                emoji = str(idea.get("emoji") or "")
                with ui.card().classes("tpi-hoja w-full p-5 gap-2"):
                    with ui.row().classes("w-full items-center gap-3 no-wrap"):
                        ui.icon(ANGULOS_ICONO.get(angulo, "bolt")).classes("text-2xl text-primary")
                        ui.label(ANGULOS.get(angulo, "Idea")).classes("tpi-titulo text-sm")
                        ui.label(f"{emoji} {idea.get('titulo', '')}".strip()).classes("text-lg font-bold")
                    ui.label(f"«{idea.get('gancho', '')}»").classes("text-base")
                    ui.label(str(idea.get("enunciado", ""))).classes("tpi-ayuda")
                    ui.label(str(idea.get("porque", ""))).classes("text-sm italic")
                    with ui.row().classes("w-full items-center gap-3"):
                        with ui.row().classes("items-center gap-2 no-wrap"):
                            for etiqueta in (
                                str(idea.get("nivel", "")),
                                materia,
                                f"≈ {idea.get('segundos', 0)} s",
                            ):
                                if etiqueta:
                                    ui.chip(etiqueta).props("dense outline size=sm")
                        ui.space()
                        ui.button(
                            "Hacer este video",
                            icon="movie",
                            on_click=lambda i=idea: self._hacer_video(i),
                        )

    async def _hacer_video(self, idea: dict) -> None:
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        enunciado = str(idea.get("enunciado") or "").strip()
        if not enunciado:
            ui.notify("Esta idea no trae el ejercicio: busca otras 3.", type="warning")
            return
        args = ["producir"]
        if idea.get("materia"):
            args += ["--materia", str(idea["materia"])]
        if idea.get("nivel"):
            args += ["--nivel", str(idea["nivel"])]
        if idea.get("gancho"):
            args += ["--gancho", str(idea["gancho"])]
        if idea.get("titulo"):
            args += ["--titulo", str(idea["titulo"])]
        if idea.get("segundos"):
            args += ["--segundos", str(idea["segundos"])]
        args += ["--", enunciado]

        self.zona_idea_video.clear()
        with self.zona_idea_video:
            with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                ui.label(f"🎬 {idea.get('titulo', 'El video')}").classes("text-lg font-bold")
                barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
                pasos = [ui.label(f"・ {p}").classes("tpi-ayuda") for p in PASOS]
                estado = ui.label("").classes("tpi-ayuda")
                boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                    "flat color=negative"
                )

        def avance(t: Tarea) -> None:
            barra.value = t.avance
            estado.text = t.texto_etapa
            actual = ETAPA_PASO.get(t.etapa, 0) if not t.terminada else len(PASOS)
            for n, etiqueta in enumerate(pasos):
                marca = "✅" if n < actual else ("⏳" if n == actual else "・")
                etiqueta.set_text(f"{marca} {PASOS[n]}")

        tarea = await TAREAS.ejecutar("Video completo", args, al_cambiar=avance)
        if not tarea.ok:
            boton_cancelar.set_visibility(False)
            if tarea.cancelada:
                ui.notify("Cancelado.", type="info")
                return
            self._error(tarea)
            return
        boton_cancelar.set_visibility(False)
        self._mostrar_video_ideas(tarea.resultado, idea)

    def _mostrar_video_ideas(self, resultado: dict, idea: dict) -> None:
        video = Path(resultado["video"])
        guion = Path(resultado["guion"])
        self.zona_idea_video.clear()
        with self.zona_idea_video:
            with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                with ui.row().classes("w-full items-start gap-6 no-wrap"):
                    ui.video(url_medio(video)).classes("h-[70vh] aspect-[9/16] rounded-lg bg-black").props(
                        'preload="metadata"'
                    )
                    with ui.column().classes("gap-2"):
                        ui.label("✅ Video completo listo").classes("tpi-titulo text-lg")
                        ui.label(
                            f"≈ {resultado.get('duracion', 0)} s · estilo {resultado.get('tema', '')} · "
                            f"guion en {guion.name}"
                        ).classes("tpi-ayuda")
                        promesa = resultado.get("prometido")
                        if promesa:
                            # Si no cupo, el ⚠️ de arriba (avisos del guion) ya lo dice: acá solo mostramos
                            # los dos números, para que la comparación la haga quien mira la tarjeta.
                            ui.label(
                                f"Prometido en la idea: ≈{promesa} s · el video duró "
                                f"{resultado.get('duracion', 0)} s"
                            ).classes("tpi-ayuda")
                        for pendiente in resultado.get("pendientes") or []:
                            ui.label(f"⚠️ Por revisar: {pendiente}").classes("text-sm").style("color:#B26A00")
                        for supuesto in resultado.get("supuestos") or []:
                            ui.label(f"ℹ️ Supuesto de la IA: {supuesto}").classes("text-sm")
                        ui.label(
                            "Revisa el guion y el video antes de publicar: la IA puede equivocarse."
                        ).classes("text-sm")
                        ui.button(
                            "Kit de publicación", icon="inventory_2", on_click=lambda: abrir_kit(video.parent)
                        ).props("outline")
                        ui.button(
                            "Abrir en el Mac", icon="open_in_new", on_click=lambda: abrir_en_mac(video)
                        ).props("outline")
                        ui.button(
                            "Otro video de este tema", icon="refresh", on_click=lambda: self._buscar_ideas()
                        ).props("flat")
        self.abrir(guion)  # el guion queda arriba, listo para retocar y recrear el video

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
