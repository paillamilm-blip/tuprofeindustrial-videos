"""Los sistemas que no tienen fórmula cerrada: se integran con SciPy.

Ni el oscilador amortiguado ni el péndulo doble se resuelven con una cuenta de pizarra. Aquí la
respuesta sale de integrar la ecuación paso a paso con ``scipy.integrate.solve_ivp``, que es el
único motivo por el que este proyecto necesita SciPy.

El módulo no dibuja ni habla: entrega números (tiempos, posiciones, ángulos, energía) y
``visuales.py`` los convierte en dibujo y en rótulos. Los errores dicen el nombre del campo del
guion, para que se pueda corregir sin saber de integrales.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

GRAVEDAD = 9.8  # la misma que usa el péndulo simple del motor
TOLERANCIA = 1e-12  # DOP853 apretado: la energía tiene que quedar plana en el gráfico


def _mayor_que_cero(valor: float, campo: str) -> float:
    v = float(valor)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{campo} tiene que ser un número mayor que cero (dice {valor})")
    return v


def _no_negativo(valor: float, campo: str) -> float:
    v = float(valor)
    if not math.isfinite(v) or v < 0:
        raise ValueError(f"{campo} tiene que ser cero o mayor (dice {valor})")
    return v


@dataclass
class Oscilador:
    """La posición de una masa con amortiguador, muestreada de corrido, y lo que vale la pena anotar."""

    t: list[float]
    x: list[float]
    masa: float
    constante: float
    amortiguamiento: float
    amplitud: float
    hasta: float
    zeta: float  # factor de amortiguamiento: cuánto de la resistencia crítica
    regimen: str
    periodo: float | None  # None si no oscila (ζ ≥ 1)
    decaimiento: float | None  # τ: en ese tiempo la amplitud se reduce a una «e»
    gravedad: float = GRAVEDAD
    unidad: str = "m"  # la unidad en la que están ``x`` y ``amplitud``: la del guion

    def sobre(self, tiempo: float) -> float:
        """La posición interpolada en un instante, para el rótulo que toque."""
        return float(np.interp(tiempo, self.t, self.x))


@dataclass
class PenduloDoble:
    """Las dos posiciones angulares y la traza de la masa de abajo, en metros desde el anclaje."""

    t: list[float]
    angulo_1: list[float]  # grados desde la vertical
    angulo_2: list[float]
    traza: list[tuple[float, float]]
    energia: list[float]
    energia_inicial: float
    masa_1: float
    masa_2: float
    longitud_1: float
    longitud_2: float
    gravedad: float = GRAVEDAD
    unidad: str = "m"  # la traza y los brazos vienen siempre en metros

    def brazos(self, i: int) -> list[tuple[float, float]]:
        """Anclaje, primera masa y segunda masa en el punto ``i`` de la muestra."""
        a1 = math.radians(self.angulo_1[i])
        a2 = math.radians(self.angulo_2[i])
        x1 = self.longitud_1 * math.sin(a1)
        y1 = -self.longitud_1 * math.cos(a1)
        return [(0.0, 0.0), (x1, y1), (x1 + self.longitud_2 * math.sin(a2), y1 - self.longitud_2 * math.cos(a2))]

    def radio_maximo(self) -> float:
        return self.longitud_1 + self.longitud_2


def _derivadas_oscilador(masa: float, constante: float, amortiguamiento: float):
    def f(_t: float, y: np.ndarray) -> list[float]:
        return [y[1], -(amortiguamiento * y[1] + constante * y[0]) / masa]

    return f


def integrar_oscilador(
    masa: float,
    constante: float,
    amortiguamiento: float,
    amplitud: float,
    hasta: float,
    gravedad: float = GRAVEDAD,
    puntos: int | None = None,
) -> Oscilador:
    """m x'' + c x' + k x = 0, soltada desde el reposo en ``amplitud`` durante ``hasta`` segundos.

    ``gravedad`` no interviene (el resorte ya está medido alrededor de su equilibrio), pero se guarda
    para que la firma de los dos analizadores se parezca.
    """
    m = _mayor_que_cero(masa, "masa")
    k = _mayor_que_cero(constante, "constante")
    c = _no_negativo(amortiguamiento, "amortiguamiento")
    a = _mayor_que_cero(amplitud, "amplitud")
    fin = _mayor_que_cero(hasta, "hasta")

    w0 = math.sqrt(k / m)
    zeta = c / (2 * math.sqrt(m * k))
    subamortiguado = zeta < 1.0
    wd = w0 * math.sqrt(1.0 - zeta**2) if subamortiguado else 0.0
    periodo = 2 * math.pi / wd if subamortiguado and wd > 0 else None
    decaimiento = 2 * m / c if c > 0 else None
    if c == 0:
        regimen = "sin amortiguamiento"
    elif zeta < 1.0:
        regimen = "subamortiguado"
    elif math.isclose(zeta, 1.0, rel_tol=1e-12, abs_tol=1e-12):
        regimen = "criticamente amortiguado"
    else:
        regimen = "sobreamortiguado"

    # Con una sola muestra por período la curva sale serrada: se le dan cuarenta.
    if puntos is None:
        puntos = 401 if periodo is None else int(min(2001, max(401, round(40 * fin / periodo) + 1)))
    t = np.linspace(0.0, fin, puntos)
    sol = solve_ivp(
        _derivadas_oscilador(m, k, c), (0.0, fin), [a, 0.0], t_eval=t, method="DOP853",
        rtol=TOLERANCIA, atol=TOLERANCIA / 100,
    )
    if not sol.success:
        raise ValueError(f"la simulación del oscilador no llegó al final ({sol.message})")

    return Oscilador(
        t=[float(v) for v in sol.t],
        x=[float(v) for v in sol.y[0]],
        masa=m,
        constante=k,
        amortiguamiento=c,
        amplitud=a,
        hasta=fin,
        zeta=zeta,
        regimen=regimen,
        periodo=periodo,
        decaimiento=decaimiento,
        gravedad=gravedad,
    )


def _derivadas_pendulo_doble(m1: float, m2: float, l1: float, l2: float, g: float):
    """Las dos ecuaciones acopladas completas, sin el «sen θ ≈ θ» que usaría un pizarrajo."""

    def f(_t: float, y: np.ndarray) -> list[float]:
        a1, v1, a2, v2 = (float(v) for v in y)
        d = a1 - a2
        seno, cos = math.sin(d), math.cos(d)
        denominador = 2 * m1 + m2 - m2 * math.cos(2 * d)
        p1 = (
            -g * (2 * m1 + m2) * math.sin(a1)
            - m2 * g * math.sin(a1 - 2 * a2)
            - 2 * seno * m2 * (v2 * v2 * l2 + v1 * v1 * l1 * cos)
        ) / (l1 * denominador)
        p2 = (
            2
            * seno
            * (v1 * v1 * l1 * (m1 + m2) + g * (m1 + m2) * math.cos(a1) + v2 * v2 * l2 * m2 * cos)
        ) / (l2 * denominador)
        return [v1, p1, v2, p2]

    return f


def _energia_pendulo_doble(
    m1: float, m2: float, l1: float, l2: float, g: float, a1: float, v1: float, a2: float, v2: float
) -> float:
    cinetica = 0.5 * m1 * l1**2 * v1**2 + 0.5 * m2 * (
        l1**2 * v1**2 + l2**2 * v2**2 + 2 * l1 * l2 * v1 * v2 * math.cos(a1 - a2)
    )
    potencial = -(m1 + m2) * g * l1 * math.cos(a1) - m2 * g * l2 * math.cos(a2)
    return cinetica + potencial


def integrar_pendulo_doble(
    masa_1: float,
    masa_2: float,
    longitud_1: float,
    longitud_2: float,
    angulo_1: float,
    angulo_2: float,
    hasta: float,
    gravedad: float = GRAVEDAD,
    puntos: int = 601,
) -> PenduloDoble:
    """Dos brazos enganchados uno en el extremo del otro, soltados desde el reposo.

    Los ángulos se escriben en grados desde la vertical (positivo hacia la derecha) y la traza sale
    en metros, con el anclaje en el origen y ``y`` creciendo hacia arriba.
    """
    m1 = _mayor_que_cero(masa_1, "masa_1")
    m2 = _mayor_que_cero(masa_2, "masa_2")
    l1 = _mayor_que_cero(longitud_1, "longitud_1")
    l2 = _mayor_que_cero(longitud_2, "longitud_2")
    fin = _mayor_que_cero(hasta, "hasta")
    for campo, valor in (("angulo_1", angulo_1), ("angulo_2", angulo_2)):
        if not math.isfinite(float(valor)) or not -180 < float(valor) < 180:
            raise ValueError(
                f"{campo} es un ángulo desde la vertical y va entre -180 y 180 grados, sin llegar "
                f"a los extremos (dice {valor})"
            )

    r1, r2 = math.radians(float(angulo_1)), math.radians(float(angulo_2))
    t = np.linspace(0.0, fin, puntos)
    sol = solve_ivp(
        _derivadas_pendulo_doble(m1, m2, l1, l2, gravedad), (0.0, fin), [r1, 0.0, r2, 0.0],
        t_eval=t, method="DOP853", rtol=TOLERANCIA, atol=TOLERANCIA / 100,
    )
    if not sol.success:
        raise ValueError(f"la simulación del péndulo doble no llegó al final ({sol.message})")

    traza: list[tuple[float, float]] = []
    energia: list[float] = []
    for a1, v1, a2, v2 in zip(*sol.y):
        x1 = l1 * math.sin(a1)
        y1 = -l1 * math.cos(a1)
        traza.append((x1 + l2 * math.sin(a2), y1 - l2 * math.cos(a2)))
        energia.append(_energia_pendulo_doble(m1, m2, l1, l2, gravedad, a1, v1, a2, v2))

    # El cero de la energía es el reposo con los dos brazos colgando: así la pantalla nunca muestra
    # una energía negativa, que no significa nada para quien mira.
    reposo = _energia_pendulo_doble(m1, m2, l1, l2, gravedad, 0.0, 0.0, 0.0, 0.0)
    energia = [e - reposo for e in energia]

    return PenduloDoble(
        t=[float(v) for v in sol.t],
        angulo_1=[math.degrees(float(v)) for v in sol.y[0]],
        angulo_2=[math.degrees(float(v)) for v in sol.y[2]],
        traza=traza,
        energia=energia,
        energia_inicial=energia[0],
        masa_1=m1,
        masa_2=m2,
        longitud_1=l1,
        longitud_2=l2,
        gravedad=gravedad,
    )
