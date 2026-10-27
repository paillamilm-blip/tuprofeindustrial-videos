"""Los visuales que el motor sabe dibujar: gráfico de función, diagrama de fuerzas, circuito y polígono regular.

Un paso del guion puede llevar `visual:`. Aquí se analiza ese contenido (nunca con `eval` suelto)
y se devuelve lo que `componentes.py` necesita para dibujarlo, con errores en español claro.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Cuánto suma cada dibujo a la duración estimada: se revela mientras se habla, pero el ojo lo sigue mirando.
SEGUNDOS_VISUAL = {
    "grafico_funcion": 3.0,
    "diagrama_fuerzas": 2.5,
    "circuito": 3.0,
    "poligono_regular": 3.0,
    "proyectil": 3.0,
    "circulo_trig": 3.0,
    "solido": 3.0,
    "solido_3d": 3.2,  # el relieve se mira un poco más que la lámina
    "venn": 3.0,
    "recta": 2.5,
    "probabilidad": 3.0,
    "torta": 3.0,
    "barras": 2.5,
    "onda": 3.0,
    "energia": 2.5,
    "optica": 3.0,
    "pendulo": 3.0,
    "resorte": 2.5,
    "polea": 3.0,
    "tanque": 3.0,
    "viga": 3.0,
    "cercha": 3.0,
    "bloques": 3.0,
    "engranaje": 3.0,
    "mohr": 3.0,
}

# Lo que se puede anotar en un polígono regular.
MARCAS_POLIGONO = ("apotema", "radio", "angulo_central", "angulo_interior")

# Lo que se puede anotar en un tiro parabólico.
MARCAS_PROYECTIL = ("alcance", "altura_maxima", "componentes")

# Lo que se puede anotar en el círculo trigonométrico.
MARCAS_CIRCULO = ("seno", "coseno", "tangente")

# Lo que se puede anotar en un sólido.
MARCAS_SOLIDO = ("volumen", "area")

# Los cuerpos que el motor sabe dibujar como lámina de libro.
SOLIDOS = ("cubo", "cilindro", "cono", "esfera")

# Lo que se puede anotar en un diagrama de Venn y en una urna de probabilidad.
MARCAS_VENN = ("total",)
MARCAS_PROBABILIDAD = ("probabilidad",)

# Lo que se puede anotar en una onda (la amplitud y λ van siempre; la velocidad es opcional).
MARCAS_ONDA = ("velocidad",)

# Lo que se puede anotar en cada máquina: la óptica no lleva marcas (sus dos ángulos van siempre).
MARCAS_PENDULO = ("periodo",)
MARCAS_RESORTE = ("fuerza",)
MARCAS_POLEA = ("aceleracion", "tension")

# Lo que se puede anotar en un tanque con llave y fisura, una viga apoyada y una cercha.
MARCAS_TANQUE = ("llenado", "vaciado")
MARCAS_VIGA = ("reacciones", "momento")
MARCAS_CERCHA = ("esfuerzo", "angulo")

# Lo que se puede anotar en el taller: el lazo cerrado, la vuelta del eje lento y los esfuerzos.
MARCAS_BLOQUES = ("lazo_cerrado",)
MARCAS_ENGRANAJE = ("velocidad", "relacion")
MARCAS_MOHR = ("principales", "cortante")

# Lo que el motor sabe dibujar como flecha en un diagrama de fuerzas.
VECTORES: dict[str, str] = {
    "P": "Peso",
    "N": "Normal",
    "f": "Rozamiento",
    "v": "Velocidad",
    "a": "Aceleración",
    "T": "Tensión",
}

CUERPOS = ("bloque", "bola")
ARREGLOS = ("serie", "paralelo")

# --------------------------------------------------------------------------------------
# El catálogo: qué campos y qué marcas tiene cada dibujo. El panel lo lee para armar el
# formulario, así que agregar un tipo al modelo sin agregarlo acá rompe una prueba.
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CampoVisual:
    clave: str
    etiqueta: str
    forma: str = "texto"  # texto | numero | numeros | lista | opcion | booleano
    ayuda: str = ""
    opciones: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TipoVisual:
    clave: str
    nombre: str
    materia: str  # matematica | fisica | ingenieria
    icono: str
    campos: tuple[str, ...]
    marcas: tuple[str, ...] = ()
    ejemplo: dict[str, Any] = field(default_factory=dict)


_MATERIAS = {"matematica": "Matemática", "fisica": "Física", "ingenieria": "Ingeniería"}

CAMPOS: dict[str, CampoVisual] = {
    c.clave: c
    for c in [
        CampoVisual("funcion", "La función, en texto plano", "texto", "-4.9t^2 + 20   ·   12/U   ·   sin(x)"),
        CampoVisual("variable", "La variable", "texto", "t"),
        CampoVisual("eje_x", "Eje horizontal", "texto", "tiempo (s)"),
        CampoVisual("eje_y", "Eje vertical", "texto", "altura (m)"),
        CampoVisual("rango", "Rango del eje horizontal", "numeros", "0 a 2,5"),
        CampoVisual("marcar", "Puntos con su valor escrito", "numeros", "0; 2,45"),
        CampoVisual("cuerpo", "El cuerpo", "opcion", "", (("bloque", "Bloque (una caja)"), ("bola", "Bola"))),
        CampoVisual("vectores", "Flechas del cuerpo", "lista"),
        CampoVisual("angulo", "Ángulo en grados", "numero", "30"),
        CampoVisual("descomponer", "Partir el peso en P sen θ y P cos θ", "booleano"),
        CampoVisual("fuente", "La fuente", "texto", "12 V"),
        CampoVisual("arreglo", "Arreglo", "opcion", "", (("serie", "En serie"), ("paralelo", "En paralelo"))),
        CampoVisual("resistencias", "Resistencias, de 2 a 4", "lista", "4 Ω, 6 Ω"),
        CampoVisual("lados", "Lados del polígono (de 3 a 8)", "numero", "6"),
        CampoVisual("lado", "Medida de un lado o arista", "texto", "12 cm"),
        CampoVisual("anotar", "Qué anotar en el dibujo", "lista"),
        CampoVisual("velocidad", "Velocidad de lanzamiento", "texto", "20 m/s"),
        CampoVisual(
            "figura",
            "El sólido",
            "opcion",
            "",
            (("cubo", "Cubo"), ("cilindro", "Cilindro"), ("cono", "Cono"), ("esfera", "Esfera")),
        ),
        CampoVisual("radio", "Radio", "texto", "3 cm"),
        CampoVisual("altura", "Altura", "texto", "5 cm"),
        CampoVisual(
            "vista",
            "La vista",
            "opcion",
            "axonometrica es la que mejor se entiende en un video",
            (
                ("axonometrica", "Axonométrica (en relieve)"),
                ("frente", "De frente"),
                ("ala", "De lado"),
                ("piso", "Desde arriba"),
            ),
        ),
        CampoVisual(
            "corte",
            "El corte",
            "opcion",
            "mitad parte el cuerpo y pinta la cara de corte en rojo (solo cubo)",
            (("sin_corte", "Sin corte"), ("mitad", "Partido por la mitad")),
        ),
        CampoVisual("solo_a", "Cuántos sólo en A", "numero", "25"),
        CampoVisual("solo_b", "Cuántos sólo en B", "numero", "13"),
        CampoVisual("ambos", "Cuántos en los dos", "numero", "12"),
        CampoVisual("fuera", "Cuántos en ninguno", "numero", "5"),
        CampoVisual("extremo_a", "Extremo izquierdo (o el origen del rayo)", "numero", "2"),
        CampoVisual("extremo_b", "Extremo derecho (vacío = rayo)", "numero", "7"),
        CampoVisual("incluye_a", "Incluye el extremo izquierdo", "booleano"),
        CampoVisual("incluye_b", "Incluye el extremo derecho", "booleano"),
        CampoVisual("derecha", "El rayo apunta a la derecha", "booleano"),
        CampoVisual("favorables", "Casos favorables", "numero", "3"),
        CampoVisual("totales", "Casos totales", "numero", "8"),
        CampoVisual("categorias", "Categorías con su valor", "lista", "Fútbol 12, Básquetbol 8"),
        CampoVisual("amplitud", "Amplitud", "texto", "0,5 m"),
        CampoVisual("longitud_onda", "Longitud de onda (λ)", "texto", "2 m"),
        CampoVisual("periodo", "Periodo en segundos", "numero", "0,4"),
        CampoVisual("n1", "Índice del medio de origen", "numero", "1,0"),
        CampoVisual("n2", "Índice del medio al que pasa", "numero", "1,33"),
        CampoVisual("angulo_incidence", "Ángulo de incidencia (desde la normal)", "numero", "30"),
        CampoVisual("longitud", "Longitud", "texto", "1 m"),
        CampoVisual("constante", "Constante del resorte", "texto", "200 N/m"),
        CampoVisual("extension", "Extensión", "texto", "10 cm"),
        CampoVisual("masa_a", "Masa A", "texto", "3 kg"),
        CampoVisual("masa_b", "Masa B", "texto", "2 kg"),
        CampoVisual("capacidad", "Capacidad del tanque", "texto", "120 L"),
        CampoVisual("entrada", "Lo que entra por la llave", "texto", "8 L/min"),
        CampoVisual("salida", "Lo que pierde por la fisura", "texto", "2 L/min"),
        CampoVisual("carga", "La carga", "texto", "200 N"),
        CampoVisual("repartida", "La carga va repartida en todo el tramo", "booleano"),
        CampoVisual("base", "Base", "texto", "6 m"),
        CampoVisual("adelante", "Ganancia del bloque directo", "texto", "10"),
        CampoVisual("retro", "Ganancia de la realimentación", "texto", "0.2"),
        CampoVisual("negativa", "La realimentación es negativa", "booleano"),
        CampoVisual("dientes_a", "Dientes de la conductora", "texto", "20"),
        CampoVisual("dientes_b", "Dientes de la conducida", "texto", "60"),
        CampoVisual("rpm", "Vueltas del eje de entrada", "texto", "1200 rpm"),
        CampoVisual("sigma_x", "Esfuerzo normal en X", "texto", "80 MPa"),
        CampoVisual("sigma_y", "Esfuerzo normal en Y", "texto", "20 MPa"),
        CampoVisual("cortante", "Esfuerzo cortante", "texto", "30 MPa"),
    ]
}

VISUALES: dict[str, TipoVisual] = {
    t.clave: t
    for t in [
        TipoVisual(
            "grafico_funcion",
            "Gráfico de la función",
            "matematica",
            "📈",
            ("funcion", "variable", "eje_x", "eje_y", "rango", "marcar"),
            ejemplo={"funcion": "-x^2 + 4x", "eje_x": "x", "eje_y": "y"},
        ),
        TipoVisual(
            "poligono_regular",
            "Polígono regular",
            "matematica",
            "⬡",
            ("lados", "lado", "anotar"),
            MARCAS_POLIGONO,
            ejemplo={"lados": 6, "lado": "12 cm", "anotar": ["apotema", "angulo_interior"]},
        ),
        TipoVisual(
            "circulo_trig",
            "Círculo trigonométrico",
            "matematica",
            "◯",
            ("angulo", "anotar"),
            MARCAS_CIRCULO,
            ejemplo={"angulo": 30, "anotar": ["seno", "coseno"]},
        ),
        TipoVisual(
            "solido",
            "Sólido (lámina)",
            "matematica",
            "🧊",
            ("figura", "lado", "radio", "altura", "anotar"),
            MARCAS_SOLIDO,
            ejemplo={"figura": "cilindro", "radio": "3 cm", "altura": "5 cm", "anotar": ["volumen"]},
        ),
        TipoVisual(
            "solido_3d",
            "Sólido en 3D",
            "ingenieria",
            "🔷",
            ("figura", "lado", "radio", "altura", "vista", "corte", "anotar"),
            MARCAS_SOLIDO,
            ejemplo={
                "figura": "cilindro",
                "radio": "3 cm",
                "altura": "5 cm",
                "vista": "axonometrica",
                "anotar": ["volumen"],
            },
        ),
        TipoVisual(
            "venn",
            "Diagrama de Venn",
            "matematica",
            "◌◌",
            ("solo_a", "solo_b", "ambos", "fuera", "anotar"),
            MARCAS_VENN,
            ejemplo={"solo_a": 25, "solo_b": 13, "ambos": 12},
        ),
        TipoVisual(
            "recta",
            "Recta numérica",
            "matematica",
            "📏",
            ("extremo_a", "extremo_b", "incluye_a", "incluye_b", "derecha"),
            (),
            ejemplo={"extremo_a": 2, "extremo_b": 7},
        ),
        TipoVisual(
            "probabilidad",
            "Urna de probabilidad",
            "matematica",
            "🎲",
            ("favorables", "totales", "anotar"),
            MARCAS_PROBABILIDAD,
            ejemplo={"favorables": 3, "totales": 8, "anotar": ["probabilidad"]},
        ),
        TipoVisual(
            "torta",
            "Torta de porcentajes",
            "matematica",
            "🥧",
            ("categorias",),
            (),
            ejemplo={"categorias": ["Fútbol 12", "Básquetbol 8", "Natación 4"]},
        ),
        TipoVisual(
            "barras",
            "Barras de datos",
            "matematica",
            "📊",
            ("categorias",),
            (),
            ejemplo={"categorias": ["2023 40", "2024 55", "2025 70"]},
        ),
        TipoVisual(
            "diagrama_fuerzas",
            "Diagrama de fuerzas",
            "fisica",
            "➡️",
            ("cuerpo", "vectores", "angulo", "descomponer"),
            (),
            ejemplo={"cuerpo": "bloque", "vectores": ["P", "N"], "angulo": 30, "descomponer": True},
        ),
        TipoVisual(
            "proyectil",
            "Tiro parabólico",
            "fisica",
            "🎯",
            ("velocidad", "angulo", "anotar"),
            MARCAS_PROYECTIL,
            ejemplo={"velocidad": "20 m/s", "angulo": 30, "anotar": ["alcance"]},
        ),
        TipoVisual(
            "circuito",
            "Circuito",
            "fisica",
            "🔌",
            ("fuente", "arreglo", "resistencias"),
            (),
            ejemplo={"fuente": "12 V", "arreglo": "serie", "resistencias": ["4 Ω", "6 Ω"]},
        ),
        TipoVisual(
            "onda",
            "Onda anotada",
            "fisica",
            "〰️",
            ("amplitud", "longitud_onda", "periodo", "anotar"),
            MARCAS_ONDA,
            ejemplo={"amplitud": "0,5 m", "longitud_onda": "2 m", "periodo": 0.4, "anotar": ["velocidad"]},
        ),
        TipoVisual(
            "energia",
            "Barras de energía",
            "fisica",
            "🔋",
            ("categorias",),
            (),
            ejemplo={"categorias": ["Cinética 60", "Térmica 40"]},
        ),
        TipoVisual(
            "optica",
            "Refracción de la luz",
            "fisica",
            "🔦",
            ("n1", "n2", "angulo_incidence"),
            (),
            ejemplo={"n1": 1.0, "n2": 1.33, "angulo_incidence": 30},
        ),
        TipoVisual(
            "pendulo",
            "Péndulo",
            "fisica",
            "🕰️",
            ("longitud", "angulo", "anotar"),
            MARCAS_PENDULO,
            ejemplo={"longitud": "1 m", "angulo": 20, "anotar": ["periodo"]},
        ),
        TipoVisual(
            "resorte",
            "Resorte",
            "fisica",
            "🌀",
            ("constante", "extension", "anotar"),
            MARCAS_RESORTE,
            ejemplo={"constante": "200 N/m", "extension": "10 cm", "anotar": ["fuerza"]},
        ),
        TipoVisual(
            "polea",
            "Polea con dos masas",
            "fisica",
            "🪝",
            ("masa_a", "masa_b", "anotar"),
            MARCAS_POLEA,
            ejemplo={"masa_a": "3 kg", "masa_b": "2 kg", "anotar": ["aceleracion", "tension"]},
        ),
        TipoVisual(
            "tanque",
            "Tanque con llave y fisura",
            "ingenieria",
            "🛢️",
            ("capacidad", "entrada", "salida", "anotar"),
            MARCAS_TANQUE,
            ejemplo={
                "capacidad": "120 L",
                "entrada": "8 L/min",
                "salida": "2 L/min",
                "anotar": ["llenado", "vaciado"],
            },
        ),
        TipoVisual(
            "viga",
            "Viga apoyada",
            "ingenieria",
            "🏗️",
            ("longitud", "carga", "repartida", "anotar"),
            MARCAS_VIGA,
            ejemplo={"longitud": "4 m", "carga": "200 N", "anotar": ["reacciones"]},
        ),
        TipoVisual(
            "cercha",
            "Cercha",
            "ingenieria",
            "🔺",
            ("base", "altura", "carga", "anotar"),
            MARCAS_CERCHA,
            ejemplo={"base": "6 m", "altura": "2 m", "carga": "500 N", "anotar": ["esfuerzo"]},
        ),
        TipoVisual(
            "bloques",
            "Lazo de control",
            "ingenieria",
            "📦",
            ("adelante", "retro", "negativa", "anotar"),
            MARCAS_BLOQUES,
            ejemplo={"adelante": "10", "retro": "0.2", "anotar": ["lazo_cerrado"]},
        ),
        TipoVisual(
            "engranaje",
            "Pareja de engranajes",
            "ingenieria",
            "⚙️",
            ("dientes_a", "dientes_b", "rpm", "anotar"),
            MARCAS_ENGRANAJE,
            ejemplo={
                "dientes_a": "20",
                "dientes_b": "60",
                "rpm": "1200 rpm",
                "anotar": ["velocidad", "relacion"],
            },
        ),
        TipoVisual(
            "mohr",
            "Círculo de Mohr",
            "ingenieria",
            "📐",
            ("sigma_x", "sigma_y", "cortante", "anotar"),
            MARCAS_MOHR,
            ejemplo={
                "sigma_x": "80 MPa",
                "sigma_y": "20 MPa",
                "cortante": "30 MPa",
                "anotar": ["principales"],
            },
        ),
    ]
}


def opciones_select() -> dict[str, str]:
    """La lista del selector: 'Matemática · Polígono regular'. ui.select no acepta optgroup, así que
    la materia va escrita en la etiqueta y el orden agrupa."""
    salida = {"": "Sin dibujo"}
    for materia in ("matematica", "fisica", "ingenieria"):
        for tipo in VISUALES.values():
            if tipo.materia == materia:
                salida[tipo.clave] = f"{_MATERIAS[materia]} · {tipo.nombre}"
    return salida


_MUESTREO = 401  # puntos con los que se buscan raíces y vértices


@dataclass
class Funcion:
    """Una función de una variable, lista para trazar, con lo que vale la pena marcar."""

    expresion: str
    variable: str
    evaluar: Callable[[float], float | None]
    rango_x: tuple[float, float]
    puntos: list[float] = field(default_factory=list)  # marcas sobre la curva (raíces y vértice)
    vertice: tuple[float, float] | None = None

    def y(self, x: float) -> float | None:
        try:
            valor = self.evaluar(x)
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return None
        if valor is None or isinstance(valor, complex) or not math.isfinite(float(valor)):
            return None
        return float(valor)

    def rango_y(self) -> tuple[float, float]:
        """Altura del cuadro: si hay una asíntota, se recorta el disparo para que la curva se vea."""
        ys = sorted(v for v in (self.y(x) for x in self._muestras()) if v is not None)
        if not ys:
            return -1.0, 1.0
        bajo, alto = ys[0], ys[-1]
        c0, c1 = ys[int(0.05 * (len(ys) - 1))], ys[int(0.95 * (len(ys) - 1))]
        if alto - bajo > 4 * max(c1 - c0, 1e-6):
            bajo, alto = c0, c1
        if alto - bajo < 1e-6:
            return _bonito(bajo - 1.0), _bonito(alto + 1.0)
        margen = (alto - bajo) * 0.15
        return _bonito(bajo - margen), _bonito(alto + margen)

    def _muestras(self) -> list[float]:
        (x0, x1) = self.rango_x
        paso = (x1 - x0) / (_MUESTREO - 1)
        return [x0 + i * paso for i in range(_MUESTREO)]


@dataclass
class Poligono:
    """Un polígono regular: su forma y todo lo que vale la pena anotar encima.

    ``vertices`` viene en las mismas unidades de la medida del guion, centrado en el origen, de
    modo que el dibujo solamente tiene que encajarlo en su franja.
    """

    lados: int
    lado: float
    unidad: str
    apotema: float
    radio: float
    angulo_interior: float
    angulo_central: float
    vertices: list[tuple[float, float]] = field(default_factory=list)


def _bonito(valor: float) -> float:
    """Redondea a un decimal «de pizarra» para que los ejes no salgan con 3,999999 (ni con -0)."""
    return 0.0 if round(valor, 2) == 0 else round(valor, 2)


def _analizar_funcion(texto: str, variable: str | None) -> tuple[Any, Any]:
    """Devuelve (expresión sympy, símbolo). Errores en español para que el profe los entienda."""
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    # «x^2» es potencia y «9,8» es decimal con coma chilena: ambas llegan escritas así.
    limpio = re.sub(r"(?<=\d),(?=\d)", ".", (texto or "").strip()).replace("^", "**").replace("−", "-")
    if not limpio:
        raise ValueError("el gráfico necesita una función, por ejemplo: funcion: '-x**2 + 4*x'")
    try:
        expr = parse_expr(
            limpio,
            transformations=standard_transformations + (implicit_multiplication_application,),
            evaluate=True,
        )
    except Exception as e:  # sympy lanza de todo según el error
        raise ValueError(f"no entiendo la función «{texto}» ({type(e).__name__}: {e})") from e
    libres = sorted(expr.free_symbols, key=str)
    if not libres:
        raise ValueError(f"«{texto}» no tiene ninguna variable; escribe algo como '2*x + 3'")
    if len(libres) > 1:
        nombres = ", ".join(str(s) for s in libres)
        raise ValueError(f"«{texto}» tiene más de una variable ({nombres}); el gráfico es de una sola")
    simbolo = libres[0]
    if variable and variable.strip() and variable.strip() != str(simbolo):
        raise ValueError(f"la función usa «{simbolo}», pero el guion dice variable: '{variable}'")
    return expr, simbolo


def _biseccion(f: Callable[[float], float | None], a: float, b: float) -> float | None:
    fa, fb = f(a), f(b)
    if fa is None or fb is None or fa * fb > 0:
        return None
    for _ in range(60):
        m = (a + b) / 2
        fm = f(m)
        if fm is None:
            return None
        if abs(fm) < 1e-12 or (b - a) < 1e-9:
            return m
        if fa * fm <= 0:
            b, fb = m, fm
        else:
            a, fa = m, fm
    return (a + b) / 2


def _cambios_de_signo(pares: list[tuple[float, float]], f: Callable[[float], float | None]) -> list[float]:
    """Raíces de una serie muestreada, afinadas por bisección sobre la función real.

    Si la bisección falla es porque entre los dos puntos la función no existe (un 1/x en el 0),
    así que ese salto se descarta: una asíntota vertical no es una raíz.
    """
    puntos: list[float] = []
    for (x0, y0), (x1, y1) in zip(pares, pares[1:], strict=False):
        if y0 == 0.0:
            puntos.append(x0)
        elif y0 * y1 < 0:
            r = _biseccion(f, x0, x1)
            if r is not None:
                puntos.append(r)
    return _sin_repetidos(puntos)


def _sin_repetidos(valores: list[float], tolerancia: float = 0.05) -> list[float]:
    """Puntos redondeados a lo que se puede escribir en la pizarra, sin duplicados."""
    salida: list[float] = []
    for v in sorted(_bonito(x) for x in valores):
        if not salida or abs(v - salida[-1]) > tolerancia:
            salida.append(v)
    return salida


def _muestrear(ventana: tuple[float, float], f: Callable[[float], float | None]) -> list[tuple[float, float]]:
    x0, x1 = ventana
    pares: list[tuple[float, float]] = []
    for i in range(_MUESTREO):
        x = x0 + (x1 - x0) * i / (_MUESTREO - 1)
        y = f(x)
        if y is not None:
            pares.append((x, y))
    return pares


def _vertice(
    pares: list[tuple[float, float]], f: Callable[[float], float | None]
) -> tuple[float, float] | None:
    """El máximo o mínimo, solo si la curva tiene exactamente uno (una parábola; no un seno)."""
    pendiente = [
        (x0, (y1 - y0) / (x1 - x0)) for (x0, y0), (x1, y1) in zip(pares, pares[1:], strict=False) if x1 != x0
    ]
    cambios = [(x0, x1) for (x0, p0), (x1, p1) in zip(pendiente, pendiente[1:], strict=False) if p0 * p1 < 0]
    if len(cambios) != 1:
        return None
    a, b = cambios[0]
    h = max((b - a) / 4, 1e-9)

    def derivada(x: float) -> float | None:
        ya, yb = f(x - h), f(x + h)
        return None if ya is None or yb is None else (yb - ya) / (2 * h)

    vx = _biseccion(derivada, a, b)
    if vx is None:
        vx = (a + b) / 2
    vy = f(vx)
    return None if vy is None else (_bonito(vx), _bonito(vy))


def _rango_por_defecto(raices: list[float], vertice_x: float | None) -> tuple[float, float]:
    """La ventana que se entiende en un celular, alrededor de lo que pasa cerca del eje Y.

    `sen(x)` tiene decenas de raíces en la pasada amplia: tomar la primera y la última dejaría
    una onda diminuta en el medio del cuadro, así que se mira el grupo de 2 o 3 que cruza el 0.
    """
    r = sorted(raices)
    if len(r) >= 2:
        tramos = [r[i : i + 2] for i in range(len(r) - 1)] + [r[i : i + 3] for i in range(len(r) - 2)]
        grupo = min(tramos, key=lambda t: abs((t[0] + t[-1]) / 2) - 0.3 * (t[-1] - t[0]))
        x0, x1 = grupo[0], grupo[-1]
        margen = max(x1 - x0, 1.0) * 0.35
        return _bonito(x0 - margen), _bonito(x1 + margen)
    if len(raices) == 1:
        return _bonito(raices[0] - 5), _bonito(raices[0] + 5)
    if vertice_x is not None:
        return _bonito(vertice_x - 4), _bonito(vertice_x + 4)
    return -5.0, 5.0


def analizar_funcion(
    texto: str,
    variable: str | None = None,
    rango: list[float] | None = None,
    marcar: list[float] | None = None,
) -> Funcion:
    """Lee `funcion:` del guion y calcula raíces, vértice y un rango que se entienda en el celular."""
    from sympy import lambdify

    expr, simbolo = _analizar_funcion(texto, variable)
    nombre = str(simbolo)
    crudo = lambdify(simbolo, expr, modules="math")

    def evaluar(x: float) -> float | None:
        """Nada de excepciones: un 1/0 o una raíz de número negativo simplemente no devuelven punto."""
        try:
            valor = crudo(float(x))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return None
        if valor is None or isinstance(valor, complex):
            return None
        valor = float(valor)
        return valor if math.isfinite(valor) else None

    ventana: tuple[float, float] | None = None
    if rango:
        if len(rango) != 2:
            raise ValueError("el rango son dos números: el mínimo y el máximo, ej. rango: [0, 5]")
        x0, x1 = float(rango[0]), float(rango[1])
        if not (math.isfinite(x0) and math.isfinite(x1)) or x0 >= x1:
            raise ValueError(f"el rango de {nombre} no sirve: [{rango[0]}, {rango[1]}]")
        ventana = (x0, x1)

    pares = _muestrear(ventana or (-10.0, 10.0), evaluar)
    if len(pares) < 2:
        raise ValueError(f"«{texto}» no entrega números en la ventana mirada; prueba otra función")

    raices = _cambios_de_signo(pares, evaluar)
    vertice = _vertice(pares, evaluar)
    if ventana is None:
        ventana = _rango_por_defecto(
            [r for r in raices if -10.0 <= r <= 10.0], vertice[0] if vertice else None
        )
        raices = [r for r in raices if ventana[0] <= r <= ventana[1]]

    marcas: list[float] = []
    for p in list(marcar or []):
        if not math.isfinite(float(p)) or not (ventana[0] <= float(p) <= ventana[1]):
            raise ValueError(f"el punto marcado {p} queda fuera del rango [{ventana[0]}, {ventana[1]}]")
        marcas.append(float(p))
    if not marcas:
        # Sin `marcar:`, se rotulan las raíces más céntricas (tres como mucho) y el vértice.
        marcas = sorted(_bonito(r) for r in sorted(raices, key=lambda r: abs(r))[:3])
        if vertice and vertice[0] not in marcas:
            marcas.append(vertice[0])

    return Funcion(
        expresion=re.sub(r"\s+", " ", (texto or "").strip()),
        variable=nombre,
        evaluar=evaluar,
        rango_x=ventana,
        puntos=_sin_repetidos(marcas),
        vertice=vertice,
    )


def normalizar_vectores(valores: list[str]) -> list[str]:
    """Acepta las flechas sin distinguir mayúsculas y las devuelve como las conoce el motor.

    «f», «v» y «a» son minúsculas a propósito (rozamiento, velocidad, aceleración), así que
    no se pueden pasar a mayúsculas: se busca el símbolo canónico ignoriendo las mayúsculas.
    """
    canonicos = {clave.lower(): clave for clave in VECTORES}
    salida: list[str] = []
    for v in valores:
        clave = canonicos.get(str(v).strip().lower())
        if clave is None:
            raise ValueError(f"no sé dibujar la flecha «{v}»; usa las que conozco: {', '.join(VECTORES)}")
        if clave not in salida:
            salida.append(clave)
    if not salida:
        raise ValueError("el diagrama necesita al menos una flecha, ej. vectores: ['P', 'N']")
    return salida


def analizar_circuito(fuente: str | None, resistencias: list[str]) -> tuple[float, list[float]]:
    """Saca el número de «12 V» y de «4 Ω»; sin eso no hay proporciones que dibujar."""

    def numero(valor: str, que: str, ejemplo: str) -> float:
        m = re.search(r"-?\d+(?:[.,]\d+)?", str(valor or ""))
        if not m:
            raise ValueError(f"{que} necesita un número con su unidad, ej. «{ejemplo}»")
        n = float(m.group().replace(",", "."))
        if n <= 0:
            raise ValueError(f"{que} debe ser un número positivo, y leí «{valor}»")
        return n

    if not fuente:
        raise ValueError("el circuito necesita la fuente, ej. fuente: '12 V'")
    if len(resistencias) < 2:
        raise ValueError("el circuito necesita al menos dos resistencias para verse algo")
    if len(resistencias) > 4:
        raise ValueError("con más de 4 resistencias el dibujo ya no se entiende en un celular")
    return numero(fuente, "la fuente", "9 V"), [
        numero(r, f"la resistencia #{i}", "4 Ω") for i, r in enumerate(resistencias, 1)
    ]


def analizar_poligono(lados: int, lado: str | None) -> Poligono:
    """Todo lo que se puede saber de un polígono regular sabiendo cuántos lados tiene y cuánto mide uno.

    La base queda apoyada horizontal a propósito: un cuadrado que se sostiene en una punta se lee
    mal en la pantalla del celular, aunque geométricamente sea el mismo cuadrado.
    """
    if lados < 3:
        raise ValueError(f"un polígono necesita 3 lados o más, y el guion pide {lados}")
    texto = str(lado or "").strip()
    m = re.search(r"\d+(?:[.,]\d+)?", texto)
    if not m:
        raise ValueError(f"la medida del lado necesita un número, ej. «12 cm»; el guion dice «{lado}»")
    valor = float(m.group().replace(",", "."))
    if valor <= 0:
        raise ValueError(f"el lado debe medir más que cero, y leí «{lado}»")

    mitad = math.pi / lados
    radio = valor / (2 * math.sin(mitad))
    desfase = 90.0 if lados % 2 else 90.0 + 180.0 / lados
    vertices = [
        (
            radio * math.cos(math.radians(desfase + k * 360.0 / lados)),
            radio * math.sin(math.radians(desfase + k * 360.0 / lados)),
        )
        for k in range(lados)
    ]
    return Poligono(
        lados=lados,
        lado=valor,
        unidad=texto[m.end() :].strip().split("/")[0],
        apotema=valor / (2 * math.tan(mitad)),
        radio=radio,
        angulo_interior=(lados - 2) * 180.0 / lados,
        angulo_central=360.0 / lados,
        vertices=vertices,
    )


@dataclass
class Proyectil:
    """Un lanzamiento sin roce: el vuelo completo resuelto desde la velocidad inicial."""

    velocidad: float
    angulo: float
    unidad: str  # la de las distancias: de «20 m/s» sale «m»
    tiempo: float  # s, del lanzamiento a la caída
    alcance: float  # m, cuánto avanza en horizontal
    altura: float  # m, lo más alto que llega
    horizontal: float  # m/s, la componente que no cambia nunca
    vertical: float  # m/s, la componente con la que parte hacia arriba


def analizar_proyectil(velocidad: str | None, angulo: float, gravedad: float = 9.8) -> Proyectil:
    """Saca el número de «20 m/s» y resuelve el vuelo con las componentes de la velocidad."""
    texto = str(velocidad or "")
    m = re.search(r"-?\d+(?:[.,]\d+)?", texto)
    if not m:
        raise ValueError(
            f"la velocidad de lanzamiento necesita un número con su unidad, ej. «20 m/s», y leí «{texto}»"
        )
    v0 = float(m.group().replace(",", "."))
    if v0 <= 0:
        raise ValueError(f"la velocidad de lanzamiento debe ser positiva, y leí «{texto}»")
    if not 0 < angulo < 90:
        raise ValueError(f"el ángulo de lanzamiento va entre 0 y 90 grados, y dice {angulo}")
    rad = math.radians(angulo)
    vertical = v0 * math.sin(rad)
    horizontal = v0 * math.cos(rad)
    tiempo = 2 * vertical / gravedad
    return Proyectil(
        velocidad=v0,
        angulo=angulo,
        unidad=texto[m.end() :].strip().split("/")[0],
        tiempo=tiempo,
        alcance=horizontal * tiempo,
        altura=vertical**2 / (2 * gravedad),
        horizontal=horizontal,
        vertical=vertical,
    )


@dataclass
class AnguloTrig:
    """Un ángulo en el círculo: el punto donde cae el radio y las tres razones que se ven ahí."""

    grados: float  # ya dentro de la vuelta (0 a 360)
    seno: float
    coseno: float
    tangente: float | None  # None en 90° y 270°: ahí la recta del radio nunca toca la tangente
    cuadrante: int  # 1 a 4


def analizar_angulo(grados: float) -> AnguloTrig:
    """Resuelve el ángulo en el círculo unitario: 390° es lo mismo que 30°."""
    g = float(grados) % 360.0
    rad = math.radians(g)
    seno, coseno = math.sin(rad), math.cos(rad)
    tangente = None if abs(coseno) < 1e-9 else seno / coseno
    return AnguloTrig(
        grados=g,
        seno=seno,
        coseno=coseno,
        tangente=tangente,
        cuadrante=int(g // 90) % 4 + 1,
    )


@dataclass
class Solido:
    """Un cuerpo de los de siempre, con su volumen y su área ya resueltos."""

    figura: str  # cubo, cilindro, cono o esfera
    unidad: str  # la de las medidas: de «3 cm» sale «cm»
    volumen: float
    area: float  # el área total de su superficie
    radio: float | None = None
    altura: float | None = None
    lado: float | None = None


def _medida_solido(texto: str | None, nombre: str, hasta_barra: bool = False) -> tuple[float, str]:
    """Saca el número y la unidad de «3 cm»; si no hay número, lo dice en español.

    Con `hasta_barra` se conserva lo que va después de la «/», que hace falta en un caudal.
    """
    crudo = str(texto or "")
    m = re.search(r"-?\d+(?:[.,]\d+)?", crudo)
    if not m:
        raise ValueError(
            f"la medida de {nombre} necesita un número con su unidad, ej. «3 cm», y leí «{crudo}»"
        )
    valor = float(m.group().replace(",", "."))
    if valor <= 0:
        raise ValueError(f"la medida de {nombre} debe ser positiva, y leí «{crudo}»")
    resto = crudo[m.end() :].strip()
    return valor, resto if hasta_barra else resto.split("/")[0]


def analizar_solido(
    figura: str, lado: str | None = None, radio: str | None = None, altura: str | None = None
) -> Solido:
    """Resuelve el cuerpo con las fórmulas del cuaderno (el cono usa su generatriz)."""
    if figura not in SOLIDOS:
        raise ValueError(f"el motor sabe dibujar {', '.join(SOLIDOS)}, y le pedí «{figura}»")
    medidas: dict[str, float] = {}
    unidad = ""
    for nombre, crudo in (("lado", lado), ("radio", radio), ("altura", altura)):
        if crudo not in (None, ""):
            valor, uni = _medida_solido(crudo, nombre)
            medidas[nombre] = valor
            unidad = uni or unidad

    def exigir(*nombres: str) -> None:
        for nombre in nombres:
            if nombre not in medidas:
                raise ValueError(
                    f"el {figura} necesita la medida de {nombre} con su unidad, ej. {nombre}: '3 cm'"
                )

    if figura == "cubo":
        exigir("lado")
        a = medidas["lado"]
        volumen, area = a**3, 6 * a * a
    elif figura == "esfera":
        exigir("radio")
        r = medidas["radio"]
        volumen, area = 4 * math.pi * r**3 / 3, 4 * math.pi * r * r
    elif figura == "cilindro":
        exigir("radio", "altura")
        r, h = medidas["radio"], medidas["altura"]
        volumen, area = math.pi * r * r * h, 2 * math.pi * r * (r + h)
    else:
        exigir("radio", "altura")
        r, h = medidas["radio"], medidas["altura"]
        volumen, area = math.pi * r * r * h / 3, math.pi * r * (r + math.hypot(r, h))
    return Solido(
        figura=figura,
        unidad=unidad,
        volumen=volumen,
        area=area,
        radio=medidas.get("radio"),
        altura=medidas.get("altura"),
        lado=medidas.get("lado"),
    )


@dataclass
class Venn:
    """Dos conjuntos que se cruzan: cuántos viven en cada una de las cuatro regiones."""

    solo_a: int
    solo_b: int
    ambos: int
    fuera: int
    total: int


def analizar_venn(solo_a: int, solo_b: int, ambos: int, fuera: int = 0) -> Venn:
    """Suma las cuatro regiones; ningún contaje puede faltar ni ser negativo."""
    regiones = {"solo A": solo_a, "solo B": solo_b, "ambos": ambos, "fuera": fuera}
    for nombre, valor in regiones.items():
        if valor is None or int(valor) < 0:
            raise ValueError(f"el contaje de «{nombre}» no puede ser negativo ni faltar, y leí «{valor}»")
    valores = [int(v) for v in regiones.values()]
    return Venn(valores[0], valores[1], valores[2], valores[3], sum(valores))


@dataclass
class Recta:
    """La recta numérica con un intervalo o un rayo marcado, y la ventana donde se dibuja."""

    a: float
    b: float | None
    incluye_a: bool
    incluye_b: bool
    derecha: bool  # hacia dónde apunta el rayo cuando no hay b
    es_rayo: bool
    x0: float  # ventana visible de la recta
    x1: float


def analizar_recta(
    a: float, b: float | None = None, incluye_a: bool = True, incluye_b: bool = True, derecha: bool = True
) -> Recta:
    """Deja la ventana con aire a los lados: el intervalo nunca toca el borde de la hoja."""
    a = float(a)
    if b is None:
        x0, x1 = (a - 1.5, a + 4.5) if derecha else (a - 4.5, a + 1.5)
        return Recta(a, None, incluye_a, incluye_b, derecha, True, x0, x1)
    b = float(b)
    if b <= a:
        raise ValueError(
            f"el extremo derecho de la recta debe ser mayor que el izquierdo: {b} no es mayor que {a}"
        )
    pad = max(1.0, (b - a) * 0.35)
    return Recta(a, b, incluye_a, incluye_b, derecha, False, a - pad, b + pad)


@dataclass
class Probabilidad:
    """La regla de Laplace: casos favorables sobre casos totales."""

    favorables: int
    totales: int
    p: float


def analizar_probabilidad(favorables: int, totales: int) -> Probabilidad:
    f, t = int(favorables), int(totales)
    if t <= 0:
        raise ValueError(f"los casos totales deben ser al menos 1, y leí {t}")
    if not 0 <= f <= t:
        raise ValueError(f"los casos favorables van entre 0 y los totales ({t}), y leí {f} favorables")
    return Probabilidad(f, t, f / t)


@dataclass
class Categoria:
    """Un pedazo de los datos: su nombre, su valor y la fracción que ocupa del total."""

    nombre: str
    valor: float
    fraccion: float


@dataclass
class Torta:
    """Las porciones de la torta, listas para convertirse en ángulos."""

    categorias: list[Categoria]
    total: float


@dataclass
class Barras:
    """Las barras, con el total y el valor más alto para escalar la altura."""

    categorias: list[Categoria]
    total: float
    maximo: float


def _leer_categorias(categorias: list[str]) -> list[tuple[str, float]]:
    """De una lista como ['Fútbol 12', ...] saca (nombre, valor); el número va al final."""
    lista = list(categorias or [])
    if len(lista) < 2 or len(lista) > 6:
        raise ValueError(
            f"una torta o unas barras van entre dos y seis categorías para que se lean en el celular, y leí {len(lista)}"
        )
    pares: list[tuple[str, float]] = []
    for entrada in lista:
        texto = str(entrada).strip()
        coincidencia = re.match(r"^(.*?)\s+(-?\d+(?:[.,]\d+)?)$", texto)
        if not coincidencia:
            raise ValueError(
                f"la categoría «{texto}» no termina en un número; escribe por ejemplo «Fútbol 12»"
            )
        nombre = coincidencia.group(1).strip()
        valor = float(coincidencia.group(2).replace(",", "."))
        pares.append((nombre, valor))
    return pares


def analizar_torta(categorias: list[str]) -> Torta:
    pares = _leer_categorias(categorias)
    for nombre, valor in pares:
        if valor <= 0:
            raise ValueError(
                f"el valor de «{nombre}» debe ser positivo (una porción de torta no puede ser {valor})"
            )
    total = sum(v for _, v in pares)
    datos = [Categoria(nombre, valor, valor / total) for nombre, valor in pares]
    return Torta(datos, total)


def analizar_barras(categorias: list[str]) -> Barras:
    pares = _leer_categorias(categorias)
    for nombre, valor in pares:
        if valor <= 0:
            raise ValueError(f"el valor de «{nombre}» debe ser positivo (una barra no puede medir {valor})")
    total = sum(v for _, v in pares)
    maximo = max(v for _, v in pares)
    datos = [Categoria(nombre, valor, valor / total) for nombre, valor in pares]
    return Barras(datos, total, maximo)


@dataclass
class Onda:
    """Una onda transversal: amplitud y longitud de onda, y lo que se pueda deducir del período."""

    amplitud: float
    longitud: float  # lambda, la distancia entre dos crestas
    unidad: str  # la de las medidas: de «2 m» sale «m»
    periodo: float | None  # segundos entre dos crestas
    frecuencia: float | None  # 1 / periodo
    velocidad: float | None  # lambda / periodo


def analizar_onda(amplitud: str, longitud_onda: str, periodo: float | None = None) -> Onda:
    """Con período dice frecuencia y velocidad (v = λ/T); sin él, solo dibuja la forma."""
    a, uni_a = _medida_solido(amplitud, "amplitud")
    lam, uni_l = _medida_solido(longitud_onda, "longitud de onda")
    if periodo is None:
        return Onda(a, lam, uni_a or uni_l, None, None, None)
    T = float(periodo)
    if T <= 0:
        raise ValueError(f"el período debe ser positivo (es un tiempo), y leí {T}")
    return Onda(a, lam, uni_a or uni_l, T, 1.0 / T, lam / T)


@dataclass
class Energia:
    """La energía total repartida en sus formas: cada tramo con su fracción del todo."""

    tramos: list[Categoria]
    total: float


def analizar_energia(categorias: list[str]) -> Energia:
    pares = _leer_categorias(categorias)
    for nombre, valor in pares:
        if valor <= 0:
            raise ValueError(f"la energía en «{nombre}» debe ser positiva (un tramo no puede ser {valor})")
    total = sum(v for _, v in pares)
    tramos = [Categoria(nombre, valor, valor / total) for nombre, valor in pares]
    return Energia(tramos, total)


@dataclass
class Optica:
    """La refracción de Snell: el ángulo que sale y el crítico por si hay reflexión total."""

    n1: float
    n2: float
    incidencia: float  # grados medidos desde la normal
    refraccion: float | None  # None = reflexión total: el raye no pasa al segundo medio
    critico: float | None  # sólo existe cuando se viene de un medio más denso


def analizar_optica(n1: float, n2: float, incidencia: float) -> Optica:
    a, b = float(n1), float(n2)
    if a <= 0 or b <= 0:
        raise ValueError(f"los índices de refracción deben ser positivos, y leí {a} y {b}")
    g = float(incidencia)
    if not 0 <= g < 90:
        raise ValueError(f"el ángulo de incidencia va de 0 a 90 grados (medido desde la normal), y dice {g}")
    sen_r = a * math.sin(math.radians(g)) / b
    critico = math.degrees(math.asin(b / a)) if a > b else None
    if sen_r > 1:
        return Optica(a, b, g, None, critico)
    return Optica(a, b, g, math.degrees(math.asin(sen_r)), critico)


@dataclass
class Pendulo:
    """Un hilo con un peso al cabo: su período solo depende del largo (y de la gravedad)."""

    longitud: float
    unidad: str
    angulo: float  # cuánto se apartó de la vertical, en grados
    periodo: float


def analizar_pendulo(longitud: str, angulo: float, gravedad: float = 9.8) -> Pendulo:
    L, uni = _medida_solido(longitud, "longitud")
    a = float(angulo)
    if not 0 < a < 90:
        raise ValueError(
            f"el ángulo del péndulo va entre 0 y 90 grados (lo que se aparta de la vertical), y dice {a}"
        )
    # El período se calcula en metros: «80 cm» son 0,8 m, no 80.
    return Pendulo(L, uni, a, 2 * math.pi * math.sqrt(_a_metros(L, uni) / gravedad))


@dataclass
class Resorte:
    """La ley de Hooke: cuánto cuesta estirar el resorte lo dice su constante."""

    constante: float  # N/m
    extension: float  # ya en metros
    fuerza: float


def _a_metros(valor: float, unidad: str) -> float:
    if unidad.startswith("mm"):
        return valor / 1000
    if unidad.startswith("cm"):
        return valor / 100
    return valor


def analizar_resorte(constante: str, extension: str) -> Resorte:
    k, _ = _medida_solido(constante, "constante")
    x, uni_x = _medida_solido(extension, "extensión")
    x_m = _a_metros(x, uni_x)
    return Resorte(k, x_m, k * x_m)


@dataclass
class Polea:
    """La máquina de Atwood: la diferencia de masas manda y el conjunto entero se mueve."""

    m1: float
    m2: float
    aceleracion: float
    tension: float
    unidad: str = ""  # la de las masas: de «3 kg» sale «kg»


def analizar_polea(masa_a: str, masa_b: str, gravedad: float = 9.8) -> Polea:
    m1, uni = _medida_solido(masa_a, "masa A")
    m2, uni_b = _medida_solido(masa_b, "masa B")
    if m1 == m2:
        raise ValueError("con masas iguales la polea no se mueve: el video necesita otra pregunta")
    a = abs(m1 - m2) * gravedad / (m1 + m2)
    tension = 2 * m1 * m2 * gravedad / (m1 + m2)
    return Polea(m1, m2, a, tension, uni or uni_b)


# ---------------------------------------------------------------- tanque, viga y cercha


@dataclass
class Tanque:
    """El clásico de «entra y se escapa»: con la fisura el tanque tarda más y nunca se vacía solo."""

    capacidad: float
    unidad: str  # la del volumen: de «120 L» sale «L»
    entrada: float
    salida: float | None
    neto: float
    llenado: float  # capacidad / neto
    vaciado: float | None  # capacidad / salida; None si no hay fisura
    unidad_tiempo: str  # de «8 L/min» sale «min»


def _caudal(texto: str | None, nombre: str) -> tuple[float, str, str]:
    """Un caudal va siempre en «algo por tiempo»: 8 L/min, 1,5 m³/h."""
    valor, unidad = _medida_solido(texto, nombre, hasta_barra=True)
    if "/" not in unidad:
        raise ValueError(f"el caudal de {nombre} va por unidad de tiempo, ej. «8 L/min», y leí «{texto}»")
    volumen, tiempo = unidad.split("/", 1)
    return valor, volumen.strip(), tiempo.strip()


def analizar_tanque(capacidad: str, entrada: str, salida: str | None = None) -> Tanque:
    """Resuelve el tanque que se llena con una fisura abierta."""
    litros, uni = _medida_solido(capacidad, "capacidad")
    q_in, _, tiempo = _caudal(entrada, "entrada")
    q_out = None
    if (salida or "").strip():
        q_out, _, tiempo_out = _caudal(salida, "salida")
        if tiempo_out != tiempo:
            raise ValueError(
                f"la entrada mide en «por {tiempo}» y la salida en «por {tiempo_out}»: usan la misma unidad"
            )
    neto = q_in - (q_out or 0.0)
    if neto <= 0:
        raise ValueError(
            f"entra {q_in:g} y sale {(q_out or 0):g}: el tanque nunca se llena, el video necesita otra pregunta"
        )
    return Tanque(
        litros,
        uni,
        q_in,
        q_out,
        neto,
        litros / neto,
        litros / q_out if q_out else None,
        tiempo,
    )


@dataclass
class Viga:
    """Viga apoyada de luz L: con carga al centro o repartida, los apoyos y el momento máximo."""

    longitud: float
    unidad: str  # la del vano: de «4 m» sale «m»
    carga: float  # P en N, o w en N/m si viene repartida
    unidad_carga: str
    reaccion: float  # cada apoyo aguanta la mitad
    momento: float  # PL/4 o wL²/8, en el centro
    repartida: bool = False


def analizar_viga(longitud: str, carga: str, repartida: bool = False) -> Viga:
    """Aplica las fórmulas de la viga simplemente apoyada que salen en cualquier ramo."""
    L, uni = _medida_solido(longitud, "luz de la viga")
    valor, uni_carga = _medida_solido(carga, "carga de la viga", hasta_barra=True)
    if repartida:
        # w va en N/m: si el guion escribió «50 N» sin la barra, la pantalla mentiría.
        if "/" not in uni_carga:
            raise ValueError(f"una carga repartida se mide por metro, ej. «50 N/m», y leí «{carga}»")
        total = valor * L  # la carga repartida pesa sobre toda la luz
        momento = valor * L * L / 8.0
    else:
        total = valor
        momento = valor * L / 4.0
    return Viga(L, uni, valor, uni_carga, total / 2.0, momento, repartida)


@dataclass
class Cercha:
    """Cercha triangular simétrica: la carga al vértice se reparte en los dos paños inclinados."""

    base: float
    altura: float
    unidad: str
    carga: float
    unidad_carga: str
    angulo: float  # inclinación del paño sobre la horizontal, en grados
    esfuerzo: float  # P / (2 sen θ)
    reaccion: float  # P / 2


def analizar_cercha(base: str, altura: str, carga: str) -> Cercha:
    """El paño más tendido aguanta más: por eso una cercha baja da un esfuerzo mayor."""
    b, uni = _medida_solido(base, "base de la cercha")
    h, _ = _medida_solido(altura, "altura de la cercha")
    p, uni_carga = _medida_solido(carga, "carga de la cercha")
    angulo = math.degrees(math.atan2(h, b / 2.0))
    return Cercha(b, h, uni, p, uni_carga, angulo, p / (2.0 * math.sin(math.radians(angulo))), p / 2.0)


# ------------------------------------------------------------------ lazo, engranajes y Mohr


@dataclass
class Bloques:
    """El lazo de control: la realimentación se come ganancia, y con signo equivocado lo vuelve loco."""

    adelante: float  # la ganancia del bloque directo
    retro: float  # la ganancia del tramo de realimentación
    lazo_cerrado: float  # G / (1 ± G·H)
    negativa: bool = True  # la resta en el comparador, que es la que estabiliza


def _ganancia(texto: str | None, nombre: str) -> float:
    """Una ganancia va suelta, sin unidad: «10», «0.2», «-3,5»."""
    crudo = str(texto or "").strip().replace(",", ".")
    try:
        valor = float(crudo)
    except ValueError:
        raise ValueError(
            f"la ganancia de {nombre} necesita un número solo, ej. «10» o «0.2», y leí «{texto}»"
        ) from None
    if not math.isfinite(valor):
        raise ValueError(f"la ganancia de {nombre} tiene que ser un número finito, y leí «{texto}»")
    return valor


def analizar_bloques(adelante: str, retro: str, negativa: bool = True) -> Bloques:
    """Cierra el lazo con la fórmula que se aprende en el primer ramo de control."""
    g = _ganancia(adelante, "el bloque directo")
    h = _ganancia(retro, "la realimentación")
    malla = g * h
    denom = 1 + malla if negativa else 1 - malla
    if abs(denom) < 1e-9 or (not negativa and malla >= 1):
        raise ValueError(
            f"con G·H = {malla:g} el lazo es inestable: la salida se va al infinito y no hay video"
        )
    return Bloques(g, h, g / denom, negativa)


@dataclass
class Engranaje:
    """La pareja de dientes: el grande gira menos veces, y siempre al revés."""

    z1: int  # dientes de la conductora
    z2: int  # dientes de la conducida
    entrada: float  # las vueltas del eje rápido
    salida: float
    relacion: float  # z2 / z1: cuánto se multiplicó el torque
    unidad: str  # de «1200 rpm» sale «rpm»
    invertida: bool = True


def analizar_engranajes(dientes_a: str, dientes_b: str, rpm: str) -> Engranaje:
    """La relación de transmisión: los dientes mandan y el sentido se invierte en cada contacto."""

    def dientes(texto: str | None, nombre: str) -> int:
        valor = _ganancia(texto, nombre)
        if valor <= 0 or valor != int(valor):
            raise ValueError(f"los dientes de {nombre} se cuentan con un entero positivo, y leí «{texto}»")
        return int(valor)

    z1, z2 = dientes(dientes_a, "la rueda conductora"), dientes(dientes_b, "la rueda conducida")
    if z1 == z2:
        raise ValueError(
            f"con los mismos {z1} dientes no hay relación de transmisión: las dos ruedas dan lo mismo"
        )
    n, uni = _medida_solido(rpm, "la velocidad de entrada", hasta_barra=True)
    return Engranaje(z1, z2, n, n * z1 / z2, z2 / z1, uni or "rpm")


@dataclass
class Mohr:
    """El círculo de Mohr del estado plano de esfuerzos, con sus principales ya leídos."""

    sigma_x: float
    sigma_y: float
    cortante: float
    unidad: str  # de «80 MPa» sale «MPa»
    centro: float  # (σx + σy) / 2, sobre el eje horizontal
    radio: float
    principal_1: float  # el esfuerzo normal mayor
    principal_2: float
    max_cortante: float  # vale lo mismo que el radio
    angulo: float  # cuánto hay que girar el elemento para llegar al plano principal, en grados


def _esfuerzo(texto: str | None, nombre: str) -> tuple[float, str]:
    """Un esfuerzo con su unidad, admitiendo cero y negativos (que en Mohr son compresión)."""
    crudo = str(texto or "")
    m = re.search(r"-?\d+(?:[.,]\d+)?", crudo)
    if not m:
        raise ValueError(
            f"el esfuerzo de {nombre} necesita un número con su unidad, ej. «80 MPa», y leí «{crudo}»"
        )
    return float(m.group().replace(",", ".")), crudo[m.end() :].strip()


def analizar_mohr(sigma_x: str, sigma_y: str, cortante: str) -> Mohr:
    """Traza el círculo: su centro, su radio y los dos esfuerzos principales que lee el ingeniero."""
    sx, uni = _esfuerzo(sigma_x, "σx")
    sy, _ = _esfuerzo(sigma_y, "σy")
    t, _ = _esfuerzo(cortante, "τxy")
    centro = (sx + sy) / 2.0
    radio = math.hypot((sx - sy) / 2.0, t)
    return Mohr(
        sx,
        sy,
        t,
        uni,
        centro,
        radio,
        centro + radio,
        centro - radio,
        radio,
        math.degrees(math.atan2(2.0 * t, sx - sy)) / 2.0,
    )
