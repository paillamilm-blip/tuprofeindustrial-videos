"""Los chequeos de un guion antes de aprobarlo: cada uno con su check, sin leer el YAML.

Sin NiceGUI (solo biblioteca estándar): se prueba sin abrir el panel. La persona que aprueba no debería
tener que abrir «Detalles técnicos» para saber si el guion está bien: acá se resume en pocas marcas.
Verde = bien, ámbar = conviene mirarlo, rojo = hay que corregirlo.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

HECHA, AVISO, ERROR = "hecha", "aviso", "error"
_PALABRA = {HECHA: "bien", AVISO: "conviene revisarlo", ERROR: "hay que corregirlo"}


@dataclass(frozen=True)
class Chequeo:
    clave: str
    texto: str
    estado: str  # HECHA, AVISO o ERROR

    @property
    def aria(self) -> str:
        """Lo que lee un lector de pantalla: «Guion válido: bien»."""
        return f"{self.texto}: {_PALABRA[self.estado]}"


def chequeos(
    *,
    error: str | None,
    voces: int,
    tiene_metadatos: bool,
    estilo_disponible: bool | None,
    observaciones: int,
) -> tuple[Chequeo, ...]:
    """Las marcas de un guion, en el orden en que importan.

    ``estilo_disponible`` es None cuando el guion no valida (no hay estilo que revisar): ese chequeo no sale.
    """
    marcas = [
        Chequeo("valido", "Guion con errores" if error else "Guion válido", ERROR if error else HECHA),
        Chequeo("voz", "Texto para la voz" if voces else "Sin texto para la voz", HECHA if voces else ERROR),
        Chequeo(
            "redes",
            "Título y hashtags" if tiene_metadatos else "Sin hashtags: el kit los escribe",
            HECHA if tiene_metadatos else AVISO,
        ),
    ]
    if estilo_disponible is not None:
        marcas.append(
            Chequeo(
                "estilo",
                "Estilo listo" if estilo_disponible else "Estilo no disponible en este equipo",
                HECHA if estilo_disponible else ERROR,
            )
        )
    marcas.append(
        Chequeo(
            "dudas",
            "Sin dudas de la IA"
            if not observaciones
            else f"{observaciones} duda{'' if observaciones == 1 else 's'} de la IA",
            HECHA if not observaciones else AVISO,
        )
    )
    return tuple(marcas)


def hay_errores(marcas: Collection[Chequeo]) -> bool:
    """True si algo en rojo impide aprobar con tranquilidad."""
    return any(m.estado == ERROR for m in marcas)
