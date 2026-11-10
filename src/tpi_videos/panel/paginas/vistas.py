"""Las rutas del panel: un solo tablero con tres pestañas.

El motor escribe y produce solo; el panel es una sala de supervisión (ver ``tablero.py``). Las rutas
antiguas siguen respondiendo y abren la pestaña (y el plegable de «Avanzado») donde ahora vive lo que
mostraban, para que ningún enlace interno ni favorito quede roto.
"""

from __future__ import annotations

from nicegui import ui

from .tablero import tablero

TITULO = "Sala de producción · Tu Profe Industrial"


def registrar() -> None:
    @ui.page("/", title=TITULO)
    def cola_de_produccion() -> None:
        tablero("cola")

    @ui.page("/qc", title=TITULO)
    def aprobacion() -> None:
        tablero("qc")

    @ui.page("/avanzado", title=TITULO)
    def avanzado() -> None:
        tablero("avanzado")

    # Las rutas de antes, cada una en su lugar nuevo.
    @ui.page("/cola", title=TITULO)
    def cola() -> None:
        tablero("cola")

    @ui.page("/crear", title=TITULO)
    def crear(guion: str | None = None) -> None:
        tablero("avanzado", abrir="crear", modo="paso", guion=guion)

    @ui.page("/fabrica", title=TITULO)
    def fabrica() -> None:
        tablero("avanzado", abrir="crear", modo="lote")

    @ui.page("/videos", title=TITULO)
    def videos() -> None:
        tablero("avanzado", abrir="videos")

    @ui.page("/motor", title=TITULO)
    def motor() -> None:
        tablero("avanzado", abrir="estilos")

    @ui.page("/estilos", title=TITULO)
    def estilos() -> None:
        tablero("avanzado", abrir="estilos")

    @ui.page("/ajustes", title=TITULO)
    def ajustes() -> None:
        tablero("avanzado", abrir="ajustes")
