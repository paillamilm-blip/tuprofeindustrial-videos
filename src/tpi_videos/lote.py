"""De un tema, los 3 videos de una sola pasada: guion + video final + kit de cada idea.

El lote no repite el pipeline: da vueltas sobre ``ideas.producir``, que ya escribe el guion, lo revisa,
compila las fórmulas, renderiza y arma el kit. Lo único que agrega acá es el orden (de uno en uno, porque
los renders pelean por la misma máquina), el progreso global (un tercio por video) y la espera con reintento
cuando Gemini está saturado.

Una idea que falla no corta el lote: se anota el motivo y sigue la siguiente. Lo que alcanzó a salir queda
en ``salida/`` y lo que no se lista al final, con la tarjeta de la idea intacta para reintentarla.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .errores import ErrorMotor
from .ideas import Idea, ResultadoProduccion, producir

INTENTOS_POR_IDEA = 2  # el segundo solo vale si el error se arregla esperando
ESPERA_ENTRE_INTENTOS = 60.0  # s: un límite de uso de Gemini se levanta en minutos, no en segundos

# progreso(etapa, avance 0–1 del lote completo, detalle ya explicado para el usuario)
Progreso = Callable[[str, float, str], None]


@dataclass
class ItemLote:
    """El resultado de una idea dentro del lote: video si salió, motivo si no."""

    idea: Idea
    ok: bool
    guion: Path | None = None
    video: Path | None = None
    portada: Path | None = None
    publicacion: Path | None = None
    duracion: float = 0.0
    promesa_incumplida: bool = False
    pendientes: list[str] = field(default_factory=list)
    error: str | None = None
    ayuda: str | None = None
    intentos: int = 1

    def como_dict(self) -> dict[str, object]:
        return {
            "titulo": self.idea.titulo,
            "angulo": self.idea.angulo,
            "emoji": self.idea.emoji,
            "ok": self.ok,
            "guion": self.guion,
            "video": self.video,
            "portada": self.portada,
            "publicacion": self.publicacion,
            "duracion": round(self.duracion, 1),
            "prometido": self.idea.segundos,
            "promesa_incumplida": self.promesa_incumplida,
            "pendientes": self.pendientes,
            "error": self.error,
            "ayuda": self.ayuda,
            "intentos": self.intentos,
        }


def ideas_desde_json(texto: str) -> list[Idea]:
    """Las 3 ideas que el panel ya tiene en pantalla, para no volver a pedirle nada a Gemini."""
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorMotor("El lote no entendió las ideas que le pasaron.", ayuda=f"JSON inválido: {e}") from e
    lista = datos.get("ideas") if isinstance(datos, dict) else datos
    if not isinstance(lista, list) or not lista:
        raise ErrorMotor(
            "El lote no recibió ninguna idea.",
            ayuda='Ej. ./tpi lote "Porcentajes" (las ideas las busca Gemini) o usa el panel.',
        )
    return [Idea.model_validate(i) for i in lista]


def _item(idea: Idea, resultado: ResultadoProduccion) -> ItemLote:
    from .redactor import promesa_incumplida as se_paso_de_largo

    return ItemLote(
        idea=idea,
        ok=True,
        guion=resultado.ruta_guion,
        video=resultado.video,
        portada=resultado.portada,
        publicacion=resultado.publicacion,
        duracion=resultado.duracion,
        promesa_incumplida=se_paso_de_largo(resultado.duracion, idea.segundos),
        pendientes=list(resultado.redaccion.pendientes),
    )


def producir_lote(
    ideas: Sequence[Idea],
    *,
    materia: str | None = None,
    nivel: str | None = None,
    modelo: str | None = None,
    calidad: str = "final",
    estilo: str | None = None,
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    subtitulos: bool = True,
    sincronizar: str = "auto",
    revisar_con_ia: bool = True,
    con_kit: bool = True,
    espera: float = ESPERA_ENTRE_INTENTOS,
    avisar: Callable[[str], None] = lambda mensaje: None,
    progreso: Progreso | None = None,
) -> list[ItemLote]:
    """Produce las ideas de a una y devuelve un ``ItemLote`` por cada una, en el mismo orden.

    ``nivel`` puede venir de cada idea (``idea.nivel``): lo que la persona eligió en el comando gana.
    ``espera`` son los segundos antes del reintento; con ``0`` el lote no espera nada.
    """
    total = len(ideas)
    items: list[ItemLote] = []

    for posicion, idea in enumerate(ideas, start=1):
        avance_local, paso, aviso = _emitidores(posicion, total, progreso, avisar)

        items.append(
            _una_idea(
                idea,
                materia=materia,
                nivel=nivel,
                modelo=modelo,
                calidad=calidad,
                estilo=estilo,
                proveedor=proveedor,
                voz=voz,
                velocidad=velocidad,
                subtitulos=subtitulos,
                sincronizar=sincronizar,
                revisar_con_ia=revisar_con_ia,
                con_kit=con_kit,
                espera=espera,
                avisar=aviso,
                progreso=avance_local,
                paso=paso,
            )
        )
    return items


def _emitidores(
    posicion: int,
    total: int,
    progreso: Progreso | None,
    avisar: Callable[[str], None],
) -> tuple[Progreso, Callable[[str, str], None], Callable[[str], None]]:
    """Los tres emisores de avance de un video del lote.

    ``avance_local`` convierte el 0–1 de un video en el 0–1 del lote completo (cada video pesa lo mismo) y
    le pone delante «Video 2 de 3», que es lo que la barra del panel alcanza a mostrar. ``paso`` es para los
    momentos sin progreso numérico (arranca la idea, se espera antes de reintentar) y ``aviso`` recibe los
    mensajes sueltos de Gemini para que también digan de qué video hablamos. En la terminal el prefijo sobra
    porque ahí ya separa la línea «Voy con «…»»; en el panel, sin él, no se sabe en qué video vamos.
    """
    etiqueta = f"Video {posicion} de {total}"
    base = (posicion - 1) / total

    def avance_local(etapa: str, avance: float, detalle: str) -> None:
        if progreso:
            progreso(etapa, round(base + avance / total, 3), f"{etiqueta} · {detalle}")

    def paso(etapa: str, detalle: str) -> None:
        if progreso:
            progreso(etapa, base, f"{etiqueta} · {detalle}")
        else:
            avisar(detalle)

    def aviso(detalle: str) -> None:
        paso("redactando", detalle)

    return avance_local, paso, aviso


def _una_idea(
    idea: Idea,
    *,
    materia: str | None,
    nivel: str | None,
    modelo: str | None,
    calidad: str,
    estilo: str | None,
    proveedor: str | None,
    voz: str | None,
    velocidad: str | None,
    subtitulos: bool,
    sincronizar: str,
    revisar_con_ia: bool,
    con_kit: bool,
    espera: float,
    avisar: Callable[[str], None],
    progreso: Progreso | None,
    paso: Callable[[str, str], None],
) -> ItemLote:
    """Una idea, con su reintento. Nunca lanza: devuelve el ItemLote con el motivo si no salió."""
    from .ia import MODELO_POR_DEFECTO

    for intento in range(1, INTENTOS_POR_IDEA + 1):
        paso("redactando", f"Voy con «{idea.titulo}» ({idea.angulo.replace('_', ' ')})")
        try:
            resultado = producir(
                idea.enunciado,
                materia=materia or idea.materia,
                nivel=nivel or idea.nivel,
                modelo=modelo or MODELO_POR_DEFECTO,
                calidad=calidad,
                tema=estilo,
                proveedor=proveedor,
                voz=voz,
                velocidad=velocidad,
                subtitulos=subtitulos,
                sincronizar=sincronizar,
                revisar_con_ia=revisar_con_ia,
                con_kit=con_kit,
                gancho=idea.gancho,
                titulo=idea.titulo,
                segundos=idea.segundos,
                avisar=avisar,
                progreso=progreso,
            )
            return _item(idea, resultado)
        except ErrorMotor as e:
            if not e.transitorio or intento == INTENTOS_POR_IDEA or espera <= 0:
                return _fallo(idea, e, intento)
            paso(
                "redactando",
                f"espero {espera:.0f} s y reintento (intento {intento + 1} de {INTENTOS_POR_IDEA})",
            )
            time.sleep(espera)  # la espera se corta con Ctrl-C o con Cancelar del panel  # fmt: skip
        except Exception as e:  # un error inesperado no debe llevarse los otros dos videos
            return _fallo(idea, e, intento)
    raise AssertionError("el lote siempre devuelve un ítem por idea")


def _fallo(idea: Idea, error: Exception, intentos: int) -> ItemLote:
    if isinstance(error, ErrorMotor):
        mensaje, ayuda = error.mensaje, error.ayuda
    else:
        mensaje, ayuda = f"Error inesperado: {error}", "Repite con esta idea; si sigue, avísale a Kiro."
    return ItemLote(idea=idea, ok=False, error=mensaje, ayuda=ayuda, intentos=intentos)
