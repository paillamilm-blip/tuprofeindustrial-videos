"""Los cuatro dibujos que el motor sabe hacer en Manim: función, fuerzas, circuito y polígono regular.

Cada constructor devuelve un ``Dibujo`` centrado en el origen y ajustado a una caja (ancho × alto),
con las piezas separadas entre lo que se **traza** (``Create``) y lo que **aparece** (``FadeIn``).
La matemática ya viene analizada en ``visuales.py``; aquí sólo se dibuja.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
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
    TAU,
    UP,
    Arc,
    Arrow,
    CapStyleType,
    Circle,
    CurvedArrow,
    DashedLine,
    DashedVMobject,
    Dot,
    Ellipse,
    Line,
    ManimColor,
    Mobject,
    Polygon,
    Rectangle,
    Sector,
    TracedPath,
    VGroup,
    VMobject,
)

from . import componentes as c
from .errores import ErrorMotor
from .simulacion import Oscilador, PenduloDoble
from .visuales import (
    DURACION_RESORTE,
    AnguloTrig,
    Barras,
    Bloques,
    Cercha,
    Energia,
    Engranaje,
    Escala,
    Funcion,
    Mohr,
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
    Tanque,
    Torta,
    Venn,
    Viga,
    analizar_circuito,
)

ALTO_DIBUJO = 3.3  # franja del pie de la pizarra que ocupa un dibujo
GROSOR_MINIMO = 3.2  # en un teléfono el trazo de 1-2 px desaparece: se lee como marcador

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
    """Un dibujo listo para la escena: su grupo, cómo sale cada parte y, si se mueve, su pose."""

    mobs: VGroup
    trazo: list[Mobject] = field(default_factory=list)  # se dibujan con Create
    aparece: list[Mobject] = field(default_factory=list)  # aparecen con FadeIn
    vivo: Callable[[float], None] | None = None  # pinta la pose p ∈ [0, 1]
    duracion: float | None = None  # segundos de física que pide la pose
    estela: Mobject | None = None  # la traza que crece; la escena la agrega sola
    # True: la pose corre a tiempo físico real (A). False: no hay reloj físico que respetar (una
    # tangente, un área, una órbita de cámara) y el recorrido se reparte entero en la voz del paso.
    fisico: bool = True
    # Lo que ``place`` corre el dibujo: la pose lo consulta para no volver al origen.
    desplazamiento: list[np.ndarray] = field(default_factory=lambda: [np.zeros(3)], repr=False)
    # Un cuerpo 3D: la vista (phi, theta) en la que termina y si queda con las piezas separadas. El paso
    # siguiente, si es el mismo dibujo, parte de ahí (``desde_vista``) en vez de dar la vuelta de nuevo.
    vista_final: tuple[float, float] | None = None  # None en los dibujos 2D
    separado_final: bool = False
    # Hasta dónde llegó su recorrido (0..1): si la voz cortó la física, el paso siguiente sigue desde ahí.
    pose_final: float = 1.0

    def place(self, x: float, y: float) -> Dibujo:
        delta = np.array([x, y, 0.0]) - self.mobs.get_center()
        self.mobs.shift(delta)
        self.desplazamiento[0] = self.desplazamiento[0] + delta
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


def afinar_trazo(mobs: VGroup, minimo: float = GROSOR_MINIMO) -> None:
    """Sube el trazo fino al grosor mínimo y redondea las puntas; los rellenos sin borde no se tocan."""
    for m in mobs.get_family():
        # solo las piezas que dibujan su propio trazo: un grupo o un texto no tienen borde que engrosar
        if isinstance(m, VMobject) and not m.submobjects and m.get_stroke_width() > 0:
            m.set_stroke(width=max(m.get_stroke_width(), minimo))
            m.set_cap_style(CapStyleType.ROUND)


# El tamaño que pidió el guion (``visual.tamano``): la fracción de la tarjeta que ocupa el dibujo.
# None = «auto»: solo se achica lo que no cabe. Se fija en ``dibujar_visual`` mientras se construye.
RELLENO = {"chico": 0.6, "mediano": 0.8, "grande": 1.0}
_relleno: ContextVar[float | None] = ContextVar("relleno_del_dibujo", default=None)
# Si el cuerpo 3D sigue del paso anterior: (phi, theta, ya separado) de donde quedó, y la órbita parte de ahí.
# None = la órbita de siempre (75° antes de la vista pedida). La fija la escena mientras construye.
desde_vista: ContextVar[tuple[float, float, bool] | None] = ContextVar("desde_vista", default=None)


def factor_de_encaje(ancho_dibujo: float, alto_dibujo: float, ancho: float, alto: float) -> float:
    """Cuánto se escala un dibujo de ese tamaño para su franja: achica lo que no cabe y, si el guion
    pidió un tamaño, lo lleva justo a esa fracción (agrandándolo si hace falta)."""
    excedido = max(ancho_dibujo / ancho, alto_dibujo / alto, 1e-9)
    relleno = _relleno.get()
    if relleno is None:
        return 1.0 / excedido if excedido > 1.0 else 1.0
    return relleno / excedido


def _encajar(todo: VGroup, ancho: float, alto: float) -> VGroup:
    """Si el dibujo se sale de la franja del pie, se encoge entero (o toma el tamaño que pidió el guion)."""
    factor = factor_de_encaje(todo.width, todo.height, ancho, alto)
    return todo if factor == 1.0 else todo.scale(factor)


def _encaje(
    todo: VGroup, ancho: float, alto: float
) -> tuple[Callable[[np.ndarray], np.ndarray], list[np.ndarray]]:
    """Encaja el grupo y devuelve cómo llevar un punto suyo al encuadre final.

    ``fijo`` deja un punto de la figura donde quedó dibujado: incluye el encogido y lo que después
    lo mueva ``place``. La caja de desplazamiento es la misma que guarda el ``Dibujo``, así la pose
    nunca vuelve al origen cuando el dibujo ya cambió de sitio.
    """
    centro = todo.get_center().copy()
    factor = factor_de_encaje(todo.width, todo.height, ancho, alto)
    if factor != 1.0:
        todo.scale(factor)
    desplazamiento = [np.zeros(3)]

    def fijo(p: np.ndarray) -> np.ndarray:
        return centro + (np.asarray(p, dtype=float) - centro) * factor + desplazamiento[0]

    return fijo, desplazamiento


def _color_de_magnitud(col: Any, fraccion: float) -> ManimColor:
    """Del tenue al acento y, sólo al tope, al error: la magnitud también se lee en el color."""
    f = min(max(fraccion, 0.0), 1.0)
    if f <= 0.5:
        return ManimColor(col.tenue).interpolate(ManimColor(col.acento), f * 2.0)
    return ManimColor(col.acento).interpolate(ManimColor(col.error), (f - 0.5) * 2.0)


def _apuntar(
    vector: Arrow, origen: np.ndarray, direccion: np.ndarray, largo: float, color: ManimColor
) -> None:
    """Reapunta una flecha en su sitio: la punta queda a ``largo`` del origen y el relleno sigue al color."""
    norma = float(np.linalg.norm(direccion))
    unitaria = direccion / norma if norma > 1e-9 else np.array([1.0, 0.0, 0.0])
    vector.put_start_and_end_on(origen, origen + unitaria * max(largo, 0.04))
    vector.set_color(color)


def _estela(punto: Mobject, color: str, grosor: float) -> TracedPath:
    """La traza que crece con el punto; se siembra en su posición para no nacer en el origen."""
    traza = TracedPath(punto.get_center, stroke_color=color, stroke_width=grosor)
    traza.set_points_as_corners([punto.get_center(), punto.get_center()])
    return traza


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
    movimiento: str = "",
    desde: float | None = None,
    hasta: float | None = None,
    anotar: list[str] | None = None,
) -> Dibujo:
    """Ejes con numeración, la curva trazada y un punto en cada raíz y en el vértice.

    Con ``movimiento`` el gráfico además vive: una tangente recorre la curva (y su pendiente se lee
    al instante) o el área bajo ella se llena con su partición. Sin él, es el gráfico de siempre.
    """
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
    if not movimiento:
        _encajar(todo, ancho, alto)
        return Dibujo(mobs=todo, trazo=[*ejes, *curva], aparece=[numeros, nombres, marcas])
    fijo, desplazamiento = _encaje(todo, ancho, alto)
    caja = (izquierda, derecha, abajo, arriba)
    a = x0 if desde is None else float(desde)
    b = x1 if hasta is None else float(hasta)
    criticos = [x for x in f.puntos if a - 1e-9 <= x <= b + 1e-9]
    vivas = _curva_viva(
        f, p, fijo, caja, (y0, y1), horizontal, a, b, criticos, movimiento, anotar or [], col, papel
    )
    todo.add(*vivas.piezas)
    vivas.vivo(0.0)
    return Dibujo(
        mobs=todo,
        trazo=[*ejes, *curva],
        aparece=[numeros, nombres, marcas, *vivas.aparece],
        vivo=vivas.vivo,
        duracion=SEGUNDOS_RECORRIDO,
        desplazamiento=desplazamiento,
        fisico=False,
    )


# Lo que dura, como referencia, un recorrido sin física (tangente, área, órbita). La escena no lo
# respeta al pie de la letra: con ``fisico=False`` estira o comprime el recorrido a la voz del paso.
SEGUNDOS_RECORRIDO = 4.0


@dataclass
class _Viva:
    piezas: list[Mobject]  # todo lo que se agrega al dibujo
    aparece: list[Mobject]  # lo que entra con FadeIn antes de empezar a moverse
    vivo: Callable[[float], None]


def _suave(t: float) -> float:
    """Arranque y frenada suaves (smoothstep): el recorrido no da tirones al empezar ni al terminar."""
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _recortar(
    centro: np.ndarray, direccion: np.ndarray, largo: float, caja: tuple[float, float, float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """El segmento de ``largo`` centrado en ``centro``, recortado a la caja de la gráfica (Liang–Barsky)."""
    izq, der, aba, arr = caja
    t0, t1 = -largo / 2, largo / 2
    for p_, q_ in (
        (-direccion[0], centro[0] - izq),
        (direccion[0], der - centro[0]),
        (-direccion[1], centro[1] - aba),
        (direccion[1], arr - centro[1]),
    ):
        if abs(p_) < 1e-12:
            continue
        r = q_ / p_
        if p_ < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
    if t1 < t0:
        t0 = t1 = 0.0
    return centro + direccion * t0, centro + direccion * t1


def _curva_viva(
    f: Funcion,
    p: Callable[[float, float], np.ndarray],
    fijo: Callable[[np.ndarray], np.ndarray],
    caja: tuple[float, float, float, float],
    rango_y: tuple[float, float],
    eje: float,
    a: float,
    b: float,
    criticos: list[float],
    movimiento: str,
    marcas: list[str],
    col: Any,
    papel: str,
) -> _Viva:
    """Las piezas móviles del gráfico vivo y su pose: todo se recalcula de la curva real.

    La pose es pura: recibe 0..1 y deja el punto, la recta o el relleno donde dice la función. No crea
    mobjects nuevos salvo el rótulo del valor, que se rehace solo cuando cambia el número escrito.
    """
    izq, der, aba, arr = caja
    y0, y1 = rango_y
    escala_x = (der - izq) / (f.rango_x[1] - f.rango_x[0])  # unidades de pantalla por unidad de x
    escala_y = (arr - aba) / (y1 - y0)

    def en_caja(x: float, y: float) -> np.ndarray:
        return p(x, min(max(y, y0), y1))

    # Los puntos críticos (raíces y vértice) se encienden cuando el recorrido pasa por ellos.
    halos = [
        Circle(radius=0.2)
        .set_stroke(col.acento, 6, 0.0)
        .set_fill(col.acento, 0.0)
        .move_to(fijo(en_caja(x, f.y(x) or 0.0)))
        for x in criticos
        if f.y(x) is not None
    ]
    ancho_halo = max((b - a) * 0.09, 1e-6)

    def encender(x_actual: float) -> None:
        for halo, xc in zip(halos, [x for x in criticos if f.y(x) is not None], strict=True):
            cerca = max(0.0, 1.0 - abs(x_actual - xc) / ancho_halo)
            halo.set_stroke(opacity=0.85 * cerca).set_fill(opacity=0.18 * cerca)
            halo.set_width(0.4 + 0.35 * cerca)

    rotulo_caja = VGroup()  # el valor en vivo, con su papel detrás para que la curva no lo tape
    escrito = [""]

    def escribir(texto: str) -> None:
        if texto == escrito[0]:
            return
        escrito[0] = texto
        # Arriba a la derecha, alineado por la derecha: cambia de ancho sin moverse de su esquina.
        # Se calcula cada vez: ``fijo`` sigue al dibujo cuando la escena lo cambia de sitio.
        esquina = fijo(np.array([der - 0.1, arr - 0.05, 0.0]))
        nuevo = c.texto(texto, 22, SEMIBOLD, col.texto)
        nuevo.move_to(esquina + LEFT * nuevo.width / 2 + DOWN * nuevo.height / 2)
        # Se cambian los hijos, no se usa become(): con otro número de letras become() rellena con
        # copias y quedan letras fantasma. Los hijos viejos además se apagan: Manim arma la lista de
        # lo que pinta al empezar cada animación y los seguiría dibujando encima del valor nuevo.
        for viejo in rotulo_caja.submobjects:
            viejo.set_opacity(0.0)
        rotulo_caja.submobjects = list(_parche(nuevo, papel, 0.16).submobjects)

    if movimiento == "tangente":
        punto = Dot(radius=0.085).set_fill(col.error, 1).set_stroke(col.formulas, 2)
        recta = Line(LEFT, RIGHT).set_stroke(col.tenue, 6)
        largo = (der - izq) * 0.42
        lee = "pendiente" in marcas

        def vivo(t: float) -> None:
            x = a + _suave(t) * (b - a)
            y, m = f.y(x), f.derivada(x)
            if y is None or m is None or not (y0 <= y <= y1):
                punto.set_opacity(0.0)
                recta.set_stroke(opacity=0.0)
                encender(x)
                return
            centro = p(x, y)
            # La pendiente en pantalla no es la de los datos: cada eje tiene su propia escala.
            direccion = np.array([escala_x, m * escala_y, 0.0])
            direccion /= float(np.linalg.norm(direccion))
            ini, fin = _recortar(centro, direccion, largo, caja)
            if float(np.linalg.norm(fin - ini)) < 1e-6:
                fin = ini + direccion * 1e-3
            recta.put_start_and_end_on(fijo(ini), fijo(fin))
            # Plana se ve tenue; subiendo va al acento y bajando al rojo: el signo de m también se ve.
            inclinacion = min(abs(m) * escala_y / escala_x / 1.5, 1.0)
            destino = col.acento if m >= 0 else col.error
            recta.set_stroke(ManimColor(col.tenue).interpolate(ManimColor(destino), inclinacion), opacity=1.0)
            punto.move_to(fijo(centro)).set_opacity(1.0)
            encender(x)
            if lee:
                escribir(f"m = {_numero_latex(m)}")

        piezas: list[Mobject] = [*halos, recta, punto]
        if lee:
            piezas.append(rotulo_caja)
        return _Viva(piezas=piezas, aparece=[recta, punto, *([rotulo_caja] if lee else [])], vivo=vivo)

    # —— El área: se llena de izquierda a derecha, con la partición marcando los tramos ——————
    base = min(max(eje, aba), arr)
    positivo = VMobject().set_fill(col.acento, 0.38).set_stroke(width=0)
    negativo = VMobject().set_fill(col.error, 0.32).set_stroke(width=0)
    barrido = Line(UP, DOWN).set_stroke(col.acento, 4)
    tramos = 8
    particion = [Line(UP, DOWN).set_stroke(col.formulas, 2.5, 0.0) for _ in range(tramos - 1)]
    cortes = [a + (b - a) * k / tramos for k in range(1, tramos)]
    lee = "area" in marcas
    muestras = 64

    def relleno(x_fin: float, signo: float) -> list[np.ndarray]:
        xs = [a + (x_fin - a) * i / muestras for i in range(muestras + 1)]
        arriba_ = []
        for x in xs:
            y = f.y(x) or 0.0
            y = max(y, 0.0) if signo > 0 else min(y, 0.0)
            arriba_.append(fijo(en_caja(x, y)))
        return [
            fijo(np.array([p(a, 0.0)[0], base, 0.0])),
            *arriba_,
            fijo(np.array([p(x_fin, 0.0)[0], base, 0.0])),
        ]

    def vivo(t: float) -> None:
        x = a + _suave(t) * (b - a)
        x = max(x, a + (b - a) * 1e-3)
        positivo.set_points_as_corners(relleno(x, 1.0))
        negativo.set_points_as_corners(relleno(x, -1.0))
        y = f.y(x) or 0.0
        barrido.put_start_and_end_on(
            fijo(np.array([p(x, 0.0)[0], base, 0.0])), fijo(en_caja(x, y)) + np.array([0.0, 1e-4, 0.0])
        )
        for linea, xc in zip(particion, cortes, strict=True):
            yc = f.y(xc) or 0.0
            linea.put_start_and_end_on(
                fijo(np.array([p(xc, 0.0)[0], base, 0.0])), fijo(en_caja(xc, yc)) + np.array([0.0, 1e-4, 0.0])
            )
            linea.set_stroke(opacity=0.55 if xc <= x else 0.0)
        encender(x)
        if lee:
            escribir(f"A ≈ {_numero_latex(f.area(a, x))}")

    piezas = [negativo, positivo, *particion, *halos, barrido]
    if lee:
        piezas.append(rotulo_caja)
    return _Viva(piezas=piezas, aparece=[barrido, *([rotulo_caja] if lee else [])], vivo=vivo)


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

    if "perimetro" in marcas:
        # Arriba, donde no hay nada: n lados iguales dan la vuelta entera.
        total = figura.lados * figura.lado
        medida(
            f"P = {figura.lados} · {_numero_latex(figura.lado)} = {_numero_latex(total)}{_sufijo(figura)}",
            [0.0, arriba + 0.42, 0.0],
            24,
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


LARGO_COMPONENTE = 0.7  # el largo máximo de vx y vy dentro del dibujo


def proyectil(
    figura: Proyectil, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El vuelo completo: la bola recorre la parábola en el tiempo real y la estela queda.

    La guía tenue deja ver hacia dónde va; las componentes de la velocidad crecen y cambian de color
    con la bola: ``vx`` no cambia nunca y ``vy`` se apaga hasta invertirse en la bajada.
    """
    # El 0,55 deja aire bajo el suelo para que la flecha de vy quepa cuando apunta hacia abajo.
    escala = min(ancho * 0.9 / figura.alcance, alto * 0.55 / figura.altura)
    gravedad = 2 * figura.vertical / figura.tiempo
    mitad = figura.alcance * escala / 2

    def posicion(t: float) -> np.ndarray:
        return np.array(
            [
                figura.horizontal * t * escala - mitad,
                (figura.vertical * t - gravedad * t * t / 2) * escala,
                0.0,
            ]
        )

    izquierda, derecha = posicion(0.0), posicion(figura.tiempo)
    cima = posicion(figura.tiempo / 2)

    suelo = Line(izquierda + LEFT * 0.3, derecha + RIGHT * 0.3, buff=0).set_stroke(col.tenue, 5)
    curva = VMobject().set_points_smoothly([posicion(figura.tiempo * i / 48) for i in range(49)])
    curva.set_stroke(col.tenue, 3)
    rayas: list = [suelo, curva]
    parches, rótulos = VGroup(), VGroup()

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
    if "tiempo" in marcas:
        # Bajo el suelo, al centro: el alcance va en la punta derecha.
        medida(f"t ≈ {_numero_latex(figura.tiempo)} s", np.array([0.0, izquierda[1] - 0.36, 0.0]), 24)
    if "altura_maxima" in marcas:
        bajada = DashedLine(cima, cima * np.array([1.0, 0.0, 1.0]), buff=0).set_stroke(col.acento, 4)
        rayas.append(bajada)
        medida(
            f"h ≈ {_numero_latex(figura.altura)}{_sufijo_proyectil(figura)}",
            cima + np.array([0.95, -0.3, 0.0]),
            24,
        )

    bola = Dot(radius=0.075).set_fill(col.acento, 1).set_stroke(width=0)
    aparece: list[Mobject] = [bola]
    vectores: list[Arrow] = []
    etiquetas = VGroup()
    if "componentes" in marcas:
        vx = Arrow(
            izquierda,
            izquierda + RIGHT * LARGO_COMPONENTE,
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.22,
        )
        vy = Arrow(
            izquierda,
            izquierda + UP * LARGO_COMPONENTE,
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.22,
        )
        vectores = [vx, vy]
        etiquetas = VGroup(
            c.texto("vx", 20, SEMIBOLD, col.texto),
            c.texto("vy", 20, SEMIBOLD, col.texto),
        )
        aparece.extend([*vectores, etiquetas])
    aparece.extend(rótulos)

    todo = VGroup(suelo, curva, *rayas[2:], *vectores, parches, rótulos, etiquetas, bola)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        t = p * figura.tiempo
        centro = fijo(posicion(t))
        bola.move_to(centro)
        if not vectores:
            return
        vx, vy = vectores
        vy_actual = figura.vertical - gravedad * t
        rapidez_x = abs(figura.horizontal) / figura.velocidad
        rapidez_y = abs(vy_actual) / figura.velocidad
        _apuntar(
            vx,
            centro,
            RIGHT * figura.horizontal,
            LARGO_COMPONENTE * rapidez_x,
            _color_de_magnitud(col, rapidez_x),
        )
        _apuntar(
            vy,
            centro,
            UP * (vy_actual if abs(vy_actual) > 1e-9 else 1.0),
            LARGO_COMPONENTE * rapidez_y,
            _color_de_magnitud(col, rapidez_y),
        )
        rotulo_vx, rotulo_vy = etiquetas
        rotulo_vx.move_to(centro + RIGHT * (LARGO_COMPONENTE * rapidez_x + 0.18))
        rotulo_vy.move_to(centro + UP * np.sign(vy_actual or 1.0) * (LARGO_COMPONENTE * rapidez_y + 0.18))

    vivo(0.0)
    estela = _estela(bola, col.acento, 5)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=rayas,
        aparece=aparece,
        vivo=vivo,
        duracion=figura.tiempo,
        estela=estela,
        desplazamiento=desplazamiento,
    )


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
# 8b · La escala: el dibujo que demuestra (caben factor² cuadrados o factor³ cubos)
# ------------------------------------------------------------------------------------------


