"""Lo que el panel lista: guiones guardados y videos creados (con miniaturas)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..entorno import raiz_proyecto
from ..publicar import guion_del_video


@dataclass
class Guardado:
    ruta: Path
    nombre: str  # para mostrar
    ejemplo: bool


def guiones() -> list[Guardado]:
    """Tus guiones (los más recientes primero) y después los ejemplos."""
    carpeta = raiz_proyecto() / "guiones"
    propios = sorted(carpeta.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
    ejemplos = sorted((carpeta / "ejemplos").glob("*.yaml"))
    return [Guardado(p, p.stem, False) for p in propios] + [
        Guardado(p, f"Ejemplo · {p.stem}", True) for p in ejemplos
    ]


@dataclass
class Video:
    carpeta: Path
    titulo: str
    tema: str
    duracion: float
    fecha: float
    final: Path | None
    borrador: Path | None
    guion: Path | None
    kit: dict[str, Any] | None

    @property
    def principal(self) -> Path:
        """El más reciente (si rehaces un borrador con otro estilo, se ve ese y no el final antiguo)."""
        existentes = [p for p in (self.final, self.borrador) if p is not None]
        return max(existentes, key=lambda p: p.stat().st_mtime)


def videos() -> list[Video]:
    salida = raiz_proyecto() / "salida"
    encontrados: list[Video] = []
    if not salida.exists():
        return encontrados
    for carpeta in salida.iterdir():
        archivo = carpeta / "linea_de_tiempo.json"
        if carpeta.name.startswith("_") or not archivo.exists():
            continue
        try:
            linea = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        final = carpeta / f"{carpeta.name}.mp4"
        borrador = carpeta / f"{carpeta.name}_borrador.mp4"
        final_ok, borrador_ok = final.exists(), borrador.exists()
        if not (final_ok or borrador_ok):
            continue
        kit = None
        if (carpeta / "publicacion.json").exists():
            try:
                kit = json.loads((carpeta / "publicacion.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                kit = None
        fecha = max(p.stat().st_mtime for p in (final, borrador) if p.exists())
        encontrados.append(
            Video(
                carpeta=carpeta,
                titulo=linea.get("titulo", carpeta.name),
                tema=linea.get("tema", "Pizarra nocturna"),
                duracion=float(linea.get("duracion_total", 0)),
                fecha=fecha,
                final=final if final_ok else None,
                borrador=borrador if borrador_ok else None,
                guion=guion_del_video(carpeta, linea),
                kit=kit,
            )  # fmt: skip
        )
    return sorted(encontrados, key=lambda v: v.fecha, reverse=True)


def miniatura(video: Video) -> Path | None:
    """Cuadro del gancho, pequeño (se crea una vez y se rehace si el video cambia)."""
    from ..errores import ErrorMotor
    from ..postproduccion import extraer_cuadro
    from ..publicar import _video_sin_subtitulos

    destino = video.carpeta / "miniatura.jpg"
    if destino.exists() and destino.stat().st_mtime >= video.fecha:
        return destino
    try:
        linea = json.loads((video.carpeta / "linea_de_tiempo.json").read_text(encoding="utf-8"))
        gancho = next((b for b in linea["bloques"] if b["seccion"] == "gancho"), linea["bloques"][0])
        momento = gancho["inicio"] + max(0.1, gancho["duracion"] - 0.15)
        return extraer_cuadro(_video_sin_subtitulos(video.carpeta, linea), momento, destino, ancho=270)
    except (ErrorMotor, OSError, KeyError, IndexError, json.JSONDecodeError):
        return None


def borrar(video: Video) -> None:
    salida = (raiz_proyecto() / "salida").resolve()
    carpeta = video.carpeta.resolve()
    if carpeta.parent == salida:  # nunca borrar nada fuera de salida/
        shutil.rmtree(carpeta, ignore_errors=True)
