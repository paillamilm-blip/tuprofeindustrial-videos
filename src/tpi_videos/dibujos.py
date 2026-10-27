"""Los cuatro dibujos que el motor sabe hacer en Manim: función, fuerzas, circuito y polígono regular.

Cada constructor devuelve un ``Dibujo`` centrado en el origen y ajustado a una caja (ancho × alto),
con las piezas separadas entre lo que se **traza** (``Create``) y lo que **aparece** (``FadeIn``).
La matemática ya viene analizada en ``visuales.py``; aquí sólo se dibuja.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from manim import (
    DOWN,
    LEFT,
    MEDIUM,
    PI,
    RIGHT,
    SEMIBOLD,
    UP,
    Arc,
    Arrow,
    Circle,
    DashedLine,
    Dot,
    Ellipse,
    Line,
    Mobject,
    Polygon,
    Rectangle,
    Sector,
    VGroup,
    VMobject,
)

from . import componentes as c
from .visuales import (
    AnguloTrig,
    Barras,
    Energia,
    Funcion,
    Onda,
    Optica,
    Pendulo,
    Polea,
    Poligono,
    Probabilidad,
    Proyectil,
    Recta,
    Resorte,
    Solido,
    Torta,
    Venn,
    analizar_circuito,
)

ALTO_DIBUJO = 3.3  # franja del pie de la pizarra que ocupa un dibujo

# Hacia dónde apunta cada flecha que el motor conoce (VER VECTORES en visuales.py).
# «plano» = siguiendo la superficie; «normal» = perpendicular a ella; con plano inclinado
# el bloque baja por el plano, y sobre una mesa «plano» es simplemente la derecha.
_DIRECCIONES = {
    "P": "abajo",
    "N": "normal",
    "f": "contra_plano",
    "v": "plano",
    "a": "plano",
    "T": "cuerda",
}


@dataclass
class Dibujo:
    """Un dibujo listo para la escena: su grupo, y cómo sale cada parte."""

    mobs: VGroup
    trazo: list[Mobject] = field(default_factory=list)  # se dibujan con Create
    aparece: list[Mobject] = field(default_factory=list)  # aparecen con FadeIn

    def place(self, x: float, y: float) -> Dibujo:
        self.mobs.move_to(np.array([x, y, 0]))
        return self


def _numero_latex(valor: float) -> str:
    """4 → «4»; 2.5 → «2,5». En Chile el decimal lleva coma (``ecuacion()`` la escribe en LaTeX)."""
    n = round(float(valor), 2)
    n = 0.0 if n == 0 else n
    return str(int(n)) if n == int(n) else str(n).replace(".", ",")


def _sufijo_proyectil(figura: Proyectil) -> str:
    """El hueco que sigue al número del vuelo: ' m', ' km/h', o nada si el guion no dijo la unidad."""
    return " " + figura.unidad if figura.unidad else ""


def _sufijo(figura: Poligono) -> str:
    """El hueco que sigue al número: ' cm', ' m', o nada si el guion no dijo la unidad."""
    return " " + figura.unidad if figura.unidad else ""


def _encajar(todo: VGroup, ancho: float, alto: float) -> VGroup:
    """Si el dibujo se sale de la franja del pie, se encoge entero. Agrandarlo no sirve de nada."""
    excedido = max(todo.width / ancho, todo.height / alto)
    return todo if excedido <= 1.0 else todo.scale(1.0 / excedido)


def _parche(m: Mobject, papel: str, holgura: float = 0.14) -> VGroup:
    """Un texto con su trozo de papel detrás: así una curva o un cable nunca lo tapa."""
    fondo = (
        Rectangle(width=m.width + holgura, height=m.height + holgura * 0.6)
        .set_fill(papel, 1)
        .set_stroke(width=0)
        .move_to(m.get_center())
    )
    return VGroup(fondo, m)


def _cartela(
    col: Any,
    papel: str,
    parches: VGroup,
    rótulos: VGroup,
    texto: str,
    donde: np.ndarray,
    tam: int = 17,
    ancla: np.ndarray | None = None,
) -> None:
    """Una medida escrita sobre su trozo de papel, guardada en las dos pilas del dibujo.

    ``ancla`` pega el borde del rótulo que mira hacia el dibujo (LEFT/RIGHT), para que la cota
    no quede tapada por la propia letra.
    """
    lab = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
    if ancla is not None:
        lab.shift(ancla * (lab.width / 2))
    fondo, lab = _parche(lab, papel, 0.1)
    parches.add(fondo)
    rótulos.add(lab)


def _graduacion(x0: float, x1: float, maximo: int = 5) -> list[float]:
    """Posiciones de los números del eje: pasos de 1, 2, 2.5 o 5 veces una potencia de 10."""
    ancho = x1 - x0
    if ancho <= 0:
        return []
    crudo = ancho / maximo
    potencia = 10.0 ** np.floor(np.log10(crudo))
    paso = next((m * potencia for m in (1, 2, 2.5, 5, 10) if crudo <= m * potencia), 10 * potencia)
    salida: list[float] = []
    v = float(np.ceil(x0 / paso) * paso)
    while v <= x1 + 1e-9:
        salida.append(round(v, 6))
        v += paso
    return salida


def _trazos_de_curva(f: Funcion, p, col: Any, y0: float, y1: float) -> list[VMobject]:
    """La curva, partida donde no existe (una asíntota no se une con el otro brazo).

    Se deja pasar apenas un dedo por encima de la caja y se recorta ahí: la rama sale del cuadro
    por arriba, en vez de quedarse estirada en una línea plana pegada al borde.
    """
    recorte = (y1 - y0) * 0.1
    trazos: list[VMobject] = []
    puntos: list[np.ndarray] = []

    def cerrar() -> None:
        if len(puntos) > 1:
            trazos.append(VMobject().set_points_as_corners(list(puntos)))
        puntos.clear()

    for x in f._muestras():
        y = f.y(x)
        if y is None or y < y0 - recorte or y > y1 + recorte:
            cerrar()
            continue
        puntos.append(p(x, max(y0, min(y1, y))))
    cerrar()
    return [t.set_stroke(col.acento, 7) for t in trazos]


# ------------------------------------------------------------------------------------------
# 1 · Gráfico de función
# ------------------------------------------------------------------------------------------


def grafico_funcion(
    f: Funcion,
    col: Any,
    ancho: float,
    alto: float,
    eje_x: str | None = None,
    eje_y: str | None = None,
    papel: str = "#FFFFFF",
) -> Dibujo:
    """Ejes con numeración, la curva trazada y un punto en cada raíz y en el vértice."""
    x0, x1 = f.rango_x
    y0, y1 = f.rango_y()
    # Los números de los ejes necesitan su propio margen: a la izquierda y abajo.
    izquierda, abajo = -ancho / 2 + 0.62, -alto / 2 + 0.5
    derecha, arriba = ancho / 2 - 0.3, alto / 2 - 0.45

    def p(x: float, y: float) -> np.ndarray:
        return np.array(
            [
                izquierda + (x - x0) / (x1 - x0) * (derecha - izquierda),
                abajo + (y - y0) / (y1 - y0) * (arriba - abajo),
                0,
            ]
        )

    vertical = p(0, y0)[0] if x0 <= 0 <= x1 else izquierda
    horizontal = p(x0, 0)[1] if y0 <= 0 <= y1 else abajo

    def punta_eje(a: np.ndarray, b: np.ndarray) -> Arrow:
        # Sin estos topes Manim hace la punta proporcional al grosor del trazo y sale una flechota.
        return Arrow(a, b, buff=0, stroke_width=4, tip_length=0.3, max_tip_length_to_length_ratio=0.07)

    ejes = (
        VGroup(
            punta_eje([izquierda - 0.12, horizontal, 0], [derecha + 0.12, horizontal, 0]),
            punta_eje([vertical, abajo - 0.12, 0], [vertical, arriba + 0.12, 0]),
        )
        .set_stroke(col.tenue, 4)
        .set_fill(col.tenue, 1)
    )

    curva = _trazos_de_curva(f, p, col, y0, y1)

    # 1) Los rótulos de las marcas, y con ellos la fila que ocupan bajo el eje.
    marcas, fila = VGroup(), []
    for x in f.puntos:
        y = f.y(x)
        if y is None:
            continue
        # Una raíz se marca con su número en el eje; un vértice, con el par de coordenadas.
        contenido = _numero_latex(x) if abs(y) < 0.05 else f"({_numero_latex(x)};\\,{_numero_latex(y)})"
        punto = p(x, y)
        rotulo = c.ecuacion(contenido, 22, col.formulas)
        hacia_arriba = abs(y) >= 0.05 and punto[1] + rotulo.height + 0.2 < arriba + 0.5
        # Una raíz se aparta hacia la banda libre: por donde la curva sube no la tapamos.
        lado = 0.0 if abs(y) >= 0.05 else (0.42 if f.y(x + 0.05) and f.y(x + 0.05) > y else -0.42)
        rotulo.move_to(
            [punto[0] + lado, punto[1] + (rotulo.height / 2 + 0.16) * (1 if hacia_arriba else -1), 0]
        )
        rotulo.set_x(
            np.clip(rotulo.get_x(), -ancho / 2 + rotulo.width / 2 + 0.05, ancho / 2 - rotulo.width / 2 - 0.05)
        )
        if not hacia_arriba:
            fila.append((rotulo.get_x(), rotulo.width))
        marcas.add(
            Dot(punto, radius=0.07).set_fill(col.acento, 1).set_stroke(col.formulas, 2),
            _parche(rotulo, papel, 0.18),
        )

    # 2) Los números de los ejes: los de abajo ceden ante un rótulo que pise su misma fila.
    numeros = VGroup()
    for tx in _graduacion(x0, x1):
        if abs(tx) < 1e-9:
            continue
        x = p(tx, y0)[0]
        numeros.add(Line([x, horizontal + 0.06, 0], [x, horizontal - 0.06, 0]).set_stroke(col.tenue, 3))
        # El último número quedaría bajo la punta del eje: ese también se salta.
        if x < derecha - 0.4 and not any(abs(x - mx) < (mw + 0.5) / 2 + 0.12 for mx, mw in fila):
            numeros.add(c.texto(_numero_latex(tx), 16, MEDIUM, col.tenue).move_to([x, horizontal - 0.3, 0]))
    for ty in _graduacion(y0, y1, 4):
        if abs(ty) < 1e-9:
            continue
        y = p(x0, ty)[1]
        numeros.add(
            Line([vertical - 0.06, y, 0], [vertical + 0.06, y, 0]).set_stroke(col.tenue, 3),
            c.texto(_numero_latex(ty), 16, MEDIUM, col.tenue).move_to([vertical - 0.36, y, 0]),
        )

    nombres = VGroup(
        _parche(
            c.texto(eje_x or f.variable, 17, SEMIBOLD, col.tenue).move_to(
                [derecha + 0.05, horizontal - 0.62, 0]
            ),
            papel,
        ),
        _parche(
            c.texto(eje_y or "y", 17, SEMIBOLD, col.tenue).move_to([vertical + 0.18, arriba + 0.42, 0]), papel
        ),
    )

    todo = VGroup(ejes, VGroup(*curva), numeros, nombres, marcas)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=[*ejes, *curva], aparece=[numeros, nombres, marcas])


# ------------------------------------------------------------------------------------------
# 2 · Diagrama de fuerzas
# ------------------------------------------------------------------------------------------


def diagrama_fuerzas(
    vectores: list[str],
    col: Any,
    ancho: float,
    alto: float,
    cuerpo: str = "bloque",
    angulo: float | None = None,
    descomponer: bool = False,
    papel: str = "#FFFFFF",
) -> Dibujo:
    """El cuerpo en el centro y una flecha por fuerza, con su símbolo en la punta."""
    inclinacion = PI * (angulo or 0) / 180
    # «plano» es la dirección en la que el cuerpo se desliza; «normal», perpendicular a él.
    plano = np.array([np.cos(inclinacion), -np.sin(inclinacion), 0.0])
    normal = np.array([-plano[1], plano[0], 0.0])
    cuelga = cuerpo == "bola"
    apoyo = np.array([0.0, -0.2, 0.0])  # el centro de la bola; el bloque recalcula su apoyo abajo

    if cuelga:
        cuerpo_m = Circle(radius=0.48).set_fill(col.panel, 1).set_stroke(col.formulas, 4).move_to(apoyo)
        soporte = VGroup()
    else:
        alto_b, ancho_b = 0.82, 1.15
        # La rampa se corta donde lo pide la franja: a 45° dos metros de plano no caben en 3,3 de alto.
        largo = min(ancho * 0.42, (alto / 2 - 0.3) / max(float(np.sin(inclinacion)), 0.3))
        base = np.array([0.0, -0.42 if angulo else -0.41, 0.0])  # el punto medio de la superficie
        # El bloque se sube por el plano: si queda a mitad de rampa, su peso cae encima del ángulo.
        contacto = base - plano * (0.35 * largo if angulo else 0.0)
        apoyo = contacto + normal * (alto_b / 2)  # el bloque apoya: su centro queda más arriba
        cuerpo_m = (
            Rectangle(width=ancho_b, height=alto_b)
            .set_fill(col.panel, 1)
            .set_stroke(col.formulas, 4)
            .rotate(-inclinacion)
            .move_to(apoyo)
        )
        ribera = base + plano * largo
        soporte = VGroup(
            Line(ribera, base - plano * largo, buff=0).set_stroke(col.tenue, 5),
        )
        if angulo:  # el ángulo se mide contra el horizontal, como en el cuaderno
            horizontal = DashedLine(ribera, ribera + LEFT * (1.2 + 0.7 * np.tan(inclinacion)))
            horizontal.set_stroke(col.tenue, 3)
            arco = Arc(radius=0.7, start_angle=PI - inclinacion, angle=inclinacion, arc_center=ribera)
            arco.set_stroke(col.tenue, 3)
            rincon = c.texto(f"{_numero_latex(angulo)}°", 20, SEMIBOLD, col.texto)
            rincon.move_to(
                ribera + np.array([np.cos(PI - inclinacion / 2), np.sin(PI - inclinacion / 2), 0]) * 1.05
            )
            soporte += VGroup(horizontal, arco, _parche(rincon, papel, 0.15))

    flechas, etiquetas = VGroup(), VGroup()
    for simbolo in vectores:
        modo = _DIRECCIONES[simbolo]
        if cuelga:
            d = {"abajo": DOWN, "cuerda": UP, "normal": UP}.get(modo, RIGHT)
        elif modo == "abajo":
            d = DOWN
        elif modo == "normal":
            d = normal
        elif modo == "contra_plano":
            d = -plano
        elif modo == "cuerda":
            d = -plano if angulo else RIGHT
        else:
            d = plano
        d = np.array([float(v) for v in d])
        inicio = apoyo + d * (0.55 if cuelga else 0.18)
        # El peso va en rojo (es la fuerza que todos olvidan); las demás, en el color de los títulos.
        tinta = col.error if simbolo == "P" else col.titulos
        flecha = Arrow(inicio, inicio + d * 1.05, buff=0, stroke_width=7, max_tip_length_to_length_ratio=0.25)
        flecha.set_stroke(tinta, 7).set_fill(tinta, 1)
        etiqueta = c.ecuacion(simbolo, 30, col.formulas).move_to(flecha.get_end() + d * 0.3)
        flechas.add(flecha)
        etiquetas.add(_parche(etiqueta, papel, 0.2))

    if descomponer and angulo and not cuelga:
        # El peso partido en dos, como en el cuaderno: una a lo largo del plano y otra clavada en él.
        # Nacen del mismo punto que el P para que se vea que son el mismo peso mirado de otro lado.
        sen, cos = float(np.sin(inclinacion)), float(np.cos(inclinacion))
        inicio_p = apoyo + DOWN * 0.18
        partes = [
            (plano, sen, r"P\,\mathrm{sen}\,\theta"),
            (-normal, cos, r"P\,\mathrm{cos}\,\theta"),
        ]
        for d, factor, tex in partes:
            punta = inicio_p + d * (1.05 * factor)
            componente = Arrow(inicio_p, punta, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.22)
            componente.set_stroke(col.tenue, 5).set_fill(col.tenue, 1)
            rotulo = c.ecuacion(tex, 24, col.texto).move_to(punta + d * 0.32)
            flechas.add(componente)
            etiquetas.add(_parche(rotulo, papel, 0.2))

    todo = VGroup(*soporte, cuerpo_m, flechas, etiquetas).set_z_index(1)
    _encajar(todo, ancho, alto)
    return Dibujo(
        mobs=todo,
        trazo=[*flechas, soporte[0]] if len(soporte) else [*flechas],
        aparece=[cuerpo_m, *etiquetas, *soporte[1:]],
    )


# ------------------------------------------------------------------------------------------
# 3 · Circuito
# ------------------------------------------------------------------------------------------


def circuito(
    fuente: float,
    resistencias: list[float],
    col: Any,
    ancho: float,
    alto: float,
    arreglo: str = "serie",
    papel: str = "#FFFFFF",
) -> Dibujo:
    """La malla, la batería y cada resistencia con su valor escrito al lado.

    En **serie** las resistencias se reparten por el cable de arriba y la pila corta el de la
    izquierda; en **paralelo** cada resistencia va en su propia rama entre las dos barras
    verticales, y la pila cuelga del cable de abajo (si fuera una sola malla, las ramas de arriba
    y de abajo se unirían con un cable limpio y sería un cortocircuito dibujado).
    """
    n = len(resistencias)
    w, h = ancho * 0.68, min(alto * 0.62, 2.2)
    izq, der, arriba, abajo = -w / 2, w / 2, h / 2, -h / 2

    cables, cajas, rotulos = VGroup(), VGroup(), VGroup()

    def linea(p, q) -> None:
        cables.add(Line(p, q, buff=0).set_stroke(col.formulas, 5))

    def resistencia(x: float, y: float, largo: float, alto_caja: float, i: int, rotulo_en) -> None:
        cajas.add(
            Rectangle(width=largo, height=alto_caja)
            .set_fill(papel, 1)
            .set_stroke(col.formulas, 4)
            .move_to([x, y, 0])
        )
        rotulo = c.ecuacion(f"R_{i} = {_numero_latex(resistencias[i - 1])}\\,\\Omega", 22, col.formulas)
        rotulo.move_to([*rotulo_en, 0])
        # El rótulo va sobre el papel, no sobre un cable: lleva su propio parche detrás.
        fondo, rotulo = _parche(rotulo, papel, 0.18)
        cajas.add(fondo)
        rotulos.add(rotulo)

    def pila(x: float, y: float, cable_vertical: bool) -> VGroup:
        """Las dos placas —una larga y una corta— perpendiculares al cable, y el hueco que lo corta."""
        largo, corto = 0.52, 0.26
        if cable_vertical:
            placas = VGroup(
                Line([x - largo / 2, y + 0.18, 0], [x + largo / 2, y + 0.18, 0]),
                Line([x - corto / 2, y - 0.18, 0], [x + corto / 2, y - 0.18, 0]),
            )
            corte = Rectangle(width=0.85, height=0.62)
        else:
            placas = VGroup(
                Line([x - 0.18, y - largo / 2, 0], [x - 0.18, y + largo / 2, 0]),
                Line([x + 0.18, y - corto / 2, 0], [x + 0.18, y + corto / 2, 0]),
            )
            corte = Rectangle(width=0.62, height=0.85)
        corte.set_fill(papel, 1).set_stroke(width=0).move_to([x, y, 0])
        return VGroup(corte, placas.set_stroke(col.formulas, 6))

    if arreglo == "serie":
        marco = Rectangle(width=w, height=h).set_stroke(col.formulas, 5).set_fill(opacity=0)
        cables.add(marco)
        pila_grupo = pila(izq, 0, cable_vertical=True)
        paso = w / (n + 1)
        for i in range(1, n + 1):
            x = izq + i * paso
            # con 4 resistencias no caben los rótulos uno al lado del otro: se alternan arriba/abajo
            arriba_rotulo = arriba + 0.5 if (n > 3 and i % 2 == 0) else arriba - 0.5
            resistencia(x, arriba, min(0.8, paso * 0.7), 0.34, i, [x, arriba_rotulo])
        rotulo_fuente = c.ecuacion(f"V = {_numero_latex(fuente)}\\,\\text{{V}}", 24, col.tenue)
        rotulo_fuente.move_to([izq + rotulo_fuente.width / 2 + 0.15, abajo - 0.42, 0])
    else:
        ramas = list(np.linspace(arriba, abajo + 0.62, n))
        paso = ramas[0] - ramas[1] if n > 1 else h
        linea([izq, abajo, 0], [izq, arriba, 0])
        linea([der, abajo, 0], [der, arriba, 0])
        for y in ramas:
            linea([izq, y, 0], [der, y, 0])
        linea([izq, abajo, 0], [der, abajo, 0])
        pila_grupo = pila(0, abajo, cable_vertical=False)
        for i, y in enumerate(ramas, 1):
            caja = min(0.8, w * 0.16)
            # El rótulo se escribe por encima de su rama, no encima del cable.
            resistencia(0, y, caja, min(0.34, paso * 0.5), i, [caja / 2 + 0.75, y + 0.28])
        rotulo_fuente = c.ecuacion(f"V = {_numero_latex(fuente)}\\,\\text{{V}}", 24, col.tenue)
        rotulo_fuente.move_to([0, abajo - 0.45, 0])

    todo = VGroup(cables, cajas, pila_grupo, rotulos, rotulo_fuente)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=[*cables], aparece=[*cajas, *pila_grupo, *rotulos, rotulo_fuente])


# ------------------------------------------------------------------------------------------
# 4 · Polígono regular
# ------------------------------------------------------------------------------------------


def poligono_regular(
    figura: Poligono,
    marcas: list[str],
    col: Any,
    ancho: float,
    alto: float,
    papel: str = "#FFFFFF",
) -> Dibujo:
    """La figura cerrada de un solo trazo, con la medida del lado escrita y las marcas del guion.

    Se dibuja con circunradio 1 y se agranda hasta la franja, así el tamaño en pantalla no depende
    de si el lado del guion mide 4 cm o 4 km. Cada medida va encima de su línea con su parche de
    papel (el mismo truco de las resistencias): en el cuaderno el número se escribe pegado a la raya.
    """
    puntas = [np.array([x / figura.radio, y / figura.radio, 0.0]) for x, y in figura.vertices]
    xs, ys = [p[0] for p in puntas], [p[1] for p in puntas]
    escala = min(ancho * 0.58 / (max(xs) - min(xs)), alto * 0.66 / (max(ys) - min(ys)))
    esquinas = [p * escala for p in puntas]
    centro = np.zeros(3)

    abajo = min(p[1] for p in esquinas)
    de_base = [p for p in esquinas if abs(p[1] - abajo) < 1e-6]
    izq_base, der_base = min(de_base, key=lambda p: p[0]), max(de_base, key=lambda p: p[0])
    arriba = max(p[1] for p in esquinas)
    i_punta = max(
        (i for i, p in enumerate(esquinas) if abs(p[1] - arriba) < 1e-6), key=lambda i: esquinas[i][0]
    )
    punta, vecino = esquinas[i_punta], esquinas[i_punta - 1]  # el vecino gira hacia la derecha

    contorno = Polygon(*esquinas, color=col.formulas, stroke_width=6).set_fill(col.formulas, 0.07)
    rayas, parches, rótulos = [contorno], VGroup(), VGroup()
    puntos = [Dot(p, radius=0.045, color=col.formulas) for p in esquinas]

    def medida(texto: str, donde: np.ndarray, tam: float = 24) -> None:
        rotulo = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = _parche(rotulo, papel, 0.16)
        parches.add(fondo)
        rótulos.add(rotulo)

    def raya(tinta: str, p, q) -> None:
        linea = DashedLine(p, q, buff=0).set_stroke(tinta, 4)
        rayas.append(linea)

    # La medida del lado, colgada de la base: es el dato que el guion trajo de casa.
    medida(
        f"{_numero_latex(figura.lado)}{_sufijo(figura)}",
        [(izq_base[0] + der_base[0]) / 2, abajo - 0.36, 0.0],
        26,
    )

    if "apotema" in marcas:
        pie = (izq_base + der_base) / 2  # la apotema baja recta desde el centro hasta el medio de la base
        raya(col.acento, centro, pie)
        medida(f"a ≈ {_numero_latex(figura.apotema)}{_sufijo(figura)}", pie / 2)
        # La escuadra del pie dice, sin palabras, que la apotema cae a plomo sobre el lado.
        canto = min(0.15, float(np.linalg.norm(pie - centro)) * 0.3)
        escuadra = VMobject(color=col.acento, stroke_width=3)
        escuadra.set_points_as_corners(
            [pie + RIGHT * canto, pie + RIGHT * canto + UP * canto, pie + UP * canto]
        )
        rayas.append(escuadra)
    if "radio" in marcas:
        raya(col.acento, centro, punta)
        medida(f"R ≈ {_numero_latex(figura.radio)}{_sufijo(figura)}", punta / 2)
    if "apotema" in marcas or "radio" in marcas:
        # En un triángulo el radio a la punta y la apotema caen en la misma raya: el punto marca el corte.
        puntos.append(Dot(centro, radius=0.06, color=col.acento))
    radio_arco = min(0.42, escala * 0.35)
    if "angulo_central" in marcas:
        # Se abre hacia arriba, entre dos radios vecinos: abajo ya están la base y la apotema.
        raya(col.tenue, centro, vecino)
        raya(col.tenue, centro, punta)
        arranque = float(np.arctan2(vecino[1], vecino[0]))
        giro = 2 * PI / figura.lados
        rayas.append(Arc(radius=radio_arco, start_angle=arranque, angle=giro).set_stroke(col.tenue, 4))
        bisección = arranque + giro / 2
        medida(
            f"{_numero_latex(figura.angulo_central)}°",
            centro + np.array([np.cos(bisección), np.sin(bisección), 0.0]) * (radio_arco + 0.3),
        )
    if "angulo_interior" in marcas:
        giro = PI * (figura.lados - 2) / figura.lados
        rayas.append(
            Arc(radius=radio_arco, start_angle=0, angle=giro, arc_center=izq_base).set_stroke(col.tenue, 4)
        )
        rincon = izq_base + np.array([np.cos(giro / 2), np.sin(giro / 2), 0.0]) * (radio_arco + 0.3)
        medida(f"{_numero_latex(figura.angulo_interior)}°", rincon)

    todo = VGroup(contorno, *rayas[1:], parches, *puntos, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[*puntos, *rótulos])


# ------------------------------------------------------------------------------------------
# 5 · Tiro parabólico
# ------------------------------------------------------------------------------------------


def proyectil(
    figura: Proyectil, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La parábola del vuelo apoyada en el suelo, con la flecha del lanzamiento y las marcas del guion.

    Se escala con el alcance y la altura que calculó ``visuales.py``: la forma de la curva es la
    verdadera, así una rampa de 45° se ve distinta de una de 30° sin que nadie escriba un número.
    """
    escala = min(ancho * 0.9 / figura.alcance, alto * 0.7 / figura.altura)
    gravedad = 2 * figura.vertical / figura.tiempo
    paso = figura.tiempo / 48
    mitad = figura.alcance * escala / 2
    puntos = []
    for i in range(49):
        t = paso * i
        x = figura.horizontal * t * escala - mitad
        y = (figura.vertical * t - gravedad * t * t / 2) * escala
        puntos.append(np.array([x, y, 0.0]))
    izquierda, derecha = puntos[0], puntos[-1]

    suelo = Line(izquierda + LEFT * 0.3, derecha + RIGHT * 0.3, buff=0).set_stroke(col.tenue, 5)
    curva = VMobject().set_points_smoothly(puntos).set_stroke(col.formulas, 6)
    rayas: list = [suelo, curva]
    parches, rótulos, puntos_vivos = VGroup(), VGroup(), []

    def medida(texto: str, donde: np.ndarray, tam: float = 22) -> None:
        rotulo = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = _parche(rotulo, papel, 0.16)
        parches.add(fondo)
        rótulos.add(rotulo)

    # La flecha del lanzamiento sale del punto de partida, con su ángulo contra el suelo.
    rad = float(np.arctan2(figura.vertical, figura.horizontal))
    direccion = np.array([np.cos(rad), np.sin(rad), 0.0])
    lanzamiento = Arrow(
        izquierda, izquierda + direccion * 1.1, buff=0, stroke_width=7, max_tip_length_to_length_ratio=0.25
    )
    lanzamiento.set_stroke(col.error, 7).set_fill(col.error, 1)
    rayas.append(lanzamiento)
    arco = Arc(radius=0.55, start_angle=0, angle=rad, arc_center=izquierda).set_stroke(col.tenue, 3)
    rayas.append(arco)
    medida(f"{_numero_latex(figura.angulo)}°", izquierda + np.array([0.95, 0.16, 0.0]))
    if "alcance" in marcas:
        medida(f"d ≈ {_numero_latex(figura.alcance)}{_sufijo_proyectil(figura)}", derecha + DOWN * 0.36, 24)
    cima = puntos[24]
    if "altura_maxima" in marcas:
        bajada = DashedLine(cima, cima * np.array([1.0, 0.0, 1.0]), buff=0).set_stroke(col.acento, 4)
        rayas.append(bajada)
        puntos_vivos.append(Dot(cima, radius=0.05, color=col.acento))
        medida(
            f"h ≈ {_numero_latex(figura.altura)}{_sufijo_proyectil(figura)}",
            cima + np.array([0.95, -0.3, 0.0]),
            24,
        )
    if "componentes" in marcas:
        t = figura.tiempo / 4
        origen = np.array(
            [
                figura.horizontal * t * escala - mitad,
                (figura.vertical * t - gravedad * t * t / 2) * escala,
                0.0,
            ]
        )
        puntos_vivos.append(Dot(origen, radius=0.05, color=col.formulas))
        vx = Arrow(origen, origen + RIGHT * 0.9, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.22)
        vx.set_stroke(col.tenue, 5).set_fill(col.tenue, 1)
        vy = Arrow(origen, origen + UP * 0.9, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.22)
        vy.set_stroke(col.tenue, 5).set_fill(col.tenue, 1)
        rayas.extend([vx, vy])
        medida("vx", origen + RIGHT * 1.15 + DOWN * 0.15, 20)
        medida("vy", origen + UP * 1.1 + RIGHT * 0.2, 20)

    todo = VGroup(suelo, curva, *rayas[2:], parches, *puntos_vivos, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[*puntos_vivos, *rótulos])


