"""Panel de control local (NiceGUI): crear, ver y publicar videos sin usar la Terminal.

- Solo escucha en 127.0.0.1: nadie más en la red (ni siquiera por WiFi) puede entrar.
- Lo pesado (redactar, crear videos, vistas previas, kit de publicación) lo hacen los mismos comandos
  ``tpi`` en procesos aparte: si un video falla, el panel sigue funcionando, y lo que hace el panel es
  exactamente lo que hacen los comandos.
"""

from .app import iniciar

__all__ = ["iniciar"]
