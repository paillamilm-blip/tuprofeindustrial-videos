"""Formato del guion (YAML) y su lectura con mensajes de error en español claro.

Cada bloque separa lo que se VE (``texto`` o ``tex`` en LaTeX) de lo que se ESCUCHA (``voz``),
porque la voz sintética no sabe leer LaTeX.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
    model_validator,
)

from .config import _validar_hex
from .errores import ErrorMotor
from .moldes import MOLDES, normalizar_molde, opciones_de_moldes
from .pausas import validar_pausas
from .tex import llaves_balanceadas
from .visuales import (
    MARCAS_BLOQUES,
    MARCAS_CERCHA,
    MARCAS_CIRCULO,
    MARCAS_EJE,
    MARCAS_ENGRANAJE,
    MARCAS_ESCALA,
    MARCAS_FLUJO,
    MARCAS_FUNCION,
    MARCAS_MOHR,
    MARCAS_ONDA,
    MARCAS_OSCILADOR,
    MARCAS_PENDULO,
    MARCAS_PENDULO_DOBLE,
    MARCAS_PLACA,
    MARCAS_POLEA,
    MARCAS_POLIGONO,
    MARCAS_PROBABILIDAD,
    MARCAS_PROYECTIL,
    MARCAS_RESORTE,
    MARCAS_SOLIDO,
    MARCAS_TANQUE,
    MARCAS_TOLVA,
    MARCAS_TUBERIA,
    MARCAS_VECTOR_3D,
    MARCAS_VENN,
    MARCAS_VIGA,
    SEGUNDOS_VISUAL,
    TIPOS_3D,
    analizar_angulo,
    analizar_barras,
    analizar_bloques,
    analizar_cercha,
    analizar_eje,
    analizar_energia,
    analizar_engranajes,
    analizar_escala,
    analizar_flujo,
    analizar_funcion,
    analizar_mohr,
    analizar_onda,
    analizar_optica,
    analizar_oscilador,
    analizar_pendulo,
    analizar_pendulo_doble,
    analizar_placa,
    analizar_polea,
    analizar_poligono,
    analizar_probabilidad,
    analizar_proyectil,
    analizar_recta,
    analizar_resorte,
    analizar_solido,
    analizar_tanque,
    analizar_tolva,
    analizar_torta,
    analizar_tuberia,
    analizar_vector_3d,
    analizar_venn,
    analizar_viga,
    aspecto_placa,
    normalizar_vectores,
)

MATERIAS: dict[str, str] = {"matematica": "MATEMÁTICA", "fisica": "FÍSICA", "ingenieria": "INGENIERÍA"}

# La categoría temática de un guion: la misma materia, con el nombre que usa el catálogo de estilos.
Categoria = Literal["matematicas", "fisica", "ingenieria"]
CATEGORIA_DE_MATERIA: dict[str, Categoria] = {
    "matematica": "matematicas",
    "fisica": "fisica",
    "ingenieria": "ingenieria",
}

# Caracteres que aparecen cuando una fórmula se escribe entre comillas DOBLES en YAML:
# "\frac" → salto de página + "rac", "\times" → tabulación + "imes", "\vec" → tab vertical…
_CONTROL_YAML = {"\x07", "\x08", "\t", "\n", "\x0b", "\x0c", "\r", "\x1b", "\x00"}
_AYUDA_COMILLAS = (
    "parece que la fórmula está entre comillas dobles y YAML se 'comió' las barras invertidas. "
    "Escríbela entre comillas simples, por ejemplo: tex: 'h = \\frac{1}{2} g t^2'"
)


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _validar_tex(valor: str | None) -> str | None:
    if valor is None:
        return None
    if any(c in valor for c in _CONTROL_YAML):
        raise ValueError(_AYUDA_COMILLAS)
    if not llaves_balanceadas(valor):
        raise ValueError("las llaves { } de la fórmula no están balanceadas")
    return valor


# Los espacios de LaTeX no cuentan al comparar términos (igual que en componentes.coincidencias).
_ESPACIOS_TEX = re.compile(r"\\[,;:!]|\\quad|\\qquad|\\ |\s+")


def _como_lista(valor: Any) -> Any:
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    return valor


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def _quitar_comillas_curvas(cls, valor: Any) -> Any:
        """TextEdit (Mac) cambia ' y " por comillas curvas; si envuelven el valor, se quitan."""
        if isinstance(valor, str):
            limpio = valor.strip()
            if len(limpio) >= 2 and limpio[0] in "“‘«" and limpio[-1] in "”’»":
                return limpio[1:-1]
        return valor


class _ConTexto(_Base):
    """Bloque que acepta la forma corta ``clave: "texto"`` o la larga con ``texto`` y ``voz``."""

    texto: str = Field(min_length=1)
    voz: str | None = None

    _pausas = field_validator("voz")(classmethod(lambda cls, v: validar_pausas(v)))

    @model_validator(mode="before")
    @classmethod
    def _forma_corta(cls, valor: Any) -> Any:
        return {"texto": valor} if isinstance(valor, str) else valor

    @property
    def voz_final(self) -> str:
        return self.voz or self.texto


class Gancho(_ConTexto):
    destacar: list[str] = []
    tex: str | None = None  # fórmula bajo la pregunta, ej. '(x+5)^2 = x^2 + 25'
    emoji: str | None = None  # ej. "🤯", "alerta" o un sticker propio
    visual: Visual | None = None  # el dibujo que acompaña la promesa, para no hablar de lo que no se ve

    _lista = field_validator("destacar", mode="before")(classmethod(lambda cls, v: _como_lista(v)))
    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))


class Enunciado(_ConTexto):
    etiqueta: str = "PROBLEMA"  # el rótulo de la tarjeta: "PROBLEMA", "LA RESPUESTA"…
    destacar: list[str] = []

    _lista = field_validator("destacar", mode="before")(classmethod(lambda cls, v: _como_lista(v)))


class Bloque(_ConTexto):
    emoji: str | None = None


class Dato(_Base):
    tex: str = Field(min_length=1)
    voz: str = Field(min_length=1)

    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))
    _pausas = field_validator("voz")(classmethod(lambda cls, v: validar_pausas(v)))


