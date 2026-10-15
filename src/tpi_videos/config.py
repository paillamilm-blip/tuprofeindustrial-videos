"""Configuración del motor: calidades de render y marca (``marca.yaml``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .entorno import raiz_proyecto
from .errores import ErrorMotor


@dataclass(frozen=True)
class Calidad:
    nombre: str
    ancho: int
    alto: int
    fps: int
    crf: int  # calidad H.264 final (menor = mejor)
    preset: str  # velocidad de codificación de FFmpeg


CALIDADES: dict[str, Calidad] = {
    # Para revisar rápido el ritmo y el contenido (4–6 veces más rápido).
    "borrador": Calidad("borrador", 540, 960, 15, 23, "veryfast"),
    # Para publicar en TikTok, Reels y Shorts.
    "final": Calidad("final", 1080, 1920, 30, 18, "medium"),
}

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validar_hex(valor: str) -> str:
    if not _HEX.match(valor):
        raise ValueError(f"«{valor}» no es un color válido; usa el formato #RRGGBB (ej. #FFC72C)")
    return valor.upper()


class Colores(_Base):
    fondo: str = "#0B1220"
    panel: str = "#121B2F"
    borde: str = "#24324F"
    texto: str = "#F8FAFC"
    tenue: str = "#94A3B8"
    acento: str = "#FFC72C"
    exito: str = "#22C55E"
    cuadricula: str = "#38BDF8"

    _hex = field_validator("*")(classmethod(lambda cls, v: _validar_hex(v)))


class ColoresMateria(_Base):
    matematica: str = "#38BDF8"
    fisica: str = "#FB923C"
    ingenieria: str = "#FACC15"

    _hex = field_validator("*")(classmethod(lambda cls, v: _validar_hex(v)))


class Voz(_Base):
    proveedor: str = "edge"
    nombre: str = "es-CL-LorenzoNeural"
    velocidad: str = "+5%"


class Cierre(_Base):
    texto: str = "Sígueme para más ejercicios resueltos"
    voz: str = "Sígueme para más ejercicios resueltos. ¡Nos vemos en el próximo!"


class EstiloSubtitulos(_Base):
    fuente: str = "Montserrat Black"
    tamano: int = Field(default=84, ge=30, le=160)
    color: str = "#FFFFFF"
    color_activo: str = "#FFC72C"
    borde: float = Field(default=7, ge=0, le=20)
    sombra: float = Field(default=3, ge=0, le=20)
    posicion_y: float = Field(default=0.72, ge=0.3, le=0.9)  # fracción del alto (0 = arriba)
    mayusculas: bool = True
    max_palabras: int = Field(default=3, ge=1, le=8)
    max_caracteres: int = Field(default=16, ge=6, le=40)

    _hex = field_validator("color", "color_activo")(classmethod(lambda cls, v: _validar_hex(v)))


class Marca(_Base):
    nombre: str = "Tu Profe Industrial"
    usuario: str = "@tuprofeindustrial"
    colores: Colores = Colores()
    materias: ColoresMateria = ColoresMateria()
    voz: Voz = Voz()
    cierre: Cierre = Cierre()
    subtitulos: EstiloSubtitulos = EstiloSubtitulos()


def cargar_marca(ruta: Path | None = None) -> Marca:
    """Lee ``marca.yaml`` (si existe) y completa lo que falte con valores por defecto."""
    ruta = ruta or raiz_proyecto() / "marca.yaml"
    if not ruta.exists():
        return Marca()
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErrorMotor(f"marca.yaml tiene un error de formato: {e}") from e
    try:
        return Marca.model_validate(datos)
    except ValidationError as e:
        detalle = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        raise ErrorMotor(f"marca.yaml tiene valores no válidos → {detalle}") from e
