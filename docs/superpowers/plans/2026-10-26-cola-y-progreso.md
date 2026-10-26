# Cola persistente, progreso por video y reanudación · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el lote guarde en disco qué video va en qué fase, muestre una barra por video en la Fábrica y se reanude solo cuando la IA vuelva, sin repetir lo que ya se produjo.

**Architecture:** Un módulo nuevo `cola.py` (solo stdlib) persiste lotes, videos, estados e hitos en `salida/.cola/trabajos.json` con escritura atómica y un candado de proceso. `ideas.producir()` acepta `reanudar` (hitos) y `hito` (callback), `lote.producir_lote()` escribe la cola y espera a la IA sin límite, el CLI expone `--reanudar` y el panel lee la cola para dibujar barras por video y una tarjeta «Cola de videos».

**Tech Stack:** Python 3.11+, PyYAML, pydantic v2, stdlib `unittest`, NiceGUI (solo panel), rich (CLI).

**Spec:** `docs/superpowers/specs/2026-10-26-cola-y-progreso-design.md`

## Global Constraints

- Versión del paquete: **0.10.0** (`pyproject.toml` y `src/tpi_videos/__init__.py`).
- Sin dependencias nuevas: la cola usa solo `json`, `os`, `uuid`, `datetime`, `pathlib` y `time`.
- Todo el texto que ve el usuario va **en español claro**, sin trazas técnicas.
- Los tests usan `unittest` de la biblioteca estándar y no importan Manim ni NiceGUI.
- `TPI_RAIZ` redirige `entorno.raiz_proyecto()`: úsalo en los tests para no tocar `salida/` real.
- En este computador el paquete no está instalado en modo editable: antepón `PYTHONPATH=src` a los comandos `python -m unittest …` y `python -m tpi_videos …` (en CI no hace falta).
- No se toca `escena.py`, los temas ni el diseño de los videos: esta fase es estado, progreso y reanudación.
- El panel sigue escuchando solo en `127.0.0.1`.
- Un solo lote escribe la cola a la vez (candado `salida/.cola/lote.lock`).
- Las escrituras de avance se frenan: fase nueva o cada 5 s como máximo; los hitos y los cambios de estado se escriben siempre.

---

### Task 1: Cola persistente (archivo, estados, hitos y poda)

**Files:**
- Create: `src/tpi_videos/cola.py`
- Test: `pruebas/test_cola.py`

**Interfaces:**
- Consumes: `entorno.raiz_proyecto()`, `errores.ErrorMotor`.
- Produces:
  - `VERSION: int`, `ESTADOS_ACTIVOS: tuple[str, ...]`, `ESTADOS_PENDIENTES: tuple[str, ...]`
  - `cargar() -> dict[str, Any]`
  - `guardar(datos: dict[str, Any]) -> None`
  - `nuevo_lote(tema: str, ajustes: dict[str, Any], ideas: Any = None) -> str`
  - `agregar_videos(lote_id: str, ideas: Any) -> list[str]`
  - `actualizar_lote(lote_id: str, **campos: Any) -> None`
  - `actualizar_video(video_id: str, **campos: Any) -> None`
  - `hito(video_id: str, nombre: str, datos_hito: dict[str, Any]) -> None`
  - `videos_del_lote(lote_id: str) -> list[dict[str, Any]]`
  - `podar() -> int`

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_cola.py
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.ideas import GanchoIdea, Idea


def _idea(titulo: str = "Reto de Ohm") -> Idea:
    return Idea(
        angulo="reto",
        titulo=titulo,
        gancho="¿Cuánto vale la corriente?",
        enunciado="Un circuito de 12 V y 4 ohm: ¿cuál es la corriente eléctrica?",
        materia="fisica",
        nivel="2° medio",
        porque="Porque reta al que mira.",
        segundos=45,
        molde="reto",
        ganchos=[GanchoIdea(texto="¿Cuánto vale la corriente?", estilo="curiosidad")],
    )