class Visual(_Base):
    """El dibujo de un paso: un gráfico de función, un diagrama de fuerzas, un circuito o un polígono.

    Sólo se usan los campos del ``tipo`` elegido; los demás quedan vacíos a propósito.
    """

    tipo: Literal[
        "grafico_funcion",
        "diagrama_fuerzas",
        "circuito",
        "poligono_regular",
        "proyectil",
        "circulo_trig",
        "solido",
        "solido_3d",
        "vector_3d",
        "venn",
        "recta",
        "probabilidad",
        "torta",
        "barras",
        "onda",
        "energia",
        "optica",
        "pendulo",
        "resorte",
        "escala",
        "oscilador",
        "pendulo_doble",
        "polea",
        "tanque",
        "viga",
        "cercha",
        "bloques",
        "engranaje",
        "mohr",
        "tolva_3d",
        "tuberia_3d",
        "eje_3d",
        "gradiente_termico",
        "perfil_flujo",
    ]

    # Todos los tipos: cuánto de su tarjeta ocupa el dibujo. «auto» = lo que decide el motor (solo achica
    # lo que no cabe); chico, mediano y grande lo llevan a esa fracción del espacio, aunque haya que agrandarlo.
    tamano: Literal["auto", "chico", "mediano", "grande"] = "auto"

    # grafico_funcion
    funcion: str | None = None
    variable: str | None = None
    rango: list[float] | None = None
    marcar: list[float] = []
    eje_x: str | None = None  # ej. "tiempo (s)"
    eje_y: str | None = None  # ej. "altura (m)"
    # Matemática viva (opcional): una tangente que recorre la curva o el área que se llena bajo ella
    movimiento: Literal["", "tangente", "area"] = ""
    desde: float | None = None  # x donde empieza el recorrido; vacío = el inicio del rango
    hasta: float | None = None  # x donde termina; vacío = el fin del rango

    # diagrama_fuerzas
    cuerpo: Literal["bloque", "bola"] = "bloque"
    vectores: list[str] = []
    angulo: float | None = None  # plano inclinado, en grados
    descomponer: bool = False  # parte el peso en P sen θ y P cos θ sobre el plano

    # circuito
    arreglo: Literal["serie", "paralelo"] = "serie"
    fuente: str | None = None  # ej. '12 V'
    resistencias: list[str] = []  # ej. ['4 Ω', '6 Ω']

    # proyectil
    velocidad: str | None = None  # la del lanzamiento, con su unidad: '20 m/s'

    # poligono_regular
    lados: int | None = None  # de 3 a 8
    lado: str | None = None  # la medida de un lado, con su unidad: '12 cm' (también la arista del cubo)
    anotar: list[str] = []  # ej. ['apotema', 'angulo_interior']

    # solido
    figura: Literal["", "cubo", "cilindro", "cono", "esfera"] = ""
    radio: str | None = None  # con su unidad: '3 cm'
    altura: str | None = None  # con su unidad: '5 cm'

    # solido_3d (además de figura / lado / radio / altura / anotar)
    vista: Literal["frente", "piso", "ala", "axonometrica"] = "axonometrica"
    corte: Literal["sin_corte", "mitad"] = "sin_corte"  # mitad solo en cubo: ver el validador
    despiece: StrictBool = False  # las piezas se separan al final de la órbita (caras, tapas o mitades)

    # vector_3d
    componentes: list[float] | None = None  # las tres: [3, 4, 12]
    unidad: str | None = None  # la misma para las tres: 'cm'

    # venn
    solo_a: int | None = None  # cuántos viven sólo en A
    solo_b: int | None = None
    ambos: int | None = None  # la intersección
    fuera: int | None = None  # los que no están en ninguno

    # recta
    extremo_a: float | None = None  # el extremo izquierdo del intervalo (o el origen del rayo)
    extremo_b: float | None = None  # sin extremo_b la recta marca un rayo
    incluye_a: bool = True  # punto lleno; false = punto abierto
    incluye_b: bool = True
    derecha: bool = True  # hacia dónde apunta el rayo

    # probabilidad
    favorables: int | None = None
    totales: int | None = None

    # escala (además de lado / anotar): caben factor² cuadrados o factor³ cubos del original
    factor: int | None = None  # cuántas veces crece el lado: 2 o 3
    dimension: int | None = None  # 2 = área (cuadrados), 3 = volumen (cubos)

    # torta / barras: categorías con su valor al final, ej. ['Fútbol 12', 'Básquetbol 8']
    categorias: list[str] = []

    # onda
    amplitud: str | None = None  # con su unidad: '0,5 m'
    longitud_onda: str | None = None  # lambda, con su unidad: '2 m'
    periodo: float | None = None  # segundos entre crestas; si falta, la onda no dice su velocidad

    # optica
    n1: float | None = None  # índice de refracción del medio del raye que llega
    n2: float | None = None  # y del medio al que pasa
    angulo_incidence: float | None = None  # grados medidos desde la normal

    # pendulo (reusa angulo: cuánto se apartó de la vertical)
    longitud: str | None = None  # del hilo, con su unidad: '1 m'

    # resorte
    constante: str | None = None  # '200 N/m'
    extension: str | None = None  # '10 cm' (el motor la pasa a metros él solo)

    # polea
    masa_a: str | None = None  # '3 kg'
    masa_b: str | None = None  # '2 kg'

    # tanque (anota 'llenado' o 'vaciado')
    capacidad: str | None = None  # '120 L'
    entrada: str | None = None  # '8 L/min'
    salida: str | None = None  # '2 L/min'; si falta, el tanque no pierde

    # viga (reusa longitud: la luz entre apoyos) y cercha (reusa base y altura)
    carga: str | None = None  # '200 N' al centro, o '50 N/m' repartida
    repartida: bool = False
    base: str | None = None  # '6 m'

    # bloques (la realimentación negativa es la regla; positiva = true para el contraejemplo)
    adelante: str | None = None  # la ganancia del bloque directo, sin unidad: '10'
    retro: str | None = None  # la ganancia del tramo de realimentación: '0.2'
    negativa: bool = True

    # engranaje
    dientes_a: str | None = None  # los de la conductora: '20'
    dientes_b: str | None = None  # los de la conducida, distintos: '60'
    rpm: str | None = None  # las vueltas del eje de entrada: '1200 rpm'

    # mohr
    sigma_x: str | None = None  # '80 MPa'
    sigma_y: str | None = None  # '20 MPa'
    cortante: str | None = None  # '30 MPa'

    # oscilador amortiguado y péndulo doble: los dos que se integran con SciPy (simulacion.py)
    masa: str | None = None  # '2 kg' o '500 g'
    amortiguamiento: str | None = None  # '8 N·s/m'; vacío = sin fricción
    duracion: float | None = None  # segundos simulados (hasta 20); vacío = 6 el resorte, 10 el doble
    masa_1: str | None = None  # la del brazo de arriba: '1 kg'
    masa_2: str | None = None  # la del brazo de abajo: '1 kg'
    longitud_1: str | None = None  # '1 m'
    longitud_2: str | None = None  # '1 m'
    angulo_1: float | None = None  # grados desde la vertical, positivo a la derecha
    angulo_2: float | None = None

    # tolva_3d (reusa radio y altura: los del cilindro), tuberia_3d (reusa radio y longitud), eje_3d
    radio_salida: str | None = None  # la boca de abajo del cono: '0,3 m'
    altura_cono: str | None = None  # '1,2 m'
    espesor: str | None = None  # la pared del tubo: '5 mm'
    bridas: bool = True  # una brida en cada extremo del tubo
    radios: list[float] = []  # los del eje, tramo por tramo: [20, 30, 25]
    largos: list[float] = []  # en el mismo orden y la misma unidad (campo «unidad»)

    # gradiente_termico (reusa base y altura para la forma de la placa)
    temp_izquierda: float | None = None  # °C de cada borde, fijos
    temp_derecha: float | None = None
    temp_arriba: float | None = None
    temp_abajo: float | None = None

    # perfil_flujo (reusa velocidad: la de la placa en Couette o la máxima en Poiseuille)
    flujo: Literal["", "couette", "poiseuille"] = ""
    separacion: str | None = None  # entre las placas: '1 cm'
    viscosidad: str | None = None  # '0,001 Pa·s'; sin ella no se calcula el esfuerzo cortante

    _listas = field_validator(
        "rango",
        "marcar",
        "vectores",
        "resistencias",
        "anotar",
        "categorias",
        "radios",
        "largos",
        mode="before",
    )(classmethod(lambda cls, v: None if v is None else _como_lista(v)))

    @field_validator("movimiento", mode="before")
    @classmethod
    def _movimiento_no_es_un_si(cls, valor: Any) -> Any:
        """Un LLM tiende a escribir «movimiento: true»: el motor necesita saber QUÉ se mueve."""
        if valor is None or valor is False:
            return ""
        if valor is True:
            raise ValueError(
                'movimiento no es verdadero/falso: di qué se mueve sobre la curva, "tangente" o "area" '
                "(los dibujos de física ya se mueven solos, sin este campo)"
            )
        return valor

    def _validar_movimiento(self) -> None:
        """La tangente o el área: un tramo que exista entero y lo que se lee en vivo, coherente."""
        desconocidas = [m for m in self.anotar if m not in MARCAS_FUNCION]
        if desconocidas:
            raise ValueError(
                f"«{desconocidas[0]}» no es una marca del gráfico; el motor sabe anotar "
                f"{', '.join(MARCAS_FUNCION)} (con movimiento: tangente o area)"
            )
        if not self.movimiento:
            if self.anotar:
                raise ValueError(
                    f"«{self.anotar[0]}» se lee mientras algo se mueve: agrega movimiento: "
                    f"{'tangente' if self.anotar[0] == 'pendiente' else 'area'}"
                )
            if self.desde is not None or self.hasta is not None:
                raise ValueError("desde y hasta marcan el recorrido: agrega movimiento: tangente o area")
            return
        pide = {"pendiente": "tangente", "area": "area"}
        for marca in self.anotar:
            if pide[marca] != self.movimiento:
                raise ValueError(
                    f"la marca «{marca}» va con movimiento: {pide[marca]}, y este gráfico dice "
                    f"movimiento: {self.movimiento}"
                )
        f = analizar_funcion(self.funcion or "", self.variable, self.rango, self.marcar)
        x0, x1 = f.rango_x
        a = x0 if self.desde is None else float(self.desde)
        b = x1 if self.hasta is None else float(self.hasta)
        if not a < b:
            raise ValueError(
                f"el recorrido va de izquierda a derecha: desde ({a:g}) tiene que ser menor que hasta ({b:g})"
            )
        if a < x0 - 1e-9 or b > x1 + 1e-9:
            raise ValueError(
                f"el recorrido [{a:g}, {b:g}] se sale del rango del gráfico [{x0:g}, {x1:g}]; "
                "ajusta desde/hasta o agranda el rango"
            )
        hueco = f.tramo_sin_huecos(a, b)
        if hueco is not None:
            raise ValueError(
                f"la función no existe en x ≈ {hueco:.2f} (asíntota o raíz de un negativo), dentro del "
                "recorrido: acorta desde/hasta para que no la cruce"
            )

    def _validar_industrial(self) -> None:
        """Las piezas 3D, la placa y el flujo: medidas completas y marcas del tipo."""
        marcas = {
            "tolva_3d": MARCAS_TOLVA,
            "tuberia_3d": MARCAS_TUBERIA,
            "eje_3d": MARCAS_EJE,
            "gradiente_termico": MARCAS_PLACA,
            "perfil_flujo": MARCAS_FLUJO,
        }[self.tipo]
        desconocidas = [m for m in self.anotar if m not in marcas]
        if desconocidas:
            raise ValueError(
                f"«{desconocidas[0]}» no es una marca de {self.tipo}; el motor sabe anotar {', '.join(marcas)}"
            )
        if self.tipo == "tolva_3d":
            faltan = [
                n
                for n in ("radio", "altura", "radio_salida", "altura_cono")
                if not (getattr(self, n) or "").strip()
            ]
            if faltan:
                raise ValueError(
                    f"la tolva necesita {', '.join(faltan)} con su unidad, ej. radio: '1,5 m', altura: '2 m', "
                    "radio_salida: '0,3 m', altura_cono: '1,2 m'"
                )
            self.tolva()
        elif self.tipo == "tuberia_3d":
            faltan = [n for n in ("radio", "espesor", "longitud") if not (getattr(self, n) or "").strip()]
            if faltan:
                raise ValueError(
                    f"la tubería necesita {', '.join(faltan)} con su unidad, ej. radio: '10 cm', "
                    "espesor: '1 cm', longitud: '80 cm'"
                )
            self.tuberia()
        elif self.tipo == "eje_3d":
            self.eje()
        elif self.tipo == "gradiente_termico":
            faltan = [
                n
                for n in ("temp_izquierda", "temp_derecha", "temp_arriba", "temp_abajo")
                if getattr(self, n) is None
            ]
            if faltan:
                raise ValueError(
                    f"la placa necesita la temperatura de cada borde en °C: falta {', '.join(faltan)}"
                )
            temps = [self.temp_izquierda, self.temp_derecha, self.temp_arriba, self.temp_abajo]
            if max(temps) - min(temps) < 1e-9:
                raise ValueError("con los cuatro bordes a la misma temperatura no hay calor que mostrar")
            aspecto_placa(self.base, self.altura)
        else:
            if not self.flujo:
                raise ValueError(
                    "falta decir el flujo: couette (una placa se mueve) o poiseuille (lo empuja la presión)"
                )
            if not (self.velocidad or "").strip() or not (self.separacion or "").strip():
                raise ValueError(
                    "el flujo necesita la velocidad y la separación, ej. velocidad: '2 m/s', separacion: '1 cm'"
                )
            figura = self.flujo_analizado()
            if "esfuerzo" in self.anotar and figura.viscosidad is None:
                raise ValueError(
                    "para anotar el esfuerzo cortante el guion necesita la viscosidad, ej. '0,001 Pa·s'"
                )

    def tolva(self):
        return analizar_tolva(
            self.radio or "", self.altura or "", self.radio_salida or "", self.altura_cono or ""
        )

    def tuberia(self):
        return analizar_tuberia(self.radio or "", self.espesor or "", self.longitud or "")

    def eje(self):
        return analizar_eje(self.radios, self.largos, self.unidad or "")

    def placa(self):
        return analizar_placa(
            float(self.temp_izquierda or 0.0),
            float(self.temp_derecha or 0.0),
            float(self.temp_arriba or 0.0),
            float(self.temp_abajo or 0.0),
            aspecto_placa(self.base, self.altura),
        )

    def flujo_analizado(self):
        return analizar_flujo(self.flujo, self.velocidad or "", self.separacion or "", self.viscosidad)

    @model_validator(mode="after")
    def _campos_del_tipo(self) -> Visual:
        if self.movimiento and self.tipo != "grafico_funcion":
            raise ValueError("movimiento (tangente o área) solo va en un grafico_funcion")
        if (self.desde is not None or self.hasta is not None) and not self.movimiento:
            raise ValueError(
                'desde y hasta marcan un recorrido: van con movimiento: "tangente" o "area", en un grafico_funcion'
            )
        if self.despiece:
            if self.tipo not in TIPOS_3D:
                raise ValueError(f"el despiece solo va en un cuerpo 3D ({', '.join(TIPOS_3D)})")
            if self.figura == "esfera":
                raise ValueError(
                    "la esfera es una sola pieza y no tiene qué separar: quita despiece o usa cubo, "
                    "cilindro o cono"
                )
        if self.tipo in ("tolva_3d", "tuberia_3d", "eje_3d", "gradiente_termico", "perfil_flujo"):
            self._validar_industrial()
        elif self.tipo == "grafico_funcion":
            if not (self.funcion or "").strip():
                raise ValueError("un gráfico de función necesita la fórmula, ej. funcion: '-x^2 + 4x'")
            if self.rango is not None and len(self.rango) != 2:
                raise ValueError("el rango son dos números, ej. rango: [0, 5]")
            self._validar_movimiento()
        elif self.tipo == "diagrama_fuerzas":
            self.vectores = normalizar_vectores(self.vectores)
            if self.angulo is not None:
                if not 0 < self.angulo < 90:
                    raise ValueError(f"el ángulo del plano va entre 0 y 90 grados, y dice {self.angulo}")
                if self.cuerpo != "bloque":
                    raise ValueError("el ángulo (plano inclinado) solo va con cuerpo: bloque")
            if self.descomponer:
                if self.angulo is None:
                    raise ValueError("descomponer el peso sólo tiene sentido sobre la rampa: ponle angulo:")
                if "P" not in self.vectores:
                    raise ValueError("para descomponer el peso el diagrama necesita la flecha «P»")
        elif self.tipo == "proyectil":
            if not (self.velocidad or "").strip():
                raise ValueError("un proyectil necesita la velocidad de lanzamiento, ej. velocidad: '20 m/s'")
            if self.angulo is None:
                raise ValueError("un proyectil necesita el ángulo de lanzamiento, ej. angulo: 30")
            analizar_proyectil(self.velocidad, self.angulo)
            desconocidas = [m for m in self.anotar if m not in MARCAS_PROYECTIL]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de un proyectil; "
                    f"el motor sabe anotar {', '.join(MARCAS_PROYECTIL)}"
                )
        elif self.tipo == "circulo_trig":
            if self.angulo is None:
                raise ValueError("un círculo trigonométrico necesita su ángulo en grados, ej. angulo: 30")
            if not 0 <= self.angulo < 360:
                raise ValueError(
                    f"el ángulo del círculo va de 0 a 360 grados (una vuelta), y dice {self.angulo}"
                )
            figura = analizar_angulo(self.angulo)
            desconocidas = [m for m in self.anotar if m not in MARCAS_CIRCULO]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del círculo trigonométrico; "
                    f"el motor sabe anotar {', '.join(MARCAS_CIRCULO)}"
                )
            if "tangente" in self.anotar and figura.tangente is None:
                raise ValueError(
                    f"a {figura.grados:g}° la tangente no existe (el radio queda paralelo a ella): "
                    "anota seno o coseno"
                )
        elif self.tipo in ("solido", "solido_3d"):
            if not self.figura:
                raise ValueError("Falta decir qué sólido es: cubo, cilindro, cono o esfera.")
            analizar_solido(self.figura, self.lado, self.radio, self.altura)
            if self.tipo == "solido_3d" and self.corte == "mitad" and self.figura != "cubo":
                raise ValueError(
                    "el corte a la mitad solo se dibuja bien en el cubo; con otra figura la cara "
                    "del corte no queda bien. Usa «Sin corte» o cambia la figura a cubo"
                )
            desconocidas = [m for m in self.anotar if m not in MARCAS_SOLIDO]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de un sólido; "
                    f"el motor sabe anotar {', '.join(MARCAS_SOLIDO)}"
                )
        elif self.tipo == "vector_3d":
            analizar_vector_3d(self.componentes or [], self.unidad or "")
            desconocidas = [m for m in self.anotar if m not in MARCAS_VECTOR_3D]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de un vector en el espacio; "
                    f"el motor sabe anotar {', '.join(MARCAS_VECTOR_3D)}"
                )
        elif self.tipo == "venn":
            if self.solo_a is None or self.solo_b is None or self.ambos is None:
                raise ValueError("el diagrama de Venn necesita los tres contajes: solo_a, solo_b y ambos")
            analizar_venn(self.solo_a, self.solo_b, self.ambos, self.fuera or 0)
            desconocidas = [m for m in self.anotar if m not in MARCAS_VENN]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del diagrama de Venn; "
                    f"el motor sabe anotar {', '.join(MARCAS_VENN)}"
                )
        elif self.tipo == "recta":
            if self.extremo_a is None:
                raise ValueError("la recta numérica necesita su extremo, ej. extremo_a: 2")
            analizar_recta(self.extremo_a, self.extremo_b, self.incluye_a, self.incluye_b, self.derecha)
            if self.anotar:
                raise ValueError("la recta numérica no lleva marcas: deja anotar vacío")
        elif self.tipo == "probabilidad":
            if self.favorables is None or self.totales is None:
                raise ValueError("la probabilidad necesita sus casos, ej. favorables: 3 y totales: 8")
            analizar_probabilidad(self.favorables, self.totales)
            desconocidas = [m for m in self.anotar if m not in MARCAS_PROBABILIDAD]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de la probabilidad; "
                    f"el motor sabe anotar {', '.join(MARCAS_PROBABILIDAD)}"
                )
        elif self.tipo in ("torta", "barras"):
            nombre = "la torta" if self.tipo == "torta" else "las barras"
            if not self.categorias:
                raise ValueError(
                    f"{nombre} necesita sus categorías, ej. categorias: ['Fútbol 12', 'Básquetbol 8']"
                )
            analizar = analizar_torta if self.tipo == "torta" else analizar_barras
            analizar(
                self.categorias
            )  # rechaza menos de 2, más de 6, valores no positivos y textos sin número
        elif self.tipo == "onda":
            if not (self.amplitud or "").strip() or not (self.longitud_onda or "").strip():
                raise ValueError(
                    "la onda necesita su amplitud y su longitud, ej. amplitud: '0,5 m' y longitud_onda: '2 m'"
                )
            analizar_onda(self.amplitud, self.longitud_onda, self.periodo)
            desconocidas = [m for m in self.anotar if m not in MARCAS_ONDA]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de la onda; el motor sabe anotar {', '.join(MARCAS_ONDA)}"
                )
            if "velocidad" in self.anotar and self.periodo is None:
                raise ValueError("para anotar la velocidad la onda necesita su periodo, ej. periodo: 0.4")
        elif self.tipo == "energia":
            if not self.categorias:
                raise ValueError(
                    "la barra de energía necesita sus tramos, ej. categorias: ['Cinética 60', 'Térmica 40']"
                )
            analizar_energia(self.categorias)
        elif self.tipo == "optica":
            if self.n1 is None or self.n2 is None or self.angulo_incidence is None:
                raise ValueError(
                    "la óptica necesita sus dos índices y el ángulo, "
                    "ej. n1: 1.0, n2: 1.33 y angulo_incidence: 30"
                )
            analizar_optica(self.n1, self.n2, self.angulo_incidence)
            if self.anotar:
                raise ValueError("la refracción no lleva marcas: sus dos ángulos van siempre")
        elif self.tipo == "pendulo":
            if not (self.longitud or "").strip() or self.angulo is None:
                raise ValueError(
                    "el péndulo necesita su longitud y su ángulo, ej. longitud: '1 m' y angulo: 20"
                )
            analizar_pendulo(self.longitud, self.angulo)
            desconocidas = [m for m in self.anotar if m not in MARCAS_PENDULO]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del péndulo; el motor sabe anotar {', '.join(MARCAS_PENDULO)}"
                )
        elif self.tipo == "resorte":
            if not (self.constante or "").strip() or not (self.extension or "").strip():
                raise ValueError(
                    "el resorte necesita su constante y su extensión, ej. constante: '200 N/m' y extension: '10 cm'"
                )
            analizar_resorte(self.constante, self.extension)
            desconocidas = [m for m in self.anotar if m not in MARCAS_RESORTE]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del resorte; "
                    f"el motor sabe anotar {', '.join(MARCAS_RESORTE)}"
                )
        elif self.tipo == "escala":
            if not (self.lado or "").strip():
                raise ValueError("la escala necesita el lado original con su unidad, ej. lado: '4 cm'")
            analizar_escala(self.lado, self.factor or 2, self.dimension or 3)
            desconocidas = [m for m in self.anotar if m not in MARCAS_ESCALA]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de la escala; "
                    f"el motor sabe anotar {', '.join(MARCAS_ESCALA)}"
                )
        elif self.tipo == "polea":
            if not (self.masa_a or "").strip() or not (self.masa_b or "").strip():
                raise ValueError("la polea necesita sus dos masas, ej. masa_a: '3 kg' y masa_b: '2 kg'")
            analizar_polea(self.masa_a, self.masa_b)
            desconocidas = [m for m in self.anotar if m not in MARCAS_POLEA]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de la polea; el motor sabe anotar {', '.join(MARCAS_POLEA)}"
                )
        elif self.tipo == "tanque":
            if not (self.capacidad or "").strip() or not (self.entrada or "").strip():
                raise ValueError(
                    "el tanque necesita su capacidad y la llave que lo llena, "
                    "ej. capacidad: '120 L' y entrada: '8 L/min'"
                )
            analizar_tanque(self.capacidad, self.entrada, self.salida)
            desconocidas = [m for m in self.anotar if m not in MARCAS_TANQUE]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del tanque; el motor sabe anotar {', '.join(MARCAS_TANQUE)}"
                )
            if "vaciado" in self.anotar and not (self.salida or "").strip():
                raise ValueError("para anotar el vaciado el tanque necesita su fisura, ej. salida: '2 L/min'")
        elif self.tipo == "viga":
            if not (self.longitud or "").strip() or not (self.carga or "").strip():
                raise ValueError("la viga necesita su luz y su carga, ej. longitud: '4 m' y carga: '200 N'")
            analizar_viga(self.longitud, self.carga, self.repartida)
            desconocidas = [m for m in self.anotar if m not in MARCAS_VIGA]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de la viga; el motor sabe anotar {', '.join(MARCAS_VIGA)}"
                )
        elif self.tipo == "cercha":
            if (
                not (self.base or "").strip()
                or not (self.altura or "").strip()
                or not (self.carga or "").strip()
            ):
                raise ValueError(
                    "la cercha necesita su base, su altura y la carga, "
                    "ej. base: '6 m', altura: '4 m' y carga: '300 N'"
                )
            analizar_cercha(self.base, self.altura, self.carga)
            desconocidas = [m for m in self.anotar if m not in MARCAS_CERCHA]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de la cercha; "
                    f"el motor sabe anotar {', '.join(MARCAS_CERCHA)}"
                )
        elif self.tipo == "bloques":
            if not (self.adelante or "").strip() or not (self.retro or "").strip():
                raise ValueError("el lazo necesita sus dos ganancias, ej. adelante: '10' y retro: '0.2'")
            analizar_bloques(self.adelante, self.retro, self.negativa)
            desconocidas = [m for m in self.anotar if m not in MARCAS_BLOQUES]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del lazo; "
                    f"el motor sabe anotar {', '.join(MARCAS_BLOQUES)}"
                )
        elif self.tipo == "engranaje":
            if (
                not (self.dientes_a or "").strip()
                or not (self.dientes_b or "").strip()
                or not (self.rpm or "").strip()
            ):
                raise ValueError(
                    "la pareja de engranajes necesita sus dientes y su entrada, "
                    "ej. dientes_a: '20', dientes_b: '60' y rpm: '1200 rpm'"
                )
            analizar_engranajes(self.dientes_a, self.dientes_b, self.rpm)
            desconocidas = [m for m in self.anotar if m not in MARCAS_ENGRANAJE]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de la pareja; "
                    f"el motor sabe anotar {', '.join(MARCAS_ENGRANAJE)}"
                )
        elif self.tipo == "mohr":
            if (
                not (self.sigma_x or "").strip()
                or not (self.sigma_y or "").strip()
                or self.cortante is None
                or not str(self.cortante).strip()
            ):
                raise ValueError(
                    "el círculo de Mohr necesita sus dos normales y su cortante, "
                    "ej. sigma_x: '80 MPa', sigma_y: '20 MPa' y cortante: '30 MPa' "
                    "(escribe '0 MPa' si no hay corte)"
                )
            analizar_mohr(self.sigma_x, self.sigma_y, self.cortante)
            desconocidas = [m for m in self.anotar if m not in MARCAS_MOHR]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del círculo de Mohr; "
                    f"el motor sabe anotar {', '.join(MARCAS_MOHR)}"
                )
        elif self.tipo == "poligono_regular":
            if not (self.lado or "").strip():
                raise ValueError("un polígono necesita la medida del lado, ej. lado: '12 cm'")
            if self.lados is None:
                raise ValueError("un polígono necesita cuántos lados tiene, ej. lados: 5")
            analizar_poligono(self.lados, self.lado)  # rechaza lados < 3 o una medida sin número
            desconocidas = [m for m in self.anotar if m not in MARCAS_POLIGONO]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de un polígono; "
                    f"el motor sabe anotar {', '.join(MARCAS_POLIGONO)}"
                )
        elif self.tipo == "oscilador":
            for etiqueta, valor, ejemplo in (
                ("masa", self.masa, "masa: '2 kg'"),
                ("constante", self.constante, "constante: '200 N/m'"),
                ("amplitud", self.amplitud, "amplitud: '10 cm'"),
            ):
                if not (valor or "").strip():
                    raise ValueError(f"un oscilador necesita {etiqueta}, ej. {ejemplo}")
            figura = analizar_oscilador(
                self.masa or "",
                self.constante or "",
                self.amplitud or "",
                self.amortiguamiento or "",
                self.duracion,
            )
            desconocidas = [m for m in self.anotar if m not in MARCAS_OSCILADOR]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del oscilador; "
                    f"el motor sabe anotar {', '.join(MARCAS_OSCILADOR)}"
                )
            if "periodo" in self.anotar and figura.periodo is None:
                raise ValueError(
                    f"con ese amortiguador el resorte queda {figura.regimen} y ya no oscila: "
                    "no hay periodo que anotar. Baja el amortiguamiento para que quede subamortiguado"
                )
            if "decaimiento" in self.anotar and figura.decaimiento is None:
                raise ValueError(
                    "para anotar en cuánto se apaga la amplitud el oscilador necesita su "
                    "amortiguamiento, ej. amortiguamiento: '8 N·s/m'"
                )
        elif self.tipo == "pendulo_doble":
            for etiqueta, valor in (
                ("masa_1", self.masa_1),
                ("masa_2", self.masa_2),
                ("longitud_1", self.longitud_1),
                ("longitud_2", self.longitud_2),
            ):
                if not (valor or "").strip():
                    raise ValueError(
                        f"un péndulo doble necesita {etiqueta}, ej. masa_1: '1 kg', masa_2: '1 kg', "
                        "longitud_1: '1 m' y longitud_2: '1 m'"
                    )
            if self.angulo_1 is None or self.angulo_2 is None:
                raise ValueError(
                    "un péndulo doble necesita desde dónde se suelta, en grados desde la vertical: "
                    "angulo_1 y angulo_2, ej. 170 y 170"
                )
            analizar_pendulo_doble(
                self.masa_1 or "",
                self.masa_2 or "",
                self.longitud_1 or "",
                self.longitud_2 or "",
                self.angulo_1,
                self.angulo_2,
                self.duracion,
            )
            desconocidas = [m for m in self.anotar if m not in MARCAS_PENDULO_DOBLE]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del péndulo doble; "
                    f"el motor sabe anotar {', '.join(MARCAS_PENDULO_DOBLE)}"
                )
        elif not (self.fuente or "").strip():
            raise ValueError("un circuito necesita la fuente, ej. fuente: '12 V'")
        elif not 2 <= len(self.resistencias) <= 4:
            raise ValueError(
                f"un circuito va entre 2 y 4 resistencias para que se entienda en el celular, y dice {len(self.resistencias)}"
            )
        return self

    @property
    def segundos(self) -> float:
        """Lo que el dibujo suma a la duración estimada: la curva se mira un rato más."""
        return SEGUNDOS_VISUAL[self.tipo]

    def funcion_analizada(self):
        """La función lista para trazar (raíces, vértice y rango). Sólo en los gráficos."""
        if self.tipo != "grafico_funcion":
            raise ValueError(f"«{self.tipo}» no tiene una función que analizar")
        return analizar_funcion(self.funcion or "", self.variable, self.rango, self.marcar)

    def proyectil(self):
        """El vuelo ya resuelto (tiempo, alcance y altura). Sólo en los proyectiles."""
        if self.tipo != "proyectil":
            raise ValueError(f"«{self.tipo}» no es un proyectil")
        return analizar_proyectil(self.velocidad or "", self.angulo or 0)

    def angulo_trig(self):
        """El ángulo resuelto en el círculo (seno, coseno, tangente y cuadrante)."""
        if self.tipo != "circulo_trig":
            raise ValueError(f"«{self.tipo}» no es un círculo trigonométrico")
        return analizar_angulo(self.angulo or 0)

    def solido(self):
        """El cuerpo ya resuelto (volumen y área). Sólo en los sólidos."""
        if self.tipo not in ("solido", "solido_3d"):
            raise ValueError(f"«{self.tipo}» no es un sólido")
        return analizar_solido(self.figura or "", self.lado, self.radio, self.altura)

    def vector_3d(self):
        """El vector del espacio ya resuelto (su sombra en el piso y su largo). Sólo en vector_3d."""
        if self.tipo != "vector_3d":
            raise ValueError(f"«{self.tipo}» no es un vector en el espacio")
        return analizar_vector_3d(self.componentes or [], self.unidad or "")

    def venn(self):
        """Las cuatro regiones del diagrama ya sumadas. Sólo en los venn."""
        if self.tipo != "venn":
            raise ValueError(f"«{self.tipo}» no es un diagrama de Venn")
        return analizar_venn(self.solo_a or 0, self.solo_b or 0, self.ambos or 0, self.fuera or 0)

    def recta(self):
        """El intervalo o rayo con su ventana de dibujo. Sólo en las rectas."""
        if self.tipo != "recta":
            raise ValueError(f"«{self.tipo}» no es una recta numérica")
        return analizar_recta(
            self.extremo_a or 0, self.extremo_b, self.incluye_a, self.incluye_b, self.derecha
        )

    def probabilidad(self):
        """El cociente de Laplace ya resuelto. Sólo en las probabilidades."""
        if self.tipo != "probabilidad":
            raise ValueError(f"«{self.tipo}» no es una probabilidad")
        return analizar_probabilidad(self.favorables or 0, self.totales or 0)

    def torta(self):
        """Las porciones con su fracción del total. Sólo en las tortas."""
        if self.tipo != "torta":
            raise ValueError(f"«{self.tipo}» no es una torta")
        return analizar_torta(self.categorias)

    def barras(self):
        """Las barras con su total y su valor más alto. Sólo en las barras."""
        if self.tipo != "barras":
            raise ValueError(f"«{self.tipo}» no son barras")
        return analizar_barras(self.categorias)

    def onda(self):
        """La onda con su frecuencia y velocidad si el guion dio el período."""
        if self.tipo != "onda":
            raise ValueError(f"«{self.tipo}» no es una onda")
        return analizar_onda(self.amplitud or "", self.longitud_onda or "", self.periodo)

    def energia(self):
        """La energía total repartida en sus tramos. Sólo en la barra de energía."""
        if self.tipo != "energia":
            raise ValueError(f"«{self.tipo}» no es una barra de energía")
        return analizar_energia(self.categorias)

    def optica(self):
        """La refracción resuelta (ángulo que sale o reflexión total). Sólo en óptica."""
        if self.tipo != "optica":
            raise ValueError(f"«{self.tipo}» no es una refracción")
        return analizar_optica(self.n1 or 1, self.n2 or 1, self.angulo_incidence or 0)

    def pendulo(self):
        """El péndulo con su período ya calculado."""
        if self.tipo != "pendulo":
            raise ValueError(f"«{self.tipo}» no es un péndulo")
        return analizar_pendulo(self.longitud or "", self.angulo or 0)

    def resorte(self):
        """La fuerza del resorte con la extensión ya pasada a metros."""
        if self.tipo != "resorte":
            raise ValueError(f"«{self.tipo}» no es un resorte")
        return analizar_resorte(self.constante or "", self.extension or "")

    def escala(self):
        """Cuántas piezas del original caben al agrandar el lado (cuadrados o cubos)."""
        if self.tipo != "escala":
            raise ValueError(f"«{self.tipo}» no es una escala")
        return analizar_escala(self.lado or "", self.factor or 2, self.dimension or 3)

    def polea(self):
        """La máquina de Atwood con su aceleración y su tensión."""
        if self.tipo != "polea":
            raise ValueError(f"«{self.tipo}» no es una polea")
        return analizar_polea(self.masa_a or "", self.masa_b or "")

    def tanque(self):
        """El tanque con su llenado (y su vaciado, si pierde)."""
        if self.tipo != "tanque":
            raise ValueError(f"«{self.tipo}» no es un tanque")
        return analizar_tanque(self.capacidad or "", self.entrada or "", self.salida)

    def viga(self):
        """La viga apoyada con sus reacciones y su momento máximo."""
        if self.tipo != "viga":
            raise ValueError(f"«{self.tipo}» no es una viga")
        return analizar_viga(self.longitud or "", self.carga or "", self.repartida)

    def cercha(self):
        """La cercha triangular con su inclinación y el esfuerzo del paño."""
        if self.tipo != "cercha":
            raise ValueError(f"«{self.tipo}» no es una cercha")
        return analizar_cercha(self.base or "", self.altura or "", self.carga or "")

    def bloques(self):
        """El lazo cerrado con su ganancia ya calculada."""
        if self.tipo != "bloques":
            raise ValueError(f"«{self.tipo}» no es un lazo de control")
        return analizar_bloques(self.adelante or "", self.retro or "", self.negativa)

    def engranaje(self):
        """La pareja de engranajes con la vuelta del eje lento."""
        if self.tipo != "engranaje":
            raise ValueError(f"«{self.tipo}» no es una pareja de engranajes")
        return analizar_engranajes(self.dientes_a or "", self.dientes_b or "", self.rpm or "")

    def mohr(self):
        """El círculo de Mohr con su centro, su radio y sus esfuerzos principales."""
        if self.tipo != "mohr":
            raise ValueError(f"«{self.tipo}» no es un círculo de Mohr")
        return analizar_mohr(self.sigma_x or "", self.sigma_y or "", self.cortante or "")

    def oscilador(self):
        """La curva del resorte con su amortiguador, ya integrada con SciPy."""
        if self.tipo != "oscilador":
            raise ValueError(f"«{self.tipo}» no es un oscilador amortiguado")
        return analizar_oscilador(
            self.masa or "",
            self.constante or "",
            self.amplitud or "",
            self.amortiguamiento or "",
            self.duracion,
        )

    def pendulo_doble(self):
        """Los brazos y la traza del péndulo doble, ya integrados con SciPy."""
        if self.tipo != "pendulo_doble":
            raise ValueError(f"«{self.tipo}» no es un péndulo doble")
        return analizar_pendulo_doble(
            self.masa_1 or "",
            self.masa_2 or "",
            self.longitud_1 or "",
            self.longitud_2 or "",
            self.angulo_1 or 0.0,
            self.angulo_2 or 0.0,
            self.duracion,
        )

    def poligono(self):
        """El polígono regular ya resuelto (apotema, radio y ángulos). Sólo en los polígonos."""
        if self.tipo != "poligono_regular":
            raise ValueError(f"«{self.tipo}» no es un polígono")
        return analizar_poligono(self.lados or 0, self.lado)


