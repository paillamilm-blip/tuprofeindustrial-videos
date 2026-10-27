"""Laboratorio de ganchos: clips cortos para elegir el primer segundo antes del video completo.

Reutiliza la escena normal con ``solo_gancho=True``: la hoja, la cabecera, la letra y la voz son las
del video real. No hay pipeline nuevo ni se guardan audios en Git (todo vive en ``salida/``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .entorno import raiz_proyecto
from .errores import ErrorMotor
from .guion import Guion, a_yaml, cabecera_de, cargar_guion, sin_tildes
from .ideas import GanchoIdea, Idea

Progreso = Callable[[str, float, str], None]


def _huella(idea: Idea) -> str:
    base = f"{idea.titulo}|{idea.enunciado}|{[g.texto for g in idea.ganchos]}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def _carpeta(idea: Idea) -> Path:
    """salida/ganchos/<slug>/; si otra idea ya usa ese nombre, agrega -2, -3."""
    from .render import slug

    base = raiz_proyecto() / "salida" / "ganchos" / slug(idea.titulo)
    for n in range(1, 100):
        carpeta = base if n == 1 else base.parent / f"{base.name}-{n}"
        marca = carpeta / "clips.json"
        if not marca.exists():
            return carpeta
        try:
            datos = json.loads(marca.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return carpeta
        if datos.get("huella") == _huella(idea):
            return carpeta
    raise ErrorMotor(
        "Hay demasiadas carpetas de ganchos con el mismo título.",
        ayuda="Borra salida/ganchos/.",
    )


def idea_desde_guion(guion: Guion) -> Idea:
    """El guion ya escrito, con la misma forma que una idea para reutilizar el laboratorio."""
    ganchos = [
        GanchoIdea(
            texto=g.texto,
            estilo="curiosidad" if n == 0 else "dato",
            emoji=g.emoji or "",
            tex=g.tex or "",
            voz=g.voz or "",
        )
        for n, g in enumerate([guion.gancho, *guion.gancho_variantes])
    ]
    return Idea(
        angulo="paso_a_paso",
        titulo=guion.titulo,
        gancho=guion.gancho.texto,
        enunciado=guion.enunciado.texto,
        materia=guion.materia,
        nivel=guion.nivel or "",
        porque="",
        segundos=45,
        molde=guion.molde or "",
        ganchos=ganchos,
    )


def guion_de_vista_previa(idea: Idea, variante: GanchoIdea) -> Guion:
    """Un guion mínimo válido: la escena corta solo dibuja la cabecera y este gancho."""
    datos = {
        "titulo": idea.titulo,
        "materia": idea.materia,
        "nivel": idea.nivel or None,
        "molde": idea.molde or None,
        "gancho": {
            "texto": variante.texto,
            "voz": variante.voz or variante.texto,
            "emoji": variante.emoji or None,
            "tex": variante.tex or None,
        },
        "enunciado": {"texto": idea.enunciado or idea.titulo, "voz": idea.enunciado or idea.titulo},
        "pasos": [{"voz": "Vista previa del gancho.", "nota": "Vista previa"}],
        "resultado": {"tex": "x", "voz": "Vista previa."},
    }
    return Guion.model_validate(datos)


def _manifiesto(idea: Idea, clips: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "titulo": idea.titulo,
        "molde": idea.molde,
        "huella": _huella(idea),
        "clips": clips,
    }


def renderizar_ganchos(
    idea: Idea,
    *,
    calidad: str = "borrador",
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    sin_voz: bool = False,
    progreso: Progreso | None = None,
) -> dict[str, Any]:
    """Un clip por variante, de a uno. El manifiesto se escribe tras cada clip (cancelar no lo pierde)."""
    from .postproduccion import duracion
    from .render import crear_clip_gancho

    variantes = idea.ganchos or [GanchoIdea(texto=idea.gancho, estilo="curiosidad")]
    carpeta = _carpeta(idea)
    carpeta.mkdir(parents=True, exist_ok=True)
    clips: list[dict[str, Any]] = []
    for numero, variante in enumerate(variantes, 1):
        if progreso:
            progreso("animacion", (numero - 1) / len(variantes), f"Gancho {numero} de {len(variantes)}")

        def avance_clip(etapa: str, valor: float, detalle: str, n: int = numero) -> None:
            if progreso:
                progreso(etapa, (n - 1 + valor) / len(variantes), detalle)

        archivo = carpeta / f"gancho-{numero}.mp4"
        crear_clip_gancho(
            guion_de_vista_previa(idea, variante),
            calidad=calidad,
            proveedor="silencio" if sin_voz else proveedor,
            voz="silencio" if sin_voz else voz,
            velocidad=velocidad,
            salida=archivo,
            progreso=avance_clip if progreso else None,
        )
        clips.append(
            {
                "numero": numero,
                "texto": variante.texto,
                "estilo": variante.estilo,
                "emoji": variante.emoji,
                "tex": variante.tex,
                "voz": variante.voz,
                "archivo": str(archivo),
                "segundos": round(duracion(archivo), 1),
            }
        )
        (carpeta / "clips.json").write_text(
            json.dumps(_manifiesto(idea, clips), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _manifiesto(idea, clips)


def elegir_gancho(ruta: str | Path, numero: int) -> Path:
    """Pone la variante N como gancho y guarda la anterior (y las demás) en gancho_variantes."""
    ruta = Path(ruta)
    guion = cargar_guion(ruta)
    lista = [guion.gancho, *guion.gancho_variantes]
    if not 1 <= numero <= len(lista):
        raise ErrorMotor(
            f"No hay un gancho {numero} en {ruta.name}: hay {len(lista)}.",
            ayuda="Mira la lista con: ./tpi ganchos " + ruta.name,
        )
    elegido = lista[numero - 1]
    otras = [g for i, g in enumerate(lista, 1) if i != numero]
    vistos = {sin_tildes(elegido.texto).casefold()}
    alternativas = []
    for g in otras:
        clave = sin_tildes(g.texto).casefold()
        if clave not in vistos:
            vistos.add(clave)
            alternativas.append(g.model_dump(exclude_none=True))
    datos = guion.model_dump()
    datos["gancho"] = elegido.model_dump(exclude_none=True)
    datos["gancho_variantes"] = alternativas[:5]
    ruta.write_text(a_yaml(datos, cabecera_de(ruta)), encoding="utf-8")
    cargar_guion(ruta)  # comprueba que lo escrito se lee igual
    return ruta
