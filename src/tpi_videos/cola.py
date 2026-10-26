"""Cola persistente de lotes: qué se está haciendo, en qué fase va y qué falta.

Vive en ``salida/.cola/trabajos.json`` (fuera de «Mis videos»). La escribe el motor y el panel la lee
para mostrar el avance y reanudar. Sin NiceGUI ni Manim: se prueba entera con ``TPI_RAIZ``.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .entorno import raiz_proyecto
from .errores import ErrorMotor

VERSION = 1

ESTADOS_ACTIVOS = ("redactando", "animando", "subtitulos", "kit")
ESTADOS_PENDIENTES = ("pendiente_ia", "en_cola", "interrumpido")

FASES = {
    "en_cola": "En espera",
    "redactando": "La IA está escribiendo",
    "animando": "Animando",
    "subtitulos": "Subtítulos",
    "kit": "Kit de publicación",
    "esperando_ia": "Esperando conexión",
    "listo": "Listo",
    "fallo": "Falló",
}


def _ruta() -> Path:
    return raiz_proyecto() / "salida" / ".cola" / "trabajos.json"


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _nuevo_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def _renombrar_roto(ruta: Path) -> None:
    destino = ruta.with_name(f"{ruta.name}.roto-{datetime.now():%Y%m%d-%H%M%S}")
    try:
        ruta.replace(destino)
    except OSError:
        pass


def cargar() -> dict[str, Any]:
    """La cola completa, ordenada por fecha. Si el archivo está roto, lo aparta y empieza vacía."""
    ruta = _ruta()
    if not ruta.exists():
        return {"version": VERSION, "lotes": []}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        _renombrar_roto(ruta)
        return {"version": VERSION, "lotes": []}
    if not isinstance(datos, dict) or not isinstance(datos.get("lotes"), list):
        _renombrar_roto(ruta)
        return {"version": VERSION, "lotes": []}
    datos.setdefault("version", VERSION)
    datos["lotes"].sort(key=lambda lote: lote.get("creado", ""))
    return datos


def guardar(datos: dict[str, Any]) -> None:
    """Escribe todo de una vez: si el proceso muere, el archivo anterior sigue válido."""
    if datos.get("version") != VERSION:
        raise ErrorMotor(
            "La cola la escribió una versión más nueva del motor.",
            ayuda="Actualiza el motor (git pull) antes de reanudar estos videos.",
        )
    ruta = _ruta()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f"{ruta.name}.tmp")
    try:
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)


def _lote(datos: dict[str, Any], lote_id: str) -> dict[str, Any] | None:
    return next((lote for lote in datos["lotes"] if lote.get("id") == lote_id), None)


def _video(datos: dict[str, Any], video_id: str) -> dict[str, Any] | None:
    for lote in datos["lotes"]:
        for video in lote.get("videos", []):
            if video.get("id") == video_id:
                return video
    return None


def _ficha_video(lote_id: str, posicion: int, idea: Any) -> dict[str, Any]:
    return {
        "id": f"{lote_id}-{posicion}",
        "posicion": posicion,
        "idea": idea.model_dump() if hasattr(idea, "model_dump") else dict(idea),
        "estado": "en_cola",
        "fase": "en_cola",
        "avance": 0.0,
        "detalle": "En espera",
        "hitos": {},
        "error": None,
        "ayuda": None,
        "intentos": 0,
        "proximo_intento": None,
        "actualizado": _ahora(),
    }


def nuevo_lote(tema: str, ajustes: dict[str, Any], ideas: Any = None) -> str:
    """Crea la ficha del lote antes de pedirle nada a la IA (así se puede reanudar si se cae)."""
    datos = cargar()
    ahora = _ahora()
    lote_id = _nuevo_id()
    lote: dict[str, Any] = {
        "id": lote_id,
        "tema": tema,
        "creado": ahora,
        "actualizado": ahora,
        "estado": "pensando_ideas" if ideas is None else "en_curso",
        "fase": "pensando_ideas" if ideas is None else "en_curso",
        "error": None,
        "ayuda": None,
        "intentos": 0,
        "proximo_intento": None,
        "ajustes": dict(ajustes),
        "videos": [],
    }
    if ideas is not None:
        lote["videos"] = [
            _ficha_video(lote_id, n, idea) for n, idea in enumerate(ideas, start=1)
        ]
    datos["lotes"].append(lote)
    guardar(datos)
    return lote_id


def agregar_videos(lote_id: str, ideas: Any) -> list[str]:
    datos = cargar()
    lote = _lote(datos, lote_id)
    if lote is None:
        raise ErrorMotor(
            "No encuentro ese lote en la cola.",
            ayuda='Vuelve a lanzarlo desde Fábrica o con ./tpi lote "Tema".',
        )
    lote["videos"] = [_ficha_video(lote_id, n, idea) for n, idea in enumerate(ideas, start=1)]
    lote["estado"], lote["fase"] = "en_curso", "en_curso"
    lote["actualizado"] = _ahora()
    guardar(datos)
    return [video["id"] for video in lote["videos"]]


def actualizar_lote(lote_id: str, **campos: Any) -> None:
    datos = cargar()
    lote = _lote(datos, lote_id)
    if lote is None:
        return
    lote.update(campos)
    lote["actualizado"] = _ahora()
    guardar(datos)


def actualizar_video(video_id: str, **campos: Any) -> None:
    datos = cargar()
    video = _video(datos, video_id)
    if video is None:
        return
    video.update(campos)
    video["actualizado"] = _ahora()
    guardar(datos)


def hito(video_id: str, nombre: str, datos_hito: dict[str, Any]) -> None:
    """Lo ya producido (guion, video, kit): es lo que permite no repetir una etapa."""
    datos = cargar()
    video = _video(datos, video_id)
    if video is None:
        return
    video.setdefault("hitos", {})[nombre] = datos_hito
    video["actualizado"] = _ahora()
    guardar(datos)


def videos_del_lote(lote_id: str) -> list[dict[str, Any]]:
    lote = _lote(cargar(), lote_id)
    return list(lote.get("videos", [])) if lote else []


def podar() -> int:
    """Conserva lo pendiente y los últimos 20 videos terminados; los archivos no se tocan."""
    datos = cargar()
    if datos.get("version") != VERSION:
        return 0
    conservar: list[dict[str, Any]] = []
    terminados = 0
    for lote in reversed(datos["lotes"]):
        if lote.get("estado") == "descartado":
            continue
        pendiente = lote.get("estado") != "listo" or any(
            video.get("estado") in ESTADOS_PENDIENTES or video.get("estado") == "fallo"
            for video in lote.get("videos", [])
        )
        if pendiente:
            conservar.append(lote)
            continue
        if terminados < 20:
            conservar.append(lote)
            terminados += sum(
                1 for video in lote.get("videos", []) if video.get("estado") == "listo"
            )
    quitados = len(datos["lotes"]) - len(conservar)
    if quitados:
        datos["lotes"] = list(reversed(conservar))
        guardar(datos)
    return quitados
