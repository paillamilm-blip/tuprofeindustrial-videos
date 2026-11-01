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
    Group,
    Indicate,
    LaggedStart,
    Mobject,
    MovingCameraScene,
    Polygon,
    Rotate,
    RoundedRectangle,
    SurroundingRectangle,
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
from .guion import Bloque, Guion, sin_tildes
from .rodaje import rodaje_de_guion
from .revision import PISO_LECTURA, segundos_a_esperar
from .voces import RESOLUCION, crear_servicio


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


# El tablero partido (``partida: mitades``): arriba el error con su rótulo MITO, abajo la forma
# correcta con REALIDAD. Ninguna de las dos se achica ni sube de sitio; cada línea se escribe en su
# casillero y la cámara se inclina hacia la que está hablando. El casillero es más angosto que la
# hoja entera a propósito: es lo único que le deja a la cámara papel libre para bajar de una mitad
# a la otra, y como además entra, la letra sale del mismo tamaño que en el plano general de siempre.
ANCHO_CASILLERO = 3.9
AIRE_CASILLERO = 0.5

# Los subtítulos se queman después, centrados en el 72 % del alto (y ≈ -1,76). Lo que se escribe
# en pantalla tiene que quedar por encima de esa banda o el subtítulo le pasa por encima.
Y_SOBRE_SUBTITULOS = -1.22
BANDA_SUBTITULO = 0.34  # el tramo del cuadro, midiendo desde abajo, que se lleva el subtítulo quemado
AIRE_DIBUJO = 0.28  # el respiro entre el techo del dibujo y la línea más baja de los pasos


def franja_del_dibujo(
    paisaje: Paisaje, alto_cuadro: float, escala_reposo: float, fondo_papel: float, tope: float
) -> tuple[float, float, float]:
    """(piso de los pasos, centro del dibujo, alto del dibujo) en el plano de reposo.

    El dibujo se apoya en el filo de abajo que le deja el subtítulo quemado, no en el borde del
    papel: en la hoja cuadriculada ese filo queda bastante más arriba, porque el cuadro ya es más
    alto que la hoja y la cámara no tiene a dónde bajar. Si ahí no entra entero, se achica él; los
    pasos se detienen en la reserva de siempre, que es lo que mantiene grande la letra.
    """
    fondo = fondo_papel + d.ALTO_DIBUJO + AIRE_DIBUJO
    piso = max(fondo_papel, paisaje.centro_y - (0.5 - BANDA_SUBTITULO) * alto_cuadro * escala_reposo)
    alto = min(d.ALTO_DIBUJO, min(fondo, tope) - AIRE_DIBUJO - piso)
    return fondo, piso + alto / 2, alto  # fmt: skip


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
    e = min(e, max(MINIMA_PRIMER_PLANO, (fondo - borde_papel) / (BANDA_SUBTITULO * alto_cuadro)))
    objetivo_y = min(objetivo_y, fondo + (0.5 - BANDA_SUBTITULO) * alto_cuadro * e)
    return e, _centro_x(0.0, e, ancho_cuadro, paisaje), _centro_y(objetivo_y, e, alto_cuadro, paisaje)


