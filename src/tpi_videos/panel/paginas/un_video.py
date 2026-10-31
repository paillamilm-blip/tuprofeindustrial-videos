"""Un video: la IA arma todo y tú cambias lo que quieras, en una sola pantalla.

A la izquierda se escribe la idea; a la derecha aparece cómo queda armada (Familia, Molde, Estilo, Voz,
Duración, Gancho, Rodaje) con su razón y su «cambiar» en cada pieza. Nada bloquea el paso: lo único que
se necesita es la frase. Lo que se muestra es siempre lo que ``tpi producir`` va a recibir — por eso la
lógica vive en ``sugerencia.py``, fuera de los widgets, y acá sólo se pinta.

El trabajo pesado corre afuera, en un proceso aparte (``TAREAS``), y se mira con un temporizador: si se
recarga la pestaña, el video se termina igual.
"""

from __future__ import annotations

import re
from pathlib import Path

from nicegui import events, ui

from ... import ia
from ...config import cargar_marca
from ...errores import ErrorMotor
from .. import formatos_ui, sugerencia
from ..comun import PIEL, abrir_en_mac, url_medio
from ..miniaturas import dibujar_miniatura
from ..tareas import TAREAS, Tarea
from .ajustes import VOCES
from .crear import ETAPAS, ETAPA_PASO, TEMAS_SUGERIDOS
from .videos import abrir_kit

# Los trabajos que esta pantalla sabe retomar si se recarga a medias
PROPIOS = ("Video",)
ICONO_PIEZA = {
    "familia": "category",
    "molde": "movie_filter",
    "tema": "palette",
    "voz": "record_voice_over",
    "segundos": "timer",
    "gancho": "bolt",
    "rodaje": "videocam",
}
# La bandera que abre cada nombre en Ajustes sobra acá: el país ya está escrito entre paréntesis.
_VOCES = {clave: re.sub(r"^[^\w]*", "", nombre) for clave, nombre in VOCES.items()}
# Las ideas de la IA que la tarjeta lee para dejar de ser un secreto
CAMPOS_IDEA = ("materia", "nivel", "titulo", "gancho", "gancho_elegido", "ganchos", "molde", "segundos")


def _propuesta(idea: dict) -> dict:
    """Sólo los campos que la tarjeta sabe mostrar: nada de valores sueltos que nadie pidió."""
    return {clave: idea[clave] for clave in CAMPOS_IDEA if idea.get(clave)}


