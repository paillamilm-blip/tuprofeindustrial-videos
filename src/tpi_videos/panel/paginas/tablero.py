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

from nicegui import background_tasks, run, ui

from ... import cola
from ...errores import ErrorMotor
from ...niveles import CARRERA_CORTA, NIVELES, PUBLICOS
from .. import didactica_ui, qc
from ..comun import abrir_en_mac, cabecera, confirmar, piel_de_la_pagina, url_medio
from ..etapas import ACTIVA, ERROR, HECHA, Etapa, avance_total
from ..herramientas import HERRAMIENTAS, herramienta_de
from ..revision import AVISO, Chequeo, chequeos
from ..supervision import (
    COMPLETADOS,
    EN_RENDER,
    LANZAMIENTO,
    PENDIENTES,
    args_de_lote,
    columnas,
    lotes_por_producir,
)
from ..tareas import TAREAS

MAXIMO_LISTOS_A_LA_VISTA = 4  # la sala muestra lo reciente; el resto se abre con «Ver los listos»


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
    video_id = t.args[t.args.index("--video-id") + 1] if "--video-id" in t.args else None
    return {
        video_id or f"{lote_id}-{n}": {
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


def _volver_a_la_sala() -> None:
    """El camino de vuelta a la sala, arriba de las pantallas que salen de ella."""
    with ui.link(target="/cola").classes("tpi-enlace-cabecera self-start"):
        ui.icon("arrow_back").classes("text-xl")
        ui.label("Sala de producción")


def _resumen_sala(haciendo: list, espera: list, problemas: list, listos: list) -> str:
    """La frase bajo el título: «1 produciendo · 2 en espera · 5 listos» (solo lo que hay)."""
    partes = []
    if haciendo:
        partes.append(f"{len(haciendo)} produciendo")
    if espera:
        partes.append(f"{len(espera)} en espera")
    if problemas:
        partes.append(f"{len(problemas)} con problema" + ("" if len(problemas) == 1 else "s"))
    if listos:
        partes.append(f"{len(listos)} listo" + ("" if len(listos) == 1 else "s"))
    return " · ".join(partes)


def _chequeos(marcas: tuple[Chequeo, ...]) -> None:
    """Las marcas de un guion en una fila: verde si está bien, ámbar si conviene mirarlo, rojo si falla."""
    iconos = {HECHA: ("check_circle", "tpi-verde"), AVISO: ("error_outline", "tpi-ambar")}
    with ui.row().classes("w-full gap-2"):
        for m in marcas:
            icono, color = iconos.get(m.estado, ("cancel", "tpi-rojo"))
            with (
                ui.row()
                .classes("tpi-chequeo items-center no-wrap gap-2")
                .props(f'role="img" aria-label="{m.aria}"')
            ):
                ui.icon(icono).classes(f"{color} text-lg")
                ui.label(m.texto)


def _etapas(etapas: tuple[Etapa, ...]) -> None:
    """Las etapas de un video en fila: un check verde si está lista, un anillo con su % si trabaja."""
    with ui.element("div").classes("tpi-etapas"):
        for e in etapas:
            with (
                ui.element("div")
                .classes(f"tpi-etapa tpi-etapa-{e.estado}")
                .props(f'role="img" aria-label="{e.texto}"')
            ):
                marca = ui.element("div").classes(f"tpi-marca-etapa tpi-marca-{e.estado}")
                if e.estado == ACTIVA:
                    marca.style(f"--p: {e.porcentaje}")  # el anillo se llena hasta su %
                with marca:
                    if e.estado == HECHA:
                        ui.icon("check").classes("text-xl")
                    elif e.estado == ERROR:
                        ui.icon("priority_high").classes("text-xl")
                ui.label(e.nombre).classes("tpi-etapa-nombre")
                ui.label(f"{e.porcentaje} %").classes("tpi-etapa-pct")


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


class ParaHoy:
    """Un video al día: tres opciones del mismo nivel, una por materia, y un botón para crear la elegida."""

    def __init__(self, al_crear: Callable[[], None]) -> None:
        self.al_crear = al_crear
        self.nivel: str | None = None
        self.indice: dict[str, int] = {}

    def render(self) -> None:
        self.ancla = ui.element("div").classes("hidden")  # los relojes viven acá: la tarjeta se repinta
        self.tarjeta()

    @ui.refreshable_method
    def tarjeta(self) -> None:
        from ...config import cargar_marca
        from .. import para_hoy

        p = para_hoy.proponer(self.nivel, cargar_marca().publico.nivel)
        if self.nivel and p.nivel != self.nivel:  # eligió un nivel sin guiones: se muestra vacío, no otro
            p.nivel, p.opciones = self.nivel, {}
        with _consola():
            with ui.row().classes("w-full items-start justify-between gap-4 flex-wrap"):
                with ui.column().classes("gap-0"):
                    _rotulo("Para hoy · elige uno")
                    falta = ", ".join(para_hoy.nombre_categoria(c) for c in p.faltan())
                    if not p.nivel:
                        encabezado = "Elige un nivel"
                    elif falta:
                        encabezado = f"{p.nivel}: falta {falta}. Pídeselo a la IA o elige otro nivel."
                    else:
                        encabezado = f"Tres del mismo nivel ({p.nivel}), uno por materia."
                    ui.label(encabezado).classes("text-lg font-semibold")
                with ui.column().classes("gap-2 items-end"):
                    for clave, nombre in PUBLICOS.items():
                        with ui.row().classes("gap-2 items-center justify-end"):
                            ui.label(nombre).classes("tpi-sobrio text-xs")
                            for nivel in (n for n in NIVELES if para_hoy.publico(n) == clave):
                                self._chip(p, nivel)
            if p.hoy:
                ui.label(f"✓ Hoy ya elegiste «{p.hoy[0]}». Mañana, otro.").classes("tpi-verde text-sm")
            if not p.nivel:
                return
            with (
                ui.element("div")
                .classes("w-full grid gap-4")
                .style("grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))")
            ):
                for categoria in para_hoy.CATEGORIAS:
                    self._columna(categoria, p.opciones.get(categoria, []), p.nivel)

    def _chip(self, p: Any, nivel: str) -> None:
        from .. import para_hoy

        materias = p.niveles.get(nivel, set())
        completo = len(materias) == len(para_hoy.CATEGORIAS)
        falta = ", ".join(para_hoy.nombre_categoria(c) for c in p.faltan(nivel))
        texto = nivel.replace(" ingeniería", "") + ("" if completo else " · incompleto")
        _clic(
            ui.label(texto).classes(
                "tpi-hashtag rounded-lg px-3 py-1 text-sm"
                + (" tpi-ficha-elegida" if nivel == p.nivel else "")
            ),
            lambda n=nivel: self._elegir_nivel(n),
            "Las tres materias tienen guion de este nivel" if completo else f"Falta {falta}",
        )

    def _columna(self, categoria: str, opciones: list[Any], nivel: str) -> None:
        from .. import para_hoy

        i = self.indice.get(categoria, 0) % len(opciones) if opciones else 0
        o = opciones[i] if opciones else None
        with ui.column().classes("tpi-ficha w-full p-4 gap-2"):
            with ui.row().classes("gap-2 items-center"):
                ui.label(para_hoy.nombre_categoria(categoria)).classes(
                    f"tpi-insignia tpi-insignia-{categoria}"
                )
                if o is not None and o.carrera:
                    ui.label(CARRERA_CORTA[o.carrera]).classes("tpi-hashtag rounded-lg px-2 text-xs")
            if o is None:
                self._pedir(categoria, nivel)
                return
            _clic(
                ui.label(o.titulo).classes("font-semibold leading-snug rounded-lg px-2 -mx-2"),
                lambda: ui.navigate.to(f"/qc?guion={quote(str(o.ruta))}"),
                "Leer la ficha completa en QC",
            )
            detalle = " · ".join(x for x in (o.molde, _nombre_estilo(o.estilo.clave, _temas())) if x)
            ui.label(detalle).classes("tpi-sobrio text-xs")
            for razon in o.razones:
                ui.label(f"• {razon}").classes("tpi-sobrio text-xs leading-snug")
            VistaPrevia(o.ruta).render()
            with ui.row().classes("w-full items-center justify-between gap-2 pt-1"):
                if len(opciones) > 1:
                    ui.button(
                        color=None,
                        text=f"Otra ({i + 1}/{len(opciones)})",
                        icon="shuffle",
                        on_click=lambda c=categoria: self._otra(c),
                    ).props("flat dense no-caps").classes("tpi-sobrio")
                else:
                    ui.label("Única de este nivel").classes("tpi-sobrio text-xs")
                ui.button(
                    color=None, text="Crear este", icon="movie", on_click=lambda o=o: self._crear(o)
                ).classes("tpi-aprobar")

    def _pedir(self, categoria: str, nivel: str) -> None:
        """La materia sin guion en este nivel: la IA escribe uno con un tema de la malla, acá mismo."""
        from .. import para_hoy

        materia = {"matematicas": "matematica"}.get(categoria, categoria)
        args = ["completar-niveles", "--nivel", nivel, "--materia", materia, "--maximo", "1"]
        t = TAREAS.actual
        if t is not None and t.args == args and not t.terminada:
            ui.label(f"La IA está escribiendo… {t.detalle or t.texto_etapa}").classes("tpi-ambar text-sm")
            return
        ui.label(f"No hay guion de {para_hoy.nombre_categoria(categoria)} para {nivel}.").classes(
            "tpi-sobrio text-sm"
        )

        def pedir() -> None:
            if TAREAS.ocupado():
                ui.notify("El motor está ocupado: inténtalo cuando termine.", type="warning")
                return
            TAREAS.lanzar(f"Escribir {para_hoy.nombre_categoria(categoria)} · {nivel}", args)
            ui.notify("La IA está escribiendo el guion (1 o 2 minutos). Aparece acá solo.", type="info")
            self.tarjeta.refresh()

            def mirar() -> None:
                actual = TAREAS.actual
                if actual is None or actual.args != args or actual.terminada:
                    reloj.deactivate()
                    if actual is not None and actual.error:
                        ui.notify(f"No se pudo: {actual.error.get('mensaje', '')}", type="negative")
                    self.tarjeta.refresh()

            with self.ancla:
                reloj = ui.timer(2.0, mirar)

        ui.button(color=None, text="Pedírselo a la IA", icon="auto_awesome", on_click=pedir).props(
            "flat dense no-caps"
        ).classes("tpi-ambar -ml-2")

    def _elegir_nivel(self, nivel: str) -> None:
        self.nivel, self.indice = nivel, {}
        self.tarjeta.refresh()

    def _otra(self, categoria: str) -> None:
        self.indice[categoria] = self.indice.get(categoria, 0) + 1
        self.tarjeta.refresh()

    def _crear(self, o: Any) -> None:
        from ...cli import encolar_guion

        try:
            lote_id = encolar_guion(o.ruta)
            qc.aprobar(o.ruta, lote_id)
        except ErrorMotor as e:
            ui.notify(f"No pude crearlo: {e.mensaje}", type="negative")
            return
        en_marcha = lanzar_en_lote()
        ui.notify(
            f"«{o.titulo}» va a producción." + ("" if en_marcha else " Queda en la cola."), type="positive"
        )
        self.indice = {}
        self.tarjeta.refresh()
        self.al_crear()


class ColaDeProduccion:
    """La sala de producción en una sola pantalla: cada video con sus etapas, su % y su check."""

    def __init__(self, ir_a: Callable[[str], None]) -> None:
        self.ir_a = ir_a
        self.firma: tuple = ()

    def render(self) -> None:
        self.firma = self._firma()  # lo recién pintado no se repinta: un clic no cae sobre algo que se va
        with ui.column().classes("tpi-sala w-full mx-auto gap-8"):
            self.sala()
            self._idea_del_dia()
            with ui.row().classes("w-full justify-center gap-2"):
                for destino, texto, icono in (
                    ("/qc", "Aprobar guiones", "fact_check"),
                    ("/avanzado", "Herramientas avanzadas", "tune"),
                ):
                    with ui.link(target=destino).classes("tpi-enlace-cabecera"):
                        ui.icon(icono).classes("text-xl")
                        ui.label(texto)
        ui.timer(1.5, self._mirar)

    def _al_crear(self) -> None:
        self.firma = ()  # la ficha nueva aparece en la lista en el próximo vistazo

    def _mirar(self) -> None:
        # Se repinta solo si algo cambió: una pantalla que parpadea cansa la vista.
        firma = self._firma()
        if firma != self.firma:
            self.firma = firma
            self.sala.refresh()

    def _firma(self) -> tuple:
        datos = cola.cargar()
        vivo = _en_vivo()
        return (
            tuple(
                (
                    v.get("id"),
                    v.get("estado"),
                    round(float(v.get("avance") or 0), 2),
                    len(v.get("hitos") or {}),
                )
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

    def _idea_del_dia(self) -> None:
        """«Para hoy» queda a mano pero cerrado: la pantalla muestra primero lo que se está produciendo."""
        caja = ui.expansion(
            "Idea para hoy", icon="lightbulb", caption="Tres guiones del mismo nivel, uno por materia"
        ).classes("tpi-plegable w-full")
        armado = {"listo": False}

        def armar(abierto: bool) -> None:
            if not abierto or armado["listo"]:
                return
            armado["listo"] = True
            with caja:
                ParaHoy(self._al_crear).render()

        caja.on_value_change(lambda e: armar(bool(e.value)))

    @ui.refreshable_method
    def sala(self) -> None:
        datos = cola.cargar()
        fichas = columnas(datos, _en_vivo())
        haciendo = fichas[EN_RENDER]
        con_problemas = [f for f in fichas[PENDIENTES] if f.fallo]
        en_espera = [f for f in fichas[PENDIENTES] if not f.fallo]
        listos = fichas[COMPLETADOS]
        self._encabezado(datos, haciendo, en_espera, con_problemas, listos)
        if not (haciendo or en_espera or con_problemas or listos):
            if TAREAS.ocupado():
                self._tarea_suelta()
            else:
                self._vacia()
            return
        if not haciendo and TAREAS.ocupado():
            self._tarea_suelta()  # un trabajo que no es de la cola (escribir un guion, un video suelto)
        self._grupo("Produciendo ahora", haciendo, self._video)
        self._grupo("En espera", en_espera, self._video)
        self._grupo("Con problemas", con_problemas, self._video)
        self._grupo("Listos", listos[:MAXIMO_LISTOS_A_LA_VISTA], self._listo)
        if len(listos) > MAXIMO_LISTOS_A_LA_VISTA:
            ui.button(
                color=None,
                text=f"Ver los {len(listos)} listos",
                icon="expand_more",
                on_click=lambda: self._lista_de("Listos", listos),
            ).props("flat no-caps").classes("tpi-sobrio self-center")

    def _encabezado(
        self, datos: dict[str, Any], haciendo: list, espera: list, problemas: list, listos: list
    ) -> None:
        por_producir = len(lotes_por_producir(datos))
        por_revisar = len(qc.guiones())
        with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
            with ui.column().classes("gap-1"):
                ui.label("Sala de producción").classes("tpi-sala-titulo")
                ui.label(
                    _resumen_sala(haciendo, espera, problemas, listos) or "Sin videos por ahora."
                ).classes("tpi-sobrio")
            with ui.row().classes("items-center gap-3"):
                if TAREAS.ocupado():
                    _clic(
                        ui.button(color=None, icon="terminal").props("flat round").classes("tpi-sobrio"),
                        _dialogo_tarea,
                        "Ver el registro del motor",
                    ).props('aria-label="Ver el registro del motor"')
                    ui.button(color=None, text="Detener", icon="stop", on_click=self._detener).props(
                        "flat no-caps"
                    ).classes("tpi-rojo")
                boton = ui.button(
                    color=None, text="Producir videos", icon="play_arrow", on_click=self._lanzar
                ).classes("tpi-boton-principal")
                if LANZAMIENTO.activo or TAREAS.ocupado():
                    boton.text = "Produciendo…"
                    boton.disable()
                elif not por_producir:
                    boton.disable()
                    boton.tooltip("No hay videos esperando. Aprueba un guion para que llegue acá.")
        if por_revisar:
            texto = (
                "1 guion espera tu aprobación"
                if por_revisar == 1
                else f"{por_revisar} guiones esperan tu aprobación"
            )
            with _clic(
                ui.row().classes("tpi-video tpi-video-espera items-center justify-between no-wrap"),
                lambda: self.ir_a("qc"),
                "Leer y aprobar los guiones",
            ):
                with ui.row().classes("items-center gap-3 no-wrap"):
                    ui.icon("fact_check").classes("tpi-ambar text-2xl")
                    ui.label(texto)
                ui.icon("chevron_right").classes("tpi-sobrio")

    def _vacia(self) -> None:
        with ui.column().classes("tpi-video items-center gap-3 py-12"):
            ui.icon("movie").classes("tpi-sobrio text-4xl")
            ui.label("Todavía no hay videos en la sala").classes("text-lg font-semibold")
            ui.label("Crea uno en el Estudio y aparece acá con su avance.").classes("tpi-sobrio")
            ui.button(
                color=None, text="Crear un video", icon="edit_note", on_click=lambda: ui.navigate.to("/")
            ).classes("tpi-boton-principal")

    def _grupo(self, titulo: str, fichas: list, dibujar: Callable[[Any], None]) -> None:
        if not fichas:
            return
        with ui.column().classes("w-full gap-3"):
            _rotulo(f"{titulo} · {len(fichas)}")
            for ficha in fichas:
                dibujar(ficha)

    def _tarea_suelta(self) -> None:
        t = TAREAS.actual
        if t is None or t.terminada:
            return
        with _clic(
            ui.column().classes("tpi-video tpi-video-activo gap-3"),
            _dialogo_tarea,
            "Ver qué está haciendo el motor",
        ):
            ui.label(t.nombre).classes("text-lg font-semibold")
            ui.linear_progress(value=t.avance, show_value=False, color=None).props(
                "rounded size=6px"
            ).classes("w-full")
            ui.label(t.detalle or t.texto_etapa).classes("tpi-sobrio text-sm")

    def _video(self, f: Any) -> None:
        """Un video en la cola: su título, el avance total y sus cuatro etapas con % y check."""
        activo = f.estado in cola.ESTADOS_ACTIVOS
        clase = "tpi-video-activo" if activo else ("tpi-video-fallo" if f.fallo else "tpi-video-espera")
        with _clic(
            ui.column().classes(f"tpi-video {clase} gap-4"),
            lambda: self._detalle(f),
            "Ver el detalle y qué hacer",
        ):
            with ui.row().classes("w-full items-start justify-between no-wrap gap-4"):
                with ui.column().classes("gap-1"):
                    if f.tema:
                        _rotulo(f.tema)
                    ui.label(f.titulo).classes("text-lg font-semibold leading-snug")
                    texto = f.detalle if activo and f.detalle else f.texto_estado
                    ui.label(texto).classes("tpi-rojo text-sm" if f.fallo else "tpi-sobrio text-sm")
                if activo:
                    ui.label(f"{avance_total(f.etapas)} %").classes("tpi-total")
                else:
                    self._boton_borrar(lambda: self._quitar(f), "Quitar de la cola")
            if activo:
                ui.linear_progress(value=avance_total(f.etapas) / 100, show_value=False, color=None).props(
                    "rounded size=4px"
                ).classes("w-full")
            _etapas(f.etapas)
            if f.fallo and f.error:
                ui.label(str(f.error)).classes("tpi-sobrio text-xs")

    def _listo(self, f: Any) -> None:
        """Un video terminado: una línea con lo que se hace con él."""
        with _clic(
            ui.row().classes("tpi-video tpi-video-espera items-center justify-between no-wrap gap-4"),
            lambda: self._detalle(f),
            "Ver el detalle y qué hacer",
        ):
            with ui.row().classes("items-center gap-3 no-wrap"):
                ui.icon("check_circle").classes("tpi-verde text-2xl")
                with ui.column().classes("gap-0"):
                    ui.label(f.titulo).classes("font-semibold leading-snug")
                    ui.label(f"Listo · {f.tema}" if f.tema else "Listo").classes("tpi-sobrio text-xs")
            with ui.row().classes("gap-1 no-wrap items-center"):
                if f.video is not None:
                    ui.button(color=None, text="Ver", icon="play_circle").props("flat dense no-caps").classes(
                        "tpi-verde"
                    ).on("click.stop", lambda _e, v=f.video: _ver(v))
                    ui.button(color=None, text="Carpeta", icon="folder_open").props(
                        "flat dense no-caps"
                    ).classes("tpi-sobrio").on("click.stop", lambda _e, v=f.video: abrir_en_mac(v, True))
                self._boton_borrar(lambda: self._a_la_papelera(f), "Enviar a la Papelera")

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
            ui.label(f.texto_estado + (f" · {avance_total(f.etapas)} %" if activo else "")).classes(color)
            if f.estado != "listo":
                _etapas(f.etapas)
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
        """Saca ESTE video de la cola (los demás de su lote siguen). Los archivos que ya salieron no se tocan."""

        def si() -> None:
            try:
                cola.descartar_video(f.video_id)
            except ErrorMotor as e:
                ui.notify(e.mensaje, type="warning")
                return
            ui.notify("Quitado de la cola. Los archivos que ya salieron no se borran.", type="info")
            self.firma = ()

        confirmar(f"¿Quitar «{f.titulo}» de la cola?", si, "Sí, quitar")

    def _a_la_papelera(self, f: Any) -> None:
        """Un video terminado: sus archivos van a la Papelera (se recuperan desde Finder) y sale de la sala."""
        from .. import biblioteca

        if f.video is None:  # la cola lo recuerda pero los archivos ya no están: solo se quita de la lista
            self._quitar(f)
            return
        carpeta = f.video.parent.resolve()
        video = next((v for v in biblioteca.videos() if v.carpeta.resolve() == carpeta), None)
        if video is None:
            ui.notify("No encuentro los archivos de este video.", type="warning")
            return

        async def si() -> None:
            if TAREAS.ocupado():
                ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
                return
            try:
                await run.io_bound(biblioteca.borrar, video)
            except ErrorMotor as e:
                ui.notify(e.mensaje, type="negative")
                return
            try:
                cola.descartar_video(f.video_id)
            except ErrorMotor:
                pass  # los archivos ya están en la Papelera; la sala lo saca en cuanto la cola quede libre
            ui.notify("Video enviado a la Papelera. Puedes recuperarlo desde Finder.", type="positive")
            self.firma = ()

        confirmar(
            f"¿Enviar «{f.titulo}» y todos sus archivos a la Papelera? Puedes recuperarlos desde Finder.",
            si,
            "Enviar a la Papelera",
        )

    def _boton_borrar(self, accion: Callable[[], None], ayuda: str) -> None:
        """El tacho de un video: sin tocar la tarjeta (no abre el detalle) y siempre con confirmación."""
        ui.button(color=None, icon="delete").props(f'flat round dense aria-label="{ayuda}"').classes(
            "tpi-borrar tpi-sobrio"
        ).tooltip(ayuda).on("click.stop", lambda _e: accion())

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
        self.abiertos: set[str] = set()  # los plegables que la persona abrió
        # /qc?guion=…: otra pantalla («Mis videos», el editor) manda a elegir el estilo de un guion.
        if abrir and qc.guion_revisable(Path(abrir)):
            self.elegido = Path(abrir).resolve()
            self.todos = qc.estado(self.elegido) != qc.POR_REVISAR

    def render(self) -> None:
        with ui.column().classes("tpi-sala w-full mx-auto gap-6"):
            _volver_a_la_sala()
            self.lista()
            self.lectura()

    @ui.refreshable_method
    def lista(self) -> None:
        """El encabezado: cuántos hay, cuál toca leer y cómo moverse entre ellos."""
        rutas = [r.resolve() for r in qc.guiones(incluir_decididos=self.todos)]
        if self.elegido is None or self.elegido not in rutas:
            self.elegido = rutas[0] if rutas else None
        with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
            with ui.column().classes("gap-1"):
                ui.label("Aprobar guiones").classes("tpi-sala-titulo")
                if not rutas:
                    resumen = "Todo al día."
                elif self.todos:
                    resumen = f"{len(rutas)} guion" + ("" if len(rutas) == 1 else "es")
                else:
                    resumen = "1 por revisar" if len(rutas) == 1 else f"{len(rutas)} por revisar"
                ui.label(resumen).classes("tpi-sobrio")
            ui.switch("Ver todos", value=self.todos, on_change=self._cambiar_filtro).props(
                "dense color=amber"
            )
        propios = len(qc.con_estilo_propio())
        if propios:
            ui.button(
                color=None,
                text=f"{propios} con estilo propio · Todos al sugerido",
                icon="auto_awesome",
                on_click=lambda: confirmar(
                    f"¿Pasar los {propios} guiones con estilo propio al estilo sugerido para cada uno?",
                    self._todos_al_sugerido,
                    boton="Sí, todos al sugerido",
                ),
            ).props("flat no-caps").classes("tpi-ambar self-start").tooltip(
                "Cada guion queda con el estilo que le sugiere el motor (molde, dibujos, error, materia)"
            )
        if not rutas:
            self._al_dia()
            return
        posicion = rutas.index(self.elegido)
        with ui.row().classes("w-full items-center justify-between gap-3"):
            with ui.row().classes("items-center gap-1"):
                anterior = ui.button(
                    color=None, icon="chevron_left", on_click=lambda: self._elegir(rutas[posicion - 1])
                ).props('flat round aria-label="Guion anterior"')
                anterior.classes("tpi-sobrio")
                if posicion == 0:
                    anterior.disable()
                ui.label(f"{posicion + 1} de {len(rutas)}").classes("tpi-posicion")
                siguiente = ui.button(
                    color=None, icon="chevron_right", on_click=lambda: self._elegir(rutas[posicion + 1])
                ).props('flat round aria-label="Guion siguiente"')
                siguiente.classes("tpi-sobrio")
                if posicion == len(rutas) - 1:
                    siguiente.disable()
            ui.button(
                color=None, text="Ver la lista", icon="list", on_click=lambda: self._dialogo_lista(rutas)
            ).props("flat no-caps").classes("tpi-sobrio")

    def _al_dia(self) -> None:
        with ui.column().classes("tpi-video items-center gap-3 py-12"):
            ui.icon("task_alt").classes("tpi-verde text-4xl")
            ui.label("No hay guiones esperando aprobación").classes("text-lg font-semibold")
            ui.label("Los que escribe el Estudio o ./tpi redactar aparecen acá solos.").classes("tpi-sobrio")
            ui.button(
                color=None,
                text="Volver a la sala",
                icon="dashboard",
                on_click=lambda: ui.navigate.to("/cola"),
            ).classes("tpi-boton-principal")

    def _dialogo_lista(self, rutas: list[Path]) -> None:
        with (
            ui.dialog() as dialogo,
            ui.card().props("flat").classes("tpi-consola p-8 gap-4 w-[560px] max-w-[95vw]"),
        ):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Guiones").classes("text-lg font-semibold")
                ui.button(color=None, icon="close", on_click=dialogo.close).props(
                    'flat round aria-label="Cerrar"'
                ).classes("tpi-sobrio")
            for ruta in rutas[:40]:
                estado = qc.estado(ruta)
                titulo, categoria = _resumen_de(ruta)
                elegida = " tpi-ficha-elegida" if ruta == self.elegido else ""
                with _clic(
                    ui.column().classes(f"tpi-ficha w-full p-4 gap-1{elegida}"),
                    lambda r=ruta: (dialogo.close(), self._elegir(r)),
                    "Leer este guion",
                ):
                    if categoria:
                        ui.label(NOMBRES_CATEGORIA[categoria]).classes(
                            f"tpi-insignia tpi-insignia-{categoria}"
                        )
                    ui.label(titulo).classes("font-semibold leading-snug")
                    color = {qc.APROBADO: "tpi-verde", qc.RECHAZADO: "tpi-rojo"}.get(estado, "tpi-celeste")
                    ui.label(qc.NOMBRES[estado]).classes(f"{color} text-xs")
        dialogo.open()

    def _todos_al_sugerido(self) -> None:
        cambiados = qc.todos_al_sugerido()
        ui.notify(f"Listo: {len(cambiados)} guiones quedaron con su estilo sugerido.", type="positive")
        self.lista.refresh()
        self.lectura.refresh()

    def _cambiar_filtro(self, e: Any) -> None:
        self.todos = bool(e.value)
        self.lista.refresh()
        self.lectura.refresh()

    def _elegir(self, ruta: Path) -> None:
        self.elegido = ruta
        self.lista.refresh()
        self.lectura.refresh()

    def _caja(self, clave: str, titulo: str, icono: str, subtitulo: str | None = None) -> ui.expansion:
        """Un plegable que recuerda si estaba abierto: al refrescar la lectura no se vuelve a cerrar."""
        caja = ui.expansion(titulo, icon=icono, caption=subtitulo, value=clave in self.abiertos).classes(
            "tpi-plegable w-full"
        )
        caja.on_value_change(lambda e, c=clave: self.abiertos.add(c) if e.value else self.abiertos.discard(c))
        return caja

    @ui.refreshable_method
    def lectura(self) -> None:
        if self.elegido is None:
            return
        f = qc.ficha(self.elegido)
        temas = _temas()
        _, categoria = _resumen_de(f.ruta)
        marcas = chequeos(
            error=f.error,
            voces=len(f.voces),
            tiene_metadatos=bool(f.metadatos),
            estilo_disponible=None if f.estilo is None else f.estilo.clave in temas,
            observaciones=len(f.observaciones),
        )
        with ui.column().classes("tpi-video gap-5"):
            with ui.row().classes("w-full items-start justify-between no-wrap gap-4"):
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-3"):
                        if categoria:
                            ui.label(NOMBRES_CATEGORIA[categoria]).classes(
                                f"tpi-insignia tpi-insignia-{categoria}"
                            )
                        _rotulo(" · ".join(x for x in (f.carrera, f.nivel, qc.NOMBRES[f.estado]) if x))
                    ui.label(f.titulo).classes("text-2xl font-semibold leading-tight")
                _clic(
                    ui.button(color=None, icon="edit").props('flat round aria-label="Abrir en el editor"'),
                    lambda: _abrir_editor(f.ruta),
                    "Abrir este guion en el editor",
                ).classes("tpi-sobrio")
            if f.error:
                ui.label(f"Este guion no pasa la validación: {f.error}").classes("tpi-rojo text-sm")
            for nota in f.observaciones:
                ui.label(f"⚠ {nota}").classes("tpi-ambar text-sm")
            _chequeos(marcas)
            self._voz(f)
            if f.estado == qc.POR_REVISAR:
                VistaPrevia(f.ruta).render()
            if f.estilo is not None:
                self._estilo(f)
        if f.estilo is not None:
            with self._caja(
                "ensena", "Qué enseña y herramientas", "school", "Contenido y recursos didácticos"
            ):
                with ui.column().classes("w-full gap-4 p-4"):
                    with _consola():
                        didactica_ui.tarjeta_contenido(f.contenido)
                    with _consola():
                        didactica_ui.tarjeta_herramientas(f.ruta, f.recursos, self.lectura.refresh)
        self._redes(f)
        with self._caja("tecnico", "Detalles técnicos", "code"):
            with ui.column().classes("w-full gap-2 p-4"):
                for linea in f.tecnico:
                    _clic(
                        ui.label(linea).classes("tpi-sobrio text-sm font-mono rounded-lg px-2"),
                        lambda x=linea: _copiar(x, "Línea"),
                        "Copiar",
                    )
                ui.code(f.yaml, language="yaml").classes("tpi-codigo w-full text-xs")
        with ui.row().classes("tpi-barra-accion w-full items-center gap-4"):
            borrar = (
                ui.button(color=None, text="Borrar guion", icon="delete", on_click=lambda: self._borrar(f))
                .props("flat no-caps")
                .classes("tpi-borrar tpi-sobrio mr-auto")
            )
            if f.estado == qc.APROBADO:
                borrar.disable()
                borrar.tooltip("Ya está en la cola: quita su video de la Sala de producción primero.")
            else:
                borrar.tooltip("Lo manda a la Papelera. Puedes recuperarlo desde Finder.")
            ui.button(
                color=None, text="Rechazar o editar", icon="close", on_click=lambda: self._rechazar(f)
            ).classes("tpi-rechazar")
            aprobar = ui.button(
                color=None, text="Aprobar y enviar a la cola", icon="check", on_click=lambda: self._aprobar(f)
            ).classes("tpi-aprobar")
            if not f.aprobable or f.estado == qc.APROBADO:
                aprobar.disable()

    def _voz(self, f: qc.Ficha) -> None:
        _rotulo("Lo que dice la voz · toca una línea para copiarla")
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

    def _redes(self, f: qc.Ficha) -> None:
        with self._caja("redes", "Para redes", "share", "Título, descripción y hashtags · toca para copiar"):
            with ui.column().classes("w-full gap-3 p-4"):
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

    # ── El estilo del video: el único lugar del panel donde se elige ───────────────────────

    def _estilo(self, f: qc.Ficha) -> None:
        estilo, sugerido = f.estilo, f.sugerido
        temas = _temas()
        elegido = estilo.origen == "guion"
        with ui.row().classes("tpi-ficha w-full p-3 gap-4 no-wrap items-center"):
            _muestra(estilo.clave, temas, ancho=48)
            with ui.column().classes("gap-0 min-w-0 grow"):
                _rotulo("Estilo del video · " + ("elegido por ti" if elegido else "★ sugerido"))
                ui.label(_nombre_estilo(estilo.clave, temas)).classes("font-semibold")
                ui.label(estilo.razon).classes("tpi-sobrio text-xs")
                if elegido and sugerido is not None and sugerido.clave != estilo.clave:
                    ui.label(
                        f"El sugerido sería {_nombre_estilo(sugerido.clave, temas)}: {sugerido.razon}"
                    ).classes("tpi-sobrio text-xs")
                if estilo.clave not in temas:
                    ui.label("Ese estilo no está en este equipo: el video no se podrá crear.").classes(
                        "tpi-rojo text-xs"
                    )
            ui.button(
                color=None, text="Cambiar", icon="palette", on_click=lambda: self._dialogo_estilo(f)
            ).props("flat no-caps").classes("tpi-ambar")

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

    def _borrar(self, f: qc.Ficha) -> None:
        """Manda el guion a la Papelera (recuperable desde Finder) y pasa al siguiente."""

        async def si() -> None:
            try:
                await run.io_bound(qc.borrar_guion, f.ruta)
            except ErrorMotor as e:
                ui.notify(e.mensaje, type="negative")
                return
            ui.notify("Guion enviado a la Papelera. Puedes recuperarlo desde Finder.", type="positive")
            self.elegido = None
            self.lista.refresh()
            self.lectura.refresh()
            self.al_aprobar()

        confirmar(
            f"¿Enviar el guion «{f.titulo}» a la Papelera? Puedes recuperarlo desde Finder.",
            si,
            "Enviar a la Papelera",
        )

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


class Herramientas:
    """«Avanzado» en una sola pantalla: cinco tarjetas y, al tocar una, esa herramienta sola (con su «volver»)."""

    def __init__(self, abrir: str | None = None, modo: str = "uno", guion: str | None = None) -> None:
        self.actual = herramienta_de(abrir)
        self.modo, self.guion = modo, guion

    def render(self) -> None:
        with ui.column().classes("w-full gap-6"):
            self.pantalla()

    def _abrir(self, clave: str | None) -> None:
        self.actual = clave
        self.pantalla.refresh()

    @ui.refreshable_method
    def pantalla(self) -> None:
        if self.actual is None:
            self._tarjetas()
        else:
            self._herramienta(self.actual)

    def _tarjetas(self) -> None:
        with ui.column().classes("tpi-sala w-full mx-auto gap-6"):
            _volver_a_la_sala()
            with ui.column().classes("gap-1"):
                ui.label("Herramientas").classes("tpi-sala-titulo")
                ui.label("Lo manual, para cuando lo necesites.").classes("tpi-sobrio")
            with (
                ui.element("div")
                .classes("w-full grid gap-4")
                .style("grid-template-columns: repeat(auto-fit, minmax(260px, 1fr))")
            ):
                for clave, (nombre, icono, ayuda) in HERRAMIENTAS.items():
                    with (
                        _clic(
                            ui.column().classes("tpi-herramienta tpi-clic"),
                            lambda c=clave: self._abrir(c),
                            ayuda,
                        )
                        .props(f'tabindex=0 role=button aria-label="{nombre}. {ayuda}"')
                        .on("keydown.enter", lambda _e, c=clave: self._abrir(c))
                    ):
                        ui.icon(icono).classes("tpi-ambar text-3xl")
                        ui.label(nombre).classes("text-lg font-semibold")
                        ui.label(ayuda).classes("tpi-sobrio text-sm")

    def _herramienta(self, clave: str) -> None:
        nombre = HERRAMIENTAS[clave][0]
        with ui.row().classes("w-full items-center gap-3"):
            ui.button(
                color=None, text="Herramientas", icon="arrow_back", on_click=lambda: self._abrir(None)
            ).props("flat no-caps").classes("tpi-sobrio")
            ui.label(nombre).classes("text-xl font-semibold")
        with ui.column().classes("tpi-legado w-full gap-6"):
            if clave == "crear":
                _fabrica_manual(self.modo, self.guion)
            elif clave == "cola":
                _cola_detallada()
            elif clave == "videos":
                _biblioteca()
            elif clave == "estilos":
                _estilos()
            else:
                _ajustes()


# ------------------------------------------------------------------------------------------
# La página
# ------------------------------------------------------------------------------------------


def tablero(
    pestana: str = "cola", abrir: str | None = None, modo: str = "uno", guion: str | None = None
) -> None:
    """Las tres pantallas de la sala: producción («/cola»), aprobar guiones («/qc») y herramientas («/avanzado»).

    Cada una es una sola pantalla, sin pestañas; las otras dos quedan a un clic.
    """
    piel_de_la_pagina()
    cabecera(con_menu=False, al_estudio=True)
    with ui.column().classes("tpi-tablero w-full max-w-7xl mx-auto px-8 py-10 gap-6"):
        if pestana == "cola":
            ColaDeProduccion(lambda clave: ui.navigate.to(f"/{clave}")).render()
            return
        if pestana == "qc":
            AprobacionDeGuiones(lambda: None, abrir=guion).render()
        else:
            Herramientas(abrir, modo, guion).render()
