"""Lo que muestra el tablero de supervisión, sacado de la cola (``salida/.cola/trabajos.json``).

Sin NiceGUI: las columnas del tablero, el próximo lote a producir y el lanzamiento en lote se
deciden acá y se prueban sin abrir el panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import cola
from .etapas import Etapa, etapas_de

PENDIENTES, EN_RENDER, COMPLETADOS = "pendientes", "en_render", "completados"
COLUMNAS = {
    PENDIENTES: "Pendientes",
    EN_RENDER: "En renderizado",
    COMPLETADOS: "Completados",
}
MAXIMO_COMPLETADOS = 12  # el tablero muestra lo reciente; la biblioteca entera vive en Avanzado

_COLUMNA_DE_ESTADO = {
    **{e: PENDIENTES for e in (*cola.ESTADOS_PENDIENTES, "fallo")},
    **{e: EN_RENDER for e in cola.ESTADOS_ACTIVOS},
    "listo": COMPLETADOS,
}


@dataclass
class Ficha:
    video_id: str
    lote_id: str
    titulo: str
    tema: str
    estado: str
    texto_estado: str
    avance: float
    detalle: str
    error: str | None
    video: Path | None  # el .mp4 terminado
    actualizado: str
    guion: Path | None = None  # el .yaml de donde sale, si ya está escrito
    etapas: tuple[Etapa, ...] = ()  # Guion, Animación, Video y Kit: cada una con su % y su check

    @property
    def fallo(self) -> bool:
        return self.estado == "fallo"


def _texto_estado(estado: str) -> str:
    return {
        "en_cola": "En espera",
        "pendiente_ia": "Esperando a la IA",
        "interrumpido": "Se interrumpió",
        "fallo": "Falló",
        "listo": "Listo",
    }.get(estado, cola.FASES.get(estado, estado))


def columnas(
    datos: dict[str, Any], en_vivo: dict[str, dict[str, Any]] | None = None
) -> dict[str, list[Ficha]]:
    """Los videos de la cola repartidos en las tres columnas, lo más nuevo primero.

    ``en_vivo`` (video_id → {avance, detalle, estado}) pisa lo guardado: la tarea en curso informa
    más seguido de lo que se escribe la cola.
    """
    salida: dict[str, list[Ficha]] = {clave: [] for clave in COLUMNAS}
    for lote in datos.get("lotes", []):
        if lote.get("estado") == "descartado":
            continue
        for video in lote.get("videos", []):
            vivo = (en_vivo or {}).get(str(video.get("id")), {})
            estado = str(vivo.get("estado") or video.get("estado") or "en_cola")
            columna = _COLUMNA_DE_ESTADO.get(estado)
            if columna is None:
                continue
            ruta = ((video.get("hitos") or {}).get("video") or {}).get("video")
            archivo = Path(str(ruta)) if ruta else None
            crudo = ((video.get("hitos") or {}).get("guion") or {}).get("ruta")
            guion = Path(str(crudo)) if crudo else None
            avance = float(vivo.get("avance", video.get("avance")) or 0.0)
            salida[columna].append(
                Ficha(
                    video_id=str(video.get("id")),
                    lote_id=str(lote.get("id")),
                    titulo=str(
                        (video.get("idea") or {}).get("titulo") or f"Video {video.get('posicion', '?')}"
                    ),
                    tema=str(lote.get("tema") or ""),
                    estado=estado,
                    texto_estado=_texto_estado(estado),
                    avance=avance,
                    detalle=str(vivo.get("detalle") or video.get("detalle") or ""),
                    error=video.get("error"),
                    video=archivo if archivo and archivo.exists() else None,
                    actualizado=str(video.get("actualizado") or lote.get("actualizado") or ""),
                    guion=guion if guion and guion.exists() else None,
                    etapas=etapas_de(estado, avance, tuple(video.get("hitos") or ())),
                )
            )
    for clave in salida:
        salida[clave].sort(key=lambda f: f.actualizado, reverse=True)
    salida[COMPLETADOS] = salida[COMPLETADOS][:MAXIMO_COMPLETADOS]
    return salida


def lotes_por_producir(
    datos: dict[str, Any], ya_intentados: set[str] | frozenset[str] = frozenset()
) -> list[str]:
    """Los lotes con videos esperando, del más antiguo al más nuevo; un fallo no se relanza solo."""
    ids = []
    for lote in datos.get("lotes", []):
        if lote.get("estado") in ("descartado", "listo") or lote.get("id") in ya_intentados:
            continue
        if any(v.get("estado") in cola.ESTADOS_PENDIENTES for v in lote.get("videos", [])):
            ids.append(str(lote["id"]))
    return ids


def args_de_lote(lote_id: str) -> list[str]:
    """El comando que produce un lote ya guardado (sin pedir ideas: los guiones ya están escritos)."""
    return ["lote", "--reanudar", "--cola-id", lote_id]


class LanzamientoEnLote:
    """«Lanzar renderización en lote»: produce los lotes pendientes uno tras otro.

    El panel sólo corre una tarea a la vez (``TAREAS``). Esto recuerda que el usuario pidió seguir y,
    cada vez que la fila queda libre, lanza el próximo lote que no se haya intentado en esta pasada.
    Así un lote que falla o queda esperando a la IA no se relanza en bucle.
    """

    def __init__(self) -> None:
        self.activo = False
        self.intentados: set[str] = set()
        self.lanzados = 0

    def empezar(self) -> None:
        self.activo, self.intentados, self.lanzados = True, set(), 0

    def detener(self) -> None:
        self.activo = False

    def siguiente(self, datos: dict[str, Any], ocupado: bool) -> list[str] | None:
        """Los argumentos del próximo lote a lanzar, o None si hay que esperar o ya no queda nada."""
        if not self.activo or ocupado:
            return None
        pendientes = lotes_por_producir(datos, self.intentados)
        if not pendientes:
            self.activo = False
            return None
        self.intentados.add(pendientes[0])
        self.lanzados += 1
        return args_de_lote(pendientes[0])


LANZAMIENTO = LanzamientoEnLote()