def _con_opacidad(pieza: VGroup, bases: list[float], a: float) -> None:
    """Enciende una pieza (sus caras o su cuadrado) a la fracción ``a`` de su opacidad propia."""
    for cara, base in zip(pieza, bases, strict=True):
        cara.set_fill(opacity=base * a).set_stroke(opacity=a)


def escala(
    figura: Escala, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """Agrandar el lado: las piezas del original entran de a una hasta llenar la figura grande.

    No es una ilustración de la fórmula: es la prueba. Primero se ve que caben 8 cubos (o 4
    cuadrados) y recién después la fórmula lo dice. La primera pieza es el original, con su medida.
    """
    k, n = figura.factor, figura.piezas
    acento = ManimColor(col.acento)
    oscuro = ManimColor(col.fondo)
    piezas: list[VGroup] = []  # en el orden en que entran: la primera es el original
    bases: list[list[float]] = []
    contorno: list[Mobject] = []
    parches, rótulos = VGroup(), VGroup()

    if figura.dimension == 3:
        s = 0.9 if k == 2 else 0.62
        cx, cy = 0.866 * s, 0.5 * s

        def iso(i: float, j: float, h: float) -> np.ndarray:
            return np.array([(i - j) * cx, h * s - (i + j) * cy, 0.0])

        celdas = [(i, j, h) for h in range(k) for i in range(k) for j in range(k)]
        original = (k - 1, k - 1, 0)  # el de adelante y abajo: se ve entero desde el primer segundo
        resto = sorted((x for x in celdas if x != original), key=lambda t: (t[2], t[0] + t[1]))
        entrada = [original, *resto]
        cubo: dict[tuple[int, int, int], VGroup] = {}
        for i, j, h in celdas:
            a1, b1 = i + 1, j + 1
            arriba = Polygon(iso(i, j, h + 1), iso(a1, j, h + 1), iso(a1, b1, h + 1), iso(i, b1, h + 1))
            derecha = Polygon(iso(a1, j, h), iso(a1, b1, h), iso(a1, b1, h + 1), iso(a1, j, h + 1))
            izquierda = Polygon(iso(i, b1, h), iso(a1, b1, h), iso(a1, b1, h + 1), iso(i, b1, h + 1))
            caras = VGroup(arriba, derecha, izquierda)
            for cara, tono in zip(caras, (0.0, 0.35, 0.55), strict=True):
                cara.set_fill(acento.interpolate(oscuro, tono), 1.0).set_stroke(papel, 2)
            cubo[(i, j, h)] = caras
        for celda in entrada:
            piezas.append(cubo[celda])
            bases.append([0.97, 0.97, 0.97])
        tapa = [iso(*e) for e in ((0, 0, k), (k, 0, k), (k, k, k), (0, k, k))]
        for p, q in zip(tapa, tapa[1:] + tapa[:1], strict=True):
            contorno.append(DashedLine(p, q, dash_length=0.12).set_stroke(col.tenue, 2.5))
        aristas = (
            ((k, 0, k), (k, 0, 0)), ((k, k, k), (k, k, 0)), ((0, k, k), (0, k, 0)),  # las verticales
            ((k, 0, 0), (k, k, 0)), ((0, k, 0), (k, k, 0)),  # el pie
        )  # fmt: skip
        for p, q in aristas:
            contorno.append(DashedLine(iso(*p), iso(*q), dash_length=0.12).set_stroke(col.tenue, 2.5))
        # orden de pintado: lo de atrás primero, así cada cubo tapa al que tiene detrás
        pintado = [cubo[t] for t in sorted(celdas, key=lambda t: (t[0] + t[1] + t[2], t[2]))]
        donde_a = (iso(k, k - 1, 0) + iso(k, k, 0)) / 2 + np.array([0.55, -0.3, 0.0])
        donde_ka = (iso(0, k, 0) + iso(k, k, 0)) / 2 + np.array([-0.7, -0.3, 0.0])
        borde_derecho = iso(k, 0, k)[0]
        techo = iso(0, 0, k)[1]
    else:
        s = 1.0 if k == 2 else 0.75
        base = -(k * s) / 2

        def esquina(i: float, j: float) -> np.ndarray:
            return np.array([base + i * s, base + j * s, 0.0])

        celdas2 = [(i, j) for j in range(k) for i in range(k)]
        cuadro: dict[tuple[int, int], VGroup] = {}
        for i, j in celdas2:
            q = Polygon(esquina(i, j), esquina(i + 1, j), esquina(i + 1, j + 1), esquina(i, j + 1))
            q.set_fill(acento, 0.9).set_stroke(papel, 3)
            cuadro[(i, j)] = VGroup(q)
        for celda in celdas2:  # el original es el de abajo a la izquierda; después, fila por fila
            piezas.append(cuadro[celda])
            bases.append([0.9])
        borde = [esquina(0, 0), esquina(k, 0), esquina(k, k), esquina(0, k)]
        for p, q in zip(borde, borde[1:] + borde[:1], strict=True):
            contorno.append(DashedLine(p, q, dash_length=0.12).set_stroke(col.tenue, 2.5))
        pintado = [cuadro[c2] for c2 in celdas2]
        donde_a = (esquina(0, 0) + esquina(1, 0)) / 2 + np.array([0.0, -0.32, 0.0])
        donde_ka = (esquina(0, 0) + esquina(0, k)) / 2 + np.array([-0.95, 0.0, 0.0])
        borde_derecho = esquina(k, k)[0]
        techo = esquina(k, k)[1]

    unidad = f" {figura.unidad}" if figura.unidad else ""
    _cartela(col, papel, parches, rótulos, f"a = {_numero_latex(figura.lado)}{unidad}", donde_a, 18)
    grande = f"{k}a = {_numero_latex(figura.lado_grande)}{unidad}"
    _cartela(col, papel, parches, rótulos, grande, donde_ka, 18)

    # El contador y la razón los enciende ``vivo``: no entran con el resto de los rótulos.
    contadores: list[VGroup] = []
    x_lado = borde_derecho + 1.05
    if "contador" in marcas:
        for numero in range(1, n + 1):
            texto = c.texto(f"{numero} de {n}", 22, SEMIBOLD, col.texto)
            texto.move_to([x_lado, techo - 0.2, 0.0])
            contadores.append(VGroup(*_parche(texto, papel, 0.12)))
    razon: VGroup | None = None
    if "razon" in marcas:
        signo = c.texto(f"×{n}", 44, SEMIBOLD, col.acento).move_to([x_lado, techo - 1.0, 0.0])
        razon = VGroup(*_parche(signo, papel, 0.14))

    todo = VGroup(*contorno, *pintado, parches, rótulos, *contadores, *([razon] if razon is not None else []))
    _fijo, desplazamiento = _encaje(todo, ancho, alto)

    inicio, fin = 0.08, 0.86  # la primera pieza ya está; las demás entran repartidas en este tramo
    tramo = (fin - inicio) / max(n - 1, 1)

    def vivo(p: float) -> None:
        encendidas = 1
        for indice, (pieza, opacidades) in enumerate(zip(piezas, bases, strict=True)):
            if indice == 0:
                a = 1.0
            else:
                a = min(max((p - inicio - (indice - 1) * tramo) / (tramo * 0.8), 0.0), 1.0)
                encendidas += a >= 0.5
            _con_opacidad(pieza, opacidades, a)
        for numero, rotulo in enumerate(contadores, 1):
            visible = 1.0 if numero == encendidas else 0.0
            rotulo[0].set_fill(opacity=visible)
            rotulo[1].set_fill(opacity=visible)
        if razon is not None:
            a = min(max((p - 0.9) / 0.08, 0.0), 1.0)
            razon[0].set_fill(opacity=a)
            razon[1].set_fill(opacity=a)

    vivo(1.0)  # la miniatura del panel muestra la figura llena
    return Dibujo(
        mobs=todo, trazo=contorno, aparece=[*rótulos], vivo=vivo, duracion=SEGUNDOS_RECORRIDO,
        fisico=False, desplazamiento=desplazamiento,
    )  # fmt: skip


# ------------------------------------------------------------------------------------------
# 9 · Estadística: torta y barras
# ------------------------------------------------------------------------------------------


def _paleta(col: Any) -> list[str]:
    """Colores del tema, en un orden que se distingue bien uno del otro en la hoja."""
    from .temas import colores_distintos

    # Sin repetir: en la familia Consola el acento puede ser el mismo verde del éxito (Reto) o el rojo
    # del error (Error), y dos porciones del mismo color se leen como una sola.
    return colores_distintos(
        [col.acento, col.cuadricula, col.exito, col.error, col.tenue, col.formulas],
        getattr(col, "panel", None),
    )


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
    # Lo que se deduce del período va bajo la onda, de a una línea: con solo la velocidad queda donde estaba.
    abajo = [
        f"f = 1/T ≈ {_numero_latex(figura.frecuencia)} Hz"
        if "frecuencia" in marcas and figura.frecuencia is not None
        else None,
        f"v = λ/T ≈ {_numero_latex(figura.velocidad)}{uni}/s"
        if "velocidad" in marcas and figura.velocidad is not None
        else None,
    ]
    for i, texto in enumerate(t for t in abajo if t):
        etiqueta(texto, np.array([0.0, -a_px - 0.55 - 0.5 * i, 0.0]), 18)

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
    """El hilo que va y vuelve en su período real; la estela queda y, si se pide, la velocidad.

    La posición sale de ``θ(t) = θ₀·cos(2πt/T)``: el ángulo de la oscilación armónica, no una
    interpolación a ojo. La velocidad es tangente al arco y se apaga en los extremos, donde vale cero.
    """
    s = alto * 0.52
    uni = f" {figura.unidad}" if figura.unidad else ""
    t0 = np.radians(figura.angulo)
    pivote = np.array([0.0, s / 2, 0.0])

    apoyo = Line(pivote + [-0.4, 0, 0], pivote + [0.4, 0, 0]).set_stroke(col.formulas, 5)
    vertical = DashedLine(pivote, pivote + [0.0, -s, 0.0]).set_stroke(col.tenue, 3)
    vuelo = Arc(radius=s, start_angle=-PI / 2 - t0, angle=2 * t0, arc_center=pivote)
    vuelo.set_stroke(col.formulas, 2)
    hilo = Line(pivote, pivote + np.array([-s * np.sin(t0), -s * np.cos(t0), 0.0])).set_stroke(
        col.formulas, 4
    )
    angulo = Arc(radius=s * 0.30, start_angle=-PI / 2, angle=-t0, arc_center=pivote)
    angulo.set_stroke(col.acento, 3)
    bola = Dot(radius=0.15).set_fill(col.acento, 0.95).set_stroke(col.acento, 2)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.angulo)}°",
        pivote
        + np.array(
            [(s * 0.30 + 0.38) * np.cos(-PI / 2 - t0 / 2), (s * 0.30 + 0.38) * np.sin(-PI / 2 - t0 / 2), 0.0]
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

    velocidad = None
    if "velocidad" in marcas:
        velocidad = Arrow(
            pivote, pivote + RIGHT * 0.4, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.25
        )

    rayas = [apoyo, vertical, vuelo, hilo, angulo, *([velocidad] if velocidad else [])]
    todo = VGroup(*rayas, bola, parches, rótulos)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        # Una vuelta completa: θ pasa de θ₀ a -θ₀ y vuelve. La pausa nunca congela la física.
        t = t0 * np.cos(TAU * p)
        centro = fijo(pivote + np.array([-s * np.sin(t), -s * np.cos(t), 0.0]))
        bola.move_to(centro)
        hilo.put_start_and_end_on(fijo(pivote), centro)
        if velocidad is None:
            return
        rapidez = abs(np.sin(TAU * p))
        sentido = 1.0 if np.sin(TAU * p) >= 0 else -1.0
        direccion = np.array([np.cos(t), -np.sin(t), 0.0]) * sentido
        _apuntar(velocidad, centro, direccion, s * 0.30 * rapidez, _color_de_magnitud(col, rapidez))
        velocidad.set_opacity(min(1.0, rapidez / 0.20))

    vivo(0.0)
    estela = _estela(bola, col.acento, 4)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=rayas,
        aparece=[bola, *rótulos],
        vivo=vivo,
        duracion=figura.periodo,
        estela=estela,
        desplazamiento=desplazamiento,
    )


