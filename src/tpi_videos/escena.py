"""Escena principal de Manim: arma el video completo a partir del guion y del tema.

Estructura (pensada para retener en video corto y para aprender):
1. Gancho: pregunta o dato sorprendente en los primeros 3 segundos (con emoji y fórmula opcionales).
2. Enunciado: lo concreto antes que lo abstracto; se subraya cada dato cuando la voz lo dice.
3. Datos: lista breve que luego queda fija arriba como referencia.
4. Pasos: cada paso es una idea; los términos se mueven de una ecuación a la siguiente
   (``TransformMatchingTex``) para MOSTRAR el cambio en vez de solo narrarlo. Un paso "error típico"
   muestra la forma equivocada y la tacha con una ✗ roja.
5. Resultado destacado, verificación opcional ("¿tiene sentido?") y un reto final para
   practicar recordando (y generar comentarios).
6. Cierre con la marca y un solo llamado a la acción.

Las transiciones se hacen mientras la voz habla, para que no haya silencios muertos.
El tema (``temas.Tema``) decide el marco, los colores, las letras y si los títulos "aparecen" o se
escriben como con plumón.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    DOWN,
    HEAVY,
    LEFT,
    MEDIUM,
    PI,
    RIGHT,
    SEMIBOLD,
    TAU,
    ULTRABOLD,
    UP,
    UR,
    Animation,
    Circumscribe,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    Flash,
    Group,
    ImageMobject,
    Indicate,
    LaggedStart,
    Mobject,
    MovingCameraScene,
    Polygon,
    Rotate,
    RoundedRectangle,
    SurroundingRectangle,
    Transform,
    TransformMatchingTex,
    UpdateFromAlphaFunc,
    VGroup,
    VMobject,
    Wiggle,
    Write,
    config,
    rate_functions,
)
from manim_voiceover import VoiceoverScene
from manim_voiceover.helper import remove_bookmarks

from . import componentes as c
from . import dibujos as d
from .config import Marca
from .errores import ErrorMotor
from .guion import Bloque, Guion
from .pausas import sin_pausas
from .rodaje import rodaje_de_guion
from .revision import PISO_LECTURA, espera_de_lectura
from .voces import RESOLUCION, crear_servicio, precargar_voz


def dibuja_el_sticker(elegido: str | None, de_la_marca: bool, tema_emojis: bool) -> bool:
    """El logo de la marca va también en los temas sobrios; los stickers cómicos siguen apagados."""
    return bool(elegido) and (tema_emojis or de_la_marca)


# Cuánto acerca la cámara en cada paso y en el resultado (multiplica lo ya acercado).
# "base" es el encuadre al que vuelve antes de cada golpe: sin ese aire, el golpe no se nota.
ESCALAS: dict[str, dict[str, float]] = {
    "suave": {"paso": 0.97, "resultado": 0.94, "minima": 0.86, "base": 0.97},
    "fuerte": {"paso": 0.93, "resultado": 0.90, "minima": 0.78, "base": 0.93},
}


HOLGURA_ANCHO = 0.12  # aire entre lo dibujado y el borde del cuadro cuando la cámara se acerca

# El golpe: la cámara entra rápido, se pasa un poco del encuadre quieto y vuelve a él.
# El margen es lo que entra de más que el borde seguro: dura un instante, no se queda.
GOLPE = {"suave": 0.02, "fuerte": 0.045}
SOBREPASO_MAX = 6.0  # más que esto y el golpe deja de parecer una cámara y parece un error

# El primer plano de un término. El aire es el fondo que queda alrededor de lo destacado; la mínima
# es el freno: más adentro que eso una letra de 84 puntos ocupa todo el cuadro y deja de leerse.
AIRE_PRIMER_PLANO = 3.3
MINIMA_PRIMER_PLANO = 0.46

# El gancho que llena el cuadro («nadie te enseñó», POV): la pregunta sola, sin la marca arriba, y
# con letra un tercio más grande. El centro elegido deja arriba el aire donde todavía no hay cabecera
# y abajo, la banda de los subtítulos.
ESCALA_GANCHO_LLENO = 1.35
Y_GANCHO_LLENO = 2.3
ALTO_GANCHO_LLENO = 6.4  # el techo del bloque: desde aquí la letra cede antes que el encuadre

# Cámara en mano. La pausa del video no se congela: el cuadro se desliza despacio sobre su encuadre
# de reposo. El alcance es la separación máxima del reposo y la mínima, la pausa más corta que vale
# la pena mover (una más corta ni se vería).
ALCANCE_DERIVA = 0.34
PAUSA_MINIMA_DERIVA = 0.6
# El respiradero: una cámara sostenida también abre y cierra un poco. En la hoja el papel es casi del
# ancho del cuadro y el paneo no tiene adónde ir; el acercamiento es lo único que se ve siempre.
# Solo acerca (nunca descubre más fondo del que pidió la toma), así que el reposo sigue siendo el techo.
RESPIRO_DERIVA = 0.05


def deriva_desplazamiento(segundos: float) -> tuple[float, float, float]:
    """Cuánto se separa el cuadro de su reposo a los ``segundos`` acumulados de cámara en mano.

    Arranca en cero para que la primera pausa no parezca un salto, y usa periodos distintos por eje
    que no coinciden dentro de un video: el cuadro nunca vuelve al mismo punto en el mismo momento.
    El tercero es el respiradero, siempre entre 0 y ``RESPIRO_DERIVA``: la toma nunca se abre más de
    lo que pidió el golpe.
    """
    return (
        ALCANCE_DERIVA * math.sin(0.79 * segundos) * math.cos(0.21 * segundos),
        ALCANCE_DERIVA * 0.62 * math.sin(0.53 * segundos),
        RESPIRO_DERIVA * (0.5 - 0.5 * math.cos(0.41 * segundos)),
    )


def avance_de_movimiento(duracion: float, ventana: float) -> tuple[float, bool]:
    """Cuánto de la simulación cabe en la voz, y si hubo que cortarla.

    La física manda: el reloj de la simulación corre a su ritmo real y la escena no lo estira
    ni lo apura. Si la voz se queda corta, se ve el principio y se avisa en la revisión.
    """
    if duracion <= 0 or ventana >= duracion:
        return 1.0, False
    return max(ventana / duracion, 0.0), True


def movimiento_de(dibujo: d.Dibujo, avance: float) -> Animation:
    """La animación que recorre la pose del dibujo de 0 a ``avance`` sobre su propio grupo.

    El grupo del dibujo tiene que ser el objeto animado: así Manim lo vuelve a pintar en cada cuadro.
    """
    return UpdateFromAlphaFunc(dibujo.mobs, lambda _m, alfa: dibujo.vivo(alfa * avance))


def recorrido_sin_fisica(ventana: float) -> tuple[float, float]:
    """``(segundos, avance)`` de un recorrido sin reloj físico: ocupa la ventana entera y llega al final.

    Una tangente que barre la curva o una órbita de cámara no tienen velocidad «real» que mentir:
    se reparten en la voz del paso y siempre terminan en su pose final.
    """
    return max(ventana, 0.35), 1.0


def plan_de_movimiento(duracion: float, restante: float) -> tuple[float, float, float, bool]:
    """Reparte lo que queda de voz: un cuarto para que el dibujo entre y el resto para la física.

    Devuelve ``(entrada, ventana, avance, se_corta)``. ``entrada + ventana == restante``, así el
    paso nunca se pasa de la voz; cuando la física no cabe, ``avance`` dice dónde se corta.
    """
    entrada = max(restante * 0.25, 0.35)
    ventana = max(restante - entrada, 0.35)
    avance, se_corta = avance_de_movimiento(duracion, ventana)
    return entrada, ventana, avance, se_corta


# El tablero partido (``partida: mitades``): arriba el error con su rótulo MITO, abajo la forma
# correcta con REALIDAD. Ninguna de las dos se achica ni sube de sitio; cada línea se escribe en su
# casillero y la cámara se inclina hacia la que está hablando. El casillero es más angosto que la
# hoja entera a propósito: es lo único que le deja a la cámara papel libre para bajar de una mitad
# a la otra, y como además entra, la letra sale del mismo tamaño que en el plano general de siempre.
ANCHO_CASILLERO = 3.9

# Lo mínimo que el dibujo terminado queda a la vista antes del paso siguiente (s): el proyectil que
# cae, los cubos llenos o la traza del péndulo se tienen que poder mirar, no solo ver pasar.
PISO_DIBUJO = 2.0

# Los dibujos que son la prueba de la idea (no su ilustración): se trazan antes que la fórmula del paso.
DIBUJOS_QUE_DEMUESTRAN = frozenset({"escala"})
AIRE_CASILLERO = 0.5

# Los subtítulos se queman después, centrados en el 72 % del alto (y ≈ -1,76). Lo que se escribe
# en pantalla tiene que quedar por encima de esa banda o el subtítulo le pasa por encima.
Y_SOBRE_SUBTITULOS = -1.22


def banda_subtitulo() -> float:
    """El tramo de abajo que se lleva el subtítulo quemado, según el tema activo."""
    return c.estilo_activo().banda_subtitulo


def aire_dibujo() -> float:
    """El respiro entre el techo del dibujo y la línea más baja de los pasos, según el tema activo."""
    return c.estilo_activo().aire_dibujo


def __getattr__(nombre: str) -> float:
    # Los nombres de siempre (los tests los importan así) resuelven contra el tema activo.
    if nombre == "BANDA_SUBTITULO":
        return banda_subtitulo()
    if nombre == "AIRE_DIBUJO":
        return aire_dibujo()
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def franja_del_dibujo(
    paisaje: Paisaje,
    alto_cuadro: float,
    escala_reposo: float,
    fondo_papel: float,
    tope: float,
    techo: float | None = None,
    borde_papel: float | None = None,
) -> tuple[float, float, float]:
    """(piso de los pasos, centro del dibujo, alto del dibujo) en el plano de reposo.

    El dibujo se apoya en el filo de abajo que le deja el subtítulo quemado y llena la banda que
    le queda por arriba: sin tope de catálogo, porque recortaba el dibujo aunque sobrase hueco.
    Los pasos se detienen en la reserva de siempre, que es lo que mantiene grande la letra.

    ``techo`` es ese filo de arriba puesto a mano: en el gancho no hay pizarra de pasos que
    respetar, así que la banda sube hasta el piso de la pregunta en vez de hasta la reserva.
    ``borde_papel`` es el fondo real del papel (no la reserva de la zona): en la hoja cuadriculada
    la grilla sigue bajando bajo la zona de pasos, y ahí el dibujo también puede bajar.
    """
    aire = aire_dibujo()
    fondo = fondo_papel + d.ALTO_DIBUJO + aire
    filo = borde_papel if borde_papel is not None else fondo_papel
    piso = max(filo, paisaje.centro_y - (0.5 - banda_subtitulo()) * alto_cuadro * escala_reposo)
    arriba = min(tope, fondo if techo is None else techo)
    return fondo, piso + (arriba - aire - piso) / 2, arriba - aire - piso  # fmt: skip


@dataclass(frozen=True)
class Paisaje:
    """Hasta dónde llega lo dibujado: si la cámara mira más allá, aparece el escritorio vacío."""

    medio_alto: float
    centro_y: float
    ancho_util: float  # lo más ancho que se dibuja: acercarse más lo corta por los lados
    # Lo que llega de izquierda a derecha el fondo (no la letra): el techo del paneo horizontal.
    medio_ancho: float = 4.5  # la pizarra y su cuadrícula ocupan el cuadro entero (9 / 2)


def paisaje_del_tema(tema: Any) -> Paisaje:
    if tema.marco == "hoja":
        return Paisaje(c.HOJA_ALTO / 2, c.HOJA_CENTRO_Y, c.ancho_util_de(tema), c.HOJA_ANCHO / 2)
    return Paisaje(7.9, 0.0, c.ancho_util_de(tema))  # la cuadrícula de la pizarra llega hasta ±8


def escala_del_paso(actual: float, modo: str) -> float:
    ajuste = ESCALAS.get(modo, ESCALAS["suave"])
    return max(ajuste["minima"], actual * ajuste["paso"])


def escala_del_resultado(actual: float, modo: str) -> float:
    ajuste = ESCALAS.get(modo, ESCALAS["suave"])
    return max(ajuste["minima"], actual * ajuste["resultado"])


def escala_base(modo: str) -> float:
    """El encuadre del que sale cada golpe: al volver a él, la cámara se toma aire para entrar."""
    return ESCALAS.get(modo, ESCALAS["suave"])["base"]


def pico_del_golpe(paisaje: Paisaje, ancho_cuadro: float, modo: str) -> float:
    """Hasta dónde llega la cámara en el pico: un poco más adentro que el borde seguro."""
    ajuste = ESCALAS.get(modo, ESCALAS["suave"])
    seguro = (paisaje.ancho_util + HOLGURA_ANCHO) / ancho_cuadro
    return max(ajuste["minima"], seguro - GOLPE.get(modo, GOLPE["suave"]))


def ritmo_de_golpe(sobrepaso: float) -> Callable[[float], float]:
    """Entra rápido, se pasa del destino (``sobrepaso`` veces el camino) y frena hasta él."""

    def ritmo(t: float) -> float:
        if t < 0.35:
            return sobrepaso * rate_functions.ease_out_cubic(t / 0.35)
        return sobrepaso + (1.0 - sobrepaso) * rate_functions.smooth((t - 0.35) / 0.65)

    return ritmo


def encuadre(
    objetivo_y: float,
    escala: float,
    paisaje: Paisaje,
    alto_cuadro: float,
    ancho_cuadro: float,
    minima: float,
    objetivo_x: float = 0.0,
) -> tuple[float, float, float]:
    """Escala efectiva y centro (x, y) a los que puede ir la cámara sin salirse de lo dibujado.

    Nunca se aleja más allá del cuadro completo (escala máxima 1), no recorta lo dibujado por los
    lados y se detiene en el borde del fondo en los dos ejes.
    """
    por_ancho = (paisaje.ancho_util + HOLGURA_ANCHO) / ancho_cuadro
    acercada = min(1.0, max(minima, por_ancho, escala))
    return (
        acercada,
        _centro_x(objetivo_x, acercada, ancho_cuadro, paisaje),
        _centro_y(objetivo_y, acercada, alto_cuadro, paisaje),
    )


def encuadre_primer_plano(
    centro_x: float,
    centro_y: float,
    ancho: float,
    alto: float,
    paisaje: Paisaje,
    alto_cuadro: float,
    ancho_cuadro: float,
) -> tuple[float, float, float]:
    """La toma más cerrada de un bulto: escala y centro (x, y), en unidades de la pizarra.

    A diferencia del plano general, el límite lo pone lo ancho del propio bulto con su aire alrededor
    —no lo más ancho de la hoja—, así que aquí la cámara sí puede entrar de verdad. Se frena en la
    legibilidad (``MINIMA_PRIMER_PLANO``) y en el borde del fondo dibujado, que es lo que corta.
    """
    # Un bulto alto y angosto (una raíz, una fracción) se encuadra por su alto, no por su ancho.
    base = max(ancho, alto * ancho_cuadro / alto_cuadro) + AIRE_PRIMER_PLANO
    acercada = min(1.0, max(MINIMA_PRIMER_PLANO, (base + HOLGURA_ANCHO) / ancho_cuadro))
    return (
        acercada,
        _centro_x(centro_x, acercada, ancho_cuadro, paisaje),
        _centro_y(centro_y, acercada, alto_cuadro, paisaje),
    )


def encuadre_con_deriva(
    base_x: float,
    base_y: float,
    escala: float,
    fase: float,
    paisaje: Paisaje,
    alto_cuadro: float,
    ancho_cuadro: float,
) -> tuple[float, float, float]:
    """El encuadre que pidió la toma, corrido y respirando como una cámara sostenida en la mano.

    Devuelve ``(escala, x, y)`` del cuadro real. Se mide siempre desde el reposo de la toma (no desde
    donde terminó el último deslizamiento) y se frena en el borde del fondo, así que el cuadro se mueve
    sin descubrir nunca el escritorio.
    """
    dx, dy, dz = deriva_desplazamiento(fase)
    e = escala * (1.0 - dz)
    return (
        e,
        _centro_x(base_x + dx, e, ancho_cuadro, paisaje),
        _centro_y(base_y + dy, e, alto_cuadro, paisaje),
    )


def _centro_x(objetivo_x: float, escala: float, ancho_cuadro: float, paisaje: Paisaje) -> float:
    libre = max(0.0, paisaje.medio_ancho - ancho_cuadro * escala / 2)
    return min(libre, max(-libre, objetivo_x))


def _centro_y(objetivo_y: float, escala: float, alto_cuadro: float, paisaje: Paisaje) -> float:
    libre = max(0.0, paisaje.medio_alto - alto_cuadro * escala / 2)
    return min(paisaje.centro_y + libre, max(paisaje.centro_y - libre, objetivo_y))


def encuadre_de_casillero(
    ancho: float,
    alto: float,
    objetivo_y: float,
    paisaje: Paisaje,
    alto_cuadro: float,
    ancho_cuadro: float,
) -> tuple[float, float, float]:
    """La toma que mira una sola mitad del tablero partido.

    El límite lo pone el ancho del casillero, no el de la hoja entera: por eso la cámara puede entrar
    de verdad y, al entrar, le queda papel de sobra arriba y abajo para inclinarse de una mitad a la
    otra sin descubrir el escritorio.

    Lo dibujado adentro no puede bajar a la banda del subtítulo, así que la toma se inclina hacia
    abajo hasta dejarle el filo del bulto justo encima; y como el papel tiene un fondo, si con la
    cámara al ras no alcanza la toma se cierra un poco más (el ``techo``).
    """
    base = max(ancho, alto * ancho_cuadro / alto_cuadro) + AIRE_CASILLERO
    e = min(1.0, max(MINIMA_PRIMER_PLANO, (base + HOLGURA_ANCHO) / ancho_cuadro))
    fondo = objetivo_y - alto / 2
    borde_papel = paisaje.centro_y - paisaje.medio_alto
    banda = banda_subtitulo()
    e = min(e, max(MINIMA_PRIMER_PLANO, (fondo - borde_papel) / (banda * alto_cuadro)))
    objetivo_y = min(objetivo_y, fondo + (0.5 - banda) * alto_cuadro * e)
    return e, _centro_x(0.0, e, ancho_cuadro, paisaje), _centro_y(objetivo_y, e, alto_cuadro, paisaje)


def casilleros_de_mitades(tope: float, fondo: float) -> dict[str, tuple[float, float, float]]:
    """``(etiqueta, línea, alto máximo)`` de cada una de las dos mitades del tablero partido.

    El casillero de abajo no se corre a mitad de video: si algún paso trae dibujo, su franja ya está
    reservada en ``fondo``, así que las dos mitades quedan fijadas desde el primer paso.
    """
    alto = (tope - fondo) / 2.0
    mitad = tope - alto
    return {
        "arriba": (tope - 0.32, (mitad + tope - 0.62) / 2, alto - 0.62),
        "abajo": (mitad - 0.32, (fondo + mitad - 0.62) / 2, alto - 0.62),
    }


CAIDA_CAJA = 1.4  # lo que tardan la fórmula y su caja en armarse (0,9 del paso + 0,5 del golpe)
AIRE_TAPA = 0.35  # el número se queda tapado, como mínimo, este rato
COLA_DE_VOZ = 0.4  # la tapa se levanta con la frase todavía sonando


def momento_del_destape(duracion_voz: float) -> float:
    """Segundo del bloque de voz en que se levanta la tapa del resultado.

    El número debe asomarse cuando la voz lo dice, no antes. Como no sabemos en qué palabra cae,
    hay dos anclas: nunca se levanta antes de que la caja esté armada (si no, la tapa dura un
    parpadeo) ni, cuando la frase alcanza, después de que la voz terminó (si no, el número llega
    en silencio).
    """
    destape = max(CAIDA_CAJA + AIRE_TAPA, duracion_voz * 0.55)
    return min(destape, max(CAIDA_CAJA, duracion_voz - COLA_DE_VOZ))


PROPORCION_TONO_TAPA = 0.14  # apenas un punto de acento: lo justo para que la tapa se vea pegada
PROPORCION_PLIEGUE = 0.2  # el pliegue y el borde son la misma nota, más sombra
ALTO_PLEGUE = 0.42  # el lado del triángulo de la esquina doblada


def tono_de_tapa(papel: str, mezcla: str, proporcion: float) -> str:
    """El color de la tapa del resultado: el fondo tirado un punto hacia ``mezcla``.

    Soltar el color exacto del fondo dejaba en la hoja un hueco blanco que borraba la rejilla; un
    tono apenas apartado, con borde fino y esquina doblada, se lee nota pegada encima del papel.
    Mezclando hacia el negro sale el pliegue y el filo de esa misma nota.
    """

    def canales(hex_color: str) -> list[int]:
        return [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]

    mezclado = [round(a + (b - a) * proporcion) for a, b in zip(canales(papel), canales(mezcla))]
    return "#{:02X}{:02X}{:02X}".format(*mezclado)


@dataclass
class OpcionesEscena:
    proveedor: str
    voz: str
    velocidad: str
    linea_de_tiempo: Path
    # progreso(bloque_actual, total_bloques, seccion): para barras de progreso (panel)
    progreso: Callable[[int, int, str], None] | None = None
    solo_gancho: bool = False  # laboratorio de ganchos: cabecera + gancho, nada más
    # Segundos que toda fórmula debe llevar completa y quieta antes de que entre el paso siguiente.
    piso_lectura: float = PISO_LECTURA
    tono: str = "+0Hz"  # pitch de la voz (edge-tts): acerca o aleja el timbre sin cambiar de voz
    # Las decisiones de herramientas (didactica.recursos_del_guion) para el registro; None = guion
    # heredado sin contenido ni recursos propios (el registro no cambia).
    didactica: list[dict] | None = None


ALTO_MAX_CONCLUSION = 4.4  # fórmula + párrafo dentro de la caja de la conclusión


def _partes_resultado(r: Any, tema: Any) -> tuple[VGroup, RoundedRectangle, Mobject | None, Mobject, VGroup]:
    """Cabeza «CONCLUSIÓN», caja, fórmula (o None) y párrafo de una conclusión con texto.

    La fórmula, si la hay, es la pieza principal; el texto la interpreta debajo. Usa el estilo
    activo (``c.usar_estilo``): quien llama lo fija y lo restablece.
    """
    col = tema.colores
    ancho = c.ANCHO_UTIL - 1.0
    eq = c.ecuacion(r.tex, c.TAM_RESULTADO, col.formulas, ancho_max=ancho) if r.tex.strip() else None
    tam = c.TAM_CUERPO if eq is not None else c.TAM_CUERPO + 5
    parrafo = c.parrafo(r.texto, tam, SEMIBOLD, col.texto, ancho_max=ancho - 0.3, max_lineas=4)
    cuerpo = VGroup(*([eq] if eq is not None else []), parrafo).arrange(DOWN, buff=0.35)
    # Alto máximo fijo: la letra mide un poco distinto en Mac, Linux y Windows, y una conclusión
    # larga no debe depender de eso para caber (la revisión ya sugiere acortarla).
    if cuerpo.height > ALTO_MAX_CONCLUSION:
        cuerpo.scale_to_fit_height(ALTO_MAX_CONCLUSION)
    cuerpo.set_z_index(1)
    caja = RoundedRectangle(corner_radius=0.22, width=cuerpo.width + 0.9, height=cuerpo.height + 0.7)
    caja.set_fill(col.acento, 0.12).set_stroke(col.acento, 5)
    cuerpo.move_to(caja)
    cabeza = VGroup(c.visto(col.exito), c.texto("CONCLUSIÓN", c.TAM_ETIQUETA + 2, ULTRABOLD, col.exito))
    cabeza.arrange(RIGHT, buff=0.2)
    VGroup(cabeza, VGroup(caja, cuerpo)).arrange(DOWN, buff=0.32)
    return cabeza, caja, eq, parrafo, cuerpo


def componente_resultado(guion: Guion, tema: Any) -> VGroup:
    """La conclusión en texto tal como se dibuja (para medirla sin renderizar el video)."""
    token = c.usar_estilo(tema)
    try:
        cabeza, caja, _, _, cuerpo = _partes_resultado(guion.resultado, tema)
        return VGroup(cabeza, caja, cuerpo)
    finally:
        c.restablecer_estilo(token)


@dataclass
class Linea:
    """Una línea de la pizarra de pasos: [nota?, ecuación, tachado?] (los emojis no pasan al historial)."""

    mobs: list[Mobject]
    eq: Mobject


def olvida_en_ancla(pila: list[Linea], ultima: Any) -> list[Linea]:
    """Las líneas que salen de pantalla al entrar el paso siguiente, en el modo ancla.

    Se queda solo la última correcta: es la que dice de dónde viene la transformación. Un paso
    hablado o tachado no deja ancla, así que si ``ultima`` es None la pizarra queda vacía.
    """
    return [linea for linea in pila if linea.eq is not ultima]


def gramatica_de(tema, n_pasos: int) -> tuple[VGroup | None, VGroup | None]:
    g = tema.gramatica
    if not c.gramatica_activa(tema) or not n_pasos:
        return None, None
    token = c.usar_estilo(tema)
    try:
        paleta = g.paleta(tema.colores)
        tabs = c.tabs_de_pasos(n_pasos, 1, paleta) if g.tabs else None
        if tabs is not None and tabs.width > c.ancho_util_de(tema):
            tabs.scale_to_fit_width(c.ancho_util_de(tema))
        panel = (
            c.panel_persistente(
                n_pasos, [], paleta, c.ancho_util_de(tema), tema.colores.panel, tema.colores.borde,
                alto_max=tema.layout.banda_panel or 1.6,
            )
            if g.panel else None
        )
        return tabs, panel
    finally:
        c.restablecer_estilo(token)


class VideoEjercicio(VoiceoverScene, MovingCameraScene):
    def __init__(
        self, guion: Guion, marca: Marca, tema: Any, opciones: OpcionesEscena, **kwargs: Any
    ) -> None:
        self.guion = guion
        self.marca = marca
        self.tema = tema
        self.op = opciones
        self.col = tema.colores
        self.color_materia = getattr(tema.materias, guion.materia)
        self.plumon = tema.animacion.titulos == "plumon"
        self.mayus = tema.tipografia.titulos.mayusculas
        self.bloques_voz: list[dict[str, Any]] = []
        # Cuántos segundos esperó el piso de lectura en total: lo que el panel perdona de la promesa.
        self.silencio_de_lectura = 0.0
        self._dibujo_listo_en: float | None = None  # cuándo quedó completo el dibujo del paso en curso
        self._titulo_oculto = False  # las dos mitades apagan el título mientras la cámara está en un casillero
        self._pendientes: list[Animation] = []  # transiciones para el próximo bloque de voz
        self._total_bloques = len(guion.textos_de_voz(marca.cierre.voz))
        # El molde decide las palabras; la receta de rodaje, cómo se filman esos pasos.
        self.receta = rodaje_de_guion(guion)
        self._chip_vivo: VGroup | None = None  # el «✗ 1 de 3» del rincón, si la receta lo pide
        # Cámara: el tema dice hasta dónde puede mirar; el guion, cuánto se acerca.
        self.modo_camara = guion.camara
        self.paisaje = paisaje_del_tema(tema)
        self.alto_cuadro = float(config.frame_height)
        self.ancho_cuadro = float(config.frame_width)
        self._camara_escala = 1.0
        self._con_conclusion = False  # el resultado cerró con una conclusión en texto
        self._camara_ancho = 1.0  # la escala que realmente está en pantalla (la deriva la respira)
        self._camara_centro = 0.0
        self._camara_centro_x = 0.0
        # El encuadre de reposo sobre el que se mide la deriva, y el tiempo ya deslizado.
        self._deriva_base_x = 0.0
        self._deriva_base_y = 0.0
        self._deriva_t = 0.0
        self._camara_cerca = 1.0  # lo más cerca que estuvo la cámara: la cabecera no vuelve hasta el plano
        self._cabecera_fija: Mobject | None = None
        self._cabecera_opacidades: list[tuple[VMobject, float, float]] = []
        self._cabecera_imagenes: list[Mobject] = []
        self._cabecera_visible = True
        super().__init__(**kwargs)

    # --------------------------------------------------------------------------------------
    # Voz y tiempos
    # --------------------------------------------------------------------------------------

    @contextmanager
    def hablar(self, texto: str, seccion: str):
        with self.voiceover(text=texto) as tracker:
            self._registrar(tracker, seccion)
            if self.op.progreso:
                self.op.progreso(len(self.bloques_voz), self._total_bloques, seccion)
            yield tracker

    def _registrar(self, tracker: Any, seccion: str) -> None:
        datos = tracker.data
        servicio = (datos.get("input_data") or {}).get("service")
        marcas = datos.get("word_boundaries") or []
        palabras = [
            {
                "texto": m["text"],
                "inicio": m["audio_offset"] / RESOLUCION,
                "fin": m["audio_offset"] / RESOLUCION + m.get("duration_milliseconds", 0) / 1000,
            }
            for m in marcas
        ]
        self.bloques_voz.append(
            {
                "seccion": seccion,
                "inicio": round(float(tracker.start_t), 3),
                "duracion": round(float(tracker.duration), 3),
                "texto": sin_pausas(" ".join(remove_bookmarks(datos["input_text"]).split())),
                "audio": str(Path(self.speech_service.cache_dir) / datos["final_audio"]),
                "servicio": servicio,
                # "exactas": vienen del sintetizador; "estimadas": reparto proporcional (sin voz)
                "marcas": "exactas"
                if servicio == "edge-tts" and palabras
                else ("estimadas" if palabras else None),
                "palabras": palabras or None,
            }
        )

    def _da_lectura(self, tracker: Any, completa_desde: float, sale_a: float | None = None) -> None:
        """Estira el bloque hasta que la fórmula lleve su piso de segundos completa y a la vista.

        El reloj llega hasta el fin del audio, no hasta el último movimiento: los énfasis dibujados
        sobre la fórmula ya escrita y los segundos que la voz todavía tarda en terminarse también
        son lectura. Esperar de más congelaba el cuadro encima de la narración. Con el piso en 0 el
        video sale exactamente como salía antes, que es lo que muestra el «cambiar» cuando se baja.
        """
        fin = tracker.start_t + tracker.duration
        if sale_a is not None:
            fin = min(fin, sale_a)
        espera = espera_de_lectura(
            self.op.piso_lectura, completa_desde=completa_desde, fin_de_bloque=max(fin, self.renderer.time)
        )
        if espera > 1 / config.frame_rate:
            self.silencio_de_lectura += espera
            self.wait(espera)

    def hasta(self, tracker: Any, segundos: float) -> None:
        """Espera hasta ``segundos`` contados desde que empezó a hablar el bloque."""
        restante = tracker.start_t + segundos - self.renderer.time
        if restante > 1 / config.frame_rate:
            self.wait(restante)

    def wait(
        self,
        duration: float = 1.0,
        stop_condition: Callable[[], bool] | None = None,
        frozen_frame: bool | None = None,
    ) -> None:
        """La espera no congela el cuadro: con la receta «en_mano» se desliza, y con la quieta respira.

        El deslizamiento dura lo mismo que duraba la pausa, así la cadena de tiempos de la voz queda
        intacta; solo cuesta el redondeo al cuadro siguiente (un frame por pausa). Con la cámara en
        «quieta» no hay cuadro que mover y se espera como siempre.
        """
        if stop_condition is None and frozen_frame is None and duration >= PAUSA_MINIMA_DERIVA:
            desliza = self._mover_camara(
                self._camara_escala, self._deriva_base_x, self._deriva_base_y, duration, pausa=True
            )
            if desliza:
                self.play(*desliza, run_time=self.validate_run_time(duration, self.wait, "duration"))
                return
        super().wait(duration, stop_condition, frozen_frame)

    def momento(self, tracker: Any, frase: str) -> float | None:
        """Segundo (dentro del bloque) en que la voz dice ``frase``, dicha en letras o en dígitos."""
        texto = " ".join(remove_bookmarks(tracker.data["input_text"]).split())
        idx = c.busca_en_la_voz(texto, frase)
        if idx < 0:
            return None
        marcas = tracker.data.get("word_boundaries") or []
        if len(marcas) >= 2:
            xs = [m["text_offset"] for m in marcas]
            ys = [m["audio_offset"] / RESOLUCION for m in marcas]
            return float(np.interp(idx, xs, ys))
        return tracker.duration * idx / max(len(texto), 1)

    def _con_pendientes(self, *animaciones: Animation, run_time: float) -> None:
        todas = [*self._pendientes, *animaciones]
        self._pendientes = []
        if todas:
            self.play(*todas, run_time=run_time)

    def _restante(self, tracker: Any) -> float:
        return tracker.get_remaining_duration()

    # --------------------------------------------------------------------------------------
    # Cámara
    # --------------------------------------------------------------------------------------

    def _fijar_cabecera(self) -> None:
        """La fila de arriba (marca o "Notas/Fecha"): se disuelve cuando la cámara se acerca."""
        cinta = getattr(self.fondo, "cinta", None)  # en la hoja, "Notas" y "Fecha" viven en el fondo
        cabeza = cinta if cinta is not None and len(cinta) else self.cabecera
        if cinta is not None and len(cinta) and len(self.cabecera):
            cabeza = Group(cinta, self.cabecera)  # el logo de la hoja se disuelve junto con la cinta
        if len(cabeza):
            self._cabecera_fija = cabeza
            # Opacidad de cada pieza: al volver de un golpe hay que devolver la suya (el chip
            # tiene relleno suave y set_opacity(1) lo dejaba como un bloque opaco sin texto).
            self._cabecera_opacidades = [
                (m, m.get_fill_opacity(), m.get_stroke_opacity())
                for m in cabeza.get_family()
                if isinstance(m, VMobject)
            ]
            # El logo es imagen: no tiene relleno ni borde, se apaga con su propia opacidad.
            self._cabecera_imagenes = [m for m in cabeza.get_family() if isinstance(m, ImageMobject)]

    def _disolver_cabecera(self, visible: bool, run_time: float) -> Animation:
        """Muestra u oculta la cabecera respetando la opacidad propia de cada pieza."""
        registros = self._cabecera_opacidades
        imagenes = self._cabecera_imagenes

        def paso(_mob: Mobject, alpha: float) -> None:
            k = alpha if visible else 1.0 - alpha
            for pieza, relleno, borde in registros:
                pieza.set_fill(opacity=relleno * k)
                pieza.set_stroke(opacity=borde * k)
            for imagen in imagenes:
                imagen.set_opacity(k)

        return UpdateFromAlphaFunc(self._cabecera_fija, paso, run_time=run_time)

    def _animaciones_camara(
        self,
        objetivo_y: float,
        escala: float,
        run_time: float = 0.5,
        pico: float | None = None,
        objetivo_x: float = 0.0,
    ) -> list[Animation]:
        """Acerca la cámara al destino que pide la cadena de pasos, sin tocar los subtítulos.

        Con ``pico`` la cámara se pasa un poco del encuadre y vuelve: es el golpe que se nota.
        """
        if self.modo_camara == "quieta":
            return []
        ajuste = ESCALAS.get(self.modo_camara, ESCALAS["suave"])
        s, centro_x, centro_y = encuadre(
            objetivo_y,
            escala,
            self.paisaje,
            self.alto_cuadro,
            self.ancho_cuadro,
            ajuste["minima"],
            objetivo_x,
        )
        return self._mover_camara(s, centro_x, centro_y, run_time, pico)

    def _primer_plano(self, bulto: Mobject, run_time: float = 0.5) -> list[Animation]:
        """Encima del término destacado, tan cerca como el fondo y la lectura aguanten."""
        if self.modo_camara == "quieta":
            return []
        s, centro_x, centro_y = encuadre_primer_plano(
            bulto.get_center()[0],
            bulto.get_center()[1],
            bulto.width,
            bulto.height,
            self.paisaje,
            self.alto_cuadro,
            self.ancho_cuadro,
        )
        return self._mover_camara(s, centro_x, centro_y, run_time)

    def _mover_camara(
        self,
        escala: float,
        centro_x: float,
        centro_y: float,
        run_time: float,
        pico: float | None = None,
        pausa: bool = False,
    ) -> list[Animation]:
        """Lleva el cuadro al destino ya calculado; es el único sitio que mueve la cámara.

        Con la receta «en_mano» el destino se traslada el vaivén de la onda: la toma queda un poco
        corrida y un poco más adentro del encuadre que pidió el golpe, que es lo que hace una cámara
        sostenida en la mano. El reposo (``_deriva_base`` y la escala pedida) no se arrastra de una toma
        a la siguiente: si no, el corrimiento se acumularía hasta chocar con el borde del fondo.

        En la receta quieta, ``pausa`` agrega el respiradero sin paneo: esperar no tiene por qué verse
        como una foto trabada.
        """
        self._deriva_base_x, self._deriva_base_y = centro_x, centro_y
        ancho = escala
        en_mano = self.receta.deriva == "en_mano" and self.modo_camara != "quieta"
        if en_mano or (pausa and self.modo_camara != "quieta"):
            self._deriva_t += run_time
            if en_mano:
                ancho, centro_x, centro_y = encuadre_con_deriva(
                    centro_x,
                    centro_y,
                    escala,
                    self._deriva_t,
                    self.paisaje,
                    self.alto_cuadro,
                    self.ancho_cuadro,
                )
            else:
                ancho = escala * (1.0 - deriva_desplazamiento(self._deriva_t)[2])
        if (
            abs(ancho - self._camara_ancho) < 0.004
            and abs(centro_y - self._camara_centro) < 0.05
            and abs(centro_x - self._camara_centro_x) < 0.05
        ):
            return []
        camino = self._camara_escala - escala
        cercano = min(escala, pico) if pico is not None else escala
        ritmo: Callable[[float], float] = rate_functions.smooth
        if pico is not None and camino > 0.01 and pico < escala:
            sobrepaso = (self._camara_escala - pico) / camino
            # El pico también arrastra el encuadre hacia el objetivo: no puede irse de lo dibujado.
            salto = abs(centro_y - self._camara_centro)
            if salto > 1e-6:
                colchon = max(0.0, self.paisaje.medio_alto - self.alto_cuadro * cercano / 2 - abs(centro_y))
                sobrepaso = min(sobrepaso, 1.0 + colchon / salto)
            sobrepaso = min(sobrepaso, SOBREPASO_MAX)
            if sobrepaso > 1.02:
                ritmo = ritmo_de_golpe(sobrepaso)
        animaciones: list[Animation] = [
            self.camera.frame.animate(run_time=run_time, rate_func=ritmo)
            .set(width=config.frame_width * ancho)
            .move_to([centro_x, centro_y, 0])
        ]
        # Al acercarse, el papel tapa la cabecera y quedaría cortada por el borde: se disuelve.
        # No vuelve hasta que la cámara regresa al plano, aunque el golpe haya sido un instante.
        self._camara_cerca = 1.0 if escala >= 0.995 else min(self._camara_cerca, cercano)
        visible = self._camara_cerca >= 0.95
        if self._cabecera_fija is not None and visible != self._cabecera_visible:
            self._cabecera_visible = visible
            animaciones.append(self._disolver_cabecera(visible, run_time))
        self._camara_escala = escala  # el encuadre pedido, no el que terminó en pantalla
        self._camara_ancho, self._camara_centro, self._camara_centro_x = ancho, centro_y, centro_x
        return animaciones

    def _acercar_al_paso(self, eq: Mobject) -> list[Animation]:
        escala = escala_del_paso(self._camara_escala, self.modo_camara)
        pico = pico_del_golpe(self.paisaje, self.ancho_cuadro, self.modo_camara)
        return self._animaciones_camara(eq.get_center()[1] + 0.3, escala, run_time=0.45, pico=pico)

    def _toma_de_casillero(self, bulto: Mobject, aire: float = 0.25) -> list[Animation]:
        """Inclina el cuadro hacia la mitad que está hablando (o hacia el dibujo de esa mitad).

        Aquí el límite lo pone el casillero, no la hoja: la cámara entra hasta él y le queda papel
        libre por arriba y por abajo, que es lo que le permite bajar del mito a la realidad.
        """
        if self.modo_camara == "quieta":
            return []
        s, centro_x, centro_y = encuadre_de_casillero(
            bulto.width,
            bulto.height,
            bulto.get_center()[1] + aire,
            self.paisaje,
            self.alto_cuadro,
            self.ancho_cuadro,
        )
        return self._mover_camara(s, centro_x, centro_y, 0.5)

    def _primer_plano_de(self, marcos: Mobject) -> None:
        """Entra al término recuadrado, lo sostiene y devuelve al paso: el respiro de la receta."""
        # Se anota el encuadre de reposo, no la posición del cuadro: con la cámara en mano la posición
        # real está corrida por el vaivén y devolver a ella sumaría deriva sobre deriva.
        antes = (self._camara_escala, self._deriva_base_x, self._deriva_base_y)
        entra = self._primer_plano(marcos)
        if not entra:
            return
        self.play(*entra, run_time=0.45)
        self.wait(0.25)
        self.play(*self._mover_camara(*antes, run_time=0.4), run_time=0.4)

    def _destello(self, caja: Mobject) -> list[Animation]:
        """La confirmación: un aro del recuadro que se expande y se apaga, y rayos cortos alrededor."""
        aro = caja.copy().set_fill(opacity=0).set_stroke(self.col.acento, 6, 1.0).set_z_index(2)
        return [
            aro.animate(rate_func=rate_functions.ease_out_cubic).scale(1.16).set_stroke(opacity=0.0),
            Flash(
                caja.get_center(),
                color=self.col.acento,
                flash_radius=max(caja.width, caja.height) / 2 + 0.25,
                line_length=0.32,
                num_lines=16,
                line_stroke_width=5,
            ),
        ]

    def _halos_del_paso(self, paso: Any, eq: Mobject, fuente: Mobject | None) -> VGroup | None:
        """El resplandor del paso: los términos que el guion sigue (``halo``) y los que llegan nuevos.

        Va detrás de la fórmula y sale con el paso siguiente, como los recuadros de ``destacar``.
        """
        partes: list[Mobject] = []
        for buscado in paso.halo:
            partes += [m for m in c.partes_por_tex(eq, buscado) if m not in partes]
        if paso.resaltar_cambio and fuente is not None:
            partes += [m for m in c.terminos_nuevos(fuente, eq) if m not in partes]
        if not partes:
            return None
        return VGroup(*[c.halo_de(m, self.col.acento) for m in partes])

    def _tomar_aire(self) -> list[Animation]:
        """Vuelve al encuadre base antes del próximo golpe: sin ese retroceso, no hay golpe."""
        return self._animaciones_camara(0.0, escala_base(self.modo_camara), run_time=0.45)

    def _volver_al_plano(self) -> list[Animation]:
        return self._animaciones_camara(0.0, 1.0, run_time=0.45)

    # --------------------------------------------------------------------------------------
    # Ayudas de estilo
    # --------------------------------------------------------------------------------------

    def _emoji(self, valor: str | None, alto: float, forzar: bool = False) -> Mobject | None:
        if not valor or not (self.tema.emojis or forzar):
            return None
        return c.imagen_emoji(valor, alto)

    @staticmethod
    def _rebote(img: Mobject, run_time: float = 0.55) -> Animation:
        """Aparece con un salto (se pasa un poco de tamaño y vuelve)."""
        return FadeIn(img, scale=0.3, rate_func=rate_functions.ease_out_back, run_time=run_time)

    def _aparecer_titulo(self, mob: Mobject, **kw: Any) -> Animation:
        """Escritura con plumón (tema) o la aparición suave original."""
        return Write(mob) if self.plumon else FadeIn(mob, **kw)

    @staticmethod
    def _pegar_en_esquina(sticker: Mobject, caja: Mobject, giro: float) -> None:
        """Pega el sticker en la esquina superior derecha de ``caja``, montado sobre el borde pero
        sin tapar lo que hay adentro (el contenido tiene ~0,35 de margen), y sin salirse de la hoja."""
        sticker.rotate(giro).move_to(caja.get_corner(UR) + RIGHT * 0.15 + UP * 0.22)
        # Montado en la esquina, no colgando afuera: cuando la cámara se acerca al recuadro, lo que
        # sobresale de él es lo primero que corta el borde del cuadro.
        tope = min(c.ANCHO_UTIL / 2 + 0.35, caja.get_right()[0] + 0.1)
        exceso = sticker.get_right()[0] - tope
        if exceso > 0:
            sticker.shift(LEFT * exceso)

    # --------------------------------------------------------------------------------------
    # Construcción
    # --------------------------------------------------------------------------------------

    def construct(self) -> None:
        c.usar_estilo(self.tema)
        servicio = crear_servicio(self.op.proveedor, self.op.voz, self.op.velocidad, self.op.tono)
        self.set_speech_service(servicio, create_subcaption=False)
        # Toda la voz del video en un solo pedido (si la voz lo permite): una frase que se traba ya no
        # traba el video. Si no se puede, cada bloque la pide como siempre.
        if self.op.solo_gancho:
            voces = [self.guion.gancho.voz_final]
        else:
            voces = [v for _, v in self.guion.textos_de_voz(self.marca.cierre.voz)]
        precargar_voz(servicio, voces)
        self.fondo = c.fondo_tema(self.tema)
        self.add(self.fondo)

        if self.op.solo_gancho:
            self._gancho()
            # El clip es más corto que el video entero: se rellena hasta 4 s para que la vista previa
            # alcance a leerse. El bloque ya dura lo que la voz (también la de silencio, estimada).
            self.wait(max(0.2, 4.0 - self.renderer.time))
            self._guardar_linea_de_tiempo()
            return

        self._iniciar_gramatica()
        self._gancho()
        self._enunciado()
        if self.guion.datos:
            self._datos()
        self._pasos()
        self._resultado()
        if self.guion.verificacion:
            self._verificacion()
        if self.guion.reto:
            self._reto()
        self._cierre()
        self._guardar_linea_de_tiempo()

    def _fijar_gramatica(self, objeto: Mobject) -> None:
        frame = self.camera.frame
        ancho, centro = frame.width, frame.get_center().copy()

        def seguir_cuadro(mob: Mobject) -> None:
            nonlocal ancho, centro
            nuevo_ancho, nuevo_centro = frame.width, frame.get_center().copy()
            mob.scale(nuevo_ancho / ancho, about_point=centro).shift(nuevo_centro - centro)
            ancho, centro = nuevo_ancho, nuevo_centro

        objeto.set_z_index(30).add_updater(seguir_cuadro)
        self.add(objeto)

    def _colocar_panel_gramatica(self, panel: VGroup) -> VGroup:
        banda = self.tema.layout.banda_panel or 1.6
        if panel.height > banda:
            panel.scale_to_fit_height(banda)
        panel.move_to([0, -self.alto_cuadro / 2 + 0.25 + panel.height / 2, 0])
        return panel.scale(self.camera.frame.width / self.ancho_cuadro, about_point=np.zeros(3)).shift(
            self.camera.frame.get_center()
        ).set_z_index(30)

    def _iniciar_gramatica(self) -> None:
        self.tabs_gram, self.panel_gram = gramatica_de(self.tema, len(self.guion.pasos))
        self.cerrados_gram: list[str] = []
        if self.tabs_gram is not None:
            # 0,36 de 16: más grandes que antes (0,32) y siempre por encima de y = 7,5
            if self.tabs_gram.height > 0.36:
                self.tabs_gram.scale_to_fit_height(0.36)
            self.tabs_gram.move_to([0, self.alto_cuadro / 2 - 0.12 - self.tabs_gram.height / 2, 0])
            self._fijar_gramatica(self.tabs_gram)
        if self.panel_gram is not None:
            self._colocar_panel_gramatica(self.panel_gram)
            self._fijar_gramatica(self.panel_gram)

    def _cerrar_paso_gramatica(self, i: int, paso: Any) -> None:
        animaciones: list[Animation] = []
        if self.panel_gram is not None:
            if paso.tex and not paso.error:
                self.cerrados_gram.append(paso.tex)
            nuevo = c.panel_persistente(
                len(self.guion.pasos), self.cerrados_gram, self.tema.gramatica.paleta(self.col),
                c.ancho_util_de(self.tema), self.col.panel, self.col.borde, completados=i,
                alto_max=self.tema.layout.banda_panel or 1.6,
            )
            self._colocar_panel_gramatica(nuevo)
            animaciones.append(Transform(self.panel_gram, nuevo))
        if self.tabs_gram is not None and self.tema.gramatica.micro:
            animacion = c.micro_movimiento("tick", self.tabs_gram[i - 1])
            marca = animacion.mobject.set_z_index(31)
            self.tabs_gram[i - 1].add(marca)
            animaciones.append(animacion)
        if animaciones:
            self.play(*animaciones, run_time=0.3)
        if self.panel_gram is not None:
            # Transform conserva los tipos de origen: el panel vacío deja puntos en vez de MathTex.
            self.panel_gram.remove(*list(self.panel_gram))
            self.panel_gram.add(*nuevo)
        formulas = self.panel_gram[1][2] if self.panel_gram is not None else None
        escribe = self.tema.gramatica.micro and paso.tex and not paso.error
        if formulas is not None and len(formulas) and escribe:
            self.play(c.micro_movimiento("cursor", formulas[-1]), run_time=0.2)

    def _cabecera(self) -> Group:
        if self.tema.marco == "hoja":
            # "Notas" y "Fecha:" ya están en el marco de la hoja; arriba solo suma el logo, al centro.
            logo = self._emoji(self.marca.cierre.emoji, 0.7, forzar=True)
            return VGroup() if logo is None else Group(logo.move_to([0, c.Y_CABECERA, 0]))
        # El logo subido en Ajustes manda también arriba; el engranaje dibujado queda de respaldo.
        logo = self._emoji(self.marca.cierre.emoji, 0.36, forzar=True)
        icono = logo if logo is not None else c.engranaje(0.17, self.col.acento, self.col.fondo)
        nombre = c.texto(self.marca.nombre.upper(), 19, ULTRABOLD, self.col.titulos)
        # Group, no VGroup: el logo es una imagen y un VGroup solo admite trazos.
        izquierda = Group(icono, nombre).arrange(RIGHT, buff=0.16)
        izquierda.move_to([0, c.Y_CABECERA, 0]).to_edge(LEFT, buff=0.6)
        # El rótulo del tema («DATO», «MITO»…) dice qué tipo de video es; sin rótulo, la materia.
        rotulo = str(getattr(self.tema, "rotulo", "") or "").strip()
        materia = c.chip(rotulo or self.guion.etiqueta_materia, self.color_materia)
        materia.move_to([0, c.Y_CABECERA, 0]).to_edge(RIGHT, buff=0.6)
        return Group(izquierda, materia)

    def _gancho(self) -> None:
        g = self.guion.gancho
        lleno = self.receta.gancho == "lleno"
        k = ESCALA_GANCHO_LLENO if lleno else 1.0
        destacar = g.destacar or c.numeros_en(g.texto)
        p = c.parrafo(
            g.texto,
            c.TAM_GANCHO * k,
            HEAVY,
            self.col.titulos,
            destacar=destacar,
            color_destacado=self.col.acento,
            interlineado=0.3,
            max_lineas=4,
            mayus=self.mayus,
        )
        emoji = None if g.visual is not None else self._emoji(g.emoji, 1.7 * k)
        formula = c.ecuacion(g.tex, c.TAM_ECUACION, self.col.formulas).set_z_index(1) if g.tex else None
        suelto = emoji is None and formula is None
        y = Y_GANCHO_LLENO if lleno else c.CENTRO_ZONA + (0.9 if suelto else 0.6)
        if suelto:
            bloque = p
            p.move_to([0, y, 0])
        else:
            bloque = Group(*[m for m in (emoji, p, formula) if m is not None])
            bloque.arrange(DOWN, buff=0.5).move_to([0, y, 0])
        if lleno and bloque.height > ALTO_GANCHO_LLENO:
            # Una pregunta larga con emoji y fórmula no puede bajar de la banda de los subtítulos:
            # si no entra, cede la letra, nunca el encuadre.
            bloque.scale_to_fit_height(ALTO_GANCHO_LLENO)
        if g.visual is not None:
            # El dibujo manda: la pregunta se sube al techo de la zona y la banda de abajo queda libre.
            bloque.move_to([0, c.Y_ZONA_SUPERIOR - bloque.height / 2 - 0.15, 0])
            piso_pregunta = bloque.get_bottom()[1]
            _, centro_dibujo, alto_dibujo = self._franja_del_dibujo(g, piso_pregunta, techo=piso_pregunta)
        else:
            piso_pregunta = bloque.get_bottom()[1]
            _, centro_dibujo, alto_dibujo = self._franja_del_dibujo(g, piso_pregunta)
        dibujo = None
        self.cabecera = self._cabecera()
        self._fijar_cabecera()
        with self.hablar(g.voz_final, "gancho") as tr:
            if lleno and len(self.cabecera):
                # La marca no acompaña: la pregunta sola ocupa el cuadro y la cabecera llega con el
                # enunciado, en el mismo movimiento que se lleva el gancho fuera.
                self._pendientes.append(FadeIn(self.cabecera, shift=DOWN * 0.15))
                self.play(
                    LaggedStart(*[FadeIn(linea, scale=0.6) for linea in p], lag_ratio=0.15), run_time=0.7
                )
            elif self.plumon:
                self.play(FadeIn(self.cabecera), Write(p), run_time=0.9)
            else:
                self.play(
                    FadeIn(self.cabecera, shift=DOWN * 0.15),
                    LaggedStart(*[FadeIn(linea, scale=0.6) for linea in p], lag_ratio=0.15),
                    run_time=0.7,
                )
            if emoji is not None:
                self.play(self._rebote(emoji))
            if formula is not None:
                self.play(Write(formula), run_time=0.8)
                completa_desde = self.renderer.time
            for frase in destacar:
                letras = c.frase_en_parrafo(p, frase)
                t = self.momento(tr, frase)
                if len(letras) and t is not None:
                    self.hasta(tr, t)
                    self.play(Indicate(letras, color=self.col.acento, scale_factor=1.18), run_time=0.5)
            if g.visual is not None and alto_dibujo > 0:
                dibujo = self._trazar_dibujo(g, centro_dibujo, alto_dibujo, tr, mover_camara=False)
                # El gancho no sostiene su dibujo (se va con la pregunta): que su «listo» no lo herede
                # el primer paso, que esperaría en silencio por un dibujo que ya no está.
                self._dibujo_listo_en = None
            if emoji is not None and self._restante(tr) > 1.0:
                self.play(Wiggle(emoji, scale_value=1.08, rotation_angle=0.05 * TAU), run_time=0.8)
            if formula is not None:
                self._da_lectura(tr, completa_desde)
        salen = [m for m in (p, emoji, formula) if m is not None]
        if dibujo is not None:
            salen.append(dibujo.mobs)
        self._pendientes.append(FadeOut(salen[0] if len(salen) == 1 else Group(*salen), shift=UP * 0.5))

    def _enunciado(self) -> None:
        e = self.guion.enunciado
        self.titulo = c.parrafo(
            self.guion.titulo,
            c.TAM_TITULO,
            ULTRABOLD,
            self.col.titulos,
            interlineado=0.3,
            max_lineas=2,
            mayus=self.mayus,
        )
        if self.titulo.height > 0.95:
            self.titulo.scale_to_fit_height(0.95)
        self.titulo.move_to([0, c.Y_TITULO, 0])

        etiqueta = c.texto(e.etiqueta.upper(), c.TAM_ETIQUETA, ULTRABOLD, self.color_materia)
        cuerpo = c.parrafo(
            e.texto,
            c.TAM_CUERPO,
            SEMIBOLD,
            self.col.texto,
            ancho_max=c.ANCHO_UTIL - 0.8,
            alineacion="left",
            destacar=e.destacar,
            color_destacado=self.col.acento,
        )
        contenido = VGroup(etiqueta, cuerpo).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        tarjeta = c.tarjeta(contenido, c.ANCHO_UTIL, self.col.panel, self.col.borde)
        if tarjeta.height > c.ALTO_ZONA - 0.4:
            tarjeta.scale_to_fit_height(c.ALTO_ZONA - 0.4)
        tarjeta.move_to([0, c.CENTRO_ZONA + 0.5, 0])
        subrayados = VGroup()

        with self.hablar(e.voz_final, "enunciado") as tr:
            self._con_pendientes(
                self._aparecer_titulo(self.titulo, shift=DOWN * 0.15),
                FadeIn(tarjeta[0], scale=0.97),
                FadeIn(etiqueta),
                run_time=0.5,
            )
            self.play(
                LaggedStart(*[FadeIn(linea, shift=RIGHT * 0.12) for linea in cuerpo], lag_ratio=0.25),
                run_time=min(1.6, 0.3 * len(cuerpo) + 0.4),
            )
            eventos = sorted((t, frase) for frase in e.destacar if (t := self.momento(tr, frase)) is not None)
            for t, frase in eventos:
                letras = c.frase_en_parrafo(cuerpo, frase)
                if not len(letras):
                    continue
                self.hasta(tr, t)
                lineas = VGroup(*[c.subrayado(m, self.col.acento, 5, 0.08) for m in letras])
                subrayados.add(lineas)
                self.play(
                    Create(lineas), Indicate(letras, color=self.col.acento, scale_factor=1.06), run_time=0.45
                )
        self._pendientes.append(FadeOut(VGroup(tarjeta, subrayados), shift=UP * 0.3))

    def _datos(self) -> None:
        etiqueta = c.texto("DATOS", c.TAM_ETIQUETA, ULTRABOLD, self.color_materia)
        items = [
            c.ecuacion(d.tex, c.TAM_DATO, self.col.formulas, ancho_max=c.ANCHO_UTIL - 1.5).set_z_index(1)
            for d in self.guion.datos
        ]
        vinetas = [Dot(radius=0.07, color=self.color_materia) for _ in items]
        filas = [VGroup(v, it).arrange(RIGHT, buff=0.3) for v, it in zip(vinetas, items, strict=True)]
        lista = VGroup(*filas).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        contenido = VGroup(etiqueta, lista).arrange(DOWN, aligned_edge=LEFT, buff=0.34)
        tarjeta = c.tarjeta(contenido, c.ANCHO_UTIL, self.col.panel, self.col.borde)
        if tarjeta.height > c.ALTO_ZONA - 0.4:
            tarjeta.scale_to_fit_height(c.ALTO_ZONA - 0.4)
        tarjeta.move_to([0, c.CENTRO_ZONA + 0.5, 0])

        for i, (dato, fila) in enumerate(zip(self.guion.datos, filas, strict=True), 1):
            with self.hablar(dato.voz, f"dato {i}"):
                if i == 1:
                    self._con_pendientes(FadeIn(tarjeta[0], scale=0.97), FadeIn(etiqueta), run_time=0.4)
                self.play(FadeIn(fila, shift=RIGHT * 0.2), run_time=0.45)

        # Los datos quedan fijos arriba, en pequeño, como referencia durante la solución.
        ancho_franja = c.ANCHO_UTIL - 0.5
        compactos = VGroup(*[it.copy() for it in items]).scale(0.72).arrange(RIGHT, buff=0.5)
        if compactos.width > ancho_franja:
            compactos.arrange_in_grid(cols=2, buff=(0.5, 0.2))
        if compactos.width > ancho_franja:
            compactos.scale_to_fit_width(ancho_franja)
        compactos.next_to(self.titulo, DOWN, buff=0.4)
        marco = RoundedRectangle(corner_radius=0.2, width=c.ANCHO_UTIL, height=compactos.height + 0.36)
        marco.set_fill(self.col.panel, 0.9).set_stroke(self.col.borde, 2).move_to(compactos)
        self._pendientes += [
            FadeOut(VGroup(tarjeta[0], etiqueta, *vinetas)),
            FadeIn(marco),
            *[
                it.animate.move_to(comp).scale(comp.height / it.height)
                for it, comp in zip(items, compactos, strict=True)
            ],
        ]
        self.datos_fijos = VGroup(marco, *items)
        self.y_inicio_pasos = marco.get_bottom()[1] - 0.4

    def _nota(self, paso: Any) -> Mobject | None:
        nota = self.tema.nota
        texto = paso.nota or ("¡ERROR TÍPICO!" if paso.error else None)
        if not texto:
            return None
        if paso.error:
            color = self.col.error
        else:
            color = {"materia": self.color_materia, "titulos": self.col.titulos, "acento": self.col.acento}[
                nota.color
            ]
        peso = SEMIBOLD if nota.rol == "texto" else HEAVY
        return c.texto(texto, 24 * nota.escala, peso, color)

    def _chip_de_errores(self, numero: int | None, total: int) -> None:
        """El «✗ 2 de 3» del rincón superior derecho, que le cede el lugar al chip de la materia.

        Con ``numero`` en None se apaga: la racha de errores terminó y el rincón vuelve a su dueño.
        """
        materia = self.cabecera[1] if len(self.cabecera) > 1 else None
        if numero is None:
            if self._chip_vivo is None:
                return
            sale, self._chip_vivo = self._chip_vivo, None
            self.play(FadeOut(sale), *([FadeIn(materia)] if materia is not None else []))
            return
        chip = c.chip(f"✗ {numero} de {total}", self.col.error, tam=21)
        chip.move_to([0, c.Y_CABECERA, 0]).to_edge(RIGHT, buff=0.6)
        sale = self._chip_vivo if self._chip_vivo is not None else materia
        self._chip_vivo = chip
        self.play(*([FadeOut(sale)] if sale is not None else []), FadeIn(chip, shift=DOWN * 0.1))

    def _franja_del_dibujo(
        self, paso: Any, tope: float, techo: float | None = None
    ) -> tuple[float, float, float]:
        """Hasta dónde baja la pizarra de pasos, y el centro y el alto con los que entra el dibujo."""
        if paso.visual is None:
            return c.Y_ZONA_INFERIOR, 0.0, 0.0
        fondo, centro, alto = franja_del_dibujo(
            self.paisaje,
            self.alto_cuadro,
            escala_base(self.modo_camara),
            c.Y_ZONA_INFERIOR,
            tope,
            techo=techo,
            borde_papel=self.paisaje.centro_y - self.paisaje.medio_alto,
        )
        # Una pregunta larga con dibujo puede dejar la banda al revés: sin banda no se dibuja
        # (más abajo el dibujo se salta), en vez de achatar la imagen por debajo de cero.
        return fondo, centro, max(alto, 0.0)

    def _mover_dibujo(
        self, dibujo: d.Dibujo, duracion: float, restante: float, camara: list[Animation]
    ) -> None:
        """Entra el dibujo con lo justo y después corre su física en el tiempo real.

        El reloj avanza lineal: la simulación dura lo que dura en el papel. Si la voz se queda
        corta, se recorre sólo el trozo que cabe y la revisión ya avisó del corte.
        """
        entrada, ventana, avance, _ = plan_de_movimiento(duracion, restante)
        recorrido = min(ventana, duracion)
        if not dibujo.fisico:
            # Sin física que respetar (tangente, área, órbita 3D): el recorrido llena la voz entera.
            recorrido, avance = recorrido_sin_fisica(ventana)
        # La pose de partida antes de entrar: un dibujo puede construirse en su pose final (la que ve
        # la miniatura) y la escena siempre arranca el movimiento desde el principio.
        dibujo.vivo(0.0)
        animaciones: list[Animation] = [Create(m) for m in dibujo.trazo]
        if dibujo.aparece:
            animaciones.append(
                LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in dibujo.aparece], lag_ratio=0.12)
            )
        if animaciones:
            self.play(*animaciones, *camara, run_time=entrada)
        elif camara:
            self.play(*camara, run_time=entrada)
        if dibujo.estela is not None:
            self.add(dibujo.estela)
        # El dibujo entero es el que se anima: Manim congela en una imagen fija todo lo que no sea
        # el objeto de la animación (ni tenga updater), así que un reloj aparte movía la pose sin
        # que se volviera a pintar. Agregarlo también trae las piezas que nacen invisibles (halos,
        # relleno del área) y que no pasan por la entrada.
        self.add(dibujo.mobs)
        self.play(
            movimiento_de(dibujo, avance),
            run_time=recorrido,
            rate_func=rate_functions.linear,
        )
        dibujo.vivo(avance)

    def _trazar_dibujo(
        self, paso: Any, centro_y: float, alto: float, tr: Any, mover_camara: bool = True
    ) -> d.Dibujo:
        """Dibuja el visual del paso con lo que queda de su voz: primero el trazo, luego lo escrito."""
        hoja = self.tema.marco == "hoja"
        # El color del papel es el de la hoja cuadriculada, o el de la tarjeta en la pizarra oscura.
        papel = self.tema.hoja.color if hoja else self.col.panel
        # Con el tablero partido el dibujo vive dentro de un casillero: si ocupara el ancho de la hoja,
        # la toma de la mitad lo cortaría por los lados.
        ancho = ANCHO_CASILLERO - 0.3 if self.receta.partida == "mitades" else c.ANCHO_UTIL
        dibujo = d.dibujar_visual(paso.visual, self.col, ancho, alto, papel)
        dibujo.place(0, centro_y)
        if not hoja:  # en la pizarra el dibujo tiene su propia tarjeta, como los pasos
            caja = (
                RoundedRectangle(corner_radius=0.28, width=ancho, height=alto)
                .set_fill(papel, 0.94)
                .set_stroke(self.col.borde, 2.5)
                .move_to([0, centro_y, 0])
            )
            # Al fondo del grupo: los dibujos que se mueven se agregan enteros a la escena (self.add de
            # dibujo.mobs) y una tarjeta al final del grupo se pintaba ENCIMA, tapándolos al 94 %.
            dibujo.mobs.add_to_back(caja)
            self.add(caja)
        restante = max(self._restante(tr) - 0.5, 1.0)
        if self.receta.partida == "mitades":
            camara = self._toma_de_casillero(dibujo.mobs, aire=0.0)
        elif mover_camara:
            camara = self._animaciones_camara(centro_y, self._camara_escala, run_time=0.55)
        else:
            camara = []  # el gancho se mira entero desde el reposo: acá la cámara no se mueve
        if dibujo.vivo is not None and dibujo.duracion:
            self._mover_dibujo(dibujo, dibujo.duracion, restante, camara)
            self._dibujo_listo_en = self.renderer.time  # desde acá se ve completo (el proyectil ya cayó)
            return dibujo
        # El dibujo termina antes que la voz: lo que queda es el rato que se mira ya completo.
        if dibujo.trazo:
            self.play(
                LaggedStart(*[Create(m) for m in dibujo.trazo], lag_ratio=0.1),
                *camara,
                run_time=restante * 0.5,
            )
            camara = []
        if dibujo.aparece:
            self.play(
                LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in dibujo.aparece], lag_ratio=0.12),
                *camara,
                run_time=restante * 0.32,
            )
        self._dibujo_listo_en = self.renderer.time
        return dibujo

    def _sostener_dibujo(self, tr: Any) -> None:
        """Deja el dibujo terminado a la vista al menos ``PISO_DIBUJO`` segundos antes de seguir.

        El movimiento llena la voz del paso, así que el cuadro final (el proyectil que cae, los ocho
        cubos llenos) duraba medio segundo y el paso siguiente lo borraba: «llegó y desapareció».
        Si la voz ya da ese rato, no se agrega nada; si no, se espera en silencio, como el piso de
        lectura de las fórmulas (con el piso en 0 el ritmo queda como antes).
        """
        listo = getattr(self, "_dibujo_listo_en", None)
        self._dibujo_listo_en = None
        if listo is None or self.op.piso_lectura <= 0:
            return
        fin = tr.start_t + tr.duration
        objetivo = listo + PISO_DIBUJO
        if objetivo <= max(fin, self.renderer.time) + 1 / config.frame_rate:
            return
        self.hasta(tr, tr.duration)  # la voz termina primero; el silencio va después
        espera = objetivo - self.renderer.time
        if espera > 1 / config.frame_rate:
            self.silencio_de_lectura += espera
            self.wait(espera)

    def _pasos(self) -> None:
        """La cadena de pasos, como diga la receta de rodaje del molde.

        ``ancla`` deja una sola línea de recuerdo arriba, chica y tenue, y el paso nuevo entra
        grande: se ve de dónde se viene y qué fue lo que cambió. ``pila`` es lo de siempre: cada
        paso se apila bajo el anterior y solo salen por arriba si ya no caben. Un paso "error
        típico" se tacha y no sirve de origen para la transformación siguiente.

        Con ``partida: mitades`` el tablero se parte en dos casilleros fijos y manda ella: el error
        se escribe arriba con su rótulo MITO y la forma correcta abajo con REALIDAD, cada uno en su
        sitio y sin achicarse. El tachado ya no se expulsa: el mito queda a la vista mientras se
        mira la realidad, que es justamente la comparación."""
        receta = self.receta
        # El «✗ 2 de 3» solo tiene sentido si hay racha que contar: un error suelto no es un marcador.
        errores_total = sum(1 for p in self.guion.pasos if p.error) if receta.contador == "errores" else 0
        errores_vistos = 0
        tope = getattr(self, "y_inicio_pasos", c.Y_ZONA_SUPERIOR - 0.2)
        self.tope_pasos = tope
        mitades = receta.partida == "mitades"
        con_dibujo = any(p.visual is not None for p in self.guion.pasos)
        reserva = d.ALTO_DIBUJO + aire_dibujo() if con_dibujo else 0.0
        casilleros = casilleros_de_mitades(tope, c.Y_ZONA_INFERIOR + (reserva if mitades else 0.0))
        vivos: dict[str, Linea | None] = {"arriba": None, "abajo": None}
        rotulos: dict[str, Mobject] = {}
        datos_vivos: Mobject | None = getattr(self, "datos_fijos", None) if mitades else None
        pila: list[Linea] = []
        en_historial: set[int] = set()  # líneas ya achicadas (por id de la ecuación)
        resaltes: list[VGroup] = []
        halos_vivos: list[VGroup] = []  # el resplandor del paso anterior: se va de golpe, no se desvanece
        extras_vivos: list[Mobject] = []  # emojis del paso anterior (salen en el siguiente)
        dibujo_vivo: d.Dibujo | None = None  # el dibujo del paso anterior (sale en el siguiente)
        ultima: Any = None  # última ecuación CORRECTA (origen de la transformación)

        for i, paso in enumerate(self.guion.pasos, 1):
            with self.hablar(paso.voz, f"paso {i}") as tr:
                if self.tabs_gram is not None:
                    c.activar_tab(self.tabs_gram, i)
                if i == 1 and self.panel_gram is not None and self.tema.gramatica.micro:
                    self.play(
                        c.micro_movimiento("contador", self.panel_gram[1][0]),
                        c.micro_movimiento("barra", self.panel_gram[1][1][1]), run_time=0.3,
                    )
                fondo, centro_dibujo, alto_dibujo = self._franja_del_dibujo(paso, tope)
                sale_dibujo = [FadeOut(dibujo_vivo.mobs)] if dibujo_vivo else []
                dibujo_vivo = None
                if paso.tex is None:  # paso solo hablado
                    self._con_pendientes(*[FadeOut(x) for x in extras_vivos], *sale_dibujo, run_time=0.5)
                    extras_vivos = []
                    if paso.visual is not None and alto_dibujo > 0:
                        dibujo_vivo = self._trazar_dibujo(paso, centro_dibujo, alto_dibujo, tr)
                    elif ultima is not None:
                        self.play(Indicate(ultima, color=self.col.acento, scale_factor=1.04), run_time=0.6)
                    if c.gramatica_activa(self.tema):
                        self.hasta(tr, max(0.0, tr.duration - 0.6))
                        self._cerrar_paso_gramatica(i, paso)
                    self._sostener_dibujo(tr)
                    continue

                terminos_mapa = [m.termino for m in paso.mapa] if self.tema.gramatica.mapa_color else []
                eq = c.ecuacion(paso.tex, c.TAM_ECUACION, self.col.formulas,
                                aislar=terminos_mapa).set_z_index(1)
                if eq.height > c.ALTO_MAX_ECUACION:
                    eq.scale_to_fit_height(c.ALTO_MAX_ECUACION)
                nota = self._nota(paso)
                # El emoji va a la derecha de la fila entera (nota + fórmula), centrado en su alto: junto a
                # la nota sola, un emoji más alto que ella se montaba sobre la fórmula de abajo y tapaba
                # sus números («30·000», «= 15000 pesos»). Se le hace espacio a las dos líneas.
                emoji = self._emoji(paso.emoji or ("alerta" if paso.error else None), 0.78)
                hueco = emoji.width + 0.2 if emoji is not None else 0.0
                # (la fórmula sola ya viene ajustada al ancho por c.ecuacion)
                for linea_de_texto in (nota, eq if emoji is not None else None):
                    if linea_de_texto is not None and linea_de_texto.width > c.ANCHO_UTIL - hueco + 1e-6:
                        linea_de_texto.scale_to_fit_width(c.ANCHO_UTIL - hueco)  # nada se sale de la hoja
                nueva = VGroup(*[m for m in (nota, eq) if m is not None]).arrange(DOWN, buff=0.16)

                # —— Dónde cae cada línea ——————————————————————————————————————————
                # En el modo de siempre las anteriores se achican y se tienuen, y si no caben todas
                # salen las más antiguas. Con las dos mitades cada una tiene su casillero fijo: no se
                # achica nada, la que estaba en ese casillero sale y entra la nueva en su mismo sitio.
                salen: list[Linea] = []
                if mitades:
                    mitad = "arriba" if paso.error else "abajo"
                    y_rotulo, y_linea, alto_max = casilleros[mitad]
                    # El emoji va al lado: la fila entera (fórmula + emoji) tiene que caber en el casillero,
                    # porque la toma de la mitad se cierra a su ancho y cortaría lo que sobre.
                    if nueva.width > ANCHO_CASILLERO - hueco:
                        nueva.scale_to_fit_width(ANCHO_CASILLERO - hueco)
                    if nueva.height > alto_max:
                        nueva.scale_to_fit_height(alto_max)
                    nueva.move_to([0, y_linea, 0])
                    vieja = vivos[mitad]
                    if vieja is not None:
                        vivos[mitad] = None
                        pila.remove(vieja)
                        salen.append(vieja)
                else:
                    if receta.pasos == "ancla":
                        # Una sola línea de recuerdo (de dónde viene la transformación); el resto fuera.
                        for vieja in olvida_en_ancla(pila, ultima):
                            pila.remove(vieja)
                            salen.append(vieja)
                    alto_zona = tope - fondo
                    while True:
                        destinos = []
                        for linea in pila:
                            copia = VGroup(*[m.copy() for m in linea.mobs])
                            if id(linea.eq) not in en_historial:
                                copia.scale(c.ESCALA_HISTORIAL)
                            destinos.append(copia.set_fill(opacity=0.35))
                        columna = VGroup(*destinos, nueva).arrange(DOWN, buff=0.34)
                        if columna.height <= alto_zona or not pila:
                            break
                        salen.append(pila.pop(0))
                    if columna.height > alto_zona:
                        columna.scale_to_fit_height(alto_zona)
                    columna.move_to([0, (tope + fondo) / 2, 0])  # pizarra centrada
                if emoji is not None:  # la fila [nota o fórmula + emoji] queda centrada
                    nueva.shift(LEFT * hueco / 2)
                    emoji.next_to(nueva, RIGHT, buff=0.2)

                # El halo se apaga de golpe: la línea a la que pertenece sube y se achica en esta misma
                # animación, y un halo que se desvanece se quedaría flotando en el sitio viejo.
                if halos_vivos:
                    self.remove(*halos_vivos)
                    halos_vivos = []
                previas: list[Animation] = (
                    [FadeOut(r) for r in resaltes] + [FadeOut(x) for x in extras_vivos] + sale_dibujo
                )
                resaltes, extras_vivos = [], []
                if mitades and datos_vivos is not None:
                    # La cámara vive encima de un casillero: los datos fijos asomarían cortados por
                    # el borde, y cada casillero ya trae su nota con lo que se usa.
                    previas.append(FadeOut(datos_vivos))
                    datos_vivos = None
                titulo = getattr(self, "titulo", None)
                if mitades and titulo is not None and not self._titulo_oculto and titulo in self.mobjects:
                    # Lo mismo el título: la toma del casillero de arriba lo dejaba gigante y cortado
                    # por los dos lados («O DEL DOBLE DESC»). Vuelve con el resultado, en el plano.
                    previas.append(FadeOut(titulo))
                    self._titulo_oculto = True
                for linea in salen:
                    previas += [FadeOut(m, shift=UP * 0.5) for m in linea.mobs]
                if not mitades:
                    for linea, destino in zip(pila, destinos, strict=True):
                        previas += [m.animate.become(d) for m, d in zip(linea.mobs, destino, strict=True)]
                        en_historial.add(id(linea.eq))
                    previas += self._tomar_aire()
                self._con_pendientes(*previas, run_time=0.45)

                # Si comparte términos con la última ecuación correcta, esos términos "viajan".
                fuente = None
                if ultima is not None and paso.transformar and not paso.error:
                    if mitades:
                        fuente = ultima.copy().set_fill(opacity=1)  # viaja dentro del mismo casillero
                    else:
                        pos = next((k for k, ln in enumerate(pila) if ln.eq is ultima), None)
                        if pos is not None:
                            fuente = destinos[pos][pila[pos].mobs.index(ultima)].copy().set_fill(opacity=1)
                        else:
                            fuente = ultima.copy().set_fill(opacity=1)
                mapa = c.coincidencias(fuente, eq) if fuente is not None else None
                aparecer: list[Animation] = []
                if nota is not None:
                    aparecer.append(Write(nota) if self.plumon else FadeIn(nota, shift=DOWN * 0.1))
                if mapa is not None:
                    aparecer.append(TransformMatchingTex(fuente, eq, key_map=mapa))
                else:
                    aparecer.append(Write(eq))
                if mitades:
                    rotulo = rotulos.get(mitad)
                    if rotulo is None:  # el rótulo del casillero llega con su primera línea
                        arriba = mitad == "arriba"
                        rotulo = c.texto(
                            "MITO" if arriba else "REALIDAD",
                            c.TAM_ETIQUETA + 2,
                            ULTRABOLD,
                            self.col.error if arriba else self.col.exito,
                        ).move_to([0, y_rotulo, 0])
                        rotulos[mitad] = rotulo
                        aparecer.append(FadeIn(rotulo, shift=DOWN * 0.08))
                    aparecer += self._toma_de_casillero(eq)
                else:
                    aparecer += self._acercar_al_paso(eq)  # el golpe de cámara entra con la fórmula
                if paso.resaltar_cambio and fuente is not None and mapa is not None:
                    # Lo que se cancela o se va se tacha sobre la fórmula anterior antes de viajar.
                    tachas = VGroup(*[c.tacha_de(m, self.col.error) for m in c.terminos_nuevos(eq, fuente)])
                    if len(tachas):
                        self.add(fuente)
                        self.play(LaggedStart(*[Create(t) for t in tachas], lag_ratio=0.2), run_time=0.4)
                        aparecer.append(FadeOut(tachas))
                # El dibujo que demuestra va ANTES que su fórmula: primero se ve (caben 8 cubos) y la
                # fórmula llega como resumen de lo que ya se vio. El rótulo del paso sí entra primero.
                demuestra_primero = (
                    paso.visual is not None and paso.visual.tipo in DIBUJOS_QUE_DEMUESTRAN and alto_dibujo > 0
                )
                if demuestra_primero:
                    if nota is not None:
                        self.play(aparecer.pop(0), run_time=0.6)
                    dibujo_vivo = self._trazar_dibujo(paso, centro_dibujo, alto_dibujo, tr)
                self.play(*aparecer, run_time=float(np.clip(tr.duration * 0.45, 0.8, 1.6)))
                completa_desde = self.renderer.time  # desde acá la fórmula ya está completa en pantalla
                if self.tema.gramatica.mapa_color and paso.mapa:
                    conceptos = c.mapa_de_color(eq, paso.mapa, self.tema.gramatica.paleta(self.col))
                    self.play(FadeIn(conceptos), run_time=0.4)
                    extras_vivos.append(conceptos)
                halos = self._halos_del_paso(paso, eq, fuente if mapa is not None else None)
                if halos is not None:
                    self.play(FadeIn(halos, scale=1.08), run_time=0.4)
                    halos_vivos.append(halos)
                if paso.visual is not None and alto_dibujo > 0 and not demuestra_primero:
                    dibujo_vivo = self._trazar_dibujo(paso, centro_dibujo, alto_dibujo, tr)

                linea_nueva = Linea(mobs=list(nueva), eq=eq)
                if emoji is not None:
                    extras_vivos.append(emoji)

                marcos = VGroup(
                    *[
                        SurroundingRectangle(
                            VGroup(*ps), color=self.col.acento, buff=0.09, corner_radius=0.1, stroke_width=5
                        )
                        for ps in (c.partes_por_tex(eq, d) for d in paso.destacar)
                        if ps
                    ]
                )
                hizo_toma = False
                if len(marcos):
                    self.play(Create(marcos), run_time=0.4)
                    # Un paso con dibujo ya se gasta la voz dibujando: ahí no cabe una toma más.
                    if (
                        receta.primer_plano == "destacar"
                        and paso.visual is None
                        and self._restante(tr) >= 1.3
                    ):
                        self._primer_plano_de(marcos)
                        hizo_toma = True

                if paso.error:
                    self.hasta(tr, tr.duration * 0.45)
                    cruz = c.tachado(eq, self.col.error)
                    self.play(Create(cruz), run_time=0.45)
                    if not hizo_toma:
                        # La fórmula y su ✗ tiemblan juntas (mismo centro, mismo movimiento).
                        # Si la cámara ya entró al término, ese empujón fue el énfasis y sobra el temblor.
                        temblor = {"scale_value": 1.06, "rotation_angle": 0.02 * TAU}
                        animaciones: list[Animation] = [Wiggle(eq, **temblor), Wiggle(cruz, **temblor)]
                        if emoji is not None:
                            animaciones.append(self._rebote(emoji))
                        self.play(*animaciones, run_time=0.7)
                    linea_nueva.mobs.append(cruz)
                    if errores_total:
                        errores_vistos += 1
                        self._chip_de_errores(errores_vistos, errores_total)
                else:
                    self._chip_de_errores(None, 0)  # se cortó la racha: el rincón vuelve a la materia
                    if emoji is not None:
                        self.play(self._rebote(emoji))

                error_sale = bool(paso.error and receta.error == "sale" and not mitades)
                # El recuadro, la ✗ y el temblor se dibujan sobre la fórmula ya escrita: no reinician
                # la lectura. Si además la línea tachada sale antes de que termine la voz, leer termina ahí.
                sale_antes = tr.start_t + max(0.0, tr.duration - 0.7) if error_sale else None
                if paso.tex:
                    self._da_lectura(tr, completa_desde, sale_antes)
                if error_sale:
                    # Un error ya mostrado y tachado no tiene por qué seguir estorbando el video. En
                    # las dos mitades el mito se queda: sin él a la vista no hay con qué comparar.
                    self.hasta(tr, max(0.0, tr.duration - 0.7))
                    bolsa = list(linea_nueva.mobs) + ([marcos] if len(marcos) else [])
                    self.play(*[FadeOut(m, shift=DOWN * 0.35) for m in bolsa], run_time=0.5)
                else:
                    pila.append(linea_nueva)
                    if mitades:
                        vivos[mitad] = linea_nueva
                    if len(marcos):
                        resaltes.append(marcos)
                    if not paso.error:
                        ultima = eq
                if c.gramatica_activa(self.tema):
                    self.hasta(tr, max(0.0, tr.duration - 0.6))
                    self._cerrar_paso_gramatica(i, paso)
                self._sostener_dibujo(tr)

        self.pila, self.resaltes, self.ultima = pila, resaltes + halos_vivos, ultima
        if self._chip_vivo is not None:
            self._pendientes.append(FadeOut(self._chip_vivo))
            self._chip_vivo = None
            materia = self.cabecera[1] if len(self.cabecera) > 1 else None
            if materia is not None:
                self._pendientes.append(FadeIn(materia))
        self._pendientes += [FadeOut(x) for x in extras_vivos]
        self._pendientes += [FadeOut(r) for r in rotulos.values()]  # el tablero se despeja entero
        if dibujo_vivo is not None:
            self._pendientes.append(FadeOut(dibujo_vivo.mobs))

    def _nota_tapa(self, ancho: float, alto: float, papel: str, centro: np.ndarray) -> VGroup:
        """La tapa como nota adherida: un punto más de color que el fondo, borde fino y esquina doblada.

        Del color exacto del fondo no sirve: en la hoja era un hueco blanco que borraba la rejilla y
        en la pizarra una tabla sin filo. El pliegue se dibujó encima, no recortado: la nota sigue
        tapando el número hasta que la voz llega a él.
        """
        cuerpo = tono_de_tapa(papel, self.col.acento, PROPORCION_TONO_TAPA)
        filo = tono_de_tapa(cuerpo, "#000000", PROPORCION_PLIEGUE)
        nota = RoundedRectangle(corner_radius=0.12, width=ancho, height=alto)
        nota.set_fill(cuerpo, 1.0).set_stroke(filo, 2)
        plegue = (
            Polygon(
                [ancho / 2 - ALTO_PLEGUE, -alto / 2 + 0.07, 0],
                [ancho / 2 - 0.07, -alto / 2 + ALTO_PLEGUE, 0],
                [ancho / 2 - ALTO_PLEGUE, -alto / 2 + ALTO_PLEGUE, 0],
            )
            .set_fill(filo, 1.0)
            .set_stroke(filo, 0)
        )
        return VGroup(nota, plegue).move_to(centro).set_z_index(2)

    def _conclusion(self) -> None:
        """Resultado con conclusión en texto (dato, mito, error): la fórmula, si la hay, va arriba."""
        self._con_conclusion = True
        r = self.guion.resultado
        cabeza, caja, eq, parrafo, cuerpo = _partes_resultado(r, self.tema)
        grupo = VGroup(cabeza, VGroup(caja, cuerpo))
        grupo.move_to([0, (self.tope_pasos + c.Y_ZONA_INFERIOR) / 2 + 0.3, 0])
        emoji = self._emoji(r.emoji, 1.0)
        if emoji is not None:
            self._pegar_en_esquina(emoji, caja, giro=-0.2)
        salen: list[Mobject] = [*self.resaltes]
        for linea in self.pila:
            salen += [m for m in linea.mobs if m is not self.ultima]
        with self.hablar(r.voz, "resultado") as tr:
            mapa = c.coincidencias(self.ultima, eq) if (self.ultima is not None and eq is not None) else None
            if mapa is not None:
                aparecer = [TransformMatchingTex(self.ultima, eq, key_map=mapa)]
            else:
                aparecer = ([Write(eq)] if eq is not None else []) + (
                    [FadeOut(self.ultima)] if self.ultima is not None else []
                )
            if aparecer or salen:
                self._con_pendientes(*[FadeOut(m) for m in salen], *self._tomar_aire(), *aparecer, run_time=0.9)
            visible = Group(caja, *([emoji] if emoji is not None else []))
            entero = 2 * max(abs(visible.get_left()[0]), abs(visible.get_right()[0])) + 2 * HOLGURA_ANCHO
            entero = min(1.0, entero / self.ancho_cuadro)
            escala = max(entero, escala_del_resultado(self._camara_escala, self.modo_camara))
            objetivo = self._encajar_conclusion(Group(grupo, *([emoji] if emoji is not None else [])), escala)
            golpe = self._animaciones_camara(
                objetivo,
                escala,
                run_time=0.55,
                pico=max(entero, pico_del_golpe(self.paisaje, self.ancho_cuadro, self.modo_camara)),
            )
            self.play(
                FadeIn(caja),
                Create(cabeza[0]),
                FadeIn(cabeza[1], shift=UP * 0.1),
                FadeIn(parrafo, shift=UP * 0.1),
                *golpe,
                run_time=0.6,
            )
            completa_desde = self.renderer.time
            self.play(
                Circumscribe(VGroup(caja, cuerpo), color=self.col.acento, fade_out=True, time_width=0.5),
                run_time=1.0,
            )
            if r.destello:
                self.play(*self._destello(caja), run_time=0.7)
            if emoji is not None:
                self.play(self._rebote(emoji))
            self._da_lectura(tr, completa_desde)
        self.bloque_resultado = (
            VGroup(cabeza, caja, cuerpo) if emoji is None else Group(cabeza, caja, cuerpo, emoji)
        )

    def _encajar_conclusion(self, bloque: Mobject, escala: float) -> float:
        """Deja la conclusión entera entre el subtítulo y el techo, ya con la cámara acercada.

        Mide en pantalla (lo que ve el celular): si no cabe se achica; si la cámara no puede ir más
        allá del fondo, se corre el bloque. Devuelve el ``objetivo_y`` para la cámara.
        """
        from .didactica import SEPARACION, piso_de_lectura

        margen = 0.1  # el pico del golpe y la deriva «en mano» se mueven un poco
        piso = piso_de_lectura(self.tema) + margen
        techo = (7.52 if self.tabs_gram is not None else 8.0) - SEPARACION - margen
        quieta = self.modo_camara == "quieta"
        if quieta:
            s, cy = self.camera.frame.width / self.ancho_cuadro, float(self.camera.frame.get_center()[1])
        else:
            minima = ESCALAS.get(self.modo_camara, ESCALAS["suave"])["minima"]
            s, _, _ = encuadre(0.0, escala, self.paisaje, self.alto_cuadro, self.ancho_cuadro, minima)
        k = 1.0 / s
        if bloque.height * k > techo - piso:
            bloque.scale((techo - piso) / (bloque.height * k))
        if not quieta:
            arriba, abajo = bloque.get_top()[1], bloque.get_bottom()[1]
            deseado = min(max(bloque.get_center()[1], arriba - techo / k), abajo - piso / k)
            s, _, cy = encuadre(deseado, escala, self.paisaje, self.alto_cuadro, self.ancho_cuadro, minima)
            k = 1.0 / s
        abajo_pantalla = (bloque.get_bottom()[1] - cy) * k
        arriba_pantalla = (bloque.get_top()[1] - cy) * k
        if abajo_pantalla < piso:
            bloque.shift(UP * (piso - abajo_pantalla) / k)
        elif arriba_pantalla > techo:
            bloque.shift(DOWN * (arriba_pantalla - techo) / k)
        return cy

    def _resultado(self) -> None:
        r = self.guion.resultado
        if r.texto:
            self._conclusion()
            return
        eq = c.ecuacion(r.tex, c.TAM_RESULTADO, self.col.formulas, ancho_max=c.ANCHO_UTIL - 1.0).set_z_index(
            1
        )
        caja = RoundedRectangle(corner_radius=0.22, width=eq.width + 0.9, height=eq.height + 0.7)
        caja.set_fill(self.col.acento, 0.12).set_stroke(self.col.acento, 5)
        eq.move_to(caja)
        cabeza = VGroup(
            c.visto(self.col.exito), c.texto("RESULTADO", c.TAM_ETIQUETA + 2, ULTRABOLD, self.col.exito)
        )
        cabeza.arrange(RIGHT, buff=0.2)
        grupo = VGroup(cabeza, VGroup(caja, eq)).arrange(DOWN, buff=0.32)
        grupo.move_to([0, (self.tope_pasos + c.Y_ZONA_INFERIOR) / 2 + 0.3, 0])
        emoji = self._emoji(r.emoji, 1.0)
        if emoji is not None:  # como sticker pegado en la esquina del recuadro
            self._pegar_en_esquina(emoji, caja, giro=-0.2)
        # La tapa (``tapar_resultado: tapada``): una nota pegada baja sobre la caja y se levanta cuando
        # la voz llega al número. En la hoja es papel sobre papel (se ve la letra desaparecer); en la
        # pizarra es una tarjeta del color del panel.
        papel = self.tema.hoja.color if self.tema.marco == "hoja" else self.col.panel
        barra = (
            self._nota_tapa(caja.width + 0.34, caja.height + 0.34, papel, caja.get_center() + UP * 1.15)
            if self.receta.tapar_resultado == "tapada"
            else None
        )

        salen: list[Mobject] = [*self.resaltes]
        for linea in self.pila:
            salen += [m for m in linea.mobs if m is not self.ultima]
        with self.hablar(r.voz, "resultado") as tr:
            mapa = c.coincidencias(self.ultima, eq) if self.ultima is not None else None
            if mapa is not None:
                aparecer = [TransformMatchingTex(self.ultima, eq, key_map=mapa)]
            else:
                aparecer = [Write(eq)] + ([FadeOut(self.ultima)] if self.ultima is not None else [])
            if barra is not None:
                self.add(barra)
                aparecer.append(barra.animate.move_to(caja))
            if self._titulo_oculto:  # las mitades lo apagaron: el resultado se lee con su título
                aparecer.append(FadeIn(self.titulo))
                self._titulo_oculto = False
            self._con_pendientes(*[FadeOut(m) for m in salen], *self._tomar_aire(), *aparecer, run_time=0.9)
            # La cámara entra al resultado, pero nunca tanto como para cortar el recuadro ni su sticker.
            visible = Group(caja, *([emoji] if emoji is not None else []))
            entero = (2 * max(abs(visible.get_left()[0]), abs(visible.get_right()[0])) + 2 * HOLGURA_ANCHO)
            entero = min(1.0, entero / self.ancho_cuadro)
            golpe = self._animaciones_camara(
                grupo.get_center()[1],
                max(entero, escala_del_resultado(self._camara_escala, self.modo_camara)),
                run_time=0.55,
                pico=max(entero, pico_del_golpe(self.paisaje, self.ancho_cuadro, self.modo_camara)),
            )
            self.play(
                FadeIn(caja),
                Create(cabeza[0]),
                FadeIn(cabeza[1], shift=UP * 0.1),
                *golpe,
                run_time=0.5,
            )
            if barra is not None:
                self.hasta(tr, momento_del_destape(tr.duration))
                self.play(FadeOut(barra, shift=UP * 0.55), run_time=0.45)
            completa_desde = self.renderer.time  # destapado y sin movimiento: acá empieza a leerse
            self.play(
                Circumscribe(VGroup(caja, eq), color=self.col.acento, fade_out=True, time_width=0.5),
                run_time=1.0,
            )
            if r.destello:
                self.play(*self._destello(caja), run_time=0.7)
            if emoji is not None:
                self.play(self._rebote(emoji))
            self._da_lectura(tr, completa_desde)
        # Sin emoji, el mismo grupo vectorial de siempre (idéntico al estilo original)
        self.bloque_resultado = VGroup(cabeza, caja, eq) if emoji is None else Group(cabeza, caja, eq, emoji)

    def _verificacion(self) -> None:
        v = self.guion.verificacion
        etiqueta = c.texto("¿TIENE SENTIDO?", c.TAM_ETIQUETA, ULTRABOLD, self.color_materia)
        cuerpo = c.parrafo(v.texto, 30, MEDIUM, self.col.texto, ancho_max=c.ANCHO_UTIL - 0.3)
        bloque = VGroup(etiqueta, cuerpo).arrange(DOWN, buff=0.2)
        bloque.next_to(self.bloque_resultado, DOWN, buff=0.55)
        if self._con_conclusion:
            self._verificacion_bajo_conclusion(v, etiqueta, bloque)
            return
        subir = max(0.0, Y_SOBRE_SUBTITULOS - bloque.get_bottom()[1])
        emoji = self._emoji(v.emoji, 0.6)
        with self.hablar(v.voz_final, "verificación"):
            animaciones = [FadeIn(bloque.shift(UP * subir), shift=UP * 0.15)]
            if subir:
                animaciones.append(self.bloque_resultado.animate.shift(UP * subir))
            self.play(*animaciones, run_time=0.5)
            if emoji is not None:
                emoji.next_to(etiqueta, RIGHT, buff=0.15)
                self.play(self._rebote(emoji))

    def _verificacion_bajo_conclusion(self, v: Bloque, etiqueta: Mobject, bloque: Mobject) -> None:
        """La verificación después de una conclusión en texto: las dos caben entre el techo de la zona
        de trabajo (bajo el título y los datos) y el subtítulo; si no caben, se achican juntas."""
        juntos = Group(self.bloque_resultado, bloque)
        hueco = self.tope_pasos - Y_SOBRE_SUBTITULOS
        factor = min(1.0, hueco / juntos.height)
        arriba = juntos.get_top()
        fondo = arriba[1] - juntos.height * factor  # el piso de las dos, ya achicadas
        # lo justo para despegar del subtítulo, sin pasar el techo (si ya lo pasaba, baja)
        subir = min(max(0.0, Y_SOBRE_SUBTITULOS - fondo), self.tope_pasos - arriba[1])
        bloque.scale(factor, about_point=arriba).shift(UP * subir)
        emoji = self._emoji(v.emoji, 0.6)
        with self.hablar(v.voz_final, "verificación"):
            animaciones = [FadeIn(bloque, shift=UP * 0.15)]
            if factor < 1.0 or subir:
                animaciones.append(self.bloque_resultado.animate.scale(factor, about_point=arriba).shift(UP * subir))
            self.play(*animaciones, run_time=0.5)
            if emoji is not None:
                emoji.next_to(etiqueta, RIGHT, buff=0.15)
                self.play(self._rebote(emoji))

    def _limpiar_tablero(self) -> list[Animation]:
        """FadeOut de todo menos el fondo y la cabecera.

        Un solo FadeOut sobre un grupo: en Manim, agregar un grupo a la escena "absorbe" a
        sus hijos, así todo sale junto aunque haya objetos anidados (con varios FadeOut
        sueltos, un objeto podía reaparecer al terminar la animación)."""
        quedan = {id(self.fondo), id(self.cabecera)}
        salen = [m for m in self.mobjects if id(m) not in quedan]
        return [FadeOut(Group(*salen))] if salen else []  # Group: la escena puede tener no-vectoriales

    def _reto(self) -> None:
        reto = self.guion.reto
        etiqueta = c.texto("AHORA TÚ", 26, HEAVY, self.col.acento)
        cuerpo = c.parrafo(
            reto.texto,
            c.TAM_CUERPO,
            SEMIBOLD,
            self.col.texto,
            ancho_max=c.ANCHO_UTIL - 0.8,
            alineacion="left",
        )
        contenido = VGroup(etiqueta, cuerpo).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        tarjeta = c.tarjeta(contenido, c.ANCHO_UTIL, self.col.panel, self.color_materia)
        tarjeta.move_to([0, c.CENTRO_ZONA + 0.8, 0])
        emoji = self._emoji(reto.emoji, 1.0)
        if emoji is not None:  # sticker en la esquina de la tarjeta
            emoji.move_to(tarjeta.get_corner(UR) + LEFT * 0.3 + DOWN * 0.1).rotate(0.18)
        with self.hablar(reto.voz_final, "reto"):
            self.play(
                *self._limpiar_tablero(), *self._volver_al_plano(), run_time=0.35
            )  # despejar sin superponer
            self.play(FadeIn(tarjeta, shift=UP * 0.2), run_time=0.45)
            if emoji is not None:
                self.play(self._rebote(emoji))

    def _cierre(self) -> None:
        cierre = self.guion.cierre or Bloque(texto=self.marca.cierre.texto, voz=self.marca.cierre.voz)
        # El guion manda (ej. la mascota de un ejercicio); si no pide sticker, va el de la marca (tu logo).
        elegido = self.marca.sticker_del_cierre(cierre.emoji)
        # En los temas sobrios se apagan los emojis, pero el logo de la marca es identidad: va igual.
        de_la_marca = not cierre.emoji
        sticker = self._emoji(elegido, 1.8, forzar=de_la_marca)
        if dibuja_el_sticker(elegido, de_la_marca, self.tema.emojis) and sticker is None:
            raise ErrorMotor(
                f"El cierre usa el sticker «{elegido}», pero no está en mis_ajustes/stickers/{elegido}.png. "
                "Súbelo en Ajustes → Tus stickers o cambia el nombre en tu marca."
            )
        icono = (
            sticker if sticker is not None else c.engranaje(0.85, self.col.acento, self.col.fondo, dientes=12)
        )
        nombre = c.texto(self.marca.nombre.upper(), 40, HEAVY, self.col.titulos)
        usuario = c.texto(self.marca.usuario, 28, SEMIBOLD, self.col.acento)
        llamado = c.parrafo(cierre.texto, 30, SEMIBOLD, self.col.texto)
        Group(icono, nombre, usuario, llamado).arrange(DOWN, buff=0.38).move_to([0, c.CENTRO_ZONA + 0.7, 0])
        with self.hablar(cierre.voz_final, "cierre") as tr:
            self.play(*self._limpiar_tablero(), *self._volver_al_plano(), run_time=0.35)
            if sticker is not None:
                self.play(self._rebote(sticker, run_time=0.5))
                self.play(
                    FadeIn(nombre, shift=UP * 0.2),
                    FadeIn(usuario),
                    FadeIn(llamado, shift=UP * 0.1),
                    run_time=0.8,
                )
                resto = self._restante(tr)
                if resto > 0.3:
                    self.play(Wiggle(sticker, scale_value=1.06, rotation_angle=0.04 * TAU), run_time=resto)
            else:
                self.play(FadeIn(icono, scale=0.5), run_time=0.4)
                self.play(
                    Rotate(icono, angle=PI / 3),
                    FadeIn(nombre, shift=UP * 0.2),
                    FadeIn(usuario),
                    FadeIn(llamado, shift=UP * 0.1),
                    run_time=0.8,
                )
                resto = self._restante(tr)
                if resto > 0.1:
                    self.play(Rotate(icono, angle=PI / 2, rate_func=lambda t: t), run_time=resto)
        self.wait(0.6)

    def _guardar_linea_de_tiempo(self) -> None:
        datos = {
            "titulo": self.guion.titulo,
            "tema": self.tema.nombre,
            "duracion_total": round(float(self.renderer.time), 3),
            "ancho": config.pixel_width,
            "alto": config.pixel_height,
            "fps": config.frame_rate,
            "bloques": self.bloques_voz,
            "silencio_de_lectura": round(float(self.silencio_de_lectura), 2),
        }
        # Solo para guiones que deciden algo propio: los renders heredados no reciben campos vacíos.
        if self.guion.contenido is not None:
            datos["contenido"] = self.guion.contenido.model_dump()
        if self.op.didactica is not None:
            datos["recursos_didacticos"] = self.op.didactica
        from .entorno import escribir_atomico

        escribir_atomico(self.op.linea_de_tiempo, json.dumps(datos, ensure_ascii=False, indent=2))