class BaseCola(unittest.TestCase):
    """Lo común a las dos clases de prueba: una carpeta temporal como raíz del motor."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        self.raiz = Path(self.tmp.name)

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def _lote_con_video(self) -> str:
        lote_id = cola.nuevo_lote("Porcentajes", {"modelo": "gemini-3.8-flash"})
        cola.agregar_videos(lote_id, [_idea()])
        return lote_id


class ColaTest(BaseCola):
    def test_crear_actualizar_y_releer(self) -> None:
        lote_id = self._lote_con_video()
        video_id = cola.videos_del_lote(lote_id)[0]["id"]
        cola.actualizar_video(video_id, estado="animando", fase="animando", avance=0.5)
        cola.actualizar_lote(lote_id, estado="en_curso", fase="animando")

        lote = cola.cargar()["lotes"][0]
        self.assertEqual(lote["id"], lote_id)
        self.assertEqual(lote["estado"], "en_curso")
        self.assertEqual(lote["videos"][0]["estado"], "animando")
        self.assertEqual(lote["videos"][0]["avance"], 0.5)
        self.assertEqual(lote["ajustes"]["modelo"], "gemini-3.8-flash")

    def test_escritura_atomica_conserva_el_anterior(self) -> None:
        lote_id = self._lote_con_video()
        with patch("tpi_videos.cola.os.replace", side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                cola.actualizar_lote(lote_id, estado="fallo")
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "en_curso")

    def test_json_corrupto_se_aparta(self) -> None:
        ruta = self.raiz / "salida" / ".cola" / "trabajos.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("{esto no es json", encoding="utf-8")

        self.assertEqual(cola.cargar()["lotes"], [])
        self.assertTrue(list(ruta.parent.glob("trabajos.json.roto-*")))

    def test_hito_se_guarda_y_se_relee(self) -> None:
        lote_id = self._lote_con_video()
        video_id = cola.videos_del_lote(lote_id)[0]["id"]
        cola.hito(video_id, "guion", {"ruta": "guiones/x.yaml"})

        hitos = cola.videos_del_lote(lote_id)[0]["hitos"]
        self.assertEqual(hitos["guion"]["ruta"], "guiones/x.yaml")

    def test_podar_conserva_veinte_terminados_y_lo_pendiente(self) -> None:
        pendiente = self._lote_con_video()
        for _ in range(22):
            lote_id = self._lote_con_video()
            video_id = cola.videos_del_lote(lote_id)[0]["id"]
            cola.actualizar_video(video_id, estado="listo")
            cola.actualizar_lote(lote_id, estado="listo")

        self.assertGreater(cola.podar(), 0)
        ids = [lote["id"] for lote in cola.cargar()["lotes"]]
        self.assertIn(pendiente, ids)
        self.assertEqual(len([i for i in ids if i != pendiente]), 20)

    def test_version_futura_no_se_sobrescribe(self) -> None:
        datos = {"version": 99, "lotes": []}
        with self.assertRaises(Exception):
            cola.guardar(datos)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest pruebas.test_cola -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tpi_videos.cola'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tpi_videos/cola.py
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
            ayuda="Vuelve a lanzarlo desde Fábrica o con ./tpi lote \"Tema\".",
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest pruebas.test_cola -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/cola.py pruebas/test_cola.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: cola persistente de lotes en salida/.cola"
```

---

### Task 2: Candado, normalización, selección y descarte

**Files:**
- Modify: `src/tpi_videos/cola.py` (agregar funciones al final)
- Test: `pruebas/test_cola.py` (agregar clase `ColaLifecycleTest` al final)

**Interfaces:**
- Consumes: todo lo de Task 1.
- Produces:
  - `candado_tomado() -> bool`
  - `tomar_candado() -> bool`
  - `soltar_candado() -> None`
  - `estado_derivado(lote: dict[str, Any]) -> str`
  - `recalcular_lote(lote_id: str) -> None`
  - `normalizar_interrumpidos() -> int`
  - `pendientes_ia() -> list[dict[str, Any]]`
  - `elegir_lote(solo_pendientes: bool = False, cola_id: str | None = None) -> dict[str, Any] | None`
  - `ultimo_lote() -> dict[str, Any] | None`
  - `lotes_visibles() -> list[dict[str, Any]]`
  - `descartar_lote(lote_id: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_cola.py — reemplaza el bloque de imports por este (agrega subprocess, sys, time y
# ErrorMotor) y agrega ColaLifecycleTest al final, antes de main
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.errores import ErrorMotor
from tpi_videos.ideas import GanchoIdea, Idea


class ColaLifecycleTest(BaseCola):
    def _video(self, lote_id: str) -> str:
        return cola.videos_del_lote(lote_id)[0]["id"]

    def test_candado_propio_y_liberado(self) -> None:
        self.assertTrue(cola.tomar_candado())
        self.assertTrue(cola.candado_tomado())
        cola.soltar_candado()
        self.assertFalse(cola.candado_tomado())

    def test_candado_de_un_proceso_muerto_se_toma(self) -> None:
        ruta = self.raiz / "salida" / ".cola" / "lote.lock"
        ruta.parent.mkdir(parents=True)
        proceso = subprocess.Popen([sys.executable, "-c", ""])
        proceso.wait()
        ruta.write_text(
            json.dumps({"pid": proceso.pid, "inicio": time.time()}), encoding="utf-8"
        )

        self.assertFalse(cola.candado_tomado())
        self.assertTrue(cola.tomar_candado())

    def test_candado_viejo_se_considera_abandonado(self) -> None:
        ruta = self.raiz / "salida" / ".cola" / "lote.lock"
        ruta.parent.mkdir(parents=True)
        ruta.write_text(
            json.dumps({"pid": os.getpid(), "inicio": time.time() - 13 * 3600}),
            encoding="utf-8",
        )
        self.assertFalse(cola.candado_tomado())

    def test_normalizar_no_toca_nada_con_el_candado_tomado(self) -> None:
        lote_id = self._lote_con_video()
        cola.actualizar_video(self._video(lote_id), estado="animando", fase="animando", avance=0.55)
        cola.tomar_candado()
        try:
            self.assertEqual(cola.normalizar_interrumpidos(), 0)
            self.assertEqual(cola.videos_del_lote(lote_id)[0]["estado"], "animando")
        finally:
            cola.soltar_candado()

    def test_normalizar_marca_interrumpido_y_deriva_el_lote(self) -> None:
        lote_id = self._lote_con_video()
        cola.actualizar_video(self._video(lote_id), estado="animando", fase="animando", avance=0.55)

        self.assertEqual(cola.normalizar_interrumpidos(), 1)
        video = cola.videos_del_lote(lote_id)[0]
        self.assertEqual(video["estado"], "interrumpido")
        self.assertIn("55", video["detalle"])
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "interrumpido")

    def test_normalizar_un_lote_sin_ideas_lo_deja_pendiente(self) -> None:
        lote_id = cola.nuevo_lote("Porcentajes", {})
        cola.normalizar_interrumpidos()
        lote = cola.cargar()["lotes"][0]
        self.assertEqual(lote["id"], lote_id)
        self.assertEqual(lote["estado"], "pendiente_ia")

    def test_elegir_lote_pendiente_y_saltar_interrumpido(self) -> None:
        listo = self._lote_con_video()
        cola.actualizar_video(self._video(listo), estado="listo")
        cola.recalcular_lote(listo)

        pendiente = self._lote_con_video()
        video_id = self._video(pendiente)
        cola.actualizar_video(video_id, estado="pendiente_ia")
        cola.recalcular_lote(pendiente)

        self.assertEqual(cola.elegir_lote(solo_pendientes=True)["id"], pendiente)

        cola.actualizar_video(video_id, estado="interrumpido")
        cola.recalcular_lote(pendiente)
        self.assertIsNone(cola.elegir_lote(solo_pendientes=True))
        self.assertEqual(cola.elegir_lote(cola_id=pendiente)["id"], pendiente)

    def test_pendientes_ia_encuentra_lotes_y_videos(self) -> None:
        sin_ideas = cola.nuevo_lote("Porcentajes", {})
        cola.normalizar_interrumpidos()
        con_video = self._lote_con_video()
        cola.actualizar_video(self._video(con_video), estado="pendiente_ia")
        cola.recalcular_lote(con_video)

        ids = [lote["id"] for lote in cola.pendientes_ia()]
        self.assertEqual(ids, [sin_ideas, con_video])

    def test_descartar_con_el_candado_tomado_avisa(self) -> None:
        lote_id = self._lote_con_video()
        cola.tomar_candado()
        try:
            with self.assertRaises(ErrorMotor):
                cola.descartar_lote(lote_id)
        finally:
            cola.soltar_candado()
        cola.descartar_lote(lote_id)
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "descartado")
        self.assertEqual(cola.lotes_visibles(), [])

    def test_lotes_visibles_muestra_pendientes_y_el_ultimo(self) -> None:
        viejo = self._lote_con_video()
        cola.actualizar_video(self._video(viejo), estado="listo")
        cola.recalcular_lote(viejo)
        nuevo = self._lote_con_video()

        ids = [lote["id"] for lote in cola.lotes_visibles()]
        self.assertEqual(ids, [nuevo])
        self.assertEqual(cola.ultimo_lote()["id"], nuevo)

    def test_podar_no_toca_nada_si_otro_proceso_trabaja(self) -> None:
        self._lote_con_video()
        with (
            patch("tpi_videos.cola.candado_tomado", return_value=True),
            patch("tpi_videos.cola._candado_es_mio", return_value=False),
        ):
            self.assertEqual(cola.podar(), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest pruebas.test_cola.ColaLifecycleTest -v`
Expected: FAIL with `AttributeError: module 'tpi_videos.cola' has no attribute 'candado_tomado'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tpi_videos/cola.py — agregar al final

def _ruta_candado() -> Path:
    return _ruta().parent / "lote.lock"


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
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
    if candado_tomado() and not _candado_es_mio():
        return 0
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
```

Y reemplaza `podar()` (Task 1) por la versión que respeta el candado de otro proceso:

```python
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
```

Agregar los imports que faltan al encabezado de `cola.py`:

```python
import sys
import time
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest pruebas.test_cola -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/cola.py pruebas/test_cola.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: candado, normalización y selección de lotes en la cola"
```

---

### Task 3: `producir()` reanudable por hitos

**Files:**
- Modify: `src/tpi_videos/ideas.py` (firma y cuerpo de `producir`, ~línea 284)
- Test: `pruebas/test_producir_reanudar.py` (crear)

**Interfaces:**
- Consumes: `redactor.redactar`, `render.crear_video`, `publicar.crear_kit`, `guion.cargar_guion`.
- Produces:
  - `producir(..., reanudar: dict[str, Any] | None = None, hito: Callable[[str, dict[str, Any]], None] | None = None) -> ResultadoProduccion`
  - Emite `progreso("kit", 0.95, …)` al empezar el kit y `progreso("kit", 1.0, "kit listo")` al terminar.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_producir_reanudar.py
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tpi_videos.ideas import producir

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "guiones" / "ejemplos" / "fisica_caida_libre.yaml"


def _video_falso(raiz: Path) -> SimpleNamespace:
    carpeta = raiz / "salida" / "demo"
    carpeta.mkdir(parents=True, exist_ok=True)
    video = carpeta / "demo.mp4"
    video.write_bytes(b"x")
    return SimpleNamespace(
        video=video,
        carpeta=carpeta,
        duracion=42.0,
        segundos_proceso=1.0,
        srt=None,
        fuentes_tiempo=set(),
        tema="Hoja de desarrollo",
    )


def _kit_falso(raiz: Path) -> SimpleNamespace:
    carpeta = raiz / "salida" / "demo"
    carpeta.mkdir(parents=True, exist_ok=True)
    portada = carpeta / "portada.png"
    portada.write_bytes(b"x")
    archivo = carpeta / "publicacion.md"
    archivo.write_text("hola", encoding="utf-8")
    textos = SimpleNamespace(
        titulo_youtube="T",
        descripcion_youtube="D",
        texto_tiktok="TT",
        texto_instagram="I",
        hashtags=["#a"],
    )
    return SimpleNamespace(
        carpeta=carpeta, portada=portada, textos=textos, con_ia=True, archivo=archivo, aviso=None
    )


def _hito_guion() -> dict:
    return {
        "ruta": str(GUION),
        "pendientes": ["revisar el signo"],
        "supuestos": [],
        "rondas": 2,
        "modelo": "gemini-3.8-flash",
        "revisado_por_ia": True,
    }


class ProducirReanudarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_con_hito_guion_no_llama_a_la_ia(self) -> None:
        nombres: list[str] = []
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            crear_video.return_value = _video_falso(self.raiz)
            crear_kit.return_value = _kit_falso(self.raiz)
            resultado = producir(
                "x", reanudar={"guion": _hito_guion()}, hito=lambda n, d: nombres.append(n)
            )

        redactar.assert_not_called()
        crear_video.assert_called_once()
        crear_kit.assert_called_once()
        self.assertEqual(nombres, ["video", "kit"])
        self.assertEqual(resultado.duracion, 42.0)
        self.assertEqual(resultado.redaccion.pendientes, ["revisar el signo"])

    def test_con_hito_video_no_renderiza(self) -> None:
        video = _video_falso(self.raiz)
        hito_video = {
            "video": str(video.video),
            "carpeta": str(video.carpeta),
            "duracion": 42.0,
            "segundos_proceso": 1.0,
            "srt": None,
            "fuentes_tiempo": [],
            "tema": "Hoja de desarrollo",
        }
        nombres: list[str] = []
        with (
            patch("tpi_videos.ideas.redactar"),
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            crear_kit.return_value = _kit_falso(self.raiz)
            producir(
                "x",
                reanudar={"guion": _hito_guion(), "video": hito_video},
                hito=lambda n, d: nombres.append(n),
            )

        crear_video.assert_not_called()
        crear_kit.assert_called_once()
        self.assertEqual(nombres, ["kit"])

    def test_con_hito_kit_no_llama_a_nadie(self) -> None:
        video = _video_falso(self.raiz)
        kit = _kit_falso(self.raiz)
        reanudar = {
            "guion": _hito_guion(),
            "video": {
                "video": str(video.video),
                "carpeta": str(video.carpeta),
                "duracion": 42.0,
                "segundos_proceso": 1.0,
                "srt": None,
                "fuentes_tiempo": [],
                "tema": "Hoja de desarrollo",
            },
            "kit": {
                "carpeta": str(kit.carpeta),
                "portada": str(kit.portada),
                "publicacion": str(kit.archivo),
                "texto_kit": "YouTube: T",
                "aviso": None,
            },
        }
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            resultado = producir("x", reanudar=reanudar)

        redactar.assert_not_called()
        crear_video.assert_not_called()
        crear_kit.assert_not_called()
        self.assertEqual(resultado.texto_kit, "YouTube: T")
        self.assertEqual(resultado.publicacion, kit.archivo)

    def test_si_falta_el_archivo_del_hito_se_rehace(self) -> None:
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            redactar.return_value = SimpleNamespace(
                ruta=GUION,
                guion=None,
                supuestos=[],
                pendientes=[],
                rondas=1,
                modelo="m",
                revisado_por_ia=True,
                historial=[],
            )
            crear_video.return_value = _video_falso(self.raiz)
            crear_kit.return_value = _kit_falso(self.raiz)
            producir("x", reanudar={"guion": {**_hito_guion(), "ruta": str(self.raiz / "nada.yaml")}})

        redactar.assert_called_once()

    def test_hito_se_llama_en_orden(self) -> None:
        nombres: list[str] = []
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            redactar.return_value = SimpleNamespace(
                ruta=GUION,
                guion=None,
                supuestos=[],
                pendientes=[],
                rondas=1,
                modelo="m",
                revisado_por_ia=True,
                historial=[],
            )
            crear_video.return_value = _video_falso(self.raiz)
            crear_kit.return_value = _kit_falso(self.raiz)
            producir("x", hito=lambda n, d: nombres.append(n))

        self.assertEqual(nombres, ["guion", "video", "kit"])

    def test_kit_a_medias_conserva_el_video(self) -> None:
        hito_video = {
            "video": str(_video_falso(self.raiz).video),
            "carpeta": str(self.raiz / "salida" / "demo"),
            "duracion": 42.0,
            "segundos_proceso": 1.0,
            "srt": None,
            "fuentes_tiempo": [],
            "tema": "Hoja de desarrollo",
        }
        with (
            patch("tpi_videos.ideas.redactar"),
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit", side_effect=RuntimeError("sin cupo")),
        ):
            with self.assertRaises(RuntimeError):
                producir("x", reanudar={"guion": _hito_guion(), "video": hito_video})
        crear_video.assert_not_called()
        self.assertTrue(Path(hito_video["video"]).exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest pruebas.test_producir_reanudar -v`
Expected: FAIL with `TypeError: producir() got an unexpected keyword argument 'reanudar'`

- [ ] **Step 3: Write minimal implementation**

Cambia la firma de `producir` en `src/tpi_videos/ideas.py`:

```python
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
```

Reemplaza el cuerpo desde `from .publicar import crear_kit` hasta el final de la función:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest pruebas.test_producir_reanudar -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/ideas.py pruebas/test_producir_reanudar.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: producir reanuda por hitos y no repite guion ni video"
```

---

### Task 4: `producir_lote` escribe la cola y espera a la IA sin límite

**Files:**
- Modify: `src/tpi_videos/lote.py`
- Test: `pruebas/test_lote_cola.py` (crear)

**Interfaces:**
- Consumes: `cola.*` de Tasks 1–2, `producir(..., reanudar=, hito=)` de Task 3.
- Produces:
  - `ItemLote.pendiente: bool`
  - `producir_lote(..., cola_id: str | None = None, dormir: Callable[[float], None] = time.sleep, reintentos: int | None = None)`
  - `espera_del_intento(intento: int, primera: float) -> float`
  - `hora_en(segundos: float) -> str`
  - `texto_espera(segundos: float) -> str`
  - Eventos de progreso con `video`, `total`, `video_avance`, `fase`, `estado`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_lote_cola.py
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.errores import ErrorMotor
from tpi_videos.ideas import GanchoIdea, Idea
from tpi_videos.lote import producir_lote


def _idea(n: int) -> Idea:
    return Idea(
        angulo=("reto", "dato_curioso", "error_tipico")[n - 1],
        titulo=f"Idea {n}",
        gancho="¿Cuánto vale la corriente?",
        enunciado="Un circuito de 12 V y 4 ohm: ¿cuál es la corriente eléctrica?",
        materia="fisica",
        nivel="2° medio",
        porque="Porque reta al que mira.",
        segundos=45,
        molde=("reto", "mito_realidad", "tres_errores")[n - 1],
        ganchos=[GanchoIdea(texto="¿Cuánto vale la corriente?", estilo="curiosidad")],
    )


def _resultado(raiz: Path) -> SimpleNamespace:
    video = raiz / "salida" / "demo" / "demo.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"x")
    return SimpleNamespace(
        ruta_guion=raiz / "guiones" / "demo.yaml",
        video=video,
        portada=None,
        publicacion=None,
        duracion=42.0,
        redaccion=SimpleNamespace(pendientes=[]),
    )


class LoteColaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        self.raiz = Path(self.tmp.name)

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def _lote(self) -> tuple[str, list[Idea]]:
        ideas = [_idea(1), _idea(2)]
        lote_id = cola.nuevo_lote("Tema", {})
        cola.agregar_videos(lote_id, ideas)
        return lote_id, ideas

    def test_transitorio_queda_pendiente_y_pausa_el_lote(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch("tpi_videos.lote.producir", side_effect=ErrorMotor("sin red", transitorio=True)):
            items = producir_lote(
                ideas, cola_id=lote_id, espera=60, reintentos=3, dormir=dormidos.append
            )

        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].pendiente)
        self.assertEqual(dormidos, [60.0, 120.0, 300.0])
        videos = cola.videos_del_lote(lote_id)
        self.assertEqual(videos[0]["estado"], "pendiente_ia")
        self.assertEqual(videos[0]["intentos"], 4)
        self.assertTrue(videos[0]["proximo_intento"])
        self.assertEqual(videos[1]["estado"], "en_cola")
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "pendiente_ia")

    def test_al_volver_la_ia_sigue_con_los_demas(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch(
            "tpi_videos.lote.producir",
            side_effect=[
                ErrorMotor("sin red", transitorio=True),
                _resultado(self.raiz),
                _resultado(self.raiz),
            ],
        ):
            items = producir_lote(ideas, cola_id=lote_id, espera=60, dormir=dormidos.append)

        self.assertEqual([item.ok for item in items], [True, True])
        self.assertEqual(dormidos, [60.0])
        self.assertEqual(
            [video["estado"] for video in cola.videos_del_lote(lote_id)], ["listo", "listo"]
        )
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "listo")

    def test_error_no_transitorio_marca_fallo_y_no_espera(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch("tpi_videos.lote.producir", side_effect=ErrorMotor("LaTeX roto")):
            items = producir_lote(ideas, cola_id=lote_id, espera=60, dormir=dormidos.append)

        self.assertEqual(dormidos, [])
        self.assertTrue(all(not item.ok and not item.pendiente for item in items))
        self.assertEqual(
            [video["estado"] for video in cola.videos_del_lote(lote_id)], ["fallo", "fallo"]
        )
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "fallo")

    def test_espera_cero_marca_pendiente_sin_dormir(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch("tpi_videos.lote.producir", side_effect=ErrorMotor("sin red", transitorio=True)):
            items = producir_lote(ideas, cola_id=lote_id, espera=0, dormir=dormidos.append)

        self.assertEqual(dormidos, [])
        self.assertTrue(items[0].pendiente)

    def test_eventos_traen_el_video_y_su_avance(self) -> None:
        lote_id, ideas = self._lote()
        eventos: list[dict] = []

        def progreso(etapa, avance, detalle, **extra):
            eventos.append({"etapa": etapa, "avance": avance, "detalle": detalle, **extra})

        with patch("tpi_videos.lote.producir", side_effect=[_resultado(self.raiz), _resultado(self.raiz)]):
            producir_lote(ideas, cola_id=lote_id, progreso=progreso)

        primero = eventos[0]
        self.assertEqual(primero["video"], 1)
        self.assertEqual(primero["total"], 2)
        self.assertEqual(primero["estado"], "redactando")
        self.assertAlmostEqual(primero["video_avance"], 0.05)
        self.assertAlmostEqual(primero["avance"], 0.025)

    def test_si_la_cola_no_se_puede_escribir_el_video_sigue(self) -> None:
        lote_id, ideas = self._lote()
        avisos: list[str] = []
        with (
            patch(
                "tpi_videos.lote.producir",
                side_effect=[_resultado(self.raiz), _resultado(self.raiz)],
            ),
            patch("tpi_videos.cola.guardar", side_effect=OSError("disco lleno")),
        ):
            items = producir_lote(ideas, cola_id=lote_id, avisar=avisos.append)

        self.assertEqual([item.ok for item in items], [True, True])
        self.assertEqual(sum("No pude guardar" in aviso for aviso in avisos), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest pruebas.test_lote_cola -v`
Expected: FAIL with `TypeError: producir_lote() got an unexpected keyword argument 'cola_id'`

- [ ] **Step 3: Write minimal implementation**

Reemplaza `src/tpi_videos/lote.py` completo por:

```python
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

INTENTOS_POR_IDEA = 2  # compatibilidad con lo que ya llamaba al lote
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
        promesa_incumplida=se_paso_de_largo(resultado.duracion, idea.segundos),
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
            esperar=lambda intento, segundos: _esperar_ia(seguir, paso, intento, segundos),
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
    ultimo = {"avance": 0.0}

    def emitir(
        etapa: str, detalle: str, fase: str, estado: str, video_avance: float | None = None
    ) -> None:
        if video_avance is not None:
            ultimo["avance"] = max(ultimo["avance"], video_avance)
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
            paso("redactando", detalle)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest pruebas.test_lote_cola -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the existing tests to check no regression**

Run: `PYTHONPATH=src python -m unittest discover -s pruebas -t . -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add src/tpi_videos/lote.py pruebas/test_lote_cola.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: lote con cola, hitos y espera ilimitada de la IA"
```

---

### Task 5: CLI crea la cola, reanuda y emite progreso por video

**Files:**
- Modify: `src/tpi_videos/cli.py` (`_progreso_json` línea 61, `_mostrar_lote` línea 613, `cmd_lote` línea 651, `construir_parser` líneas 1060–1089)
- Test: `pruebas/test_cli_cola.py` (crear)

**Interfaces:**
- Consumes: `cola.*`, `producir_lote(cola_id=…)`, `espera_del_intento`, `hora_en`, `texto_espera`.
- Produces:
  - `_progreso_json(etapa, avance, detalle, **extra)`
  - `tpi lote --reanudar [--solo-pendientes] [--cola-id ID]`
  - Resultado con `pendiente: bool` y `cola_id: str | None`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_cli_cola.py
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


class CliColaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(
            os.environ,
            TPI_RAIZ=self.tmp.name,
            NO_COLOR="1",
            PYTHONPATH=str(RAIZ / "src"),
        )
        (Path(self.tmp.name) / "salida").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _correr(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tpi_videos", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.env,
            timeout=60,
        )

    def test_reanudar_sin_pendientes_sale_limpio(self) -> None:
        resultado = self._correr("lote", "--reanudar")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("No hay videos pendientes", resultado.stdout)

    def test_reanudar_no_acepta_tema(self) -> None:
        resultado = self._correr("lote", "--reanudar", "Porcentajes")
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("no indiques tema", resultado.stdout)

    def test_solo_pendientes_va_con_reanudar(self) -> None:
        resultado = self._correr("lote", "--solo-pendientes", "Porcentajes")
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("van con --reanudar", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest pruebas.test_cli_cola -v`
Expected: FAIL with `AssertionError` (the CLI rejects unknown `--reanudar`)

- [ ] **Step 3: Write minimal implementation**

**3a.** Cambia el emisor de progreso en `src/tpi_videos/cli.py`:

```python
def _progreso_json(etapa: str, avance: float, detalle: str, **extra: object) -> None:
    _emitir(etapa=etapa, avance=avance, detalle=detalle, **extra)
```

**3b.** En `_mostrar_lote`, antes del bloque `if not item.ok:`, agrega el caso pendiente:

```python
        if item.pendiente:
            consola.print(f" [bold]{n}[/]  [yellow]⏳[/] {guion}")
            consola.print(f"    [yellow]{item.error}[/]")
            if item.ayuda:
                consola.print(f"    [dim]{item.ayuda}[/]")
            continue
```

**3c.** Reemplaza `cmd_lote` completo por:

```python
def _ajustes_lote(
    args: argparse.Namespace, modelo: str, proveedor: str | None, voz: str | None
) -> dict:
    """Todo lo que hace falta para repetir el lote exactamente igual al reanudar."""
    return {
        "materia": args.materia,
        "nivel": args.nivel,
        "dificultad": args.dificultad,
        "modelo": modelo,
        "calidad": "borrador" if args.borrador else "final",
        "estilo": args.estilo,
        "proveedor": proveedor,
        "voz": voz,
        "velocidad": args.velocidad,
        "subtitulos": not args.sin_subtitulos,
        "sincronizar": args.sincronizar,
        "revisar_con_ia": not args.sin_revision,
        "con_kit": not args.sin_kit,
    }


def _producir_desde_ajustes(ajustes: dict) -> dict:
    return {
        "materia": ajustes.get("materia"),
        "nivel": ajustes.get("nivel"),
        "dificultad": ajustes.get("dificultad"),
        "modelo": ajustes.get("modelo"),
        "calidad": ajustes.get("calidad") or "final",
        "estilo": ajustes.get("estilo"),
        "proveedor": ajustes.get("proveedor"),
        "voz": ajustes.get("voz"),
        "velocidad": ajustes.get("velocidad"),
        "subtitulos": bool(ajustes.get("subtitulos", True)),
        "sincronizar": ajustes.get("sincronizar") or "auto",
        "revisar_con_ia": bool(ajustes.get("revisar_con_ia", True)),
        "con_kit": bool(ajustes.get("con_kit", True)),
    }


def _pedir_ideas(
    proponer: Any, *, tema: str, ajustes: dict, espera: float, avisar, lote_id: str
) -> list[Any] | None:
    """Pide las 3 ideas y espera a la IA con la misma secuencia que los videos."""
    from . import cola
    from .ia import MODELO_POR_DEFECTO
    from .lote import espera_del_intento, hora_en, texto_espera

    intento = 0
    while True:
        intento += 1
        try:
            return proponer(
                tema=tema,
                materia=ajustes.get("materia"),
                nivel=ajustes.get("nivel"),
                dificultad=ajustes.get("dificultad"),
                modelo=ajustes.get("modelo") or MODELO_POR_DEFECTO,
                avisar=avisar,
            )
        except ErrorMotor as e:
            if not e.transitorio:
                cola.actualizar_lote(
                    lote_id, estado="fallo", fase="fallo", error=e.mensaje, ayuda=e.ayuda
                )
                raise
            if espera <= 0:
                cola.actualizar_lote(
                    lote_id,
                    estado="pendiente_ia",
                    fase="esperando_ia",
                    error=e.mensaje,
                    ayuda=e.ayuda,
                    intentos=intento,
                )
                return None
            segundos = espera_del_intento(intento, espera)
            cola.actualizar_lote(
                lote_id,
                estado="pendiente_ia",
                fase="esperando_ia",
                error=e.mensaje,
                ayuda=e.ayuda,
                intentos=intento,
                proximo_intento=hora_en(segundos),
            )
            avisar(f"Sin conexión con la IA: reintento en {texto_espera(segundos)}")
            time.sleep(segundos)


def _resultado_lote(
    items: list,
    ideas: list,
    tema: str | None,
    lote_id: str | None,
    json_activo: bool,
    pendiente: bool = False,
) -> None:
    pendiente = pendiente or any(item.pendiente for item in items) or len(items) < len(ideas)
    if json_activo:
        _emitir(
            etapa="resultado",
            avance=1.0,
            tema=tema or "",
            lote=[item.como_dict() for item in items],
            pendiente=pendiente,
            cola_id=lote_id,
        )
    elif pendiente:
        consola.print(
            "\n[yellow]La IA no responde.[/] El lote quedó guardado: se reanuda solo cuando vuelva "
            "(o con ./tpi lote --reanudar).\n"
        )


def _cmd_reanudar(args: argparse.Namespace, *, json_activo: bool, avisar) -> int:
    from . import cola
    from .ideas import Idea, proponer_ideas
    from .lote import producir_lote

    if args.ideas_json:
        raise ErrorMotor(
            "Para reanudar no indiques tema ni ideas; usa --cola-id si quieres elegir un lote."
        )
    if not cola.tomar_candado():
        if json_activo:
            _emitir(
                etapa="resultado", avance=1.0, lote=[], pendiente=False, cola_id=None,
                detalle="Ya hay un lote en curso.",
            )  # fmt: skip
        else:
            consola.print("[yellow]Ya hay un lote en curso.[/] Espera a que termine.")
        return 0
    try:
        cola.podar()
        lote = cola.elegir_lote(solo_pendientes=args.solo_pendientes, cola_id=args.cola_id)
        if lote is None or lote.get("estado") == "listo":
            if json_activo:
                _emitir(etapa="resultado", avance=1.0, lote=[], pendiente=False, cola_id=None)
            else:
                consola.print("No hay videos pendientes." if lote is None else "Ese lote ya está listo.")
            return 0

        ajustes = dict(lote.get("ajustes") or {})
        if lote.get("videos"):
            ideas = [Idea.model_validate(video["idea"]) for video in lote["videos"]]
        else:
            avisar(f"Retomo el lote de «{lote['tema']}»: pido de nuevo las 3 ideas…")
            ideas = _pedir_ideas(
                proponer_ideas,
                tema=str(lote.get("tema") or ""),
                ajustes=ajustes,
                espera=args.espera,
                avisar=avisar,
                lote_id=lote["id"],
            )
            if ideas is None:
                if json_activo:
                    _emitir(
                        etapa="resultado", avance=1.0, tema=lote.get("tema"), lote=[],
                        pendiente=True, cola_id=lote["id"],
                    )  # fmt: skip
                else:
                    consola.print(
                        "\n[yellow]La IA no responde.[/] El lote quedó guardado para cuando vuelva.\n"
                    )
                return 0
            cola.agregar_videos(lote["id"], ideas)

        items = producir_lote(
            ideas,
            **_producir_desde_ajustes(ajustes),
            espera=args.espera,
            cola_id=lote["id"],
            reintentos=None,
            avisar=avisar,
            progreso=_progreso_json if json_activo else None,
        )
        _resultado_lote(items, ideas, lote.get("tema"), lote["id"], json_activo)
        _mostrar_lote(items, lote.get("tema"))
        return 0
    finally:
        cola.soltar_candado()


def cmd_lote(args: argparse.Namespace) -> int:
    """De un tema, los 3 videos de una pasada: guion revisado + video final + kit de cada idea."""
    from . import cola
    from .ia import MODELO_POR_DEFECTO
    from .ideas import proponer_ideas
    from .lote import ideas_desde_json, producir_lote

    json_activo = _modo_json(args)
    proveedor, voz = _dividir_voz(args.voz)
    modelo = args.modelo or MODELO_POR_DEFECTO
    tema = " ".join(args.tema).strip() or None

    def avisar(mensaje: str) -> None:
        if json_activo:
            _emitir(etapa="redactando", avance=0.0, detalle=mensaje)
        else:
            consola.print(f"[dim]→ {mensaje}[/dim]")

    if (args.solo_pendientes or args.cola_id) and not args.reanudar:
        raise ErrorMotor("--solo-pendientes y --cola-id van con --reanudar.")
    if args.reanudar:
        if tema:
            raise ErrorMotor(
                "Para reanudar no indiques tema ni ideas; usa --cola-id si quieres elegir un lote."
            )
        return _cmd_reanudar(args, json_activo=json_activo, avisar=avisar)

    if cola.candado_tomado():
        raise ErrorMotor(
            "Ya hay un lote en curso.",
            ayuda="Espera a que termine (mira Fábrica) o ciérralo antes de lanzar otro.",
        )
    ajustes = _ajustes_lote(args, modelo, proveedor, voz)
    cola.tomar_candado()
    try:
        if args.ideas_json:
            ideas = ideas_desde_json(args.ideas_json)
            lote_id = cola.nuevo_lote(tema or ideas[0].titulo, ajustes, ideas=ideas)
        else:
            if not tema:
                raise ErrorMotor(
                    "El lote necesita el tema.",
                    ayuda='Ej. ./tpi lote "Porcentajes"   (o usa el botón «Crear los 3 videos» de Fábrica)',
                )
            lote_id = cola.nuevo_lote(tema, ajustes)
            ideas = _pedir_ideas(
                proponer_ideas,
                tema=tema,
                ajustes=ajustes,
                espera=args.espera,
                avisar=avisar,
                lote_id=lote_id,
            )
            if ideas is None:
                _resultado_lote([], [], tema, lote_id, json_activo, pendiente=True)
                return 0
            cola.agregar_videos(lote_id, ideas)

        if not json_activo:
            consola.print(
                f"\n[bold]📦 Lote de {len(ideas)} videos[/] · de uno en uno, unos {len(ideas) * 3} "
                "minutos.\n   Si una idea falla el lote sigue con las otras; lo que salga queda en salida/."
            )

        items = producir_lote(
            ideas,
            **_producir_desde_ajustes(ajustes),
            espera=args.espera,
            cola_id=lote_id,
            reintentos=None,
            avisar=avisar,
            progreso=_progreso_json if json_activo else None,
        )
    finally:
        cola.soltar_candado()

    _resultado_lote(items, ideas, tema, lote_id, json_activo)
    _mostrar_lote(items, tema)
    if args.abrir:
        for item in items:
            if item.ok:
                _abrir(Path(item.video))
    return 0
```

**3d.** En `construir_parser`, dentro del bloque del comando `lote`, agrega antes de `--espera`:

```python
    s.add_argument(
        "--reanudar",
        action="store_true",
        help="sigue el lote que quedó pendiente en la cola (usa los ajustes guardados)",
    )
    s.add_argument("--solo-pendientes", action="store_true", help=argparse.SUPPRESS)
    s.add_argument("--cola-id", help=argparse.SUPPRESS)
```

Y cambia la ayuda de `--espera`:

```python
    s.add_argument(
        "--espera",
        type=float,
        default=60.0,
        help="segundos de la primera espera si Gemini está saturado; luego 2 min, 5 min y cada 5 min",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest pruebas.test_cli_cola -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run all tests**

Run: `PYTHONPATH=src python -m unittest discover -s pruebas -t . -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add src/tpi_videos/cli.py pruebas/test_cli_cola.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: tpi lote guarda la cola, reanuda y emite progreso por video"
```

---

### Task 6: El panel entiende los eventos por video

**Files:**
- Modify: `src/tpi_videos/panel/__init__.py` (import perezoso)
- Modify: `src/tpi_videos/panel/tareas.py` (líneas 22–60 y `_aplicar` línea 139)
- Test: `pruebas/test_tareas.py` (crear)

**Interfaces:**
- Consumes: eventos del CLI con `video`, `total`, `video_avance`, `fase`, `estado`, `cola_id`.
- Produces:
  - `Tarea.videos: dict[int, dict[str, Any]]`
  - `Tarea.cola_id: str | None`

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_tareas.py
import unittest

from tpi_videos.panel.tareas import Tarea, Tareas


class TareasTest(unittest.TestCase):
    def test_evento_con_video_actualiza_su_ficha(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(
            tarea,
            {
                "etapa": "animacion",
                "avance": 0.3,
                "detalle": "Video 2 de 3 · animando",
                "video": 2,
                "total": 3,
                "video_avance": 0.55,
                "fase": "animando",
                "estado": "animando",
            },
        )

        self.assertEqual(tarea.videos[2]["estado"], "animando")
        self.assertEqual(tarea.videos[2]["total"], 3)
        self.assertAlmostEqual(tarea.videos[2]["avance"], 0.55)
        self.assertAlmostEqual(tarea.avance, 0.3)

    def test_un_avance_menor_no_retrocede(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(
            tarea,
            {"etapa": "animacion", "avance": 0.5, "video": 1, "total": 3, "video_avance": 0.6},
        )
        Tareas._aplicar(
            tarea,
            {"etapa": "animacion", "avance": 0.4, "video": 1, "total": 3, "video_avance": 0.2},
        )

        self.assertAlmostEqual(tarea.videos[1]["avance"], 0.6)
        self.assertAlmostEqual(tarea.avance, 0.5)

    def test_evento_sin_video_mantiene_el_comportamiento(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(
            tarea, {"etapa": "redactando", "avance": 0.0, "detalle": "Gemini está pensando"}
        )

        self.assertEqual(tarea.etapa, "redactando")
        self.assertEqual(tarea.detalle, "Gemini está pensando")
        self.assertEqual(tarea.videos, {})

    def test_resultado_conserva_pendiente_y_cola(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(
            tarea,
            {"etapa": "resultado", "avance": 1.0, "pendiente": True, "cola_id": "abc", "lote": []},
        )

        self.assertTrue(tarea.resultado["pendiente"])
        self.assertEqual(tarea.cola_id, "abc")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest pruebas.test_tareas -v`
Expected: FAIL con `ModuleNotFoundError` (NiceGUI no está instalado) o `TypeError` por `videos`

- [ ] **Step 3: Write minimal implementation**

**3a.** `src/tpi_videos/panel/__init__.py` completo:

```python
"""Panel de control local (NiceGUI): crear, ver y publicar videos sin usar la Terminal.

