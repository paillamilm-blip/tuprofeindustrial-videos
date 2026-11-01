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
    "esperando_ia": "Esperando conexión",
    "publicando": "Kit de publicación",
}


@dataclass
class Tarea:
    nombre: str
    args: list[str]
    etapa: str = "preparando"
    avance: float = 0.0
    detalle: str = ""
    videos: dict[int, dict[str, Any]] = field(default_factory=dict)  # avance y fase de cada video
    cola_id: str | None = None
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
        self._en_curso: asyncio.Task | None = None

    def ocupado(self) -> bool:
        return self.actual is not None and not self.actual.terminada

    def _prender(self, nombre: str, args: list[str]) -> Tarea:
        if self.ocupado():
            raise ErrorMotor("Ya hay un trabajo en curso.", ayuda="Espera a que termine o cancélalo.")
        tarea = Tarea(nombre=nombre, args=args)
        self.actual = tarea
        return tarea

    def lanzar(self, nombre: str, args: list[str]) -> Tarea:
        """Prende el trabajo y no espera por él: la página lo mira con un temporizador.

        El trabajo le pertenece a la app, no a la pestaña: si cierra (o navega a otra página), el
        video se termina igual y el resultado queda en ``TAREAS.actual`` para cuando se vuelva.
        """
        tarea = self._prender(nombre, args)
        self._en_curso = asyncio.create_task(self._correr(tarea, None))
        return tarea

    async def ejecutar(
        self, nombre: str, args: list[str], al_cambiar: Callable[[Tarea], Any] | None = None
    ) -> Tarea:
        """Ejecuta ``tpi <comando> --progreso-json <resto>`` y devuelve la tarea terminada."""
        tarea = self._prender(nombre, args)
        self._en_curso = asyncio.create_task(self._correr(tarea, al_cambiar))
        return await asyncio.shield(self._en_curso)

    async def _correr(self, tarea: Tarea, al_cambiar: Callable[[Tarea], Any] | None) -> Tarea:
        entorno = dict(os.environ, PYTHONUNBUFFERED="1", NO_COLOR="1", COLUMNS="120")
        # --progreso-json va junto al comando: después puede venir «--» (un enunciado que empieza con «-»)
        comando = [tarea.args[0], "--progreso-json", *tarea.args[1:]]
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

        try:
            await asyncio.gather(leer_salida(), leer_errores())
            codigo = await tarea.proceso.wait()
            if codigo != 0 and tarea.error is None and not tarea.cancelada:
                final = "\n".join(tarea.registro[-6:])
                tarea.error = {"mensaje": "El motor terminó con un error.", "ayuda": final or None}
        except asyncio.CancelledError:
            tarea.cancelada = True
            raise
        except Exception as e:  # leer, «_aplicar» o el callback fallaron: el trabajo se cierra igual,
            if tarea.error is None:  # si no, TAREAS.actual quedaría «en curso» para siempre y todo se tapa
                tarea.error = {"mensaje": "El trabajo se cortó.", "ayuda": str(e)}
        finally:
            if tarea.proceso is not None and tarea.proceso.returncode is None:
                try:
                    os.killpg(tarea.proceso.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
            self._cerrar(tarea, al_cambiar)
        return tarea

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
                    datos["avance"] = max(float(datos.get("avance") or 0.0), float(evento["video_avance"]))
                for campo in ("fase", "estado", "detalle"):
                    if evento.get(campo) is not None:
                        datos[campo] = evento[campo]

    def _cerrar(self, tarea: Tarea, al_cambiar: Callable[[Tarea], Any] | None) -> Tarea:
        tarea.terminada = True
        tarea.fin = time.time()
        if tarea.ok:
            tarea.avance, tarea.etapa = 1.0, "listo"
        if al_cambiar:
            try:
                al_cambiar(tarea)
            except Exception:  # un callback roto no puede impedir cerrar el trabajo y liberar la fila
                pass
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


async def consultar(
    args: list[str],
    segundos: float = 180,
    al_evento: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Un comando rápido que no ocupa la fila de trabajos (ej. el diagnóstico): su resultado final.

    ``al_evento`` recibe cada aviso del motor *mientras sale*, no solo el final: así la pantalla puede
    pintar el proceso en vivo en vez de dejar la pared quieta durante el viaje a la IA.
    """
    proceso = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tpi_videos", args[0], "--progreso-json", *args[1:],
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        env=dict(os.environ, PYTHONUNBUFFERED="1", NO_COLOR="1"), limit=4 * 1024 * 1024,
    )  # fmt: skip
    final: dict[str, Any] = {}
    try:
        async with asyncio.timeout(segundos):
            assert proceso.stdout is not None
            async for crudo in proceso.stdout:
                linea = crudo.decode("utf-8", errors="replace").strip()
                if not linea:
                    continue
                try:
                    evento = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                if evento.get("etapa") == "error":
                    raise ErrorMotor(evento.get("mensaje", "Error"), ayuda=evento.get("ayuda"))
                if evento.get("etapa") == "resultado":
                    final = evento
                if al_evento:
                    al_evento(evento)
            await proceso.wait()
    except TimeoutError:
        raise ErrorMotor("El comando tardó demasiado.") from None
    finally:
        if proceso.returncode is None:  # el aviso se fue antes de terminar: no dejamos un proceso suelto
            proceso.kill()
    return final


TAREAS = Tareas()
