"""Completar los niveles: escribir con la IA los guiones que faltan para que cada nivel tenga las tres
materias (lo que «Para hoy» necesita para proponer tres del mismo nivel).

Un «hueco» es un nivel × materia sin ningún guion por revisar. Para cada hueco se elige un ramo de la
malla (y, en Ingeniería universitaria, la carrera con menos guiones en ese nivel), se le piden ideas a
la IA sobre ese ramo y se redacta la primera: el mismo camino que «tema → idea → guion» del panel.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .errores import ErrorMotor
from .guion import cargar_guion
from .malla import MATERIAS_MALLA, ramos
from .niveles import CARRERAS, NIVELES, NIVELES_MEDIA, NIVELES_UNIVERSIDAD, nombre_carrera, normalizar

NOMBRE_MATERIA = {"matematica": "Matemáticas", "fisica": "Física", "ingenieria": "Ingeniería"}


@dataclass(frozen=True)
class Hueco:
    nivel: str
    materia: str
    carrera: str | None
    ramo: str

    @property
    def texto(self) -> str:
        carrera = f" · {nombre_carrera(self.carrera)}" if self.carrera else ""
        return f"{self.nivel} · {NOMBRE_MATERIA[self.materia]}{carrera}: {self.ramo}"


def _guiones() -> tuple[list[tuple[str, str, str | None]], list[tuple[str, str, str | None]]]:
    """(los que esperan revisión, todos), como (nivel, materia, carrera)."""
    from .panel import qc

    por_revisar = {p.resolve() for p in qc.guiones()}
    pendientes, todos = [], []
    for ruta in qc.guiones(incluir_decididos=True):
        try:
            g = cargar_guion(ruta)
        except ErrorMotor:
            continue
        nivel = normalizar(g.nivel)
        if nivel is None:
            continue
        fila = (nivel, g.materia, g.carrera)
        todos.append(fila)
        if ruta.resolve() in por_revisar:
            pendientes.append(fila)
    return pendientes, todos


def huecos(publico: str = "todos", nivel: str | None = None, materia: str | None = None) -> list[Hueco]:
    """Los niveles × materias sin guion por revisar, con el ramo y la carrera que tocan."""
    niveles = {"media": NIVELES_MEDIA, "universidad": NIVELES_UNIVERSIDAD}.get(publico, NIVELES)
    if nivel:
        niveles = tuple(n for n in niveles if n == (normalizar(nivel) or nivel))
    materias = (materia,) if materia else MATERIAS_MALLA
    pendientes, todos = _guiones()
    hay = {(n, m) for n, m, _c in pendientes}
    usados = Counter(todos)
    salida = []
    for n in niveles:
        for m in materias:
            if (n, m) in hay:
                continue
            carrera = None
            if m == "ingenieria" and n in NIVELES_UNIVERSIDAD:
                carrera = min(CARRERAS, key=lambda c: (usados[(n, m, c)], list(CARRERAS).index(c)))
            opciones = ramos(n, m, carrera)
            if not opciones:
                continue
            ya = sum(v for (nn, mm, _c), v in usados.items() if (nn, mm) == (n, m))
            salida.append(Hueco(n, m, carrera, opciones[ya % len(opciones)]))
    return salida


def _escribir(h: Hueco, avisar: Callable[[str], None]) -> Path:
    from .ideas import proponer_ideas
    from .malla import pista_para_la_ia
    from .redactor import redactar

    tema = h.ramo
    if pista := pista_para_la_ia(h.nivel, h.materia, h.carrera):
        tema = f"{h.ramo}. {pista}"
    ideas = proponer_ideas(tema=tema, materia=h.materia, nivel=h.nivel, avisar=avisar)
    idea = ideas[0]
    resultado = redactar(
        idea.enunciado,
        materia=h.materia,
        nivel=h.nivel,
        carrera=h.carrera,
        molde=idea.molde or None,
        avisar=avisar,
    )
    return resultado.ruta


def completar(
    lista: list[Hueco],
    avisar: Callable[[str], None] = lambda mensaje: None,
    escribir: Callable[[Hueco, Callable[[str], None]], Path] = _escribir,
) -> tuple[list[tuple[Hueco, Path]], list[tuple[Hueco, str]]]:
    """Escribe un guion por hueco. Si uno falla, se anota y se sigue con el siguiente."""
    escritos, fallidos = [], []
    for i, h in enumerate(lista, 1):
        avisar(f"({i}/{len(lista)}) {h.texto}")
        try:
            escritos.append((h, escribir(h, avisar)))
        except ErrorMotor as e:
            fallidos.append((h, e.mensaje))
    return escritos, fallidos