def casilleros_de_mitades(tope: float, fondo: float) -> dict[str, tuple[float, float, float]]:
    """ ``(etiqueta, línea, alto máximo)`` de cada una de las dos mitades del tablero partido.

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
                "texto": " ".join(remove_bookmarks(datos["input_text"]).split()),
                "audio": str(Path(self.speech_service.cache_dir) / datos["final_audio"]),
                "servicio": servicio,
                # "exactas": vienen del sintetizador; "estimadas": reparto proporcional (sin voz)
                "marcas": "exactas"
                if servicio == "edge-tts" and palabras
                else ("estimadas" if palabras else None),
                "palabras": palabras or None,
            }
        )

    def _da_lectura(self, desde: float) -> None:
        """Estira el bloque hasta que la fórmula lleve su piso de segundos completa y quieta.

        ``desde`` es el instante en que la fórmula dejó de moverse. Con el piso en 0 el video sale
        exactamente como salía antes, que es lo que muestra el «cambiar» cuando se baja.
        """
        espera = segundos_a_esperar(self.op.piso_lectura, self.renderer.time - desde)
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
        """Con la receta «en_mano» la pausa no congela el cuadro: lo desliza mientras espera.

        El deslizamiento dura lo mismo que duraba la pausa, así la cadena de tiempos de la voz queda
        intacta; solo cuesta el redondeo al cuadro siguiente (un frame por pausa). Con la receta quieta
        no hay a dónde moverse y se espera como siempre.
        """
        if stop_condition is None and frozen_frame is None and duration >= PAUSA_MINIMA_DERIVA:
            desliza = self._mover_camara(
                self._camara_escala, self._deriva_base_x, self._deriva_base_y, duration
            )
            if desliza:
                self.play(*desliza, run_time=self.validate_run_time(duration, self.wait, "duration"))
                return
        super().wait(duration, stop_condition, frozen_frame)

    def momento(self, tracker: Any, frase: str) -> float | None:
        """Segundo (dentro del bloque) en que la voz dice ``frase``."""
        texto = " ".join(remove_bookmarks(tracker.data["input_text"]).split())
        idx = sin_tildes(texto.lower()).find(sin_tildes(frase.lower()))
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
        if len(cabeza):
            self._cabecera_fija = cabeza
            # Opacidad de cada pieza: al volver de un golpe hay que devolver la suya (el chip
            # tiene relleno suave y set_opacity(1) lo dejaba como un bloque opaco sin texto).
            self._cabecera_opacidades = [
                (m, m.get_fill_opacity(), m.get_stroke_opacity())
                for m in cabeza.get_family()
                if isinstance(m, VMobject)
            ]

    def _disolver_cabecera(self, visible: bool, run_time: float) -> Animation:
        """Muestra u oculta la cabecera respetando la opacidad propia de cada pieza."""
        registros = self._cabecera_opacidades

        def paso(_mob: Mobject, alpha: float) -> None:
            k = alpha if visible else 1.0 - alpha
            for pieza, relleno, borde in registros:
                pieza.set_fill(opacity=relleno * k)
                pieza.set_stroke(opacity=borde * k)

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
    ) -> list[Animation]:
        """Lleva el cuadro al destino ya calculado; es el único sitio que mueve la cámara.

        Con la receta «en_mano» el destino se traslada el vaivén de la onda: la toma queda un poco
        corrida y un poco más adentro del encuadre que pidió el golpe, que es lo que hace una cámara
        sostenida en la mano. El reposo (``_deriva_base`` y la escala pedida) no se arrastra de una toma
        a la siguiente: si no, el corrimiento se acumularía hasta chocar con el borde del fondo.
        """
        self._deriva_base_x, self._deriva_base_y = centro_x, centro_y
        ancho = escala
        if self.receta.deriva == "en_mano" and self.modo_camara != "quieta":
            self._deriva_t += run_time
            ancho, centro_x, centro_y = encuadre_con_deriva(
                centro_x,
                centro_y,
                escala,
                self._deriva_t,
                self.paisaje,
                self.alto_cuadro,
                self.ancho_cuadro,
            )
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
                colchon = max(
                    0.0, self.paisaje.medio_alto - self.alto_cuadro * cercano / 2 - abs(centro_y)
                )
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
        exceso = sticker.get_right()[0] - (c.ANCHO_UTIL / 2 + 0.35)
        if exceso > 0:
            sticker.shift(LEFT * exceso)

    # --------------------------------------------------------------------------------------
    # Construcción
    # --------------------------------------------------------------------------------------

    def construct(self) -> None:
        c.usar_estilo(self.tema)
        servicio = crear_servicio(self.op.proveedor, self.op.voz, self.op.velocidad)
        self.set_speech_service(servicio, create_subcaption=False)
        self.fondo = c.fondo_tema(self.tema)
        self.add(self.fondo)

        if self.op.solo_gancho:
            self._gancho()
            # El clip es más corto que el video entero: se rellena hasta 4 s para que la vista previa
            # alcance a leerse. El bloque ya dura lo que la voz (también la de silencio, estimada).
            self.wait(max(0.2, 4.0 - self.renderer.time))
            self._guardar_linea_de_tiempo()
            return

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

    def _cabecera(self) -> VGroup:
        if self.tema.marco == "hoja":
            return VGroup()  # "Notas" y "Fecha:" ya están en el marco de la hoja
        icono = c.engranaje(0.17, self.col.acento, self.col.fondo)
        nombre = c.texto(self.marca.nombre.upper(), 19, ULTRABOLD, self.col.titulos)
        izquierda = VGroup(icono, nombre).arrange(RIGHT, buff=0.16)
        izquierda.move_to([0, c.Y_CABECERA, 0]).to_edge(LEFT, buff=0.6)
        materia = c.chip(self.guion.etiqueta_materia, self.color_materia)
        materia.move_to([0, c.Y_CABECERA, 0]).to_edge(RIGHT, buff=0.6)
        return VGroup(izquierda, materia)

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
        emoji = self._emoji(g.emoji, 1.7 * k)
        formula = c.ecuacion(g.tex, c.TAM_ECUACION, self.col.formulas).set_z_index(1) if g.tex else None
        suelto = emoji is None and formula is None
        y = (Y_GANCHO_LLENO if lleno else c.CENTRO_ZONA + (0.9 if suelto else 0.6))
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
                quieto_desde = self.renderer.time
            for frase in destacar:
                letras = c.frase_en_parrafo(p, frase)
                t = self.momento(tr, frase)
                if len(letras) and t is not None:
                    self.hasta(tr, t)
                    self.play(Indicate(letras, color=self.col.acento, scale_factor=1.18), run_time=0.5)
            if emoji is not None and self._restante(tr) > 1.0:
                self.play(Wiggle(emoji, scale_value=1.08, rotation_angle=0.05 * TAU), run_time=0.8)
            if formula is not None:
                self._da_lectura(quieto_desde)
        salen = [m for m in (p, emoji, formula) if m is not None]
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

    def _franja_del_dibujo(self, paso: Any, tope: float) -> tuple[float, float, float]:
        """Hasta dónde baja la pizarra de pasos, y el centro y el alto con los que entra el dibujo."""
        if paso.visual is None:
            return c.Y_ZONA_INFERIOR, 0.0, 0.0
        return franja_del_dibujo(
            self.paisaje,
            self.alto_cuadro,
            escala_base(self.modo_camara),
            c.Y_ZONA_INFERIOR,
            tope,
        )

    def _trazar_dibujo(self, paso: Any, centro_y: float, alto: float, tr: Any) -> d.Dibujo:
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
            dibujo.mobs.add(caja)
            self.add(caja)
        restante = max(self._restante(tr) - 0.5, 1.0)
        if self.receta.partida == "mitades":
            camara = self._toma_de_casillero(dibujo.mobs, aire=0.0)
        else:
            camara = self._animaciones_camara(centro_y, self._camara_escala, run_time=0.55)
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
        return dibujo

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
        reserva = d.ALTO_DIBUJO + AIRE_DIBUJO if any(p.visual is not None for p in self.guion.pasos) else 0.0
        casilleros = casilleros_de_mitades(tope, c.Y_ZONA_INFERIOR + (reserva if mitades else 0.0))
        vivos: dict[str, Linea | None] = {"arriba": None, "abajo": None}
        rotulos: dict[str, Mobject] = {}
        datos_vivos: Mobject | None = getattr(self, "datos_fijos", None) if mitades else None
        pila: list[Linea] = []
        en_historial: set[int] = set()  # líneas ya achicadas (por id de la ecuación)
        resaltes: list[VGroup] = []
        extras_vivos: list[Mobject] = []  # emojis del paso anterior (salen en el siguiente)
        dibujo_vivo: d.Dibujo | None = None  # el dibujo del paso anterior (sale en el siguiente)
        ultima: Any = None  # última ecuación CORRECTA (origen de la transformación)

        for i, paso in enumerate(self.guion.pasos, 1):
            with self.hablar(paso.voz, f"paso {i}") as tr:
                fondo, centro_dibujo, alto_dibujo = self._franja_del_dibujo(paso, tope)
                sale_dibujo = [FadeOut(dibujo_vivo.mobs)] if dibujo_vivo else []
                dibujo_vivo = None
                if paso.tex is None:  # paso solo hablado
                    self._con_pendientes(*[FadeOut(x) for x in extras_vivos], *sale_dibujo, run_time=0.5)
                    extras_vivos = []
                    if paso.visual is not None:
                        dibujo_vivo = self._trazar_dibujo(paso, centro_dibujo, alto_dibujo, tr)
                    elif ultima is not None:
                        self.play(Indicate(ultima, color=self.col.acento, scale_factor=1.04), run_time=0.6)
                    continue

                eq = c.ecuacion(paso.tex, c.TAM_ECUACION, self.col.formulas).set_z_index(1)
                if eq.height > c.ALTO_MAX_ECUACION:
                    eq.scale_to_fit_height(c.ALTO_MAX_ECUACION)
                nota = self._nota(paso)
                # El emoji va a la derecha de la nota (o de la fórmula si no hay nota): se le hace espacio
                emoji = self._emoji(paso.emoji or ("alerta" if paso.error else None), 0.78)
                ancla = nota if nota is not None else eq
                hueco = emoji.width + 0.2 if emoji is not None else 0.0
                # (la fórmula sola ya viene ajustada al ancho por c.ecuacion)
                if (ancla is nota or emoji is not None) and ancla.width > c.ANCHO_UTIL - hueco + 1e-6:
                    ancla.scale_to_fit_width(c.ANCHO_UTIL - hueco)  # una nota larga no se sale de la hoja
                nueva = VGroup(*[m for m in (nota, eq) if m is not None]).arrange(DOWN, buff=0.16)

                # —— Dónde cae cada línea ——————————————————————————————————————————
                # En el modo de siempre las anteriores se achican y se tienuen, y si no caben todas
                # salen las más antiguas. Con las dos mitades cada una tiene su casillero fijo: no se
                # achica nada, la que estaba en ese casillero sale y entra la nueva en su mismo sitio.
                salen: list[Linea] = []
                if mitades:
                    mitad = "arriba" if paso.error else "abajo"
                    y_rotulo, y_linea, alto_max = casilleros[mitad]
                    if nueva.width > ANCHO_CASILLERO:
                        nueva.scale_to_fit_width(ANCHO_CASILLERO)
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
                    ancla.shift(LEFT * hueco / 2)
                    emoji.next_to(ancla, RIGHT, buff=0.2)

                previas: list[Animation] = (
                    [FadeOut(r) for r in resaltes] + [FadeOut(x) for x in extras_vivos] + sale_dibujo
                )
                resaltes, extras_vivos = [], []
                if mitades and datos_vivos is not None:
                    # La cámara vive encima de un casillero: los datos fijos asomarían cortados por
                    # el borde, y cada casillero ya trae su nota con lo que se usa.
                    previas.append(FadeOut(datos_vivos))
                    datos_vivos = None
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
                self.play(*aparecer, run_time=float(np.clip(tr.duration * 0.45, 0.8, 1.6)))
                quieto_desde = self.renderer.time  # desde acá la fórmula ya está completa en pantalla
                if paso.visual is not None:
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
                    quieto_desde = self.renderer.time  # el recuadro y el acercamiento movieron el cuadro

                if paso.error:
                    self.hasta(tr, tr.duration * 0.45)
                    cruz = c.tachado(eq, self.col.error)
                    self.play(Create(cruz), run_time=0.45)
                    quieto_desde = self.renderer.time
                    if not hizo_toma:
                        # La fórmula y su ✗ tiemblan juntas (mismo centro, mismo movimiento).
                        # Si la cámara ya entró al término, ese empujón fue el énfasis y sobra el temblor.
                        temblor = {"scale_value": 1.06, "rotation_angle": 0.02 * TAU}
                        animaciones: list[Animation] = [Wiggle(eq, **temblor), Wiggle(cruz, **temblor)]
                        if emoji is not None:
                            animaciones.append(self._rebote(emoji))
                        self.play(*animaciones, run_time=0.7)
                        quieto_desde = self.renderer.time
                    linea_nueva.mobs.append(cruz)
                    if errores_total:
                        errores_vistos += 1
                        self._chip_de_errores(errores_vistos, errores_total)
                else:
                    self._chip_de_errores(None, 0)  # se cortó la racha: el rincón vuelve a la materia
                    if emoji is not None:
                        self.play(self._rebote(emoji))

                if paso.tex:
                    self._da_lectura(quieto_desde)  # sin esto la fórmula se va antes de terminarla de leer
                if paso.error and receta.error == "sale" and not mitades:
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

        self.pila, self.resaltes, self.ultima = pila, resaltes, ultima
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
        plegue = Polygon(
            [ancho / 2 - ALTO_PLEGUE, -alto / 2 + 0.07, 0],
            [ancho / 2 - 0.07, -alto / 2 + ALTO_PLEGUE, 0],
            [ancho / 2 - ALTO_PLEGUE, -alto / 2 + ALTO_PLEGUE, 0],
        ).set_fill(filo, 1.0).set_stroke(filo, 0)
        return VGroup(nota, plegue).move_to(centro).set_z_index(2)

    def _resultado(self) -> None:
        r = self.guion.resultado
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
            self._con_pendientes(*[FadeOut(m) for m in salen], *self._tomar_aire(), *aparecer, run_time=0.9)
            golpe = self._animaciones_camara(
                grupo.get_center()[1],
                escala_del_resultado(self._camara_escala, self.modo_camara),
                run_time=0.55,
                pico=pico_del_golpe(self.paisaje, self.ancho_cuadro, self.modo_camara),
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
            quieto_desde = self.renderer.time  # destapado y sin movimiento: acá empieza a leerse
            self.play(
                Circumscribe(VGroup(caja, eq), color=self.col.acento, fade_out=True, time_width=0.5),
                run_time=1.0,
            )
            if emoji is not None:
                self.play(self._rebote(emoji))
            self._da_lectura(quieto_desde)
        # Sin emoji, el mismo grupo vectorial de siempre (idéntico al estilo original)
        self.bloque_resultado = VGroup(cabeza, caja, eq) if emoji is None else Group(cabeza, caja, eq, emoji)

    def _verificacion(self) -> None:
        v = self.guion.verificacion
        etiqueta = c.texto("¿TIENE SENTIDO?", c.TAM_ETIQUETA, ULTRABOLD, self.color_materia)
        cuerpo = c.parrafo(v.texto, 30, MEDIUM, self.col.texto, ancho_max=c.ANCHO_UTIL - 0.3)
        bloque = VGroup(etiqueta, cuerpo).arrange(DOWN, buff=0.2)
        bloque.next_to(self.bloque_resultado, DOWN, buff=0.55)
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
        self.op.linea_de_tiempo.parent.mkdir(parents=True, exist_ok=True)
        self.op.linea_de_tiempo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
