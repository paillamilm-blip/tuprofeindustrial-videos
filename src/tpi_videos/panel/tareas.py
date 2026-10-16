"""Trabajos pesados del panel: ejecuta comandos ``tpi … --progreso-json`` en un proceso aparte.

Uno a la vez (crear un video usa todo el computador). El estado es global, así cualquier página (o una
pestaña recargada) ve el avance. Cancelar detiene también los programas que el comando abrió
(LaTeX, FFmpeg).
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..errores import ErrorMotor

ETAPAS = {
    "preparando": "Preparando",
    "animacion": "Animando",
    "subtitulos": "Subtítulos",
    "video final": "Uniendo el video",
    "listo": "Listo",
    "redactando": "La IA está escribiendo",
    "publicando": "Kit de publicación",
}


@dataclass
class Tarea:
    nombre: str
    args: list[str]
    etapa: str = "preparando"
    avance: float = 0.0
    detalle: str = ""
    resultado: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None  # {"mensaje": …, "ayuda": …}
    registro: list[str] = field(default_factory=list)  # lo que el comando escribió para personas
    terminada: bool = False
    cancelada: bool = False
    inicio: float = field(default_factory=time.time)
    fin: float | None = None
    proceso: asyncio.subprocess.Process | None = None

    @property
    def ok(self) -> bool:
        return self.terminada and self.error is None and not self.cancelada

    def reciente(self, segundos: float = 8.0) -> bool:
        return self.fin is not None and time.time() - self.fin < segundos

    @property
    def texto_etapa(self) -> str:
        nombre = ETAPAS.get(self.etapa, self.etapa.capitalize())
        return f"{nombre}: {self.detalle}" if self.detalle and self.etapa != "listo" else nombre


class Tareas:
    def __init__(self) -> None:
        self.actual: Tarea | None = None

    def ocupado(self) -> bool:
        return self.actual is not None and not self.actual.terminada

    async def ejecutar(
        self, nombre: str, args: list[str], al_cambiar: Callable[[Tarea], Any] | None = None
    ) -> Tarea:
        """Ejecuta ``tpi <comando> --progreso-json <resto>`` y devuelve la tarea terminada."""
        if self.ocupado():
            raise ErrorMotor("Ya hay un trabajo en curso.", ayuda="Espera a que termine o cancélalo.")
        tarea = Tarea(nombre=nombre, args=args)
        self.actual = tarea
        entorno = dict(os.environ, PYTHONUNBUFFERED="1", NO_COLOR="1", COLUMNS="120")
        # --progreso-json va junto al comando: después puede venir «--» (un enunciado que empieza con «-»)
        comando = [args[0], "--progreso-json", *args[1:]]
        try:
            tarea.proceso = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "tpi_videos", *comando,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=entorno,
                start_new_session=True,  # así se puede detener todo junto (LaTeX, FFmpeg)
                limit=4 * 1024 * 1024,  # líneas largas (ej. un registro de LaTeX) no cortan la lectura
            )  # fmt: skip
        except OSError as e:
            tarea.error = {"mensaje": f"No pude iniciar el motor: {e}", "ayuda": "Revisa ./tpi doctor"}
            return self._cerrar(tarea, al_cambiar)

        async def leer_salida() -> None:
            assert tarea.proceso and tarea.proceso.stdout
            async for crudo in tarea.proceso.stdout:
                linea = crudo.decode("utf-8", errors="replace").strip()
                try:
                    evento = json.loads(linea)
                except json.JSONDecodeError:
                    if linea:
                        tarea.registro.append(linea)
                    continue
                self._aplicar(tarea, evento)
                if al_cambiar:
                    al_cambiar(tarea)

        async def leer_errores() -> None:
            assert tarea.proceso and tarea.proceso.stderr
            async for crudo in tarea.proceso.stderr:
                linea = crudo.decode("utf-8", errors="replace").rstrip()
                if linea.strip():
                    tarea.registro.append(linea)
                    del tarea.registro[:-300]

        await asyncio.gather(leer_salida(), leer_errores())
        codigo = await tarea.proceso.wait()
        if codigo != 0 and tarea.error is None and not tarea.cancelada:
            final = "\n".join(tarea.registro[-6:])
            tarea.error = {"mensaje": "El motor terminó con un error.", "ayuda": final or None}
        return self._cerrar(tarea, al_cambiar)

    @staticmethod
    def _aplicar(tarea: Tarea, evento: dict[str, Any]) -> None:
        etapa = evento.get("etapa", "")
        if etapa == "error":
            tarea.error = {"mensaje": evento.get("mensaje", "Error"), "ayuda": evento.get("ayuda")}
            return
        if etapa in ("resultado", "guion"):
            tarea.resultado.update({k: v for k, v in evento.items() if k not in ("etapa", "avance")})
            return
        tarea.etapa = etapa or tarea.etapa
        if evento.get("avance"):  # los avisos de la IA no traen avance (0): no se retrocede
            tarea.avance = max(tarea.avance, float(evento["avance"]))
        tarea.detalle = str(evento.get("detalle", ""))

    def _cerrar(self, tarea: Tarea, al_cambiar: Callable[[Tarea], Any] | None) -> Tarea:
        tarea.terminada = True
        tarea.fin = time.time()
        if tarea.ok:
            tarea.avance, tarea.etapa = 1.0, "listo"
        if al_cambiar:
            al_cambiar(tarea)
        return tarea

    def cancelar(self) -> None:
        t = self.actual
        if t is None or t.terminada or t.proceso is None:
            return
        t.cancelada = True
        try:
            os.killpg(t.proceso.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


async def consultar(args: list[str], segundos: float = 180) -> dict[str, Any]:
    """Un comando rápido que no ocupa la fila de trabajos (ej. el diagnóstico): su resultado final."""
    proceso = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tpi_videos", args[0], "--progreso-json", *args[1:],
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        env=dict(os.environ, PYTHONUNBUFFERED="1", NO_COLOR="1"), limit=4 * 1024 * 1024,
    )  # fmt: skip
    try:
        salida, _ = await asyncio.wait_for(proceso.communicate(), timeout=segundos)
    except TimeoutError:
        proceso.kill()
        raise ErrorMotor("El comando tardó demasiado.") from None
    final: dict[str, Any] = {}
    for linea in salida.decode("utf-8", errors="replace").splitlines():
        try:
            evento = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if evento.get("etapa") == "error":
            raise ErrorMotor(evento.get("mensaje", "Error"), ayuda=evento.get("ayuda"))
        if evento.get("etapa") == "resultado":
            final = evento
    return final


TAREAS = Tareas()
