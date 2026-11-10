"""«Para hoy»: un video al día, elegido entre tres. Uno por materia, los tres del mismo nivel.

Sin NiceGUI: acá solo se decide qué proponer y por qué, para probarlo sin navegador. Las opciones
salen de los guiones que esperan revisión en QC; nada se inventa ni se escribe.

Cómo se ordena cada materia (el primero es el propuesto; «Otra» pasa al siguiente):
1° que no repita el molde del último video que salió (variedad en tu muro),
2° que ya traiga título y hashtags para redes, 3° que ya tenga vista previa al día,
4° el que lleva más tiempo esperando.
"""

from __future__ import annotations

import datetime as dt
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..config import cargar_marca
from ..entorno import raiz_proyecto
from ..errores import ErrorMotor
from ..guion import CATEGORIA_DE_MATERIA, Guion, cargar_guion, sin_tildes
from ..moldes import nombre_molde
from ..temas import NOMBRE_CATEGORIA, EstiloSugerido, estilo_del_guion
from . import qc

CATEGORIAS = ("matematicas", "fisica", "ingenieria")
# «º» (ordinal) sale como «o» después de sin_tildes: «2º medio» → «2o medio».
_NIVEL = re.compile(r"\b([1-4])\s*[°ºo]?\s*(?:ano\s+)?(?:de\s+)?medio")


def nivel_de(texto: str | None) -> str | None:
    """«3° medio», «3 medio», «4° medio · PAES» → «3° medio» / «4° medio». Lo demás no es un nivel claro."""
    m = _NIVEL.search(sin_tildes(str(texto or "")).lower())
    return f"{m.group(1)}° medio" if m else None


def _orden_nivel(nivel: str) -> int:
    return int(nivel[0]) if nivel[:1].isdigit() else 9


@dataclass(frozen=True)
class Opcion:
    ruta: Path
    titulo: str
    categoria: str
    nivel: str
    molde: str  # nombre visible ("" si no tiene)
    estilo: EstiloSugerido
    razones: tuple[str, ...]


@dataclass
class Propuesta:
    nivel: str | None  # el nivel elegido (None si no hay ningún guion con nivel claro)
    niveles: dict[str, set[str]]  # cada nivel con las materias que tienen guion
    opciones: dict[str, list[Opcion]] = field(default_factory=dict)  # por materia, la mejor primero
    hoy: list[str] = field(default_factory=list)  # títulos que ya elegiste hoy

    @property
    def completos(self) -> list[str]:
        """Los niveles donde se puede elegir entre las tres materias."""
        return [n for n in self.niveles if len(self.niveles[n]) == len(CATEGORIAS)]

    def faltan(self, nivel: str | None = None) -> list[str]:
        """Las materias sin guion en ese nivel (por defecto, el elegido)."""
        tiene = self.niveles.get(nivel or self.nivel or "", set())
        return [c for c in CATEGORIAS if c not in tiene]


def _borrador_al_dia(ruta: Path) -> bool:
    from ..render import slug

    nombre = slug(ruta.stem)
    video = raiz_proyecto() / "salida" / nombre / f"{nombre}_borrador.mp4"
    return video.exists() and video.stat().st_mtime >= ruta.stat().st_mtime


def _ultimo_molde() -> str | None:
    """El molde del último video que salió (para no repetirlo dos días seguidos)."""
    from .biblioteca import videos

    hechos = sorted(videos(), key=lambda v: v.fecha, reverse=True)
    return (hechos[0].molde or None) if hechos else None


def _dias(segundos: float) -> str:
    dias = int(segundos // 86_400)
    return (
        "Llegó hoy"
        if dias < 1
        else ("Lleva 1 día esperando" if dias == 1 else f"Lleva {dias} días esperando")
    )


def _opcion(
    ruta: Path, guion: Guion, nivel: str, ultimo: str | None, ahora: float, marca
) -> tuple[tuple, Opcion]:
    listo_redes = guion.metadatos is not None
    con_vista = _borrador_al_dia(ruta)
    repite = bool(ultimo) and guion.molde == ultimo
    razones = [_dias(ahora - ruta.stat().st_mtime)]
    if listo_redes:
        razones.append("trae título y hashtags")
    if con_vista:
        razones.append("ya tiene vista previa")
    if guion.molde and not repite and ultimo:
        razones.append(f"cambia de formato ({nombre_molde(guion.molde)})")
    elif repite:
        razones.append("repite el formato del último video")
    opcion = Opcion(
        ruta=ruta,
        titulo=guion.titulo,
        categoria=guion.categoria,
        nivel=nivel,
        molde=nombre_molde(guion.molde) if guion.molde else "",
        estilo=estilo_del_guion(guion, marca),
        razones=tuple(razones),
    )
    return (repite, not listo_redes, not con_vista, ruta.stat().st_mtime), opcion


def elegidos_hoy(hoy: dt.date | None = None) -> list[str]:
    """Los títulos de los guiones que aprobaste hoy (para decir «hoy ya elegiste»)."""
    dia = (hoy or dt.date.today()).isoformat()
    salida = []
    for ruta in qc.guiones(incluir_decididos=True):
        decision = qc.decision(ruta) or {}
        if qc.estado(ruta) == qc.APROBADO and str(decision.get("fecha", "")).startswith(dia):
            try:
                salida.append(cargar_guion(ruta).titulo)
            except ErrorMotor:
                salida.append(ruta.stem.replace("_", " "))
    return salida


def proponer(nivel: str | None = None, preferido: str | None = None) -> Propuesta:
    """Las opciones de hoy. ``nivel``: el que tocó en pantalla; ``preferido``: el de Ajustes.

    Si no se pide un nivel, va el preferido si está completo; si no, el nivel completo con más
    guiones; si ninguno está completo, el que tenga más materias.
    """
    marca = cargar_marca()
    ultimo = _ultimo_molde()
    ahora = time.time()
    candidatos: dict[str, dict[str, list[tuple[tuple, Opcion]]]] = {}
    for ruta in qc.guiones():  # solo los que esperan revisión
        try:
            guion = cargar_guion(ruta)
        except ErrorMotor:
            continue  # uno que no valida no se puede crear: se arregla en QC
        el_nivel = nivel_de(guion.nivel)
        if el_nivel is None or CATEGORIA_DE_MATERIA.get(guion.materia) is None:
            continue
        candidatos.setdefault(el_nivel, {}).setdefault(guion.categoria, []).append(
            _opcion(ruta, guion, el_nivel, ultimo, ahora, marca)
        )
    niveles = {n: set(candidatos[n]) for n in sorted(candidatos, key=_orden_nivel)}
    propuesta = Propuesta(nivel=None, niveles=niveles, hoy=elegidos_hoy())
    if not niveles:
        return propuesta
    preferido = nivel_de(preferido)
    total = {n: sum(len(v) for v in candidatos[n].values()) for n in niveles}
    if nivel in niveles:
        propuesta.nivel = nivel
    elif preferido in propuesta.completos:
        propuesta.nivel = preferido
    elif propuesta.completos:
        propuesta.nivel = max(propuesta.completos, key=lambda n: (total[n], -_orden_nivel(n)))
    else:
        propuesta.nivel = max(niveles, key=lambda n: (len(niveles[n]), total[n], -_orden_nivel(n)))
    for categoria in CATEGORIAS:
        lista = sorted(candidatos[propuesta.nivel].get(categoria, []), key=lambda par: par[0])
        propuesta.opciones[categoria] = [opcion for _clave, opcion in lista]
    return propuesta


def nombre_categoria(categoria: str) -> str:
    return NOMBRE_CATEGORIA.get(categoria, categoria)
