"""El Estudio: la pantalla única del panel (la ruta «/»).

Tres zonas, de arriba abajo en la columna principal y el muro de videos al costado:

① La idea: el ejercicio, el nivel y el tipo de contenido (Paso a paso, Error, Mito, Dato, Reto).
② Revisa el guion: el gancho (y sus alternativas), el dibujo de cada paso (ver, cambiar, quitar), el
   cierre del video y el llamado del texto de la publicación. Nada se escribe a mano en YAML.
③ Tus videos: el que se está creando, con su avance en vivo, y los últimos, para verlos y copiar
   sus textos.

Escribir un guion no ocupa la fila de trabajos (se puede escribir el próximo mientras un video se
crea); hacer el video sí, porque usa todo el computador. La lógica vive en ``panel/estudio.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from nicegui import background_tasks, run, ui

from ...errores import ErrorMotor
from ...guion import Guion, cargar_guion
from ...niveles import NIVELES
from .. import biblioteca, didactica_ui, estudio, miniaturas, qc
from ..comun import cabecera, piel_de_la_pagina, url_medio
from ..tareas import TAREAS, consultar

NIVEL_IA = "Que lo decida la IA"
_PAUSA = re.compile(r"<break[^>]*/?>")


def _boton(*args: Any, **kwargs: Any) -> ui.button:
    """Un botón sin el color de Quasar: así manda la clase de la piel (ámbar, tenue…)."""
    kwargs.setdefault("color", None)
    return ui.button(*args, **kwargs)


def _sin_pausas(voz: str) -> str:
    """La voz como se lee: sin las marcas de pausa (<break time="1s"/>) que usa el motor."""
    return " ".join(_PAUSA.sub(" ", voz).split())


def _rotulo(numero: str, texto: str, activa: bool = True) -> None:
    with ui.row().classes("items-center gap-3"):
        ui.label(numero).classes("tpi-zona" + ("" if activa else " tpi-zona-apagada"))
        ui.label(texto).classes("text-lg font-semibold")


def _consola(clases: str = "") -> ui.card:
    return ui.card().props("flat").classes(f"tpi-consola w-full p-6 gap-5 {clases}")


def _copiar(texto: str, que: str) -> None:
    ui.clipboard.write(texto)
    ui.notify(f"{que}: copiado.", type="positive")


def _tema_de(guion: Guion) -> str:
    """El estilo con que saldrá el video (para dibujar las miniaturas con sus colores)."""
    try:
        from ...config import cargar_marca
        from ...temas import estilo_del_guion

        return estilo_del_guion(guion, cargar_marca()).clave
    except Exception:  # una miniatura con otros colores no justifica botar la pantalla
        return "consola_pasos"


def _cierre_por_defecto() -> str:
    try:
        from ...config import cargar_marca

        return cargar_marca().cierre.texto
    except Exception:
        return ""


class Estudio:
    def __init__(self, guion: str | None) -> None:
        atajos = estudio.cargar_atajos()
        self.idea = ""
        self.nivel = atajos["nivel"] or NIVEL_IA
        self.tipo = atajos["tipo"]
        self.intenciones: list[str] = []  # «Qué enseña»; vacío = lo decide la IA
        self.objetivo = ""
        self.recientes: list[dict[str, Any]] = atajos["recientes"]
        self.escribiendo = False
        self.error_idea: ErrorMotor | None = None
        self.ruta: Path | None = None
        self.guion: Guion | None = None
        self.error_guion: str | None = None
        self.ocupado_paso: int | None = None  # el paso cuyo dibujo está armando la IA
        self._firma_tarea: tuple = ()
        # Un trabajo que ya había terminado al abrir la pantalla no cuenta como «recién terminado»:
        # si no, el primer tic redibujaba el muro y la revisión enteros (y relanzaba las miniaturas).
        anterior = TAREAS.actual
        self._fin_visto: float | None = anterior.fin if anterior is not None and anterior.terminada else None
        self._miniaturas: dict[str, str | None] = {}  # visual (JSON) → url del PNG; None = no se pudo
        if guion:
            self._cargar(Path(guion), con_url=False)  # la URL ya trae el guion

    # ----------------------------------------------------------------------------------
    # La página
    # ----------------------------------------------------------------------------------

    def render(self) -> None:
        piel_de_la_pagina()
        cabecera(con_menu=False, estudio=True)
        with ui.element("div").classes("tpi-estudio tpi-columnas w-full max-w-7xl mx-auto px-6 py-8"):
            with ui.column().classes("w-full gap-6 min-w-0"):
                self.composer()
                self.revision()
            with ui.column().classes("tpi-costado w-full gap-4 min-w-0"):
                self.en_curso()
                self.muro()
        ui.timer(0.7, self._mirar_tarea)

    # ----------------------------------------------------------------------------------
    # ① La idea
    # ----------------------------------------------------------------------------------

    @ui.refreshable_method
    def composer(self) -> None:
        with _consola():
            _rotulo("1", "¿Qué video hacemos?")
            area = (
                ui.textarea(
                    label="El ejercicio o la idea",
                    placeholder=estudio.TIPOS[self.tipo].ejemplo,
                    value=self.idea,
                )
                .props("outlined autogrow dark color=amber")
                .classes("tpi-idea w-full")
            )
            area.bind_value(self, "idea")
            area.on("keydown.ctrl.enter", self._escribir)
            area.on("keydown.meta.enter", self._escribir)

            with ui.row().classes("w-full items-end gap-4 wrap"):
                ui.select([NIVEL_IA, *NIVELES], label="Nivel", value=self.nivel).props(
                    "outlined dark color=amber options-dark"
                ).classes("w-64").bind_value(self, "nivel")
            with ui.column().classes("w-full gap-2"):
                ui.label("Tipo de contenido").classes("tpi-rotulo")
                with ui.row().classes("gap-2 wrap").props('role="radiogroup" aria-label="Tipo de contenido"'):
                    for clave, tipo in estudio.TIPOS.items():
                        activo = clave == self.tipo
                        _boton(tipo.nombre, on_click=lambda _e=None, c=clave: self._elegir_tipo(c)).props(
                            f'flat no-caps role="radio" aria-checked="{str(activo).lower()}"'
                        ).classes("tpi-chip-tipo" + (" activo" if activo else ""))
                ui.label(estudio.TIPOS[self.tipo].ayuda).classes("tpi-sobrio text-sm")
            with ui.row().classes("w-full items-end gap-4 wrap"):
                ui.select(
                    estudio.INTENCIONES_UI, label="Qué enseña (opcional)", multiple=True, value=self.intenciones
                ).props("outlined dark color=amber options-dark use-chips").classes("w-64").bind_value(
                    self, "intenciones"
                )
                ui.input(
                    "Qué aprenderá (si eliges qué enseña)", placeholder="Ej. que el volumen crece por 8"
                ).props("outlined dark color=amber").classes("grow").bind_value(self, "objetivo")

            if self.recientes:
                with ui.column().classes("w-full gap-2"):
                    ui.label("Lo último que hiciste").classes("tpi-rotulo")
                    with ui.row().classes("gap-2 wrap"):
                        for atajo in self.recientes:
                            _boton(
                                estudio.resumen_atajo(atajo),
                                on_click=lambda _e=None, a=atajo: self._usar_atajo(a),
                            ).props("flat no-caps dense").classes("tpi-atajo").tooltip(atajo["idea"])

            if self.error_idea is not None:
                with ui.column().classes("tpi-aviso-error w-full gap-1 tpi-entra"):
                    ui.label(self.error_idea.mensaje).classes("font-semibold")
                    if self.error_idea.ayuda:
                        ui.label(str(self.error_idea.ayuda)).classes("tpi-sobrio text-sm")
                    _boton("Reintentar", icon="refresh", on_click=self._escribir).props(
                        "flat no-caps dense"
                    ).classes("tpi-ambar -ml-2")

            with ui.row().classes("w-full items-center gap-4"):
                boton = (
                    _boton(
                        "Escribiendo el guion…" if self.escribiendo else "Escribir el guion",
                        icon=None if self.escribiendo else "auto_awesome",
                        on_click=self._escribir,
                    )
                    .props("no-caps unelevated" + (" loading" if self.escribiendo else ""))
                    .classes("tpi-boton-principal")
                )
                boton.set_enabled(not self.escribiendo)
                self.estado_idea = ui.label(
                    "La IA tarda cerca de un minuto." if self.escribiendo else "Ctrl + Enter también sirve."
                ).classes("tpi-sobrio text-sm")

    def _elegir_tipo(self, clave: str) -> None:
        self.tipo = clave
        self.composer.refresh()

    def _usar_atajo(self, atajo: dict[str, Any]) -> None:
        self.idea = atajo["idea"]
        self.nivel = atajo.get("nivel") or NIVEL_IA
        self.tipo = atajo["tipo"]
        self.composer.refresh()

    async def _escribir(self) -> None:
        if self.escribiendo:
            return
        nivel = None if self.nivel == NIVEL_IA else self.nivel
        try:
            contenido = estudio.contenido_pedido(self.intenciones, self.objetivo)
            args = estudio.args_redactar(self.idea, nivel, self.tipo, contenido)
        except ErrorMotor as e:
            ui.notify(e.mensaje, type="warning")
            return
        self.recientes = estudio.recordar(self.idea, nivel, self.tipo)["recientes"]
        self.escribiendo, self.error_idea = True, None
        self.composer.refresh()
        hallado: dict[str, Any] = {}

        def al_evento(evento: dict[str, Any]) -> None:
            if evento.get("etapa") == "guion":
                hallado.update(evento)
            elif evento.get("detalle"):
                try:
                    self.estado_idea.text = str(evento["detalle"])
                except Exception:  # la pestaña se cerró: el guion se escribe igual
                    pass

        try:
            await consultar(args, segundos=900, al_evento=al_evento)
            if not hallado.get("guion"):
                raise ErrorMotor("La IA no entregó el guion.", ayuda="Reintenta en un momento.")
        except ErrorMotor as e:
            self.error_idea = e
        finally:
            self.escribiendo = False
        self.composer.refresh()
        if hallado.get("guion"):
            self._cargar(Path(str(hallado["guion"])))
            pendientes = hallado.get("pendientes") or []
            if pendientes:
                ui.notify(
                    f"La IA dejó {len(pendientes)} observación(es): revísalas antes del video.",
                    type="warning",
                )
            self.revision.refresh()

    # ----------------------------------------------------------------------------------
    # ② Revisa el guion
    # ----------------------------------------------------------------------------------

    def _cargar(self, ruta: Path, con_url: bool = True) -> None:
        try:
            ruta = estudio.ruta_de_guion(ruta)
            self.guion = cargar_guion(ruta)
            self.ruta, self.error_guion = ruta, None
        except ErrorMotor as e:
            self.ruta, self.guion = None, None
            self.error_guion = f"{e.mensaje} {e.ayuda or ''}".strip()
        if (
            con_url and self.ruta is not None
        ):  # así recargar la pestaña (o guardarla de favorita) vuelve a este mismo guion
            ui.run_javascript(f"history.replaceState(null, '', '/?guion={quote(str(ruta))}')")

    def _cambiar(self, funcion: Any, *args: Any, aviso: str = "Guardado.") -> None:
        """Aplica un cambio al guion; si no vale, el archivo no se toca y se explica por qué."""
        if self.ruta is None:
            return
        try:
            self.guion = funcion(self.ruta, *args)
        except ErrorMotor as e:
            ui.notify(f"{e.mensaje} {e.ayuda or ''}".strip(), type="negative", multi_line=True)
            return
        ui.notify(aviso, type="positive")
        self.revision.refresh()

    @ui.refreshable_method
    def revision(self) -> None:
        g = self.guion
        with _consola("tpi-entra" if g else ""):
            _rotulo("2", "Revisa el guion", activa=g is not None)
            if self.error_guion:
                with ui.column().classes("tpi-aviso-error w-full gap-1"):
                    ui.label("No pude leer ese guion.").classes("font-semibold")
                    ui.label(self.error_guion).classes("tpi-sobrio text-sm")
                return
            if g is None or self.ruta is None:
                ui.label(
                    "Aquí aparece el guion para que elijas el gancho, revises los dibujos y el cierre "
                    "antes de hacer el video."
                ).classes("tpi-sobrio")
                return
            tipo = estudio.TIPOS[estudio.tipo_de_molde(g.molde)]
            with ui.column().classes("w-full gap-1"):
                ui.label(g.titulo).classes("text-xl font-semibold")
                detalle = " · ".join(p for p in (tipo.nombre, g.nivel or "", g.etiqueta_materia) if p)
                ui.label(f"{detalle} · {len(g.pasos)} pasos").classes("tpi-sobrio text-sm")
            ficha = qc.ficha(self.ruta)
            didactica_ui.tarjeta_contenido(ficha.contenido)
            didactica_ui.tarjeta_herramientas(self.ruta, ficha.recursos, self._recargar_didactica)
            self._ganchos(g)
            self._pasos(g)
            self._cierres(g, tipo)
            self._hacer_video(g)

    def _recargar_didactica(self) -> None:
        if self.ruta is not None:
            self._cargar(self.ruta, con_url=False)
        self.revision.refresh()

    def _ganchos(self, g: Guion) -> None:
        with ui.column().classes("w-full gap-2"):
            ui.label("El gancho · lo primero que se ve y se escucha").classes("tpi-rotulo")
            with ui.column().classes("w-full gap-2").props('role="radiogroup" aria-label="Gancho"'):
                for n, gancho in enumerate([g.gancho, *g.gancho_variantes], 1):
                    elegido = n == 1
                    fila = ui.element("button").classes("tpi-opcion" + (" elegida" if elegido else ""))
                    fila.props(f'type="button" role="radio" aria-checked="{str(elegido).lower()}"')
                    if not elegido:
                        fila.on(
                            "click",
                            lambda _e=None, k=n: self._cambiar(
                                estudio.usar_gancho, k, aviso="Gancho cambiado."
                            ),
                        )
                    with fila, ui.row().classes("w-full items-center gap-3 no-wrap"):
                        ui.icon("radio_button_checked" if elegido else "radio_button_unchecked").classes(
                            "tpi-ambar" if elegido else "tpi-sobrio"
                        )
                        ui.label(gancho.texto).classes("flex-1 text-base")
                        if elegido:
                            ui.label("En el video").classes("tpi-ambar text-xs")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                propio = (
                    ui.input(label="O escribe el tuyo", placeholder="Máx. 10 palabras, con el número clave")
                    .props(f"outlined dense dark color=amber maxlength={estudio.LARGO_GANCHO} counter")
                    .classes("flex-1")
                )

                def usar_propio() -> None:
                    if propio.value.strip():
                        self._cambiar(
                            estudio.escribir_gancho, propio.value, aviso="Gancho nuevo en el video."
                        )

                propio.on("keydown.enter", usar_propio)
                _boton("Usar", on_click=usar_propio).props("flat no-caps").classes("tpi-ambar")

    def _pasos(self, g: Guion) -> None:
        tema = _tema_de(g)
        with ui.column().classes("w-full gap-2"):
            ui.label("Los pasos y sus dibujos").classes("tpi-rotulo")
            for n, paso in enumerate(g.pasos, 1):
                with ui.element("div").classes("tpi-paso w-full" + (" tpi-paso-error" if paso.error else "")):
                    ui.label(str(n)).classes("tpi-num-paso")
                    with ui.column().classes("gap-1 min-w-0"):
                        titulo = paso.nota or ("Error típico" if paso.error else f"Paso {n}")
                        with ui.row().classes("items-center gap-2"):
                            ui.label(titulo).classes("font-semibold")
                            if paso.error:
                                ui.label("ERROR").classes("tpi-rojo text-xs font-bold")
                        ui.label(_sin_pausas(paso.voz)).classes("tpi-sobrio text-sm line-clamp-3")
                        self._acciones_dibujo(g, n)
                    self._cuadro(paso, n, tema)

    def _acciones_dibujo(self, g: Guion, n: int) -> None:
        paso = g.pasos[n - 1]
        tiene = paso.visual is not None
        armando = self.ocupado_paso == n
        with ui.row().classes("items-center gap-1 -ml-2 mt-1"):
            if armando:
                ui.spinner(size="sm").classes("tpi-ambar ml-2")
                ui.label("La IA está armando el dibujo…").classes("tpi-ambar text-sm")
                return
            ui.label(estudio.nombre_dibujo(paso.visual.tipo if tiene else None)).classes(
                "text-sm ml-2 mr-2" + ("" if tiene else " tpi-sobrio")
            )
            with (
                _boton("Cambiar" if tiene else "Agregar dibujo", icon="swap_horiz" if tiene else "add")
                .props("flat dense no-caps")
                .classes("tpi-ambar")
            ):
                with ui.menu().props("dark").classes("tpi-consola"):
                    for op in estudio.animaciones_sugeridas(g, n):
                        ui.menu_item(
                            op.nombre, on_click=lambda _e=None, k=n, d=op.dibujo: self._redibujar(k, d)
                        )
            if tiene:
                actual = paso.visual.tamano
                with (
                    _boton(f"Tamaño: {estudio.TAMANOS[actual]}", icon="aspect_ratio")
                    .props("flat dense no-caps")
                    .classes("tpi-sobrio")
                ):
                    with ui.menu().props("dark").classes("tpi-consola"):
                        for clave, nombre in estudio.TAMANOS.items():
                            ui.menu_item(
                                ("✓ " if clave == actual else "") + nombre,
                                on_click=lambda _e=None, k=n, t=clave, nm=nombre: self._cambiar(
                                    estudio.cambiar_tamano, k, t, aviso=f"Paso {k}: dibujo {nm.lower()}."
                                ),
                            )
                _boton(
                    "Quitar",
                    icon="close",
                    on_click=lambda _e=None, k=n: self._cambiar(
                        estudio.quitar_dibujo, k, aviso=f"Paso {k} sin dibujo."
                    ),
                ).props("flat dense no-caps").classes("tpi-sobrio")
            _boton("Editar", icon="edit", on_click=lambda _e=None, k=n: self._editar_paso(k)).props(
                "flat dense no-caps"
            ).classes("tpi-sobrio")

    def _cuadro(self, paso: Any, n: int, tema: str) -> None:
        caja = (
            ui.element("div")
            .classes("tpi-cuadro-paso")
            .props(f'aria-label="Dibujo del paso {n}"' if paso.visual else 'aria-hidden="true"')
        )
        if paso.visual is None:
            caja.classes("vacio")
            with caja:
                ui.icon("text_fields").classes("tpi-sobrio text-2xl")
            return
        visual = paso.visual.model_dump(exclude_none=True)
        clave = json.dumps({"v": visual, "t": tema}, sort_keys=True, ensure_ascii=False)
        if clave in self._miniaturas:
            self._pintar_cuadro(caja, self._miniaturas[clave], paso.visual.tipo)
            return
        with caja:
            ui.element("div").classes("tpi-esqueleto w-full h-full")

        async def dibujar() -> None:
            try:
                png = await run.io_bound(miniaturas.dibujar_miniatura, visual, tema)
                url = url_medio(png) or None
            except Exception:  # sin Manim, o un dibujo incompleto: se muestra el ícono del tipo
                url = None
            self._miniaturas[clave] = url
            try:
                caja.clear()
                self._pintar_cuadro(caja, url, paso.visual.tipo)
            except Exception:  # la revisión se redibujó mientras tanto: ese cuadro ya no existe
                pass

        background_tasks.create(dibujar(), name=f"miniatura paso {n}")

    @staticmethod
    def _pintar_cuadro(caja: ui.element, url: str | None, tipo: str) -> None:
        with caja:
            if url:
                ui.image(url).props(f'no-spinner alt="{estudio.nombre_dibujo(tipo)}"')
            else:
                with ui.column().classes("items-center gap-1 p-1"):
                    ui.icon("insights").classes("tpi-ambar text-2xl")
                    ui.label(estudio.nombre_dibujo(tipo)).classes(
                        "tpi-sobrio text-[10px] text-center leading-tight"
                    )

    async def _redibujar(self, n: int, dibujo: str) -> None:
        if self.ruta is None or self.ocupado_paso is not None:
            return
        self.ocupado_paso = n
        self.revision.refresh()
        try:
            await consultar(estudio.args_redibujar(self.ruta, n, dibujo), segundos=300)
            self.guion = cargar_guion(self.ruta)
            ui.notify(f"Paso {n}: dibujo nuevo.", type="positive")
        except ErrorMotor as e:
            ui.notify(f"{e.mensaje} {e.ayuda or ''}".strip(), type="negative", multi_line=True)
        finally:
            self.ocupado_paso = None
        self.revision.refresh()

    def _editar_paso(self, n: int) -> None:
        if self.guion is None:
            return
        paso = self.guion.pasos[n - 1]
        with (
            ui.dialog() as dialogo,
            ui.card().props("flat").classes("tpi-consola tpi-estudio p-6 gap-4 w-[560px] max-w-[95vw]"),
        ):
            ui.label(f"Paso {n}").classes("text-lg font-semibold")
            nota = (
                ui.input("Lo que dice la pantalla (corto)", value=paso.nota or "")
                .props("outlined dark color=amber maxlength=40 counter")
                .classes("w-full")
            )
            voz = (
                ui.textarea("Lo que dice la voz", value=paso.voz)
                .props("outlined autogrow dark color=amber")
                .classes("w-full")
            )
            if paso.tex:
                ui.label("La fórmula no cambia aquí; para eso está el editor completo.").classes(
                    "tpi-sobrio text-xs"
                )

            def guardar() -> None:
                dialogo.close()
                self._cambiar(estudio.cambiar_paso, n, nota.value, voz.value, aviso=f"Paso {n} guardado.")

            with ui.row().classes("w-full justify-end gap-2"):
                _boton("Cancelar", on_click=dialogo.close).props("flat no-caps").classes("tpi-sobrio")
                _boton("Guardar", on_click=guardar).props("no-caps unelevated").classes("tpi-boton-principal")
        dialogo.open()

    def _cierres(self, g: Guion, tipo: estudio.Tipo) -> None:
        actual_cierre = g.cierre.texto if g.cierre else _cierre_por_defecto()
        self._campo_con_sugerencias(
            "El cierre del video · lo último que se lee y se escucha",
            actual_cierre,
            tipo.cierres,
            estudio.LARGO_CIERRE,
            lambda texto: self._cambiar(estudio.cambiar_cierre, texto, aviso="Cierre guardado."),
        )
        self._campo_con_sugerencias(
            "El texto de la publicación · cómo invitas a comentar",
            g.llamado or "",
            tipo.llamados,
            estudio.LARGO_LLAMADO,
            lambda texto: self._cambiar(estudio.cambiar_llamado, texto, aviso="Llamado guardado."),
            vacio="Vacío = el de siempre («Te leo en los comentarios 👇»)",
        )

    def _campo_con_sugerencias(
        self,
        rotulo: str,
        actual: str,
        sugerencias: tuple[str, ...],
        largo: int,
        guardar: Any,
        vacio: str = "",
    ) -> None:
        with ui.column().classes("w-full gap-2"):
            ui.label(rotulo).classes("tpi-rotulo")
            with ui.row().classes("gap-2 wrap"):
                for s in sugerencias:
                    elegida = s == actual
                    _boton(s, on_click=lambda _e=None, t=s: guardar(t)).props("flat no-caps dense").classes(
                        "tpi-sugerencia" + (" elegida" if elegida else "")
                    )
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                campo = (
                    ui.input(placeholder=vacio or "Escribe el tuyo", value=actual)
                    .props(f"outlined dense dark color=amber maxlength={largo}")
                    .classes("flex-1")
                )
                boton = (
                    _boton("Guardar", on_click=lambda: guardar(campo.value))
                    .props("flat no-caps")
                    .classes("tpi-ambar")
                )
                boton.set_visibility(False)
                campo.on_value_change(lambda e: boton.set_visibility((e.value or "").strip() != actual))
                campo.on("keydown.enter", lambda: guardar(campo.value))

    def _hacer_video(self, g: Guion) -> None:
        ocupado = TAREAS.ocupado()
        with ui.row().classes("w-full items-center gap-4 pt-2 wrap"):
            principal = (
                _boton("Hacer video", icon="movie", on_click=lambda: self._lanzar_video(False))
                .props("no-caps unelevated")
                .classes("tpi-boton-principal")
            )
            principal.set_enabled(not ocupado)
            rapido = (
                _boton("Borrador rápido", icon="bolt", on_click=lambda: self._lanzar_video(True))
                .props("flat no-caps")
                .classes("tpi-ambar")
            )
            rapido.set_enabled(not ocupado)
            ui.link("Editor completo", f"/crear?guion={quote(str(self.ruta))}").classes("tpi-sobrio text-sm")
        ui.label(
            "Hay un video creándose: cuando termine, sigue este."
            if ocupado
            else "El video final trae su portada y los textos para publicar. Tarda unos minutos."
        ).classes("tpi-sobrio text-sm")

    def _lanzar_video(self, borrador: bool) -> None:
        if self.ruta is None or self.guion is None:
            return
        if TAREAS.ocupado():
            ui.notify("Ya hay un video creándose: espera a que termine.", type="warning")
            return
        nombre = f"{'Borrador' if borrador else 'Video'} · {self.guion.titulo}"
        try:
            TAREAS.lanzar(nombre, estudio.args_video(self.ruta, borrador))
        except ErrorMotor as e:
            ui.notify(e.mensaje, type="warning")
            return
        ui.notify("¡Manos a la obra! Mira el avance en «Tus videos».", type="positive")
        self.revision.refresh()
        self.en_curso.refresh()

    # ----------------------------------------------------------------------------------
    # ③ Tus videos
    # ----------------------------------------------------------------------------------

    def _mirar_tarea(self) -> None:
        t = TAREAS.actual
        # «reciente» entra en la firma: la tarjeta de «Listo» se esconde sola a los 30 s.
        firma = () if t is None else (id(t), t.etapa, round(t.avance * 100), t.terminada, t.reciente(30))
        if firma == self._firma_tarea:
            return
        self._firma_tarea = firma
        self.en_curso.refresh()
        if t is not None and t.terminada and t.fin != self._fin_visto:
            self._fin_visto = t.fin
            self.muro.refresh()
            if self.guion is not None:
                self.revision.refresh()  # el botón «Hacer video» vuelve a estar disponible

    @ui.refreshable_method
    def en_curso(self) -> None:
        t = TAREAS.actual
        if t is None or not t.args or t.args[0] not in ("crear", "publicar"):
            return
        if t.terminada and not t.reciente(30):
            return
        with _consola("gap-3 tpi-entra"):
            with ui.row().classes("w-full items-center justify-between no-wrap"):
                ui.label(t.nombre).classes("font-semibold truncate")
                if not t.terminada:
                    _boton(icon="stop", on_click=TAREAS.cancelar).props(
                        'flat round dense aria-label="Detener"'
                    ).classes("tpi-rojo").tooltip("Detener")
            if t.terminada:
                if t.ok:
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("Listo ✓").classes("tpi-verde font-semibold")
                        video = t.resultado.get("video")
                        if video and Path(str(video)).exists():
                            _boton(
                                "Ver", icon="play_arrow", on_click=lambda v=str(video): self._ver_ruta(v)
                            ).props("flat dense no-caps").classes("tpi-verde")
                    if t.resultado.get("kit_aviso"):
                        ui.label(str(t.resultado["kit_aviso"])).classes("tpi-ambar text-xs")
                elif t.cancelada:
                    ui.label("Detenido.").classes("tpi-sobrio")
                else:
                    with ui.column().classes("tpi-aviso-error w-full gap-1"):
                        ui.label((t.error or {}).get("mensaje") or "El video no salió.").classes(
                            "font-semibold"
                        )
                        if (t.error or {}).get("ayuda"):
                            ui.label(str(t.error["ayuda"])[:300]).classes("tpi-sobrio text-xs")
                        _boton(
                            "Reintentar", icon="refresh", on_click=lambda: self._reintentar(t.nombre, t.args)
                        ).props("flat no-caps dense").classes("tpi-ambar -ml-2")
                return
            ui.linear_progress(value=t.avance, show_value=False).props("rounded size=8px").classes("w-full")
            ui.label(f"{t.texto_etapa} · {round(t.avance * 100)} %").classes("tpi-sobrio text-sm")

    def _reintentar(self, nombre: str, args: list[str]) -> None:
        try:
            TAREAS.lanzar(nombre, args)
        except ErrorMotor as e:
            ui.notify(e.mensaje, type="warning")
        self.en_curso.refresh()

    @ui.refreshable_method
    def muro(self) -> None:
        with _consola("gap-4"):
            _rotulo("3", "Tus videos")
            try:
                videos = biblioteca.videos()[:12]
            except Exception as e:  # una carpeta rara en salida/ no puede dejar la pantalla en blanco
                with ui.column().classes("tpi-aviso-error w-full gap-1"):
                    ui.label("No pude leer tus videos.").classes("font-semibold")
                    ui.label(str(e)).classes("tpi-sobrio text-xs")
                    _boton("Reintentar", icon="refresh", on_click=self.muro.refresh).props(
                        "flat no-caps dense"
                    ).classes("tpi-ambar -ml-2")
                return
            if not videos:
                ui.label("Todavía no hay videos. El primero aparecerá aquí apenas lo hagas.").classes(
                    "tpi-sobrio text-sm"
                )
                return
            for video in videos:
                self._video(video)
            ui.link("Ver todos en la sala", "/videos").classes("tpi-sobrio text-sm")

    def _video(self, video: biblioteca.Video) -> None:
        with ui.row().classes("w-full gap-3 no-wrap items-start"):
            caja = ui.element("div").classes("tpi-cuadro-video")
            with caja:
                ui.element("div").classes("tpi-esqueleto w-full h-full")

            async def portada() -> None:
                try:
                    url = url_medio(await run.io_bound(biblioteca.miniatura, video)) or None
                except Exception:
                    url = None
                try:
                    caja.clear()
                    with caja:
                        if url:
                            ui.image(url).props(f'no-spinner alt="Portada de {video.titulo}"')
                        else:
                            ui.icon("movie").classes("tpi-sobrio text-2xl m-auto")
                except Exception:
                    pass

            background_tasks.create(portada(), name="portada del muro")
            with ui.column().classes("gap-1 min-w-0 flex-1"):
                ui.label(video.titulo).classes("font-semibold leading-tight line-clamp-2")
                calidad = "Final" if video.final else "Borrador"
                ui.label(f"{calidad} · {video.duracion:.0f} s").classes("tpi-sobrio text-xs")
                with ui.row().classes("gap-0 -ml-2"):
                    _boton("Ver", icon="play_arrow", on_click=lambda _e=None, v=video: self._ver(v)).props(
                        "flat dense no-caps"
                    ).classes("tpi-verde")
                    self._menu_textos(video)
                    if video.guion is not None:
                        _boton(
                            "Guion", icon="edit_note", on_click=lambda _e=None, v=video: self._abrir_guion(v)
                        ).props("flat dense no-caps").classes("tpi-sobrio").tooltip("Revisarlo arriba")

    @staticmethod
    def _ver_ruta(ruta: str) -> None:
        from .videos import ver_video

        ver_video(Path(ruta))

    @staticmethod
    def _ver(video: biblioteca.Video) -> None:
        from .videos import ver_video

        ver_video(video.principal)

    def _abrir_guion(self, video: biblioteca.Video) -> None:
        if video.guion is None:
            return
        self._cargar(video.guion)
        self.revision.refresh()
        ui.run_javascript("window.scrollTo({top: 0, behavior: 'smooth'})")

    def _menu_textos(self, video: biblioteca.Video) -> None:
        kit = video.kit
        with _boton("Textos", icon="content_copy").props("flat dense no-caps").classes("tpi-ambar"):
            with ui.menu().props("dark").classes("tpi-consola"):
                if not kit:
                    ui.menu_item(
                        "Armar los textos para publicar", on_click=lambda _e=None, v=video: self._armar_kit(v)
                    )
                    return
                etiquetas = " ".join(kit.get("hashtags") or [])
                opciones = (
                    ("TikTok", f"{kit.get('texto_tiktok', '')} {etiquetas}".strip()),
                    ("Instagram", f"{kit.get('texto_instagram', '')}\n\n{etiquetas}".strip()),
                    ("YouTube · título", kit.get("titulo_youtube", "")),
                    ("YouTube · descripción", f"{kit.get('descripcion_youtube', '')}\n\n{etiquetas}".strip()),
                    ("Solo los hashtags", etiquetas),
                )
                for nombre, texto in opciones:
                    if texto:
                        ui.menu_item(
                            f"Copiar {nombre}", on_click=lambda _e=None, n=nombre, t=texto: _copiar(t, n)
                        )

    def _armar_kit(self, video: biblioteca.Video) -> None:
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        try:
            TAREAS.lanzar(f"Textos · {video.titulo}", ["publicar", str(video.carpeta)])
        except ErrorMotor as e:  # otra pestaña lanzó algo en el mismo instante
            ui.notify(e.mensaje, type="warning")
            return
        self.en_curso.refresh()


def pagina(guion: str | None = None) -> None:
    Estudio(guion).render()
