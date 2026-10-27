"""Arranque del panel: rutas de archivos, páginas y servidor (solo 127.0.0.1)."""

from __future__ import annotations

import socket
import webbrowser

from nicegui import app, ui

from ..entorno import FUENTES_DIR, PAQUETE, raiz_proyecto
from ..icono import IMAGEN
from ..temas import FONDOS_DIR
from .paginas import ajustes, crear, estilos, fabrica, videos
from .tareas import TAREAS

HOST = "127.0.0.1"  # NiceGUI escucha en 0.0.0.0 (toda la red) si no se indica: aquí, solo este Mac


def _ya_abierto(puerto: int) -> bool:
    """¿Ya hay algo escuchando en ese puerto? (Se prueba conectándose: un panel recién cerrado deja el
    puerto unos segundos «en espera» y no por eso está ocupado.)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, puerto)) == 0


async def _reanudar_cola() -> None:
    """Al abrir el panel: lo que quedó esperando a la IA se retoma solo (sin tocar renders a medias)."""
    from .. import cola, ia

    if TAREAS.ocupado() or cola.candado_tomado():
        return
    cola.normalizar_interrumpidos()
    if ia.obtener_clave() is None:
        return
    if cola.elegir_lote(solo_pendientes=True) is None:
        return
    TAREAS.lanzar("Reanudar cola", ["lote", "--reanudar", "--solo-pendientes"])


def iniciar(puerto: int = 8765, abrir: bool = True) -> None:
    from ..cli import consola

    url = f"http://{HOST}:{puerto}"
    if _ya_abierto(puerto):
        consola.print(f"[yellow]El panel ya está abierto:[/] {url}")
        consola.print(f"   (Si no es el panel, ábrelo en otro puerto: ./tpi panel --puerto {puerto + 1})")
        if abrir:
            webbrowser.open(url)
        return

    raiz = raiz_proyecto()
    (raiz / "salida").mkdir(exist_ok=True)
    for sub in ("stickers", "fondos"):
        (raiz / "mis_ajustes" / sub).mkdir(parents=True, exist_ok=True)
    app.add_static_files("/fuentes", FUENTES_DIR)
    app.add_static_files("/emojis", PAQUETE / "assets" / "emojis")
    app.add_static_files("/marca", IMAGEN.parent)  # el ícono de la marca (encabezado del panel)
    # Solo estas carpetas se pueden ver desde el navegador (nunca .env ni el resto del Mac)
    app.add_media_files("/medios/salida", raiz / "salida")
    app.add_media_files("/medios/stickers", raiz / "mis_ajustes" / "stickers")
    app.add_media_files("/medios/fondos", raiz / "mis_ajustes" / "fondos")
    app.add_media_files("/medios/fondos_paquete", FONDOS_DIR)  # las texturas incluidas
    app.on_shutdown(TAREAS.cancelar)  # al cerrar el panel no queda un video creándose a escondidas

    for pagina in (fabrica, crear, videos, estilos, ajustes):
        pagina.registrar()

    app.on_startup(_reanudar_cola)

    consola.print(f"[green bold]🎛  Panel abierto:[/] {url}")
    consola.print("   Deja esta ventana abierta mientras lo usas. Para cerrar el panel: Control + C")
    ui.run(
        host=HOST,
        port=puerto,
        title="Panel · Tu Profe Industrial",
        favicon=IMAGEN,  # la pestaña del navegador lleva el mismo ícono del Escritorio
        language="es",
        reload=False,
        show=abrir,
        show_welcome_message=False,
        uvicorn_logging_level="warning",
        # El bucle estándar de Python (no uvloop): lanza los comandos con el subprocess de Python, que es
        # seguro mientras otros hilos trabajan (miniaturas, fórmulas). Con uvloop, iniciar un comando en
        # ese momento podía dejar el panel congelado.
        loop="asyncio",
    )
