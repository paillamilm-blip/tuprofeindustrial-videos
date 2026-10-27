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

from ... import cola, ia
from ...entorno import raiz_proyecto
from ...errores import ErrorMotor
from ...ideas import ANGULOS, DIFICULTADES
from ...moldes import nombre_molde
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
PROPIOS = ("3 videos de", "Reintento", "Reanudar")

ESTADOS_FILA = {
    "en_cola": ("radio_button_unchecked", GRIS, "En espera"),
    "redactando": ("edit_note", AZUL, "La IA está escribiendo…"),
    "animando": ("movie", AZUL, "Animando"),
    "subtitulos": ("subtitles", AZUL, "Subtítulos"),
    "kit": ("content_copy", AZUL, "Kit de publicación"),
    "pendiente_ia": ("wifi_off", NARANJA, "Pendiente de conexión"),
    "interrumpido": ("pause_circle", NARANJA, "Se interrumpió"),
    "listo": ("task_alt", VERDE, "Listo"),
    "fallo": ("cancel", ROJO, "Falló"),
}
ESTADOS_QUE_PENDEN = ("pendiente_ia", "interrumpido", "fallo")
NOMBRES_ESTADO = {
    "pensando_ideas": "Pensando las ideas",
    "en_curso": "En curso",
    "pendiente_ia": "Pendiente de conexión",
    "interrumpido": "Interrumpido",
    "listo": "Listo",
    "fallo": "Terminó con errores",
    "descartado": "Descartado",
}


def _sin_prefijo(texto: str) -> str:
    encontrado = VIDEO_DE.match(texto)
    return encontrado.group(3) if encontrado else texto


def _nombre_estado(estado: str) -> str:
    return NOMBRES_ESTADO.get(estado, estado.replace("_", " ").capitalize())


def _fecha(valor: object) -> str:
    texto = str(valor or "")
    return f"{texto[8:10]}-{texto[5:7]} {texto[11:16]}" if len(texto) >= 16 else texto


