"""Panel de control local (NiceGUI): crear, ver y publicar videos sin usar la Terminal.

- Solo escucha en 127.0.0.1: nadie más en la red (ni siquiera por WiFi) puede entrar.
- Lo pesado (redactar, crear videos, vistas previas, kit de publicación) lo hacen los mismos comandos
  ``tpi`` en procesos aparte: si un video falla, el panel sigue funcionando, y lo que hace el panel es
  exactamente lo que hacen los comandos.
"""

__all__ = ["iniciar"]


def iniciar(*args, **kwargs):
    """Se importa recién al abrir el panel: así ``tpi_videos.panel.tareas`` se prueba sin NiceGUI."""
    from .app import iniciar as _iniciar

    return _iniciar(*args, **kwargs)
