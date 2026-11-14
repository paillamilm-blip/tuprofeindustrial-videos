"""Las etapas de un video en la sala de producción: cada una con su porcentaje y su check.

Sin NiceGUI (solo biblioteca estándar): se prueba sin abrir el panel. Un video pasa por cuatro etapas
que la persona entiende (Guion, Animación, Video y Kit). Cada una se saca de lo que ya guarda la
cola: el estado del video, su avance de 0 a 1 y los hitos (guion, video, kit) que dejan una etapa
terminada aunque el avance se haya reiniciado al retomar un video interrumpido.

Los cortes del avance son los mismos que usa ``lote._traducir``: el guion llega a 0,25; la animación,
a 0,90; los subtítulos y la unión del video, a 0,95; y el kit cierra en 1.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

HECHA, ACTIVA, ESPERA, ERROR = "hecha", "activa", "espera", "error"

# (clave, nombre que ve la persona, avance donde empieza, avance donde termina, hito que la deja lista)
_ETAPAS = (
    ("guion", "Guion", 0.00, 0.25, "guion"),
    ("animacion", "Animación", 0.25, 0.90, None),
    ("video", "Video", 0.90, 0.95, "video"),
    ("kit", "Kit", 0.95, 1.00, "kit"),
)
_ACTIVOS = ("redactando", "animando", "subtitulos", "kit")  # = cola.ESTADOS_ACTIVOS, sin importarla


@dataclass(frozen=True)
class Etapa:
    clave: str
    nombre: str
    porcentaje: int  # 0–100
    estado: str  # HECHA, ACTIVA, ESPERA o ERROR

    @property
    def hecha(self) -> bool:
        return self.estado == HECHA

    @property
    def texto(self) -> str:
        """Lo que lee un lector de pantalla: «Animación: 62 %» o «Guion: listo»."""
        if self.hecha:
            return f"{self.nombre}: listo"
        if self.estado == ERROR:
            return f"{self.nombre}: falló en {self.porcentaje} %"
        return f"{self.nombre}: {self.porcentaje} %"


def etapas_de(estado: str, avance: float, hitos: Collection[str] = ()) -> tuple[Etapa, ...]:
    """Las cuatro etapas de un video, en orden, con su porcentaje y su check.

    ``estado`` es el de la cola («en_cola», «animando», «fallo», «listo»…); ``avance``, el 0–1 del
    video entero; ``hitos``, los nombres de lo ya producido.
    """
    if estado == "listo":
        return tuple(Etapa(clave, nombre, 100, HECHA) for clave, nombre, *_ in _ETAPAS)
    avance = max(0.0, min(1.0, float(avance or 0.0)))
    hechas = [(hito in hitos if hito else False) or avance >= hasta for *_, hasta, hito in _ETAPAS]
    # Lo que viene después terminado implica que lo de antes también (la animación no tiene hito propio).
    for i in range(len(hechas) - 2, -1, -1):
        hechas[i] = hechas[i] or hechas[i + 1]
    actual = next((i for i, hecha in enumerate(hechas) if not hecha), None)
    salida = []
    for i, (clave, nombre, desde, hasta, _hito) in enumerate(_ETAPAS):
        if hechas[i]:
            salida.append(Etapa(clave, nombre, 100, HECHA))
        elif i == actual:
            # round (no int): 0,325 / 0,65 da 0,4999… y se vería 49 %. Tope en 99: el 100 es del check.
            porcentaje = min(99, max(0, round((avance - desde) / (hasta - desde) * 100)))
            situacion = ERROR if estado == "fallo" else (ACTIVA if estado in _ACTIVOS else ESPERA)
            salida.append(Etapa(clave, nombre, porcentaje, situacion))
        else:
            salida.append(Etapa(clave, nombre, 0, ESPERA))
    return tuple(salida)


def avance_total(etapas: Collection[Etapa]) -> int:
    """El porcentaje del video entero: cada etapa pesa lo que ocupa en el avance de 0 a 1."""
    pesos = {clave: hasta - desde for clave, _n, desde, hasta, _h in _ETAPAS}
    return round(sum(pesos.get(e.clave, 0.0) * e.porcentaje for e in etapas))
