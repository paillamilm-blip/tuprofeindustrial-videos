"""Las herramientas manuales del panel («Avanzado»), sin NiceGUI: se prueban sin abrir el panel.

«Avanzado» es una sola pantalla con cinco tarjetas; cada una abre su herramienta, de a una. Las rutas
antiguas (``/crear``, ``/videos``, ``/estilos``…) llegan con la clave de la herramienta que ahora las contiene.
"""

from __future__ import annotations

# clave → (nombre, ícono de Material, una línea que dice para qué sirve)
HERRAMIENTAS: dict[str, tuple[str, str, str]] = {
    "crear": ("Crear a mano", "edit_note", "Un video, un lote de 3 o el editor paso a paso"),
    "cola": ("Cola por lotes", "view_list", "Reanudar, reintentar o descartar un lote"),
    "videos": ("Mis videos", "video_library", "Todo lo que ya salió, con su kit para publicar"),
    "estilos": ("Estilos visuales", "palette", "Colores, letra y fondo de los videos"),
    "ajustes": ("Ajustes", "settings", "Clave de Gemini, voz, marca y el chequeo del equipo"),
}


def herramienta_de(abrir: str | None) -> str | None:
    """La herramienta que se abre directo (por una ruta antigua), o None para mostrar las cinco tarjetas."""
    return abrir if abrir in HERRAMIENTAS else None