def _hora(valor: object) -> str:
    texto = str(valor or "")
    return texto[11:16] if len(texto) >= 16 else texto


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
        self._cola_rota = False  # la cola anterior se apartó por dañada; se avisa hasta que hay lotes

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

        self.zona_cola = ui.column().classes("w-full gap-3")
        self._dibujar_cola()

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
                ui.label(
                    "Si la IA está saturada, espera y reintenta sola: el video queda pendiente hasta "
                    "que vuelva la conexión."
                ).classes("tpi-ayuda")

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
                    with ui.column().classes("gap-1 flex-1"):
                        titulo = ui.label(f"Video {n + 1}").classes("font-bold")
                        estado = ui.label("En espera").classes("tpi-ayuda text-sm")
                        barra = (
                            ui.linear_progress(value=0, show_value=False)
                            .props("size=6px rounded")
                            .classes("w-full")
                        )
                    self.filas.append({"icono": icono, "titulo": titulo, "estado": estado, "barra": barra})

    def _marcar_fila(self, numero: int, datos: dict) -> None:
        fila = self.filas[numero - 1]
        estado = str(datos.get("estado") or "en_cola")
        icono, color, etiqueta = ESTADOS_FILA.get(estado, ESTADOS_FILA["en_cola"])
        detalle = _sin_prefijo(str(datos.get("detalle") or ""))
        if detalle and estado in ESTADOS_QUE_PENDEN:
            etiqueta = f"{etiqueta} · {detalle}"
        fila["icono"].set_name(icono).set_text_color(color)
        fila["estado"].text = etiqueta
        fila["barra"].value = 1.0 if estado == "listo" else float(datos.get("avance") or 0.0)
        if estado == "listo":
            fila["barra"].props("color=positive")
        elif estado in ESTADOS_QUE_PENDEN:
            fila["barra"].props("color=warning")
        else:
            fila["barra"].props("color=primary")

    def _avance(self, t: Tarea) -> None:
        self.barra.value = t.avance
        self.porcentaje.text = f"{round(t.avance * 100)} %"
        self.detalle.text = _sin_prefijo(t.detalle or "") or t.texto_etapa
        if not t.videos:
            return
        total = max((int(d.get("total") or 0) for d in t.videos.values()), default=0) or len(t.videos)
        self._asegurar_filas(total)
        for numero, datos in t.videos.items():
            if not 1 <= numero <= len(self.filas):
                continue
            encontrado = TITULO.search(str(datos.get("detalle") or ""))
            if encontrado:
                self.titulos[numero - 1] = encontrado.group(1)
            if self.titulos[numero - 1]:
                self.filas[numero - 1]["titulo"].text = self.titulos[numero - 1]
            self._marcar_fila(numero, datos)

    # ── la cola persistente ────────────────────────────────────────────────────────────

    def _dibujar_cola(self) -> None:
        self.zona_cola.clear()
        if TAREAS.ocupado():
            self.zona_cola.set_visibility(False)
            return
        datos = cola.cargar()
        if datos.get("roto"):
            # La cola anterior estaba dañada y se apartó: se avisa hasta que vuelve a haber lotes.
            self._cola_rota = True
        if datos.get("version") != cola.VERSION:
            # La escribió una versión más nueva del motor: se muestra, no se sobrescribe.
            with self.zona_cola:
                ui.label(
                    "La cola la escribió una versión más nueva del motor. Actualiza con git pull."
                ).classes("tpi-ayuda")
            self.zona_cola.set_visibility(True)
            return
        # Con el panel en reposo, lo que quedó a medio hacer pasa a «interrumpido» y se puede reanudar.
        cola.normalizar_interrumpidos()
        lotes = cola.lotes_visibles()
        if self._cola_rota and lotes:
            self._cola_rota = False  # ya hay trabajo nuevo: el aviso cumplió su función
        if not lotes and not self._cola_rota:
            self.zona_cola.set_visibility(False)
            return
        self.zona_cola.set_visibility(True)
        with self.zona_cola:
            if self._cola_rota:
                ui.label(
                    "La cola anterior estaba dañada y se apartó: esos videos no se pudieron reanudar."
                ).classes("tpi-ayuda text-sm").set_text_color(NARANJA)
            if lotes:
                ui.label("Cola de videos").classes("tpi-titulo text-lg")
                for lote in reversed(lotes):
                    self._tarjeta_lote(lote)

    def _tarjeta_lote(self, lote: dict) -> None:
        estado = str(lote.get("estado") or "")
        activo = estado in ("pensando_ideas", "en_curso")
        with ui.card().classes("tpi-hoja w-full p-4 gap-2"):
            with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                with ui.column().classes("gap-0"):
                    ui.label(str(lote.get("tema") or "Un video")).classes("font-bold")
                    ui.label(f"{_fecha(lote.get('creado'))} · {_nombre_estado(estado)}").classes(
                        "tpi-ayuda text-sm"
                    )
                with ui.row().classes("gap-2"):
                    if not activo and estado != "listo":
                        ui.button(
                            "Reanudar",
                            icon="play_arrow",
                            on_click=lambda lt=lote: self._reanudar_lote(lt["id"]),
                        ).props("outline dense")
                    if not activo:
                        ui.button(
                            "Descartar",
                            icon="delete_outline",
                            on_click=lambda lt=lote: self._confirmar_descarte(lt),
                        ).props("flat dense")
            for video in lote.get("videos", []):
                self._fila_cola(video)
            if estado == "listo":
                ui.button(
                    "Abrir la carpeta",
                    icon="folder_open",
                    on_click=lambda: abrir_en_mac(raiz_proyecto() / "salida"),
                ).props("outline dense")

    def _fila_cola(self, video: dict) -> None:
        estado = str(video.get("estado") or "en_cola")
        icono, color, etiqueta = ESTADOS_FILA.get(estado, ESTADOS_FILA["en_cola"])
        idea = video.get("idea") or {}
        titulo = str(idea.get("titulo") or f"Video {video.get('posicion', '?')}")
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.icon(icono, size="18px").set_text_color(color)
            with ui.column().classes("gap-0 flex-1"):
                ui.label(titulo).classes("text-sm")
                extra = ""
                if estado == "pendiente_ia" and video.get("proximo_intento"):
                    extra = f" · reintento {_hora(video['proximo_intento'])}"
                ui.label(f"{etiqueta}{extra}").classes("tpi-ayuda text-xs")
                if estado == "fallo" and video.get("error"):
                    ui.label(str(video["error"])).classes("text-xs").style(f"color:{ROJO}")
                if estado != "listo":
                    ui.linear_progress(value=float(video.get("avance") or 0.0), show_value=False).props(
                        "size=4px rounded"
                    ).classes("w-full")
            if estado == "fallo" and idea:
                ui.button(
                    "Intentar solo este",
                    icon="refresh",
                    on_click=lambda i=idea: self._arrancar_uno(i),
                ).props("flat dense")
            if estado == "listo" and (video.get("hitos") or {}).get("video"):
                ruta = Path(str(video["hitos"]["video"].get("video") or ""))
                if ruta.exists():
                    ui.button("Ver video", icon="movie", on_click=lambda r=ruta: abrir_en_mac(r)).props(
                        "flat dense"
                    )

    def _reanudar_lote(self, lote_id: str) -> None:
        self._correr(["lote", "--reanudar", "--cola-id", lote_id], "Reanudar cola")

    def _confirmar_descarte(self, lote: dict) -> None:
        with ui.dialog() as dialogo, ui.card().classes("gap-2"):
            ui.label(f"¿Sacar de la cola «{lote.get('tema') or 'este lote'}»?").classes("font-bold")
            ui.label("Los videos que ya salieron no se borran.").classes("tpi-ayuda")
            with ui.row().classes("gap-2"):
                ui.button("Sí, sacarlo", on_click=lambda: self._descartar(lote["id"], dialogo)).props(
                    "color=negative"
                )
                ui.button("Mejor no", on_click=dialogo.close).props("flat")
        dialogo.open()

    def _descartar(self, lote_id: str, dialogo) -> None:
        try:
            cola.descartar_lote(lote_id)
        except ErrorMotor as e:
            ui.notify(e.mensaje, type="warning")
        dialogo.close()
        self._dibujar_cola()

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
                nombre_molde(str(item.get("molde"))) if item.get("molde") else "",
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
        self._dibujar_cola()
        if t.cancelada:
            ui.notify("Cancelado. Lo que ya terminó queda en la carpeta salida/.", type="info")
            return
        self._mostrar_resultado(t)

    def _mostrar_resultado(self, t: Tarea) -> None:
        if t.resultado.get("pendiente"):
            self.zona_resultado.clear()
            self.zona_resultado.set_visibility(False)
            self.zona_inicio.set_visibility(True)
            self._dibujar_cola()
            ui.notify("Quedó pendiente de conexión. Se reanuda solo cuando vuelva la IA.", type="info")
            return
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