class PaginaUnVideo:
    def __init__(self) -> None:
        self.cambios: dict[str, str] = {}
        self.propuesta: dict = {}
        self.kit = True
        self.mio = False  # si esta pestaña está siguiendo el trabajo de "Crear el video"
        self.solo_lectura = False  # mientras graba, la tarjeta ya no se puede cambiar
        self._visto: tuple | None = None  # no repintar (ni dibujar) si la receta no cambió
        self._miniatura: dict[tuple, Path] = {}  # manim no se repite dos veces en la misma pantalla
        self._variantes: list[dict] = []  # las 3 ideas de la IA, tales como viajaron
        self.marcas: list[bool] = []  # cuáles quiere producir: la opción B

    # ── el armazón ──────────────────────────────────────────────────────────────────────

    def render(self) -> None:
        # La tarjeta se arma por pestaña (cada cliente con la suya): `refreshable` suelto, no del clase.
        self.costado = ui.refreshable(self._costado)
        self.zona_inicio = ui.column().classes("w-full gap-4")
        with self.zona_inicio:
            self._cabecera()
            with ui.row().classes("tpi-columnas w-full items-start"):
                with ui.column().classes("gap-4 w-full min-w-0"):
                    self._panel_idea()
                    self._panel_ia()
                    self._panel_acciones()
                    self.zona_trabajo = ui.column().classes("w-full gap-2")
                    with self.zona_trabajo:
                        self._pantalla_trabajo()
                    self.zona_trabajo.set_visibility(False)
                    self.zona_resultado = ui.column().classes("w-full gap-2")
                    self.zona_resultado.set_visibility(False)
                with ui.column().classes("tpi-costado gap-3 w-full min-w-0"):
                    self.costado(self._sugerencia())
        self._reanudar()
        ui.timer(0.7, self._mirar)

    def _cabecera(self) -> None:
        with ui.column().classes("w-full gap-1"):
            ui.label("Un video, armado por la IA").classes("tpi-titulo text-2xl")
            ui.label(
                "Escribe la idea y a la derecha vas viendo cómo queda armado. Cada pieza dice por qué "
                "está así y se puede cambiar; nada te tapa el botón."
            ).classes("tpi-ayuda")

    # ── la idea ─────────────────────────────────────────────────────────────────────────

    def _panel_idea(self) -> None:
        with ui.card().classes("tpi-hoja w-full p-6 gap-3"):
            if ia.obtener_clave() is None:
                with ui.row().classes(f"w-full items-center gap-2 bg-[{PIEL['banda_aviso']}] rounded p-3"):
                    ui.icon("key").classes("text-xl text-orange-8")
                    ui.label("Para crear el video falta tu clave de Gemini (es gratis).")
                    ui.link("Configurarla en Ajustes", "/ajustes").classes("font-bold")
            self.idea = (
                ui.textarea(
                    "La idea o el enunciado",
                    placeholder="Un bus viaja a 72 km/h constantes. ¿Cuántos minutos tarda en recorrer 18 km?",
                    on_change=self._al_escribir,
                )
                .props("outlined autogrow input-debounce=400")
                .classes("w-full")
            )  # fmt: skip
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.label("O toca un tema:").classes("tpi-ayuda")
                for sugerido in TEMAS_SUGERIDOS:
                    ui.button(
                        sugerido,
                        icon="add",
                        on_click=lambda t=sugerido: self._con_idea(t),
                    ).props("outline dense no-caps size=sm")

    def _al_escribir(self, _e: events.ValueChangeEventArguments) -> None:
        self.propuesta = {}  # una frase escrita por ti no es la idea de la IA
        self._pintar()

    def _con_idea(self, texto: str) -> None:
        self.idea.value = texto  # el bind_value dispara `_al_escribir` y con eso se repinta la tarjeta

    # ── las 3 ideas de la IA ────────────────────────────────────────────────────────────

    def _panel_ia(self) -> None:
        with ui.card().classes("tpi-hoja w-full p-5 gap-2"):
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                self.boton_ideas = ui.button(
                    "Pedir 3 ideas a la IA", icon="lightbulb", on_click=self._buscar_ideas
                ).props("outline no-caps")
                self.estado_ideas = ui.label("").classes("tpi-ayuda")
            self.barra_ideas = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
            self.barra_ideas.set_visibility(False)
            self.tarjetas_ideas = ui.column().classes("w-full gap-2")
            self._lugar_comun(self.tarjetas_ideas)
            with ui.row().classes("w-full items-center gap-3 no-wrap") as self.barra_variantes:
                self.contador_variantes = ui.label("ninguna seleccionada").classes("tpi-ayuda")
                self.boton_compilar = ui.button(
                    "Compilar seleccionados", icon="inventory_2", on_click=self._compilar
                ).props("outline no-caps")
            self.boton_compilar.disable()
            self.barra_variantes.set_visibility(False)
            ui.label(
                "«Compilar» manda una sola tarea: produce de a una las variantes marcadas y el avance "
                "lo ves en «Cola y biblioteca»."
            ).classes("tpi-ayuda text-xs")

    def _lugar_comun(self, contenedor) -> None:
        """El aviso que ocupa la pared mientras no hay ideas: el mismo texto, una sola vez escrito."""
        with contenedor:
            ui.label(
                "Acá aparecen las 3 ideas. Marca las que quieras y toca «Compilar seleccionados»: "
                "salen de una, como el Lote. «Usar esta idea» la pasa a la caja de arriba igual que antes."
            ).classes("tpi-ayuda")

    async def _buscar_ideas(self) -> None:
        texto = (self.idea.value or "").strip()
        if not texto:
            ui.notify("Escribe un tema primero (ej. «Porcentajes»).", type="warning")
            return
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        self.boton_ideas.disable()
        self.barra_ideas.set_visibility(True)
        self.tarjetas_ideas.clear()  # las ideas anteriores ya valieron: la pared nueva las pinta encima
        self._variantes, self.marcas = [], []
        self.barra_variantes.set_visibility(False)
        self._lugar_comun(self.tarjetas_ideas)
        self.estado_ideas.text = "La IA está pensando 3 ideas…"
        tarea = await TAREAS.ejecutar("Buscando ideas", ["ideas", "--", texto])
        self.boton_ideas.enable()
        self.barra_ideas.set_visibility(False)
        self.estado_ideas.text = ""
        if not tarea.ok:
            if not tarea.cancelada:
                self._avisar_error(tarea)
            return
        ideas = list(tarea.resultado.get("ideas") or [])
        if not ideas:
            ui.notify("La IA no trajo ideas: prueba con un tema más concreto.", type="warning")
            return
        self._mostrar_ideas(ideas)

    def _mostrar_ideas(self, ideas: list[dict]) -> None:
        self.tarjetas_ideas.clear()
        self._variantes = list(ideas)
        self.marcas = [False] * len(ideas)
        with self.tarjetas_ideas:
            for n, idea in enumerate(ideas):
                with ui.card().classes("w-full p-4 gap-1 border rounded-lg").style(
                    f"background:{PIEL['caja']}; border-color:{PIEL['borde_hoja']}"
                ):
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.checkbox(
                            value=False,
                            on_change=lambda _e, i=n: self._al_marcar(i),
                        ).props("dense")
                        ui.label(str(idea.get("titulo") or "La idea")).classes("font-bold")
                        ui.label("lo escribió la IA").classes("tpi-ayuda text-xs")
                    ui.label(str(idea.get("gancho") or "")).classes("text-sm italic")
                    ui.label(
                        f"molde: {idea.get('molde') or 'lo decide la IA'} · ≈{idea.get('segundos', 0)} s"
                        f" · {str(idea.get('nivel') or '')}"
                    ).classes("tpi-ayuda text-xs")
                    ui.button("Usar esta idea", icon="check", on_click=lambda i=idea: self._usar_idea(i)).props(
                        "outline dense no-caps size=sm"
                    )
        self.barra_variantes.set_visibility(True)
        self._contador()

    def _al_marcar(self, n: int) -> None:
        self.marcas[n] = not self.marcas[n]
        self._contador()

    def _contador(self) -> None:
        """Las marcadas mandan: contador, botón prendido sólo con una arriba y el número adentro."""
        n = sum(self.marcas)
        self.contador_variantes.text = f"{n} seleccionada{'s' if n != 1 else ''}" if n else "ninguna seleccionada"
        self.boton_compilar.set_text(f"Compilar seleccionados{' (' + str(n) + ')' if n else ''}")
        if n:
            self.boton_compilar.enable()
        else:
            self.boton_compilar.disable()

    def _compilar(self) -> None:
        """La opción B: las variantes marcadas salen de una, con el mismo `tpi lote` de Fábrica."""
        try:
            elegidas = sugerencia.variantes_seleccionadas(self._variantes, self.marcas)
        except ValueError:
            elegidas = []
        if not elegidas:
            ui.notify("Marca al menos una idea para compilar.", type="warning")
            return
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        cantidad = len(elegidas)
        TAREAS.lanzar(f"Compilar {cantidad} variantes", sugerencia.args_compilacion(elegidas))
        ui.notify(
            f"{'Puesta' if cantidad == 1 else 'Puestas'} en cola {cantidad} "
            f"variante{'s' if cantidad != 1 else ''}: el avance lo ves en «Cola y biblioteca».",
            type="positive",
        )

    def _usar_idea(self, idea: dict) -> None:
        """La idea entra completa a la caja y a la receta: su molde, su gancho, su largo ya no son un secreto."""
        self.idea.value = str(idea.get("enunciado") or idea.get("titulo") or "").strip()
        # va después del valor: `_al_escribir` limpia la propuesta, acá vuelve a cargarla
        self.propuesta = _propuesta(idea)
        self._pintar()
        ui.notify("Idea cargada: mira la tarjeta de la derecha y toca «Crear el video».", type="positive")

    # ── el botón ────────────────────────────────────────────────────────────────────────

    def _panel_acciones(self) -> None:
        with ui.row().classes("w-full items-center gap-4 flex-wrap"):
            self.boton_arrancar = ui.button(
                "Crear el video", icon="movie_creation", on_click=self._arrancar
            ).props("size=lg color=negative")
            self.nota_tiempo = ui.label(
                "Unos 3 minutos. Puedes dejarlo corriendo y volver a esta pestaña."
            ).classes("tpi-ayuda")

    # ── mientras trabaja ────────────────────────────────────────────────────────────────

    def _pantalla_trabajo(self) -> None:
        with ui.card().classes("tpi-hoja w-full p-5 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Grabando").classes("tpi-titulo text-lg")
                self.boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                    "flat color=negative"
                )
            self.barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
            self.porcentaje = ui.label("0 %").classes("text-sm font-bold")
            self.detalle = ui.label("").classes("tpi-ayuda")
            self.pasos = [
                (
                    ui.icon("radio_button_unchecked", size="16px"),
                    ui.label(paso).classes("tpi-ayuda text-sm"),
                )
                for paso in ETAPAS
            ]

    def _arrancar(self) -> None:
        su = self._sugerencia()
        bloqueada = su.bloqueada()
        if bloqueada:
            ui.notify(bloqueada, type="warning")
            return
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        self.mio = True
        self._visto = None  # el resultado nuevo se pinta aunque la receta sea la misma
        TAREAS.lanzar("Video completo", list(su.args))
        self.zona_resultado.clear()
        self.zona_resultado.set_visibility(False)
        self._abloquear(True, su)
        self.zona_trabajo.set_visibility(True)
        self.barra.value = 0.0
        self.porcentaje.text = "0 %"
        self.detalle.text = "La IA está escribiendo el guion…"
        self.boton_cancelar.set_visibility(True)

    def _abloquear(self, grabando: bool, su: sugerencia.Sugerencia | None = None) -> None:
        """Mientras graba, la tarjeta se vuelve de solo lectura: lo que ya viajó al motor no se toca.

        La tarjeta entera se repinta con `solo_lectura` puesto (sus controles se crean ya apagados); acá
        sólo se apagan los que viven fuera de ella.
        """
        self.solo_lectura = grabando
        for elemento in (self.idea, self.boton_arrancar, self.boton_ideas):
            if grabando:
                elemento.disable()
            else:
                elemento.enable()
        if grabando:
            self.costado.refresh(su or self._sugerencia())
        else:
            self._visto = None  # al terminar, la tarjeta vuelve a seguir lo que está escrito
            self._pintar()

    def _mirar(self) -> None:
        """El trabajo es de la app, no de esta pestaña: acá solo se mira, aunque se recargue la página."""
        if not self.mio:
            return
        t = TAREAS.actual
        if t is None:
            self.mio = False
            return
        self._avance(t)
        if not t.terminada:
            return
        self.mio = False
        self._abloquear(False)
        self.zona_trabajo.set_visibility(False)
        if t.cancelada:
            ui.notify("Cancelado. Lo que alcanzó a salir queda en la carpeta salida/.", type="info")
            return
        self._mostrar_resultado(t)

    def _avance(self, t: Tarea) -> None:
        self.barra.value = t.avance
        self.porcentaje.text = f"{round(t.avance * 100)} %"
        self.detalle.text = t.detalle or t.texto_etapa
        actual = ETAPA_PASO.get(t.etapa, 0) if not t.terminada else len(ETAPAS)
        for n, (icono, etiqueta) in enumerate(self.pasos):
            if n < actual:
                icono.set_name("task_alt").set_text_color(PIEL["exito"])
            elif n == actual:
                icono.set_name("sync").set_text_color(PIEL["marca"])
            else:
                icono.set_name("radio_button_unchecked").set_text_color(PIEL["gris"])
            etiqueta.text = ETAPAS[n]

    # ── cuando termina ──────────────────────────────────────────────────────────────────

    def _mostrar_resultado(self, t: Tarea) -> None:
        self.zona_resultado.clear()
        try:
            with self.zona_resultado:
                if t.ok:
                    self._pantalla_resultado(t.resultado)
                else:
                    error = t.error or {}
                    self._pantalla_error(error.get("mensaje", "El motor no respondió."), error.get("ayuda"))
        except Exception as e:  # noqa: BLE001 - un resultado raro no puede dejarla sin pantalla
            self.zona_resultado.clear()
            with self.zona_resultado:
                self._pantalla_error("El panel no alcanzó a leer el resultado.", str(e))
        self.zona_resultado.set_visibility(True)

    def _pantalla_resultado(self, resultado: dict) -> None:
        video = Path(str(resultado.get("video") or ""))
        with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
            with ui.row().classes("w-full items-start gap-5 no-wrap"):
                if video.exists():
                    ui.video(url_medio(video)).classes("h-[62vh] aspect-[9/16] rounded-lg bg-black").props(
                        'preload="metadata"'
                    )
                with ui.column().classes("gap-2 min-w-0"):
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.icon("task_alt").classes("text-xl").set_text_color(PIEL["exito"])
                        ui.label("Video listo").classes("tpi-titulo text-lg")
                    ui.label(
                        f"≈{resultado.get('duracion', 0)} s · estilo {resultado.get('tema', '—')} · "
                        f"guion en {Path(str(resultado.get('guion') or 'guion')).name}"
                    ).classes("tpi-ayuda")
                    promesa = resultado.get("prometido")
                    if promesa:
                        ui.label(
                            f"La idea prometió ≈{promesa} s y el video duró {resultado.get('duracion', 0)} s."
                        ).classes("tpi-ayuda")
                    for pendiente in resultado.get("pendientes") or []:
                        self._nota("priority_high", PIEL["aviso_fuerte"], f"Por revisar: {pendiente}")
                    for supuesto in resultado.get("supuestos") or []:
                        self._nota("info", PIEL["gris"], f"Supuesto de la IA: {supuesto}")
                    ui.label("Revísalo antes de publicar: la IA puede equivocarse con un número.").classes(
                        "text-sm"
                    )
                    if video.exists():
                        with ui.row().classes("gap-2 no-wrap items-center"):
                            ui.button(
                                "Kit de publicación",
                                icon="inventory_2",
                                on_click=lambda v=video: abrir_kit(v.parent),
                            ).props("outline no-caps")
                            ui.button(
                                "Abrir en el Mac", icon="open_in_new", on_click=lambda v=video: abrir_en_mac(v)
                            ).props("outline no-caps")
                    with ui.row().classes("gap-2 no-wrap items-center pt-1"):
                        ui.button(
                            "Crear otro con esta misma idea",
                            icon="refresh",
                            on_click=self._arrancar,
                        ).props("flat no-caps")
                        ui.link("Verlos todos en Mis videos", "/videos").classes("text-sm font-bold")
            ui.label("El video anterior no se borra: cada uno tiene su carpeta en salida/.").classes(
                "tpi-ayuda text-xs"
            )

    def _pantalla_error(self, mensaje: str, ayuda: str | None) -> None:
        with ui.card().classes("tpi-hoja w-full p-5 gap-2 tpi-error"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("error").classes("text-2xl").set_text_color(PIEL["error"])
                ui.label("Este video no salió").classes("tpi-titulo text-lg")
            ui.label(str(mensaje)).classes("whitespace-pre-wrap")
            if ayuda:
                ui.label(f"→ {ayuda}").classes("text-sm").style(f"color:{PIEL['aviso_fuerte']}")
            with ui.row().classes("gap-3 items-center"):
                ui.button("Volver a intentar", icon="refresh", on_click=self._arrancar).props("outline no-caps")
                ui.link("Revisar Ajustes", "/ajustes").classes("font-bold")

    def _avisar_error(self, t: Tarea) -> None:
        error = t.error or {}
        ui.notify(f"{error.get('mensaje', 'No salió.')} {error.get('ayuda') or ''}".strip(), type="negative")

    def _nota(self, icono: str, color: str, texto: str) -> None:
        """Un aviso con su icono y su color, nunca solo con el color (se lee igual en escala de grises)."""
        with ui.row().classes("items-start gap-2 no-wrap"):
            ui.icon(icono, size="16px").set_text_color(color)
            ui.label(texto).classes("text-sm leading-snug")

    # ── la tarjeta de la derecha ────────────────────────────────────────────────────────

    def _sugerencia(self) -> sugerencia.Sugerencia:
        return sugerencia.armar(
            idea=str(self.idea.value or ""),
            cambios=self.cambios,
            preferencias=self._preferencias(),
            propuesta=self.propuesta,
            kit=self.kit,
        )

    def _preferencias(self) -> sugerencia.Preferencias:
        """El estilo y la voz de siempre, los que están guardados en Ajustes."""
        marca = cargar_marca()
        return sugerencia.Preferencias(tema=marca.tema, voz=marca.voz.nombre, voces=dict(_VOCES))

    def _pintar(self) -> None:
        if self._trabajando():
            return  # mientras graba, la receta ya viajó al motor: no se pinta otra
        su = self._sugerencia()
        firma = (
            su.idea, su.familia, self.kit,
            tuple(sorted(self.cambios.items())), tuple(sorted(self.propuesta.items())),
        )  # fmt: skip
        if firma == self._visto:
            return
        self._visto = firma
        self.costado.refresh(su)

    def _trabajando(self) -> bool:
        t = TAREAS.actual
        return t is not None and not t.terminada and t.nombre.startswith(PROPIOS)

    def _costado(self, su: sugerencia.Sugerencia) -> None:
        with ui.card().classes("tpi-tarjeta w-full p-5 gap-3"):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.label("Así está armado").classes("tpi-titulo text-lg").style(
                    f"color:{PIEL['texto_muro']}"
                )
                ui.space()
                self.switch_kit = ui.switch("Kit", value=self.kit, on_change=self._al_kit).props(
                    "dense right-color=white"
                ).tooltip("El kit de publicación: la portada y los textos para TikTok, Shorts y Reels")
                self.switch_kit.set_enabled(not self.solo_lectura)
            self._portada(su)
            for pieza in su.piezas:
                self._fila(su, pieza)
            with ui.row().classes("w-full items-start gap-2 no-wrap border-t pt-3"):
                ui.icon("terminal", size="16px").set_text_color(PIEL["tenue_muro"])
                ui.label("tpi " + " ".join(su.args)).classes("text-xs font-mono").style(
                    f"color:{PIEL['tenue_muro']}"
                )

    def _al_kit(self, e: events.ValueChangeEventArguments) -> None:
        self.kit = bool(e.value)
        self._visto = None
        self._pintar()

    def _portada(self, su: sugerencia.Sugerencia) -> None:
        """El cuadro que sale de esta familia, al lado de lo que la receta hace pasar en pantalla."""
        clave_tema = next((p.codigo for p in su.piezas if p.clave == "tema"), None)
        tema = clave_tema or "hoja_de_desarrollo"
        destino, error = None, None
        try:
            visual = formatos_ui.visual_de_portada(su.clave_familia)
            clave = (str(visual["tipo"]), tema)
            if clave not in self._miniatura:
                self._miniatura[clave] = dibujar_miniatura(visual, tema=tema)
            destino = self._miniatura[clave]
        except ErrorMotor as e:
            error = e.mensaje
        with ui.row().classes("w-full items-start gap-3 no-wrap"):
            if destino is not None:
                ui.image(url_medio(destino)).classes("shrink-0 rounded-md").style("width:132px")
            else:
                ui.element("div").classes("shrink-0 rounded-md").style(
                    f"width:132px; aspect-ratio:9/16; background:{PIEL['tarjeta']}"
                )
            with ui.column().classes("gap-1 min-w-0"):
                if error:
                    ui.label(error).classes("text-xs").style(f"color:{PIEL['aviso_muro']}")
                else:
                    ui.label("Lo que se ve pasar").classes("tpi-tenue text-xs")
                    for nota in sugerencia.anotaciones(su.rodaje):
                        with ui.row().classes("items-start gap-1 no-wrap"):
                            ui.icon("chevron_right", size="12px").set_text_color(PIEL["tenue_muro"])
                            ui.label(nota).classes("text-xs leading-snug").style(
                                f"color:{PIEL['texto_muro']}"
                            )

    def _fila(self, su: sugerencia.Sugerencia, pieza) -> None:
        with ui.row().classes("w-full items-start gap-2 no-wrap border-t pt-3"):
            ui.icon(ICONO_PIEZA.get(pieza.clave, "tune"), size="18px").set_text_color(PIEL["tenue_muro"])
            with ui.column().classes("gap-0 min-w-0 flex-1"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.label(pieza.etiqueta).classes("text-xs uppercase tracking-wide").style(
                        f"color:{PIEL['tenue_muro']}"
                    )
                    if pieza.tocada:
                        ui.label("lo cambiaste tú").classes("text-xs font-bold").style(
                            f"color:{PIEL['aviso_muro']}"
                        )
                ui.label(pieza.valor).classes("text-sm leading-snug").style(f"color:{PIEL['texto_muro']}")
                ui.label(pieza.razon).classes("tpi-tenue text-xs")
            if self.solo_lectura:
                ui.label("ya viajó").classes("text-xs self-center").style(f"color:{PIEL['tenue_muro']}")
            elif pieza.destino:
                ui.link("cambiar", pieza.destino).classes("text-xs font-bold self-center")
            else:
                ui.button(
                    "cambiar",
                    on_click=lambda p=pieza.clave: self._cambiar(p, su),
                ).props("flat dense size=sm no-caps").style(f"color:{PIEL['texto_muro']}")

    # ── los diálogos de «cambiar» ───────────────────────────────────────────────────────

    def _cambiar(self, clave: str, su: sugerencia.Sugerencia) -> None:
        actual = su.pieza(clave)
        codigo = "" if actual is None or actual.codigo is None else str(actual.codigo)
        if clave == "voz":
            self._dialogo_lista(clave, "Tu voz de siempre", _VOCES, codigo)
            return
        if clave == "gancho":
            self._dialogo_texto(clave, "Escribe el gancho", codigo)
            return
        if clave == "segundos":
            self._dialogo_lista(clave, "¿Cuánto dura?", sugerencia.opciones(clave), codigo)
            return
        if clave == "tema":
            self._dialogo_lista(clave, "Tu estilo de siempre", sugerencia.opciones(clave), codigo, False)
            return
        self._dialogo_lista(
            clave, f"Cambiar {sugerencia.ETIQUETAS[clave].lower()}", sugerencia.opciones(clave), codigo
        )

    def _dialogo_lista(
        self,
        clave: str,
        titulo: str,
        opciones: dict[str, str],
        codigo: str,
        permite_ia: bool = True,
    ) -> None:
        """La lista sale de las mismas colecciones del motor: si aparece un molde nuevo, acá también.

        El valor de cada opción es la clave real (lo que viaja en la bandera), nunca el nombre bonito.
        """
        valores = ({"": "Que lo decida la IA"} if permite_ia else {}) | opciones
        with ui.dialog() as dialogo, ui.card().classes("p-5 gap-3 w-[360px]"):
            ui.label(titulo).classes("tpi-titulo text-base")
            opciones_ui = ui.select(
                valores, value=codigo if codigo in valores else "", label="Elegí"
            ).props("outlined")

            def aplicar(valor: object) -> None:
                self.cambios[clave] = str(valor or "")
                self._visto = None
                dialogo.close()
                self._pintar()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Mejor no", on_click=dialogo.close).props("flat no-caps")
                ui.button("Cambiar", on_click=lambda: aplicar(opciones_ui.value)).props("no-caps")
        dialogo.open()

    def _dialogo_texto(self, clave: str, titulo: str, actual: str) -> None:
        with ui.dialog() as dialogo, ui.card().classes("p-5 gap-3 w-[440px]"):
            ui.label(titulo).classes("tpi-titulo text-base")
            campo = ui.textarea(value=actual).props("outlined autogrow").classes("w-full")
            ui.label("Se lo manda al guion tal como lo escribiste, sin que la IA lo cambie.").classes(
                "tpi-ayuda text-xs"
            )
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.button(
                    "Cambiar", on_click=lambda: self._guardar(clave, str(campo.value or ""), dialogo)
                ).props("no-caps")
                ui.button("Que lo escriba la IA", on_click=lambda: self._guardar(clave, "", dialogo)).props(
                    "flat no-caps"
                )
                ui.button("Mejor no", on_click=dialogo.close).props("flat no-caps")
        dialogo.open()

    def _guardar(self, clave: str, texto: str, dialogo) -> None:
        self.cambios[clave] = texto.strip()
        self._visto = None
        dialogo.close()
        self._pintar()

    # ── retomar al recargar ─────────────────────────────────────────────────────────────

    def _reanudar(self) -> None:
        """Se recargó la pestaña con un video a medio hacer: la tarjeta se pone a mirarlo otra vez."""
        t = TAREAS.actual
        if t is None or not t.nombre.startswith(PROPIOS):
            return
        self.zona_resultado.clear()
        self.zona_resultado.set_visibility(False)
        self.zona_trabajo.set_visibility(True)
        self.boton_cancelar.set_visibility(not t.terminada)
        self._avance(t)
        if not t.terminada:
            self.mio = True
            self._abloquear(True)