- Solo escucha en 127.0.0.1: nadie más en la red (ni siquiera por WiFi) puede entrar.
- Lo pesado (redactar, crear videos, vistas previas, kit de publicación) lo hacen los mismos comandos
  ``tpi`` en procesos aparte: si un video falla, el panel sigue funcionando, y lo que hace el panel es
  exactamente lo que hacen los comandos.
"""

__all__ = ["iniciar"]


def iniciar(*args, **kwargs):
    """Se importa recién al abrir el panel: así ``tpi_videos.panel.tareas`` se prueba sin NiceGUI."""
    from .app import iniciar as _iniciar

    return _iniciar(*args, **kwargs)
```

**3b.** En `tareas.py`, agrega `"esperando_ia": "Esperando conexión"` al diccionario `ETAPAS`.

**3c.** Agrega los campos a `Tarea` después de `detalle`:

```python
    videos: dict[int, dict[str, Any]] = field(default_factory=dict)  # avance y fase de cada video
    cola_id: str | None = None
```

**3d.** Reemplaza `_aplicar` por:

```python
    @staticmethod
    def _aplicar(tarea: Tarea, evento: dict[str, Any]) -> None:
        etapa = evento.get("etapa", "")
        if etapa == "error":
            tarea.error = {"mensaje": evento.get("mensaje", "Error"), "ayuda": evento.get("ayuda")}
            return
        if etapa in ("resultado", "guion"):
            tarea.resultado.update({k: v for k, v in evento.items() if k not in ("etapa", "avance")})
            if evento.get("cola_id"):
                tarea.cola_id = str(evento["cola_id"])
            return
        tarea.etapa = etapa or tarea.etapa
        if evento.get("avance"):  # los avisos de la IA no traen avance (0): no se retrocede
            tarea.avance = max(tarea.avance, float(evento["avance"]))
        tarea.detalle = str(evento.get("detalle", ""))
        numero = evento.get("video")
        if numero is not None:
            try:
                n = int(numero)
            except (TypeError, ValueError):
                n = 0
            if n:
                datos = tarea.videos.setdefault(n, {"total": int(evento.get("total") or 0)})
                if evento.get("total"):
                    datos["total"] = int(evento["total"])
                if evento.get("video_avance") is not None:
                    datos["avance"] = max(
                        float(datos.get("avance") or 0.0), float(evento["video_avance"])
                    )
                for campo in ("fase", "estado", "detalle"):
                    if evento.get(campo) is not None:
                        datos[campo] = evento[campo]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest pruebas.test_tareas -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/panel/__init__.py src/tpi_videos/panel/tareas.py pruebas/test_tareas.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: el panel guarda avance y fase de cada video del lote"
```

---

### Task 7: Fábrica con barras por video, tarjeta de cola y reanudación automática

**Files:**
- Modify: `src/tpi_videos/panel/paginas/fabrica.py`
- Modify: `src/tpi_videos/panel/app.py`
- Test: manual en el Mac (el panel no corre en CI). Lo automático ya está cubierto por las Tasks 1–6.

**Interfaces:**
- Consumes: `Tarea.videos`, `Tarea.cola_id`, `cola.*`.
- Produces: pantalla de trabajo con una barra por video; tarjeta «Cola de videos» con **Reanudar**, **Descartar** y **Abrir la carpeta**; arranque que lanza `tpi lote --reanudar --solo-pendientes`.

- [ ] **Step 1: Reemplaza el encabezado y las constantes de `fabrica.py`**

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from nicegui import ui

from ... import cola, ia
from ...entorno import raiz_proyecto
from ...errores import ErrorMotor
from ...ideas import ANGULOS, DIFICULTADES
from ...moldes import nombre_molde
from ..comun import AZUL, GRIS, ROJO, VERDE, abrir_en_mac, marco
from ..tareas import TAREAS, Tarea
from .crear import TEMAS_SUGERIDOS
from .videos import abrir_kit

# «Video 2 de 3 · animando la fórmula»: el prefijo que el lote pone en cada aviso
VIDEO_DE = re.compile(r"^Video (\d+) de (\d+) · (.*)$")
TITULO = re.compile(r"^Voy con «(.+?)»")
# El naranja del panel para los avisos que no son errores
NARANJA = "#B26A00"
# Los nombres de los trabajos que esta pantalla sabe retomar si se recarga a medio lote
PROPIOS = ("3 videos de", "Reintento", "Reanudar")

ESTADOS_FILA = {
    "en_cola": ("radio_button_unchecked", GRIS, "En espera"),
    "redactando": ("edit_note", AZUL, "La IA está escribiendo…"),
    "animando": ("movie", AZUL, "Animando"),
    "subtitulos": ("subtitles", AZUL, "Subtítulos"),
    "kit": ("content_copy", AZUL, "Kit de publicación"),
    "pendiente_ia": ("wifi_off", NARANJA, "Pendiente de conexión"),
    "interrumpido": ("pause_circle", NARANJA, "Se interrumpió"),
    "listo": ("task_alt", VERDE, "Listo"),
    "fallo": ("cancel", ROJO, "Falló"),
}
ESTADOS_QUE_PENDEN = ("pendiente_ia", "interrumpido", "fallo")
NOMBRES_ESTADO = {
    "pensando_ideas": "Pensando las ideas",
    "en_curso": "En curso",
    "pendiente_ia": "Pendiente de conexión",
    "interrumpido": "Interrumpido",
    "listo": "Listo",
    "fallo": "Terminó con errores",
    "descartado": "Descartado",
}


def _sin_prefijo(texto: str) -> str:
    encontrado = VIDEO_DE.match(texto)
    return encontrado.group(3) if encontrado else texto


def _nombre_estado(estado: str) -> str:
    return NOMBRES_ESTADO.get(estado, estado.replace("_", " ").capitalize())


def _fecha(valor: object) -> str:
    texto = str(valor or "")
    return f"{texto[8:10]}-{texto[5:7]} {texto[11:16]}" if len(texto) >= 16 else texto


def _hora(valor: object) -> str:
    texto = str(valor or "")
    return texto[11:16] if len(texto) >= 16 else texto
```

- [ ] **Step 2: Agrega la zona de cola al final de `_pantalla_inicio`**

Al final de `_pantalla_inicio`, **con la misma indentación que `with ui.card(...)`** (dentro de `zona_inicio`, fuera de la tarjeta), agrega:

```python
        self.zona_cola = ui.column().classes("w-full gap-3")
        self._dibujar_cola()
```

- [ ] **Step 3: Reemplaza `_asegurar_filas` y `_marcar_filas` por las filas con barra**

```python
    def _asegurar_filas(self, total: int) -> None:
        """Una fila por video del lote, la primera vez que sabemos cuántos son."""
        if len(self.filas) == total:
            return
        self.filas_videos.clear()
        self.filas, self.titulos = [], [""] * total
        with self.filas_videos:
            for n in range(total):
                with ui.row().classes("w-full items-center gap-3 no-wrap border-t pt-3"):
                    icono = ui.icon("radio_button_unchecked").set_text_color(GRIS)
                    with ui.column().classes("gap-1 flex-1"):
                        titulo = ui.label(f"Video {n + 1}").classes("font-bold")
                        estado = ui.label("En espera").classes("tpi-ayuda text-sm")
                        barra = ui.linear_progress(value=0, show_value=False).props(
                            "size=6px rounded"
                        ).classes("w-full")
                    self.filas.append(
                        {"icono": icono, "titulo": titulo, "estado": estado, "barra": barra}
                    )

    def _marcar_fila(self, numero: int, datos: dict) -> None:
        fila = self.filas[numero - 1]
        estado = str(datos.get("estado") or "en_cola")
        icono, color, etiqueta = ESTADOS_FILA.get(estado, ESTADOS_FILA["en_cola"])
        detalle = _sin_prefijo(str(datos.get("detalle") or ""))
        if detalle and estado in ESTADOS_QUE_PENDEN:
            etiqueta = f"{etiqueta} · {detalle}"
        fila["icono"].set_name(icono).set_text_color(color)
        fila["estado"].text = etiqueta
        fila["barra"].value = 1.0 if estado == "listo" else float(datos.get("avance") or 0.0)
        if estado == "listo":
            fila["barra"].props("color=positive")
        elif estado in ESTADOS_QUE_PENDEN:
            fila["barra"].props("color=warning")
        else:
            fila["barra"].props("color=primary")
```

Además, en `_pantalla_trabajo` cambia el texto de la pista (hoy promete un solo reintento de 60 s):

```python
                ui.label(
                    "Si la IA está saturada, espera y reintenta sola: el video queda pendiente hasta "
                    "que vuelva la conexión."
                ).classes("tpi-ayuda")
```

- [ ] **Step 4: Reemplaza `_avance` por la versión por video**

```python
    def _avance(self, t: Tarea) -> None:
        self.barra.value = t.avance
        self.porcentaje.text = f"{round(t.avance * 100)} %"
        self.detalle.text = _sin_prefijo(t.detalle or "") or t.texto_etapa
        if not t.videos:
            return
        total = max((int(d.get("total") or 0) for d in t.videos.values()), default=0) or len(
            t.videos
        )
        self._asegurar_filas(total)
        for numero, datos in t.videos.items():
            if not 1 <= numero <= len(self.filas):
                continue
            encontrado = TITULO.search(str(datos.get("detalle") or ""))
            if encontrado:
                self.titulos[numero - 1] = encontrado.group(1)
            if self.titulos[numero - 1]:
                self.filas[numero - 1]["titulo"].text = self.titulos[numero - 1]
            self._marcar_fila(numero, datos)
```

- [ ] **Step 5: Agrega la tarjeta «Cola de videos» y sus acciones**

Agrega estos métodos antes de `_pantalla_resultado`:

```python
    # ── la cola persistente ────────────────────────────────────────────────────────────

    def _dibujar_cola(self) -> None:
        self.zona_cola.clear()
        if TAREAS.ocupado():
            self.zona_cola.set_visibility(False)
            return
        datos = cola.cargar()
        if datos.get("version") != cola.VERSION:
            # La escribió una versión más nueva del motor: se muestra, no se sobrescribe.
            with self.zona_cola:
                ui.label(
                    "La cola la escribió una versión más nueva del motor. Actualiza con git pull."
                ).classes("tpi-ayuda")
            self.zona_cola.set_visibility(True)
            return
        lotes = cola.lotes_visibles()
        if not lotes:
            self.zona_cola.set_visibility(False)
            return
        self.zona_cola.set_visibility(True)
        with self.zona_cola:
            ui.label("Cola de videos").classes("tpi-titulo text-lg")
            for lote in reversed(lotes):
                self._tarjeta_lote(lote)

    def _tarjeta_lote(self, lote: dict) -> None:
        estado = str(lote.get("estado") or "")
        activo = estado in ("pensando_ideas", "en_curso")
        with ui.card().classes("tpi-hoja w-full p-4 gap-2"):
            with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                with ui.column().classes("gap-0"):
                    ui.label(str(lote.get("tema") or "Un video")).classes("font-bold")
                    ui.label(
                        f"{_fecha(lote.get('creado'))} · {_nombre_estado(estado)}"
                    ).classes("tpi-ayuda text-sm")
                with ui.row().classes("gap-2"):
                    if not activo and estado != "listo":
                        ui.button(
                            "Reanudar",
                            icon="play_arrow",
                            on_click=lambda l=lote: self._reanudar_lote(l["id"]),
                        ).props("outline dense")
                    if not activo:
                        ui.button(
                            "Descartar",
                            icon="delete_outline",
                            on_click=lambda l=lote: self._confirmar_descarte(l),
                        ).props("flat dense")
            for video in lote.get("videos", []):
                self._fila_cola(video)
            if estado == "listo":
                ui.button(
                    "Abrir la carpeta",
                    icon="folder_open",
                    on_click=lambda: abrir_en_mac(raiz_proyecto() / "salida"),
                ).props("outline dense")

    def _fila_cola(self, video: dict) -> None:
        estado = str(video.get("estado") or "en_cola")
        icono, color, etiqueta = ESTADOS_FILA.get(estado, ESTADOS_FILA["en_cola"])
        idea = video.get("idea") or {}
        titulo = str(idea.get("titulo") or f"Video {video.get('posicion', '?')}")
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.icon(icono, size="18px").set_text_color(color)
            with ui.column().classes("gap-0 flex-1"):
                ui.label(titulo).classes("text-sm")
                extra = ""
                if estado == "pendiente_ia" and video.get("proximo_intento"):
                    extra = f" · reintento {_hora(video['proximo_intento'])}"
                ui.label(f"{etiqueta}{extra}").classes("tpi-ayuda text-xs")
                if estado == "fallo" and video.get("error"):
                    ui.label(str(video["error"])).classes("text-xs").style(f"color:{ROJO}")
                if estado != "listo":
                    ui.linear_progress(
                        value=float(video.get("avance") or 0.0), show_value=False
                    ).props("size=4px rounded").classes("w-full")
            if estado == "fallo" and idea:
                ui.button(
                    "Intentar solo este",
                    icon="refresh",
                    on_click=lambda i=idea: self._arrancar_uno(i),
                ).props("flat dense")
            if estado == "listo" and (video.get("hitos") or {}).get("video"):
                ruta = Path(str(video["hitos"]["video"].get("video") or ""))
                if ruta.exists():
                    ui.button(
                        "Ver video", icon="movie", on_click=lambda r=ruta: abrir_en_mac(r)
                    ).props("flat dense")

    def _reanudar_lote(self, lote_id: str) -> None:
        self._correr(["lote", "--reanudar", "--cola-id", lote_id], "Reanudar cola")

    def _confirmar_descarte(self, lote: dict) -> None:
        with ui.dialog() as dialogo, ui.card().classes("gap-2"):
            ui.label(f"¿Sacar de la cola «{lote.get('tema') or 'este lote'}»?").classes("font-bold")
            ui.label("Los videos que ya salieron no se borran.").classes("tpi-ayuda")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Sí, sacarlo", on_click=lambda: self._descartar(lote["id"], dialogo)
                ).props("color=negative")
                ui.button("Mejor no", on_click=dialogo.close).props("flat")
        dialogo.open()

    def _descartar(self, lote_id: str, dialogo) -> None:
        try:
            cola.descartar_lote(lote_id)
        except ErrorMotor as e:
            ui.notify(e.mensaje, type="warning")
        dialogo.close()
        self._dibujar_cola()
```

- [ ] **Step 6: Ajusta `_correr`, `_mirar` y `_mostrar_resultado`**

En `_correr`, no hace falta tocar la tarjeta: `zona_cola` vive dentro de `zona_inicio`, que ya se oculta
mientras se trabaja. (La tarjeta se vuelve a dibujar al terminar, en `_mirar`.)

En `_mirar`, justo después de `self.zona_inicio.set_visibility(True)` (así también se redibuja cuando el
trabajo se canceló), agrega:

```python
        self._dibujar_cola()
```

En `_mostrar_resultado`, al principio, agrega:

```python
        if t.resultado.get("pendiente"):
            self.zona_resultado.clear()
            self.zona_resultado.set_visibility(False)
            self.zona_inicio.set_visibility(True)
            self._dibujar_cola()
            ui.notify(
                "Quedó pendiente de conexión. Se reanuda solo cuando vuelva la IA.", type="info"
            )
            return
```

- [ ] **Step 7: Reanudación automática al abrir el panel**

En `src/tpi_videos/panel/app.py`, agrega antes de `iniciar`:

```python
async def _reanudar_cola() -> None:
    """Al abrir el panel: lo que quedó esperando a la IA se retoma solo (sin tocar renders a medias)."""
    from .. import cola, ia

    if TAREAS.ocupado() or cola.candado_tomado():
        return
    cola.normalizar_interrumpidos()
    if ia.obtener_clave() is None:
        return
    if cola.elegir_lote(solo_pendientes=True) is None:
        return
    TAREAS.lanzar("Reanudar cola", ["lote", "--reanudar", "--solo-pendientes"])
```

Y en `iniciar`, después del bucle que registra las páginas:

```python
    app.on_startup(_reanudar_cola)
```

- [ ] **Step 8: Verificación automática que sí corre en CI**

Run: `python -m compileall -q src/tpi_videos/panel`
Expected: sin salida (sin errores de sintaxis)

Run: `PYTHONPATH=src python -m unittest discover -s pruebas -t . -v`
Expected: PASS (todos)

- [ ] **Step 9: Commit**

```bash
git add src/tpi_videos/panel/paginas/fabrica.py src/tpi_videos/panel/app.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: Fábrica con barras por video y tarjeta de cola que reanuda"
```

---

### Task 8: CI, versión y documentación

**Files:**
- Modify: `.github/workflows/render.yml`
- Modify: `pyproject.toml` (línea 7)
- Modify: `src/tpi_videos/__init__.py`
- Modify: `docs/PLAN.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: suite de tests en CI antes del render; paquete 0.10.0; documentación de la fase.

- [ ] **Step 1: Agrega el paso de pruebas al workflow**

En `.github/workflows/render.yml`, entre «Instalar el motor» y «Render de un guion de ejemplo»:

```yaml
      - name: Pruebas del motor
        # Cola, hitos, espera de la IA y eventos del panel: sin Manim, sin NiceGUI y sin internet.
        run: python -m unittest discover -s pruebas -t . -v
```

- [ ] **Step 2: Sube la versión**

`pyproject.toml`:

```toml
version = "0.10.0"
```

`src/tpi_videos/__init__.py`:

```python
__version__ = "0.10.0"
```

- [ ] **Step 3: Actualiza la documentación**

En `docs/PLAN.md`, agrega la fila del módulo en la tabla, después de `ideas.py`:

```markdown
| `cola.py` | Cola persistente (`salida/.cola/trabajos.json`): estado, fase, avance e hitos de cada video, candado de proceso y reanudación |
```

Y agrega el punto 11 al final de la hoja de ruta:

```markdown
11. ✅ **v0.10 · Cola y progreso:** cada video del lote tiene su barra, su fase y su estado en la Fábrica.
    El estado vive en `salida/.cola/trabajos.json` (escritura atómica y candado), los hitos (guion, video,
    kit) evitan repetir trabajo y la IA se espera con 60 s, 2 min, 5 min y luego cada 5 min, sin límite.
    Al reabrir el panel se retoma solo lo pendiente de conexión; un render interrumpido se reanuda con un
    botón. `tpi lote --reanudar` hace lo mismo desde la terminal.
    Spec: `docs/superpowers/specs/2026-10-26-cola-y-progreso-design.md`.
```

- [ ] **Step 4: Verifica todo junto**

Run: `PYTHONPATH=src python -m unittest discover -s pruebas -t . -v`
Expected: PASS (todos)

Run: `python -m compileall -q src/tpi_videos`
Expected: sin salida

Run: `PYTHONPATH=src python -m tpi_videos lote --help`
Expected: aparece `--reanudar` en la ayuda

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/render.yml pyproject.toml src/tpi_videos/__init__.py docs/PLAN.md
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "chore: pruebas en CI, versión 0.10.0 y documentación de la cola"
```

---

### Task 9: Verificación final y Pull Request

**Files:** ninguno (solo verificación).

- [ ] **Step 1: Corre la suite completa dos veces** (la cola escribe archivos: no debe depender del orden)

Run: `PYTHONPATH=src python -m unittest discover -s pruebas -t . -v`
Expected: PASS (todos), sin archivos nuevos en `salida/.cola/` del repo (los tests usan `TPI_RAIZ`)

Run: `PYTHONPATH=src python -m unittest discover -s pruebas -t . -v`
Expected: PASS (todos), los mismos

- [ ] **Step 2: Revisa que no quedó basura en el repo**

Run: `git status --short`
Expected: solo los archivos de las tareas, nada de `salida/.cola/`

- [ ] **Step 3: Publica la rama**

```bash
git push -u origin feat/cola-y-progreso
```

- [ ] **Step 4: Abre el Pull Request** (con la API: `gh` no está instalado)

Escribe el cuerpo con la herramienta Write en `.pr-body.json`, con los campos `"title"`, `"head": "feat/cola-y-progreso"` y `"base": "main"`, y este texto como `"body"`:

```markdown
## Qué hace

- Guarda la cola en `salida/.cola/trabajos.json` (escritura atómica, candado y poda de lo viejo).
- Cada video tiene barra, fase y estado propios en la Fábrica.
- Los errores transitorios de Gemini ya no botan el video: se espera 60 s, 2 min, 5 min y luego cada 5 min.
- Hitos de guion, video y kit: al reanudar no se repite lo que ya salió.
- Al abrir el panel se retoma solo lo pendiente de conexión; lo interrumpido a mitad de render se reanuda
  con un botón.
- `tpi lote --reanudar` hace lo mismo desde la terminal.

## Pruebas

- [ ] `python -m unittest discover -s pruebas -t . -v`
- [ ] CI: render de ejemplo y clips de gancho sin cambios
- [ ] Manual en el Mac: barras por video, corte de internet, cierre y reapertura del panel

Spec: `docs/superpowers/specs/2026-10-26-cola-y-progreso-design.md`
```

Y envíalo sin imprimir el token:

```bash
TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n 's/^password=//p')
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/paillamilm-blip/tuprofeindustrial-videos/pulls \
  --data-binary @.pr-body.json
rm -f .pr-body.json
```

Expected: la respuesta trae `"html_url"`. No fusionar: el PR lo revisa y fusiona el usuario.

---

## Notas de ejecución

- **Windows local:** los tests corren con `python -m unittest discover -s pruebas -t . -v`; el panel y el render real solo se comprueban en el Mac y en CI.
- **Nunca borres `salida/` para «arreglar» la cola:** el motor ignora los hitos cuyos archivos faltan y rehace solo esa etapa.
- **El candado de los tests** debe soltarse siempre en `finally`; si un test falla a mitad, el `tearDown` borra la carpeta temporal completa.
- **La escritura de la cola** la hace únicamente el proceso `tpi lote`; el panel solo lee (salvo `descartar`), para no competir con el candado.