class MapaColor(_Base):
    """Une un término de la fórmula con su concepto mediante un color (gramática XCris)."""

    termino: str = Field(min_length=1)
    concepto: str = Field(min_length=1)
    color: str | None = None

    _hex = field_validator("color")(classmethod(lambda cls, v: _validar_hex(v) if v is not None else None))


class Paso(_Base):
    voz: str = Field(min_length=1)
    tex: str | None = None
    nota: str | None = None
    destacar: list[str] = []
    transformar: bool = True
    emoji: str | None = None
    visual: Visual | None = None
    # Error típico: la fórmula (equivocada) se tacha con una ✗ roja; no cuenta como paso correcto
    error: bool = False
    # Álgebra viva (opcional): un resplandor sobre términos que se siguen paso a paso, y el cambio
    # de la transformación a la vista (lo que se va se tacha, lo que llega se ilumina)
    halo: list[str] = []
    resaltar_cambio: StrictBool = False
    # Gramática XCris (opcional): cada término de la fórmula se une a su concepto con un color
    mapa: list[MapaColor] = []

    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))
    _lista = field_validator("destacar", "halo", mode="before")(classmethod(lambda cls, v: _como_lista(v)))
    _pausas = field_validator("voz")(classmethod(lambda cls, v: validar_pausas(v)))

    @model_validator(mode="after")
    def _error_con_formula(self) -> Paso:
        if self.error and not self.tex:
            raise ValueError("un paso con «error: true» necesita la fórmula equivocada en «tex»")
        return self

    @model_validator(mode="after")
    def _algebra_coherente(self) -> Paso:
        """El halo y el cambio solo valen sobre una fórmula que exista: nada de términos inventados."""
        if (self.halo or self.resaltar_cambio) and not self.tex:
            raise ValueError("halo y resaltar_cambio iluminan la fórmula: este paso necesita «tex»")
        if self.resaltar_cambio and self.error:
            raise ValueError(
                "resaltar_cambio no va en un paso con «error: true»: el error se tacha entero, no se transforma"
            )
        formula = _ESPACIOS_TEX.sub("", self.tex or "")
        for termino in self.halo:
            if _ESPACIOS_TEX.sub("", termino) not in formula:
                raise ValueError(
                    f"el halo «{termino}» no aparece en la fórmula del paso ({self.tex}): copia el término tal cual"
                )
        return self

    @model_validator(mode="after")
    def _mapa_coherente(self) -> Paso:
        if self.mapa and not self.tex:
            raise ValueError("el mapa de color ilumina la fórmula: este paso necesita «tex»")
        formula = _ESPACIOS_TEX.sub("", self.tex or "")
        for m in self.mapa:
            termino = _ESPACIOS_TEX.sub("", m.termino)
            if not termino:
                raise ValueError("el término del mapa debe contener algo más que espacios de LaTeX")
            if termino not in formula:
                raise ValueError(
                    f"el término «{m.termino}» del mapa no aparece en la fórmula del paso ({self.tex})"
                )
        return self


