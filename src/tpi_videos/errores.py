"""Errores con mensajes claros para quien usa el motor (sin trazas técnicas)."""

from __future__ import annotations


class ErrorMotor(Exception):
    """Error esperado: se muestra al usuario como mensaje + ayuda, sin traceback."""

    def __init__(self, mensaje: str, ayuda: str | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.ayuda = ayuda
