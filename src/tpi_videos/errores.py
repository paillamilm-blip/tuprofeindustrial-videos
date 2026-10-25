"""Errores con mensajes claros para quien usa el motor (sin trazas técnicas)."""

from __future__ import annotations


class ErrorMotor(Exception):
    """Error esperado: se muestra al usuario como mensaje + ayuda, sin traceback.

    ``transitorio`` marca lo que se arregla solo esperando (cuota agotada, el servicio caído, internet
    cortado). El lote lo usa para saber si vale la pena volver a intentar o hay que avisar de una vez.
    """

    def __init__(self, mensaje: str, ayuda: str | None = None, transitorio: bool = False) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.ayuda = ayuda
        self.transitorio = transitorio
