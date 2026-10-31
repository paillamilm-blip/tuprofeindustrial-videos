"""Crear: el camino de cuatro pantallas — Idea, Formato, La hoja, Video.

Se navega libremente entre ellas: la barra de arriba nunca está bloqueada y ninguna sugerencia sin tocar
impide llegar al video. Lo único que se pide es la idea escrita."""

from __future__ import annotations

import json
import re
from pathlib import Path

from nicegui import events, ui

from ... import ia
from ...config import ajustes_dir, cargar_marca
from ...entorno import PLANTILLAS_DIR, raiz_proyecto
from ...errores import ErrorMotor
from ...guion import cabecera_de, cargar_guion
from ...ideas import ANGULOS
from ...moldes import nombre_molde
from ...revision import Revision
from ...temas import listar_temas
from .. import biblioteca, formatos_ui
from ..comun import PIEL, abrir_en_mac, titulo_seccion, url_medio
from ..editor import EditorGuion
from ..tareas import TAREAS, Tarea
from .videos import abrir_kit, dialogo_rehacer

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
# Las cuatro pantallas del camino. La del medio se ve una a la vez; la barra deja saltar a cualquiera.
PASOS = ("idea", "formato", "hoja", "video")
_NOMBRES = {"idea": "Idea", "formato": "Formato", "hoja": "La hoja", "video": "Video"}


def puede_continuar(estado: dict) -> tuple[bool, str]:
    """Ninguna sugerencia sin tocar impide avanzar: solo hace falta la idea escrita."""
    if not (estado.get("idea") or "").strip():
        return False, "Escribe la idea (o sube una foto) para seguir."
    return True, ""


