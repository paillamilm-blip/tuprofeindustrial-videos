"""De un tema al video completo: la IA propone 3 ideas, la persona elige y el motor hace todo.

- ``tpi ideas "Teorema de Pitágoras"`` → 3 ideas distintas, cada una con su gancho, su ejercicio con
  números, su nivel y su duración aproximada. Con ``--evitar`` se piden otras 3 sin repetir las visibles.
- ``tpi producir "…"`` → escribe el guion, lo revisa, crea el video final y arma el kit de publicación.

Cada idea trae un ``enunciado`` con números reales: al elegir, ese enunciado entra tal cual a
``redactor.redactar``, que es donde el motor valida el formato, compila las fórmulas y revisa la
matemática. Así la idea solo decide *de qué* es el video; el contenido pasa por las mismas
validaciones que un enunciado escrito por el profesor.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from . import ia
from .emojis import lista_para_ia, normalizar_para_ia, quitar_emojis
from .entorno import PLANTILLAS_DIR
from .errores import ErrorMotor
from .guion import Guion
from .redactor import ResultadoRedaccion, pedir_json, redactar

IDEAS_PETICION = 3

# Ángulo narrativo de cada idea: es lo que las hace distintas entre sí
ANGULOS: dict[str, str] = {
    "error_tipico": "Error típico",
    "aplicacion_real": "Aplicación real",
    "dato_curioso": "Dato curioso",
    "paso_a_paso": "Ejercicio de prueba",
    "reto": "Reto para comentar",
}


class Idea(BaseModel):
    angulo: Literal["error_tipico", "aplicacion_real", "dato_curioso", "paso_a_paso", "reto"] = Field(
        description="Uno de los 5 ángulos; las 3 ideas usan ángulos DISTINTOS"
    )
    titulo: str = Field(description="Nombre corto del video, máximo 45 caracteres")
    gancho: str = Field(description="La pregunta grande del inicio, máximo 10 palabras, con los números")
    enunciado: str = Field(
        description="El ejercicio completo, resuelto con números concretos y todos sus datos: "
        "de 60 a 260 caracteres"
    )
    materia: Literal["matematica", "fisica", "ingenieria"]
    nivel: str = Field(description="Curso al que va, ej. '2° medio' o 'técnico en electricidad'")
    emoji: str = Field(default="", description="1 emoji de la lista permitida (vacío = ninguno)")
    porque: str = Field(description="Una frase: por qué este video funciona en TikTok o Reels")
    segundos: int = Field(description="Duración aproximada del video, entre 30 y 75 segundos")


class PropuestaIA(BaseModel):
    ideas: list[Idea] = Field(description="Exactamente 3 ideas", min_length=3, max_length=3)


def _texto(valor: str) -> str:
    """Los emojis van en su propio campo: dentro de un texto no se dibujan y la voz los leería."""
    return " ".join(quitar_emojis(valor or "").split())


def _idea(idea: Idea, materia: str | None, nivel: str | None) -> Idea:
    """Lo que pide la persona manda sobre lo que deduce la IA; nada de emojis sueltos en los textos."""
    return idea.model_copy(
        update={
            "titulo": _texto(idea.titulo)[:45],
            "gancho": _texto(idea.gancho),
            "enunciado": _texto(idea.enunciado),
            "porque": _texto(idea.porque),
            "materia": materia or idea.materia,
            "nivel": _texto(nivel or idea.nivel),
            "emoji": normalizar_para_ia(idea.emoji) or "",
            "segundos": max(25, min(90, idea.segundos)),
        }
    )


def _limpiar(ideas: Iterable[Idea], materia: str | None, nivel: str | None) -> list[Idea]:
    """Ideas normales, sin repetidas y con un enunciado que sí se puede resolver."""
    limpia: list[Idea] = []
    vistos: set[str] = set()
    for idea in ideas:
        nueva = _idea(idea, materia, nivel)
        clave = nueva.enunciado.casefold().replace(" ", "")[:80]
        if len(nueva.enunciado) < 30 or clave in vistos:
            continue
        vistos.add(clave)
        limpia.append(nueva)
    return limpia


def proponer_ideas(
    tema: str | None = None,
    materia: str | None = None,
    nivel: str | None = None,
    modelo: str = ia.MODELO_POR_DEFECTO,
    evitar: Iterable[str] = (),
    avisar: Callable[[str], None] = lambda mensaje: None,
) -> list[Idea]:
    """Pide 3 ideas a Gemini y devuelve las que sirven (ángulos distintos, enunciado resolvable)."""
    sistema = (
        (PLANTILLAS_DIR / "ia" / "ideas.md")
        .read_text(encoding="utf-8")
        .replace("{{EMOJIS}}", lista_para_ia())
    )
    contenido: list[Any] = [
        f"TEMA: {tema.strip()}" if tema and tema.strip() else "TEMA: elige tú los temas.",
        "Nivel de los estudiantes: {}.".format(nivel or "enseñanza media (Chile)"),
    ]
    if materia:
        contenido.append(f"Materia obligatoria: {materia}.")
    repetidas = [t for t in (evitar or ()) if t and t.strip()]
    if repetidas:
        contenido.append(
            "YA mostraste estas ideas. NO las repitas (ni el mismo ejercicio ni el mismo gancho): "
            + " | ".join(repetidas)
        )
    contenido.append("Responde solo con las 3 ideas pedidas.")

    avisar("Gemini está pensando 3 ideas de video (unos segundos)…")
    respuesta = pedir_json(ia.cliente(), modelo, sistema, contenido, PropuestaIA, "low")
    ideas = _limpiar(respuesta.ideas, materia, nivel)
    if len(ideas) < IDEAS_PETICION:
        raise ErrorMotor(
            f"Gemini devolvió {len(ideas)} idea(s) aprovechable(s) en vez de {IDEAS_PETICION}.",
            ayuda="Repite el comando, o prueba con un tema más concreto (ej. «ley de Ohm»).",
        )
    return ideas[:IDEAS_PETICION]


# ------------------------------------------------------------------------------------------
# De la idea al video completo
# ------------------------------------------------------------------------------------------


@dataclass
class ResultadoProduccion:
    guion: Guion
    ruta_guion: Path
    redaccion: ResultadoRedaccion
    video: Path
    duracion: float
    tema: str
    srt: Path | None
    fuentes_tiempo: set[str]
    portada: Path | None = None
    publicacion: Path | None = None  # publicacion.md del kit
    texto_kit: str | None = None
    kit_aviso: str | None = None


def producir(
    valor: str,
    materia: str | None = None,
    nivel: str | None = None,
    modelo: str = ia.MODELO_POR_DEFECTO,
    nombre: str | None = None,
    forzar: bool = False,
    calidad: str = "final",
    tema: str | None = None,
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    subtitulos: bool = True,
    sincronizar: str = "auto",
    revisar_con_ia: bool = True,
    con_kit: bool = True,
    avisar: Callable[[str], None] = lambda mensaje: None,
    progreso: Callable[[str, float, str], None] | None = None,
) -> ResultadoProduccion:
    """Guion revisado + video + kit de publicación, en un solo llamado.

    Es lo que hace ``tpi ideas`` cuando eliges una idea, y sirve igual con cualquier enunciado.
    """
    from .publicar import crear_kit
    from .render import crear_video

    redaccion = redactar(
        valor,
        materia=materia,
        nivel=nivel,
        modelo=modelo,
        nombre=nombre,
        forzar=forzar,
        revisar_con_ia=revisar_con_ia,
        avisar=avisar,
    )

    avisar(f"Creando el video ({calidad})… puede tardar unos minutos.")
    video = crear_video(
        redaccion.ruta,
        calidad=calidad,
        proveedor=proveedor,
        voz=voz,
        velocidad=velocidad,
        subtitulos=subtitulos,
        sincronizar=sincronizar,
        carpeta_salida=None,
        tema=tema,
        progreso=progreso,
    )

    resultado = ResultadoProduccion(
        guion=redaccion.guion,
        ruta_guion=redaccion.ruta,
        redaccion=redaccion,
        video=video.video,
        duracion=video.duracion,
        tema=video.tema,
        srt=video.srt,
        fuentes_tiempo=video.fuentes_tiempo,
    )

    if con_kit:
        kit = crear_kit(video.carpeta, con_ia=True, modelo=modelo, avisar=avisar)
        resultado.portada = kit.portada
        resultado.publicacion = kit.archivo
        resultado.kit_aviso = kit.aviso
        t = kit.textos
        resultado.texto_kit = (
            f"YouTube: {t.titulo_youtube}\n"
            f"Descripción: {t.descripcion_youtube}\n"
            f"TikTok: {t.texto_tiktok}\n"
            f"Instagram: {t.texto_instagram}\n"
            f"Hashtags: {' '.join(t.hashtags)}"
        )
    return resultado
