"""Fábrica: un tema, un botón, los 3 videos listos para publicar.

Es la portada del panel y no tiene opciones que elegir: la IA reparte los tres ángulos y las tres
dificultades, el lote los produce de uno en uno y acá solo se ve en qué video vamos. Lo que sale se
abre desde la misma pantalla: el video, su kit de publicación, o la carpeta en el Finder.

El trabajo pesado lo hace ``tpi lote`` afuera, en un proceso aparte (``TAREAS``), para que el panel
siga respondiendo mientras se anima un video.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from nicegui import ui

from ... import ia
from ...entorno import raiz_proyecto
from ...ideas import ANGULOS, DIFICULTADES
from ..comun import AZUL, GRIS, ROJO, VERDE, abrir_en_mac, marco
from ..tareas import TAREAS, Tarea
from .crear import TEMAS_SUGERIDOS
from .videos import abrir_kit

# «Video 2 de 3 · animando la fórmula»: el prefijo que el lote pone en cada aviso
VIDEO_DE = re.compile(r"^Video (\d+) de (\d+) · (.*)$")
TITULO = re.compile(r"^Voy con «(.+?)»")
# El naranja del panel para los avisos que no son errores
NARANJA = "#B26A00"
# Los nombres de los trabajos que esta pantalla sabe retomar si se recarga a medio lote
PROPIOS = ("3 videos de", "Reintento")


def _ruta_salida(ruta: Path | None) -> str:
    """La ruta corta, como la ve el Finder: salida/descuento_y_alza/descuento_y_alza.mp4."""
    if not ruta:
        return ""
    salida = (raiz_proyecto() / "salida").resolve()
    try:
        return f"salida/{ruta.resolve().relative_to(salida)}"
    except (ValueError, OSError):
        return str(ruta)


class PaginaFabrica:
    def __init__(self) -> None:
        self.filas: list[dict] = []
        self.titulos: list[str] = []
        self.mio = False  # si esta pestaña está siguiendo un trabajo de la Fábrica

    def render(self) -> None:
        """Las tres pantallas, una visible a la vez."""
        self.zona_inicio = ui.column().classes("w-full gap-4")
        self.zona_trabajo = ui.column().classes("w-full gap-4")
        self.zona_resultado = ui.column().classes("w-full gap-4")
        with self.zona_inicio:
            self._pantalla_inicio()
        with self.zona_trabajo:
            self._pantalla_trabajo()
        self.zona_trabajo.set_visibility(False)
        self.zona_resultado.set_visibility(False)
        self._reanudar()
        ui.timer(0.7, self._mirar)

    def _reanudar(self) -> None:
        """Volvió a la pestaña (o recargó) con el lote a medio hacer o ya terminado."""
        t = TAREAS.actual
        if t is None or not t.nombre.startswith(PROPIOS):
            return
        if t.terminada and not t.cancelada:
            self._mostrar_resultado(t)
            return
        self.mio = True
        self.zona_inicio.set_visibility(False)
        self.zona_trabajo.set_visibility(True)
        self._avance(t)

    # ── 1 · la pantalla de entrada ──────────────────────────────────────────────────────

    def _pantalla_inicio(self) -> None:
        with ui.column().classes("w-full gap-1"):
            ui.label("Tres videos de un tema").classes("tpi-titulo text-2xl")
            ui.label(
                "Escribe el tema y aprieta el botón. Los tres estilos y las tres dificultades los "
                "reparte la IA."
            ).classes("tpi-ayuda")

        with ui.card().classes("tpi-hoja w-full p-6 gap-4"):
            if ia.obtener_clave() is None:
                with ui.row().classes("w-full items-center gap-2 bg-[#FFF4E5] rounded p-3"):
                    ui.icon("key").classes("text-xl text-orange-8")
                    ui.label("Para crear los videos falta tu clave de Gemini (es gratis).")
                    ui.link("Configurarla en Ajustes", "/ajustes").classes("font-bold")

            self.tema = ui.input("Tema", placeholder="Porcentajes").props("outlined").classes("w-full")
            ui.label("Otro tema sirve igual: un nombre, una fórmula, un error típico.").classes("tpi-ayuda")

            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.label("Toca un tema sugerido:").classes("tpi-ayuda")
                for sugerido in TEMAS_SUGERIDOS:
                    ui.button(sugerido, on_click=lambda t=sugerido: self._con_tema(t)).props(
                        "outline dense no-caps"
                    )

            with ui.row().classes("w-full items-center gap-4 flex-wrap"):
                self.boton_arrancar = ui.button(
                    "Crear los 3 videos", icon="play_arrow", on_click=self._arrancar
                ).props("size=lg color=negative")
                ui.label("Unos 9 minutos. Puedes dejarlo corriendo y volver.").classes("tpi-ayuda")

            with ui.row().classes("w-full items-center gap-2 pt-2"):
                ui.icon("info", size="18px").set_text_color(GRIS)
                ui.label("Usa la voz y el estilo que elegiste en Ajustes. ¿Prefieres revisar las ideas?")
                ui.link("Elegirlas una por una", "/crear").classes("font-bold")

    def _con_tema(self, tema: str) -> None:
        self.tema.value = tema

    # ── 2 · mientras trabaja ────────────────────────────────────────────────────────────

    def _pantalla_trabajo(self) -> None:
        with ui.card().classes("tpi-hoja w-full p-6 gap-3"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Trabajando").classes("tpi-titulo text-lg")
                self.boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                    "flat color=negative"
                )
            self.barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
            self.porcentaje = ui.label("0 %").classes("text-sm font-bold")
            self.detalle = ui.label("").classes("tpi-ayuda")
            self.filas_videos = ui.column().classes("w-full")
            with ui.row().classes("w-full items-center gap-2 pt-2"):
                ui.icon("hourglass_top", size="18px").set_text_color(GRIS)
                ui.label("Si la IA está saturada, el motor espera 60 segundos y reintenta solo.").classes(
                    "tpi-ayuda"
                )

    def _asegurar_filas(self, total: int) -> None:
        """Una fila por video del lote, la primera vez que sabemos cuántos son."""
        if len(self.filas) == total:
            return
        self.filas_videos.clear()
        self.filas, self.titulos = [], [""] * total
        with self.filas_videos:
            for n in range(total):
                with ui.row().classes("w-full items-center gap-3 no-wrap border-t pt-3"):
                    icono = ui.icon("radio_button_unchecked").set_text_color(GRIS)
                    with ui.column().classes("gap-0"):
                        titulo = ui.label(f"Video {n + 1}").classes("font-bold")
                        estado = ui.label("En espera").classes("tpi-ayuda text-sm")
                    self.filas.append({"icono": icono, "titulo": titulo, "estado": estado})

    def _marcar_filas(self, actual: int) -> None:
        for n, fila in enumerate(self.filas, start=1):
            if self.titulos[n - 1]:
                fila["titulo"].text = self.titulos[n - 1]
            if n < actual:
                fila["icono"].set_name("task_alt").set_text_color(VERDE)
                fila["estado"].text = "Terminado"
            elif n == actual:
                fila["icono"].set_name("pending").set_text_color(AZUL)
                fila["estado"].text = "Trabajando ahora"
            else:
                fila["icono"].set_name("radio_button_unchecked").set_text_color(GRIS)
                fila["estado"].text = "En espera"

    def _avance(self, t: Tarea) -> None:
        self.barra.value = t.avance
        self.porcentaje.text = f"{round(t.avance * 100)} %"
        prefijo = VIDEO_DE.match(t.detalle or "")
        if not prefijo:
            self.detalle.text = t.detalle or t.texto_etapa
            return
        numero, total, resto = int(prefijo.group(1)), int(prefijo.group(2)), prefijo.group(3)
        self._asegurar_filas(total)
        self.detalle.text = f"Video {numero} de {total} · {resto}"
        encontrado = TITULO.match(resto)
        if encontrado:
            self.titulos[numero - 1] = encontrado.group(1)
        self._marcar_filas(numero)

    # ── 3 · cuando terminan ─────────────────────────────────────────────────────────────

    def _pantalla_resultado(self, items: list[dict]) -> None:
        listos = sum(1 for i in items if i.get("ok"))
        carpeta = raiz_proyecto() / "salida"
        with ui.card().classes("tpi-hoja w-full p-6 gap-3"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
                with ui.column().classes("gap-1"):
                    ui.label(f"{listos} de {len(items)} videos listos").classes("tpi-titulo text-2xl")
                    ui.label(
                        "Cada video tiene su carpeta en salida/, con la portada y los textos para publicar."
                    ).classes("tpi-ayuda")
                ui.button(
                    "Abrir la carpeta", icon="folder_open", on_click=lambda: abrir_en_mac(carpeta)
                ).props("outline size=lg")

            for item in items:
                self._fila_resultado(item)

            with ui.row().classes("w-full items-center gap-2 pt-2 border-t"):
                ui.icon("tips_and_updates", size="18px").set_text_color(GRIS)
                ui.label("Revísalos antes de publicar: la IA puede equivocarse con un número.").classes(
                    "tpi-ayuda"
                )
                ui.link("Verlos todos en Mis videos", "/videos").classes("font-bold")

    def _fila_resultado(self, item: dict) -> None:
        ok = bool(item.get("ok"))
        pasado = ok and not item.get("promesa_incumplida")
        etiqueta = " · ".join(
            str(texto)
            for texto in (
                f"≈{item.get('duracion')} s" if ok and item.get("duracion") else "",
                ANGULOS.get(str(item.get("angulo")), ""),
                DIFICULTADES.get(str(item.get("dificultad")), ""),
            )
            if texto
        )
        with ui.row().classes("w-full items-start gap-4 no-wrap border-t pt-4"):
            icono, color = "task_alt", VERDE
            if not ok:
                icono, color = "cancel", ROJO
            elif not pasado:
                icono, color = "priority_high", NARANJA
            ui.icon(icono).classes("text-2xl").set_text_color(color)
            with ui.column().classes("gap-1 flex-1"):
                ui.label(str(item.get("titulo") or "La idea")).classes("font-bold text-base")
                if etiqueta:
                    ui.label(etiqueta).classes("tpi-ayuda text-sm")
                if not ok:
                    ui.label(str(item.get("error") or "No salió")).classes("text-sm").style(f"color:{ROJO}")
                    if item.get("ayuda"):
                        ui.label(str(item["ayuda"])).classes("tpi-ayuda text-sm")
                    if item.get("idea"):
                        ui.button(
                            "Intentar solo este",
                            icon="refresh",
                            on_click=lambda i=item: self._arrancar_uno(i["idea"]),
                        ).props("outline dense")
                    return
                video = Path(item["video"])
                ui.label(_ruta_salida(video)).classes("text-xs text-gray-7 font-mono")
                with ui.row().classes("gap-2 no-wrap items-center"):
                    ui.button("Ver el video", icon="movie", on_click=lambda: abrir_en_mac(video)).props(
                        "outline dense"
                    )
                    ui.button(
                        "Kit de publicación", icon="content_copy", on_click=lambda: abrir_kit(video.parent)
                    ).props("flat dense")
                    if not pasado:
                        guion = quote(str(item.get("guion") or ""))
                        ui.link("Achicar el guion", f"/crear?guion={guion}").classes(
                            "text-sm font-bold self-center"
                        )
                for pendiente in item.get("pendientes") or []:
                    ui.label(f"Por revisar: {pendiente}").classes("text-sm").style(f"color:{NARANJA}")

    def _pantalla_error(self, mensaje: str, ayuda: str | None) -> None:
        with ui.card().classes("tpi-hoja w-full p-6 gap-3 tpi-error"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("error").classes("text-2xl").set_text_color(ROJO)
                ui.label("Nada salió").classes("tpi-titulo text-lg")
            ui.label(mensaje).classes("whitespace-pre-wrap")
            if ayuda:
                ui.label(f"→ {ayuda}").classes("text-sm").style(f"color:{NARANJA}")
            with ui.row().classes("gap-3 items-center"):
                ui.button("Volver a intentar", icon="refresh", on_click=self._arrancar).props("outline")
                ui.link("Revisar Ajustes", "/ajustes").classes("font-bold")

    # ── el botón ────────────────────────────────────────────────────────────────────────

    def _arrancar(self) -> None:
        texto = (self.tema.value or "").strip()
        if not texto:
            ui.notify("Escribe un tema (ej. «Porcentajes») o toca uno de los sugeridos.", type="warning")
            return
        self._correr(["lote", "--", texto], f"3 videos de «{texto}»")

    def _arrancar_uno(self, idea: dict) -> None:
        """La idea que falló, suelta: sin volver a pedirle ideas a Gemini."""
        self._correr(["lote", "--ideas-json", json.dumps([idea], ensure_ascii=False)], "Reintento")

    def _correr(self, args: list[str], nombre: str) -> None:
        """Prende el lote y se va a la pantalla de trabajo; el avance lo trae el temporizador."""
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        TAREAS.lanzar(nombre, args)
        self.zona_resultado.clear()
        self.filas, self.titulos = [], []  # un lote nuevo empieza con sus propias filas
        self.filas_videos.clear()
        self.zona_inicio.set_visibility(False)
        self.zona_resultado.set_visibility(False)
        self.zona_trabajo.set_visibility(True)
        self.barra.value = 0.0
        self.porcentaje.text = "0 %"
        self.detalle.text = "La IA está pensando las 3 ideas…"
        self.boton_cancelar.set_visibility(True)
        self.mio = True

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
        self.boton_cancelar.set_visibility(False)
        self.zona_trabajo.set_visibility(False)
        self.zona_inicio.set_visibility(True)
        if t.cancelada:
            ui.notify("Cancelado. Lo que ya terminó queda en la carpeta salida/.", type="info")
            return
        self._mostrar_resultado(t)

    def _mostrar_resultado(self, t: Tarea) -> None:
        self.zona_resultado.clear()
        try:
            with self.zona_resultado:
                if t.ok:
                    self._pantalla_resultado(list(t.resultado.get("lote") or []))
                else:
                    error = t.error or {}
                    self._pantalla_error(
                        error.get("mensaje", "El motor no respondió."),
                        str(error.get("ayuda") or ""),
                    )
        except Exception as e:  # noqa: BLE001 - un resultado raro no puede dejarla sin pantalla
            self.zona_resultado.clear()
            with self.zona_resultado:
                self._pantalla_error("El panel no alcanzó a leer el resultado del lote.", ayuda=str(e))
        self.zona_resultado.set_visibility(True)


def registrar() -> None:
    @ui.page("/", title="Fábrica · Tu Profe Industrial")
    def pagina() -> None:
        with marco("/"):
            PaginaFabrica().render()