def _puntos_espira(x_pared: float, x_fin: float, n: int) -> list[np.ndarray]:
    """La espira entre la pared y el extremo libre, con siempre las mismas vueltas."""
    largo = x_fin - x_pared
    paso = (largo - 0.30) / n
    pts = [np.array([x_pared, 0.0, 0.0]), np.array([x_pared + 0.15, 0.0, 0.0])]
    for i in range(n):
        x0 = x_pared + 0.15 + paso * i
        pts.append(np.array([x0 + paso / 2, 0.24 if i % 2 == 0 else -0.24, 0.0]))
        pts.append(np.array([x0 + paso, 0.0, 0.0]))
    pts.append(np.array([x_fin, 0.0, 0.0]))
    return pts


def resorte(
    figura: Resorte, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La ley de Hooke en movimiento: la espira se estira y la fuerza crece con ella.

    La cota mide la extensión final que pide el guion y no se mueve; lo que se mueve es el extremo
    libre, el bloque y la flecha de la fuerza. El estiramiento es suave, como el de una mano.
    """
    x_pared = -ancho * 0.32
    largo = ancho * 0.38
    lado = min(alto * 0.30, ancho * 0.13)
    x_fin = x_pared + largo
    x_reposo = x_fin - min(largo * 0.26, 0.65)

    pared = Line([x_pared, -alto * 0.28, 0], [x_pared, alto * 0.28, 0]).set_stroke(col.formulas, 5)
    rayado = VGroup(
        *[
            Line([x_pared, y + alto * 0.28, 0], [x_pared - 0.22, y + alto * 0.28 - 0.22, 0])
            for y in np.arange(-0.20, alto * 0.56, 0.32)
        ]
    ).set_stroke(col.tenue, 3)

    espira = VMobject().set_points_as_corners(_puntos_espira(x_pared, x_reposo, 7))
    espira.set_stroke(col.acento, 5)

    bloque = Rectangle(width=lado, height=lado).move_to([x_reposo + lado / 2, 0.0, 0.0])
    bloque.set_fill(col.acento, 0.22).set_stroke(col.formulas, 4)

    # La flecha arranca con su largo final: así entra en la caja del dibujo y después sólo se acorta.
    estira = Arrow(
        [x_fin + lado, 0.0, 0.0],
        [x_fin + lado + ancho * 0.12, 0.0, 0.0],
        buff=0,
        stroke_width=5,
        max_tip_length_to_length_ratio=0.30,
    )
    estira.set_stroke(col.error, 5).set_fill(col.error, 1)

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
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        suave = p * p * (3.0 - 2.0 * p)  # la mano no arranca ni frena de golpe
        x_t = x_reposo + (x_fin - x_reposo) * suave
        espira.set_points_as_corners([fijo(q) for q in _puntos_espira(x_pared, x_t, 7)])
        bloque.move_to(fijo(np.array([x_t + lado / 2, 0.0, 0.0])))
        largo_fuerza = max(ancho * 0.12 * suave, 0.04)
        estira.put_start_and_end_on(
            fijo(np.array([x_t + lado, 0.0, 0.0])),
            fijo(np.array([x_t + lado + largo_fuerza, 0.0, 0.0])),
        )
        estira.set_color(_color_de_magnitud(col, suave))

    vivo(0.0)
    estela = _estela(bloque, col.acento, 4)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=rayas,
        aparece=[cota, estira, *rótulos],
        vivo=vivo,
        duracion=DURACION_RESORTE,
        estela=estela,
        desplazamiento=desplazamiento,
    )


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
# 12) Ingeniería: el tanque que pierde, la viga apoyada y la cercha triangular
# ------------------------------------------------------------------------------------------


def tanque(
    figura: Tanque, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El tanque con su llave arriba y su válvula abajo: entra, se escapa y aun así se llena."""
    w, h = ancho * 0.30, alto * 0.52
    x_cuba = ancho * 0.03
    arriba, bajo = alto * 0.20, alto * 0.20 - h
    x_izq, x_der = x_cuba - w / 2, x_cuba + w / 2
    cuba = Rectangle(width=w, height=h).move_to([x_cuba, (arriba + bajo) / 2, 0.0])
    cuba.set_stroke(col.formulas, 5).set_fill(papel, 0)

    # El agua llega hasta su nivel y se corta en recto: sin la superficie parece un cartel, no un tanque.
    nivel = bajo + h * 0.45
    agua = (
        Rectangle(width=w - 0.08, height=nivel - bajo - 0.04)
        .move_to([x_cuba, (nivel + bajo) / 2, 0.0])
        .set_fill(col.cuadricula, 0.45)
        .set_stroke(width=0)
    )
    superficie = Line([x_izq + 0.04, nivel, 0], [x_der - 0.04, nivel, 0]).set_stroke(col.cuadricula, 5)

    x_llave = x_cuba - w * 0.22
    llave = Arrow(
        [x_llave, arriba + alto * 0.20, 0],
        [x_llave, arriba + alto * 0.02, 0],
        buff=0,
        stroke_width=5,
        max_tip_length_to_length_ratio=0.22,
    )
    llave.set_stroke(col.cuadricula, 5).set_fill(col.cuadricula, 1)

    # La salida es un tubo con su válvula: dos triángulos que se tocan de frente, el símbolo de siempre.
    y_tubo = bajo + h * 0.22
    tubo = Line([x_der, y_tubo, 0], [x_der + ancho * 0.17, y_tubo, 0]).set_stroke(col.formulas, 5)
    vx = x_der + ancho * 0.085
    valvula = VGroup(
        Polygon([vx, y_tubo, 0], [vx - 0.17, y_tubo + 0.17, 0], [vx - 0.17, y_tubo - 0.17, 0]),
        Polygon([vx, y_tubo, 0], [vx + 0.17, y_tubo + 0.17, 0], [vx + 0.17, y_tubo - 0.17, 0]),
    )
    valvula.set_stroke(col.formulas, 4).set_fill(papel, 1)
    fuga = Arrow(
        [x_der + ancho * 0.18, y_tubo, 0],
        [x_der + ancho * 0.26, y_tubo, 0],
        buff=0,
        stroke_width=5,
        max_tip_length_to_length_ratio=0.40,
    )
    fuga.set_stroke(col.error, 5).set_fill(col.error, 1)

    uni_v, uni_t = figura.unidad or "L", figura.unidad_tiempo or "min"
    ambos = "llenado" in marcas and "vaciado" in marcas and figura.vaciado is not None
    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.capacidad)} {uni_v}",
        np.array([x_cuba, arriba - h * 0.16, 0.0]),
        20,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"entran {_numero_latex(figura.entrada)} {uni_v}/{uni_t}",
        np.array([x_llave - 0.10, arriba + alto * 0.26, 0.0]),
        16,
        LEFT,
    )
    if figura.salida:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"se escapan {_numero_latex(figura.salida)} {uni_v}/{uni_t}",
            np.array([x_der + ancho * 0.155, y_tubo + 0.40, 0.0]),
            16,
        )
    if "llenado" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"se llena en ≈ {_numero_latex(figura.llenado)} {uni_t}",
            np.array([x_cuba - (ancho * 0.20 if ambos else 0.0), -alto * 0.42, 0.0]),
            17,
        )
    if "vaciado" in marcas and figura.vaciado is not None:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"se vacía en ≈ {_numero_latex(figura.vaciado)} {uni_t}",
            np.array([x_cuba + (ancho * 0.20 if ambos else 0.0), -alto * 0.42, 0.0]),
            17,
        )

    rayas = [cuba, agua, superficie, llave, tubo, valvula]
    todo = VGroup(*rayas, fuga, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=[cuba, tubo, valvula], aparece=[agua, superficie, llave, fuga, *rótulos])


