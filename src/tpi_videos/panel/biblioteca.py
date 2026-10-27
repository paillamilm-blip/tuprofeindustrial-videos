"""Lo que el panel lista: guiones guardados y videos creados (con miniaturas)."""

from __future__ import annotations

import functools
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..entorno import raiz_proyecto
from ..publicar import guion_del_video

FONDO_POR_DEFECTO = "#080A0D"
TEXTO_POR_DEFECTO = "#EAF2FF"


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
    tema_clave: str | None = None  # la clave con la que se creó (el nombre visible no carga colores)
    materia: str = ""
    molde: str = ""

    @property
    def principal(self) -> Path:
        """El más reciente (si rehaces un borrador con otro estilo, se ve ese y no el final antiguo)."""
        existentes = [p for p in (self.final, self.borrador) if p is not None]
        return max(existentes, key=lambda p: p.stat().st_mtime)


@functools.lru_cache(maxsize=256)
def _datos_guion(ruta: str) -> tuple[str, str]:
    """Materia y molde del guion: los videos creados antes no los guardaron en la línea de tiempo."""
    try:
        crudo = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return "", ""
    if not isinstance(crudo, dict):
        return "", ""
    return str(crudo.get("materia") or ""), str(crudo.get("molde") or "")


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
        guion = guion_del_video(carpeta, linea)
        materia, molde = str(linea.get("materia") or ""), str(linea.get("molde") or "")
        if guion is not None and not (materia and molde):
            del_guion_materia, del_guion_molde = _datos_guion(str(guion))
            materia, molde = materia or del_guion_materia, molde or del_guion_molde
        encontrados.append(
            Video(
                carpeta=carpeta,
                titulo=linea.get("titulo", carpeta.name),
                tema=linea.get("tema", "Pizarra nocturna"),
                tema_clave=linea.get("tema_clave"),
                materia=materia,
                molde=molde,
                duracion=float(linea.get("duracion_total", 0)),
                fecha=fecha,
                final=final if final_ok else None,
                borrador=borrador if borrador_ok else None,
                guion=guion,
                kit=kit,
            )  # fmt: skip
        )
    return sorted(encontrados, key=lambda v: v.fecha, reverse=True)


def portada_de_reserva(titulo: str, color_fondo: str, color_texto: str, destino: Path) -> Path:
    """El cuadro que se muestra cuando extraer el fotograma falla: el gancho sobre el color del tema.

    Se arma con PIL (sin render, sin IA) para que el muro de «Mis videos» nunca tenga un cuadro gris.
    """
    from PIL import Image, ImageDraw, ImageFont

    from ..tipografia import archivo

    ancho, alto = 540, 960
    imagen = Image.new("RGB", (ancho, alto), color_fondo)
    trazo = ImageDraw.Draw(imagen)
    fuente = ImageFont.truetype(str(archivo("Montserrat", "HEAVY")), 62)
    lineas: list[str] = []
    actual = ""
    for palabra in (titulo or "Video sin título").split():
        candidato = f"{actual} {palabra}".strip()
        if trazo.textlength(candidato, font=fuente) <= ancho - 96:
            actual = candidato
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    lineas = [x for x in lineas if x][:6] or ["Video sin título"]
    y = (alto - len(lineas) * 78) // 2
    for linea in lineas:
        x = (ancho - trazo.textlength(linea, font=fuente)) / 2
        trazo.text((x, y), linea, fill=color_texto, font=fuente)
        y += 78
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(destino, "PNG")
    return destino


def _colores_del_tema(video: Video) -> tuple[str, str]:
    from ..config import cargar_marca
    from ..errores import ErrorMotor
    from ..temas import cargar_tema

    if not video.tema_clave:
        return FONDO_POR_DEFECTO, TEXTO_POR_DEFECTO
    try:
        estilo = cargar_tema(video.tema_clave, cargar_marca())
    except ErrorMotor:
        return FONDO_POR_DEFECTO, TEXTO_POR_DEFECTO
    return estilo.colores.fondo, estilo.colores.texto


def miniatura(video: Video) -> Path:
    """Cuadro del gancho, pequeño (se crea una vez y se rehace si el video cambia).

    Siempre devuelve una imagen: si el fotograma no se puede sacar, se arma la portada con el gancho.
    """
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
        fondo, texto = _colores_del_tema(video)
        return portada_de_reserva(video.titulo, fondo, texto, video.carpeta / "miniatura_fallback.png")


def borrar(video: Video) -> None:
    salida = (raiz_proyecto() / "salida").resolve()
    carpeta = video.carpeta.resolve()
    if carpeta.parent == salida:  # nunca borrar nada fuera de salida/
        shutil.rmtree(carpeta, ignore_errors=True)
