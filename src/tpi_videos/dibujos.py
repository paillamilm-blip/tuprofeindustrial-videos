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
    Line,
    Mobject,
    Polygon,
    Rectangle,
    VGroup,
    VMobject,
)

from . import componentes as c
from .visuales import Funcion, Poligono, analizar_circuito

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
        return diagrama_fuerzas(visual.vectores, col, ancho, alto, visual.cuerpo, visual.angulo)
    if visual.tipo == "poligono_regular":
        return poligono_regular(visual.poligono(), visual.anotar, col, ancho, alto, papel)
    fuente, resistencias = analizar_circuito(visual.fuente, visual.resistencias)
    return circuito(fuente, resistencias, col, ancho, alto, visual.arreglo, papel)