# La etapa del comando dice en qué paso del video completo vamos
ETAPAS = ("El guion", "El video", "El kit")
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
        self.ideas_mostradas: list[dict] = []
        # Lo que él tocó en el muro de familias. Vacío = manda lo que sugiere la máquina; nada de esto
        # bloquea el paso siguiente.
        self.eleccion: dict[str, str | None] = {"clave": None, "molde": None, "tema": None, "dibujo": None}
        self.zona_muro: ui.column | None = None
        self.paso = "idea"
        self.zona_barra: ui.column | None = None
        self.zonas: dict[str, ui.column] = {}
        self.zona_guion: ui.column | None = None
        self.zona_idea_video: ui.column | None = None
        self.ultimo_guion: Path | None = None

    # --------------------------------------------------------------------------------------
    # El camino: una barra arriba y una sola pantalla en el cuerpo
    # --------------------------------------------------------------------------------------

    def arrancar(self) -> None:
        self.zona_barra = ui.column().classes("w-full")
        with ui.column().classes("w-full gap-4"):
            self.zonas = {p: ui.column().classes("w-full gap-4") for p in PASOS}
        with self.zonas["idea"]:
            self.seccion_ejercicio()
        with self.zonas["hoja"]:
            self.zona_guion = ui.column().classes("w-full gap-4")
            with self.zona_guion:
                self._hoja_vacia()
            self.controles_video()
        with self.zonas["video"]:
            self.zona_idea_video = ui.column().classes("w-full gap-3")
            self.pantalla_video()
        self._pintar_barra()
        self._mostrar_paso()

    def ir(self, paso: str) -> None:
        """Moverse por el camino es siempre libre: la barra nunca está bloqueada."""
        self.paso = paso
        if paso == "formato":
            self._pintar_formato()
        self._mostrar_paso()

    def _mostrar_paso(self) -> None:
        for clave, zona in self.zonas.items():
            zona.set_visibility(clave == self.paso)
        self._pintar_barra()

    def _pintar_barra(self) -> None:
        if self.zona_barra is None:
            return
        self.zona_barra.clear()
        with self.zona_barra, ui.row().classes("w-full items-center gap-1 no-wrap"):
            for n, clave in enumerate(PASOS):
                if n:
                    ui.icon("chevron_right").classes("text-base").style(f"color:{PIEL['gris']}")
                boton = ui.button(_NOMBRES[clave], on_click=lambda p=clave: self.ir(p)).props(
                    "flat dense no-caps size=sm"
                )
                if clave == self.paso:
                    boton.classes("font-bold").style(f"color:{PIEL['tinta']}")
                else:
                    boton.classes("tpi-ayuda")

    def _idea_texto(self) -> str:
        """La idea escrita, venga del buscador de ideas o del enunciado suelto."""
        return (self.tema_idea.value or "").strip() or (self.enunciado.value or "").strip()

    def _estado_camino(self) -> dict:
        texto = self._idea_texto()
        return {"idea": texto if texto or self.subida is None else f"foto {self.subida.name}"}

    def _familia_activa(self) -> str:
        return formatos_ui.elegir(self.eleccion["clave"], formatos_ui.sugerido(self._idea_texto())).activo

    def _seguir_formato(self) -> None:
        continuable, motivo = puede_continuar(self._estado_camino())
        if not continuable:
            ui.notify(motivo, type="warning")
            return
        self.ir("formato")

    def _pintar_formato(self) -> None:
        zona = self.zonas["formato"]
        zona.clear()
        idea = self._idea_texto()
        with zona:
            titulo_seccion(
                None,
                "Formato",
                "La familia elegida, con su molde, su estilo y su dibujo ya puestos. Toca «cambiar» en "
                "cualquiera: la familia se queda y nada te bloquea el paso.",
            )
            formatos_ui.pantalla_formato(
                formatos_ui.elegir(self.eleccion["clave"], formatos_ui.sugerido(idea)),
                idea,
                self._elegir_tambien_aqui,
                self._cambiar_pieza,
            )
            with ui.row().classes("w-full items-center gap-3"):
                ui.button("Seguir a la hoja", icon="edit_note", on_click=self._a_la_hoja).props("unelevated")
                ui.button("Volver a la idea", icon="arrow_back", on_click=lambda: self.ir("idea")).props(
                    "flat"
                )

    def _elegir_tambien_aqui(self, clave: str) -> None:
        self._elegir_familia(clave)
        self._pintar_formato()

    def _a_la_hoja(self) -> None:
        """La hoja arranca con el molde y el estilo de la familia; si no tocó nada, los pone la sugerencia."""
        f = formatos_ui.formato(self._familia_activa())
        idea = self._idea_texto()
        base = cargar_guion(PLANTILLAS_DIR / "guion_base.yaml")
        guion = base.model_copy(
            update={
                "titulo": (idea[:60] if idea else base.titulo),
                "molde": self.eleccion["molde"] or f.moldes[0],
                "tema": self.eleccion["tema"] or f.tema,
            }
        )
        self.cargar_editor(EditorGuion(guion, None))

    def _hoja_vacia(self) -> None:
        with ui.card().classes("tpi-hoja w-full p-5 gap-2"):
            ui.label("La hoja todavía está en blanco.").classes("tpi-titulo text-lg")
            ui.label(
                "Escribe la idea y toca un tema, o escribe el enunciado y pulsa «Escribir el guion con IA»: "
                "el guion se arma acá y puedes cambiar cada frase."
            ).classes("tpi-ayuda")
            ui.button("Volver a la idea", icon="arrow_back", on_click=lambda: self.ir("idea")).props(
                "outline"
            )

    # --------------------------------------------------------------------------------------
    # 1 · El ejercicio
    # --------------------------------------------------------------------------------------

    def seccion_ejercicio(self) -> None:
        titulo_seccion(
            None,
            "Idea",
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
            with ui.row().classes(f"w-full items-center gap-2 bg-[{PIEL['banda_aviso']}] rounded p-3"):
                ui.icon("key").classes("text-xl text-orange-8")
                ui.label("Para buscar ideas falta tu clave de Gemini (gratis).")
                ui.link("Configurarla en Ajustes", "/ajustes").classes("font-bold")
        self.tema_idea = ui.input(
            "¿De qué tema quieres un video?", placeholder="Ej. Teorema de Pitágoras"
        ).props("outlined input-debounce=400").classes("w-full")  # fmt: skip
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
        ui.separator().classes("w-full opacity-30")
        ui.label("¿Qué familia de videos es esto?").classes("tpi-titulo text-base")
        ui.label(
            "Toca una tarjeta para cambiar la que está marcada. Si no tocas ninguna, se queda la que "
            "reconoce lo que escribiste arriba."
        ).classes("tpi-ayuda -mt-2")
        self.zona_muro = ui.column().classes("w-full")
        self.tema_idea.on_value_change(lambda _e: self._pintar_muro())
        self._pintar_muro()
        ui.button("Seguir con esta familia", icon="arrow_forward", on_click=self._seguir_formato).props(
            "unelevated"
        ).classes("self-start")
        self.zona_ganchos = ui.column().classes("w-full gap-3")

    # --------------------------------------------------------------------------------------
    # El muro de las cuatro familias
    # --------------------------------------------------------------------------------------

    def _pintar_muro(self) -> None:
        if self.zona_muro is None:
            return
        self.zona_muro.clear()
        with self.zona_muro:
            formatos_ui.muro_y_costado(
                self.eleccion["clave"],
                self.tema_idea.value or "",
                self._elegir_familia,
                self._cambiar_pieza,
            )

    def _elegir_familia(self, clave: str) -> None:
        self.eleccion["clave"] = clave
        self._pintar_muro()

    def _cambiar_pieza(self, clave: str, pieza: str) -> None:
        """La pieza que trajo la familia, editable sin deshacer la familia."""
        campo = {"Molde": "molde", "Estilo": "tema", "Dibujos": "dibujo"}[pieza]
        f = formatos_ui.formato(clave)
        por_defecto = {"Molde": f.moldes[0], "Estilo": f.tema, "Dibujos": f.dibujos[0]}[pieza]
        opciones = dict(next(op for nombre, _valor, op in formatos_ui.piezas(clave) if nombre == pieza))
        with ui.dialog() as dialogo, ui.card().classes("tpi-hoja w-96 p-4 gap-3"):
            ui.label(f"{pieza} de «{f.nombre}»").classes("tpi-titulo text-base")
            valor = ui.select(opciones, value=self.eleccion[campo] or por_defecto, label=pieza).props(
                "outlined dense"
            )
            ui.button(
                "Listo", icon="check", on_click=lambda: self._aplicar_pieza(dialogo, campo, valor)
            ).props("unelevated")
        dialogo.open()

    def _aplicar_pieza(self, dialogo: ui.dialog, campo: str, selector: ui.select) -> None:
        self.eleccion[campo] = selector.value
        dialogo.close()
        self._pintar_muro()
        if self.paso == "formato":
            self._pintar_formato()

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
        self.ideas_mostradas = ideas
        with self.tarjetas_ideas:
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(f"3 ideas para «{tema}»").classes("tpi-titulo text-lg")
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.button("Otras 3 ideas", icon="refresh", on_click=lambda: self._buscar_ideas()).props(
                        "outline"
                    )
                    ui.button(
                        "Hacer los 3 videos",
                        icon="playlist_add_check",
                        on_click=self._hacer_lote,
                    ).props("color=primary")
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
                        ui.label("lo escribió la IA").classes("tpi-ayuda")
                    molde = str(idea.get("molde") or "")
                    if molde:
                        ui.chip(nombre_molde(molde), icon="movie_filter").props("dense outline size=sm")
                    elegido_label = ui.label(f"«{idea.get('gancho', '')}»").classes("text-base")
                    ganchos = list(idea.get("ganchos") or [])
                    if ganchos:
                        with ui.expansion(f"Ver los {len(ganchos)} ganchos", icon="bolt").classes("w-full"):
                            for g in ganchos:
                                ui.label(f"{g.get('estilo', '')}: «{g.get('texto', '')}»").classes(
                                    "tpi-ayuda"
                                )
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
                        if ganchos:
                            ui.button(
                                "Probar ganchos",
                                icon="videocam",
                                on_click=lambda i=idea, e=elegido_label: self._probar_ganchos(i, e),
                            ).props("outline")
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
        variante = idea.get("gancho_elegido")
        if variante:
            args += ["--gancho-json", json.dumps(variante, ensure_ascii=False)]
        elif idea.get("gancho"):
            args += ["--gancho", str(idea["gancho"])]
        if idea.get("ganchos"):
            args += ["--ganchos-json", json.dumps(idea["ganchos"], ensure_ascii=False)]
        if idea.get("molde"):
            args += ["--molde", str(idea["molde"])]
        if idea.get("titulo"):
            args += ["--titulo", str(idea["titulo"])]
        if idea.get("segundos"):
            args += ["--segundos", str(idea["segundos"])]
        args += ["--", enunciado]

        self.ir("video")
        self.zona_idea_video.clear()
        with self.zona_idea_video:
            with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                ui.label(f"🎬 {idea.get('titulo', 'El video')}").classes("text-lg font-bold")
                barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
                pasos = [ui.label(f"・ {p}").classes("tpi-ayuda") for p in ETAPAS]
                estado = ui.label("").classes("tpi-ayuda")
                boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                    "flat color=negative"
                )

        def avance(t: Tarea) -> None:
            barra.value = t.avance
            estado.text = t.texto_etapa
            actual = ETAPA_PASO.get(t.etapa, 0) if not t.terminada else len(ETAPAS)
            for n, etiqueta in enumerate(pasos):
                marca = "✅" if n < actual else ("⏳" if n == actual else "・")
                etiqueta.set_text(f"{marca} {ETAPAS[n]}")

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

    async def _probar_ganchos(self, idea: dict, etiqueta) -> None:
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        if not idea.get("ganchos"):
            ui.notify("Esta idea no trae variantes: busca otras 3.", type="warning")
            return
        self.zona_ganchos.clear()
        with self.zona_ganchos:
            with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                ui.label(f"🎣 Probando los ganchos de «{idea.get('titulo', '')}»").classes(
                    "text-lg font-bold"
                )
                barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
                estado = ui.label("Preparando los clips…").classes("tpi-ayuda")
                boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                    "flat color=negative"
                )
                fila = ui.row().classes("w-full gap-4 items-start flex-wrap")

        def avance(t: Tarea) -> None:
            barra.value = t.avance
            estado.text = t.texto_etapa

        tarea = await TAREAS.ejecutar(
            "Ganchos",
            ["ganchos", "--idea-json", json.dumps(idea, ensure_ascii=False)],
            al_cambiar=avance,
        )
        boton_cancelar.set_visibility(False)
        if not tarea.ok:
            if tarea.cancelada:
                ui.notify(
                    "Cancelado: los clips que alcanzaron a salir quedan en salida/ganchos/.", type="info"
                )
                return
            self._error(tarea)
            return
        estado.text = "Elige el que más frena el scroll."
        clips = list(tarea.resultado.get("clips") or [])
        if not clips:
            ui.notify("No se generó ningún clip.", type="warning")
            return

        def usar(clip: dict) -> None:
            idea["gancho"] = clip["texto"]
            idea["gancho_elegido"] = clip
            idea["ganchos"] = [clip] + [g for g in idea.get("ganchos", []) if g.get("texto") != clip["texto"]]
            etiqueta.text = f"«{clip['texto']}»"
            ui.notify("Ese gancho viaja al video cuando toques «Hacer este video».", type="positive")

        with fila:
            for clip in clips:
                archivo = Path(str(clip.get("archivo", "")))
                with ui.column().classes("items-center gap-2 w-44"):
                    ui.video(url_medio(archivo)).classes("w-full aspect-[9/16] rounded-lg bg-black").props(
                        'preload="metadata"'
                    )
                    ui.label(f"{clip.get('numero')}. «{clip.get('texto', '')}»").classes(
                        "text-sm font-bold text-center"
                    )
                    ui.label(f"{clip.get('estilo', '')} · {clip.get('segundos', 0)} s").classes("tpi-ayuda")
                    ui.button("Usar este", icon="check", on_click=lambda c=clip: usar(c)).props(
                        "outline dense"
                    )

    async def _hacer_lote(self) -> None:
        """Los 3 videos de las ideas que ya están en pantalla, en un solo trabajo de cola."""
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        ideas = [i for i in self.ideas_mostradas if str(i.get("enunciado") or "").strip()]
        if len(ideas) < 2:
            ui.notify("Estas ideas no traen el ejercicio: busca otras 3.", type="warning")
            return
        args = ["lote", "--ideas-json", json.dumps(ideas, ensure_ascii=False)]

        self.ir("video")
        self.zona_idea_video.clear()
        with self.zona_idea_video:
            with ui.card().classes("tpi-hoja w-full p-5 gap-2"):
                ui.label(f"📦 Lote de {len(ideas)} videos, uno detrás de otro").classes("text-lg font-bold")
                barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
                estado = ui.label("").classes("tpi-ayuda")
                ui.label(
                    "Tarda unos 3 minutos por video. Si una idea falla, el lote sigue con las siguientes y "
                    "guarda lo que salió."
                ).classes("tpi-ayuda")
                boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                    "flat color=negative"
                )

        def avance(t: Tarea) -> None:
            barra.value = t.avance
            estado.text = t.texto_etapa

        tarea = await TAREAS.ejecutar("Lote de videos", args, al_cambiar=avance)
        boton_cancelar.set_visibility(False)
        if not tarea.ok:
            if tarea.cancelada:
                ui.notify("Cancelado: los videos que ya terminaron quedan en salida/.", type="info")
                return
            self._error(tarea)
            return
        self._mostrar_lote(list(tarea.resultado.get("lote") or []))

    def _mostrar_lote(self, items: list[dict]) -> None:
        """La tabla del lote: qué salió, qué quedó por revisar y por qué falló el que no salió."""
        listos = sum(1 for item in items if item.get("ok"))
        self.zona_idea_video.clear()
        with self.zona_idea_video:
            with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                ui.label(f"Lote terminado: {listos} de {len(items)} videos").classes("tpi-titulo text-lg")
                for item in items:
                    with ui.column().classes("w-full gap-1 border-t pt-2"):
                        with ui.row().classes("w-full items-center gap-3 no-wrap"):
                            if item.get("ok"):
                                aviso = "⚠️" if item.get("promesa_incumplida") else "✅"
                                ui.label(f"{aviso} {item.get('emoji', '')} {item.get('titulo', '')}").classes(
                                    "font-bold"
                                )
                                promesa = item.get("prometido")
                                duracion = f"≈{item.get('duracion', 0)} s"
                                ui.label(
                                    f"{duracion}" + (f" · prometidos ≈{promesa} s" if promesa else "")
                                ).classes("tpi-ayuda")
                                if item.get("molde"):
                                    ui.label(nombre_molde(str(item["molde"]))).classes("tpi-ayuda")
                            else:
                                ui.label(f"❌ {item.get('emoji', '')} {item.get('titulo', '')}").classes(
                                    "font-bold"
                                )
                                ui.label(str(item.get("error") or "No salió")).classes("text-sm").style(
                                    f"color:{PIEL['error']}"
                                )
                            ui.space()
                            if item.get("ok"):
                                video = Path(item["video"])
                                ui.button(
                                    "Abrir", icon="play_circle", on_click=lambda v=video: abrir_en_mac(v)
                                ).props("flat dense")
                                ui.button(
                                    "Kit", icon="inventory_2", on_click=lambda v=video: abrir_kit(v.parent)
                                ).props("flat dense")
                        for pendiente in item.get("pendientes") or []:
                            ui.label(f"⚠️ Por revisar: {pendiente}").classes("text-sm").style(
                                f"color:{PIEL['aviso']}"
                            )
                if listos < len(items):
                    ui.label(
                        "Las tarjetas de arriba siguen sirviendo: «Hacer este video» reintenta una por una."
                    ).classes("tpi-ayuda")

    def _mostrar_video_ideas(self, resultado: dict, idea: dict) -> None:
        video = Path(resultado["video"])
        guion = Path(resultado["guion"])
        self.ultimo_guion = guion
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
                            ui.label(f"⚠️ Por revisar: {pendiente}").classes("text-sm").style(
                                f"color:{PIEL['aviso']}"
                            )
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
                        ui.button(
                            "Editar la hoja", icon="edit_note", on_click=lambda: self.abrir(guion)
                        ).props("outline")

    def _panel_ia(self) -> None:
        if ia.obtener_clave() is None:
            with ui.row().classes(f"w-full items-center gap-2 bg-[{PIEL['banda_aviso']}] rounded p-3"):
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
            ui.label("lo escribió la IA").classes("tpi-ayuda")
            ui.label(f"✅ Guion listo: {ruta.name}. Revísalo abajo: la IA puede equivocarse.").classes(
                "font-bold"
            )
            for s in tarea.resultado.get("supuestos") or []:
                ui.label(f"ℹ️ Supuesto de la IA: {s}").classes("text-sm")
            for p in tarea.resultado.get("pendientes") or []:
                ui.label(f"⚠️ Por revisar: {p}").classes("text-sm").style(f"color:{PIEL['aviso']}")
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
    # La hoja: lo que se ve y lo que se escucha
    # --------------------------------------------------------------------------------------

    def cargar_editor(self, editor: EditorGuion) -> None:
        self.editor = editor
        editor.al_cambiar_revision = self._mostrar_revision
        self.zona_guion.clear()
        with self.zona_guion:
            titulo_seccion(
                None,
                "La hoja",
                "El gancho, las cuentas y el cierre, todos a la vez. Lo que se ve y lo que se escucha. "
                "Los cambios se guardan al crear el video.",
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
        # El selector muestra el estilo que trae el guion (el de la familia): si no, crearía con otro
        # distinto del que él vio en el muro.
        estilo_del_guion = editor.datos.get("tema")
        if estilo_del_guion in self.tema.options:
            self.tema.value = estilo_del_guion
        self.ir("hoja")
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
                with ui.card().classes(f"w-full p-4 bg-[{PIEL['banda_error']}] gap-1").props("flat"):
                    ui.label("Falta completar:").classes("font-bold").style(f"color:{PIEL['error_fuerte']}")
                    for linea in errores:
                        ui.label(f"• {linea}").classes("text-sm")
                self.resumen.text = ""
                return
            if rev is None:
                return
            self.resumen.text = f"⏱ ~{rev.segundos:.0f} s · {rev.palabras} palabras"
            if not rev.avisos:
                ui.label("✅ Sin observaciones. ¡Buen guion!").classes("text-sm").style(
                    f"color:{PIEL['exito']}"
                )
            for aviso in rev.avisos:
                icono = "⚠️" if aviso.nivel == "advertencia" else "💡"
                ui.label(f"{icono} {aviso.donde}: {aviso.mensaje}").classes("text-sm")

    # --------------------------------------------------------------------------------------
    # Video
    # --------------------------------------------------------------------------------------

    def controles_video(self) -> None:
        """El pie de la hoja: lo que arranca el render. Ninguno se apaga por no haber tocado una sugerencia."""
        with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
            temas = {i: t.nombre for i, t, _ in listar_temas()}
            por_defecto = cargar_marca().tema
            with ui.row().classes("w-full items-center gap-3"):
                self.tema = ui.select(
                    temas, label="Estilo", value=por_defecto if por_defecto in temas else None
                )
                self.tema.props("outlined dense").classes("w-64")
                ui.button("Crear borrador", icon="bolt", on_click=lambda: self._crear(True)).props("outline")
                ui.button("Crear el video", icon="movie", on_click=lambda: self._crear(False))

    def pantalla_video(self) -> None:
        """La pantalla Video: el reproductor con su kit, el clip de 5 s y el «otra vez con este estilo»."""
        with ui.column().classes("w-full gap-4") as self.zona_video:
            titulo_seccion(
                None,
                "Video",
                "Lo que sale del motor. Si algo no te gusta, vuelve a la hoja y cambia la frase.",
            )
            self.boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                "flat color=negative"
            )
            self.boton_cancelar.set_visibility(False)
            self.barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
            self.barra.set_visibility(False)
            self.estado = ui.label("").classes("tpi-ayuda")
            self.resultado = ui.row().classes("w-full gap-6 items-start no-wrap")
            with ui.row().classes("w-full items-center gap-3"):
                ui.button("Solo el gancho (≈5 s)", icon="crop_free", on_click=self._solo_gancho).props(
                    "outline"
                )
                ui.button("Otra vez con este estilo", icon="refresh", on_click=self._otra_vez).props("flat")
                ui.label(
                    "El clip de 5 s es solo el gancho, sin subtítulos: sirve para ver si frena el scroll."
                ).classes("tpi-ayuda")

    def _guion_del_render(self) -> Path | None:
        """El guion que hay que renderizar: el último que salió, o la hoja guardada ahora."""
        return self.ultimo_guion or self._guardar()

    async def _solo_gancho(self) -> None:
        """El laboratorio de ganchos del motor, sobre el guion de la hoja: ./tpi ganchos <guion>."""
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        ruta = self._guion_del_render()
        if ruta is None:
            ui.notify("Primero guarda la hoja.", type="warning")
            return
        self.ir("video")
        self.barra.set_visibility(True)
        self.barra.value = 0
        self.boton_cancelar.set_visibility(True)
        self.resultado.clear()

        def avance(t: Tarea) -> None:
            self.barra.value = t.avance
            self.estado.text = t.texto_etapa

        tarea = await TAREAS.ejecutar("El gancho (5 s)", ["ganchos", str(ruta)], al_cambiar=avance)
        self.boton_cancelar.set_visibility(False)
        self.barra.set_visibility(False)
        if not tarea.ok:
            self.estado.text = ""
            if tarea.cancelada:
                ui.notify("Cancelado: lo que alcanzó a salir queda en salida/ganchos/.", type="info")
            else:
                self._error(tarea)
            return
        clips = list(tarea.resultado.get("clips") or [])
        self.estado.text = f"🎣 {len(clips)} clip(s) de gancho en salida/ganchos/"
        with self.resultado:
            for clip in clips:
                with ui.column().classes("items-center gap-2 w-44"):
                    ui.video(url_medio(Path(str(clip.get("archivo", ""))))).classes(
                        "w-full aspect-[9/16] rounded-lg bg-black"
                    ).props('preload="metadata"')
                    ui.label(f"{clip.get('numero')}. «{clip.get('texto', '')}»").classes(
                        "text-sm font-bold text-center"
                    )
                    ui.label(f"{clip.get('estilo', '')} · {clip.get('segundos', 0)} s").classes("tpi-ayuda")

    def _otra_vez(self) -> None:
        """El mismo guion, otro estilo: el mismo diálogo que usa «Mis videos»."""
        ruta = self._guion_del_render()
        if ruta is None:
            ui.notify("Primero guarda la hoja.", type="warning")
            return
        titulo = self.editor.nombre["valor"] if self.editor else ruta.stem
        dialogo_rehacer(ruta, titulo, por_defecto=self.tema.value, al_terminar=self._repintar)

    def _repintar(self) -> None:
        """El reproductor muestra el clip recién rehacer, no el anterior."""
        t = TAREAS.actual
        if t and t.ok and t.resultado.get("video"):
            self._reproducir(Path(t.resultado["video"]), t.resultado, borrador=False)

    def _reproducir(self, video: Path, resultado: dict, borrador: bool) -> None:
        """El clip que salió, con el kit de publicación al lado."""
        self.resultado.clear()
        with self.resultado:
            ui.video(url_medio(video)).classes("h-[70vh] aspect-[9/16] rounded-lg bg-black").props(
                'preload="metadata"'
            )
            with ui.column().classes("gap-2"):
                ui.label("¿Te gusta?").classes("tpi-titulo text-lg")
                ui.label(f"creado con IA · ≈ {resultado.get('duracion', 0)} s").classes("tpi-ayuda")
                ui.button("Abrir en el Mac", icon="open_in_new", on_click=lambda: abrir_en_mac(video)).props(
                    "outline"
                )
                ui.button(
                    "Mostrar en Finder", icon="folder_open", on_click=lambda: abrir_en_mac(video, True)
                ).props("outline")
                ui.button("Kit de publicación", icon="inventory_2", on_click=lambda: abrir_kit(video.parent))
                if borrador:
                    ui.button("Crear video final", icon="movie", on_click=lambda: self._crear(False))

    async def _crear(self, borrador: bool) -> None:
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        ruta = self._guardar()
        if ruta is None:
            ui.notify("Escribe la idea (o sube una foto) para seguir.", type="warning")
            return
        self.ultimo_guion = ruta
        self.ir("video")
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
        self.estado.text = f"✅ Listo en {tarea.resultado.get('segundos', 0)} s · {tarea.resultado.get('duracion', 0)} s de video"  # fmt: skip
        self._reproducir(video, tarea.resultado, borrador)

    def _error(self, tarea: Tarea) -> None:
        error = tarea.error or {}
        with ui.dialog() as dialogo, ui.card().classes("p-6 gap-3 w-[640px] max-w-[95vw]"):
            ui.label("Algo no salió").classes("tpi-titulo text-lg").style(f"color:{PIEL['error']}")
            ui.label(error.get("mensaje", "Error")).classes("whitespace-pre-wrap")
            if error.get("ayuda"):
                ui.label(f"→ {error['ayuda']}").classes("whitespace-pre-wrap text-sm").style(
                    f"color:{PIEL['aviso_fuerte']}"
                )
            with ui.expansion("Detalle técnico (para Kiro)").classes("w-full"):
                ui.code("\n".join(tarea.registro[-40:]) or "(sin detalle)").classes("w-full text-xs")
            ui.button("Cerrar", on_click=dialogo.close).classes("self-end")
        dialogo.open()