def viga(
    figura: Viga, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La viga apoyada: los dos pies se reparten la carga y el vano se dobla en el centro."""
    vano = ancho * 0.60
    y_viga = alto * 0.17
    peralte = alto * 0.10
    canto = y_viga + peralte / 2
    x_izq, x_der = -vano / 2, vano / 2
    lomo = Rectangle(width=vano, height=peralte).move_to([0.0, y_viga, 0.0])
    lomo.set_stroke(col.formulas, 5).set_fill(col.formulas, 0.16)
    piso = y_viga - peralte / 2 - 0.34

    def pie(x: float, rodillos: bool) -> VGroup:
        pata = Polygon([x, y_viga - peralte / 2, 0], [x - 0.24, piso, 0], [x + 0.24, piso, 0])
        pata.set_stroke(col.formulas, 4).set_fill(col.acento, 0.18)
        grupo = VGroup(pata)
        if rodillos:
            ruedas = [Circle(radius=0.06).move_to([x + dx, piso - 0.11, 0.0]) for dx in (-0.13, 0.0, 0.13)]
            VGroup(*ruedas).set_stroke(col.formulas, 3).set_fill(papel, 1)
            grupo.add(*ruedas)
            grupo.add(
                Line([x - 0.32, piso - 0.20, 0], [x + 0.32, piso - 0.20, 0]).set_stroke(col.formulas, 5)
            )
        else:
            grupo.add(Line([x - 0.32, piso, 0], [x + 0.32, piso, 0]).set_stroke(col.formulas, 5))
        return grupo

    apoyo_izq, apoyo_der = pie(x_izq, False), pie(x_der, True)

    if figura.repartida:
        techo = Line([x_izq, canto + 0.42, 0], [x_der, canto + 0.42, 0]).set_stroke(col.error, 4)
        cargas = VGroup()
        for i in range(7):
            x = x_izq + vano * (i + 0.5) / 7
            saeta = Arrow(
                [x, canto + 0.40, 0],
                [x, canto + 0.03, 0],
                buff=0,
                stroke_width=4,
                max_tip_length_to_length_ratio=0.35,
            )
            saeta.set_stroke(col.error, 4).set_fill(col.error, 1)
            cargas.add(saeta)
        peso: list[Mobject] = [techo, cargas]
    else:
        saeta = Arrow(
            [0.0, canto + 0.72, 0],
            [0.0, canto + 0.03, 0],
            buff=0,
            stroke_width=6,
            max_tip_length_to_length_ratio=0.18,
        )
        saeta.set_stroke(col.error, 6).set_fill(col.error, 1)
        peso = [saeta]

    empuja = VGroup()
    if "reacciones" in marcas:
        for x in (x_izq, x_der):
            flecha = Arrow(
                [x, piso - 0.74, 0],
                [x, piso - 0.26, 0],
                buff=0,
                stroke_width=5,
                max_tip_length_to_length_ratio=0.35,
            )
            flecha.set_stroke(col.exito, 5).set_fill(col.exito, 1)
            empuja.add(flecha)

    y_cota = -alto * 0.38
    cota = VGroup(
        DashedLine([x_izq, piso - 0.98, 0], [x_izq, y_cota - 0.08, 0]),
        DashedLine([x_der, piso - 0.98, 0], [x_der, y_cota - 0.08, 0]),
        Line([x_izq, y_cota, 0], [x_der, y_cota, 0]),
    ).set_stroke(col.tenue, 3)

    uni_fuerza = figura.unidad_carga.split("/")[0].strip()
    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.carga)} {figura.unidad_carga}",
        np.array([0.0 if figura.repartida else 0.14, canto + (0.58 if figura.repartida else 0.66), 0.0]),
        17,
        None if figura.repartida else RIGHT,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.longitud)} {figura.unidad}",
        np.array([0.0, y_cota, 0.0]),
        16,
    )
    if "reacciones" in marcas:
        for x, nombre in ((x_izq, "R₁"), (x_der, "R₂")):
            _cartela(
                col,
                papel,
                parches,
                rótulos,
                f"{nombre} ≈ {_numero_latex(figura.reaccion)} {uni_fuerza}",
                np.array([x, piso - 1.00, 0.0]),
                15,
            )
    if "momento" in marcas:
        centro = Dot([0.0, y_viga - peralte / 2, 0.0], radius=0.06).set_fill(col.cuadricula, 1)
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"M ≈ {_numero_latex(figura.momento)} {uni_fuerza}·{figura.unidad}",
            np.array([0.0, y_viga - peralte / 2 - 0.32, 0.0]),
            16,
        )
    else:
        centro = VGroup()

    rayas = [lomo, apoyo_izq, apoyo_der, *peso, cota]
    todo = VGroup(*rayas, centro, empuja, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(
        mobs=todo,
        trazo=[lomo, apoyo_izq, apoyo_der, cota],
        aparece=[*peso, *empuja, centro, *rótulos],
    )


def cercha(
    figura: Cercha, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La cercha triangular: la carga del vértice baja inclinada por los dos paños hasta los apoyos."""
    altura = min(alto * 0.48, ancho * 0.46 * figura.altura / max(figura.base, 1e-6))
    base = min(altura * figura.base / max(figura.altura, 1e-6), ancho * 0.46)
    altura = base * figura.altura / max(figura.base, 1e-6)
    y_suelo = -alto * 0.14
    izq = np.array([-base / 2, y_suelo, 0.0])
    der = np.array([base / 2, y_suelo, 0.0])
    cima = np.array([0.0, y_suelo + altura, 0.0])

    paños = VGroup(Line(izq, cima), Line(der, cima), Line(izq, der)).set_stroke(col.formulas, 7)
    nudos = VGroup(
        *[Dot(p, radius=0.07).set_fill(col.acento, 1).set_stroke(col.formulas, 2) for p in (izq, der, cima)]
    )

    def pie(p: np.ndarray) -> VGroup:
        pata = Polygon([p[0], p[1] - 0.05, 0], [p[0] - 0.22, p[1] - 0.36, 0], [p[0] + 0.22, p[1] - 0.36, 0])
        pata.set_stroke(col.formulas, 4).set_fill(col.acento, 0.18)
        piso = Line([p[0] - 0.30, p[1] - 0.36, 0], [p[0] + 0.30, p[1] - 0.36, 0]).set_stroke(col.formulas, 5)
        return VGroup(pata, piso)

    apoyos = VGroup(pie(izq), pie(der))

    peso = Arrow(
        [cima[0], cima[1] + alto * 0.24, 0],
        [cima[0], cima[1] + 0.08, 0],
        buff=0,
        stroke_width=6,
        max_tip_length_to_length_ratio=0.22,
    )
    peso.set_stroke(col.error, 6).set_fill(col.error, 1)

    empuja = VGroup()
    for p in (izq, der):
        flecha = Arrow(
            [p[0], p[1] - 0.90, 0],
            [p[0], p[1] - 0.46, 0],
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.35,
        )
        flecha.set_stroke(col.exito, 5).set_fill(col.exito, 1)
        empuja.add(flecha)

    radio = min(0.50, base * 0.24)
    giro = Arc(
        radius=radio,
        start_angle=0,
        angle=np.radians(figura.angulo),
        arc_center=izq,
    ).set_stroke(col.cuadricula, 4)

    uni = figura.unidad_carga
    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.carga)} {uni}",
        np.array([cima[0] + 0.12, cima[1] + alto * 0.24, 0.0]),
        17,
        LEFT,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.base)} {figura.unidad}",
        np.array([0.0, y_suelo - 0.24, 0.0]),
        16,
    )
    for p, nombre in ((izq, "R₁"), (der, "R₂")):
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"{nombre} = {_numero_latex(figura.reaccion)} {uni}",
            np.array([p[0], p[1] - 1.12, 0.0]),
            15,
        )
    if "angulo" in marcas:
        bis = np.radians(figura.angulo / 2)
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"θ ≈ {_numero_latex(figura.angulo)}°",
            izq + radio * 1.9 * np.array([np.cos(bis), np.sin(bis), 0.0]),
            15,
        )
    if "esfuerzo" in marcas:
        medio = (izq + cima) / 2
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"F ≈ {_numero_latex(figura.esfuerzo)} {uni}",
            np.array([medio[0] - 0.14, medio[1] + 0.14, 0.0]),
            16,
            LEFT,
        )

    rayas = [paños, apoyos, nudos, giro, *empuja]
    todo = VGroup(*rayas, peso, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=[paños, apoyos], aparece=[nudos, giro, peso, *rótulos])