# ------------------------------------------------------------------------------------------
# 6 · Círculo trigonométrico
# ------------------------------------------------------------------------------------------


def circulo_trig(
    figura: AnguloTrig, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El radio girado hasta el ángulo: el seno es su sombra vertical y el coseno la horizontal.

    Los tres segmentos se dibujan sobre el mismo círculo, así «sen 30° = 0,5» deja de ser un
    número suelto y pasa a ser un alto que se ve.
    """
    radio = min(alto * 0.4, ancho * 0.2)
    rad = float(np.radians(figura.grados))
    punto = np.array([radio * float(np.cos(rad)), radio * float(np.sin(rad)), 0.0])

    eje_h = Line([-radio - 0.35, 0, 0], [radio + 0.8, 0, 0], buff=0).set_stroke(col.tenue, 3)
    eje_v = Line([0, -radio - 0.25, 0], [0, radio + 0.25, 0], buff=0).set_stroke(col.tenue, 3)
    circulo = Circle(radius=radio).set_stroke(col.tenue, 4)
    rayas: list = [eje_h, eje_v, circulo]
    parches, rótulos, puntos_vivos = VGroup(), VGroup(), []

    def medida(texto: str, donde: np.ndarray, tam: float = 22) -> None:
        rotulo = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = _parche(rotulo, papel, 0.16)
        parches.add(fondo)
        rótulos.add(rotulo)

    radio_linea = Line(np.zeros(3), punto, buff=0).set_stroke(col.formulas, 5)
    rayas.append(radio_linea)
    arco = Arc(radius=radio * 0.38, start_angle=0, angle=rad).set_stroke(col.tenue, 3)
    rayas.append(arco)
    mitad_arco = np.array([np.cos(rad / 2), np.sin(rad / 2), 0.0]) * radio * 0.45
    medida(f"{_numero_latex(figura.grados)}°", mitad_arco, 18)
    puntos_vivos.append(Dot(punto, radius=0.05, color=col.formulas))

    base = np.array([punto[0], 0.0, 0.0])
    if "seno" in marcas:
        seno = Line(base, punto, buff=0).set_stroke(col.error, 6)
        rayas.append(seno)
        lado = RIGHT if figura.coseno >= 0 else LEFT
        medida(f"sen = {_numero_latex(figura.seno)}", (base + punto) / 2 + lado * 0.85)
    if "coseno" in marcas:
        coseno = Line(np.zeros(3), base, buff=0).set_stroke(col.cuadricula, 6)
        rayas.append(coseno)
        arriba = DOWN if figura.seno >= 0 else UP
        medida(f"cos = {_numero_latex(figura.coseno)}", base / 2 + arriba * 0.3)
    if "tangente" in marcas and figura.tangente is not None:
        toque = np.array([radio, radio * figura.tangente, 0.0])
        pie = np.array([radio, 0.0, 0.0])
        segmento = Line(pie, toque, buff=0).set_stroke(col.acento, 6)
        alargo = DashedLine(punto, toque, buff=0).set_stroke(col.tenue, 3)
        rayas.extend([segmento, alargo])
        medida(f"tan = {_numero_latex(figura.tangente)}", (pie + toque) / 2 + RIGHT * 0.85)

    todo = VGroup(*rayas, parches, *puntos_vivos, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[*puntos_vivos, *rótulos])


# ------------------------------------------------------------------------------------------
# 7 · Sólidos (lámina de libro)
# ------------------------------------------------------------------------------------------


def _sufijo_solido(figura: Solido, potencia: int) -> str:
    """El hueco del número: ' cm³' para el volumen, ' cm²' para el área, nada sin unidad."""
    return f" {figura.unidad}{'³' if potencia == 3 else '²'}" if figura.unidad else ""


def solido(
    figura: Solido, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El cuerpo como en la lámina del libro: perspectiva chica, medidas acotadas y V y A escritas.

    No es un 3D de verdad: es el dibujo que el alumno reconoce del cuaderno, con el radio, la
    altura o la arista acotados y el volumen y el área que calculó ``visuales.py``.
    """
    r, h, a = figura.radio or 0.0, figura.altura or 0.0, figura.lado or 0.0
    if figura.figura == "cubo":
        alto_cuerpo, ancho_cuerpo = a, a
    else:
        alto_cuerpo = 2 * r if figura.figura == "esfera" else h
        ancho_cuerpo = 2 * r
    escala = min(alto * 0.62 / alto_cuerpo, ancho * 0.34 / ancho_cuerpo)
    R, H, A = r * escala, h * escala, a * escala
    E = R * 0.32  # la mitad del alto de las elipses: la "profundidad" que ve el ojo

    rayas: list = []
    parches, rótulos = VGroup(), VGroup()

    def medida(texto: str, donde: np.ndarray, tam: float = 22) -> None:
        rotulo = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = _parche(rotulo, papel, 0.16)
        parches.add(fondo)
        rótulos.add(rotulo)

    def acotada(p: np.ndarray, q: np.ndarray, texto: str, donde: np.ndarray) -> None:
        rayas.append(DashedLine(p, q, buff=0).set_stroke(col.tenue, 3))
        medida(texto, donde, 20)

    if figura.figura == "cilindro":
        tapa = Ellipse(width=2 * R, height=2 * E).move_to(UP * H / 2).set_stroke(col.formulas, 4)
        base = Ellipse(width=2 * R, height=2 * E).move_to(DOWN * H / 2).set_stroke(col.tenue, 4)
        rayas.extend([tapa, base])
        for x in (-R, R):
            rayas.append(Line([x, -H / 2, 0], [x, H / 2, 0], buff=0).set_stroke(col.formulas, 4))
        acotada(
            [0, H / 2, 0],
            [R, H / 2, 0],
            f"r = {_numero_latex(r)} {figura.unidad}".strip(),
            np.array([R / 2, H / 2 + 0.3, 0.0]),
        )
        acotada(
            [-R - 0.3, -H / 2, 0],
            [-R - 0.3, H / 2, 0],
            f"h = {_numero_latex(h)} {figura.unidad}".strip(),
            np.array([-R - 0.8, 0.0, 0.0]),
        )
    elif figura.figura == "cono":
        base = Ellipse(width=2 * R, height=2 * E).move_to(DOWN * H / 2).set_stroke(col.tenue, 4)
        rayas.append(base)
        for x in (-R, R):
            rayas.append(Line([0, H / 2, 0], [x, -H / 2, 0], buff=0).set_stroke(col.formulas, 4))
        acotada(
            [0, H / 2, 0],
            [0, -H / 2, 0],
            f"h = {_numero_latex(h)} {figura.unidad}".strip(),
            np.array([0.4, 0.0, 0.0]),
        )
        acotada(
            [0, -H / 2, 0],
            [R, -H / 2, 0],
            f"r = {_numero_latex(r)} {figura.unidad}".strip(),
            np.array([R / 2, -H / 2 - 0.32, 0.0]),
        )
    elif figura.figura == "esfera":
        rayas.append(Circle(radius=R).set_stroke(col.formulas, 4))
        rayas.append(Ellipse(width=2 * R, height=2 * E).set_stroke(col.tenue, 3))
        acotada(
            [0, 0, 0],
            [R, 0, 0],
            f"r = {_numero_latex(r)} {figura.unidad}".strip(),
            np.array([R / 2, 0.3, 0.0]),
        )
    else:
        d = A * 0.38  # el desplazamiento oblicuo de la cara de atrás
        frente = [
            np.array([x - d / 2, y - d / 2, 0.0])
            for x, y in ((-A / 2, -A / 2), (A / 2, -A / 2), (A / 2, A / 2), (-A / 2, A / 2))
        ]
        atras = [p + np.array([d, d, 0.0]) for p in frente]
        rayas.append(Polygon(*frente, color=col.formulas, stroke_width=4))
        rayas.append(Polygon(*atras, color=col.tenue, stroke_width=3))
        for p, q in zip(frente, atras, strict=True):
            rayas.append(Line(p, q, buff=0).set_stroke(col.tenue, 3))
        medida(
            f"a = {_numero_latex(a)} {figura.unidad}".strip(),
            (frente[0] + frente[1]) / 2 + DOWN * 0.3,
            20,
        )

    cuerpo = VGroup(*rayas, parches)
    columna = cuerpo.width / 2 + 1.1
    if "volumen" in marcas:
        medida(
            f"V ≈ {_numero_latex(figura.volumen)}{_sufijo_solido(figura, 3)}",
            np.array([columna, 0.32, 0.0]),
            24,
        )
    if "area" in marcas:
        medida(
            f"A ≈ {_numero_latex(figura.area)}{_sufijo_solido(figura, 2)}",
            np.array([columna, -0.32, 0.0]),
            24,
        )

    todo = VGroup(*rayas, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[*rótulos])


# ------------------------------------------------------------------------------------------
# 8 · Venn, recta numérica y probabilidad
# ------------------------------------------------------------------------------------------


def venn(
    figura: Venn, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """Los dos círculos que se cruzan con su número en cada región: el total lo saca el motor."""
    r = min(alto * 0.33, ancho * 0.15)
    d = r * 0.62
    ca, cb = np.array([-d, 0.0, 0.0]), np.array([d, 0.0, 0.0])
    circ_a = Circle(radius=r).move_to(ca).set_stroke(col.formulas, 4)
    circ_b = Circle(radius=r).move_to(cb).set_stroke(col.formulas, 4)
    rayas: list = [circ_a, circ_b]
    parches, rótulos = VGroup(), VGroup()

    def rotulo(texto: str, donde: np.ndarray, color: str, tam: float = 24) -> None:
        m = c.texto(texto, tam, SEMIBOLD, color).move_to(donde)
        fondo, m = _parche(m, papel, 0.16)
        parches.add(fondo)
        rótulos.add(m)

    rotulo(_numero_latex(figura.solo_a), ca + LEFT * r * 0.55, col.texto, 26)
    rotulo(_numero_latex(figura.ambos), np.zeros(3), col.acento, 26)
    rotulo(_numero_latex(figura.solo_b), cb + RIGHT * r * 0.55, col.texto, 26)
    rotulo(_numero_latex(figura.fuera), np.array([d + r + 0.5, r * 0.7, 0.0]), col.tenue, 22)
    rotulo("A", ca + UP * (r + 0.28), col.tenue, 20)
    rotulo("B", cb + UP * (r + 0.28), col.tenue, 20)
    if "total" in marcas:
        rotulo(f"total = {_numero_latex(figura.total)}", np.array([0.0, -r - 0.45, 0.0]), col.texto, 24)

    todo = VGroup(*rayas, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[*rótulos])


def recta(
    figura: Recta, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La recta con sus rayitas y números, y el intervalo (o rayo) subrayado en amarillo."""
    x0, x1 = figura.x0, figura.x1
    eje = Line([x0, 0, 0], [x1, 0, 0], buff=0).set_stroke(col.tenue, 4)
    rayas: list = [eje]
    parches, rótulos, puntos = VGroup(), VGroup(), []

    for t in _graduacion(x0, x1, maximo=7):
        rayas.append(Line([t, -0.08, 0], [t, 0.08, 0], buff=0).set_stroke(col.tenue, 3))
        m = c.texto(_numero_latex(t), 16, SEMIBOLD, col.tenue).move_to([t, -0.34, 0])
        fondo, m = _parche(m, papel, 0.12)
        parches.add(fondo)
        rótulos.add(m)

    def extremo(x: float, cerrado: bool) -> Mobject:
        if cerrado:
            return Dot([x, 0, 0], radius=0.09, color=col.formulas)
        return Circle(radius=0.09).move_to([x, 0, 0]).set_stroke(col.formulas, 4).set_fill("#FFFFFF", 1)

    if figura.es_rayo:
        fin = x1 - 0.2 if figura.derecha else x0 + 0.2
        rayas.append(Line([figura.a, 0, 0], [fin, 0, 0], buff=0).set_stroke(col.acento, 6))
        puntos.append(extremo(figura.a, figura.incluye_a))
    else:
        rayas.append(Line([figura.a, 0, 0], [figura.b, 0, 0], buff=0).set_stroke(col.acento, 6))
        puntos.extend([extremo(figura.a, figura.incluye_a), extremo(figura.b, figura.incluye_b)])

    todo = VGroup(*rayas, *puntos, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[*puntos, *rótulos])


def probabilidad(
    figura: Probabilidad, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La urna dibujada: los casos favorables en rojo, el resto en gris, y el cociente escrito."""
    paso = 0.42
    columnas = min(10, figura.totales)
    filas = -(-figura.totales // columnas)  # techo sin importar math
    puntos = []
    for i in range(figura.totales):
        x = (i % columnas - (columnas - 1) / 2) * paso
        y = ((filas - 1) / 2 - i // columnas) * paso
        color = col.error if i < figura.favorables else col.tenue
        puntos.append(Dot([x, y, 0], radius=0.13, color=color))
    parches, rótulos = VGroup(), VGroup()
    if "probabilidad" in marcas:
        m = c.texto(
            f"P = {_numero_latex(figura.favorables)}/{_numero_latex(figura.totales)} "
            f"≈ {_numero_latex(figura.p)}",
            24,
            SEMIBOLD,
            col.texto,
        ).move_to([0.0, -((filas - 1) / 2) * paso - 0.5, 0.0])
        fondo, m = _parche(m, papel, 0.16)
        parches.add(fondo)
        rótulos.add(m)

    todo = VGroup(*puntos, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=puntos, aparece=[*rótulos])


# ------------------------------------------------------------------------------------------
# 9 · Estadística: torta y barras
# ------------------------------------------------------------------------------------------


def _paleta(col: Any) -> list[str]:
    """Colores del tema, en un orden que se distingue bien uno del otro en la hoja."""
    return [col.acento, col.cuadricula, col.exito, col.error, col.tenue, col.formulas]


def _porcentaje(fraccion: float) -> str:
    return f"{_numero_latex(fraccion * 100)}%"


def torta(datos: Torta, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> Dibujo:
    """La torta de porcentajes: cada porción con su nombre y su porcentaje al lado."""
    r = min(alto * 0.40, ancho * 0.20)
    colores = _paleta(col)
    sectores: list = []
    parches, rótulos = VGroup(), VGroup()
    angulo = PI / 2  # se empieza arriba y se gira en sentido contrario a las agujas
    for i, cat in enumerate(datos.categorias):
        barrido = cat.fraccion * 2 * PI
        sector = Sector(radius=r, start_angle=angulo, angle=barrido, fill_opacity=0.82)
        sector.set_color(colores[i % len(colores)]).set_stroke(col.tenue, 2)
        sectores.append(sector)

        mitad = angulo + barrido / 2
        u = np.array([np.cos(mitad), np.sin(mitad), 0.0])
        pos = u * (r + 0.12)
        lab = c.texto(f"{cat.nombre} {_porcentaje(cat.fraccion)}", 17, SEMIBOLD, col.texto)
        lab.move_to(pos + (RIGHT if u[0] >= 0 else LEFT) * (lab.width / 2))
        fondo, lab = _parche(lab, papel, 0.12)
        parches.add(fondo)
        rótulos.add(lab)
        angulo += barrido

    todo = VGroup(*sectores, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=sectores, aparece=[*rótulos])


def barras(datos: Barras, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> Dibujo:
    """Las barras de datos: altura proporcional al mayor, valor arriba y categoría abajo."""
    n = len(datos.categorias)
    colores = _paleta(col)
    base = -alto * 0.20
    max_h = alto * 0.52
    paso = min(ancho * 0.86 / n, 1.35)
    ancho_barra = paso * 0.56
    eje = Line(
        [-(n - 1) / 2 * paso - paso * 0.4, base, 0], [(n - 1) / 2 * paso + paso * 0.4, base, 0], buff=0
    )
    eje.set_stroke(col.tenue, 3)
    barras_grp, parches, rótulos = [], VGroup(), VGroup()
    for i, cat in enumerate(datos.categorias):
        x = (i - (n - 1) / 2) * paso
        h = max((cat.valor / datos.maximo) * max_h, 0.06)
        barra = Rectangle(width=ancho_barra, height=h).move_to([x, base + h / 2, 0])
        barra.set_fill(colores[i % len(colores)], 0.82).set_stroke(col.tenue, 2)
        barras_grp.append(barra)

        def etiqueta(texto: str, donde: np.ndarray, tam: float) -> None:
            lab = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
            fondo, lab = _parche(lab, papel, 0.1)
            parches.add(fondo)
            rótulos.add(lab)

        etiqueta(_numero_latex(cat.valor), np.array([x, base + h + 0.24, 0.0]), 18)
        etiqueta(cat.nombre, np.array([x, base - 0.28, 0.0]), 14)

    todo = VGroup(eje, *barras_grp, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=[eje, *barras_grp], aparece=[*rótulos])


# ------------------------------------------------------------------------------------------
# 10 · Física: onda transversal y barra de energía
# ------------------------------------------------------------------------------------------


def onda(
    figura: Onda, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La onda dibujada a escala con sus dos cotas de siempre: la amplitud y lambda."""
    k = min(ancho * 0.85 / (2 * figura.longitud), alto * 0.34 / figura.amplitud)
    lam_px = figura.longitud * k
    a_px = figura.amplitud * k
    uni = f" {figura.unidad}" if figura.unidad else ""

    pts = [np.array([x, a_px * np.sin(2 * PI * x / lam_px), 0.0]) for x in np.linspace(-lam_px, lam_px, 121)]
    curva = VMobject().set_points_smoothly(pts)
    curva.set_stroke(col.acento, 5)
    eje = DashedLine([-lam_px - 0.3, 0, 0], [lam_px + 0.3, 0, 0]).set_stroke(col.tenue, 3)

    cresta = lam_px / 4  # la primera cresta, midiendo desde el centro
    flecha_a = Arrow(
        [cresta, 0, 0], [cresta, a_px, 0], buff=0, stroke_width=4, max_tip_length_to_length_ratio=0.25
    )
    flecha_a.set_stroke(col.error)
    flecha_l = Arrow(
        [cresta, a_px + 0.3, 0],
        [cresta + lam_px, a_px + 0.3, 0],
        buff=0,
        stroke_width=4,
        max_tip_length_to_length_ratio=0.12,
    )
    flecha_l.set_stroke(col.cuadricula)

    rayas: list = [eje, curva]
    parches, rótulos = VGroup(), VGroup()

    def etiqueta(texto: str, donde: np.ndarray, tam: float, ancla: np.ndarray | None = None) -> None:
        lab = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
        if ancla is not None:  # arrima el borde que mira al dibujo, para no tapar la cota
            lab.shift(ancla * (lab.width / 2))
        fondo, lab = _parche(lab, papel, 0.1)
        parches.add(fondo)
        rótulos.add(lab)

    etiqueta(f"A = {_numero_latex(figura.amplitud)}{uni}", np.array([cresta - 0.15, a_px / 2, 0.0]), 17, LEFT)
    etiqueta(
        f"λ = {_numero_latex(figura.longitud)}{uni}", np.array([cresta + lam_px / 2, a_px + 0.55, 0.0]), 17
    )
    if "velocidad" in marcas and figura.velocidad is not None:
        etiqueta(
            f"v = λ/T ≈ {_numero_latex(figura.velocidad)}{uni}/s",
            np.array([0.0, -a_px - 0.55, 0.0]),
            18,
        )

    todo = VGroup(*rayas, flecha_a, flecha_l, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[flecha_a, flecha_l, *rótulos])


def energia(datos: Energia, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> Dibujo:
    """La energía total en una sola barra repartida en sus formas: cada tramo, su porcentaje."""
    w, h = ancho * 0.78, alto * 0.30
    colores = _paleta(col)
    tramos, parches, rótulos = [], VGroup(), VGroup()
    x = -w / 2
    for i, tramo in enumerate(datos.tramos):
        seg = tramo.fraccion * w
        barra = Rectangle(width=seg, height=h).move_to([x + seg / 2, 0, 0])
        barra.set_fill(colores[i % len(colores)], 0.82).set_stroke(col.tenue, 3)
        tramos.append(barra)

        lab = c.texto(f"{tramo.nombre} {_porcentaje(tramo.fraccion)}", 16, SEMIBOLD, col.texto)
        lab.move_to([x + seg / 2, h / 2 + 0.32, 0])
        fondo, lab = _parche(lab, papel, 0.1)
        parches.add(fondo)
        rótulos.add(lab)
        x += seg

    total = c.texto(f"total = {_numero_latex(datos.total)}", 18, SEMIBOLD, col.texto).move_to(
        [0.0, -h / 2 - 0.38, 0.0]
    )
    fondo, total = _parche(total, papel, 0.1)
    parches.add(fondo)
    rótulos.add(total)

    todo = VGroup(*tramos, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=tramos, aparece=[*rótulos])


# ------------------------------------------------------------------------------------------
# 11 · Óptica y máquinas simples
# ------------------------------------------------------------------------------------------


def optica(
    figura: Optica, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La refracción de Snell: el raye entra por un lado y al cambiar de medio dobla hacia la normal."""
    t1 = np.radians(figura.incidencia)
    L = min(ancho * 0.24, alto * 0.40)
    r = L * 0.32
    origen = np.array([0.0, 0.0, 0.0])
    largo = min(ancho * 0.30, 2.6)

    superficie = Line([-largo, 0, 0], [largo, 0, 0]).set_stroke(col.tenue, 4)
    normal = DashedLine([0, L + 0.15, 0], [0, -L - 0.15, 0]).set_stroke(col.formulas, 3)

    def raye(a: np.ndarray, b: np.ndarray, tinta: str) -> Arrow:
        saeta = Arrow(a, b, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.15)
        saeta.set_stroke(tinta, 5).set_fill(tinta, 1)
        return saeta

    incidente = raye(np.array([-L * np.sin(t1), L * np.cos(t1), 0.0]), origen, col.acento)
    arcos = [Arc(radius=r, start_angle=PI / 2, angle=t1, arc_center=origen).set_stroke(col.acento, 3)]

    if figura.refraccion is None:
        # Reflexión total: el raye rebota y no pisa el segundo medio.
        saliente = raye(origen, np.array([L * np.sin(t1), L * np.cos(t1), 0.0]), col.error)
        arcos.append(Arc(radius=r, start_angle=PI / 2, angle=-t1, arc_center=origen).set_stroke(col.error, 3))
    else:
        t2 = np.radians(figura.refraccion)
        saliente = raye(origen, np.array([L * np.sin(t2), -L * np.cos(t2), 0.0]), col.cuadricula)
        arcos.append(
            Arc(radius=r, start_angle=-PI / 2, angle=t2, arc_center=origen).set_stroke(col.cuadricula, 3)
        )

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"θ₁ = {_numero_latex(figura.incidencia)}°",
        np.array([(r + 0.45) * np.cos(PI / 2 + t1 / 2), (r + 0.45) * np.sin(PI / 2 + t1 / 2), 0.0]),
        17,
        LEFT,
    )
    if figura.refraccion is None:
        _cartela(col, papel, parches, rótulos, "no pasa al otro lado", np.array([0.0, -L - 0.50, 0.0]), 18)
        angulo_2 = PI / 2 - t1 / 2
        texto_2 = f"θᵣ = {_numero_latex(figura.incidencia)}°"
    else:
        angulo_2 = -PI / 2 + np.radians(figura.refraccion) / 2
        texto_2 = f"θ₂ = {_numero_latex(figura.refraccion)}°"
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        texto_2,
        np.array([(r + 0.45) * np.cos(angulo_2), (r + 0.45) * np.sin(angulo_2), 0.0]),
        17,
        RIGHT,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"n₁ = {_numero_latex(figura.n1)}",
        np.array([-largo, L * 1.05, 0.0]),
        17,
        RIGHT,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"n₂ = {_numero_latex(figura.n2)}",
        np.array([largo, -L * 1.05, 0.0]),
        17,
        LEFT,
    )
    if figura.critico is not None:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"θ crítico ≈ {_numero_latex(figura.critico)}°",
            np.array([-largo, -L * 1.05, 0.0]),
            17,
            RIGHT,
        )

    rayas = [superficie, normal, *arcos]
    todo = VGroup(*rayas, incidente, saliente, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[incidente, saliente, *rótulos])


def pendulo(
    figura: Pendulo, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El hilo con su peso apartado de la vertical: el largo manda en el tiempo de una vuelta."""
    s = alto * 0.52
    uni = f" {figura.unidad}" if figura.unidad else ""
    t = np.radians(figura.angulo)
    pivote = np.array([0.0, s / 2, 0.0])
    peso = pivote + np.array([-s * np.sin(t), -s * np.cos(t), 0.0])

    apoyo = Line(pivote + [-0.4, 0, 0], pivote + [0.4, 0, 0]).set_stroke(col.formulas, 5)
    vertical = DashedLine(pivote, pivote + [0.0, -s, 0.0]).set_stroke(col.tenue, 3)
    vuelo = Arc(radius=s, start_angle=-PI / 2 - t, angle=2 * t, arc_center=pivote)
    vuelo.set_stroke(col.formulas, 2)
    hilo = Line(pivote, peso).set_stroke(col.formulas, 4)
    angulo = Arc(radius=s * 0.30, start_angle=-PI / 2, angle=-t, arc_center=pivote)
    angulo.set_stroke(col.acento, 3)
    bola = Circle(radius=0.16).move_to(peso)
    bola.set_fill(col.acento, 0.9).set_stroke(col.acento, 3)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.angulo)}°",
        pivote
        + np.array(
            [(s * 0.30 + 0.38) * np.cos(-PI / 2 - t / 2), (s * 0.30 + 0.38) * np.sin(-PI / 2 - t / 2), 0.0]
        ),
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"L = {_numero_latex(figura.longitud)}{uni}",
        pivote + np.array([0.25, -s * 0.55, 0.0]),
        17,
        RIGHT,
    )
    if "periodo" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"T ≈ {_numero_latex(figura.periodo)} s",
            np.array([0.0, -s / 2 - 0.42, 0.0]),
            18,
        )

    rayas = [apoyo, vertical, vuelo, hilo, angulo]
    todo = VGroup(*rayas, bola, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[bola, *rótulos])


def resorte(
    figura: Resorte, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La ley de Hooke: la pared, el resorte estirado y la fuerza que cuesta dejarlo así."""
    x_pared = -ancho * 0.32
    largo = ancho * 0.38
    lado = min(alto * 0.30, ancho * 0.13)
    x_fin = x_pared + largo

    pared = Line([x_pared, -alto * 0.28, 0], [x_pared, alto * 0.28, 0]).set_stroke(col.formulas, 5)
    rayado = VGroup(
        *[
            Line([x_pared, y + alto * 0.28, 0], [x_pared - 0.22, y + alto * 0.28 - 0.22, 0])
            for y in np.arange(-0.20, alto * 0.56, 0.32)
        ]
    ).set_stroke(col.tenue, 3)

    n = 7
    paso = (largo - 0.30) / n
    pts = [np.array([x_pared, 0.0, 0.0]), np.array([x_pared + 0.15, 0.0, 0.0])]
    for i in range(n):
        x0 = x_pared + 0.15 + paso * i
        pts.append(np.array([x0 + paso / 2, 0.24 if i % 2 == 0 else -0.24, 0.0]))
        pts.append(np.array([x0 + paso, 0.0, 0.0]))
    pts.append(np.array([x_fin, 0.0, 0.0]))
    espira = VMobject().set_points_as_corners(pts)
    espira.set_stroke(col.acento, 5)

    bloque = Rectangle(width=lado, height=lado).move_to([x_fin + lado / 2, 0.0, 0.0])
    bloque.set_fill(col.acento, 0.22).set_stroke(col.formulas, 4)

    estira = Arrow(
        [x_fin + lado, 0.0, 0.0],
        [x_fin + lado + ancho * 0.12, 0.0, 0.0],
        buff=0,
        stroke_width=5,
        max_tip_length_to_length_ratio=0.30,
    )
    estira.set_stroke(col.error, 5).set_fill(col.error, 1)

    x_reposo = x_fin - min(largo * 0.26, 0.65)
    guias = VGroup(
        DashedLine([x_reposo, 0.30, 0], [x_reposo, 0.60, 0]),
        DashedLine([x_fin, 0.30, 0], [x_fin, 0.60, 0]),
    ).set_stroke(col.tenue, 2)
    cota = Arrow(
        [x_reposo, 0.46, 0], [x_fin, 0.46, 0], buff=0, stroke_width=3, max_tip_length_to_length_ratio=0.35
    )
    cota.set_stroke(col.cuadricula, 4).set_fill(col.cuadricula, 1)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"x = {_numero_latex(figura.extension)} m",
        np.array([(x_reposo + x_fin) / 2, 0.78, 0.0]),
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"k = {_numero_latex(figura.constante)} N/m",
        np.array([x_pared + 0.2, alto * 0.34, 0.0]),
        17,
        RIGHT,
    )
    if "fuerza" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"F = k·x ≈ {_numero_latex(figura.fuerza)} N",
            np.array([x_fin + lado + ancho * 0.06, -0.80, 0.0]),
            18,
        )

    rayas = [pared, rayado, espira, guias, bloque]
    todo = VGroup(*rayas, cota, estira, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[cota, estira, *rótulos])


def polea(
    figura: Polea, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La máquina de Atwood: la masa más pesada gana y arrastra al conjunto entero."""
    r = min(alto * 0.15, ancho * 0.09)
    centro = np.array([0.0, alto * 0.34, 0.0])
    pesada_izq = figura.m1 >= figura.m2
    abajo, arriba = -alto * 0.34, -alto * 0.10
    uni = f" {figura.unidad}" if figura.unidad else ""
    mayor = max(figura.m1, figura.m2)

    def bloque(masa: float, x: float, y: float) -> Rectangle:
        lado = 0.30 + 0.28 * masa / mayor
        b = Rectangle(width=lado, height=lado).move_to([x, y + lado / 2, 0.0])
        b.set_fill(col.acento, 0.24).set_stroke(col.formulas, 4)
        return b

    bloque_a = bloque(figura.m1, -r, abajo if pesada_izq else arriba)
    bloque_b = bloque(figura.m2, r, arriba if pesada_izq else abajo)

    rueda = Circle(radius=r).move_to(centro)
    rueda.set_fill(col.acento, 0.10).set_stroke(col.formulas, 4)
    # La cuerda va por fuera del borde: si coincidiera con la circunferencia, desaparecería detrás.
    x_izq, x_der = -(r + 0.05), r + 0.05
    cuerda = Arc(radius=r + 0.05, start_angle=0, angle=PI, arc_center=centro).set_stroke(col.formulas, 5)
    izq = Line([x_izq, centro[1], 0], [x_izq, bloque_a.get_top()[1], 0]).set_stroke(col.formulas, 5)
    der = Line([x_der, centro[1], 0], [x_der, bloque_b.get_top()[1], 0]).set_stroke(col.formulas, 5)

    def flecha(b: Rectangle, baja: bool) -> Arrow:
        punta = DOWN if baja else UP
        inicio = b.get_center() + 0.35 * -punta
        saeta = Arrow(
            inicio, inicio + 0.65 * punta, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.3
        )
        saeta.set_stroke(col.error, 5).set_fill(col.error, 1)
        return saeta

    mov_a = flecha(bloque_a, pesada_izq)
    mov_b = flecha(bloque_b, not pesada_izq)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"m₁ = {_numero_latex(figura.m1)}{uni}",
        np.array([bloque_a.get_left()[0] - 0.14, bloque_a.get_center()[1], 0.0]),
        17,
        LEFT,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"m₂ = {_numero_latex(figura.m2)}{uni}",
        np.array([bloque_b.get_right()[0] + 0.14, bloque_b.get_center()[1], 0.0]),
        17,
        RIGHT,
    )
    if "tension" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"T ≈ {_numero_latex(figura.tension)} N",
            np.array([x_izq - 0.12, centro[1] - r - 0.30, 0.0]),
            18,
            LEFT,
        )
    if "aceleracion" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"a ≈ {_numero_latex(figura.aceleracion)} m/s²",
            np.array([0.0, abajo - 0.26, 0.0]),
            18,
        )

    rayas = [rueda, cuerda, izq, der, bloque_a, bloque_b]
    todo = VGroup(*rayas, mov_a, mov_b, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=rayas, aparece=[mov_a, mov_b, *rótulos])


# ------------------------------------------------------------------------------------------
# Elección del dibujo según el guion
# ------------------------------------------------------------------------------------------


def dibujar_visual(visual: Any, col: Any, ancho: float, alto: float, papel: str | None = None) -> Dibujo:
    """El ``visual:`` de un paso convertido en dibujo, centrado en el origen.

    ``papel`` es el color sobre el que se dibuja: sirve para 'cortar' un cable con una caja del
    mismo color (resistencias, batería y las medidas del polígono) sin que se note el truco.
    """
    papel = papel or col.fondo
    if visual.tipo == "grafico_funcion":
        return grafico_funcion(
            visual.funcion_analizada(), col, ancho, alto, visual.eje_x, visual.eje_y, papel
        )
    if visual.tipo == "diagrama_fuerzas":
        return diagrama_fuerzas(
            visual.vectores, col, ancho, alto, visual.cuerpo, visual.angulo, visual.descomponer
        )
    if visual.tipo == "poligono_regular":
        return poligono_regular(visual.poligono(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "proyectil":
        return proyectil(visual.proyectil(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "circulo_trig":
        return circulo_trig(visual.angulo_trig(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "solido":
        return solido(visual.solido(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "venn":
        return venn(visual.venn(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "recta":
        return recta(visual.recta(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "probabilidad":
        return probabilidad(visual.probabilidad(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "torta":
        return torta(visual.torta(), col, ancho, alto, papel)
    if visual.tipo == "barras":
        return barras(visual.barras(), col, ancho, alto, papel)
    if visual.tipo == "onda":
        return onda(visual.onda(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "energia":
        return energia(visual.energia(), col, ancho, alto, papel)
    if visual.tipo == "optica":
        return optica(visual.optica(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "pendulo":
        return pendulo(visual.pendulo(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "resorte":
        return resorte(visual.resorte(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "polea":
        return polea(visual.polea(), visual.anotar, col, ancho, alto, papel)
    fuente, resistencias = analizar_circuito(visual.fuente, visual.resistencias)
    return circuito(fuente, resistencias, col, ancho, alto, visual.arreglo, papel)
