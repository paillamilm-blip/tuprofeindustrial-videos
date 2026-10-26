"""Cola persistente de lotes: qué se está haciendo, en qué fase va y qué falta.

Vive en ``salida/.cola/trabajos.json`` (fuera de «Mis videos»). La escribe el motor y el panel la lee
para mostrar el avance y reanudar. Sin NiceGUI ni Manim: se prueba entera con ``TPI_RAIZ``.
"""

from __future__ import annotations

import json
import os
import time
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
    if candado_tomado() and not _candado_es_mio():
        return 0  # hay un lote trabajando: no se reescribe la cola bajo sus pies
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


def _ruta_candado() -> Path:
    return _ruta().parent / "lote.lock"


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # PROCESS_QUERY_LIMITED_INFORMATION: alcanza para preguntar si sigue corriendo
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            codigo = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return False
            return codigo.value == 259  # STILL_ACTIVE: el proceso terminado sigue con su handle abierto
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _candado() -> dict[str, Any] | None:
    try:
        datos = json.loads(_ruta_candado().read_text(encoding="utf-8"))
        return {"pid": int(datos.get("pid", 0)), "inicio": float(datos.get("inicio", 0))}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def candado_tomado() -> bool:
    """¿Hay otro ``tpi lote`` vivo escribiendo la cola? (12 h sin renovar = abandonado)."""
    datos = _candado()
    if datos is None:
        return False
    return _pid_vivo(datos["pid"]) and time.time() - datos["inicio"] < 12 * 3600


def _candado_es_mio() -> bool:
    """``podar`` también corre con el candado puesto (lo toma ``tpi lote --reanudar``)."""
    datos = _candado()
    return datos is not None and datos["pid"] == os.getpid() and candado_tomado()


def tomar_candado() -> bool:
    if candado_tomado() and not _candado_es_mio():
        return False
    ruta = _ruta_candado()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps({"pid": os.getpid(), "inicio": time.time()}), encoding="utf-8"
        )
    except OSError:
        return True  # sin candado se puede trabajar igual; no es motivo para no hacer el video
    return True


def soltar_candado() -> None:
    try:
        _ruta_candado().unlink(missing_ok=True)
    except OSError:
        pass


def estado_derivado(lote: dict[str, Any]) -> str:
    """El estado del lote sale de sus videos: nunca se adivina ni se deja «en curso» de mentira."""
    estados = [video.get("estado") for video in lote.get("videos", [])]
    if not estados:
        return "pendiente_ia" if lote.get("estado") == "pensando_ideas" else lote.get("estado", "en_curso")
    vivos = [estado for estado in estados if estado != "descartado"]
    if not vivos:
        return "descartado"
    if "interrumpido" in vivos:
        return "interrumpido"
    if "pendiente_ia" in vivos:
        return "pendiente_ia"
    if any(estado in ESTADOS_ACTIVOS for estado in vivos):
        return "en_curso"
    if "en_cola" in vivos:
        return "interrumpido"
    if all(estado == "listo" for estado in vivos):
        return "listo"
    if "fallo" in vivos:
        return "fallo"
    return lote.get("estado", "en_curso")


def recalcular_lote(lote_id: str) -> None:
    datos = cargar()
    lote = _lote(datos, lote_id)
    if lote is None or lote.get("estado") == "descartado":
        return
    lote["estado"] = estado_derivado(lote)
    lote["fase"] = lote["estado"]
    lote["actualizado"] = _ahora()
    guardar(datos)


def normalizar_interrumpidos() -> int:
    """Al abrir el panel: lo que quedó a medio hacer pasa a «interrumpido». Respeta el candado."""
    if candado_tomado():
        return 0  # hay un tpi lote vivo: la cola es suya
    datos = cargar()
    if datos.get("version") != VERSION:
        return 0
    cambiados, tocados = 0, 0
    for lote in datos["lotes"]:
        if lote.get("estado") in ("listo", "fallo", "descartado"):
            continue
        for video in lote.get("videos", []):
            if video.get("estado") in ESTADOS_ACTIVOS:
                fase = FASES.get(video.get("fase", ""), "el video")
                porcentaje = round(float(video.get("avance") or 0.0) * 100)
                video["estado"] = "interrumpido"
                video["detalle"] = f"Se interrumpió {fase.lower()} ({porcentaje} %)"
                cambiados += 1
        nuevo = estado_derivado(lote)
        if nuevo != lote.get("estado"):
            tocados += 1
        lote["estado"] = nuevo
        lote["fase"] = nuevo
        lote["actualizado"] = _ahora()
    if cambiados or tocados:  # un lote que solo cambió de estado (sin ideas) igual se guarda
        guardar(datos)
    return cambiados


def pendientes_ia() -> list[dict[str, Any]]:
    return [
        lote
        for lote in cargar()["lotes"]
        if lote.get("estado") == "pendiente_ia"
        or any(video.get("estado") == "pendiente_ia" for video in lote.get("videos", []))
    ]


def elegir_lote(
    solo_pendientes: bool = False, cola_id: str | None = None
) -> dict[str, Any] | None:
    """El lote que hay que retomar: el más antiguo no terminado, o el que se pide por id."""
    lotes = [lote for lote in cargar()["lotes"] if lote.get("estado") != "descartado"]
    if cola_id:
        lote = next((lote for lote in lotes if lote.get("id") == cola_id), None)
        if lote is None:
            raise ErrorMotor(
                "No encuentro ese lote en la cola.",
                ayuda="Mira la tarjeta «Cola de videos» en Fábrica.",
            )
        return lote
    for lote in lotes:
        if lote.get("estado") == "listo":
            continue
        if not solo_pendientes:
            return lote
        videos = lote.get("videos", [])
        if any(video.get("estado") == "interrumpido" for video in videos):
            continue
        if not videos:  # le faltan las 3 ideas: hay que volver a pedirlas (nunca un fallo)
            if lote.get("estado") in ("pensando_ideas", "pendiente_ia"):
                return lote
            continue
        if any(video.get("estado") in ("pendiente_ia", "en_cola") for video in videos):
            return lote
    return None


def ultimo_lote() -> dict[str, Any] | None:
    lotes = [lote for lote in cargar()["lotes"] if lote.get("estado") != "descartado"]
    return lotes[-1] if lotes else None


def lotes_visibles() -> list[dict[str, Any]]:
    lotes = [lote for lote in cargar()["lotes"] if lote.get("estado") != "descartado"]
    if not lotes:
        return []
    ultimo = lotes[-1]
    return [lote for lote in lotes if lote.get("estado") != "listo" or lote is ultimo]


def descartar_lote(lote_id: str) -> None:
    datos = cargar()
    lote = _lote(datos, lote_id)
    if lote is None:
        raise ErrorMotor("No encuentro ese lote en la cola.")
    if lote.get("estado") in ("en_curso", "pensando_ideas") and candado_tomado():
        raise ErrorMotor(
            "Ese lote está trabajando ahora.",
            ayuda="Espera a que termine o cancela el trabajo antes de sacarlo de la cola.",
        )
    lote["estado"], lote["fase"] = "descartado", "descartado"
    lote["actualizado"] = _ahora()
    for video in lote.get("videos", []):
        if video.get("estado") != "listo":
            video["estado"] = "descartado"
    guardar(datos)