class Resultado(_Base):
    # La fórmula final. Vacía solo cuando el contenido no es un ejercicio (ver Guion._resultado_visible).
    tex: str = ""
    # La conclusión en palabras, para un dato, mito o error que no termina en una fórmula (opcional).
    texto: str | None = None
    voz: str = Field(min_length=1)
    emoji: str | None = None
    destello: StrictBool = False  # un destello de confirmación sale del recuadro al cerrar la respuesta

    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))
    _pausas = field_validator("voz")(classmethod(lambda cls, v: validar_pausas(v)))
    _texto = field_validator("texto")(classmethod(lambda cls, v: v or None))  # «» = sin conclusión


INTENCIONES: dict[str, str] = {
    "dato": "Dato",
    "mito": "Mito",
    "error": "Error",
    "ejercicio": "Ejercicio",
}


class Contenido(_Base):
    """Qué enseña el video: la intención educativa (dato, mito, error, ejercicio) y su objetivo.

    No es el molde (cómo se cuenta) ni el estilo (cómo se ve). Opcional: sin él, el guion es un ejercicio.
    """

    intenciones: list[Literal["dato", "mito", "error", "ejercicio"]] = Field(min_length=1, max_length=4)
    objetivo: str = Field(min_length=1, max_length=260)

    @field_validator("intenciones")
    @classmethod
    def _sin_repetir(cls, valor: list[str]) -> list[str]:
        if len(valor) != len(set(valor)):
            raise ValueError("No repitas intenciones del contenido.")
        return valor

    @field_validator("objetivo")
    @classmethod
    def _objetivo_con_texto(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("El objetivo necesita texto.")
        return valor


class RecursosDidacticos(_Base):
    """Las herramientas de la explicación, por guion: true activa, false apaga, sin valor = sugerido."""

    tabs: StrictBool | None = None
    panel: StrictBool | None = None
    mapa_color: StrictBool | None = None
    micro: StrictBool | None = None


class Metadatos(_Base):
    """Lo que acompaña al video al publicarlo: título con gancho, descripción y hashtags.

    Opcional. Si viene en el guion, el kit de publicación lo usa tal cual sin llamar a la IA.
    """

    titulo: str = Field(min_length=1, max_length=100)  # YouTube corta a los 100 caracteres
    descripcion: str = Field(min_length=1, max_length=2200)  # el máximo de Instagram y TikTok
    hashtags: list[str] = Field(min_length=3, max_length=15)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags_limpios(cls, valor: Any) -> Any:
        """«#Física», «fisica» y «# fisica» quedan como «#fisica»; repetidos, una vez."""
        if isinstance(valor, str):
            valor = valor.replace(",", " ").split()
        if not isinstance(valor, list):
            return valor
        limpios: list[str] = []
        for crudo in valor:
            etiqueta = sin_tildes(str(crudo)).lower().replace(" ", "").lstrip("#")
            if not re.fullmatch(r"[a-z0-9_ñ]+", etiqueta):
                raise ValueError(
                    f"«{crudo}» no sirve como hashtag: solo letras y números, sin espacios ni signos (ej. #fisica)"
                )
            if f"#{etiqueta}" not in limpios:
                limpios.append(f"#{etiqueta}")
        return limpios

    @field_validator("titulo", "descripcion")
    @classmethod
    def _sin_hashtags_en_el_texto(cls, valor: str) -> str:
        if re.search(r"(^|\s)#\w", valor):
            raise ValueError("los hashtags van en «hashtags», no dentro del título ni de la descripción")
        return valor


class Guion(_Base):
    titulo: str = Field(min_length=1)
    materia: Literal["matematica", "fisica", "ingenieria"]
    nivel: str | None = None
    # Para la universidad: la carrera de la malla (ver niveles.py). Opcional, también en Ingeniería.
    carrera: Literal["industrial", "electrica", "obras_civiles"] | None = None
    molde: str | None = None  # estructura narrativa (ver moldes.py); opcional
    tema: str | None = None  # estilo visual de este video (ver ./tpi temas)
    camara: Literal["quieta", "suave", "fuerte"] = "suave"  # cuánto se acerca la cámara en los pasos
    voz: str | None = None
    velocidad: str | None = None
    gancho: Gancho
    gancho_variantes: list[Gancho] = []  # alternativas al gancho elegido; no lo repiten
    enunciado: Enunciado
    datos: list[Dato] = []
    pasos: list[Paso] = Field(min_length=1)
    resultado: Resultado
    verificacion: Bloque | None = None
    reto: Bloque | None = None
    cierre: Bloque | None = None
    # El llamado a la acción del TEXTO de la publicación (no se dice en el video): «¿Tú también lo
    # creías? Cuéntame 👇». Vacío = el de siempre del kit.
    llamado: str | None = Field(default=None, max_length=150)
    metadatos: Metadatos | None = None  # título, descripción y hashtags para publicar (opcional)
    # Qué enseña (dato, mito, error, ejercicio) y con qué herramientas; los dos opcionales.
    contenido: Contenido | None = None
    recursos: RecursosDidacticos | None = None

    @model_validator(mode="after")
    def _resultado_visible(self) -> Guion:
        """Un ejercicio cierra con su fórmula; un dato, mito o error puede cerrar con una conclusión."""
        intenciones = self.contenido.intenciones if self.contenido else ["ejercicio"]
        if "ejercicio" in intenciones and not self.resultado.tex.strip():
            raise ValueError("Un ejercicio necesita la fórmula final en resultado.tex.")
        if not (self.resultado.tex.strip() or (self.resultado.texto or "").strip()):
            raise ValueError("El resultado necesita una fórmula o una conclusión visible.")
        return self

    @field_validator("materia", mode="before")
    @classmethod
    def _normalizar_materia(cls, valor: Any) -> Any:
        if not isinstance(valor, str):
            return valor
        limpio = sin_tildes(valor).strip().lower()
        return limpio[:-1] if limpio.endswith("s") else limpio  # "matemáticas" → "matematica"

    @field_validator("carrera", mode="before")
    @classmethod
    def _normalizar_carrera(cls, valor: Any) -> Any:
        """«Eléctrica», «obras civiles» o «Ing. Civil Industrial» quedan como su clave."""
        if valor in (None, ""):
            return None
        limpio = sin_tildes(str(valor)).strip().lower()
        for clave, pista in (
            ("obras_civiles", "obras"),
            ("electrica", "electric"),
            ("industrial", "industrial"),
        ):
            if pista in limpio:
                return clave
        raise ValueError(
            f"«{valor}» no es una carrera de la malla; usa industrial, electrica u obras_civiles"
        )

    @field_validator("molde", mode="before")
    @classmethod
    def _normalizar_molde(cls, valor: Any) -> Any:
        if valor in (None, ""):
            return None
        clave = normalizar_molde(str(valor))
        if not clave:
            raise ValueError(
                f"«{valor}» no es un molde conocido; usa {opciones_de_moldes()} o quita el campo"
            )
        return clave

    @field_validator("velocidad")
    @classmethod
    def _validar_velocidad(cls, valor: str | None) -> str | None:
        if valor is not None and not re.fullmatch(r"[+-]\d{1,3}%", valor):
            raise ValueError("usa un porcentaje con signo, por ejemplo '+5%' o '-10%'")
        return valor

    @property
    def etiqueta_materia(self) -> str:
        return MATERIAS[self.materia]

    @model_validator(mode="before")
    @classmethod
    def _revisar_categoria(cls, datos: Any) -> Any:
        """``categoria:`` es opcional en el YAML: si viene, debe calzar con ``materia`` y luego se descarta.

        Así nunca se desincroniza (el editor, ``model_copy`` y la IA solo cambian la materia).
        """
        if not isinstance(datos, dict) or "categoria" not in datos:
            return datos
        datos = dict(datos)
        escrita = datos.pop("categoria")
        if escrita in (None, ""):
            return datos
        materia = sin_tildes(str(datos.get("materia") or "")).strip().lower()
        materia = materia[:-1] if materia.endswith("s") else materia
        esperada = CATEGORIA_DE_MATERIA.get(materia)
        limpia = sin_tildes(str(escrita)).strip().lower()
        limpia = {"matematica": "matematicas"}.get(limpia, limpia)
        if limpia not in CATEGORIA_DE_MATERIA.values():
            raise ValueError(f"categoria «{escrita}» no existe; usa matematicas, fisica o ingenieria")
        if esperada is not None and limpia != esperada:
            raise ValueError(
                f"categoria «{escrita}» no calza con materia «{datos.get('materia')}» "
                f"(le toca «{esperada}»): cambia la materia o quita la línea categoria"
            )
        return datos

    @property
    def categoria(self) -> Categoria:
        """La categoría del guion (decide su estilo visual). Sale siempre de ``materia``."""
        return CATEGORIA_DE_MATERIA[self.materia]

    def textos_de_voz(self, cierre_por_defecto: str) -> list[tuple[str, str]]:
        """Todos los textos que se dirán, en orden, con el nombre de su sección."""
        voces = [("gancho", self.gancho.voz_final), ("enunciado", self.enunciado.voz_final)]
        voces += [(f"dato {i}", d.voz) for i, d in enumerate(self.datos, 1)]
        voces += [(f"paso {i}", p.voz) for i, p in enumerate(self.pasos, 1)]
        voces.append(("resultado", self.resultado.voz))
        if self.verificacion:
            voces.append(("verificación", self.verificacion.voz_final))
        if self.reto:
            voces.append(("reto", self.reto.voz_final))
        voces.append(("cierre", self.cierre.voz_final if self.cierre else cierre_por_defecto))
        return voces


# ---------------------------------------------------------------------------------------------
# Lectura con errores amigables
# ---------------------------------------------------------------------------------------------

_MENSAJES = {
    "missing": "falta este campo (es obligatorio)",
    "extra_forbidden": "este campo no existe: ¿quizás un error de tipeo?",
    "string_type": "debe ser un texto",
    "list_type": "debe ser una lista (cada elemento empieza con '- ')",
    "bool_type": "debe ser true o false",
    "bool_parsing": "debe ser true o false",
    "float_parsing": "debe ser un número (los decimales llevan punto: 4.9)",
    "float_type": "debe ser un número (los decimales llevan punto: 4.9)",
    "too_short": "no puede quedar vacío",
    "string_too_short": "no puede quedar vacío",
    "model_type": "debe tener sub-campos (por ejemplo texto: y voz:)",
    "model_attributes_type": "debe tener sub-campos (por ejemplo texto: y voz:)",
}


def emojis_del_guion(guion: Guion) -> list[tuple[str, str]]:
    """(sección, valor) de cada emoji usado en el guion."""
    usados = [("gancho", guion.gancho.emoji)]
    usados += [(f"paso {i}", p.emoji) for i, p in enumerate(guion.pasos, 1)]
    usados.append(("resultado", guion.resultado.emoji))
    for nombre in ("verificacion", "reto", "cierre"):
        bloque = getattr(guion, nombre)
        if bloque is not None:
            usados.append((nombre, bloque.emoji))
    return [(donde, valor) for donde, valor in usados if valor]


def _hay_correcto_despues(pasos: list[Paso], desde: int) -> bool:
    return any(not p.error for p in pasos[desde + 1 :])


def problemas_de_molde(guion: Guion) -> list[str]:
    """Las reglas objetivas del molde: avisos corregibles, nunca un bloqueo del render."""
    if not guion.molde:
        return []
    molde = MOLDES.get(guion.molde)
    if molde is None:
        return [f"«{guion.molde}» no es un molde conocido; usa {opciones_de_moldes()}."]
    errores = [i for i, p in enumerate(guion.pasos) if p.error]
    if molde.regla == "un_error":
        if not errores:
            return [f"«{molde.nombre}» necesita al menos un paso con «error: true»."]
        if not _hay_correcto_despues(guion.pasos, errores[0]):
            return [f"«{molde.nombre}» necesita un paso correcto después del error."]
    elif molde.regla == "tres_errores":
        if len(errores) != 3:
            return [
                f"«{molde.nombre}» necesita exactamente 3 pasos con «error: true» y este guion tiene "
                f"{len(errores)}."
            ]
        if not _hay_correcto_despues(guion.pasos, errores[-1]):
            return [f"«{molde.nombre}» necesita un paso correcto después de los 3 errores."]
    elif molde.regla == "reto" and guion.reto is None:
        return [f"«{molde.nombre}» necesita el bloque «reto:» al final."]
    elif molde.regla == "verificacion" and guion.verificacion is None:
        return [f"«{molde.nombre}» necesita el bloque «verificacion:»."]
    return []


def _ubicacion(loc: tuple[Any, ...]) -> str:
    partes: list[str] = []
    for item in loc:
        if isinstance(item, int):
            partes.append(f"#{item + 1}")
        elif not str(item).startswith("function-"):  # nombres internos de validadores
            partes.append(str(item))
    return " → ".join(partes) or "(raíz)"


def _opciones_es(opciones: list[str]) -> str:
    """['a', 'b'] → «a o b» (en español la lista se cierra con «o», no con «or»)."""
    if len(opciones) <= 1:
        return opciones[0] if opciones else "revisa los ejemplos de guiones/"
    return ", ".join(opciones[:-1]) + " o " + opciones[-1]


def explicar_errores(error: ValidationError) -> list[str]:
    lineas = []
    for err in error.errors():
        tipo = err.get("type", "")
        if tipo == "value_error":
            mensaje = str(err.get("msg", "")).removeprefix("Value error, ")
        elif tipo == "literal_error":
            # pydantic entrega las opciones en inglés: "'a', 'b' or 'c'"
            opciones = re.findall(r"'([^']*)'", str(err.get("ctx", {}).get("expected", "")))
            mensaje = f"valor no válido; las opciones son: {_opciones_es(opciones)}"
        else:
            mensaje = _MENSAJES.get(tipo, err.get("msg", "valor no válido"))
        lineas.append(f"{_ubicacion(err.get('loc', ()))}: {mensaje}")
    return lineas


def cargar_guion(ruta: str | Path) -> Guion:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorMotor(
            f"No encuentro el guion «{ruta}».",
            ayuda="Revisa la ruta. Ejemplo: ./tpi crear guiones/ejemplos/fisica_caida_libre.yaml",
        )
    crudo = ruta.read_text(encoding="utf-8")
    try:
        datos = yaml.safe_load(crudo)
    except yaml.YAMLError as e:
        ayuda = "Revisa la sangría (2 espacios, sin tabulaciones) y pon entre comillas los textos con ':'."
        if "escape" in str(e):
            ayuda = "Escribe las fórmulas LaTeX entre comillas simples: tex: '\\frac{1}{2}'"
        if any(q in crudo for q in "“”‘’"):
            ayuda += (
                " Además, el archivo tiene comillas curvas (“ ”): si usas TextEdit, desactiva "
                "Edición → Sustituciones → Comillas inteligentes."
            )
        marca = getattr(e, "problem_mark", None)
        donde = f" (línea {marca.line + 1})" if marca else ""
        raise ErrorMotor(f"El archivo {ruta.name} tiene un error de formato YAML{donde}.", ayuda=ayuda) from e
    if not isinstance(datos, dict):
        raise ErrorMotor(f"{ruta.name} no parece un guion: debería empezar con 'titulo:'.")
    try:
        return Guion.model_validate(datos)
    except ValidationError as e:
        detalle = "\n".join(f"  • {linea}" for linea in explicar_errores(e))
        raise ErrorMotor(
            f"El guion {ruta.name} tiene problemas:\n{detalle}",
            ayuda="Compara con guiones/ejemplos/ o con docs/GUIA_GUIONES.md",
        ) from e


_LINEA_TEMA = re.compile(r"^tema:[^\n]*(?:\n|$)", re.MULTILINE)
_ANCLA_TEMA = re.compile(r"^(?:categoria|materia):[^\n]*(?:\n|$)", re.MULTILINE)


def fijar_tema(ruta: str | Path, clave: str | None) -> Guion:
    """Escribe (o borra, con ``None``) la línea ``tema:`` del guion, sin tocar nada más del archivo.

    Los comentarios, el orden y las comillas quedan como estaban. Si el guion resultante no valida,
    el archivo queda exactamente como antes y se avisa.
    """
    ruta = Path(ruta)
    original = ruta.read_text(encoding="utf-8")
    if clave is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", clave):
        raise ErrorMotor(f"«{clave}» no es un nombre de estilo válido.")
    texto = _LINEA_TEMA.sub("", original)
    if clave:
        anclas = list(_ANCLA_TEMA.finditer(texto))
        fin = anclas[-1].end() if anclas else 0
        salto = "" if fin == 0 or texto[fin - 1] == "\n" else "\n"
        texto = f"{texto[:fin]}{salto}tema: {clave}\n{texto[fin:]}"
    if texto == original:
        return cargar_guion(ruta)
    from .entorno import escribir_atomico

    escribir_atomico(ruta, texto)
    try:
        return cargar_guion(ruta)
    except ErrorMotor:
        escribir_atomico(ruta, original)
        raise


# ---------------------------------------------------------------------------------------------
# Escritura (el inverso de cargar_guion): textos con "…", fórmulas con '…', como en los ejemplos
# ---------------------------------------------------------------------------------------------


def _dobles(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _simples(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _numero(valor: Any) -> str:
    """30.0 → «30», 2.5 → «2.5»: como se escribe un número en un guion a mano."""
    n = round(float(valor), 4)
    return str(n).removesuffix(".0")


def _numeros(vals: list[Any]) -> str:
    """[0, 5] con la coma como separador YAML y punto decimal (el que lee el motor)."""
    return "[" + ", ".join(_numero(v) for v in vals) + "]"


def _visual_yaml(v: dict[str, Any], sangria: str = "      ") -> list[str]:
    """Los campos del visual que corresponden a su tipo, con la sangría del bloque que lo lleva."""
    tipo = v["tipo"]
    campos: list[tuple[str, str]] = [("tipo", tipo)]
    if tipo == "grafico_funcion":
        campos.append(("funcion", _simples(v.get("funcion") or "")))
        if v.get("variable"):
            campos.append(("variable", _dobles(v["variable"])))
        if v.get("rango"):
            campos.append(("rango", _numeros(v["rango"])))
        if v.get("marcar"):
            campos.append(("marcar", _numeros(v["marcar"])))
        for clave in ("eje_x", "eje_y"):
            if v.get(clave):
                campos.append((clave, _dobles(v[clave])))
        if v.get("movimiento"):
            campos.append(("movimiento", v["movimiento"]))
            for clave in ("desde", "hasta"):
                if v.get(clave) is not None:
                    campos.append((clave, _numero(v[clave])))
            if v.get("anotar"):
                campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "diagrama_fuerzas":
        if v.get("cuerpo") not in (None, "bloque"):
            campos.append(("cuerpo", v["cuerpo"]))
        campos.append(("vectores", "[" + ", ".join(_simples(x) for x in v.get("vectores") or []) + "]"))
        if v.get("angulo") is not None:
            campos.append(("angulo", _numero(v["angulo"])))
        if v.get("descomponer"):
            campos.append(("descomponer", "true"))
    elif tipo == "proyectil":
        campos.append(("velocidad", _simples(v.get("velocidad") or "")))
        campos.append(("angulo", _numero(v.get("angulo") or 0)))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "circulo_trig":
        campos.append(("angulo", _numero(v.get("angulo") or 0)))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo in ("solido", "solido_3d"):
        campos.append(("figura", v.get("figura") or ""))
        for clave in ("lado", "radio", "altura"):
            if v.get(clave):
                campos.append((clave, _simples(v[clave])))
        if tipo == "solido_3d":
            campos.append(("vista", v.get("vista") or "axonometrica"))
            if v.get("corte") not in (None, "", "sin_corte"):
                campos.append(("corte", v["corte"]))
            if v.get("despiece"):
                campos.append(("despiece", "true"))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "vector_3d":
        campos.append(("componentes", _numeros(v.get("componentes") or [])))
        if v.get("unidad"):
            campos.append(("unidad", _simples(v["unidad"])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "venn":
        for clave in ("solo_a", "solo_b", "ambos"):
            campos.append((clave, _numero(v.get(clave) or 0)))
        if v.get("fuera"):
            campos.append(("fuera", _numero(v["fuera"])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "recta":
        campos.append(("extremo_a", _numero(v.get("extremo_a") or 0)))
        if v.get("extremo_b") is not None:
            campos.append(("extremo_b", _numero(v["extremo_b"])))
        for clave in ("incluye_a", "incluye_b", "derecha"):
            if v.get(clave) is False:
                campos.append((clave, "false"))
    elif tipo == "probabilidad":
        campos.append(("favorables", _numero(v.get("favorables") or 0)))
        campos.append(("totales", _numero(v.get("totales") or 0)))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "poligono_regular":
        campos.append(("lados", _numero(v.get("lados") or 0)))
        campos.append(("lado", _simples(v.get("lado") or "")))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo in ("torta", "barras", "energia"):
        campos.append(("categorias", "[" + ", ".join(_simples(c) for c in v.get("categorias") or []) + "]"))
    elif tipo == "onda":
        campos.append(("amplitud", _simples(v.get("amplitud") or "")))
        campos.append(("longitud_onda", _simples(v.get("longitud_onda") or "")))
        if v.get("periodo") is not None:
            campos.append(("periodo", _numero(v["periodo"])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "optica":
        for clave in ("n1", "n2", "angulo_incidence"):
            campos.append((clave, _numero(v.get(clave) or 0)))
    elif tipo == "pendulo":
        campos.append(("longitud", _simples(v.get("longitud") or "")))
        campos.append(("angulo", _numero(v.get("angulo") or 0)))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "resorte":
        campos.append(("constante", _simples(v.get("constante") or "")))
        campos.append(("extension", _simples(v.get("extension") or "")))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "escala":
        campos.append(("lado", _simples(v.get("lado") or "")))
        campos.append(("factor", str(int(v.get("factor") or 2))))
        campos.append(("dimension", str(int(v.get("dimension") or 3))))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "polea":
        campos.append(("masa_a", _simples(v.get("masa_a") or "")))
        campos.append(("masa_b", _simples(v.get("masa_b") or "")))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "tanque":
        campos.append(("capacidad", _simples(v.get("capacidad") or "")))
        campos.append(("entrada", _simples(v.get("entrada") or "")))
        if v.get("salida"):
            campos.append(("salida", _simples(v["salida"])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "viga":
        campos.append(("longitud", _simples(v.get("longitud") or "")))
        campos.append(("carga", _simples(v.get("carga") or "")))
        if v.get("repartida"):
            campos.append(("repartida", "true"))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "cercha":
        campos.append(("base", _simples(v.get("base") or "")))
        campos.append(("altura", _simples(v.get("altura") or "")))
        campos.append(("carga", _simples(v.get("carga") or "")))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "bloques":
        campos.append(("adelante", _simples(str(v.get("adelante") or ""))))
        campos.append(("retro", _simples(str(v.get("retro") or ""))))
        if v.get("negativa") is False:
            campos.append(("negativa", "false"))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "engranaje":
        campos.append(("dientes_a", _simples(str(v.get("dientes_a") or ""))))
        campos.append(("dientes_b", _simples(str(v.get("dientes_b") or ""))))
        campos.append(("rpm", _simples(v.get("rpm") or "")))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "mohr":
        for clave in ("sigma_x", "sigma_y", "cortante"):
            campos.append((clave, _simples(v.get(clave) or "")))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "oscilador":
        for clave in ("masa", "constante", "amplitud"):
            campos.append((clave, _simples(v.get(clave) or "")))
        if v.get("amortiguamiento"):
            campos.append(("amortiguamiento", _simples(v["amortiguamiento"])))
        if v.get("duracion") is not None:
            campos.append(("duracion", _numero(v["duracion"])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "pendulo_doble":
        for clave in ("masa_1", "masa_2", "longitud_1", "longitud_2"):
            campos.append((clave, _simples(v.get(clave) or "")))
        for clave in ("angulo_1", "angulo_2"):
            if v.get(clave) is not None:
                campos.append((clave, _numero(v[clave])))
        if v.get("duracion") is not None:
            campos.append(("duracion", _numero(v["duracion"])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo in ("tolva_3d", "tuberia_3d", "eje_3d"):
        claves = {
            "tolva_3d": ("radio", "altura", "radio_salida", "altura_cono"),
            "tuberia_3d": ("radio", "espesor", "longitud"),
            "eje_3d": (),
        }[tipo]
        for clave in claves:
            campos.append((clave, _simples(v.get(clave) or "")))
        if tipo == "tuberia_3d" and v.get("bridas") is False:
            campos.append(("bridas", "false"))
        if tipo == "eje_3d":
            campos.append(("radios", _numeros(v.get("radios") or [])))
            campos.append(("largos", _numeros(v.get("largos") or [])))
            if v.get("unidad"):
                campos.append(("unidad", _simples(v["unidad"])))
        if v.get("vista") not in (None, "", "axonometrica"):
            campos.append(("vista", v["vista"]))
        if v.get("despiece"):
            campos.append(("despiece", "true"))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "gradiente_termico":
        for clave in ("temp_izquierda", "temp_derecha", "temp_arriba", "temp_abajo"):
            campos.append((clave, _numero(v.get(clave) or 0)))
        for clave in ("base", "altura"):
            if v.get(clave):
                campos.append((clave, _simples(v[clave])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "perfil_flujo":
        campos.append(("flujo", v.get("flujo") or ""))
        for clave in ("velocidad", "separacion"):
            campos.append((clave, _simples(v.get(clave) or "")))
        if v.get("viscosidad"):
            campos.append(("viscosidad", _simples(v["viscosidad"])))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    else:
        if v.get("arreglo") not in (None, "serie"):
            campos.append(("arreglo", v["arreglo"]))
        campos.append(("fuente", _simples(v.get("fuente") or "")))
        campos.append(
            ("resistencias", "[" + ", ".join(_simples(r) for r in v.get("resistencias") or []) + "]")
        )
    if v.get("tamano") not in (None, "", "auto"):
        campos.append(("tamano", v["tamano"]))
    return [f"{sangria}{clave}: {valor}" for clave, valor in campos]


def a_yaml(guion: dict[str, Any], cabecera: list[str] | None = None) -> str:
    """Escribe un guion (dict con la forma de ``Guion``) como YAML legible. Omite lo que está por defecto."""
    # Un salto de línea dentro de un comentario rompería el YAML
    cabecera = [c.replace("\r", " ").replace("\n", " ") for c in (cabecera or [])]
    lineas = [f"# {c}" if c else "#" for c in cabecera] + ([""] if cabecera else [])
    lineas.append(f"titulo: {_dobles(guion['titulo'])}")
    lineas.append(f"materia: {guion['materia']}")
    materia = sin_tildes(str(guion["materia"])).strip().lower()
    if categoria := CATEGORIA_DE_MATERIA.get(materia[:-1] if materia.endswith("s") else materia):
        lineas.append(f"categoria: {categoria}  # sale de la materia; elige el estilo si no hay «tema»")
    if guion.get("nivel"):
        lineas.append(f"nivel: {_dobles(guion['nivel'])}")
    if guion.get("carrera"):
        lineas.append(f"carrera: {guion['carrera']}")
    if guion.get("molde"):
        lineas.append(f"molde: {guion['molde']}")
    if guion.get("camara") not in (None, "suave"):
        lineas.append(f"camara: {guion['camara']}")
    for clave in ("tema", "voz", "velocidad"):
        if guion.get(clave):
            lineas.append(f"{clave}: {_dobles(guion[clave])}")
    # Qué enseña y con qué herramientas: solo si vienen. En recursos se omite lo vacío (= sugerido),
    # nunca un false (= apagado a propósito).
    if contenido := guion.get("contenido"):
        objetivo = " ".join(str(contenido["objetivo"]).split())
        lineas += [
            "",
            "contenido:",
            f"  intenciones: [{', '.join(contenido['intenciones'])}]",
            f"  objetivo: {_dobles(objetivo)}",
        ]
    recursos = {k: v for k, v in (guion.get("recursos") or {}).items() if v is not None}
    if recursos:
        lineas += ["", "recursos:"]
        lineas += [f"  {clave}: {'true' if valor else 'false'}" for clave, valor in recursos.items()]

    def bloque(nombre: str, b: dict[str, Any]) -> None:
        lineas.extend(["", f"{nombre}:", f"  texto: {_dobles(b['texto'])}"])
        if b.get("voz"):
            lineas.append(f"  voz: {_dobles(b['voz'])}")
        if b.get("destacar"):
            lineas.append(f"  destacar: [{', '.join(_dobles(d) for d in b['destacar'])}]")
        if b.get("tex"):
            lineas.append(f"  tex: {_simples(b['tex'])}")
        if b.get("emoji"):
            lineas.append(f"  emoji: {_dobles(b['emoji'])}")
        if b.get("visual"):
            lineas.append("  visual:")
            lineas.extend(_visual_yaml(b["visual"], "    "))
        # El rótulo de la tarjeta del enunciado: solo si no es el de fábrica, para no ensuciar los
        # guiones de siempre. Sin esto, reescribir el guion lo devolvía a «PROBLEMA».
        etiqueta = str(b.get("etiqueta") or "").strip()
        if etiqueta and etiqueta != "PROBLEMA":
            lineas.append(f"  etiqueta: {_dobles(etiqueta)}")

    bloque("gancho", guion["gancho"])
    if guion.get("gancho_variantes"):
        lineas += ["", "gancho_variantes:"]
        for v in guion["gancho_variantes"]:
            lineas.append(f"  - texto: {_dobles(v['texto'])}")
            for clave in ("voz", "emoji"):
                if v.get(clave):
                    lineas.append(f"    {clave}: {_dobles(v[clave])}")
            if v.get("tex"):
                lineas.append(f"    tex: {_simples(v['tex'])}")
            if v.get("destacar"):
                lineas.append(f"    destacar: [{', '.join(_dobles(d) for d in v['destacar'])}]")
            if v.get("visual"):
                lineas.append("    visual:")
                lineas.extend(_visual_yaml(v["visual"], "      "))
    bloque("enunciado", guion["enunciado"])
    if guion.get("datos"):
        lineas += ["", "datos:"]
        for d in guion["datos"]:
            lineas += [f"  - tex: {_simples(d['tex'])}", f"    voz: {_dobles(d['voz'])}"]
    lineas += ["", "pasos:"]
    for p in guion["pasos"]:
        primero = True
        for clave in ("nota", "tex", "voz"):
            if p.get(clave):
                valor = _simples(p[clave]) if clave == "tex" else _dobles(p[clave])
                lineas.append(f"  {'- ' if primero else '  '}{clave}: {valor}")
                primero = False
        if p.get("destacar"):
            lineas.append(f"    destacar: [{', '.join(_simples(d) for d in p['destacar'])}]")
        if p.get("transformar") is False:
            lineas.append("    transformar: false")
        if p.get("halo"):
            lineas.append(f"    halo: [{', '.join(_simples(d) for d in p['halo'])}]")
        if p.get("resaltar_cambio"):
            lineas.append("    resaltar_cambio: true")
        if p.get("emoji"):
            lineas.append(f"    emoji: {_dobles(p['emoji'])}")
        if p.get("mapa"):
            lineas.append("    mapa:")
            for m in p["mapa"]:
                termino = yaml.safe_dump(m["termino"], allow_unicode=True, default_style='"')
                termino = termino.strip().replace("\n", "\n        ")
                concepto = yaml.safe_dump(m["concepto"], allow_unicode=True, default_style='"')
                concepto = concepto.strip().replace("\n", "\n        ")
                lineas += [
                    f"      - termino: {termino}",
                    f"        concepto: {concepto}",
                ]
                if m.get("color"):
                    lineas.append(f"        color: {_dobles(m['color'])}")
        if p.get("visual"):
            lineas.append("    visual:")
            lineas += _visual_yaml(p["visual"])
        if p.get("error"):
            lineas.append("    error: true   # error típico: se muestra tachado")
    lineas += ["", "resultado:"]
    if str(guion["resultado"].get("tex") or "").strip():
        lineas.append(f"  tex: {_simples(guion['resultado']['tex'])}")
    if str(guion["resultado"].get("texto") or "").strip():
        lineas.append(f"  texto: {_dobles(guion['resultado']['texto'])}")
    lineas.append(f"  voz: {_dobles(guion['resultado']['voz'])}")
    if guion["resultado"].get("emoji"):
        lineas.append(f"  emoji: {_dobles(guion['resultado']['emoji'])}")
    if guion["resultado"].get("destello"):
        lineas.append("  destello: true")
    for nombre in ("verificacion", "reto", "cierre"):
        if guion.get(nombre):
            bloque(nombre, guion[nombre])
    if str(guion.get("llamado") or "").strip():
        llamado = _dobles(str(guion["llamado"]).strip())
        lineas += ["", f"llamado: {llamado}  # el cierre del texto de la publicación"]
    if guion.get("metadatos"):
        m = guion["metadatos"]
        lineas += [
            "",
            "metadatos:",
            f"  titulo: {_dobles(m['titulo'])}",
            f"  descripcion: {_dobles(m['descripcion']).replace(chr(10), chr(92) + 'n')}",
        ]
        lineas.append(f"  hashtags: [{', '.join(_dobles(h) for h in m.get('hashtags') or [])}]")
    return "\n".join(lineas) + "\n"


def cabecera_de(ruta: Path) -> list[str]:
    """Los comentarios del inicio de un guion (supuestos de la IA, etc.), para conservarlos al guardar."""
    cabecera: list[str] = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.startswith("#"):
            break
        cabecera.append(linea[2:] if linea.startswith("# ") else linea[1:])
    return cabecera