# ------------------------------------------------------------------------------------------
# 13) El taller: el lazo de control, la pareja de engranajes y el círculo de Mohr
# ------------------------------------------------------------------------------------------


def bloques(
    figura: Bloques, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El diagrama de bloques: la realimentación vuelve con signo menos y le come ganancia al lazo."""
    y_lazo = alto * 0.16
    caja_g = Rectangle(width=ancho * 0.22, height=alto * 0.30).move_to([ancho * 0.06, y_lazo, 0.0])
    caja_g.set_stroke(col.formulas, 5).set_fill(papel, 1)
    x_in, x_out = caja_g.get_left()[0], caja_g.get_right()[0]

    sumidero = Circle(radius=alto * 0.10).move_to([x_in - ancho * 0.14, y_lazo, 0.0])
    sumidero.set_stroke(col.formulas, 4).set_fill(papel, 1)
    x_sum = sumidero.get_center()[0]

    señal = [
        Arrow([-ancho * 0.46, y_lazo, 0], [x_sum - alto * 0.10, y_lazo, 0], buff=0, stroke_width=5),
        Arrow([x_sum + alto * 0.10, y_lazo, 0], [x_in, y_lazo, 0], buff=0, stroke_width=5),
        Arrow([x_out, y_lazo, 0], [ancho * 0.46, y_lazo, 0], buff=0, stroke_width=5),
    ]
    for saeta in señal:
        saeta.set_stroke(col.formulas, 5).set_fill(col.formulas, 1)

    # La realimentación sale de la propia señal, baja, cruza por debajo y vuelve al comparador.
    x_toma = ancho * 0.36
    y_retro = -alto * 0.22
    puntos = [
        Line([x_toma, y_lazo, 0], [x_toma, y_retro, 0]),
        Line([x_toma, y_retro, 0], [x_sum, y_retro, 0]),
        Arrow([x_sum, y_retro, 0], [x_sum, y_lazo - alto * 0.10, 0], buff=0, stroke_width=5),
    ]
    puntos[2].set_stroke(col.acento, 5).set_fill(col.acento, 1)
    for tramo in puntos[:2]:
        tramo.set_stroke(col.acento, 5)
    toma = Dot([x_toma, y_lazo, 0.0], radius=0.06).set_fill(col.formulas, 1)

    caja_h = Rectangle(width=ancho * 0.17, height=alto * 0.24).move_to(
        [(x_sum + x_toma) / 2 + ancho * 0.04, y_retro, 0.0]
    )
    caja_h.set_stroke(col.acento, 5).set_fill(papel, 1)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"G = {_numero_latex(figura.adelante)}",
        np.array([caja_g.get_center()[0], y_lazo, 0.0]),
        18,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"H = {_numero_latex(figura.retro)}",
        np.array([caja_h.get_center()[0], y_retro, 0.0]),
        17,
    )
    _cartela(col, papel, parches, rótulos, "entrada", np.array([-ancho * 0.40, y_lazo + 0.34, 0.0]), 14)
    _cartela(col, papel, parches, rótulos, "salida", np.array([ancho * 0.40, y_lazo + 0.34, 0.0]), 14)
    # El signo del comparador: ahí se decide si el lazo se calma o se descontrola.
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        "−" if figura.negativa else "+",
        np.array([x_sum - 0.10, y_lazo - 0.16, 0.0]),
        16,
    )
    if "malla" in marcas:
        # Lo que da la vuelta entera: la ganancia directa por la de vuelta, rotulada sobre la realimentación.
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"GH = {_numero_latex(figura.adelante * figura.retro)}",
            np.array([(x_sum + x_toma) / 2 + ancho * 0.04, y_retro - alto * 0.20, 0.0]),
            17,
        )
    if "lazo_cerrado" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"T = G/(1{'+' if figura.negativa else '-'}GH) ≈ {_numero_latex(figura.lazo_cerrado)}",
            np.array([0.0, -alto * 0.44, 0.0]),
            17,
        )

    rayas = [caja_g, sumidero, *señal, *puntos, caja_h, toma]
    todo = VGroup(*rayas, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=[caja_g, caja_h, sumidero], aparece=[*señal, *puntos, toma, *rótulos])


def _rueda(col: Any, centro: np.ndarray, radio: float, dientes: int, tinta: str, papel: str) -> VGroup:
    """La lámina de un engranaje: su circunferencia con los dientes marcados y su chumquera al centro."""
    paso = 2 * PI / dientes
    punta = radio * 1.09
    bordes = []
    for i in range(dientes):
        base = paso * i
        for fr, r in ((0.0, punta), (0.42, punta), (0.58, radio), (1.0, radio)):
            a = base + paso * fr
            bordes.append(centro + np.array([r * np.cos(a), r * np.sin(a), 0.0]))
    cuerpo = Polygon(*bordes)
    cuerpo.set_stroke(tinta, 4).set_fill(papel, 0)
    chumbrera = Circle(radius=radio * 0.22).move_to(centro)
    chumbrera.set_stroke(tinta, 4).set_fill(papel, 1)
    eje = Dot(centro, radius=0.05).set_fill(tinta, 1)
    return VGroup(cuerpo, chumbrera, eje)


def engranaje(
    figura: Engranaje, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La pareja que se muerde: el chico da más vueltas y el grande sale al revés y más lento."""
    mayor, menor = max(figura.z1, figura.z2), min(figura.z1, figura.z2)
    r_grande = min(alto * 0.28, ancho * 0.20)
    r_chica = r_grande * menor / mayor
    r1 = r_chica if figura.z1 <= figura.z2 else r_grande
    r2 = r_grande if figura.z1 <= figura.z2 else r_chica
    y = alto * 0.10
    c1 = np.array([-r2, y, 0.0])  # la conductora empuja desde la izquierda
    c2 = np.array([r1, y, 0.0])

    rueda_1 = _rueda(col, c1, r1, figura.z1, col.formulas, papel)
    rueda_2 = _rueda(col, c2, r2, figura.z2, col.formulas, papel)

    def giro(centro: np.ndarray, radio: float, horario: bool) -> CurvedArrow:
        r = radio * 1.30
        a0, a1 = (np.radians(58), np.radians(122)) if horario else (np.radians(122), np.radians(58))
        p0 = centro + np.array([r * np.cos(a0), r * np.sin(a0), 0.0])
        p1 = centro + np.array([r * np.cos(a1), r * np.sin(a1), 0.0])
        saeta = CurvedArrow(p0, p1, angle=(62 if horario else -62) * PI / 180)
        saeta.set_stroke(col.acento, 5).set_fill(col.acento, 1)
        return saeta

    da_vuelta_1 = giro(c1, r1, True)
    da_vuelta_2 = giro(c2, r2, False)

    uni = figura.unidad
    parches, rótulos = VGroup(), VGroup()
    # El z₁ crece hacia afuera: si queda centrado bajo su rueda, le pisa los dientes a la grande.
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"z₁ = {figura.z1}",
        np.array([c1[0] - r1, y - r1 - 0.26, 0.0]),
        16,
        RIGHT,
    )
    _cartela(col, papel, parches, rótulos, f"z₂ = {figura.z2}", np.array([c2[0], y - r2 - 0.26, 0.0]), 16)
    # Las vueltas van a los costados, a la altura de su eje: arriba están las flechas del giro.
    if "velocidad" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"{_numero_latex(figura.entrada)} {uni}",
            np.array([c1[0] - r1 - 0.20, y, 0.0]),
            16,
            LEFT,
        )
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"{_numero_latex(figura.salida)} {uni}",
            np.array([c2[0] + r2 + 0.20, y, 0.0]),
            16,
            RIGHT,
        )
    if "relacion" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"i = z₂/z₁ ≈ {_numero_latex(figura.relacion)}",
            np.array([0.0, -alto * 0.44, 0.0]),
            16,
        )

    rayas = [rueda_1, rueda_2, da_vuelta_1, da_vuelta_2]
    todo = VGroup(*rayas, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(mobs=todo, trazo=[rueda_1, rueda_2], aparece=[da_vuelta_1, da_vuelta_2, *rótulos])


def mohr(
    figura: Mohr, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El círculo de Mohr: el diámetro que une los dos puntos conocidos y lo que lee el ingeniero."""
    bajo = min(0.0, figura.centro - figura.radio)
    arriba = max(0.0, figura.centro + figura.radio)
    escala = min(ancho * 0.60 / max(arriba - bajo, 1e-9), alto * 0.70 / max(2 * figura.radio, 1e-9))
    x_cero = -((arriba + bajo) / 2.0) * escala

    def px(sigma: float) -> float:
        return x_cero + sigma * escala

    def py(t: float) -> float:
        return t * escala + alto * 0.02

    centro = np.array([px(figura.centro), py(0.0), 0.0])
    r = figura.radio * escala
    circulo = Circle(radius=max(r, 0.05)).move_to(centro)
    circulo.set_stroke(col.acento, 5).set_fill(col.acento, 0.10)

    eje_sigma = Arrow([px(bajo) - 0.30, py(0.0), 0], [px(arriba) + 0.42, py(0.0), 0], buff=0, stroke_width=4)
    eje_tau = Arrow(
        [px(0.0), py(0.0) - alto * 0.36, 0], [px(0.0), py(0.0) + alto * 0.38, 0], buff=0, stroke_width=4
    )
    for eje in (eje_sigma, eje_tau):
        eje.set_stroke(col.tenue, 4).set_fill(col.tenue, 1)

    # El diámetro de Mohr: (σx, τ) arriba y (σy, −τ) abajo; sus extremos son los principales.
    x_ref = np.array([px(figura.sigma_x), py(figura.cortante), 0.0])
    y_ref = np.array([px(figura.sigma_y), py(-figura.cortante), 0.0])
    diametro = Line(x_ref, y_ref).set_stroke(col.cuadricula, 4)
    puntos_ref = VGroup(
        *[Dot(p, radius=0.07).set_fill(col.cuadricula, 1).set_stroke(col.formulas, 2) for p in (x_ref, y_ref)]
    )
    p1 = np.array([px(figura.principal_1), py(0.0), 0.0])
    p2 = np.array([px(figura.principal_2), py(0.0), 0.0])
    radio_vertical = Line(centro, [centro[0], py(figura.radio), 0.0]).set_stroke(col.error, 4)

    uni = figura.unidad
    parches, rótulos = VGroup(), VGroup()
    _cartela(col, papel, parches, rótulos, "σ", np.array([px(arriba) + 0.42, py(0.0) + 0.26, 0.0]), 16)
    _cartela(col, papel, parches, rótulos, "τ", np.array([px(0.0) + 0.26, py(0.0) + alto * 0.36, 0.0]), 16)
    # El centro se escribe a la izquierda del radio vertical: a la derecha está el punto X.
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"C = {_numero_latex(figura.centro)} {uni}",
        np.array([centro[0] - 0.14, py(0.0) + 0.30, 0.0]),
        15,
        RIGHT,
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"X({_numero_latex(figura.sigma_x)}, {_numero_latex(figura.cortante)})",
        np.array([x_ref[0] + 0.12, x_ref[1] + 0.22, 0.0]),
        14,
        LEFT,
    )
    # Los dos principales bajan del eje y se van cada uno a su orilla: en el medio quedaría C.
    if "principales" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"σ₁ ≈ {_numero_latex(figura.principal_1)} {uni}",
            np.array([p1[0] + 0.16, py(0.0) - 0.38, 0.0]),
            15,
            LEFT,
        )
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"σ₂ ≈ {_numero_latex(figura.principal_2)} {uni}",
            np.array([p2[0] - 0.16, py(0.0) - 0.38, 0.0]),
            15,
            RIGHT,
        )
    if "cortante" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"τ máx ≈ {_numero_latex(figura.max_cortante)} {uni}",
            np.array([centro[0] - 0.12, py(figura.radio) + 0.22, 0.0]),
            15,
            RIGHT,
        )

    rayas = [eje_sigma, eje_tau, circulo, diametro, puntos_ref, radio_vertical]
    todo = VGroup(*rayas, parches, rótulos)
    _encajar(todo, ancho, alto)
    return Dibujo(
        mobs=todo,
        trazo=[eje_sigma, eje_tau, circulo],
        aparece=[diametro, puntos_ref, radio_vertical, *rótulos],
    )


# ------------------------------------------------------------------------------------------
# 16 · Física: oscilador amortiguado y péndulo doble (los que salen de una integral)
# ------------------------------------------------------------------------------------------


def _energia_redonda(julios: float) -> str:
    """29 J, no 28,9516: en pantalla se escribe lo que un profesor diría en voz alta."""
    return _numero_latex(round(julios, 0 if abs(julios) >= 10 else 1))


def oscilador(
    figura: Oscilador, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La curva x(t) que sale de la integral, con el sobre que la apaga y lo que el guion anota."""
    t_fin = figura.hasta
    x_tope = max(figura.amplitud, max(abs(v) for v in figura.x)) or 1.0
    e_x = ancho * 0.82  # el ancho que ocupa el eje del tiempo
    e_y = alto * 0.58  # y el alto que ocupa la amplitud, de -A a +A

    def px(t: float) -> float:
        return -e_x / 2.0 + t * (e_x / t_fin)

    def py(x: float) -> float:
        return x * (e_y / (2.0 * x_tope))

    curva = VMobject().set_points_smoothly(
        [np.array([px(t), py(x), 0.0]) for t, x in zip(figura.t, figura.x)]
    )
    curva.set_stroke(col.tenue, 3)  # la guía completa: se ve adónde va antes de llegar

    eje_t = Arrow([px(0.0), 0.0, 0], [px(t_fin) + 0.32, 0.0, 0], buff=0, stroke_width=4)
    eje_x = Arrow([px(0.0), -e_y / 2 - 0.12, 0], [px(0.0), e_y / 2 + 0.22, 0], buff=0, stroke_width=4)
    for eje in (eje_t, eje_x):
        eje.set_stroke(col.tenue, 4).set_fill(col.tenue, 1)

    sobres: list = []
    if figura.decaimiento:
        alfa = 1.0 / figura.decaimiento
        for signo in (1.0, -1.0):
            borde = VMobject().set_points_smoothly(
                [np.array([px(t), py(signo * figura.amplitud * np.exp(-alfa * t)), 0.0]) for t in figura.t]
            )
            sobre = DashedVMobject(borde, num_dashes=48)
            sobre.set_stroke(col.tenue, 3)
            sobres.append(sobre)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"x ({figura.unidad or 'm'})",
        np.array([px(0.0) - 0.14, e_y / 2 + 0.34, 0.0]),
        15,
        LEFT,
    )
    _cartela(col, papel, parches, rótulos, "t (s)", np.array([px(t_fin) + 0.32, -0.26, 0.0]), 15, RIGHT)

    # Los datos van en una sola banda bajo la curva, de izquierda a derecha, para que no se pisen.
    banda = -e_y / 2 - 0.40
    if "regimen" in marcas:
        regimen = (
            figura.regimen if figura.zeta == 0 else f"ζ = {_numero_latex(figura.zeta)} ({figura.regimen})"
        )
        _cartela(col, papel, parches, rótulos, regimen, np.array([px(0.0), banda, 0.0]), 15, RIGHT)
    if "decaimiento" in marcas and figura.decaimiento is not None:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"τ ≈ {_numero_latex(figura.decaimiento)} s",
            np.array([px(t_fin) * 0.32, banda, 0.0]),
            15,
        )
    if "periodo" in marcas and figura.periodo is not None:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"T ≈ {_numero_latex(figura.periodo)} s",
            np.array([px(t_fin), banda, 0.0]),
            15,
            LEFT,
        )

    punto = Dot(radius=0.09).set_fill(col.acento, 1).set_stroke(width=0)
    todo = VGroup(eje_t, eje_x, curva, punto, *sobres, parches, rótulos)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        t = figura.hasta * p
        punto.move_to(fijo(np.array([px(t), py(figura.sobre(t)), 0.0])))

    vivo(0.0)
    estela = _estela(punto, col.acento, 5)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=[eje_t, eje_x, curva],
        aparece=[punto, *sobres, *rótulos],
        vivo=vivo,
        duracion=figura.hasta,
        estela=estela,
        desplazamiento=desplazamiento,
    )


