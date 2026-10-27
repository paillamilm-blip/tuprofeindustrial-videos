"""De un tema al video completo: la IA propone 3 ideas, la persona elige y el motor hace todo.

- ``tpi ideas "Teorema de Pitágoras"`` → 3 ideas distintas, cada una con su gancho, su ejercicio con
  números, su nivel, su dificultad y su duración aproximada. Con ``--evitar`` se piden otras 3 sin
  repetir las visibles.
- ``tpi producir "…"`` → escribe el guion, lo revisa, crea el video final y arma el kit de publicación.

Cada idea trae un ``enunciado`` con números reales: al elegir, ese enunciado entra tal cual a
``redactor.redactar``, que es donde el motor valida el formato, compila las fórmulas y revisa la
matemática. Así la idea solo decide *de qué* es el video; el contenido pasa por las mismas
validaciones que un enunciado escrito por el profesor.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from . import ia
from .emojis import lista_para_ia, normalizar_para_ia, quitar_emojis
from .entorno import PLANTILLAS_DIR
from .errores import ErrorMotor
from .guion import Gancho, Guion, sin_tildes
from .moldes import moldes_para_ia, normalizar_molde
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

# Qué tan lejos llega el ejercicio. No es un filtro de la IA: decide cuántos pasos y qué trampa tiene.
DIFICULTADES: dict[str, str] = {"facil": "Fácil", "media": "Media", "dificil": "Difícil"}
_DIFICULTAD_OTRAS_PALABRAS = {
    "facil": ("facil", "faciles", "baja", "basico", "basica", "principiante", "intro"),
    "media": ("media", "medio", "medias", "intermedia", "intermedio", "estandar", "normal"),
    "dificil": ("dificil", "dificiles", "alta", "avanzado", "avanzada", "experto", "desafio"),
}
# Lo que la pista le pide al redactor por cada nivel: es la diferencia real entre los tres videos
DIFICULTAD_PISTA = {
    "facil": "una sola fórmula, números redondos y ningún truco: explícalo como si el estudiante "
    "viera el tema por primera vez",
    "media": "el ejercicio estándar de prueba: la fórmula con sus unidades y el despeje completo, "
    "sin saltarse pasos",
    "dificil": "un paso más de lo esperado: un dato que hay que convertir o la trampa que la mayoría "
    "pasa por alto, y nombra esa trampa al resolver",
}

ESTILOS_GANCHO = ("dolor", "curiosidad", "error", "reto", "dato")
_EQUIVALENCIAS_ESTILO = {"desafio": "reto", "miedo": "dolor", "sorpresa": "dato"}


class GanchoIdea(BaseModel):
    """Una variante del primer segundo. El modelo es tolerante; la limpieza fuerte vive en _limpiar."""

    texto: str = ""
    estilo: str = ""
    emoji: str = ""
    tex: str = ""  # fórmula corta bajo el gancho
    voz: str = ""  # si falta, se usa texto


def _estilo(valor: str) -> str:
    limpio = "".join(c for c in sin_tildes(valor or "").casefold() if c.isalnum())
    limpio = _EQUIVALENCIAS_ESTILO.get(limpio, limpio)
    return limpio if limpio in ESTILOS_GANCHO else ""


def dificultad_normal(valor: str | None) -> str:
    """Los tres niveles que conoce el motor, venga como venga lo que escribió la IA (o la persona)."""
    limpio = "".join(
        c
        for c in unicodedata.normalize("NFKD", (valor or "").casefold().replace("_", ""))
        if not unicodedata.combining(c)
    ).strip(" .-")
    for clave, otras in _DIFICULTAD_OTRAS_PALABRAS.items():
        if limpio in otras:
            return clave
    return ""


class Idea(BaseModel):
    angulo: Literal["error_tipico", "aplicacion_real", "dato_curioso", "paso_a_paso", "reto"] = Field(
        description="Uno de los 5 ángulos; las 3 ideas usan ángulos DISTINTOS"
    )
    titulo: str = Field(description="Nombre corto del video, máximo 45 caracteres")
    gancho: str = Field(
        default="", description="La pregunta grande del inicio, máximo 10 palabras, con los números"
    )
    ganchos: list[GanchoIdea] = Field(
        default_factory=list, description="De 3 a 5 variantes del gancho, con estilos distintos"
    )
    molde: str = Field(
        default="", description="Molde narrativo (ver moldes.py); las 3 ideas usan moldes DISTINTOS"
    )
    enunciado: str = Field(
        description="El ejercicio completo, resuelto con números concretos y todos sus datos: "
        "de 60 a 260 caracteres"
    )
    materia: Literal["matematica", "fisica", "ingenieria"]
    nivel: str = Field(description="Curso al que va, ej. '2° medio' o 'técnico en electricidad'")
    dificultad: str = Field(
        default="",
        description="'facil', 'media' o 'dificil'; las 3 ideas usan dificultades DISTINTAS "
        "(no es el curso: es qué tan hondo llega el ejercicio)",
    )
    emoji: str = Field(default="", description="1 emoji de la lista permitida (vacío = ninguno)")
    porque: str = Field(description="Una frase: por qué este video funciona en TikTok o Reels")
    segundos: int = Field(description="Duración aproximada del video, entre 30 y 75 segundos")

    @field_validator("molde", mode="before")
    @classmethod
    def _molde(cls, valor: Any) -> str:
        return normalizar_molde(str(valor)) if valor else ""

    @model_validator(mode="after")
    def _gancho_y_ganchos(self) -> Idea:
        if not self.ganchos and self.gancho.strip():
            self.ganchos = [GanchoIdea(texto=self.gancho.strip(), estilo="curiosidad")]
        if not self.gancho.strip() and self.ganchos:
            self.gancho = self.ganchos[0].texto
        return self


class PropuestaIA(BaseModel):
    ideas: list[Idea] = Field(description="Exactamente 3 ideas", min_length=3, max_length=3)


def _texto(valor: str) -> str:
    """Los emojis van en su propio campo: dentro de un texto no se dibujan y la voz los leería."""
    return " ".join(quitar_emojis(valor or "").split())


def _gancho_limpio(g: GanchoIdea) -> GanchoIdea | None:
    texto = " ".join((g.texto or "").split())
    if not texto or len(texto.split()) > 10 or quitar_emojis(texto) != texto:
        return None
    voz = " ".join((g.voz or "").split())
    if quitar_emojis(voz) != voz:
        return None
    estilo = _estilo(g.estilo)
    if not estilo:
        return None
    try:
        valido = Gancho(texto=texto, voz=voz or None, tex=(g.tex or None))
    except ValidationError:
        return None
    return GanchoIdea(
        texto=texto,
        estilo=estilo,
        emoji=normalizar_para_ia(g.emoji) or "",
        tex=valido.tex or "",
        voz=valido.voz or "",
    )


def _idea(idea: Idea, materia: str | None, nivel: str | None, dificultad: str | None) -> Idea:
    """Lo que pide la persona manda sobre lo que deduce la IA; nada de emojis sueltos en los textos."""
    limpios = [g for g in (_gancho_limpio(x) for x in idea.ganchos) if g is not None]
    unicos: list[GanchoIdea] = []
    vistos: set[str] = set()
    for g in limpios:
        clave = sin_tildes(g.texto).casefold()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(g)
    return idea.model_copy(
        update={
            "titulo": _texto(idea.titulo)[:45],
            # La tarjeta, el CLI y el lote deben mandar el mismo gancho: el primero que queda limpio.
            "gancho": unicos[0].texto if unicos else "",
            "ganchos": unicos[:5],
            "molde": normalizar_molde(idea.molde),
            "enunciado": _texto(idea.enunciado),
            "porque": _texto(idea.porque),
            "materia": materia or idea.materia,
            "nivel": _texto(nivel or idea.nivel),
            "dificultad": dificultad or dificultad_normal(idea.dificultad),
            "emoji": normalizar_para_ia(idea.emoji) or "",
            "segundos": max(25, min(90, idea.segundos)),
        }
    )


def _limpiar(
    ideas: Iterable[Idea], materia: str | None, nivel: str | None, dificultad: str | None = None
) -> list[Idea]:
    """Ideas normales, sin repetidas y con un enunciado que sí se puede resolver."""
    limpia: list[Idea] = []
    vistos: set[str] = set()
    moldes_vistos: set[str] = set()
    for idea in ideas:
        nueva = _idea(idea, materia, nivel, dificultad)
        clave = nueva.enunciado.casefold().replace(" ", "")[:80]
        if len(nueva.enunciado) < 30 or clave in vistos:
            continue
        if len(nueva.ganchos) < 3 or len({g.estilo for g in nueva.ganchos}) < 2:
            continue
        if not nueva.molde or nueva.molde in moldes_vistos:
            continue
        vistos.add(clave)
        moldes_vistos.add(nueva.molde)
        limpia.append(nueva)
    return limpia


def proponer_ideas(
    tema: str | None = None,
    materia: str | None = None,
    nivel: str | None = None,
    dificultad: str | None = None,
    modelo: str = ia.MODELO_POR_DEFECTO,
    evitar: Iterable[str] = (),
    avisar: Callable[[str], None] = lambda mensaje: None,
) -> list[Idea]:
    """Pide 3 ideas a Gemini y devuelve las que sirven (ángulos distintos, enunciado resolvable)."""
    sistema = (
        (PLANTILLAS_DIR / "ia" / "ideas.md")
        .read_text(encoding="utf-8")
        .replace("{{EMOJIS}}", lista_para_ia())
        .replace("{{MOLDES}}", moldes_para_ia())
    )
    contenido: list[Any] = [
        f"TEMA: {tema.strip()}" if tema and tema.strip() else "TEMA: elige tú los temas.",
        "Nivel de los estudiantes: {}.".format(nivel or "enseñanza media (Chile)"),
    ]
    if materia:
        contenido.append(f"Materia obligatoria: {materia}.")
    forzada = dificultad_normal(dificultad)
    if forzada:
        contenido.append(
            f'Las 3 ideas van a dificultad "{forzada}" (NO las repartas esta vez): el ejercicio de cada '
            "una igual tiene que ser distinto."
        )
    repetidas = [t for t in (evitar or ()) if t and t.strip()]
    if repetidas:
        contenido.append(
            "YA mostraste estas ideas. NO las repitas (ni el mismo ejercicio ni el mismo gancho): "
            + " | ".join(repetidas)
        )
    contenido.append("Responde solo con las 3 ideas pedidas.")

    avisar("Gemini está pensando 3 ideas de video (unos segundos)…")
    respuesta = pedir_json(ia.cliente(), modelo, sistema, contenido, PropuestaIA, "low")
    ideas = _limpiar(respuesta.ideas, materia, nivel, forzada or None)
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
    gancho: str | None = None,
    titulo: str | None = None,
    segundos: int | None = None,
    dificultad: str | None = None,
    molde: str | None = None,
    gancho_variante: dict[str, Any] | None = None,
    gancho_variantes: list[dict[str, Any]] | None = None,
    avisar: Callable[[str], None] = lambda mensaje: None,
    progreso: Callable[[str, float, str], None] | None = None,
    reanudar: dict[str, Any] | None = None,
    hito: Callable[[str, dict[str, Any]], None] | None = None,
) -> ResultadoProduccion:
    """Guion revisado + video + kit de publicación, en un solo llamado.

    Es lo que hace ``tpi ideas`` cuando eliges una idea, y sirve igual con cualquier enunciado.
    ``gancho``, ``titulo``, ``segundos`` y ``dificultad`` son los de la idea elegida: se los pasamos a
    ``redactar`` para que el video mantenga el gancho que frenó el scroll, dure lo que anunciamos y
    llegue hondo lo que la tarjeta prometía, en vez de que la IA escriba otro gancho y se vaya a 70 s
    con un ejercicio más fácil de la que uno pidió.
    """
    from .guion import cargar_guion
    from .publicar import crear_kit
    from .redactor import ResultadoRedaccion
    from .render import ResultadoVideo, crear_video

    guardado = reanudar or {}

    pistas = []
    if gancho_variante and str(gancho_variante.get("texto") or "").strip():
        gancho = str(gancho_variante["texto"]).strip()
    if gancho:
        pistas.append(
            f"GANCHO YA ELEGIDO para este video: «{gancho}». Úsalo tal cual (o casi) en gancho_texto "
            "y dilo natural en gancho_voz: es lo que frena el scroll."
        )
    if titulo:
        pistas.append(f"Título pensado para el video: «{titulo}».")
    nivel_dificultad = dificultad_normal(dificultad)
    if nivel_dificultad:
        pistas.append(
            f"DIFICULTAD PEDIDA: {DIFICULTADES[nivel_dificultad]} → {DIFICULTAD_PISTA[nivel_dificultad]}. "
            "No la cambies: el video se anuncia con ese nivel."
        )

    datos_guion = guardado.get("guion") or {}
    ruta_guion = Path(datos_guion["ruta"]) if datos_guion.get("ruta") else None
    if ruta_guion and ruta_guion.exists():
        redaccion = ResultadoRedaccion(
            ruta=ruta_guion,
            guion=cargar_guion(ruta_guion),
            supuestos=list(datos_guion.get("supuestos") or []),
            pendientes=list(datos_guion.get("pendientes") or []),
            rondas=int(datos_guion.get("rondas") or 0),
            modelo=str(datos_guion.get("modelo") or ""),
            revisado_por_ia=bool(datos_guion.get("revisado_por_ia")),
        )
        avisar("El guion ya estaba escrito: no se vuelve a llamar a la IA.")
    else:
        redaccion = redactar(
            valor,
            materia=materia,
            nivel=nivel,
            modelo=modelo,
            nombre=nombre,
            forzar=forzar,
            revisar_con_ia=revisar_con_ia,
            pistas=pistas or None,
            segundos_prometidos=segundos,
            molde=molde,
            gancho_variante=gancho_variante,
            gancho_variantes=gancho_variantes,
            avisar=avisar,
        )
        if hito:
            hito(
                "guion",
                {
                    "ruta": str(redaccion.ruta),
                    "pendientes": list(redaccion.pendientes),
                    "supuestos": list(redaccion.supuestos),
                    "rondas": redaccion.rondas,
                    "modelo": redaccion.modelo,
                    "revisado_por_ia": redaccion.revisado_por_ia,
                },
            )

    datos_video = guardado.get("video") or {}
    ruta_video = Path(datos_video["video"]) if datos_video.get("video") else None
    if ruta_video and ruta_video.exists():
        video = ResultadoVideo(
            video=ruta_video,
            carpeta=Path(datos_video.get("carpeta") or ruta_video.parent),
            duracion=float(datos_video.get("duracion") or 0.0),
            segundos_proceso=float(datos_video.get("segundos_proceso") or 0.0),
            srt=Path(datos_video["srt"]) if datos_video.get("srt") else None,
            fuentes_tiempo=set(datos_video.get("fuentes_tiempo") or []),
            tema=str(datos_video.get("tema") or ""),
        )
        avisar("El video ya estaba creado: solo falta el kit.")
        if progreso:
            progreso("video final", 0.93, "video ya creado")
    else:
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
        if hito:
            hito(
                "video",
                {
                    "video": str(video.video),
                    "carpeta": str(video.carpeta),
                    "duracion": video.duracion,
                    "segundos_proceso": video.segundos_proceso,
                    "srt": str(video.srt) if video.srt else None,
                    "fuentes_tiempo": sorted(video.fuentes_tiempo),
                    "tema": video.tema,
                },
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
        datos_kit = guardado.get("kit") or {}
        archivo_kit = Path(datos_kit["publicacion"]) if datos_kit.get("publicacion") else None
        portada_kit = Path(datos_kit["portada"]) if datos_kit.get("portada") else None
        if archivo_kit and archivo_kit.exists() and portada_kit and portada_kit.exists():
            resultado.portada = portada_kit
            resultado.publicacion = archivo_kit
            resultado.texto_kit = datos_kit.get("texto_kit")
            resultado.kit_aviso = datos_kit.get("aviso")
            if progreso:
                progreso("kit", 1.0, "kit ya creado")
        else:
            if progreso:
                progreso("kit", 0.95, "portada y textos de publicación")
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
            if hito:
                hito(
                    "kit",
                    {
                        "carpeta": str(kit.carpeta),
                        "portada": str(kit.portada),
                        "publicacion": str(kit.archivo),
                        "texto_kit": resultado.texto_kit,
                        "aviso": kit.aviso,
                    },
                )
            if progreso:
                progreso("kit", 1.0, "kit listo")

    return resultado
