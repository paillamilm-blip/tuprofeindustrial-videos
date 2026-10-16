"""Temas visuales: todo lo que define cómo se ve un video (marco, colores, letras, fondo, subtítulos).

- Los temas incluidos están en ``plantillas/temas/``: ``hoja_de_desarrollo`` (por defecto) y
  ``pizarra_nocturna`` (el estilo original del motor).
- Los temas propios (creados en el panel) viven en ``mis_ajustes/temas/``. Git ignora esa carpeta, así
  que actualizar el motor nunca choca con ellos. Si un tema propio tiene el mismo nombre que uno
  incluido, se usa el propio.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import Colores, ColoresMateria, EstiloSubtitulos, Marca, _validar_hex
from .entorno import PAQUETE, PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor
from .tipografia import existe

TEMAS_DIR = PLANTILLAS_DIR / "temas"
FONDOS_DIR = PAQUETE / "assets" / "fondos"
TEMA_POR_DEFECTO = "hoja_de_desarrollo"


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FuenteRol(_Base):
    familia: str = "Montserrat"
    # "conservar" = cada texto usa su propio grosor (como el estilo original); o NORMAL, BOLD, HEAVY…
    grosor: str = "conservar"
    mayusculas: bool = False
    escala: float = Field(default=1.0, ge=0.5, le=2.0)

    @field_validator("familia")
    @classmethod
    def _familia(cls, v: str) -> str:
        if not existe(v):
            from .tipografia import FAMILIAS

            raise ValueError(f"no tengo la letra «{v}»; opciones: {', '.join(FAMILIAS)}")
        return v


class Tipografia(_Base):
    titulos: FuenteRol = FuenteRol()
    texto: FuenteRol = FuenteRol()


class ColoresTema(_Base):
    fondo: str = "#0B1220"
    panel: str = "#121B2F"
    borde: str = "#24324F"
    titulos: str = "#F8FAFC"
    texto: str = "#F8FAFC"
    formulas: str = "#F8FAFC"
    tenue: str = "#94A3B8"
    acento: str = "#FFC72C"
    exito: str = "#22C55E"
    cuadricula: str = "#38BDF8"
    error: str = "#EF4444"  # la ✗ y la nota del paso "error típico"

    _hex = field_validator("*")(classmethod(lambda cls, v: _validar_hex(v)))


class Nota(_Base):
    """Estilo de la nota pequeña sobre cada fórmula ("Despejamos t")."""

    rol: Literal["texto", "titulos"] = "texto"
    escala: float = Field(default=1.0, ge=0.5, le=2.5)
    color: Literal["materia", "titulos", "acento"] = "materia"


class Fondo(_Base):
    tipo: Literal["cuadricula", "imagen", "color", "degradado"] = "cuadricula"
    imagen: str = "difuminado"  # incluida (assets/fondos/) o propia (mis_ajustes/fondos/)
    degradado: list[str] = ["#1E3A8A", "#0B1220"]

    _hex = field_validator("degradado")(classmethod(lambda cls, v: [_validar_hex(c) for c in v]))


class Hoja(_Base):
    """La hoja cuadriculada del marco "hoja" (textos vacíos = no se muestran)."""

    encabezado: str = "HOJADEDESARROLLO"
    etiqueta: str = "Notas"
    fecha: str = "Fecha:"
    color: str = "#FFFFFF"
    lineas: str = "#D4D4D4"
    cuadricula: bool = True

    _hex = field_validator("color", "lineas")(classmethod(lambda cls, v: _validar_hex(v)))


class Animacion(_Base):
    # "plumon": los títulos y notas se escriben trazo a trazo, como con un plumón
    titulos: Literal["aparecer", "plumon"] = "aparecer"


class Tema(_Base):
    nombre: str
    descripcion: str = ""
    marco: Literal["pizarra", "hoja"] = "pizarra"
    # Compatibilidad: colores, materias y subtítulos salen de marca.yaml (estilo original)
    usar_marca: bool = False
    colores: ColoresTema = ColoresTema()
    materias: ColoresMateria = ColoresMateria()
    tipografia: Tipografia = Tipografia()
    nota: Nota = Nota()
    formulas_negrita: bool = True
    fondo: Fondo = Fondo()
    hoja: Hoja = Hoja()
    subtitulos: EstiloSubtitulos = EstiloSubtitulos()
    animacion: Animacion = Animacion()
    emojis: bool = True


def temas_usuario_dir() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "temas"


def fondos_usuario_dir() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "fondos"


def id_tema(nombre: str) -> str:
    """Nombre de archivo a partir de un nombre visible: "Mi Tema 2" → "mi_tema_2"."""
    from .guion import sin_tildes

    return re.sub(r"[^a-z0-9]+", "_", sin_tildes(nombre.lower())).strip("_") or "tema"


def _rutas(identificador: str) -> list[Path]:
    return [temas_usuario_dir() / f"{identificador}.yaml", TEMAS_DIR / f"{identificador}.yaml"]


def existe_tema(identificador: str) -> bool:
    return any(ruta.exists() for ruta in _rutas(identificador.strip()))


def listar_temas() -> list[tuple[str, Tema, bool]]:
    """(id, tema, es_propio) de todos los temas válidos; primero los incluidos."""
    vistos: dict[str, tuple[str, Tema, bool]] = {}
    for carpeta, propio in ((TEMAS_DIR, False), (temas_usuario_dir(), True)):
        if not carpeta.exists():
            continue
        for ruta in sorted(carpeta.glob("*.yaml")):
            try:
                vistos[ruta.stem] = (ruta.stem, _leer(ruta), propio)
            except ErrorMotor:
                continue  # un tema propio dañado no debe impedir listar los demás
    return list(vistos.values())


def _leer(ruta: Path) -> Tema:
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        return Tema.model_validate(datos)
    except (yaml.YAMLError, ValidationError) as e:
        if isinstance(e, ValidationError):
            detalle = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        else:
            detalle = str(e)
        raise ErrorMotor(f"El tema {ruta.name} tiene un error: {detalle}") from e


def _con_marca(tema: Tema, marca: Marca) -> Tema:
    c: Colores = marca.colores
    colores = ColoresTema(
        fondo=c.fondo, panel=c.panel, borde=c.borde, titulos=c.texto, texto=c.texto, formulas=c.texto,
        tenue=c.tenue, acento=c.acento, exito=c.exito, cuadricula=c.cuadricula,
    )  # fmt: skip
    return tema.model_copy(
        update={"colores": colores, "materias": marca.materias, "subtitulos": marca.subtitulos}
    )


def cargar_tema(identificador: str | None, marca: Marca) -> Tema:
    identificador = (identificador or marca.tema or TEMA_POR_DEFECTO).strip()
    for ruta in _rutas(identificador):
        if ruta.exists():
            tema = _leer(ruta)
            return _con_marca(tema, marca) if tema.usar_marca else tema
    opciones = ", ".join(t for t, _, _ in listar_temas())
    raise ErrorMotor(f"No existe el tema «{identificador}».", ayuda=f"Temas disponibles: {opciones}")


def guardar_tema(identificador: str, tema: Tema) -> Path:
    destino = temas_usuario_dir() / f"{id_tema(identificador)}.yaml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    datos = tema.model_dump(mode="json")
    destino.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destino


def ruta_fondo(nombre: str) -> Path:
    for candidato in (fondos_usuario_dir() / f"{nombre}.png", FONDOS_DIR / f"{nombre}.png", Path(nombre)):
        if candidato.exists():
            return candidato
    raise ErrorMotor(
        f"No encuentro la imagen de fondo «{nombre}».", ayuda="Elige otro fondo en el panel (Estilos)."
    )