def pendulo_doble(
    figura: PenduloDoble, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """Los dos brazos recorriendo el camino integrado, con la traza de la masa de abajo creciendo.

    La escala sale de la caja que ocupan **todas** las poses y la traza completa: así ningún
    instante del caos se sale de la franja, aunque el dibujo se vea en movimiento.
    """
    xs, ys = [], []
    for i in range(len(figura.t)):
        for x, y in figura.brazos(i):
            xs.append(x)
            ys.append(y)
    xs.extend(p[0] for p in figura.traza)
    ys.extend(p[1] for p in figura.traza)
    caja_x = max(max(xs) - min(xs), 0.2)
    caja_y = max(max(ys) - min(ys), 0.2)
    escala = min(alto * 0.86 / caja_y, ancho * 0.46 / caja_x)
    centro_x = (max(xs) + min(xs)) / 2.0
    centro_y = (max(ys) + min(ys)) / 2.0

    def punto(p: tuple[float, float]) -> np.ndarray:
        return np.array([(p[0] - centro_x) * escala, (p[1] - centro_y) * escala, 0.0])

    paso = max(1, len(figura.traza) // 240)
    camino = VMobject().set_points_as_corners([punto(p) for p in figura.traza[::paso]])
    camino.set_stroke(col.tenue, 3)

    anclaje, masa_1, masa_2 = figura.brazos(0)
    brazo_1 = Line(punto(anclaje), punto(masa_1)).set_stroke(col.formulas, 4)
    brazo_2 = Line(punto(masa_1), punto(masa_2)).set_stroke(col.formulas, 4)
    pivote = Dot(punto(anclaje), radius=0.06).set_fill(col.formulas, 1).set_stroke(width=0)
    bola_1 = Dot(punto(masa_1), radius=0.08).set_fill(col.formulas, 1).set_stroke(width=0)
    bola_2 = Dot(punto(masa_2), radius=0.10).set_fill(col.acento, 1).set_stroke(width=0)

    piezas = VGroup(camino, brazo_1, brazo_2, pivote, bola_1, bola_2)
    # La figura se pega al borde izquierdo y los datos arrancan a su derecha: así ningún rótulo cae
    # encima de la traza, que es lo único que el chico tiene que mirar.
    ancho_figura = caja_x * escala
    corrimiento = np.array([-ancho / 2.0 + ancho_figura / 2.0 + 0.10, 0.0, 0.0])
    piezas.shift(corrimiento)
    x_datos = -ancho / 2.0 + ancho_figura + 0.50

    def punto_final(p: tuple[float, float]) -> np.ndarray:
        return punto(p) + corrimiento

    parches, rótulos = VGroup(), VGroup()
    if "energia" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"E ≈ {_energia_redonda(figura.energia_inicial)} J",
            np.array([x_datos, alto * 0.18, 0.0]),
            17,
            RIGHT,
        )
    if "angulos" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"desde {_numero_latex(figura.angulo_1[0])}° y {_numero_latex(figura.angulo_2[0])}°",
            np.array([x_datos, -alto * 0.16, 0.0]),
            16,
            RIGHT,
        )

    todo = VGroup(piezas, parches, rótulos)
    fijo, desplazamiento = _encaje(todo, ancho, alto)
    ultimo = len(figura.t) - 1

    def vivo(p: float) -> None:
        i = min(int(round(p * ultimo)), ultimo)
        a, m1, m2 = figura.brazos(i)
        brazo_1.put_start_and_end_on(fijo(punto_final(a)), fijo(punto_final(m1)))
        brazo_2.put_start_and_end_on(fijo(punto_final(m1)), fijo(punto_final(m2)))
        bola_1.move_to(fijo(punto_final(m1)))
        bola_2.move_to(fijo(punto_final(m2)))

    vivo(0.0)
    estela = _estela(bola_2, col.acento, 5)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=[camino],
        aparece=[brazo_1, brazo_2, pivote, bola_1, bola_2, *rótulos],
        vivo=vivo,
        duracion=figura.t[-1] - figura.t[0],
        estela=estela,
        desplazamiento=desplazamiento,
    )


