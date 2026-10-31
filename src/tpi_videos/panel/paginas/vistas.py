"""Las tres vistas del panel: Fábrica, Cola y biblioteca, Motor visual y ajustes.

Una vista por tarea del autor, no una por pantalla del motor. Los tres caminos de producción
(Un video, Lote de 3, Paso a paso) son pestañas dentro de la Fábrica; cada producer sigue siendo
el mismo de antes, con su temporizador y su tarjeta, y sólo uno vive a la vez. Las rutas antiguas
siguen respondiendo — apuntan a la vista que ahora contiene aquella página — para que ningún
enlace interno ni favorito quede roto.
"""

from __future__ import annotations

from nicegui import ui

from ..comun import marco, titulo_seccion
from ..tareas import TAREAS
from . import ajustes
from .crear import PaginaCrear, guion_permitido
from .estilos import lista_de_temas
from .fabrica import ColaLotes, PaginaFabrica
from .un_video import PaginaUnVideo
from .videos import PaginaVideos

AYUDA_FABRICA = "Tres caminos, una fábrica: la IA arma el video, tú cambias lo que quieras."
AYUDA_COLA = "Lo que el motor está haciendo ahora y todo lo que ya salió. 📦 abre la portada y los textos para publicar."
AYUDA_MOTOR = "Cómo se ven tus videos y qué usa el motor. Todo se guarda en mis_ajustes/ (actualizar el motor nunca lo borra)."


def _fabrica(modo: str, guion: str | None = None) -> None:
    """La Fábrica: las tres formas de producir, una pestaña visible a la vez."""
    with marco("/"):
        titulo_seccion(None, "Fábrica de contenido", AYUDA_FABRICA)
        pestanas = ui.tabs(value=modo)
        with pestanas:
            ui.tab("uno", label="Un video", icon="movie_creation")
            ui.tab("lote", label="Lote de 3", icon="bolt")
            ui.tab("paso", label="Paso a paso", icon="edit_note")
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

        def al_cambiar(e) -> None:
            zona.clear()
            with zona:
                productor(e.value)

        pestanas.on_value_change(al_cambiar)
        with zona:
            productor(modo)


def _cola_y_biblioteca() -> None:
    """Arriba la tarea en curso y la cola de lotes; abajo, la biblioteca entera."""
    with marco("/cola"):
        titulo_seccion(None, "Cola y biblioteca", AYUDA_COLA)

        @ui.refreshable
        def tarjeta_tarea() -> None:
            t = TAREAS.actual
            if t is None or (t.terminada and not t.reciente()):
                return
            with ui.card().classes("tpi-hoja w-full p-4 gap-2"):
                with ui.row().classes("w-full items-center justify-between gap-2"):
                    ui.label(t.nombre).classes("font-bold")
                    with ui.row().classes("items-center gap-2"):
                        if t.terminada:
                            etiqueta = "✅ Listo" if t.ok else ("⏹ Cancelado" if t.cancelada else "❌ Falló")
                            ui.label(etiqueta).classes("text-sm font-bold")
                        else:
                            ui.label(f"{round(t.avance * 100)} %").classes("text-sm font-bold")
                            ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                                "flat dense color=negative"
                            )
                if not t.terminada:
                    ui.linear_progress(value=t.avance, show_value=False).props("size=6px rounded").classes(
                        "w-full"
                    )
                detalle = t.detalle or t.texto_etapa or ""
                if detalle:
                    ui.label(detalle).classes("tpi-ayuda text-sm")

        def lanzar(args: list[str], nombre: str) -> None:
            if TAREAS.ocupado():
                ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
                return
            TAREAS.lanzar(nombre, args)
            ui.notify("Puesto en marcha: el avance se ve acá arriba.", type="positive")
            tarjeta_tarea.refresh()

        tarjeta_tarea()
        vista_cola = ColaLotes(lanzar)
        vista_cola.dibujar()
        biblioteca = PaginaVideos()  # una sola instancia: los controles y la lista comparten el contador
        biblioteca.controles()
        biblioteca.lista()

        estado = {"ocupado": TAREAS.ocupado()}

        def mirar() -> None:
            tarjeta_tarea.refresh()
            ahora = TAREAS.ocupado()
            if ahora != estado["ocupado"]:
                estado["ocupado"] = ahora  # el lote cambió de estado: la cola se pinta otra vez
                vista_cola.dibujar()

        ui.timer(0.7, mirar)


def _motor_y_ajustes() -> None:
    """El estilo de la imagen y las preferencias del motor, en la misma hoja."""
    with marco("/motor"):
        titulo_seccion(None, "Motor visual y ajustes", AYUDA_MOTOR)
        ui.label("Tus estilos").classes("tpi-titulo text-lg")
        lista_de_temas()
        ui.label("Tus ajustes").classes("tpi-titulo text-lg")
        ajustes.cuerpo()


def registrar() -> None:
    """Tres vistas nuevas; las rutas antiguas siguen respondiendo, cada una en su vista."""
    FABRICA = "Fábrica de contenido · Tu Profe Industrial"
    COLA = "Cola y biblioteca · Tu Profe Industrial"
    MOTOR = "Motor visual y ajustes · Tu Profe Industrial"

    @ui.page("/", title=FABRICA)
    def fabrica_uno() -> None:
        _fabrica("uno")

    @ui.page("/fabrica", title=FABRICA)
    def fabrica_lote() -> None:
        _fabrica("lote")

    @ui.page("/crear", title=FABRICA)
    def fabrica_paso(guion: str | None = None) -> None:
        _fabrica("paso", guion)

    @ui.page("/cola", title=COLA)
    def cola() -> None:
        _cola_y_biblioteca()

    @ui.page("/videos", title=COLA)
    def videos() -> None:
        _cola_y_biblioteca()

    @ui.page("/motor", title=MOTOR)
    def motor() -> None:
        _motor_y_ajustes()

    @ui.page("/estilos", title=MOTOR)
    def estilos() -> None:
        _motor_y_ajustes()

    @ui.page("/ajustes", title=MOTOR)
    def ajustes_alias() -> None:
        _motor_y_ajustes()
