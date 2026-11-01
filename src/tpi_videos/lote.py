"""De un tema, los 3 videos de una sola pasada: guion + video final + kit de cada idea.

El lote no repite el pipeline: da vueltas sobre ``ideas.producir``, que ya escribe el guion, lo revisa,
compila las fórmulas, renderiza y arma el kit. Lo que agrega acá es el orden (de uno en uno, porque los
renders pelean por la misma máquina), el progreso por video, la cola persistente y la espera sin límite
cuando Gemini no responde.

Una idea que falla no corta el lote: se anota el motivo y sigue la siguiente. Si la IA se cae, el video
queda pendiente, el lote se pausa y al volver se retoma sin repetir lo que ya se produjo.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .errores import ErrorMotor
from .ideas import Idea, ResultadoProduccion, producir

ESPERA_ENTRE_INTENTOS = 60.0  # s: un límite de uso de Gemini se levanta en minutos, no en segundos
ESPERA_LARGA = 300.0  # s: después del segundo reintento, cada 5 minutos

# progreso(etapa, avance 0–1 del lote completo, detalle ya explicado para el usuario, **video)
Progreso = Callable[..., None]

ESTADO_DE_FASE = {
    "redactando": "redactando",
    "animando": "animando",
    "subtitulos": "subtitulos",
    "video final": "animando",
    "kit": "kit",
}


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
    lectura: float = 0.0
    promesa_incumplida: bool = False
    pendientes: list[str] = field(default_factory=list)
    error: str | None = None
    ayuda: str | None = None
    intentos: int = 1
    pendiente: bool = False

    def como_dict(self) -> dict[str, object]:
        return {
            "titulo": self.idea.titulo,
            "angulo": self.idea.angulo,
            "dificultad": self.idea.dificultad,
            "molde": self.idea.molde,
            "emoji": self.idea.emoji,
            # la idea completa detrás del ítem: así el panel reintenta una sin volverle a pedir nada a Gemini
            "idea": self.idea.model_dump(),
            "ok": self.ok,
            "guion": self.guion,
            "video": self.video,
            "portada": self.portada,
            "publicacion": self.publicacion,
            "duracion": round(self.duracion, 1),
            "lectura": round(self.lectura, 1),
            "prometido": self.idea.segundos,
            "promesa_incumplida": self.promesa_incumplida,
            "pendientes": self.pendientes,
            "error": self.error,
            "ayuda": self.ayuda,
            "intentos": self.intentos,
            "pendiente": self.pendiente,
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


def espera_del_intento(intento: int, primera: float) -> float:
    """La primera espera la elige la persona; después 2 min, 5 min y cada 5 min."""
    if intento <= 1:
        return primera
    if intento == 2:
        return 120.0
    return ESPERA_LARGA


def hora_en(segundos: float) -> str:
    return (datetime.now() + timedelta(seconds=segundos)).isoformat(timespec="seconds")


def texto_espera(segundos: float) -> str:
    minutos = round(segundos / 60)
    return f"{minutos} min" if minutos >= 1 else f"{round(segundos)} s"


def _item(idea: Idea, resultado: ResultadoProduccion, intentos: int = 1) -> ItemLote:
    from .redactor import promesa_incumplida as se_paso_de_largo

    return ItemLote(
        idea=idea,
        ok=True,
        guion=resultado.ruta_guion,
        video=resultado.video,
        portada=resultado.portada,
        publicacion=resultado.publicacion,
        duracion=resultado.duracion,
        lectura=resultado.lectura,
        promesa_incumplida=se_paso_de_largo(resultado.duracion, idea.segundos, resultado.lectura),
        pendientes=list(resultado.redaccion.pendientes),
        intentos=intentos,
    )


def _guardar(avisar: Callable[[str], None]) -> Callable[..., None]:
    """Escribe en la cola sin botar el video si el disco no deja: avisa una vez y sigue."""
    avisado = {"ya": False}

    def seguro(accion: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        try:
            accion(*args, **kwargs)
        except OSError:
            if not avisado["ya"]:
                avisado["ya"] = True
                avisar("No pude guardar la cola: si cierras el panel, este trabajo no se podrá reanudar.")

    return seguro


class _Ficha:
    """Escribe el avance de un video en la cola, con freno para no reescribir el JSON en cada evento."""

    def __init__(self, ficha: dict[str, Any], escribir: Callable[..., None]) -> None:
        self.video_id = ficha["id"]
        self.hitos: dict[str, Any] = ficha.setdefault("hitos", {})
        self._escribir = escribir
        self._ultima = 0.0
        self._fase = ""

    def etapa(self, fase: str, estado: str, avance: float, detalle: str) -> None:
        from . import cola

        ahora = time.time()
        if fase == self._fase and ahora - self._ultima < 5:
            return
        self._fase, self._ultima = fase, ahora
        self._escribir(
            cola.actualizar_video,
            self.video_id,
            fase=fase,
            estado=estado,
            avance=round(avance, 3),
            detalle=detalle,
        )

    def hito(self, nombre: str, datos: dict[str, Any]) -> None:
        from . import cola

        self.hitos[nombre] = datos
        self._escribir(cola.hito, self.video_id, nombre, datos)

    def pendiente(self, intento: int, segundos: float) -> None:
        from . import cola

        self._escribir(
            cola.actualizar_video,
            self.video_id,
            estado="pendiente_ia",
            fase="esperando_ia",
            intentos=intento,
            proximo_intento=hora_en(segundos),
            detalle=f"Sin conexión con la IA: reintento en {texto_espera(segundos)}",
        )


def producir_lote(
    ideas: Sequence[Idea],
    *,
    materia: str | None = None,
    nivel: str | None = None,
    dificultad: str | None = None,
    modelo: str | None = None,
    calidad: str = "final",
    estilo: str | None = None,
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    piso: float | None = None,
    subtitulos: bool = True,
    sincronizar: str = "auto",
    revisar_con_ia: bool = True,
    con_kit: bool = True,
    espera: float = ESPERA_ENTRE_INTENTOS,
    cola_id: str | None = None,
    dormir: Callable[[float], None] = time.sleep,
    reintentos: int | None = None,
    avisar: Callable[[str], None] = lambda mensaje: None,
    progreso: Progreso | None = None,
) -> list[ItemLote]:
    """Produce las ideas de a una y devuelve un ``ItemLote`` por cada una, en el mismo orden.

    Con ``cola_id`` el avance y los hitos quedan en la cola. ``espera=0`` marca el video pendiente sin
    dormir (tests y quien no quiere esperar); ``reintentos=None`` reintenta mientras el proceso viva.
    """
    from . import cola

    total = len(ideas)
    items: list[ItemLote] = []
    fichas = {ficha["posicion"]: ficha for ficha in cola.videos_del_lote(cola_id)} if cola_id else {}
    escribir = _guardar(avisar)

    for posicion, idea in enumerate(ideas, start=1):
        ficha = fichas.get(posicion)
        seguir = _Ficha(ficha, escribir) if ficha else None
        avance_local, paso, aviso = _emitidores(posicion, total, progreso, avisar, seguir)
        if ficha:
            escribir(
                cola.actualizar_video,
                ficha["id"],
                estado="redactando",
                fase="redactando",
                avance=0.05,
                detalle="La IA está escribiendo…",
                proximo_intento=None,
            )
        item = _una_idea(
            idea,
            materia=materia,
            nivel=nivel,
            dificultad=dificultad,
            modelo=modelo,
            calidad=calidad,
            estilo=estilo,
            proveedor=proveedor,
            voz=voz,
            velocidad=velocidad,
            piso=piso,
            subtitulos=subtitulos,
            sincronizar=sincronizar,
            revisar_con_ia=revisar_con_ia,
            con_kit=con_kit,
            espera=espera,
            dormir=dormir,
            reintentos=reintentos,
            reanudar=ficha.setdefault("hitos", {}) if ficha else {},
            hito=seguir.hito if seguir else None,
            avisar=aviso,
            progreso=avance_local,
            paso=paso,
            esperar=lambda intento, segundos, _s=seguir, _p=paso: _esperar_ia(_s, _p, intento, segundos),
        )
        items.append(item)
        if ficha:
            if item.ok:
                escribir(
                    cola.actualizar_video,
                    ficha["id"],
                    estado="listo",
                    fase="listo",
                    avance=1.0,
                    detalle="Listo",
                    intentos=item.intentos,
                    error=None,
                    ayuda=None,
                )
            elif item.pendiente:
                escribir(
                    cola.actualizar_video,
                    ficha["id"],
                    estado="pendiente_ia",
                    fase="esperando_ia",
                    error=item.error,
                    ayuda=item.ayuda,
                    intentos=item.intentos,
                )
                break
            else:
                escribir(
                    cola.actualizar_video,
                    ficha["id"],
                    estado="fallo",
                    fase="fallo",
                    error=item.error,
                    ayuda=item.ayuda,
                    intentos=item.intentos,
                )
    if cola_id:
        escribir(cola.recalcular_lote, cola_id)
    return items


def _esperar_ia(
    seguir: _Ficha | None,
    paso: Callable[[str, str], None],
    intento: int,
    segundos: float,
) -> None:
    paso("esperando_ia", f"Sin conexión con la IA: reintento en {texto_espera(segundos)}")
    if seguir:
        seguir.pendiente(intento, segundos)


def _traducir(etapa: str, avance: float) -> tuple[str, float]:
    """De las etapas del render a la fase y el 0–1 visibles del video."""
    if etapa in ("preparando", "animacion"):
        return "animando", 0.25 + 0.65 * max(0.0, min(1.0, avance))
    if etapa == "subtitulos":
        return "subtitulos", 0.90
    if etapa in ("video final", "listo"):
        return "video final", 0.93
    if etapa == "kit":
        return "kit", max(0.95, min(1.0, avance))
    return "redactando", 0.05


def _emitidores(
    posicion: int,
    total: int,
    progreso: Progreso | None,
    avisar: Callable[[str], None],
    seguir: _Ficha | None = None,
) -> tuple[Progreso, Callable[[str, str], None], Callable[[str], None]]:
    """Los tres emisores de avance de un video del lote, con su número y su 0–1 propio."""
    etiqueta = f"Video {posicion} de {total}"
    ultimo = {"avance": 0.0, "fase": "redactando", "estado": "redactando"}

    def emitir(etapa: str, detalle: str, fase: str, estado: str, video_avance: float | None = None) -> None:
        if video_avance is not None:
            ultimo["avance"] = max(ultimo["avance"], video_avance)
        ultimo["fase"], ultimo["estado"] = fase, estado
        if progreso:
            progreso(
                etapa,
                round(((posicion - 1) + ultimo["avance"]) / total, 3),
                f"{etiqueta} · {detalle}",
                video=posicion,
                total=total,
                video_avance=round(ultimo["avance"], 3),
                fase=fase,
                estado=estado,
            )
        if seguir and estado != "pendiente_ia":
            seguir.etapa(fase, estado, ultimo["avance"], detalle)

    def avance_local(etapa: str, avance: float, detalle: str) -> None:
        fase, valor = _traducir(etapa, avance)
        emitir(etapa, detalle, fase, ESTADO_DE_FASE.get(fase, "redactando"), valor)

    def paso(etapa: str, detalle: str) -> None:
        if etapa == "esperando_ia":
            emitir(etapa, detalle, "esperando_ia", "pendiente_ia")
        elif etapa == "redactando":
            emitir(etapa, detalle, "redactando", "redactando", 0.05)
        else:
            emitir(etapa, detalle, etapa, ESTADO_DE_FASE.get(etapa, etapa))
        if not progreso:
            avisar(detalle)

    def aviso(detalle: str) -> None:
        if progreso:
            # Reemite con la fase y el avance actuales: un aviso del kit no hace retroceder la barra.
            emitir(ultimo["fase"], detalle, ultimo["fase"], ultimo["estado"])
        else:
            avisar(detalle)

    return avance_local, paso, aviso


def _una_idea(
    idea: Idea,
    *,
    materia: str | None,
    nivel: str | None,
    dificultad: str | None,
    modelo: str | None,
    calidad: str,
    estilo: str | None,
    proveedor: str | None,
    voz: str | None,
    velocidad: str | None,
    piso: float | None,
    subtitulos: bool,
    sincronizar: str,
    revisar_con_ia: bool,
    con_kit: bool,
    espera: float,
    dormir: Callable[[float], None],
    reintentos: int | None,
    reanudar: dict[str, Any],
    hito: Callable[[str, dict[str, Any]], None] | None,
    avisar: Callable[[str], None],
    progreso: Progreso | None,
    paso: Callable[[str, str], None],
    esperar: Callable[[int, float], None],
) -> ItemLote:
    """Una idea, con su espera. Nunca lanza: devuelve el ItemLote con el motivo si no salió."""
    from .ia import MODELO_POR_DEFECTO

    intento = 0
    while True:
        intento += 1
        paso("redactando", f"Voy con «{idea.titulo}» ({idea.angulo.replace('_', ' ')})")
        try:
            resultado = producir(
                idea.enunciado,
                materia=materia or idea.materia,
                nivel=nivel or idea.nivel,
                dificultad=dificultad or idea.dificultad or None,
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
                molde=idea.molde or None,
                gancho_variante=idea.ganchos[0].model_dump() if idea.ganchos else None,
                gancho_variantes=[g.model_dump() for g in idea.ganchos] or None,
                titulo=idea.titulo,
                segundos=idea.segundos,
                piso=piso,
                avisar=avisar,
                progreso=progreso,
                reanudar=reanudar,
                hito=hito,
            )
            return _item(idea, resultado, intento)
        except ErrorMotor as e:
            if not e.transitorio:
                return _fallo(idea, e, intento)
            if espera <= 0 or (reintentos is not None and intento > reintentos):
                return _pendiente(idea, e, intento)
            segundos = espera_del_intento(intento, espera)
            esperar(intento, segundos)
            dormir(segundos)  # la espera se corta con Ctrl-C o con Cancelar del panel  # fmt: skip
        except Exception as e:  # un error inesperado no debe llevarse los otros dos videos
            return _fallo(idea, e, intento)


def _fallo(idea: Idea, error: Exception, intentos: int) -> ItemLote:
    if isinstance(error, ErrorMotor):
        mensaje, ayuda = error.mensaje, error.ayuda
    else:
        mensaje, ayuda = f"Error inesperado: {error}", "Repite con esta idea; si sigue, avísale a Kiro."
    return ItemLote(idea=idea, ok=False, error=mensaje, ayuda=ayuda, intentos=intentos)


def _pendiente(idea: Idea, error: ErrorMotor, intentos: int) -> ItemLote:
    return ItemLote(
        idea=idea,
        ok=False,
        pendiente=True,
        intentos=intentos,
        error=error.mensaje,
        ayuda="Queda en la cola: se reanuda solo cuando vuelva la conexión con la IA.",
    )