# ------------------------------------------------------------------------------------------
# Elección del dibujo según el guion
# ------------------------------------------------------------------------------------------


# ------------------------------------------------------------------------------------------
# Calor en una placa y flujo entre placas
# ------------------------------------------------------------------------------------------

# Frío a caliente: azul, celeste, crema, naranjo y rojo. Es un código que se lee igual en cualquier
# tema (el azul siempre es frío), por eso no sale de la paleta del tema.
MAPA_TERMICO = ("#2F5BEA", "#5FB6F2", "#F4EBC3", "#F28C38", "#D7263D")


def color_termico(fraccion: float) -> ManimColor:
    """El color de una temperatura, con ``fraccion`` = 0 en la más fría y 1 en la más caliente."""
    f = min(max(float(fraccion), 0.0), 1.0) * (len(MAPA_TERMICO) - 1)
    i = min(int(f), len(MAPA_TERMICO) - 2)
    return ManimColor(MAPA_TERMICO[i]).interpolate(ManimColor(MAPA_TERMICO[i + 1]), f - i)


def _isotermas(campo: np.ndarray, niveles: list[float], punto: Callable[[float, float], np.ndarray]):
    """Los tramos de cada curva de nivel (marching squares): pares de puntos ya en pantalla."""
    ny, nx = campo.shape
    tramos = []
    for nivel in niveles:
        for j in range(ny - 1):
            for i in range(nx - 1):
                esquinas = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                valores = [campo[b, a] for a, b in esquinas]
                cortes = []
                for k in range(4):
                    (a0, b0), (a1, b1) = esquinas[k], esquinas[(k + 1) % 4]
                    v0, v1 = valores[k], valores[(k + 1) % 4]
                    if (v0 - nivel) * (v1 - nivel) < 0:
                        f = (nivel - v0) / (v1 - v0)
                        cortes.append(punto(a0 + f * (a1 - a0), b0 + f * (b1 - b0)))
                for k in range(0, len(cortes) - 1, 2):
                    tramos.append((cortes[k], cortes[k + 1]))
    return tramos


def _escala(fijo: Callable[[np.ndarray], np.ndarray]) -> float:
    """Cuánto encogió ``_encaje`` el dibujo: los largos que se recalculan se miden en la escala final."""
    return float(np.linalg.norm(fijo(np.array([1.0, 0.0, 0.0])) - fijo(np.zeros(3))))


