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


# ------------------------------------------------------------------------------------------
# Conducción en una placa: la ecuación del calor en 2D, por diferencias finitas
# ------------------------------------------------------------------------------------------
#
# Cuatro bordes a temperatura fija y la placa partiendo pareja a la temperatura del borde más frío.
# Se integra con el esquema explícito (FTCS) hasta que deja de cambiar: la última foto es el régimen
# permanente (la ecuación de Laplace) y las anteriores, cómo se llega a él. El esquema es estable con
# r = α·Δt/Δx² ≤ 1/4; se usa 0,24.

PASO_TERMICO = 0.24
FOTOS_PLACA = 48


@dataclass
class PlacaTermica:
    """Las fotos de la temperatura de la placa (filas de abajo hacia arriba) y sus bordes."""

    fotos: list[np.ndarray]  # cada una de forma (ny, nx), incluidos los bordes
    izquierda: float
    derecha: float
    arriba: float
    abajo: float
    minima: float
    maxima: float

    @property
    def permanente(self) -> np.ndarray:
        return self.fotos[-1]

    def en(self, avance: float) -> np.ndarray:
        """La temperatura en el avance 0..1 del recorrido, interpolada entre las dos fotos vecinas."""
        posicion = min(max(avance, 0.0), 1.0) * (len(self.fotos) - 1)
        i = min(int(posicion), len(self.fotos) - 2)
        f = posicion - i
        return self.fotos[i] * (1 - f) + self.fotos[i + 1] * f

    def centro(self, campo: np.ndarray | None = None) -> float:
        """La temperatura del punto central de la placa."""
        t = self.permanente if campo is None else campo
        ny, nx = t.shape
        return float((t[(ny - 1) // 2, (nx - 1) // 2] + t[ny // 2, nx // 2]) / 2)


def conducir_placa(
    izquierda: float,
    derecha: float,
    arriba: float,
    abajo: float,
    nx: int = 33,
    ny: int = 17,
    tolerancia: float = 1e-4,
    maximo: int = 40000,
) -> PlacaTermica:
    """Integra la placa desde la temperatura más fría hasta el régimen permanente."""
    bordes = [float(v) for v in (izquierda, derecha, arriba, abajo)]
    for valor, nombre in zip(bordes, ("izquierda", "derecha", "arriba", "abajo"), strict=True):
        if not math.isfinite(valor):
            raise ValueError(f"la temperatura de {nombre} tiene que ser un número (dice {valor})")
    if nx < 5 or ny < 5:
        raise ValueError("la placa necesita al menos 5 puntos por lado")
    minima, maxima = min(bordes), max(bordes)
    t = np.full((ny, nx), minima, dtype=float)

    def fijar(campo: np.ndarray) -> None:
        campo[:, 0], campo[:, -1] = izquierda, derecha
        campo[-1, 1:-1], campo[0, 1:-1] = arriba, abajo
        # Las esquinas son el promedio de sus dos bordes: no pertenecen a ninguno.
        campo[0, 0] = (izquierda + abajo) / 2
        campo[0, -1] = (derecha + abajo) / 2
        campo[-1, 0] = (izquierda + arriba) / 2
        campo[-1, -1] = (derecha + arriba) / 2

    fijar(t)
    historia = [t.copy()]
    escala = max(maxima - minima, 1e-9)
    for _ in range(maximo):
        vecinos = t[1:-1, :-2] + t[1:-1, 2:] + t[:-2, 1:-1] + t[2:, 1:-1]
        nuevo = t.copy()
        nuevo[1:-1, 1:-1] = t[1:-1, 1:-1] + PASO_TERMICO * (vecinos - 4 * t[1:-1, 1:-1])
        cambio = float(np.abs(nuevo - t).max()) / escala
        t = nuevo
        historia.append(t.copy())
        if cambio < tolerancia * PASO_TERMICO:
            break
    # Fotos repartidas en raíz del tiempo: el calor entra rápido al principio y después se asienta.
    n = len(historia) - 1
    indices = sorted({round(n * (k / (FOTOS_PLACA - 1)) ** 2) for k in range(FOTOS_PLACA)})
    return PlacaTermica(
        fotos=[historia[i] for i in indices],
        izquierda=float(izquierda),
        derecha=float(derecha),
        arriba=float(arriba),
        abajo=float(abajo),
        minima=minima,
        maxima=maxima,
    )


# ------------------------------------------------------------------------------------------
# Flujo entre placas: Couette y Poiseuille, desde el reposo hasta el perfil desarrollado
# ------------------------------------------------------------------------------------------
#
# Las dos tienen solución exacta en serie de Fourier (ecuación de difusión de la cantidad de
# movimiento). ``s = y/h`` va de 0 (placa de abajo) a 1 (placa de arriba) y ``tau = ν·t/h²`` es el
# tiempo adimensional: con tau ≈ 0,5 el perfil ya no se distingue del desarrollado.

TIEMPO_FLUJO = 0.5
TERMINOS_FLUJO = 80


def perfil_couette(s: np.ndarray | float, tau: float) -> np.ndarray:
    """u/U de un fluido entre una placa quieta (s=0) y una que se mueve a U (s=1)."""
    s = np.asarray(s, dtype=float)
    u = s.copy()
    if tau <= 0:
        return np.where(s >= 1.0, 1.0, 0.0)
    for n in range(1, TERMINOS_FLUJO + 1):
        u = u + 2 * (-1) ** n / (n * math.pi) * np.sin(n * math.pi * s) * math.exp(
            -((n * math.pi) ** 2) * tau
        )
    return u


def perfil_poiseuille(s: np.ndarray | float, tau: float) -> np.ndarray:
    """u/u_max de un fluido empujado por presión entre dos placas quietas (perfil parabólico)."""
    s = np.asarray(s, dtype=float)
    u = 4 * s * (1 - s)
    if tau <= 0:
        return np.zeros_like(s)
    for n in range(1, 2 * TERMINOS_FLUJO, 2):
        u = u - 32 / (n * math.pi) ** 3 * np.sin(n * math.pi * s) * math.exp(-((n * math.pi) ** 2) * tau)
    return u


def gradiente_de_perfil(flujo: str, s: np.ndarray | float) -> np.ndarray:
    """d(u/u_ref)/d(s) del perfil desarrollado: el esfuerzo cortante es μ·u_ref/h por esto."""
    s = np.asarray(s, dtype=float)
    if flujo == "couette":
        return np.ones_like(s)
    return 4 * (1 - 2 * s)