def gradiente_termico(
    placa: Any, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La placa coloreada por temperatura: el calor entra por los bordes y se asienta.

    Cada celda es un punto de la malla de diferencias finitas y su color sale de la temperatura que
    calculó ``simulacion.conducir_placa``. La última pose es el régimen permanente.
    """
    campo = placa.permanente
    ny, nx = campo.shape
    lado = min(0.62 * ancho / nx, 0.70 * alto / ny)
    ancho_p, alto_p = lado * nx, lado * ny
    izquierda, abajo = -ancho_p / 2 - 0.35, -alto_p / 2

    def punto(i: float, j: float) -> np.ndarray:
        return np.array([izquierda + (i + 0.5) * lado, abajo + (j + 0.5) * lado, 0.0])

    rango = max(placa.maxima - placa.minima, 1e-9)
    celdas = VGroup(
        *[
            Rectangle(width=lado, height=lado).move_to(punto(i, j)).set_stroke(width=0)
            for j in range(ny)
            for i in range(nx)
        ]
    )
    borde = Rectangle(width=ancho_p, height=alto_p).move_to(punto((nx - 1) / 2, (ny - 1) / 2))
    borde.set_stroke(col.formulas, 4)
    centro_x, centro_y = float(borde.get_center()[0]), float(borde.get_center()[1])

    def grados(valor: float) -> str:
        return f"{_numero_latex(round(valor))} °C"

    parches, rótulos = VGroup(), VGroup()

    def rotulo(texto: str, donde: list[float], tam: float = 20) -> Mobject:
        r = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(np.array(donde, dtype=float))
        fondo, r = _parche(r, papel, 0.12)
        parches.add(fondo)
        rótulos.add(r)
        return r

    rotulo(grados(placa.izquierda), [izquierda - 0.55, centro_y, 0])
    rotulo(grados(placa.arriba), [centro_x, abajo + alto_p + 0.24, 0])
    rotulo(grados(placa.abajo), [centro_x, abajo - 0.24, 0])
    derecha = rotulo(grados(placa.derecha), [izquierda + ancho_p + 0.55, centro_y, 0])

    # La escala de colores con sus dos extremos: sin ella el color no dice cuántos grados son.
    x_barra = float(derecha.get_right()[0]) + 0.45
    tramos_barra = 20
    alto_barra = alto_p * 0.9
    barra = VGroup(
        *[
            Rectangle(width=0.22, height=alto_barra / tramos_barra)
            .set_fill(color_termico((k + 0.5) / tramos_barra), 1)
            .set_stroke(width=0)
            .move_to([x_barra, centro_y - alto_barra / 2 + (k + 0.5) * alto_barra / tramos_barra, 0])
            for k in range(tramos_barra)
        ]
    )
    marco_barra = Rectangle(width=0.22, height=alto_barra).move_to([x_barra, centro_y, 0])
    marco_barra.set_stroke(col.tenue, 2)
    rotulo(grados(placa.maxima), [x_barra, centro_y + alto_barra / 2 + 0.2, 0], 17)
    rotulo(grados(placa.minima), [x_barra, centro_y - alto_barra / 2 - 0.2, 0], 17)

    isotermas = VMobject().set_stroke(col.formulas, 2.5, 0.75)
    niveles = [placa.minima + rango * f for f in (0.2, 0.4, 0.6, 0.8)]
    con_isotermas = "isotermas" in marcas
    con_centro = "centro" in marcas
    centro = Dot(punto((nx - 1) / 2, (ny - 1) / 2), radius=0.06).set_fill(col.formulas, 1)
    lectura = VGroup()
    escrito = [""]

    todo = VGroup(celdas, isotermas, borde, barra, marco_barra, parches, rótulos)
    if con_centro:
        todo.add(centro, lectura)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def leer(valor: float) -> None:
        texto = f"T centro ≈ {grados(valor)}"
        if texto == escrito[0]:
            return
        escrito[0] = texto
        sitio = fijo(np.array([centro_x, abajo + alto_p + 0.62, 0.0]))
        nuevo = c.texto(texto, 22, SEMIBOLD, col.texto)
        nuevo.scale(_escala(fijo)).move_to(sitio)
        for viejo in lectura.submobjects:  # como en el gráfico vivo: nada de letras fantasma
            viejo.set_opacity(0.0)
        lectura.submobjects = list(_parche(nuevo, papel, 0.14).submobjects)

    def vivo(t: float) -> None:
        valores = placa.en(t)
        for (j, i), celda in zip(np.ndindex(ny, nx), celdas, strict=True):
            tono = color_termico((valores[j, i] - placa.minima) / rango)
            celda.set_fill(tono, 1).set_stroke(tono, 0.6, 1)  # borde del mismo tono: sin rendijas
        if con_isotermas:
            isotermas.clear_points()
            for p0, p1 in _isotermas(valores, niveles, lambda i, j: fijo(punto(i, j))):
                isotermas.start_new_path(p0)
                isotermas.add_line_to(p1)
        if con_centro:
            leer(placa.centro(valores))

    vivo(1.0)
    aparece: list[Mobject] = [celdas, barra, marco_barra, rótulos]
    if con_isotermas:
        aparece.append(isotermas)
    if con_centro:
        aparece += [centro, lectura]
    return Dibujo(
        mobs=todo,
        trazo=[borde],
        aparece=aparece,
        vivo=vivo,
        duracion=SEGUNDOS_RECORRIDO,
        fisico=False,
        desplazamiento=desplazamiento,
    )


FLECHAS_FLUJO = 11


def perfil_flujo(
    figura: Any, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El fluido entre dos placas: una flecha por capa, de largo y color según su velocidad.

    Arranca en reposo y llega al perfil desarrollado (recto en Couette, parábola en Poiseuille)
    siguiendo la solución exacta de ``simulacion``. Con la marca ``esfuerzo`` se agrega la columna
    del esfuerzo cortante τ = μ·du/dy, que es máximo en las paredes.
    """
    from .simulacion import TIEMPO_FLUJO, perfil_couette, perfil_poiseuille

    perfil = perfil_couette if figura.flujo == "couette" else perfil_poiseuille
    con_esfuerzo = "esfuerzo" in marcas
    alto_c = 0.62 * alto
    largo_max = (0.34 if con_esfuerzo else 0.5) * ancho
    x0 = -0.42 * ancho + 0.4
    y0, y1 = -alto_c / 2, alto_c / 2

    def y_de(s: float) -> float:
        return y0 + s * (y1 - y0)

    largo_placa = largo_max + 0.9 + (1.6 if con_esfuerzo else 0.0)
    placas = VGroup()
    for y, afuera in ((y0, -1), (y1, 1)):
        placas.add(Line([x0 - 0.3, y, 0], [x0 - 0.3 + largo_placa, y, 0]).set_stroke(col.formulas, 6))
        for k in range(int(largo_placa / 0.28)):
            x = x0 - 0.16 + k * 0.28
            placas.add(Line([x, y, 0], [x - 0.14, y + afuera * 0.16, 0]).set_stroke(col.tenue, 2.5))
    base = DashedLine([x0, y0, 0], [x0, y1, 0], dash_length=0.08).set_stroke(col.tenue, 2.5)

    capas = np.array([(k + 0.5) / FLECHAS_FLUJO for k in range(FLECHAS_FLUJO)])
    flechas = [
        Arrow(
            [x0, y_de(s), 0],
            [x0 + 0.1, y_de(s), 0],
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.25,
        )
        for s in capas
    ]
    envolvente = VMobject().set_stroke(col.acento, 4)

    parches, rótulos = VGroup(), VGroup()

    def rotulo(texto: str, donde: list[float], tam: float = 20) -> Mobject:
        r = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(np.array(donde, dtype=float))
        fondo, r = _parche(r, papel, 0.12)
        parches.add(fondo)
        rótulos.add(r)
        return r

    rotulo(f"h = {figura.texto_separacion}", [x0 - 0.8, 0, 0], 19)
    if figura.flujo == "couette":
        mueve = Arrow([x0 + 0.2, y1 + 0.34, 0], [x0 + 1.3, y1 + 0.34, 0], buff=0, stroke_width=6)
        mueve.set_color(col.error)
        placas.add(mueve)
        rotulo(f"U = {figura.texto_velocidad}", [x0 + 2.25, y1 + 0.34, 0])
        rotulo("placa quieta", [x0 + 1.0, y0 - 0.34, 0], 17)
    else:
        rotulo(f"u máx = {figura.texto_velocidad}", [x0 + largo_max * 0.55, y1 + 0.34, 0])
        rotulo("la presión empuja →", [x0 + 1.4, y0 - 0.34, 0], 17)

    x_tau = x0 + largo_max + 1.0
    tau_flechas: list[Arrow] = []
    tau_base = None
    largo_tau = 0.65
    if con_esfuerzo:
        tau_base = DashedLine([x_tau, y0, 0], [x_tau, y1, 0], dash_length=0.08).set_stroke(col.tenue, 2.5)
        tau_flechas = [
            Arrow(
                [x_tau, y_de(s), 0],
                [x_tau + 0.1, y_de(s), 0],
                buff=0,
                stroke_width=4,
                max_tip_length_to_length_ratio=0.3,
            )
            for s in capas
        ]
        rotulo(f"τ pared = {_numero_latex(figura.esfuerzo_pared)} Pa", [x_tau + 0.3, y1 + 0.34, 0], 19)

    todo = VGroup(placas, base, *flechas, envolvente, parches, rótulos)
    if tau_base is not None:
        todo.add(tau_base, *tau_flechas)
    fijo, desplazamiento = _encaje(todo, ancho, alto)
    muestras = np.linspace(0.0, 1.0, 41)
    referencia = 1.0 if figura.flujo == "couette" else 4.0  # la pendiente del perfil en la pared

    def vivo(t: float) -> None:
        tau = TIEMPO_FLUJO * t**1.5 if t < 1.0 else 50.0  # al final, el perfil desarrollado
        escala = _escala(fijo)
        u = perfil(capas, tau)
        for flecha, s, v in zip(flechas, capas, u, strict=True):
            origen = fijo(np.array([x0, y_de(float(s)), 0.0]))
            v = max(float(v), 0.0)
            _apuntar(flecha, origen, RIGHT, largo_max * v * escala, _color_de_magnitud(col, v))
        envolvente.set_points_as_corners(
            [
                fijo(np.array([x0 + largo_max * max(float(v), 0.0), y_de(float(s)), 0.0]))
                for s, v in zip(muestras, perfil(muestras, tau), strict=True)
            ]
        )
        if con_esfuerzo:
            h = 1e-3
            pendiente = (perfil(capas + h, tau) - perfil(capas - h, tau)) / (2 * h)
            for flecha, s, g in zip(tau_flechas, capas, pendiente, strict=True):
                origen = fijo(np.array([x_tau, y_de(float(s)), 0.0]))
                fraccion = min(abs(float(g)) / referencia, 1.0)
                _apuntar(
                    flecha,
                    origen,
                    RIGHT if g >= 0 else LEFT,
                    largo_tau * fraccion * escala,
                    _color_de_magnitud(col, fraccion),
                )

    vivo(1.0)
    aparece: list[Mobject] = [*flechas, envolvente, rótulos, *tau_flechas]
    trazo: list[Mobject] = [placas, base, *([tau_base] if tau_base is not None else [])]
    return Dibujo(
        mobs=todo,
        trazo=trazo,
        aparece=aparece,
        vivo=vivo,
        duracion=SEGUNDOS_RECORRIDO,
        fisico=False,
        desplazamiento=desplazamiento,
    )


def dibujar_visual(visual: Any, col: Any, ancho: float, alto: float, papel: str | None = None) -> Dibujo:
    """El ``visual:`` de un paso convertido en dibujo, centrado en el origen.

    ``papel`` es el color sobre el que se dibuja: sirve para 'cortar' un cable con una caja del
    mismo color (resistencias, batería y las medidas del polígono) sin que se note el truco.
    """
    marca = _relleno.set(RELLENO.get(getattr(visual, "tamano", "auto") or "auto"))
    try:
        dibujo = _dibujar_visual(visual, col, ancho, alto, papel)
    finally:
        _relleno.reset(marca)
    tecnico = visual.tipo == "tolva_3d" or (visual.tipo == "solido_3d" and visual.figura == "cubo")
    afinar_trazo(dibujo.mobs, minimo=1.5 if tecnico else GROSOR_MINIMO)
    return dibujo


def _dibujar_visual(visual: Any, col: Any, ancho: float, alto: float, papel: str | None = None) -> Dibujo:
    papel = papel or col.fondo
    if visual.tipo == "grafico_funcion":
        return grafico_funcion(
            visual.funcion_analizada(),
            col,
            ancho,
            alto,
            visual.eje_x,
            visual.eje_y,
            papel,
            visual.movimiento,
            visual.desde,
            visual.hasta,
            visual.anotar,
        )
    if visual.tipo == "diagrama_fuerzas":
        return diagrama_fuerzas(
            visual.vectores, col, ancho, alto, visual.cuerpo, visual.angulo, visual.descomponer, papel
        )
    if visual.tipo == "poligono_regular":
        return poligono_regular(visual.poligono(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "proyectil":
        return proyectil(visual.proyectil(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "circulo_trig":
        return circulo_trig(visual.angulo_trig(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "solido":
        return solido(visual.solido(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "solido_3d":
        from .dibujos_3d import dibujar_solido_3d  # adentro: manim 3D no debe pesar en los dibujos 2D

        return dibujar_solido_3d(visual, col, ancho, alto, papel)
    if visual.tipo == "vector_3d":
        from .dibujos_3d import dibujar_vector_3d  # misma cámara 3D, con sus líneas y su flecha

        return dibujar_vector_3d(visual, col, ancho, alto, papel)
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
    if visual.tipo == "escala":
        return escala(visual.escala(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "polea":
        return polea(visual.polea(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "tanque":
        return tanque(visual.tanque(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "viga":
        return viga(visual.viga(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "cercha":
        return cercha(visual.cercha(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "bloques":
        return bloques(visual.bloques(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "engranaje":
        return engranaje(visual.engranaje(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "oscilador":
        return oscilador(visual.oscilador(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "pendulo_doble":
        return pendulo_doble(visual.pendulo_doble(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "mohr":
        return mohr(visual.mohr(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo in ("tolva_3d", "tuberia_3d", "eje_3d"):
        from . import dibujos_3d  # adentro, como el sólido: la malla 3D no pesa en los dibujos 2D

        construir = {
            "tolva_3d": dibujos_3d.dibujar_tolva_3d,
            "tuberia_3d": dibujos_3d.dibujar_tuberia_3d,
            "eje_3d": dibujos_3d.dibujar_eje_3d,
        }[visual.tipo]
        return construir(visual, col, ancho, alto, papel)
    if visual.tipo == "gradiente_termico":
        return gradiente_termico(visual.placa(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "perfil_flujo":
        return perfil_flujo(visual.flujo_analizado(), visual.anotar, col, ancho, alto, papel)
    if visual.tipo == "circuito":
        fuente, resistencias = analizar_circuito(visual.fuente, visual.resistencias)
        return circuito(fuente, resistencias, col, ancho, alto, visual.arreglo, papel)
    raise ErrorMotor(f"el motor todavía no sabe dibujar «{visual.tipo}»")
